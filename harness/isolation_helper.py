"""Fixed container supervisor and bounded regular-file state protocol."""
from __future__ import annotations

import base64
import ctypes
import hashlib
import json
import os
import selectors
import signal
import stat
import struct
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

MAGIC = b"ISOLATED1\n"
STATE_MAGIC = b"REGTREE1\n"
STATE_LIMIT = 32 * 1024 * 1024
FILE_LIMIT = 2 * 1024 * 1024
FILE_COUNT = 2048
OUTPUT_LIMIT = 1024 * 1024
HEADER_LIMIT = 48 * 1024 * 1024
UID = 1001
WORK = Path("/work")
ENV = {
    "PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": "/tmp", "TMPDIR": "/tmp",
    "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
    "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_SYSTEM": "/dev/null",
    "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_TERMINAL_PROMPT": "0",
    "GIT_NO_REPLACE_OBJECTS": "1", "GIT_OPTIONAL_LOCKS": "0",
}
EVALUATION_ENV_KEYS = {
    "PATH", "HOME", "TMPDIR", "TMP", "TEMP", "XDG_CACHE_HOME", "XDG_CONFIG_HOME",
    "XDG_DATA_HOME", "XDG_STATE_HOME", "LANG", "LC_ALL", "LC_CTYPE", "TZ",
    "PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "PYTHONNOUSERSITE", "PYTHONHASHSEED",
    "PYTEST_DISABLE_PLUGIN_AUTOLOAD", "TEST_CMD", "MVE_COMPLEXITY", "MVE_DUPLICATION", "MVE_LINT",
}
SUPERVISOR_CAPS = (1 << 1) | (1 << 5) | (1 << 6) | (1 << 7)


class ProtocolError(ValueError):
    """Malformed or over-limit sandbox data."""


def identity_facts():
    libc = ctypes.CDLL(None, use_errno=True)
    status = {}
    for line in Path("/proc/self/status").read_text().splitlines():
        name, _, value = line.partition(":")
        if name in ("CapEff", "CapPrm", "CapInh", "CapAmb", "CapBnd"):
            status[name] = int(value.strip(), 16)
    return {
        "uid": list(os.getresuid()), "gid": list(os.getresgid()),
        "dumpability": libc.prctl(3, 0, 0, 0, 0),
        "no_new_privileges": libc.prctl(39, 0, 0, 0, 0),
        "thread_count": len(os.listdir("/proc/self/task")),
        "capabilities": status,
    }


def verify_identity(facts, *, supervisor=False):
    uid = 0 if supervisor else UID
    expected = SUPERVISOR_CAPS if supervisor else 0
    if (facts["uid"] != [uid] * 3 or facts["gid"] != [uid] * 3
            or facts["dumpability"] != 0 or facts["no_new_privileges"] != 1
            or facts["thread_count"] != 1
            or facts["capabilities"]["CapEff"] != expected
            or facts["capabilities"]["CapPrm"] != expected
            or facts["capabilities"]["CapInh"] != 0 or facts["capabilities"]["CapAmb"] != 0
            or facts["capabilities"]["CapBnd"] != SUPERVISOR_CAPS):
        raise ProtocolError("Supervisor/child setup identity protection failed")


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def path_ok(value, *, git=True):
    if not isinstance(value, str) or not value or len(value.encode()) > 1024:
        raise ProtocolError("Invalid path")
    path = PurePosixPath(value)
    if (path.is_absolute() or str(path) != value or "\\" in value
            or any(p in ("", ".", "..") or len(p.encode()) > 255 for p in path.parts)
            or any(ord(c) < 32 or ord(c) == 127 for c in value)
            or (not git and ".git" in path.parts) or len(path.parts) > 32):
        raise ProtocolError("Unsafe path")
    return value


