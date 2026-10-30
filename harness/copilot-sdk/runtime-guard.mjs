import { spawn } from 'node:child_process';
import { Transform, pipeline } from 'node:stream';
import { readFile, mkdir } from 'node:fs/promises';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { randomUUID } from 'node:crypto';

export const LIMITS = Object.freeze({
  record: 8 * 1024 * 1024,
  events: 64 * 1024 * 1024,
  stderr: 1024 * 1024,
});

// Validate frames before the SDK's JSON-RPC reader can buffer their bodies.
export class RpcFrames extends Transform {
  constructor(limit = LIMITS.record, aggregateLimit = LIMITS.events) {
    super();
    this.limit = limit;
    this.buffer = Buffer.alloc(0);
    this.length = null;
    this.total = 0;
    this.aggregateLimit = aggregateLimit;
  }
  _transform(chunk, encoding, done) {
    try {
      this.total += chunk.length;
      if (this.total > this.aggregateLimit) throw new Error('rpc_aggregate_limit');
      let offset = 0;
      while (offset < chunk.length) {
        const capacity = this.length === null ? 1024 : this.length;
        const take = Math.min(chunk.length - offset, capacity - this.buffer.length);
        if (take <= 0) throw new Error('rpc_frame_limit');
        this.buffer = Buffer.concat([this.buffer, chunk.subarray(offset, offset + take)]);
        offset += take;
        if (this.length === null) {
          const end = this.buffer.indexOf('\r\n\r\n');
          if (end < 0) {
            if (this.buffer.length === 1024) throw new Error('rpc_header_limit');
            continue;
          }
          const header = this.buffer.subarray(0, end).toString('ascii');
          const match = /^Content-Length: ([0-9]+)$/i.exec(header);
          if (!match) throw new Error('rpc_header_invalid');
          this.length = Number(match[1]);
          if (!Number.isSafeInteger(this.length) || this.length < 1 || this.length > this.limit)
            throw new Error('rpc_frame_limit');
          this.header = this.buffer.subarray(0, end + 4);
          this.buffer = this.buffer.subarray(end + 4);
        }
        if (this.buffer.length >= this.length) {
          const body = this.buffer.subarray(0, this.length);
          const rest = this.buffer.subarray(this.length);
          this.push(Buffer.concat([this.header, body]));
          this.buffer = Buffer.alloc(0);
          this.length = null;
          if (rest.length) {
            offset -= rest.length;
          }
        }
      }
      done();
    } catch (error) {
      done(error);
    }
  }
  _flush(done) {
    done(this.buffer.length || this.length !== null ? new Error('rpc_truncated') : undefined);
  }
}

export function hostEnvironment(source = process.env) {
  const result = {};
  // Keep the host OAuth/keychain context, never token/config override variables.
  for (const key of ['HOME', 'PATH', 'LANG', 'LC_ALL', 'XDG_RUNTIME_DIR', 'DBUS_SESSION_BUS_ADDRESS']) {
    if (typeof source[key] === 'string') result[key] = source[key];
  }
  return result;
}

export async function prepareRuntimeDirectories(baseDirectory) {
  try {
    await mkdir(baseDirectory, { recursive: true, mode: 0o700 });
    const directory = resolve(baseDirectory, `runtime-${randomUUID()}`);
    await mkdir(directory, { mode: 0o700 });
    const work = resolve(directory, 'work');
    const data = resolve(directory, 'data');
    await mkdir(work, { mode: 0o700 });
    await mkdir(data, { mode: 0o700 });
    return { work, data };
  } catch {
    throw Object.assign(new Error('runtime_directory_setup_failed'), {
      transportCode: 'runtime_directory_setup_failed',
    });
  }
}

