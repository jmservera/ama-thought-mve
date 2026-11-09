import { test } from 'node:test';
import assert from 'node:assert/strict';
import { Readable } from 'node:stream';
import { existsSync } from 'node:fs';
import { createRequire } from 'node:module';
import { pathToFileURL } from 'node:url';
import { sessionConfig, noToolEvidence, readRequest, resolveCliPath, judgeSession,
  encodeResponse, VERSION } from './copilot-judge.mjs';

class ToolSet {
  constructor() { this.entries = []; }
  addBuiltIn(name) { this.entries.push(['builtin', name]); return this; }
  addMcp(name) { this.entries.push(['mcp', name]); return this; }
}

test('session disables every tool and all discovery without modifying experiment config', () => {
  const config = sessionConfig({ judge: { model: 'pinned-model' }, max_ai_credits: 10 }, 'session', ToolSet, () => {});
  assert.equal(config.model, 'pinned-model');
  assert.equal(config.reasoningEffort, 'medium');
  assert.deepEqual(config.availableTools.entries, []);
  assert.deepEqual(config.excludedTools.entries, [['builtin', '*'], ['mcp', '*']]);
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
            sendAndWait: async ({ prompt }) => {
              captured = prompt;
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
  });