def regular_files(files, *, git=False):
    if not isinstance(files, list) or len(files) > FILE_COUNT:
        raise ProtocolError("File count exceeded")
    seen, size, result = set(), 0, []
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {"path", "mode", "content"}:
            raise ProtocolError("Invalid file entry")
        name = path_ok(entry["path"], git=git)
        if name in seen or type(entry["mode"]) is not int or entry["mode"] not in (0o644, 0o755):
            raise ProtocolError("Duplicate path or unsafe mode")
        seen.add(name)
        try:
            if not isinstance(entry["content"], str):
                raise TypeError("Base64 content must be a string")
            raw = base64.b64decode(entry["content"], validate=True)
        except (ValueError, TypeError) as exc:
            raise ProtocolError("Invalid file content") from exc
        size += len(raw)
        if len(raw) > FILE_LIMIT or size > STATE_LIMIT:
            raise ProtocolError("File bytes exceeded")
        result.append((name, entry["mode"], raw))
    for name in seen:
        if any(str(parent) in seen for parent in PurePosixPath(name).parents if str(parent) != "."):
            raise ProtocolError("File/directory collision")
    return sorted(result)


def manifest(files):
    return {name: [mode, hashlib.sha256(raw).hexdigest()] for name, mode, raw in files}


def read_exact(stream, size):
    data = bytearray()
    while len(data) < size:
        part = stream.read(size - len(data))
        if not part:
            raise ProtocolError("Truncated frame")
        data.extend(part)
    return bytes(data)


def frame(header, blob=b""):
    header = dict(header, blob_length=len(blob), blob_sha256=hashlib.sha256(blob).hexdigest())
    encoded = canonical(header)
    if len(encoded) > HEADER_LIMIT or len(blob) > STATE_LIMIT:
        raise ProtocolError("Frame limit exceeded")
    return MAGIC + struct.pack(">I", len(encoded)) + encoded + blob


def unframe(stream):
    if read_exact(stream, len(MAGIC)) != MAGIC:
        raise ProtocolError("Invalid frame magic")
    size = struct.unpack(">I", read_exact(stream, 4))[0]
    if size > HEADER_LIMIT:
        raise ProtocolError("Frame header exceeded")
    encoded = read_exact(stream, size)
    header = json.loads(encoded)
    if canonical(header) != encoded or not isinstance(header, dict):
        raise ProtocolError("Noncanonical frame")
    length = header.get("blob_length")
    if type(length) is not int or not 0 <= length <= STATE_LIMIT:
        raise ProtocolError("Frame state exceeded")
    blob = read_exact(stream, length)
    if hashlib.sha256(blob).hexdigest() != header.get("blob_sha256") or stream.read(1):
        raise ProtocolError("Invalid digest or trailing frame")
    return header, blob


def pack_tree(root):
    entries, chunks, total, nodes, file_count = [], [], 0, 0, 0
    for current, dirs, names in os.walk(root, followlinks=False):
        dirs.sort()
        names.sort()
        for name in dirs + names:
            nodes += 1
            if nodes > FILE_COUNT * 2:
                raise ProtocolError("State directory/file count exceeded")
            path = Path(current) / name
            info = path.lstat()
            rel = path_ok(path.relative_to(root).as_posix())
            if stat.S_ISDIR(info.st_mode):
                if name in names:
                    raise ProtocolError("Tree changed during capture")
                if info.st_mode & 0o7000:
                    raise ProtocolError("State privileged directory modes rejected")
                entries.append([rel, 0o755, -1])
                continue
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ProtocolError("State links/special files rejected")
            if info.st_mode & 0o7000:
                raise ProtocolError("State privileged modes rejected")
            file_count += 1
            if info.st_size > FILE_LIMIT or file_count > FILE_COUNT:
                raise ProtocolError("State file limit exceeded")
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                before = os.fstat(fd)
                raw = os.read(fd, FILE_LIMIT + 1)
                after = os.fstat(fd)
            finally:
                os.close(fd)
            if (before.st_ino, before.st_size, before.st_mtime_ns) != (
                    after.st_ino, after.st_size, after.st_mtime_ns) or len(raw) != before.st_size:
                raise ProtocolError("Unstable state file")
            mode = 0o755 if info.st_mode & 0o111 else 0o644
            entries.append([rel, mode, len(raw)])
            chunks.append(raw)
            total += len(raw)
            if total > STATE_LIMIT:
                raise ProtocolError("State bytes exceeded")
    header = canonical(entries)
    data = STATE_MAGIC + struct.pack(">I", len(header)) + header + b"".join(chunks)
    if len(data) > STATE_LIMIT:
        raise ProtocolError("State frame exceeded")
    return data