export async function makeRuntime(request, deadline) {
  const { CopilotClient, RuntimeConnection } = await import('@github/copilot-sdk');
  const manifest = JSON.parse(await readFile(
    new URL('./node_modules/@github/copilot-sdk/package.json', import.meta.url), 'utf8'));
  if (manifest.version !== '1.0.28' || manifest.copilotCliVersion !== '1.0.105')
    throw new Error('sdk_pin_mismatch');
  const { work, data } = await prepareRuntimeDirectories(request.baseDirectory);
  const client = new CopilotClient({
    connection: RuntimeConnection.forStdio({
      path: process.execPath,
      args: [fileURLToPath(import.meta.url), '--guard', request.cliPath, String(deadline),
        '--disable-builtin-mcps'],
    }),
    mode: 'empty',
    baseDirectory: data,
    workingDirectory: work,
    env: hostEnvironment(),
    useLoggedInUser: true,
    logLevel: 'none',
  });
  // These pinned SDK internals are needed only to supervise its owned proxy:
  // startCLIServer otherwise unconditionally retains and prints raw stderr.
  const launch = client.startCLIServer.bind(client);
  let owned;
  let stderrBytes = 0;
  let guardFailure;
  let diagnosticBytes = 0;
  const savedConsole = new Map();
  for (const method of ['log', 'info', 'warn', 'error', 'debug']) {
    savedConsole.set(method, console[method]);
    console[method] = () => {
      diagnosticBytes += 15;
      if (diagnosticBytes > LIMITS.stderr - 1024) {
        guardFailure = true;
        owned?.kill('SIGTERM');
      } else {
        process.stderr.write('sdk_diagnostic\n');
      }
    };
  }
  client.startCLIServer = async () => {
    const started = launch();
    owned = client.cliProcess;
    if (!owned?.stderr) throw new Error('sdk_supervision_unavailable');
    owned.stderr.removeAllListeners('data');
    owned.stderr.on('data', chunk => {
      stderrBytes += chunk.length;
      if (stderrBytes > LIMITS.stderr) owned.kill('SIGTERM');
      guardFailure = true;
    });
    await started;
  };
  return {
    client,
    async close() {
      // The guard owns its process group and performs TERM/KILL/reap on EOF.
      // Never SIGKILL the guard before it has reaped its own CLI.
      if (owned && owned.exitCode === null && owned.signalCode === null) {
        const exited = new Promise(resolveExit => owned.once('close', resolveExit));
        owned.kill('SIGTERM');
        await exited;
      }
      try { await client.forceStop(); }
      finally {
        for (const [method, original] of savedConsole) console[method] = original;
      }
      if (guardFailure) throw new Error('runtime_guard_failure');
    },
  };
}

async function guardMain() {
  const cliPath = process.argv[3];
  const deadline = Number(process.argv[4]);
  const args = process.argv.slice(5);
  if (!cliPath?.startsWith('/') || !Number.isFinite(deadline) || deadline <= Date.now())
    throw new Error('guard_arguments');
  const child = spawn(cliPath, args, {
    cwd: process.cwd(), env: process.env, stdio: ['pipe', 'pipe', 'pipe'],
    detached: true,
  });
  let stopping = false;
  let failed = false;
  let stderrBytes = 0;
  let killTimer;
  const signalGroup = signal => {
    if (!child.pid) return;
    try { process.kill(-child.pid, signal); }
    catch (error) { if (error.code !== 'ESRCH') failed = true; }
  };
  const finish = failure => {
    if (stopping) return;
    failed ||= failure;
    stopping = true;
    signalGroup('SIGTERM');
    killTimer = setTimeout(() => signalGroup('SIGKILL'), 500);
  };
  const timer = setTimeout(() => finish(true), Math.max(1, deadline - Date.now()));
  process.on('SIGTERM', () => finish(false));
  process.on('SIGINT', () => finish(true));
  process.stdin.on('end', () => finish(false));
  process.stdin.on('error', () => finish(true));
  process.stdout.on('error', () => finish(true));
  child.on('error', () => finish(true));
  child.stderr.on('data', chunk => {
    stderrBytes += chunk.length;
    if (stderrBytes > LIMITS.stderr) finish(true);
  });
  pipeline(process.stdin, new RpcFrames(), child.stdin, error => { if (error) finish(true); });
  pipeline(child.stdout, new RpcFrames(), process.stdout, error => { if (error) finish(true); });
  await new Promise(resolveExit => child.once('close', resolveExit));
  // Kill descendants even if the group leader exited first.
  signalGroup('SIGKILL');
  clearTimeout(timer);
  clearTimeout(killTimer);
  if (!stopping) failed = true;
  if (failed) process.stderr.write('runtime_guard_failure\n');
  process.exitCode = failed ? 1 : 0;
  process.stdin.destroy();
}

if (process.argv[2] === '--guard' && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  guardMain().catch(() => {
    process.stderr.write('runtime_guard_failure\n');
    process.exitCode = 1;
  });
}
