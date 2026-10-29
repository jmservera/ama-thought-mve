#!/usr/bin/env node
import { randomUUID } from 'node:crypto';
import { resolve, isAbsolute } from 'node:path';
import { pathToFileURL } from 'node:url';
import { mkdir } from 'node:fs/promises';
import { ToolSet } from '@github/copilot-sdk';
import { LIMITS, makeRuntime } from './runtime-guard.mjs';

export const SDK_VERSION = '1.0.28';
export const CLI_VERSION = '1.0.105';
export const PROTOCOL_VERSION = 3;
const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
const keysOnly = (value, names) => object(value) && Object.keys(value).every(key => names.includes(key));
const text = value => typeof value === 'string' && value.length > 0;
const nano = value => Number.isSafeInteger(value) && value >= 0;
const fault = code => Object.assign(new Error(code), { transportCode: code });

export function validateRequest(request) {
  if (!keysOnly(request, ['model', 'reasoningEffort', 'prompt', 'remainingSeconds',
    'maxAiCredits', 'cliPath', 'baseDirectory']) ||
    !text(request.model) || request.model.length > 200 ||
    request.reasoningEffort !== 'medium' || !text(request.prompt) ||
    !Number.isFinite(request.remainingSeconds) || request.remainingSeconds <= 0 ||
    request.remainingSeconds > 86400 ||
    !Number.isFinite(request.maxAiCredits) || request.maxAiCredits <= 0 ||
    !text(request.cliPath) || !isAbsolute(request.cliPath) ||
    !text(request.baseDirectory) || !isAbsolute(request.baseDirectory))
    throw fault('invalid_initial_request');
  return request;
}

export function validateArguments(args, remainingSeconds) {
  return keysOnly(args, ['command', 'timeoutSeconds']) && text(args.command) &&
    Buffer.byteLength(args.command) <= 64 * 1024 && !args.command.includes('\0') &&
    Number.isFinite(args.timeoutSeconds) && args.timeoutSeconds > 0 &&
    args.timeoutSeconds <= remainingSeconds;
}

export function permissionHandler(sessionId) {
  return (request, invocation) => {
    const prompt = invocation?.promptRequest;
    const promptValid = prompt === undefined ||
      (keysOnly(prompt, ['kind', 'toolName', 'toolDescription', 'args', 'toolCallId']) &&
        prompt.kind === 'custom-tool' && prompt.toolName === request?.toolName &&
        prompt.toolCallId === request?.toolCallId &&
        prompt.toolDescription === request?.toolDescription &&
        JSON.stringify(prompt.args) === JSON.stringify(request?.args));
    const permitted = keysOnly(request, ['kind', 'toolName', 'toolDescription', 'args',
      'toolCallId', 'skipPermission', 'managedApprovalRequired']) &&
      keysOnly(invocation, ['sessionId', 'managedSettingsEnabled', 'promptRequest']) &&
      invocation.sessionId === sessionId && request.kind === 'custom-tool' &&
      request.toolName === 'isolated_exec' && text(request.toolDescription) &&
      (request.skipPermission === undefined || request.skipPermission === false) &&
      (request.managedApprovalRequired === undefined || request.managedApprovalRequired === false) &&
      (invocation.managedSettingsEnabled === undefined || invocation.managedSettingsEnabled === false) &&
      promptValid &&
      text(request.toolCallId) && validateArguments(request.args, Infinity);
    return { kind: permitted ? 'approved' : 'denied-no-approval-rule-and-could-not-request-from-user' };
  };
}

export class InputRecords {
  constructor(onRecord, onFailure, limits = LIMITS) {
    this.onRecord = onRecord;
    this.onFailure = onFailure;
    this.limits = limits;
    this.buffer = Buffer.alloc(0);
    this.total = 0;
    this.failed = false;
  }
  push(chunk) {
    if (this.failed) return;
    try {
      this.total += chunk.length;
      if (this.total > this.limits.events) throw fault('input_aggregate_limit');
      let offset = 0;
      while (offset < chunk.length) {
        const newline = chunk.indexOf(10, offset);
        const end = newline < 0 ? chunk.length : newline;
        const part = chunk.subarray(offset, end);
        if (this.buffer.length + part.length > this.limits.record)
          throw fault('input_record_limit');
        this.buffer = Buffer.concat([this.buffer, part]);
        if (newline < 0) return;
        if (!this.buffer.length) throw fault('empty_record');
        const record = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(this.buffer));
        this.buffer = Buffer.alloc(0);
        this.onRecord(record);
        offset = newline + 1;
      }
    } catch (error) {
      this.failed = true;
      this.onFailure(error);
    }
  }
}