def restore_tree(data, root):
    import io
    if len(data) > STATE_LIMIT:
        raise ProtocolError("State frame exceeded")
    stream = io.BytesIO(data)
    if read_exact(stream, len(STATE_MAGIC)) != STATE_MAGIC:
        raise ProtocolError("Invalid state magic")
    size = struct.unpack(">I", read_exact(stream, 4))[0]
    if size > STATE_LIMIT:
        raise ProtocolError("State index exceeded")
    encoded = read_exact(stream, size)
    entries = json.loads(encoded)
    if canonical(entries) != encoded or not isinstance(entries, list) or len(entries) > FILE_COUNT * 2:
        raise ProtocolError("Invalid state index")
    files, seen, directories = [], set(), set()
    for entry in entries:
        if not isinstance(entry, list) or len(entry) != 3:
            raise ProtocolError("Invalid state entry")
        name, mode, length = entry
        path_ok(name)
        if name in seen or type(mode) is not int or mode not in (0o644, 0o755):
            raise ProtocolError("Duplicate state path or mode")
        if type(length) is not int or not -1 <= length <= FILE_LIMIT:
            raise ProtocolError("State file bytes exceeded")
        seen.add(name)
        if length == -1:
            if mode != 0o755:
                raise ProtocolError("Invalid directory mode")
            directories.add(name)
        else:
            files.append((name, mode, read_exact(stream, length)))
    if len(files) > FILE_COUNT:
        raise ProtocolError("State file count exceeded")
    for name in seen:
        if any(str(parent) in seen - directories for parent in PurePosixPath(name).parents):
            raise ProtocolError("State file/directory collision")
    if stream.read(1):
        raise ProtocolError("Trailing state data")
    for name in sorted(directories, key=lambda value: (len(PurePosixPath(value).parts), value)):
        (root / name).mkdir(mode=0o755, parents=True, exist_ok=True)
    for name, mode, raw in files:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
        try:
            if os.write(fd, raw) != len(raw):
                raise ProtocolError("Incomplete state file restoration")
            os.fchmod(fd, mode)
        finally:
            os.close(fd)


def drop_identity():
    libc = ctypes.CDLL(None, use_errno=True)
    os.setgroups([])
    os.setgid(UID)
    os.setuid(UID)
    # setuid clears effective/permitted caps; clear inheritable and ambient too.
    class CapHeader(ctypes.Structure):
        _fields_ = [("version", ctypes.c_uint32), ("pid", ctypes.c_int)]
    class CapData(ctypes.Structure):
        _fields_ = [("effective", ctypes.c_uint32), ("permitted", ctypes.c_uint32),
                    ("inheritable", ctypes.c_uint32)]
    header, data = CapHeader(0x20080522, 0), (CapData * 2)()
    if libc.capset(ctypes.byref(header), ctypes.byref(data)) != 0:
        raise OSError(ctypes.get_errno(), "capset")
    if libc.prctl(38, 1, 0, 0, 0) != 0 or libc.prctl(4, 0, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "prctl")
    os.umask(0o022)


def candidate_pids():
    result = []
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            status = Path("/proc", name, "status").read_text()
            uid = next(line for line in status.splitlines() if line.startswith("Uid:"))
            if int(uid.split()[1]) == UID:
                result.append(int(name))
        except (FileNotFoundError, ProcessLookupError, StopIteration):
            continue
    return result


def quiesce():
    for _ in range(100):
        alive = candidate_pids()
        if not alive:
            return
        for pid in alive:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        while True:
            try:
                pid, _ = os.waitpid(-1, os.WNOHANG)
                if not pid:
                    break
            except ChildProcessError:
                break
        time.sleep(0.01)
    raise ProtocolError("Candidate descendants remain")


