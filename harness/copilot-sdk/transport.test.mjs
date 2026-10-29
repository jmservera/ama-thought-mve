import test from 'node:test';
import assert from 'node:assert/strict';
import { PassThrough, Writable } from 'node:stream';
import { once } from 'node:events';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { readdir, rm, stat, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { Evidence, InputRecords, OutputRecords, assertRuntime, permissionHandler,
  runTransport, sessionConfig, validateArguments } from './transport.mjs';
import { RpcFrames, hostEnvironment, prepareRuntimeDirectories } from './runtime-guard.mjs';

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
            config.onEvent(usage(config.sessionId, options.usage));
            config.onEvent(event('session.idle', {}));
          },
          rpc: { async shutdown() { config.onEvent(shutdown(config.sessionId)); } },
        };
      },
    };
    return { client, async close() { state.closed++; } };
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
      if (record.type === 'tool' && !options.noToolResult)
        input.write(JSON.stringify({ type: 'tool_result', id: record.id,
          result: { stdout: 'bounded output', stderr: '', exit_code: 0 } }) + '\n');
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

test('NDJSON happy path preserves raw events, exact shared budget and correlated tool results', async () => {
  let toolResult;
  const result = await runFake({ async action(config) {
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

test('invalid tool arguments are safe errors; pending-tool/correlation violations abort', async () => {
  let invalid;
  const safe = await runFake({ async action(config) {
    invalid = await config.tools[0].handler({ command: 'pwd', timeoutSeconds: 999, host: '/' },
      { sessionId: config.sessionId, toolName: 'isolated_exec', toolCallId: 'one' });
  } });
  assert.equal(invalid.resultType, 'rejected');
  assert.equal(safe.exitCode, 0);
  assert.equal(validateArguments({ command: 'x', timeoutSeconds: 2 }, 1), false);
  const concurrent = await runFake({ noToolResult: true, async action(config) {
    const call = id => config.tools[0].handler({ command: 'pwd', timeoutSeconds: 1 },
      { sessionId: config.sessionId, toolName: 'isolated_exec', toolCallId: id });
    await Promise.all([call('one'), call('two')]);
  } });
  assert.equal(concurrent.receipt.protocol_error, 'pending_tool_limit');
  assert.equal(concurrent.state.closed, 1);
  assert.equal(concurrent.receipt.usage.totalNanoAiu, null);
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
