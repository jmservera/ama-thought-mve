import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Readable } from 'node:stream';
import { existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { sessionConfig, noToolEvidence, readRequest, resolveCliPath, judgeSession,
  encodeResponse, verdictSchema, VERSION } from './copilot-judge.mjs';

class ToolSet {
  constructor() { this.entries = []; }
  addBuiltIn(name) { this.entries.push(['builtin', name]); return this; }
  addMcp(name) { this.entries.push(['mcp', name]); return this; }
  toArray() { return this.entries.map(([source, name]) => `${source}:${name}`); }
}

test('session disables every tool and all discovery without modifying experiment config', () => {
  const config = sessionConfig({ judge: { model: 'pinned-model' }, max_ai_credits: 10 }, 'session', ToolSet, () => {});
  assert.equal(config.model, 'pinned-model');
  assert.equal(config.reasoningEffort, 'medium');
  assert.deepEqual(config.availableTools, []);
  assert.deepEqual(config.excludedTools, ['builtin:*', 'mcp:*']);
  assert.deepEqual(config.tools, []);
  assert.equal(config.enableConfigDiscovery, false);
  assert.equal(config.enableExperimentalMode, false);
  assert.deepEqual(config.infiniteSessions, { enabled: false });
  assert.equal(config.onPermissionRequest().kind, 'denied-no-approval-rule-and-could-not-request-from-user');
});

test('no-tool evidence accepts only an empty catalog and forbids tool execution', () => {
  class Base { observe(event) { this.last = event; } }
  const Evidence = noToolEvidence(Base);
  const evidence = new Evidence();
  evidence.verifyToolCatalog({ tools: [] });
  assert.equal(evidence.toolCatalogVerified, true);
  assert.throws(() => evidence.verifyToolCatalog({ tools: [{ name: 'shell' }] }));
  assert.throws(() => evidence.verifyToolCatalog({}));
  assert.throws(() => evidence.observe({ type: 'tool.execution_start' }));
  evidence.observe({ type: 'assistant.message' });
  assert.equal(evidence.last.type, 'assistant.message');
});

test('stdin requires the exact adapter revision and bounded request', async () => {
  const request = { schema: 'blind-s1-judging-v1', judge: { model: 'pinned-model', version: VERSION },
    timeout_seconds: 30, max_ai_credits: 10 };
  assert.deepEqual(await readRequest(Readable.from([Buffer.from(JSON.stringify(request))])), request);
  await assert.rejects(readRequest(Readable.from([Buffer.from(JSON.stringify({
    ...request, judge: { ...request.judge, version: 'different' },
  }))])));
  await assert.rejects(readRequest(Readable.from([Buffer.alloc(2 * 1024 * 1024 + 1)])));
});

test('CLI paths resolve explicitly; a relative override cannot bypass the transport guard', () => {
  assert.equal(resolveCliPath({ JUDGING_COPILOT_PATH: process.execPath }), process.execPath);
  assert.throws(() => resolveCliPath({ JUDGING_COPILOT_PATH: 'copilot' }));
  assert.throws(() => resolveCliPath({ PATH: '/missing-judge-path' }));
});

test('serialized verdict preserves duplicate model keys for controller rejection', () => {
  const rawVerdictJson = '{"scenarios":[],"scenarios":[{"scenario_id":"duplicate"}]}';
  const output = encodeResponse({ judge_id: 'judge', verdict: JSON.parse(rawVerdictJson), rawVerdictJson });
  assert.equal(output, '{"judge_id":"judge","verdict":' + rawVerdictJson + '}');
});

const sdkInstalled = existsSync(new URL('../harness/copilot-sdk/node_modules/@github/copilot-sdk/package.json',
  import.meta.url));

test('startup failure retains safe diagnostics without prompts, responses or provider messages', async () => {
  const diagnostics = [];
  let closed = 0;
  class Evidence {
    receipt() { return { usage: { credits_complete: false, totalNanoAiu: null }, protocol_error: 'judge_runtime_failure' }; }
  }
  await assert.rejects(judgeSession({ judge: { id: 'judge', model: 'pinned-model' },
    timeout_seconds: 30, max_ai_credits: 30, specimen: { secret: 'private-specimen' } }, {
    ToolSet, Evidence, cliPath: '/unused', assertRuntime: async () => {},
    makeRuntime: async () => ({ close: async () => { closed++; }, client: {
      createSession: async () => { throw new TypeError('list is not iterable'); },
    } }), onDiagnostic: async value => { diagnostics.push(value); },
  }), /reservation must be retained/);
  assert.equal(closed, 1);
  assert.equal(diagnostics[0].stage, 'session_create');
  assert.deepEqual(diagnostics[0].failure, { name: 'TypeError', code: 'sdk_tool_filter_not_iterable' });
  assert.equal(diagnostics[0].prompt_dispatched, false);
  assert.equal(diagnostics[0].runtime_closed, true);
  assert.equal(diagnostics[0].usage.totalNanoAiu, null);
  assert.equal(JSON.stringify(diagnostics).includes('private-specimen'), false);
});

test('CommonJS SDK tool filters normalize in the ESM client without starting a runtime',
  { skip: !sdkInstalled }, async () => {
    const require = createRequire(import.meta.url);
    const commonjs = await import(pathToFileURL(require.resolve('@github/copilot-sdk', {
      paths: [new URL('../harness/copilot-sdk/', import.meta.url).pathname],
    })).href);
    const esm = await import(new URL('../harness/copilot-sdk/node_modules/@github/copilot-sdk/dist/index.js',
      import.meta.url));
    assert.notEqual(commonjs.ToolSet, esm.ToolSet);
    const client = new esm.CopilotClient({ mode: 'empty', autoStart: false, autoRestart: false,
      baseDirectory: new URL('../.study/offline-judge-config-test', import.meta.url).pathname });
    const config = sessionConfig({ judge: { model: 'pinned-model' }, max_ai_credits: 30 },
      'offline-session', commonjs.ToolSet, () => {});

    assert.deepEqual(client.resolveToolFilterOptions(config), {
      availableTools: [], excludedTools: ['builtin:*', 'mcp:*'], toolFilterPrecedence: 'excluded',
    });
    assert.equal(Boolean(client.connection), false);
    assert.equal(Boolean(client.cliProcess), false);
  });

test('actual SDK evidence completes a no-tool judge session with correlated billing, without inference',
  { skip: !sdkInstalled }, async () => {
    const require = createRequire(import.meta.url);
    const sdk = await import(pathToFileURL(require.resolve('@github/copilot-sdk', {
      paths: [new URL('../harness/copilot-sdk/', import.meta.url).pathname],
    })).href);
    const { Evidence, assertRuntime } = await import('../harness/copilot-sdk/transport.mjs');
    const request = { judge: { id: 'judge', model: 'pinned-model', version: VERSION },
      timeout_seconds: 30, max_ai_credits: 10, rubric: {}, specimen: { specimen_id: 'blind' },
      response_shape: { scenarios: [] } };
    const event = (type, data) => ({ id: crypto.randomUUID(), type, data });
    let closed = 0;
    let captured;
    let capturedSchema;
    const makeRuntime = async () => ({
      close: async () => { closed++; },
      client: {
        start: async () => {},
        getStatus: async () => ({ version: '1.0.105', protocolVersion: 3 }),
        ping: async () => ({ protocolVersion: 3 }),
        getAuthStatus: async () => ({ isAuthenticated: true, authType: 'user' }),
        createSession: async config => {
          config.onEvent(event('session.start', { sessionId: config.sessionId, selectedModel: 'pinned-model',
            reasoningEffort: 'medium', copilotVersion: '1.0.105', sessionLimits: { maxAiCredits: 10 } }));
          return {
            sessionId: config.sessionId,
            sendAndWait: async ({ prompt, responseSchema }) => {
              captured = prompt;
              capturedSchema = responseSchema;
              config.onEvent(event('assistant.message', { content: '{"scenarios":[]}' }));
              config.onEvent(event('assistant.usage', { model: 'pinned-model', reasoningEffort: 'medium',
                aiCreditsStatus: 'complete',
                accounting: { sourceSessionId: config.sessionId, sequence: 1, usageId: 'call-one' },
                copilotUsage: { totalNanoAiu: 123 } }));
              config.onEvent(event('session.idle', {}));
            },
            rpc: {
              tools: { initializeAndValidate: async () => {}, getCurrentMetadata: async () => ({ tools: [] }) },
              shutdown: async () => config.onEvent(event('session.shutdown', { shutdownType: 'routine',
                currentModel: 'pinned-model', totalNanoAiu: 123, usageAccountingWatermarks: { [config.sessionId]: 1 },
                modelMetrics: { 'pinned-model': { totalNanoAiu: 123, requests: { count: 1 } } } })),
            },
          };
        },
      },
    });
    const response = await judgeSession(request, { ToolSet: sdk.ToolSet, Evidence, assertRuntime, makeRuntime,
      cliPath: '/unused-trusted-test-cli' });
    assert.deepEqual(response.usage, { credits_complete: true, totalNanoAiu: 123 });
    assert.deepEqual(response.verdict, { scenarios: [] });
    assert.equal(closed, 1);
    assert.match(captured, /"specimen_id":"blind"/);
    assert.equal(captured.includes('cliPath'), false);
    assert.deepEqual(capturedSchema.required, ['scenarios']);
    assert.deepEqual(capturedSchema.properties.scenarios.items.required,
      ['scenario_id', 'scores', 'evidence_ids', 'rationale']);
  });

test('verdictSchema constrains required fields, dimensions, scenario IDs and allowed evidence IDs', () => {
  const schema = verdictSchema({
    scenarios: [
      { id: 'registration', final: { observations: [{ id: 'registration:1' }], error_type: null } },
      { id: 'ranking', final: { observations: [], error_type: 'AttributeError' } },
    ],
  });
  const item = schema.properties.scenarios.items;
  assert.equal(schema.additionalProperties, false);
  assert.equal(item.additionalProperties, false);
  assert.deepEqual(item.required, ['scenario_id', 'scores', 'evidence_ids', 'rationale']);
  assert.deepEqual(item.properties.scenario_id.enum, ['registration', 'ranking']);
  assert.deepEqual(item.properties.evidence_ids.items.enum, ['registration:1', 'ranking:error']);
  assert.deepEqual(item.properties.scores.required,
    ['functional_completeness', 'workflow_coherence', 'error_recovery', 'api_usability']);
});