def run_child(argv, timeout, limit=OUTPUT_LIMIT, input_data=None, extra_env=None):
    # This fixed supervisor starts no threads. Refuse even foreign-library
    # threads before the child-only credential/audit transition can fork.
    if len(os.listdir("/proc/self/task")) != 1:
        raise ProtocolError("Credential transition requires a single-threaded supervisor")
    audit_read, audit_write = os.pipe2(os.O_CLOEXEC)

    def setup():
        drop_identity()
        facts = identity_facts()
        verify_identity(facts)
        encoded = canonical(facts)
        if len(encoded) > 4096 or os.write(audit_write, encoded) != len(encoded):
            raise ProtocolError("Child setup evidence exceeded")
        # The model executable never inherits this one-way setup evidence pipe.
        os.close(audit_write)

    try:
        process = subprocess.Popen(
            argv, cwd=WORK, env={**ENV, **(extra_env or {})},
            stdin=subprocess.PIPE if input_data is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, close_fds=True,
            pass_fds=(audit_write,),
            preexec_fn=setup,  # noqa: PLW1509 - Kernel task-count gate enforces single-threaded fork.
            start_new_session=True,
        )
    except BaseException:
        os.close(audit_read)
        raise
    finally:
        os.close(audit_write)
    try:
        evidence = os.read(audit_read, 4097)
        child_setup = json.loads(evidence)
        if canonical(child_setup) != evidence:
            raise ProtocolError("Invalid child setup evidence")
        verify_identity(child_setup)
    except BaseException:
        process.kill()
        process.wait()
        quiesce()
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream and not stream.closed:
                stream.close()
        raise
    finally:
        os.close(audit_read)
    selector = selectors.DefaultSelector()
    for stream in (process.stdout, process.stderr):
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ)
    position = 0
    if input_data is not None:
        os.set_blocking(process.stdin.fileno(), False)
        selector.register(process.stdin, selectors.EVENT_WRITE)
    chunks = {process.stdout: bytearray(), process.stderr: bytearray()}
    deadline, failure, size = time.monotonic() + timeout, None, 0
    try:
        while selector.get_map() or process.poll() is None:
            if time.monotonic() >= deadline:
                failure = "Candidate deadline exceeded"
                break
            for key, _ in selector.select(min(0.05, max(0, deadline - time.monotonic()))):
                if key.fileobj is process.stdin:
                    try:
                        position += os.write(key.fd, input_data[position:position + 65536])
                    except BrokenPipeError:
                        position = len(input_data)
                    if position == len(input_data):
                        selector.unregister(key.fileobj)
                        process.stdin.close()
                    continue
                part = os.read(key.fd, 65536)
                if not part:
                    selector.unregister(key.fileobj)
                    continue
                size += len(part)
                if size > limit:
                    failure = "Candidate output exceeded"
                    break
                chunks[key.fileobj].extend(part)
            if failure:
                break
    finally:
        selector.close()
        if process.poll() is None:
            process.kill()
        process.wait()
        quiesce()
        process.stdout.close()
        process.stderr.close()
        if process.stdin and not process.stdin.closed:
            process.stdin.close()
    if failure:
        raise ProtocolError(failure)
    stdout = chunks[process.stdout].decode("utf-8", "replace")
    stderr = chunks[process.stderr].decode("utf-8", "replace")
    if len(stdout.encode()) + len(stderr.encode()) > limit:
        raise ProtocolError("Candidate normalized output exceeded")
    return {"exit_code": process.returncode, "stdout": stdout, "stderr": stderr,
            "child_setup": child_setup}


def git(*args):
    result = subprocess.run(
        ["/usr/bin/git", "--no-pager", "-c", "core.hooksPath=/dev/null",
         "-c", "core.fsmonitor=false", "-c", "core.attributesFile=/dev/null", *args],
        cwd=WORK, env=ENV, stdin=subprocess.DEVNULL, capture_output=True, check=True,
        timeout=30,
    )
    if len(result.stdout) > STATE_LIMIT or len(result.stderr) > OUTPUT_LIMIT:
        raise ProtocolError("Git output exceeded")
    return result.stdout