export class OutputRecords {
  constructor(stream, onFailure, limits = LIMITS) {
    this.stream = stream;
    this.onFailure = onFailure;
    this.limits = limits;
    this.queue = [];
    this.queuedBytes = 0;
    this.eventBytes = 0;
    this.active = false;
    this.waiters = [];
    this.failed = false;
    this.onError = () => this.fail(fault('parent_output_closed'));
    this.onClose = () => this.fail(fault('parent_output_closed'));
    stream.on('error', this.onError);
    stream.on('close', this.onClose);
  }
  fail(error) {
    if (this.failed) return;
    this.failed = true;
    this.queue = [];
    this.queuedBytes = 0;
    this.active = false;
    this.onFailure(error);
    this.settle();
  }
  write(record) {
    if (this.failed) throw fault('parent_output_closed');
    const line = JSON.stringify(record) + '\n';
    const size = Buffer.byteLength(line);
    if (size > this.limits.record) throw fault('output_record_limit');
    if (record.type === 'event') {
      this.eventBytes += size;
      if (this.eventBytes > this.limits.events) throw fault('event_journal_limit');
    }
    if (this.queuedBytes + size > this.limits.events) throw fault('output_queue_limit');
    this.queue.push({ line, size });
    this.queuedBytes += size;
    this.pump();
  }
  pump() {
    if (this.active || this.failed) return;
    const next = this.queue.shift();
    if (!next) return this.settle();
    this.active = true;
    try {
      this.stream.write(next.line, error => {
        this.active = false;
        this.queuedBytes -= next.size;
        if (error) this.fail(fault('parent_output_closed'));
        else this.pump();
      });
    } catch {
      this.active = false;
      this.fail(fault('parent_output_closed'));
    }
  }
  settle() {
    if (!this.active && !this.queue.length) {
      for (const resolveWait of this.waiters.splice(0)) resolveWait();
    }
  }
  flush() {
    return !this.active && !this.queue.length ? Promise.resolve() :
      new Promise(resolveWait => this.waiters.push(resolveWait));
  }
  dispose() {
    this.stream.off('error', this.onError);
    this.stream.off('close', this.onClose);
  }
}

