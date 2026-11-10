import test from 'node:test';
import assert from 'node:assert/strict';
import { PassThrough, Writable } from 'node:stream';
import { once } from 'node:events';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { mkdtemp, readFile, readdir, rm, stat, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { CopilotRequestHandler } from '@github/copilot-sdk';
import { Evidence, InputRecords, OutputRecords, assertRuntime, permissionHandler,
  runTransport, sessionConfig, validateArguments, WEBSOCKET_RESET_MESSAGE } from './transport.mjs';
import { RpcFrames, hostEnvironment, makeRuntime, prepareRuntimeDirectories } from './runtime-guard.mjs';

const request = (extra = {}) => ({ model: 'test-model', reasoningEffort: 'medium', prompt: 'test',
  remainingSeconds: 2, maxAiCredits: 173.5, cliPath: '/trusted/copilot',
  baseDirectory: '/trusted/sterile', ...extra });
const event = (type, data) => ({ id: crypto.randomUUID(), parentId: null,
  timestamp: new Date().toISOString(), type, data });
const start = (sid, req = request()) => event('session.start', {
  sessionId: sid, copilotVersion: '1.0.105', selectedModel: req.model,
  reasoningEffort: 'medium', sessionLimits: { maxAiCredits: req.maxAiCredits },
});
const usage = (sid, extra = {}) => event('assistant.usage', {
  model: 'test-model', reasoningEffort: 'medium', aiCreditsStatus: 'complete',
  accounting: { sourceSessionId: sid, sequence: 1, usageId: 'call-one' },
  copilotUsage: { totalNanoAiu: 123 }, ...extra,
});
const shutdown = sid => event('session.shutdown', {
  shutdownType: 'routine', currentModel: 'test-model', totalNanoAiu: 123,
  usageAccountingWatermarks: { [sid]: 1 },
  modelMetrics: { 'test-model': { totalNanoAiu: 123, requests: { count: 1 } } },
});

function fakeRuntime(options = {}) {
  const state = { closed: 0, created: 0, sent: 0, order: [] };
  const factory = async (req, deadline) => {
    state.deadline = deadline;
    const client = {
      async start() { state.order.push('start'); },
      async getStatus() { return { version: options.version || '1.0.105', protocolVersion: 3 }; },
      async ping() { return { protocolVersion: options.protocol || 3 }; },
      async getAuthStatus() { return { isAuthenticated: true, authType: 'user' }; },
      async createSession(config) {
        state.created++;
        if (options.createError) throw new Error('SDK response may contain sensitive details');
        state.config = config;
        state.order.push('create');
        config.onEvent(start(config.sessionId, req));
        return {
          sessionId: config.sessionId,
          async sendAndWait() {
            state.sent++;
            if (options.action) await options.action(config, state);
            if (options.hang) return new Promise(() => {});
            config.onEvent(usage(config.sessionId,
              typeof options.usage === 'function' ? options.usage(config.sessionId) : options.usage));
            config.onEvent(event('session.idle', {}));
          },
          rpc: {
            tools: {
              async initializeAndValidate() {},
              async getCurrentMetadata() {
                if (state.sent && options.finalMetadata) return options.finalMetadata;
                return options.metadata ?? { tools: [{ name: 'isolated_exec' }] };
              },
            },
            async shutdown() {
              config.onEvent(options.shutdown?.(config.sessionId) ?? shutdown(config.sessionId));
            },
          },
        };
      },
    };
    return { client, async close() {
      state.closed++;
      if (options.closeEvents) options.closeEvents(state.config);
    } };
  };
  return { factory, state };
}

async function runFake(options = {}, req = request(), limits) {
  const input = new PassThrough();
  const output = new PassThrough();
  const records = [];
  let buffer = '';
  output.on('data', chunk => {
    buffer += chunk.toString();
    let newline;
    while ((newline = buffer.indexOf('\n')) >= 0) {
      const record = JSON.parse(buffer.slice(0, newline));
      records.push(record);
      buffer = buffer.slice(newline + 1);
      if (record.type === 'tool' && !options.noToolResult) {
        const reply = () => input.write(JSON.stringify({ type: 'tool_result', id: record.id,
          result: options.toolReply?.(record) ??
            { stdout: 'bounded output', stderr: '', exit_code: 0 } }) + '\n');
        if (options.delayToolResult) setImmediate(reply);
        else reply();
      }
    }
  });
  const runtime = fakeRuntime(options);
  const running = runTransport({ input, output, runtimeFactory: runtime.factory, limits });
  input.write(JSON.stringify(req) + '\n');
  if (options.disconnect) setImmediate(() => input.destroy());
  const result = await running;
  input.destroy();
  output.destroy();
  return { ...result, records, state: runtime.state };
}

test('exact source-qualified tools, permission/session checks, shared limits and token-free environment', () => {
  const config = sessionConfig(request(), 'registered', () => {}, () => {});
  assert.deepEqual(config.availableTools.toArray(), ['custom:isolated_exec']);
  assert.deepEqual(config.excludedTools.toArray(), ['builtin:*', 'mcp:*']);
  assert.deepEqual(config.disabledMcpServers, ['github-mcp-server']);
  assert.deepEqual(config.sessionLimits, { maxAiCredits: 173.5 });
  assert.equal(config.enableConfigDiscovery, false);
  assert.equal(config.tools.length, 1);
  assert.equal(config.tools[0].skipPermission, undefined);
  assert.equal(config.systemMessage, undefined);
  const allow = permissionHandler('registered');
  const args = { command: 'pwd', timeoutSeconds: 1 };
  const permission = { kind: 'custom-tool', toolName: 'isolated_exec',
    toolDescription: 'isolated', toolCallId: 'one', args };
  assert.equal(allow(permission, { sessionId: 'registered' }).kind, 'approved');
  assert.equal(allow(permission, { sessionId: 'registered', promptRequest: permission }).kind, 'approved');
  for (const change of [{ kind: 'shell' }, { toolName: 'bash' }, { surprise: true },
    { managedApprovalRequired: true }, { skipPermission: true }, { args: { ...args, host: '/' } }])
    assert.notEqual(allow({ ...permission, ...change }, { sessionId: 'registered' }).kind, 'approved');
  assert.notEqual(allow(permission, { sessionId: 'other' }).kind, 'approved');
  assert.notEqual(allow(permission, { sessionId: 'registered', promptRequest: { kind: 'shell' } }).kind,
    'approved');
  assert.deepEqual(hostEnvironment({ HOME: '/host', PATH: '/bin', GH_TOKEN: 'secret',
    GITHUB_TOKEN: 'secret', COPILOT_HOME: '/host/config', NODE_OPTIONS: 'unsafe' }),
  { HOME: '/host', PATH: '/bin' });
});

test('complete correlated terminal aggregate deduplicates per-call and cumulative events', () => {
  const evidence = new Evidence(request(), 'session');
  evidence.observe(start('session'));
  const call = usage('session');
  evidence.observe(call);
  evidence.observe({ ...call, id: 'replayed' });
  const checkpoint = event('session.usage_checkpoint', {
    totalNanoAiu: 123, usageAccountingWatermarks: { session: 1 },
  });
  evidence.observe(checkpoint);
  evidence.observe({ ...checkpoint, id: 'checkpoint-replay' });
  evidence.observe(event('session.completion_receipt', { success: true }));
  assert.equal(evidence.receipt().usage.totalNanoAiu, null);
  evidence.observe(event('session.idle', {}));
  evidence.observe(shutdown('session'));
  evidence.observe(shutdown('session'));
  assert.deepEqual(evidence.receipt().usage,
    { totalNanoAiu: 123, credits_complete: true, aiCreditsStatus: 'complete' });
  assert.equal(evidence.receipt('sdk_failure').usage.totalNanoAiu, null);
});

test('partial, unavailable, duplicate-conflicting and missing accounting never imply zero', () => {
  for (const amount of [{ aiCreditsStatus: 'partial' },
    { aiCreditsStatus: 'unavailable', copilotUsage: undefined }, { aiCreditsStatus: undefined }]) {
    const evidence = new Evidence(request(), 's');
    evidence.observe(start('s'));
    evidence.observe(usage('s', amount));
    evidence.observe(event('session.idle', {}));
    evidence.observe(shutdown('s'));
    assert.equal(evidence.receipt().usage.totalNanoAiu, null);
    assert.equal(evidence.receipt().usage.credits_complete, false);
  }
  const evidence = new Evidence(request(), 's');
  assert.throws(() => evidence.observe(usage('s', { accounting: undefined })), /correlation/);
  evidence.observe(usage('s'));
  assert.throws(() => evidence.observe(usage('s', { copilotUsage: { totalNanoAiu: 1 } })), /duplicate/);
});

test('actual missing/mismatched model or effort and routing/discovery changes fail closed', () => {
  for (const invalid of [{ model: 'fallback' }, { reasoningEffort: undefined },
    { reasoningEffort: 'low' }, { isAuto: true }, { fusion: {} }]) {
    const evidence = new Evidence(request(), 's');
    evidence.observe(start('s'));
    assert.throws(() => evidence.observe(usage('s', invalid)));
    assert.equal(evidence.receipt('identity_failure').usage.credits_complete, false);
  }
  for (const [type, data] of [
    ['session.model_change', { newModel: 'fallback', reasoningEffort: 'medium', source: 'automatic' }],
    ['session.skills_loaded', { skills: [{ name: 'host-skill' }] }],
    ['session.mcp_servers_loaded', { servers: [{ name: 'host' }] }],
    ['session.extensions_loaded', { extensions: [{ id: 'host' }] }],
    ['instruction.update', {}], ['tool.execution_start', { toolName: 'bash' }],
  ]) assert.throws(() => new Evidence(request(), 's').observe(event(type, data)));
});

test('only the exact disabled builtin MCP catalog is inert; active or ambiguous MCP remains denied', () => {
  const disabled = { name: 'github-mcp-server', status: 'disabled', source: 'builtin' };
  const evidence = new Evidence(request(), 's');
  evidence.observe(event('session.mcp_servers_loaded', { servers: [disabled] }));
  for (const servers of [
    [null], [disabled, disabled], [{ ...disabled, name: 'other' }],
    [{ ...disabled, source: 'user' }], [{ ...disabled, source: undefined }],
    [{ ...disabled, error: 'failed' }], [{ ...disabled, tools: ['host'] }],
    ...['pending', 'connected', 'failed', 'not_configured', undefined].map(status =>
      [{ ...disabled, status }]),
  ]) assert.throws(() => new Evidence(request(), 's').observe(
    event('session.mcp_servers_loaded', { servers })), /unexpected_discovery/);
  for (const type of ['session.mcp_server_status_changed', 'session.mcp_server_tools_loaded',
    'mcp.oauth_required'])
    assert.throws(() => evidence.observe(event(type, disabled)), /unexpected_runtime_activity/);
  assert.throws(() => evidence.observe(event('tool.execution_start',
    { toolName: 'isolated_exec', mcpServerName: 'github-mcp-server' })), /unexpected_tool/);
});

test('only an exact isolated-only catalog and correlated nonexistent tools are accepted', () => {
  const catalog = { tools: [{ name: 'isolated_exec' }] };
  for (const invalid of [null, {}, { tools: null }, { tools: [] },
    { tools: [{ name: 'create' }] }, { tools: [{ name: 'isolated_exec' }, { name: 'create' }] },
    { tools: [{ name: 'isolated_exec', mcpServerName: 'server' }] },
    { tools: [{ name: 'isolated_exec', namespacedName: 'server:isolated_exec' }] }]) {
    assert.throws(() => new Evidence(request(), 's').verifyToolCatalog(invalid),
      /unexpected_tool_catalog/);
  }
  const createStart = event('tool.execution_start', { toolName: 'create', toolCallId: 'c' });
  const createDone = event('tool.execution_complete', { toolCallId: 'c', success: false,
    error: { code: 'failure', message: "Tool 'create' does not exist." } });
  assert.throws(() => new Evidence(request(), 's').observe(createStart), /unexpected_tool/);
  const evidence = new Evidence(request(), 's');
  evidence.verifyToolCatalog(catalog);
  for (const name of ['create', 'edit', 'view', 'bash']) {
    evidence.observe(event('tool.execution_start', { toolName: name, toolCallId: name }));
    evidence.observe(event('tool.execution_complete', { toolCallId: name, success: false,
      error: { code: 'failure', message: `Tool '${name}' does not exist.` } }));
  }
  evidence.observe(createStart);
  evidence.observe(event('tool.execution_start', { toolName: 'isolated_exec', toolCallId: 'i' }));
  evidence.observe(event('tool.execution_complete', { toolCallId: 'i', success: true }));
  evidence.observe(createDone);
  assert.throws(() => evidence.observe(createStart), /unexpected_tool/);
  assert.throws(() => evidence.observe(createDone), /unexpected_tool/);

  for (const changed of [{ success: true }, { success: undefined }, { result: {} },
    { error: undefined }, { error: { code: 'denied', message: "Tool 'create' does not exist." } },
    { error: { code: 'failure', message: 'other failure' } }, { toolCallId: 'other' }]) {
    const invalid = new Evidence(request(), 's');
    invalid.verifyToolCatalog(catalog);
    invalid.observe(createStart);
    assert.throws(() => invalid.observe(event('tool.execution_complete',
      { ...createDone.data, ...changed })), /unexpected_tool/);
  }
  const missing = new Evidence(request(), 's');
  missing.verifyToolCatalog(catalog);
  missing.observe(createStart);
  assert.throws(() => missing.observe(event('session.idle', {})), /incomplete_tool_execution/);
  assert.equal(missing.receipt().usage.credits_complete, false);
  for (const data of [{ toolName: 'create' }, { toolName: 'server:bash', toolCallId: 'b' },
    { toolName: "bad'name", toolCallId: 'c' }, { toolName: 'x'.repeat(129), toolCallId: 'c' },
    { toolName: 'create', toolCallId: 'c', mcpServerName: 'server' },
    { toolName: 'create', toolCallId: 'c', mcpToolName: 'create' },
    { toolName: 'create', toolCallId: 'c', namespacedName: 'server:create' }]) {
    const invalid = new Evidence(request(), 's');
    invalid.verifyToolCatalog(catalog);
    assert.throws(() => invalid.observe(event('tool.execution_start', data)), /unexpected_tool/);
  }
});

test('a verified missing edit can be followed by isolated work with complete usage', async () => {
  const result = await runFake({ async action(config) {
    config.onEvent(event('tool.execution_start', { toolName: 'edit', toolCallId: 'c' }));
    config.onEvent(event('tool.execution_complete', { toolCallId: 'c', success: false,
      error: { code: 'failure', message: "Tool 'edit' does not exist." } }));
    config.onEvent(event('tool.execution_start', { toolName: 'isolated_exec', toolCallId: 'i' }));
    const reply = await config.tools[0].handler({ command: 'touch feature.py', timeoutSeconds: 1 },
      { sessionId: config.sessionId, toolName: 'isolated_exec', toolCallId: 'i' });
    assert.equal(reply.resultType, 'success');
    config.onEvent(event('tool.execution_complete', { toolCallId: 'i', success: true }));
  } });
  assert.equal(result.exitCode, 0);
  assert.equal(result.receipt.usage.credits_complete, true);
  assert.equal(result.records.filter(record => record.type === 'tool').length, 1);
});

test('an authenticated isolated tool rejection lets the same session recover without a new prompt', async () => {
  const result = await runFake({
    toolReply: record => record.id === 'unsafe' ?
      { stdout: '', stderr: 'Unsupported filesystem artifact; prior state is retained.', exit_code: 1 } :
      { stdout: 'safe work', stderr: '', exit_code: 0 },
    async action(config) {
      for (const [id, command, expected] of [
        ['unsafe', 'ln -s target unsupported-link', 'failure'],
        ['safe', 'printf safe', 'success'],
      ]) {
        config.onEvent(event('tool.execution_start', { toolName: 'isolated_exec', toolCallId: id }));
        const reply = await config.tools[0].handler({ command, timeoutSeconds: 1 },
          { sessionId: config.sessionId, toolName: 'isolated_exec', toolCallId: id });
        assert.equal(reply.resultType, expected);
        config.onEvent(event('tool.execution_complete', { toolCallId: id, success: id === 'safe' }));
      }
    },
  });
  assert.equal(result.exitCode, 0);
  assert.equal(result.receipt.usage.credits_complete, true);
  assert.equal(result.state.sent, 1);
  assert.equal(result.records.filter(record => record.type === 'tool').length, 2);
  assert.equal(result.state.config.sessionLimits.maxAiCredits, 173.5);
});

test('a changed or unavailable tool catalog stops before the first prompt', async () => {
  for (const metadata of [{}, { tools: [] },
    { tools: [{ name: 'isolated_exec' }, { name: 'create' }] }]) {
    const result = await runFake({ metadata });
    assert.equal(result.state.sent, 0);
    assert.equal(result.receipt.protocol_error, 'unexpected_tool_catalog');
    assert.equal(result.receipt.usage.credits_complete, false);
  }
  const changed = await runFake({ finalMetadata: { tools: [{ name: 'isolated_exec' }, { name: 'edit' }] } });
  assert.equal(changed.state.sent, 1);
  assert.equal(changed.receipt.protocol_error, 'unexpected_tool_catalog');
  assert.equal(changed.receipt.usage.credits_complete, false);
});

const providerFailure = (extra = {}) => ({
  model: 'test-model', reasoningEffort: 'medium', statusCode: 500, failureKind: 'api',
  transport: 'websocket', errorCode: 'internal_error', errorType: 'websocket_error',
  isAuto: false, isByok: false, retryAttempt: 0,
  apiCallId: 'failed-api', serviceRequestId: 'failed-service', ...extra,
});
const resetFailure = (extra = {}) => ({
  model: 'test-model', reasoningEffort: 'medium', failureKind: 'transport',
  transport: 'websocket', rte: true, source: 'top_level', apiEndpoint: 'ws:/responses',
  errorMessage: WEBSOCKET_RESET_MESSAGE, isAuto: false, isByok: false, retryAttempt: 0,
  apiCallId: 'failed-api', serviceRequestId: 'failed-service', ...extra,
});
const providerMirror = (failure, turn = 0) => failure.failureKind === 'transport' ? {
  kind: 'model_call_failure', turn, reasoningEffort: failure.reasoningEffort,
  modelCall: { model: failure.model, api_id: failure.apiCallId,
    service_request_id: failure.serviceRequestId, transport: failure.transport,
    failure_kind: 'transport', rte: failure.rte, api_endpoint: failure.apiEndpoint,
    error: failure.errorMessage, retry_attempt: failure.retryAttempt },
} : ({
  kind: 'model_call_failure', turn, reasoningEffort: failure.reasoningEffort,
  modelCall: { model: failure.model, status: failure.statusCode, api_id: failure.apiCallId,
    service_request_id: failure.serviceRequestId, transport: failure.transport,
    errorCode: failure.errorCode, errorType: failure.errorType, retry_attempt: failure.retryAttempt },
});
function failProvider(config, failure = providerFailure(), turn = 0) {
  config.onEvent(event('model.call_start', { model: 'test-model', turnId: String(turn) }));
  config.onEvent(event('model.call_failure', failure));
  config.onEvent(event('model.model_call_failure', providerMirror(failure, turn)));
  config.onEvent(event('model.call_finished', { turnId: String(turn), outcome: 'error' }));
}
function successfulRetry(config, turn = 1) {
  config.onEvent(event('model.call_start', { model: 'test-model', turnId: String(turn) }));
  config.onEvent(event('model.call_finished', { turnId: String(turn), outcome: 'success' }));
}

test('real same-turn provider retry preserves limits and accounts for the failed request', async () => {
  for (const failure of [providerFailure(),
    providerFailure({ statusCode: 503, errorCode: 'service_unavailable' }), resetFailure(),
    resetFailure({ rte: false })]) {
    const result = await runFake({
      async action(config) {
        config.onEvent(event('model.call_start', { model: 'test-model', turnId: '0' }));
        config.onEvent(event('model.call_failure', failure));
        config.onEvent(event('model.model_call_failure', providerMirror(failure)));
        config.onEvent(usage(config.sessionId, { apiCallId: failure.apiCallId,
          serviceRequestId: failure.serviceRequestId, copilotUsage: { totalNanoAiu: 17 } }));
        successfulRetry(config, 0);
      },
      usage: sid => ({ accounting: { sourceSessionId: sid, sequence: 2, usageId: 'call-two' } }),
      shutdown: sid => event('session.shutdown', {
        shutdownType: 'routine', currentModel: 'test-model', totalNanoAiu: 140,
        usageAccountingWatermarks: { [sid]: 2 },
        modelMetrics: { 'test-model': { totalNanoAiu: 140, requests: { count: 2 } } },
      }),
    });
    assert.equal(result.exitCode, 0, `status ${failure.statusCode}`);
    assert.equal(result.receipt.usage.totalNanoAiu, 140);
    assert.equal(result.receipt.provider_failures[0].accounting_complete, true);
    assert.equal(result.state.sent, 1);
    assert.equal(result.state.config.sessionLimits.maxAiCredits, 173.5);
  }
});

test('a matched transport reset does not certify a missing failed-request charge', async () => {
  const failure = resetFailure();
  const result = await runFake({ async action(config) {
    failProvider(config, failure);
    successfulRetry(config, 0);
  } });
  assert.equal(result.receipt.protocol_error, 'provider_retry_usage_incomplete');
  assert.equal(result.receipt.usage.totalNanoAiu, null);
  assert.equal(result.receipt.provider_failures[0].failure_kind, 'transport');
  assert.equal(result.receipt.provider_failures[0].status_code, null);
});

test('mixed finished and unfinished same-turn retries preserve every charge and original limits', async () => {
  const first = providerFailure();
  const second = providerFailure({ retryAttempt: 1, apiCallId: 'second-api', serviceRequestId: 'second-service' });
  const result = await runFake({
    async action(config) {
      failProvider(config, first, 6);
      config.onEvent(usage(config.sessionId, { apiCallId: first.apiCallId,
        serviceRequestId: first.serviceRequestId, copilotUsage: { totalNanoAiu: 17 } }));
      config.onEvent(event('model.call_start', { model: 'test-model', turnId: '6' }));
      config.onEvent(event('model.call_failure', second));
      config.onEvent(event('model.model_call_failure', providerMirror(second, 6)));
      config.onEvent(usage(config.sessionId, { apiCallId: second.apiCallId,
        serviceRequestId: second.serviceRequestId, copilotUsage: { totalNanoAiu: 19 },
        accounting: { sourceSessionId: config.sessionId, sequence: 2, usageId: 'second-failure' } }));
      successfulRetry(config, 6);
    },
    usage: sid => ({ accounting: { sourceSessionId: sid, sequence: 3, usageId: 'success' } }),
    shutdown: sid => event('session.shutdown', { shutdownType: 'routine', currentModel: 'test-model',
      totalNanoAiu: 159, usageAccountingWatermarks: { [sid]: 3 },
      modelMetrics: { 'test-model': { totalNanoAiu: 159, requests: { count: 3 } } } }),
  });
  assert.equal(result.exitCode, 0);
  assert.equal(result.receipt.usage.totalNanoAiu, 159);
  assert.equal(result.receipt.provider_failures.length, 2);
  assert.ok(result.receipt.provider_failures.every(failure => failure.accounting_complete));
  assert.equal(result.state.sent, 1);
  assert.equal(result.state.config.sessionLimits.maxAiCredits, 173.5);
});

test('mixed-boundary retry never treats omitted failed-request charges as zero', async () => {
  for (const omitted of ['first', 'second', 'both']) {
    let sequence = 0;
    let charged = 0;
    const first = providerFailure();
    const second = providerFailure({ retryAttempt: 1, apiCallId: 'second-api', serviceRequestId: 'second-service' });
    const result = await runFake({
      async action(config) {
        const charge = failure => {
          sequence++; charged += 17;
          config.onEvent(usage(config.sessionId, { apiCallId: failure.apiCallId,
            serviceRequestId: failure.serviceRequestId, copilotUsage: { totalNanoAiu: 17 },
            accounting: { sourceSessionId: config.sessionId, sequence, usageId: `charge-${sequence}` } }));
        };
        failProvider(config, first, 6);
        if (omitted === 'second') charge(first);
        config.onEvent(event('model.call_start', { model: 'test-model', turnId: '6' }));
        config.onEvent(event('model.call_failure', second));
        config.onEvent(event('model.model_call_failure', providerMirror(second, 6)));
        if (omitted === 'first') charge(second);
        successfulRetry(config, 6);
      },
      usage: sid => ({ accounting: { sourceSessionId: sid, sequence: sequence + 1, usageId: 'success' } }),
      shutdown: sid => event('session.shutdown', { shutdownType: 'routine', currentModel: 'test-model',
        totalNanoAiu: 123 + charged, usageAccountingWatermarks: { [sid]: sequence + 1 },
        modelMetrics: { 'test-model': { totalNanoAiu: 123 + charged, requests: { count: sequence + 1 } } } }),
    });
    assert.equal(result.receipt.protocol_error, 'provider_retry_usage_incomplete');
    assert.equal(result.receipt.usage.totalNanoAiu, null);
    assert.equal(result.receipt.usage.credits_complete, false);
  }
});

test('finished same-turn failures cannot reset the three-failure ceiling', async () => {
  const result = await runFake({ async action(config) {
    for (let retry = 0; retry < 4; retry++) {
      failProvider(config, providerFailure({ retryAttempt: retry,
        apiCallId: `api-${retry}`, serviceRequestId: `service-${retry}` }), 6);
    }
  } });
  assert.equal(result.receipt.protocol_error, 'provider_retry_limit');
  assert.equal(result.receipt.provider_failures.length, 3);
  assert.equal(result.receipt.usage.credits_complete, false);
});

test('finished retry boundaries still require a fresh per-attempt accounting watermark', async () => {
  const first = providerFailure();
  const later = providerFailure({ retryAttempt: 1, apiCallId: 'later-api', serviceRequestId: 'later-service' });
  const result = await runFake({
    async action(config) {
      failProvider(config, first, 6);
      config.onEvent(usage(config.sessionId, { apiCallId: later.apiCallId,
        serviceRequestId: later.serviceRequestId, copilotUsage: { totalNanoAiu: 17 } }));
      config.onEvent(event('model.call_start', { model: 'test-model', turnId: '6' }));
      config.onEvent(event('model.call_failure', later));
      config.onEvent(event('model.model_call_failure', providerMirror(later, 6)));
      config.onEvent(usage(config.sessionId, { apiCallId: first.apiCallId,
        serviceRequestId: first.serviceRequestId, copilotUsage: { totalNanoAiu: 17 },
        accounting: { sourceSessionId: config.sessionId, sequence: 2, usageId: 'first-charge' } }));
      successfulRetry(config, 6);
    },
    usage: sid => ({ accounting: { sourceSessionId: sid, sequence: 3, usageId: 'success' } }),
    shutdown: sid => event('session.shutdown', { shutdownType: 'routine', currentModel: 'test-model',
      totalNanoAiu: 157, usageAccountingWatermarks: { [sid]: 3 },
      modelMetrics: { 'test-model': { totalNanoAiu: 157, requests: { count: 3 } } } }),
  });
  assert.equal(result.receipt.protocol_error, 'provider_retry_usage_incomplete');
  assert.equal(result.receipt.usage.credits_complete, false);
  assert.equal(result.receipt.provider_failures[1].accounting_complete, false);
});

test('a transport reset needs the exact structured top-level signature, not a message alone', async () => {
  for (const change of [
    { failureKind: 'api' }, { transport: 'http' }, { source: 'subagent' },
    { apiEndpoint: 'https://unreviewed.example/responses' }, { isAuto: true }, { isByok: true },
    { statusCode: 500 }, { errorCode: 'internal_error' }, { errorType: 'websocket_error' },
    { errorMessage: '"WebSocket authentication failed"' }, { errorMessage: '[ECONNRESET]' },
  ]) {
    const result = await runFake({ async action(config) {
      failProvider(config, resetFailure(change));
      successfulRetry(config);
    } });
    assert.equal(result.exitCode, 1);
    assert.equal(result.receipt.usage.credits_complete, false);
  }
});

test('reset mirrors must match transport endpoint, exact error and IDs', async () => {
  for (const change of [{ failure_kind: 'api' }, { api_endpoint: 'ws:/other' },
    { error: 'different error' }, { status: 500 }, { errorCode: 'internal_error' },
    { service_request_id: 'other-request' }, { api_id: 'other-api' }]) {
    const result = await runFake({ async action(config) {
      const failure = resetFailure();
      config.onEvent(event('model.call_start', { model: 'test-model', turnId: '0' }));
      config.onEvent(event('model.call_failure', failure));
      const mirror = providerMirror(failure);
      mirror.modelCall = { ...mirror.modelCall, ...change };
      config.onEvent(event('model.model_call_failure', mirror));
    } });
    assert.equal(result.receipt.protocol_error, 'provider_failure_correlation_unavailable');
    assert.equal(result.receipt.usage.credits_complete, false);
  }
});

test('close1001 without request correlation is an explicit usage-unknown stop, never a retry', async () => {
  const result = await runFake({ async action(config) {
    config.onEvent(event('model.call_start', { model: 'test-model', turnId: '0' }));
    config.onEvent(event('model.call_failure', {
      model: 'test-model', reasoningEffort: 'medium', failureKind: 'transport',
      transport: 'websocket', apiEndpoint: 'ws:/responses', source: 'top_level',
      rte: false, isAuto: false, isByok: false, retryAttempt: 0,
      errorMessage: '"WebSocket closed unexpectedly (request-id: opaque-reference): 1001 please reconnect"',
    }));
  } });
  assert.equal(result.receipt.protocol_error, 'websocket_closed_usage_unknown');
  assert.equal(result.receipt.usage.credits_complete, false);
  assert.equal(result.receipt.usage.totalNanoAiu, null);
  assert.deepEqual(result.receipt.provider_failures, []);
  assert.equal(result.state.sent, 1);
});

test('repeated WebSocket resets share the three-failure ceiling', async () => {
  const result = await runFake({ async action(config) {
    config.onEvent(event('model.call_start', { model: 'test-model', turnId: '0' }));
    for (let retry = 0; retry < 4; retry++) {
      const failure = resetFailure({ retryAttempt: retry, apiCallId: `failed-${retry}`,
        serviceRequestId: `service-${retry}` });
      config.onEvent(event('model.call_failure', failure));
      config.onEvent(event('model.model_call_failure', providerMirror(failure)));
      config.onEvent(event('model.call_start', { model: 'test-model', turnId: '0' }));
    }
  } });
  assert.equal(result.receipt.protocol_error, 'provider_retry_limit');
  assert.equal(result.receipt.provider_failures.length, 3);
  assert.equal(result.receipt.usage.credits_complete, false);
});

test('same-turn service-unavailable retry still requires complete failed-request charges', async () => {
  const failure = providerFailure({ statusCode: 503, errorCode: 'service_unavailable' });
  const result = await runFake({ async action(config) {
    config.onEvent(event('model.call_start', { model: 'test-model', turnId: '0' }));
    config.onEvent(event('model.call_failure', failure));
    config.onEvent(event('model.model_call_failure', providerMirror(failure)));
    successfulRetry(config, 0);
  } });
  assert.equal(result.receipt.protocol_error, 'provider_retry_usage_incomplete');
  assert.equal(result.receipt.usage.credits_complete, false);
  assert.equal(result.receipt.usage.totalNanoAiu, null);
});

test('same-turn retry requires one matched failure and rejects overlap or changed turns', async () => {
  for (const damage of ['before-mirror', 'duplicate-start', 'changed-turn', 'unpaired-error']) {
    const failure = providerFailure();
    const result = await runFake({ async action(config) {
      config.onEvent(event('model.call_start', { model: 'test-model', turnId: '0' }));
      config.onEvent(event('model.call_failure', failure));
      if (damage !== 'before-mirror')
        config.onEvent(event('model.model_call_failure', providerMirror(failure)));
      config.onEvent(event('model.call_start', {
        model: 'test-model', turnId: damage === 'changed-turn' ? '1' : '0',
      }));
      if (damage === 'duplicate-start')
        config.onEvent(event('model.call_start', { model: 'test-model', turnId: '0' }));
      if (damage === 'unpaired-error')
        config.onEvent(event('model.call_finished', { turnId: '0', outcome: 'error' }));
    } });
    assert.equal(result.exitCode, 1);
    assert.equal(result.receipt.usage.credits_complete, false);
    assert.ok(['provider_call_correlation_unavailable', 'unexpected_runtime_activity']
      .includes(result.receipt.protocol_error), damage);
  }
});

test('same-turn provider retry remains bounded at three failures', async () => {
  const result = await runFake({ async action(config) {
    config.onEvent(event('model.call_start', { model: 'test-model', turnId: '0' }));
    for (let retry = 0; retry < 4; retry++) {
      const failure = providerFailure({ statusCode: 503, errorCode: 'service_unavailable',
        retryAttempt: retry, apiCallId: `failed-${retry}`, serviceRequestId: `service-${retry}` });
      config.onEvent(event('model.call_failure', failure));
      config.onEvent(event('model.model_call_failure', providerMirror(failure)));
      config.onEvent(event('model.call_start', { model: 'test-model', turnId: '0' }));
    }
  } });
  assert.equal(result.receipt.protocol_error, 'provider_retry_limit');
  assert.equal(result.receipt.provider_failures.length, 3);
  assert.equal(result.receipt.usage.credits_complete, false);
});

test('an earlier matching charge cannot account for a later attempt in the same turn', async () => {
  const first = providerFailure();
  const later = providerFailure({ retryAttempt: 1, apiCallId: 'later-api', serviceRequestId: 'later-service' });
  const result = await runFake({
    async action(config) {
      config.onEvent(event('model.call_start', { model: 'test-model', turnId: '0' }));
      config.onEvent(event('model.call_failure', first));
      config.onEvent(event('model.model_call_failure', providerMirror(first)));
      config.onEvent(usage(config.sessionId, { apiCallId: later.apiCallId,
        serviceRequestId: later.serviceRequestId, copilotUsage: { totalNanoAiu: 17 } }));
      config.onEvent(event('model.call_start', { model: 'test-model', turnId: '0' }));
      config.onEvent(event('model.call_failure', later));
      config.onEvent(event('model.model_call_failure', providerMirror(later)));
      config.onEvent(usage(config.sessionId, { apiCallId: first.apiCallId,
        serviceRequestId: first.serviceRequestId, copilotUsage: { totalNanoAiu: 17 },
        accounting: { sourceSessionId: config.sessionId, sequence: 2, usageId: 'first-failure' } }));
      successfulRetry(config, 0);
    },
    usage: sid => ({ accounting: { sourceSessionId: sid, sequence: 3, usageId: 'successful-retry' } }),
    shutdown: sid => event('session.shutdown', {
      shutdownType: 'routine', currentModel: 'test-model', totalNanoAiu: 157,
      usageAccountingWatermarks: { [sid]: 3 },
      modelMetrics: { 'test-model': { totalNanoAiu: 157, requests: { count: 3 } } },
    }),
  });
  assert.equal(result.receipt.protocol_error, 'provider_retry_usage_incomplete');
  assert.equal(result.receipt.usage.totalNanoAiu, null);
});

test('correlated transient retry preserves original limits and requires every failed request charge', async () => {
  const result = await runFake({
    async action(config) {
      failProvider(config);
      config.onEvent(usage(config.sessionId, { apiCallId: 'failed-api',
        serviceRequestId: 'failed-service', copilotUsage: { totalNanoAiu: 17 } }));
      successfulRetry(config);
    },
    usage: sid => ({ accounting: { sourceSessionId: sid, sequence: 2, usageId: 'call-two' } }),
    shutdown: sid => event('session.shutdown', {
      shutdownType: 'routine', currentModel: 'test-model', totalNanoAiu: 140,
      usageAccountingWatermarks: { [sid]: 2 },
      modelMetrics: { 'test-model': { totalNanoAiu: 140, requests: { count: 2 } } },
    }),
  });
  assert.equal(result.exitCode, 0);
  assert.equal(result.receipt.protocol_error, null);
  assert.equal(result.receipt.usage.totalNanoAiu, 140);
  assert.equal(result.receipt.usage.credits_complete, true);
  assert.equal(result.receipt.provider_failures[0].accounting_complete, true);
  assert.equal(result.state.sent, 1);
  assert.equal(result.state.config.sessionLimits.maxAiCredits, 173.5);
  assert.equal(result.state.closed, 1);
});

test('a retried provider error without explicit failed-request usage never becomes zero-cost', async () => {
  const result = await runFake({ async action(config) {
    failProvider(config);
    successfulRetry(config);
  } });
  assert.equal(result.exitCode, 1);
  assert.equal(result.receipt.protocol_error, 'provider_retry_usage_incomplete');
  assert.equal(result.receipt.usage.credits_complete, false);
  assert.equal(result.receipt.usage.totalNanoAiu, null);
  assert.deepEqual(result.receipt.provider_failures, [{
    status_code: 500, error_code: 'internal_error', transport: 'websocket',
    retry_attempt: 0, accounting_complete: false,
  }]);
  for (const change of [{ apiCallId: 'another-api' }, { serviceRequestId: 'another-service' },
    { aiCreditsStatus: 'partial' }, { copilotUsage: undefined }]) {
    const mismatched = await runFake({ async action(config) {
      failProvider(config);
      config.onEvent(usage(config.sessionId, {
        apiCallId: 'failed-api', serviceRequestId: 'failed-service', ...change,
      }));
      successfulRetry(config);
    } });
    assert.equal(mismatched.exitCode, 1);
    assert.equal(mismatched.receipt.usage.totalNanoAiu, null);
  }
});

test('an earlier matching charge cannot account for a later failed model turn', async () => {
  const result = await runFake({
    async action(config) {
      config.onEvent(usage(config.sessionId, { apiCallId: 'failed-api',
        serviceRequestId: 'failed-service', copilotUsage: { totalNanoAiu: 17 } }));
      failProvider(config);
      successfulRetry(config);
    },
    usage: sid => ({ accounting: { sourceSessionId: sid, sequence: 2, usageId: 'call-two' } }),
    shutdown: sid => event('session.shutdown', {
      shutdownType: 'routine', currentModel: 'test-model', totalNanoAiu: 140,
      usageAccountingWatermarks: { [sid]: 2 },
      modelMetrics: { 'test-model': { totalNanoAiu: 140, requests: { count: 2 } } },
    }),
  });
  assert.equal(result.exitCode, 1);
  assert.equal(result.receipt.protocol_error, 'provider_retry_usage_incomplete');
  assert.equal(result.receipt.usage.totalNanoAiu, null);
});

test('explicit current-turn usage arriving before its error can still account for the failed request', () => {
  const evidence = new Evidence(request(), 's');
  evidence.observe(start('s'));
  evidence.verifyToolCatalog({ tools: [{ name: 'isolated_exec' }] });
  evidence.observe(event('model.call_start', { model: 'test-model', turnId: '0' }));
  evidence.observe(usage('s', { apiCallId: 'failed-api', serviceRequestId: 'failed-service',
    copilotUsage: { totalNanoAiu: 17 } }));
  evidence.observe(event('model.call_failure', providerFailure()));
  evidence.observe(event('model.model_call_failure', providerMirror(providerFailure())));
  evidence.observe(event('model.call_finished', { turnId: '0', outcome: 'error' }));
  evidence.observe(event('model.call_start', { model: 'test-model', turnId: '1' }));
  evidence.observe(usage('s', { accounting: { sourceSessionId: 's', sequence: 2, usageId: 'call-two' } }));
  evidence.observe(event('model.call_finished', { turnId: '1', outcome: 'success' }));
  evidence.observe(event('session.idle', {}));
  evidence.observe(event('session.shutdown', {
    shutdownType: 'routine', currentModel: 'test-model', totalNanoAiu: 140,
    usageAccountingWatermarks: { s: 2 },
    modelMetrics: { 'test-model': { totalNanoAiu: 140, requests: { count: 2 } } },
  }));
  assert.equal(evidence.receipt().usage.credits_complete, true);
  assert.equal(evidence.receipt().usage.totalNanoAiu, 140);
});

test('provider retries remain bounded and terminal failure never produces a successful idle', async () => {
  const limit = await runFake({ async action(config) {
    for (let turn = 0; turn < 4; turn++) {
      failProvider(config, providerFailure({
        apiCallId: `failed-${turn}`, serviceRequestId: `service-${turn}`,
      }), turn);
    }
  } });
  assert.equal(limit.receipt.protocol_error, 'provider_retry_limit');
  assert.equal(limit.receipt.provider_failures.length, 3);
  assert.equal(limit.receipt.usage.credits_complete, false);
  const unfinished = await runFake({ async action(config) { failProvider(config); } });
  assert.equal(unfinished.receipt.protocol_error, 'incomplete_provider_retry');
  const terminal = await runFake({ async action(config) {
    failProvider(config);
    config.onEvent(event('session.error', { message: 'private provider details' }));
  } });
  assert.equal(terminal.receipt.protocol_error, 'transient_provider_failure');
});

test('uncorrelated, auth, client, model, effort and routing failures remain denied', async () => {
  for (const change of [{ statusCode: 401 }, { statusCode: 403 }, { statusCode: 429 },
    { statusCode: 400 }, { statusCode: 501 }, { statusCode: '500' },
    { failureKind: 'permission' }, { transport: 'unknown' }, { errorCode: 'quota_exceeded' },
    { errorType: 'authentication_error' }, { isAuto: true }, { isByok: true },
    { fusion: true }, { model: 'other' }, { reasoningEffort: 'high' },
    { serviceRequestId: undefined }, { apiCallId: undefined }, { retryAttempt: 1 },
    { statusCode: 500, errorCode: 'service_unavailable' },
    { statusCode: 504, errorCode: 'service_unavailable' },
    { statusCode: 503, errorCode: 'quota_exceeded' }]) {
    const result = await runFake({ async action(config) {
      failProvider(config, providerFailure(change));
    } });
    assert.equal(result.exitCode, 1);
    assert.equal(result.receipt.usage.credits_complete, false);
    assert.ok(['unexpected_runtime_activity', 'actual_identity_unavailable_or_mismatched']
      .includes(result.receipt.protocol_error));
  }
  const uncorrelated = await runFake({ async action(config) {
    config.onEvent(event('model.call_failure', providerFailure()));
  } });
  assert.equal(uncorrelated.receipt.protocol_error, 'unexpected_runtime_activity');
  for (const mirror of [{ turn: 1 }, { modelCall: {} }, { reasoningEffort: 'high' }]) {
    const result = await runFake({ async action(config) {
      config.onEvent(event('model.call_start', { model: 'test-model', turnId: '0' }));
      config.onEvent(event('model.call_failure', providerFailure()));
      config.onEvent(event('model.model_call_failure', { ...providerMirror(providerFailure()), ...mirror }));
    } });
    assert.equal(result.receipt.protocol_error, 'provider_failure_correlation_unavailable');
  }
});

test('transient backend evidence never enables discovery, model changes or host tools', async () => {
  for (const violation of [
    event('mcp.started', {}),
    event('session.model_change', { newModel: 'other', reasoningEffort: 'medium' }),
    event('tool.execution_start', { toolName: 'create', toolCallId: 'host' }),
  ]) {
    const result = await runFake({ async action(config) {
      failProvider(config);
      successfulRetry(config);
      config.onEvent(violation);
      if (violation.type === 'tool.execution_start')
        config.onEvent(event('tool.execution_complete', { toolCallId: 'host', success: true }));
    } });
    assert.equal(result.exitCode, 1);
    assert.equal(result.receipt.usage.credits_complete, false);
  }
});

test('bounded input framing rejects oversized, aggregate floods, malformed UTF-8 and unterminated records', () => {
  const limits = { record: 20, events: 30 };
  for (const chunks of [
    [Buffer.alloc(21, 65)], [Buffer.from('{"a":1}\n'.repeat(5))],
    [Buffer.from([0xff, 10])], [Buffer.from('{}\n\n')],
  ]) {
    const errors = [];
    const parser = new InputRecords(() => {}, error => errors.push(error), limits);
    for (const chunk of chunks) parser.push(chunk);
    assert.equal(errors.length, 1);
    parser.push(Buffer.alloc(100));
    assert.equal(errors.length, 1);
  }
  const seen = [];
  const parser = new InputRecords(record => seen.push(record), assert.fail);
  parser.push(Buffer.from('{"a"'));
  parser.push(Buffer.from(':1}\n{}\n'));
  assert.deepEqual(seen, [{ a: 1 }, {}]);
  const partial = new InputRecords(() => assert.fail(), assert.fail);
  partial.push(Buffer.from('{"a":'));
  assert.ok(partial.buffer.length);
});

test('RPC frames are bounded before SDK parsing and owned proxy reaps its child', async () => {
  const bytes = Buffer.from('Content-Length: 2\r\n\r\n{}Content-Length: 3\r\n\r\n123');
  const frames = new RpcFrames(8);
  let result = '';
  frames.on('data', chunk => { result += chunk; });
  for (const byte of bytes) frames.write(Buffer.from([byte]));
  frames.end();
  await once(frames, 'end');
  assert.equal(result, bytes.toString());
  for (const frame of ['Content-Length: 9\r\n\r\n', 'Content-Length: 3\r\n\r\nx',
    'Invalid: 1\r\n\r\nx']) {
    const rejected = new RpcFrames(8);
    rejected.resume();
    const error = once(rejected, 'error');
    rejected.end(frame);
    await error;
  }
  const rpcFlood = new RpcFrames(8, 24);
  rpcFlood.resume();
  const rpcFailure = once(rpcFlood, 'error');
  rpcFlood.end(bytes);
  assert.match((await rpcFailure)[0].message, /aggregate_limit/);
  const proxy = spawn(process.execPath, [fileURLToPath(new URL('./runtime-guard.mjs', import.meta.url)),
    '--guard', process.execPath, String(Date.now() + 2000), '-e',
    'process.stdout.write("Content-Length: "+Buffer.byteLength(String(process.pid))+"\\r\\n\\r\\n"+process.pid);setInterval(()=>{},1000)'],
  { stdio: ['pipe', 'pipe', 'pipe'] });
  let diagnostic = '';
  proxy.stderr.on('data', chunk => { diagnostic += chunk; });
  const [chunk] = await once(proxy.stdout, 'data');
  const childPid = Number(chunk.toString().split('\r\n\r\n')[1]);
  assert.ok(childPid > 1);
  const closed = once(proxy, 'close');
  proxy.kill('SIGTERM');
  await closed;
  assert.throws(() => process.kill(childPid, 0), { code: 'ESRCH' });
  assert.equal(diagnostic, '');
  const noisy = spawn(process.execPath, [fileURLToPath(new URL('./runtime-guard.mjs', import.meta.url)),
    '--guard', process.execPath, String(Date.now() + 2000), '-e',
    'process.stderr.write("SECRET".repeat(300000));setInterval(()=>{},1000)'],
  { stdio: ['pipe', 'pipe', 'pipe'] });
  let noise = '';
  noisy.stdout.resume();
  noisy.stderr.on('data', chunk => { noise += chunk; });
  const [code] = await once(noisy, 'close');
  assert.equal(code, 1);
  assert.equal(noise, 'runtime_guard_failure\n');
});

test('guarded SDK startup forwards MCP disabling and the version pin to its actual CLI child', async () => {
  const directory = await mkdtemp(join(tmpdir(), 'mve-sdk-argv-'));
  let runtime;
  try {
    const cliPath = join(directory, 'fake-cli');
    const argvPath = join(directory, 'argv');
    await writeFile(cliPath,
      `#!/bin/sh\nprintf '%s\\n' "$@" > '${argvPath}'\nexit 1\n`, { mode: 0o700 });
    runtime = await makeRuntime(request({ cliPath, baseDirectory: directory }), Date.now() + 3000);
    await assert.rejects(runtime.client.start());
    const argv = (await readFile(argvPath, 'utf8')).trim().split('\n');
    assert.ok(argv.includes('--disable-builtin-mcps'), 'CLI must explicitly disable built-in MCP');
    assert.ok(argv.includes('--no-auto-update'), 'CLI must run the bundled pinned version');
  } finally {
    try { if (runtime) await runtime.close(); }
    catch (error) { assert.equal(error.message, 'runtime_guard_failure'); }
    finally { await rm(directory, { recursive: true, force: true }); }
  }
});

test('failed sessions retain close-time usage diagnostics without certifying zero or clearing failure', async () => {
  const result = await runFake({
    async action(config) {
      config.onEvent(event('session.mcp_server_status_changed',
        { serverName: 'github-mcp-server', status: 'pending' }));
    },
    closeEvents(config) {
      config.onEvent(event('session.shutdown', { shutdownType: 'routine',
        totalNanoAiu: 0, totalPremiumRequests: 0, totalApiDurationMs: 0, modelMetrics: {} }));
    },
  });
  assert.equal(result.exitCode, 1);
  assert.equal(result.state.closed, 1);
  assert.equal(result.receipt.protocol_error, 'unexpected_runtime_activity');
  assert.equal(result.receipt.usage.credits_complete, false);
  assert.equal(result.receipt.usage.totalNanoAiu, null);
  const diagnostic = result.records.find(record =>
    record.type === 'event' && record.event.type === 'session.shutdown');
  assert.equal(diagnostic.event.data.totalNanoAiu, 0);
  assert.equal(result.records.at(-1).type, 'complete');
});

test('NDJSON happy path preserves raw events, exact shared budget and correlated tool results', async () => {
  let toolResult;
  const result = await runFake({ async action(config) {
    config.onEvent(event('session.mcp_servers_loaded', {
      servers: [{ name: 'github-mcp-server', status: 'disabled', source: 'builtin' }],
    }));
    toolResult = await config.tools[0].handler({ command: 'pwd', timeoutSeconds: 1 },
      { sessionId: config.sessionId, toolName: 'isolated_exec', toolCallId: 'tool-one' });
  } });
  assert.equal(result.exitCode, 0);
  assert.equal(result.state.closed, 1);
  assert.deepEqual(result.state.order, ['start', 'create']);
  assert.equal(result.state.config.sessionLimits.maxAiCredits, 173.5);
  assert.equal(JSON.parse(toolResult.textResultForLlm).stdout, 'bounded output');
  assert.equal(result.records.filter(record => record.type === 'tool').length, 1);
  assert.equal(result.records.at(-1).type, 'complete');
  for (const record of result.records.filter(record => record.type === 'event')) {
    assert.equal(record.sessionId, result.receipt.session_id);
    assert.ok(record.event.id);
  }
});

test('real SDK rejects native tools without touching host files and still dispatches isolated_exec',
  { skip: !process.env.MVE_COPILOT_CLI, timeout: 95000 }, async () => {
    assert.ok(process.env.TMUX, 'actual SDK checks require a new owned tmux session');
    const directory = await mkdtemp(join(tmpdir(), 'mve-sdk-tool-test-'));
    const original = join(directory, 'owned-sentinel');
    const missing = join(directory, 'new-sentinel');
    await writeFile(original, 'unchanged');
    const req = request({ model: 'gpt-6.1-sol', maxAiCredits: 30, remainingSeconds: 90,
      cliPath: process.env.MVE_COPILOT_CLI, baseDirectory: directory });
    let runtime;
    let isolatedCalls = 0;
    class OfflineRequests extends CopilotRequestHandler {
      async sendRequest() { return new Response('offline', { status: 403 }); }
      async openWebSocket() { throw new Error('offline_fixture'); }
    }
    try {
      runtime = await makeRuntime(req, Date.now() + 90000);
      runtime.client.requestHandler = new OfflineRequests();
      runtime.client.setupClientGlobalHandlers();
      assert.equal(runtime.client.clientGlobalHandlers.llmInference, runtime.client.requestAdapter);
      await assertRuntime(runtime.client);
      const session = await runtime.client.createSession(sessionConfig(req, crypto.randomUUID(),
        async () => { isolatedCalls++; return { textResultForLlm: 'fixture', resultType: 'success' }; },
        () => {}));
      await session.rpc.tools.initializeAndValidate();
      const metadata = await session.rpc.tools.getCurrentMetadata();
      const evidence = new Evidence(req, session.sessionId);
      evidence.verifyToolCatalog(metadata);
      for (const name of ['create', 'edit', 'view', 'bash']) {
        for (const path of [original, missing]) {
          const result = await session.rpc.tools.execute({ name,
            arguments: { path, file_text: 'should not be written', old_str: 'unchanged',
              new_str: 'modified', command: `touch ${missing}` }, toolCallId: crypto.randomUUID() });
          assert.equal(result.resultType, 'failure');
          assert.equal(result.error, `Tool '${name}' does not exist.`);
        }
      }
      assert.equal(await readFile(original, 'utf8'), 'unchanged');
      await assert.rejects(stat(missing), { code: 'ENOENT' });
      const result = await session.rpc.tools.execute({ name: 'isolated_exec',
        arguments: { command: 'pwd', timeoutSeconds: 1 }, toolCallId: crypto.randomUUID() });
      assert.equal(result.resultType, 'success');
      assert.equal(isolatedCalls, 1);
    } finally {
      try { if (runtime) await runtime.close(); }
      finally { await rm(directory, { recursive: true, force: true }); }
    }
  });

test('real SDK deferred startup disables MCP before locally rejected inference',
  { skip: !process.env.MVE_COPILOT_CLI, timeout: 95000 }, async () => {
    assert.ok(process.env.TMUX, 'actual SDK checks require a new owned tmux session');
    const directory = await mkdtemp(join(tmpdir(), 'mve-sdk-offline-'));
    const input = new PassThrough();
    const output = new PassThrough();
    const records = [];
    const state = { local: 0, logical: 0, closed: 0, tools: null };
    let runtime;
    let buffer = '';
    output.on('data', chunk => {
      buffer += chunk.toString();
      let newline;
      while ((newline = buffer.indexOf('\n')) >= 0) {
        records.push(JSON.parse(buffer.slice(0, newline)));
        buffer = buffer.slice(newline + 1);
      }
    });
    class OfflineRequests extends CopilotRequestHandler {
      async sendRequest(request, context) {
        state.local++;
        if (context.agentInvocationId) state.logical++;
        if (state.session) {
          const metadata = await state.session.rpc.tools.getCurrentMetadata();
          state.tools = metadata.tools?.map(tool => tool.name);
        }
        return new Response('{"error":{"message":"Offline fixture","type":"offline_fixture"}}',
          { status: 403, headers: { 'content-type': 'application/json' } });
      }
      async openWebSocket() {
        state.local++;
        throw new Error('offline_fixture');
      }
    }
    try {
      const running = runTransport({ input, output, runtimeFactory: async (req, deadline) => {
        runtime = await makeRuntime(req, deadline);
        // Pinned SDK test instrumentation; register before start, never use a forwarder.
        runtime.client.requestHandler = new OfflineRequests();
        runtime.client.setupClientGlobalHandlers();
        assert.ok(runtime.client.requestAdapter);
        assert.equal(runtime.client.clientGlobalHandlers.llmInference, runtime.client.requestAdapter);
        const create = runtime.client.createSession.bind(runtime.client);
        runtime.client.createSession = async config => {
          state.session = await create(config);
          return state.session;
        };
        return { client: runtime.client, async close() {
          await runtime.close();
          state.closed++;
        } };
      } });
      input.write(JSON.stringify(request({ model: 'gpt-6.1-sol', maxAiCredits: 30,
        remainingSeconds: 90, cliPath: process.env.MVE_COPILOT_CLI,
        baseDirectory: directory })) + '\n');
      const result = await running;
      assert.ok(state.local > 0 && state.logical > 0);
      assert.deepEqual(state.tools, ['isolated_exec']);
      assert.equal(state.closed, 1);
      const events = records.filter(record => record.type === 'event').map(record => record.event);
      assert.ok(events.some(item => item.type === 'assistant.turn_start'));
      assert.ok(events.some(item => item.type === 'model.call_failure'));
      assert.ok(events.some(item => item.type === 'session.mcp_servers_loaded' &&
        item.data.servers.length === 1 && item.data.servers[0].status === 'disabled'));
      assert.ok(!events.some(item => item.type.startsWith('mcp.') ||
        item.type.startsWith('tool.execution') || (item.type.startsWith('session.mcp_') &&
        item.type !== 'session.mcp_servers_loaded')));
      assert.equal(result.exitCode, 1);
      assert.equal(result.receipt.protocol_error, 'unexpected_runtime_activity');
      assert.equal(result.receipt.usage.credits_complete, false);
      assert.equal(result.receipt.usage.totalNanoAiu, null);
    } finally {
      try { if (runtime) await runtime.close(); }
      finally {
        input.destroy();
        output.destroy();
        await rm(directory, { recursive: true, force: true });
      }
    }
  });

test('partial terminal usage keeps reservation unknown, never certifies a zero', async () => {
  const result = await runFake({ usage: { aiCreditsStatus: 'partial' } });
  assert.equal(result.exitCode, 1);
  assert.equal(result.state.closed, 1);
  assert.equal(result.receipt.usage.totalNanoAiu, null);
  assert.equal(result.receipt.usage.aiCreditsStatus, 'partial');
});

test('event journal floods and output frame caps abort and clean up without complete usage', async () => {
  const flooded = await runFake({ async action(config) {
    for (let i = 0; i < 50; i++) config.onEvent(event('assistant.message_delta', { content: 'a'.repeat(100) }));
  } }, request(), { record: 1024, events: 2048 });
  assert.equal(flooded.receipt.protocol_error, 'event_journal_limit');
  assert.equal(flooded.receipt.usage.totalNanoAiu, null);
  assert.equal(flooded.state.closed, 1);
  const oversized = await runFake({ async action(config) {
    config.onEvent(event('assistant.message_delta', { content: 'a'.repeat(2000) }));
  } }, request(), { record: 1024, events: 4096 });
  assert.equal(oversized.receipt.protocol_error, 'output_record_limit');
  const input = new PassThrough();
  const output = new PassThrough();
  output.resume();
  const runtime = fakeRuntime({ hang: true });
  const running = runTransport({ input, output, runtimeFactory: runtime.factory,
    limits: { record: 1024, events: 4096 } });
  input.write(JSON.stringify(request()) + '\n');
  await new Promise(resolveTick => setImmediate(resolveTick));
  input.write('x'.repeat(1025));
  const inputCapped = await running;
  assert.equal(inputCapped.receipt.protocol_error, 'input_record_limit');
  assert.equal(runtime.state.closed, 1);
  input.destroy();
  output.destroy();
  const stream = new Writable({ write(chunk, encoding, callback) { this.savedCallback = callback; } });
  const errors = [];
  const queue = new OutputRecords(stream, error => errors.push(error), { record: 100, events: 130 });
  queue.write({ type: 'event', value: 'a'.repeat(50) });
  assert.throws(() => queue.write({ type: 'tool', value: 'b'.repeat(50) }), /queue_limit/);
  stream.savedCallback();
  await queue.flush();
  queue.dispose();
});

test('parent disconnect and original deadline abort hanging SDK work and reap owned runtime', async () => {
  const disconnected = await runFake({ hang: true, disconnect: true });
  assert.equal(disconnected.receipt.protocol_error, 'parent_disconnected');
  assert.equal(disconnected.state.closed, 1);
  const timed = await runFake({ hang: true }, request({ remainingSeconds: 0.02 }));
  assert.equal(timed.receipt.protocol_error, 'original_deadline_exhausted');
  assert.equal(timed.state.closed, 1);
  assert.equal(timed.receipt.usage.credits_complete, false);
  const input = new PassThrough();
  const output = new Writable({ write() {} });
  const runtime = fakeRuntime();
  const stalled = runTransport({ input, output, runtimeFactory: runtime.factory });
  input.write(JSON.stringify(request({ remainingSeconds: 0.02 })) + '\n');
  const stalledResult = await stalled;
  assert.equal(runtime.state.closed, 1);
  assert.equal(stalledResult.exitCode, 1);
  assert.equal(stalledResult.receipt.usage.credits_complete, false);
  assert.ok(output.destroyed);
  input.destroy();
});

test('invalid arguments are rejected, parallel tools serialize and correlation violations abort', async () => {
  let invalid;
  const safe = await runFake({ async action(config) {
    invalid = await config.tools[0].handler({ command: 'pwd', timeoutSeconds: 999, host: '/' },
      { sessionId: config.sessionId, toolName: 'isolated_exec', toolCallId: 'one' });
  } });
  assert.equal(invalid.resultType, 'rejected');
  assert.equal(safe.exitCode, 0);
  assert.equal(validateArguments({ command: 'x', timeoutSeconds: 2 }, 1), false);
  let results;
  const concurrent = await runFake({ delayToolResult: true, async action(config) {
    const call = id => config.tools[0].handler({ command: 'pwd', timeoutSeconds: 1 },
      { sessionId: config.sessionId, toolName: 'isolated_exec', toolCallId: id });
    results = await Promise.all([call('one'), call('two')]);
  } });
  assert.equal(concurrent.exitCode, 0);
  assert.deepEqual(concurrent.records.filter(record => record.type === 'tool').map(record => record.id),
    ['one', 'two']);
  assert.ok(results.every(result => result.resultType === 'success'));
  assert.equal(concurrent.state.closed, 1);
  assert.equal(concurrent.receipt.usage.totalNanoAiu, 123);
  const input = new PassThrough();
  const output = new PassThrough();
  output.resume();
  const runtime = fakeRuntime({ hang: true });
  const running = runTransport({ input, output, runtimeFactory: runtime.factory });
  input.write(JSON.stringify(request()) + '\n');
  await new Promise(resolveTick => setImmediate(resolveTick));
  input.write(JSON.stringify({ type: 'tool_result', id: 'unknown',
    result: { stdout: '', stderr: '', exit_code: 0 } }) + '\n');
  const uncorrelated = await running;
  assert.equal(uncorrelated.receipt.protocol_error, 'invalid_tool_result_correlation');
  assert.equal(runtime.state.closed, 1);
  input.destroy();
  output.destroy();
});

test('queued tools obey the original deadline, abort promptly and cannot reuse identities', async () => {
  for (const mode of ['deadline', 'abort', 'duplicate']) {
    const controller = new AbortController();
    let results;
    let handlers;
    const outcome = await runFake({ noToolResult: true, async action(config) {
      const call = id => config.tools[0].handler({ command: 'pwd', timeoutSeconds: 0.01 },
        { sessionId: config.sessionId, toolName: 'isolated_exec', toolCallId: id,
          signal: id === 'two' ? controller.signal : undefined });
      handlers = Promise.all([call('one'), call(mode === 'duplicate' ? 'one' : 'two')]);
      if (mode === 'abort') setImmediate(() => controller.abort());
      results = await handlers;
    } }, request({ remainingSeconds: 0.1 }));
    await handlers;
    assert.equal(outcome.receipt.protocol_error, {
      deadline: 'original_deadline_exhausted', abort: 'sdk_tool_aborted',
      duplicate: 'invalid_tool_call_id',
    }[mode]);
    assert.equal(outcome.receipt.usage.credits_complete, false);
    assert.equal(outcome.state.closed, 1);
    assert.ok(results.every(result => result.resultType === 'failure' || result.resultType === 'denied'));
    assert.ok(outcome.records.filter(record => record.type === 'tool').length <= 1);
  }
});

test('runtime setup creates missing sterile parents; strict startup failures precede sessions', async () => {
  const fixture = fileURLToPath(new URL(`./node_modules/.transport-tests-${crypto.randomUUID()}`, import.meta.url));
  const base = join(fixture, 'missing-parent', 'sdk');
  try {
    const first = await prepareRuntimeDirectories(base);
    const second = await prepareRuntimeDirectories(base);
    assert.notEqual(first.data, second.data);
    for (const directory of [base, first.data, first.work, second.data, second.work]) {
      assert.equal((await stat(directory)).mode & 0o777, 0o700);
      if (directory !== base) assert.deepEqual(await readdir(directory), []);
    }
    const blocked = join(fixture, 'not-a-directory');
    await writeFile(blocked, 'fixture');
    await assert.rejects(prepareRuntimeDirectories(join(blocked, 'sdk')), error =>
      error.transportCode === 'runtime_directory_setup_failed' &&
      error.message === 'runtime_directory_setup_failed');
    const input = new PassThrough();
    const output = new PassThrough();
    output.resume();
    const running = runTransport({ input, output,
      runtimeFactory: () => prepareRuntimeDirectories(join(blocked, 'sdk')) });
    input.write(JSON.stringify(request()) + '\n');
    const setupFailure = await running;
    assert.equal(setupFailure.receipt.protocol_error, 'runtime_directory_setup_failed');
    assert.equal(setupFailure.receipt.failure_stage, 'runtime_setup');
    assert.equal(setupFailure.receipt.usage.totalNanoAiu, null);
    input.destroy();
    output.destroy();
  } finally { await rm(fixture, { recursive: true, force: true }); }
  for (const options of [{ version: '1.0.104' }, { protocol: 4 }]) {
    const result = await runFake(options);
    assert.equal(result.state.created, 0);
    assert.equal(result.state.closed, 1);
    assert.equal(result.receipt.protocol_error, 'runtime_pin_mismatch');
    assert.equal(result.receipt.failure_stage, 'runtime_startup');
  }
  const createFailure = await runFake({ createError: true });
  assert.equal(createFailure.receipt.protocol_error, 'sdk_failure');
  assert.equal(createFailure.receipt.failure_stage, 'session_create');
  assert.equal(createFailure.state.sent, 0);
  assert.equal(createFailure.receipt.usage.totalNanoAiu, null);
  const runtime = await fakeRuntime().factory(request(), Date.now() + 1000);
  assert.deepEqual(await assertRuntime(runtime.client), {
    sdkVersion: '1.0.28', cliVersion: '1.0.105', protocolVersion: 3,
    isAuthenticated: true, userAuthentication: true,
  });
});