def seed_child(files, bundle=b""):
    validated = regular_files(files)
    git("init", "--initial-branch=main", ".")
    if bundle:
        bundle_path = WORK / ".trusted-seed.bundle"
        bundle_path.write_bytes(bundle)
        try:
            heads = git("bundle", "list-heads", str(bundle_path), "HEAD").splitlines()
            if len(heads) != 1:
                raise ProtocolError("Trusted bundle must name HEAD")
            seed_head, name = heads[0].split()
            if name != b"HEAD":
                raise ProtocolError("Trusted bundle HEAD missing")
            git("fetch", "--update-head-ok", "--no-write-fetch-head", str(bundle_path), "+refs/*:refs/*")
            git("update-ref", "refs/heads/main", seed_head)
            git("read-tree", "HEAD")
        finally:
            bundle_path.unlink(missing_ok=True)
    for name, mode, raw in validated:
        path = WORK / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
        path.chmod(mode)
    if bundle:
        exported = export_child()
        if manifest(regular_files(exported["files"])) != manifest(validated):
            raise ProtocolError("Trusted bundle HEAD differs from seed regular content")
    git("config", "user.name", "Isolated candidate")
    git("config", "user.email", "candidate@invalid")
    if not bundle:
        git("add", "--all", "--", ".")
        git("commit", "--allow-empty", "-m", "Neutral seed")
    return {"seed_head": git("rev-parse", "--verify", "HEAD").decode().strip()}


def export_child(review=False):
    # Never honor candidate config, hooks, attributes, replacement refs or archives.
    config = WORK / ".git/config"
    config.write_text("[core]\nrepositoryformatversion = 0\nbare = false\n")
    head = git("rev-parse", "--verify", "HEAD").decode().strip()
    if len(head) != 40 or any(c not in "0123456789abcdef" for c in head):
        raise ProtocolError("Invalid HEAD")
    entries = git("ls-tree", "-r", "-z", "--full-tree", "HEAD").split(b"\0")
    files, total = [], 0
    for entry in entries:
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, kind, oid = metadata.split()
        if mode not in (b"100644", b"100755") or kind != b"blob":
            raise ProtocolError("Nonregular committed tree")
        name = path_ok(raw_path.decode("utf-8"), git=False)
        size = int(git("cat-file", "-s", oid))
        total += size
        if size > FILE_LIMIT or total > STATE_LIMIT or len(files) >= FILE_COUNT:
            raise ProtocolError("Committed tree exceeded")
        raw = git("cat-file", "blob", oid)
        if len(raw) != size:
            raise ProtocolError("Inconsistent Git blob")
        files.append({"path": name, "mode": int(mode, 8) & 0o777,
                      "content": base64.b64encode(raw).decode()})
    changed = []
    if review:
        status = git("status", "--porcelain=v1", "-z", "--untracked-files=all", "--no-renames")
        for item in status.split(b"\0"):
            if not item:
                continue
            if len(item) < 4 or item[2:3] != b" ":
                raise ProtocolError("Invalid isolated Git status")
            changed.append(path_ok(item[3:].decode("utf-8"), git=False))
    return {"files": files, "head": head, "work_changed_paths": sorted(set(changed)),
            "commit_count": int(git("rev-list", "--count", "HEAD"))}