export class Evidence {
  constructor(request, sessionId) {
    this.request = request;
    this.sessionId = sessionId;
    this.models = new Set();
    this.efforts = new Set();
    this.calls = new Map();
    this.completeCalls = 0;
    this.reportedCalls = 0;
    this.routing = [];
    this.started = false;
    this.idle = false;
    this.shutdown = null;
    this.checkpoints = [];
    this.status = 'unavailable';
  }
  identity(model, effort) {
    if (text(model)) this.models.add(model);
    if (text(effort)) this.efforts.add(effort);
    if (model !== this.request.model || effort !== this.request.reasoningEffort)
      throw fault('actual_identity_unavailable_or_mismatched');
  }
  observe(event) {
    if (!object(event) || !text(event.id) || !text(event.type) || !object(event.data))
      throw fault('invalid_sdk_event');
    const data = event.data;
    if (event.agentId) throw fault('unexpected_subagent');
    if (data.sessionId !== undefined && data.sessionId !== this.sessionId)
      throw fault('event_session_mismatch');
    if (this.shutdown && event.type !== 'session.shutdown')
      throw fault('event_after_shutdown');
    if (event.type === 'session.start') {
      if (this.started || data.sessionId !== this.sessionId || data.copilotVersion !== CLI_VERSION ||
        data.sessionLimits?.maxAiCredits !== this.request.maxAiCredits)
        throw fault('session_configuration_mismatch');
      this.started = true;
      this.identity(data.selectedModel, data.reasoningEffort);
    } else if (event.type === 'session.model_change') {
      this.routing.push(data);
      this.identity(data.newModel, data.reasoningEffort);
      if (data.source === 'automatic' || data.cause) throw fault('unexpected_model_routing');
    } else if (event.type === 'assistant.usage') {
      this.identity(data.model, data.reasoningEffort);
      if (data.copilotUsage?.model !== undefined && data.copilotUsage.model !== data.model) {
        this.models.add(data.copilotUsage.model);
        throw fault('unexpected_billing_model');
      }
      if (data.isAuto || data.isByok || data.fusion) throw fault('unexpected_model_routing');
      const accounting = data.accounting;
      if (!object(accounting) || accounting.sourceSessionId !== this.sessionId ||
        !Number.isSafeInteger(accounting.sequence) || accounting.sequence < 1 ||
        !text(accounting.usageId)) throw fault('usage_correlation_unavailable');
      const previous = this.calls.get(accounting.sequence);
      if (previous && JSON.stringify(previous) !== JSON.stringify(data))
        throw fault('conflicting_usage_duplicate');
      this.calls.set(accounting.sequence, data);
      if (!previous && nano(data.copilotUsage?.totalNanoAiu)) {
        this.reportedCalls++;
        if (data.aiCreditsStatus === 'complete') this.completeCalls++;
      }
      this.status = this.completeCalls === this.calls.size ? 'complete' :
        this.reportedCalls ? 'partial' : 'unavailable';
    } else if (event.type === 'session.usage_checkpoint') {
      if (!nano(data.totalNanoAiu) || !object(data.usageAccountingWatermarks) ||
        Object.keys(data.usageAccountingWatermarks).length !== 1 ||
        !nano(data.usageAccountingWatermarks[this.sessionId]))
        throw fault('checkpoint_correlation_unavailable');
      this.checkpoints.push(data);
    } else if (event.type === 'session.idle') {
      if (data.aborted) throw fault('session_aborted');
      this.idle = true;
    } else if (event.type === 'assistant.turn_start') {
      this.idle = false;
    } else if (event.type === 'session.shutdown') {
      if (!this.idle || data.shutdownType !== 'routine') throw fault('unexpected_shutdown');
      if (this.shutdown && JSON.stringify(this.shutdown) !== JSON.stringify(data))
        throw fault('conflicting_shutdown_duplicate');
      this.shutdown = data;
    } else if (['session.error', 'abort', 'model.call_failure', 'session.model_deselected',
      'session.truncation', 'session.handoff', 'session.instruction_update',
      'instruction.update',
      'skill.invoked', 'subagent.started', 'hook.start', 'tool.search_activated',
      'session.managed_plugin_progress'].includes(event.type) || event.type.startsWith('session.fusion') ||
      event.type.startsWith('assistant.fusion') || event.type.startsWith('mcp.') ||
      event.type.startsWith('subagent.') || event.type.startsWith('hook.') ||
      (event.type.startsWith('session.mcp_') && event.type !== 'session.mcp_servers_loaded') ||
      (event.type === 'system.notification' && data.kind?.type === 'instruction_discovered') ||
      (event.type === 'model.call_finished' && data.outcome !== 'success')) {
      throw fault('unexpected_runtime_activity');
    } else if (event.type === 'tool.execution_start' &&
      (data.toolName !== 'isolated_exec' || data.mcpServerName)) {
      throw fault('unexpected_tool');
    }
    const catalogs = {
      'session.skills_loaded': 'skills', 'session.custom_agents_updated': 'agents',
      'session.mcp_servers_loaded': 'servers', 'session.extensions_loaded': 'extensions',
    };
    const catalog = catalogs[event.type];
    if (catalog && (!Array.isArray(data[catalog]) || data[catalog].length))
      throw fault('unexpected_discovery');
  }
  receipt(errorCode = null) {
    const shutdown = this.shutdown;
    const sequences = [...this.calls.keys()].sort((a, b) => a - b);
    const calls = [...this.calls.values()];
    const sum = calls.reduce((total, call) => total + (call.copilotUsage?.totalNanoAiu ?? 0), 0);
    const watermarks = shutdown?.usageAccountingWatermarks;
    const metric = shutdown?.modelMetrics?.[this.request.model];
    const complete = !errorCode && this.started && this.idle && shutdown &&
      this.status === 'complete' && sequences.length > 0 &&
      sequences.every((sequence, index) => sequence === index + 1) &&
      new Set(calls.map(call => call.accounting.usageId)).size === calls.length &&
      object(watermarks) && Object.keys(watermarks).length === 1 &&
      watermarks[this.sessionId] === sequences.length &&
      nano(shutdown.totalNanoAiu) && nano(sum) && shutdown.totalNanoAiu === sum &&
      shutdown.currentModel === this.request.model &&
      object(shutdown.modelMetrics) && Object.keys(shutdown.modelMetrics).length === 1 &&
      metric?.requests?.count === calls.length && metric.totalNanoAiu === sum;
    const checkpointsConsistent = this.checkpoints.every(checkpoint =>
      checkpoint.totalNanoAiu <= sum &&
      checkpoint.usageAccountingWatermarks[this.sessionId] <= sequences.length);
    const certified = complete && checkpointsConsistent;
    return {
      session_id: this.sessionId,
      sdk_version: SDK_VERSION, cli_version: CLI_VERSION, protocol_version: PROTOCOL_VERSION,
      usage: {
        totalNanoAiu: certified ? sum : null,
        credits_complete: Boolean(certified),
        aiCreditsStatus: certified ? 'complete' : this.status === 'unavailable' ? 'unavailable' : 'partial',
      },
      actual_models: [...this.models],
      actual_reasoning_efforts: [...this.efforts],
      model_calls: calls.map(call => ({
        accounting: call.accounting, model: call.model,
        reasoningEffort: call.reasoningEffort ?? null,
        aiCreditsStatus: call.aiCreditsStatus ?? 'unavailable',
        totalNanoAiu: nano(call.copilotUsage?.totalNanoAiu) ? call.copilotUsage.totalNanoAiu : null,
      })),
      routing_changes: this.routing,
      protocol_error: errorCode || (certified ? null : 'complete_usage_evidence_unavailable'),
    };
  }
}

export function sessionConfig(request, sessionId, handler, onEvent) {
  return {
    sessionId, model: request.model, reasoningEffort: request.reasoningEffort,
    sessionLimits: { maxAiCredits: request.maxAiCredits },
    availableTools: new ToolSet().addCustom('isolated_exec'),
    excludedTools: new ToolSet().addBuiltIn('*').addMcp('*'),
    enableConfigDiscovery: false,
    enableExperimentalMode: false,
    infiniteSessions: { enabled: false },
    tools: [{
      name: 'isolated_exec',
      description: 'Run one shell command with timeoutSeconds in isolated /work. ' +
        'No host filesystem or network access. Each invocation uses a fresh bounded container; ' +
        'only filesystem state persists, not background processes.',
      parameters: {
        type: 'object', additionalProperties: false, required: ['command', 'timeoutSeconds'],
        properties: { command: { type: 'string', minLength: 1, maxLength: 65536 },
          timeoutSeconds: { type: 'number', exclusiveMinimum: 0 } },
      },
      defer: 'never',
      handler,
    }],
    onPermissionRequest: permissionHandler(sessionId),
    onEvent,
  };
}

export async function assertRuntime(client) {
  await client.start();
  const status = await client.getStatus();
  const ping = await client.ping();
  if (status.version !== CLI_VERSION || status.protocolVersion !== PROTOCOL_VERSION ||
    ping.protocolVersion !== PROTOCOL_VERSION) throw fault('runtime_pin_mismatch');
  const auth = await client.getAuthStatus();
  return { sdkVersion: SDK_VERSION, cliVersion: status.version, protocolVersion: ping.protocolVersion,
    isAuthenticated: auth.isAuthenticated === true,
    userAuthentication: ['user', 'gh-cli'].includes(auth.authType) };
}

function safeCode(error) {
  return error?.transportCode || 'sdk_failure';
}