def supervisor(request, blob):
    op = request.get("op")
    timeout = request.get("timeout", 120)
    limit = 600 if op == "evaluate" else 300
    if type(timeout) not in (int, float) or not 0 < timeout <= limit:
        raise ProtocolError("Invalid timeout")
    if op in ("execute", "export"):
        restored = run_child(
            ["/usr/local/bin/python3", "-I", "/opt/isolation_helper.py", "_restore"],
            timeout, input_data=blob,
        )
        if restored["exit_code"]:
            raise ProtocolError(restored["stderr"])
    if op == "seed":
        # Seed input is trusted regular content, but Git and all candidate data
        # processing still run with the candidate identity.
        result = run_child(
            ["/usr/local/bin/python3", "-I", "/opt/isolation_helper.py", "_seed"],
            timeout, HEADER_LIMIT, input_data=frame({"files": request["files"]}, blob),
        )
        if result["exit_code"]:
            raise ProtocolError(result["stderr"])
        return {**json.loads(result["stdout"]), "child_setup": result["child_setup"]}, pack_tree(WORK)
    if op == "execute":
        command = request.get("command")
        if not isinstance(command, str) or not command or len(command.encode()) > 65536:
            raise ProtocolError("Invalid command")
        result = run_child(["/bin/sh", "-c", command], timeout)
        return result, pack_tree(WORK)
    if op == "export":
        result = run_child(
            ["/usr/local/bin/python3", "-I", "/opt/isolation_helper.py", "_export",
             "review" if request.get("review") else "head"],
            timeout, HEADER_LIMIT,
        )
        if result["exit_code"]:
            raise ProtocolError(result["stderr"])
        exported = json.loads(result["stdout"])
        exported["child_setup"] = result["child_setup"]
        # No candidate processes remain while privileged regular files are read.
        work = []
        if request.get("review"):
            import io
            data = pack_tree(WORK)
            stream = io.BytesIO(data[len(STATE_MAGIC):])
            index = json.loads(read_exact(stream, struct.unpack(">I", read_exact(stream, 4))[0]))
            for name, mode, length in index:
                if length == -1:
                    continue
                raw = read_exact(stream, length)
                if name.split("/")[0] != ".git":
                    work.append((name, mode, raw))
        exported["review"] = next(
            (base64.b64encode(raw).decode() for name, _, raw in work if name == "REVIEW.md"), None,
        )
        return exported, b""
    if op == "evaluate":
        argv = request.get("argv")
        if (not isinstance(argv, list) or not argv or len(argv) > 128
                or any(not isinstance(a, str) or len(a.encode()) > 65536 for a in argv)
                or not argv[0].startswith("/")):
            raise ProtocolError("Invalid trusted evaluator argv")
        env = request.get("env") or {}
        if (not isinstance(env, dict) or not set(env) <= EVALUATION_ENV_KEYS
                or any(not isinstance(value, str) or "\0" in value or len(value) > 65536
                       for value in env.values())):
            raise ProtocolError("Invalid trusted evaluator environment")
        result = run_child(argv, timeout, extra_env=env)
        result["result"] = None
        name = request.get("result_path")
        if name is not None:
            rel = path_ok(name.removeprefix("/tmp/"))
            if not name.startswith("/tmp/") or "/" in rel:
                raise ProtocolError("Evaluator result must be a /tmp regular basename")
            path = Path("/tmp") / rel
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > OUTPUT_LIMIT:
                raise ProtocolError("Invalid evaluator result file")
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
            try:
                raw = os.read(fd, OUTPUT_LIMIT + 1)
            finally:
                os.close(fd)
            if len(raw) > OUTPUT_LIMIT:
                raise ProtocolError("Evaluator result exceeded")
            result["result"] = base64.b64encode(raw).decode()
        return result, b""
    raise ProtocolError("Unknown operation")


def main():
    if len(sys.argv) > 1:
        if os.getuid() != UID:
            raise ProtocolError("Child helper must be unprivileged")
        if sys.argv[1] == "_seed":
            request, bundle = unframe(sys.stdin.buffer)
            value = seed_child(request["files"], bundle)
        elif sys.argv[1] == "_export":
            value = export_child(len(sys.argv) > 2 and sys.argv[2] == "review")
        elif sys.argv[1] == "_restore":
            restore_tree(sys.stdin.buffer.read(STATE_LIMIT + 1), WORK)
            value = {}
        else:
            raise ProtocolError("Unknown child operation")
        sys.stdout.buffer.write(canonical(value))
        return
    if os.getuid() != 0:
        raise ProtocolError("Supervisor identity required")
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(4, 0, 0, 0, 0) or libc.prctl(36, 1, 0, 0, 0):
        raise ProtocolError("Supervisor process protection failed")
    try:
        before = identity_facts()
        verify_identity(before, supervisor=True)
        request, blob = unframe(sys.stdin.buffer)
        result, state = supervisor(request, blob)
        after = identity_facts()
        verify_identity(after, supervisor=True)
        sys.stdout.buffer.write(frame(
            {"ok": True, **result, "supervisor": {"before": before, "after": after}}, state,
        ))
    except (OSError, ValueError, TypeError, KeyError, subprocess.SubprocessError) as exc:
        quiesce()
        sys.stdout.buffer.write(frame({"ok": False, "error": str(exc)[:8192]}))


if __name__ == "__main__":
    main()