export async function runTransport({ input = process.stdin, output = process.stdout,
  runtimeFactory = makeRuntime, limits = LIMITS } = {}) {
  let runtime;
  let pending;
  let evidence;
  let timer;
  let deadline = Date.now() + 30000;
  let initialized = false;
  let finished = false;
  let failure;
  const toolIds = new Set();
  let rejectFailure;
  let resolveInitial;
  const initial = new Promise(resolveInit => { resolveInitial = resolveInit; });
  const failed = new Promise((resolveFailure, reject) => { rejectFailure = reject; });
  // Failure may arrive before the first race (e.g. malformed initial input).
  failed.catch(() => {});
  const fail = error => {
    if (finished || failure) return;
    failure = fault(safeCode(error));
    rejectFailure(failure);
    if (pending) {
      pending.resolve({ stdout: '', stderr: 'Isolated tool interrupted.', exit_code: 1 });
      pending = null;
    }
  };
  const writer = new OutputRecords(output, fail, limits);
  timer = setTimeout(() => fail(fault('missing_initial_request')), 30000);
  const parser = new InputRecords(record => {
    if (!initialized) {
      const request = validateRequest(record);
      initialized = true;
      clearTimeout(timer);
      deadline = Date.now() + request.remainingSeconds * 1000;
      timer = setTimeout(() => fail(fault('original_deadline_exhausted')),
        Math.max(1, deadline - Date.now()));
      resolveInitial({ request, deadline });
      return;
    }
    if (!keysOnly(record, ['type', 'id', 'result']) || record.type !== 'tool_result' ||
      !pending || record.id !== pending.id || !object(record.result) ||
      typeof record.result.stdout !== 'string' || typeof record.result.stderr !== 'string' ||
      !Number.isSafeInteger(record.result.exit_code))
      throw fault('invalid_tool_result_correlation');
    if (Buffer.byteLength(JSON.stringify(record.result)) > limits.record - 4096)
      throw fault('tool_result_limit');
    const current = pending;
    pending = null;
    current.resolve(record.result);
  }, fail, limits);
  const onData = chunk => parser.push(Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk));
  const onEnd = () => fail(fault(parser.buffer.length ? 'truncated_control_record' : 'parent_disconnected'));
  const onError = () => fail(fault('parent_disconnected'));
  input.on('data', onData);
  input.on('end', onEnd);
  input.on('error', onError);
  input.on('close', onEnd);
  const onSignal = () => fail(fault('transport_interrupted'));
  process.on('SIGTERM', onSignal);
  process.on('SIGINT', onSignal);
  try {
    const { request } = await Promise.race([initial, failed]);
    if (failure) throw failure;
    evidence = new Evidence(request, randomUUID());
    runtime = await Promise.race([runtimeFactory(request, deadline), failed]);
    const { client } = runtime;
    const status = await Promise.race([assertRuntime(client), failed]);
    if (!status.isAuthenticated || !status.userAuthentication) throw fault('host_user_auth_unavailable');
    const config = sessionConfig(request, evidence.sessionId, async (args, invocation) => {
      const remaining = (deadline - Date.now()) / 1000;
      if (failure) return { textResultForLlm: 'Tool unavailable.', resultType: 'failure' };
      if (!keysOnly(invocation, ['sessionId', 'toolCallId', 'toolName', 'arguments',
        'availableTools', 'traceparent', 'tracestate', 'signal', 'agentId', 'requestId']) ||
        invocation.sessionId !== evidence.sessionId || invocation.toolName !== 'isolated_exec' ||
        invocation.agentId !== undefined || invocation.availableTools !== undefined) {
        fail(fault('tool_identity_mismatch'));
        return { textResultForLlm: 'Tool denied.', resultType: 'denied' };
      }
      if (!validateArguments(args, remaining))
        return { textResultForLlm: 'Invalid command or timeout; timeout must fit remaining time.',
          resultType: 'rejected' };
      if (pending) {
        fail(fault('pending_tool_limit'));
        return { textResultForLlm: 'Concurrent tool denied.', resultType: 'denied' };
      }
      const id = invocation.toolCallId;
      if (!text(id) || id.length > 200 || toolIds.has(id)) {
        fail(fault('invalid_tool_call_id'));
        return { textResultForLlm: 'Tool denied.', resultType: 'denied' };
      }
      toolIds.add(id);
      const onAbort = () => fail(fault('sdk_tool_aborted'));
      if (invocation.signal?.aborted) {
        onAbort();
        return { textResultForLlm: 'Tool interrupted.', resultType: 'failure' };
      }
      invocation.signal?.addEventListener('abort', onAbort, { once: true });
      const result = await new Promise(resolveResult => {
        pending = { id, resolve: resolveResult };
        try { writer.write({ type: 'tool', id, arguments: args }); }
        catch (error) { fail(error); }
      });
      invocation.signal?.removeEventListener('abort', onAbort);
      return { textResultForLlm: JSON.stringify(result),
        resultType: result.exit_code === 0 ? 'success' : 'failure' };
    }, event => {
      if (failure) return;
      try {
        writer.write({ type: 'event', sessionId: evidence.sessionId, event });
        evidence.observe(event);
      } catch (error) { fail(error); }
    });
    if (failure) throw failure;
    const session = await Promise.race([client.createSession(config), failed]);
    if (session.sessionId !== evidence.sessionId) throw fault('created_session_mismatch');
    if (!evidence.started) throw fault('session_identity_unavailable');
    await Promise.race([session.sendAndWait({ prompt: request.prompt },
      Math.max(1, deadline - Date.now())), failed]);
    if (!evidence.idle || pending) throw fault('session_not_idle');
    await Promise.race([session.rpc.shutdown({ type: 'routine' }), failed]);
  } catch (error) {
    fail(error);
  } finally {
    if (runtime) {
      try { await runtime.close(); }
      catch { failure ||= fault('runtime_cleanup_failure'); }
    }
    const flushBounded = async () => {
      let flushTimer;
      try {
        await Promise.race([writer.flush(), new Promise(resolveFlush => {
          flushTimer = setTimeout(() => {
            writer.fail(fault('output_deadline_exhausted'));
            output.destroy();
            resolveFlush();
          }, Math.max(1, deadline - Date.now()));
        })]);
      } finally { clearTimeout(flushTimer); }
    };
    // A terminal receipt is never queued ahead of an undrained event journal.
    await flushBounded();
    if (Date.now() >= deadline) failure ||= fault('original_deadline_exhausted');
    let receipt = evidence ? evidence.receipt(failure?.message) : {
      sdk_version: SDK_VERSION, usage: { totalNanoAiu: null, credits_complete: false,
        aiCreditsStatus: 'unavailable' }, actual_models: [], actual_reasoning_efforts: [],
      protocol_error: failure?.message || 'missing_initial_request',
    };
    let exitCode = receipt.usage.credits_complete ? 0 : 1;
    try {
      writer.write({ type: 'complete', receipt, exit_code: exitCode });
      await flushBounded();
    } catch (error) {
      fail(error);
    }
    if (failure && receipt.usage.credits_complete) {
      receipt = evidence.receipt(failure.message);
      exitCode = 1;
    }
    clearTimeout(timer);
    input.off('data', onData);
    input.off('end', onEnd);
    input.off('error', onError);
    input.off('close', onEnd);
    process.off('SIGTERM', onSignal);
    process.off('SIGINT', onSignal);
    finished = true;
    writer.dispose();
    return { receipt, exitCode };
  }
}

async function main() {
  if (process.argv[2] === '--check-runtime') {
    const args = process.argv.slice(3);
    if (args.length !== 4 || args[0] !== '--cli-path' || args[2] !== '--base-directory' ||
      !isAbsolute(args[1]) || !isAbsolute(args[3])) throw fault('invalid_check_runtime_arguments');
    await mkdir(args[3], { recursive: true, mode: 0o700 });
    const runtime = await makeRuntime({ cliPath: args[1], baseDirectory: args[3] }, Date.now() + 30000);
    try { process.stdout.write(JSON.stringify(await assertRuntime(runtime.client)) + '\n'); }
    finally { await runtime.close(); }
    return;
  }
  if (process.argv.length !== 2) throw fault('invalid_transport_arguments');
  const result = await runTransport();
  process.exitCode = result.exitCode;
  process.stdin.pause();
}

if (process.argv[1] && pathToFileURL(resolve(process.argv[1])).href === import.meta.url) {
  main().catch(error => {
    process.stderr.write(`transport: ${safeCode(error)}\n`);
    process.exitCode = 1;
    process.stdin.pause();
  });
}
