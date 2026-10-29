"""Trusted Docker broker: no candidate state is extracted on the host."""
from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import selectors
import subprocess
import time
import uuid
from functools import wraps
from pathlib import Path

try:
    from .isolation_helper import (
        EVALUATION_ENV_KEYS,
        HEADER_LIMIT,
        OUTPUT_LIMIT,
        STATE_LIMIT,
        canonical,
        frame,
        manifest,
        path_ok,
        regular_files,
        unframe,
        verify_identity,
    )
except ImportError:
    from isolation_helper import (
        EVALUATION_ENV_KEYS,
        HEADER_LIMIT,
        OUTPUT_LIMIT,
        STATE_LIMIT,
        canonical,
        frame,
        manifest,
        path_ok,
        regular_files,
        unframe,
        verify_identity,
    )


class IsolationError(RuntimeError):
    """Isolation, state publication, or ownership verification failed."""


def fail_closed(method):
    @wraps(method)
    def guarded(*args, **kwargs):
        try:
            return method(*args, **kwargs)
        except IsolationError:
            raise
        except Exception as exc:
            raise IsolationError(f"{method.__name__}: {type(exc).__name__}: {str(exc)[:2048]}") from exc
    return guarded


def atomic(path, content):
    pending = path.with_suffix(path.suffix + ".pending")
    fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        pending.unlink(missing_ok=True)


class SandboxBroker:
    """Single opaque candidate state, immutable image, exact-owned cleanup."""

    @fail_closed
    def __init__(self, image: str, directory: Path, *, timeout_seconds=120,
                 state_limit=STATE_LIMIT, output_limit=OUTPUT_LIMIT):
        if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
            raise IsolationError("Use the inspected immutable local image content ID")
        if state_limit != STATE_LIMIT or output_limit != OUTPUT_LIMIT:
            raise IsolationError("Protocol limits are fixed by the immutable helper")
        self.image = image
        self.directory = Path(directory).absolute()
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        if self.directory.is_symlink() or self.directory.stat().st_uid != os.getuid():
            raise IsolationError("Broker directory must be owned and not a symlink")
        self.directory.chmod(0o700)
        self.timeout_seconds = timeout_seconds
        self.journal = self.directory / "container.json"
        self.metadata = self.directory / "state.json"
        self.state_path = self.directory / "latest.state"
        owner_path = self.directory / "owner"
        if not owner_path.exists():
            atomic(owner_path, uuid.uuid4().hex.encode())
        self.owner = owner_path.read_text()
        self.recover()

    def _docker(self, args, *, check=True):
        result = subprocess.run(
            ["docker", *args], capture_output=True, timeout=30, check=False,
        )
        if check and result.returncode:
            raise IsolationError(result.stderr.decode("utf-8", "replace")[:8192])
        return result

    def _record(self, record):
        atomic(self.journal, canonical(record))

    def _inspect(self, target):
        result = self._docker(["inspect", "--type=container", target], check=False)
        if result.returncode:
            diagnostic = result.stderr.decode("utf-8", "replace")
            if "No such" in diagnostic:
                return None
            raise IsolationError("Container inspection unavailable: " + diagnostic[:1024])
        values = json.loads(result.stdout)
        if len(values) != 1:
            raise IsolationError("Ambiguous container inspection")
        return values[0]

    def _verify(self, record, target):
        info = self._inspect(target)
        if info is None:
            return None
        if (info["Name"] != "/" + record["name"] or info["Image"] != record["image"]
                or any(info["Config"].get("Labels", {}).get(k) != v
                       for k, v in record["labels"].items())
                or not re.fullmatch(r"[0-9a-f]{64}", info["Id"])
                or (record.get("id") and record["id"] != info["Id"])):
            raise IsolationError("Ambiguous container ownership; replacement blocked")
        return info

    @fail_closed
    def recover(self):
        if not self.journal.exists():
            return
        record = json.loads(self.journal.read_bytes())
        if record.get("status") == "ambiguous":
            raise IsolationError("Ambiguous previous launch blocks replacement")
        try:
            if record["image"] != self.image or record["labels"]["mve.owner"] != self.owner:
                raise IsolationError("Previous launch owner/image differs")
            target = record.get("id")
            if not target:
                cidfile = Path(record["cidfile"])
                if cidfile != self.directory / "container.cid":
                    raise IsolationError("Unexpected recorded cidfile")
                target = cidfile.read_text().strip() if cidfile.exists() else record["name"]
            info = self._verify(record, target)
            if info is None:
                if not record.get("id"):
                    raise IsolationError("Pending create has no provable container identity")
            else:
                record["id"] = info["Id"]
                self._record(record)
                self._docker(["rm", "--force", info["Id"]])
                if self._inspect(info["Id"]) is not None:
                    raise IsolationError("Owned container removal not confirmed")
            (self.directory / "container.cid").unlink(missing_ok=True)
            self.journal.unlink()
        except Exception:
            record["status"] = "ambiguous"
            self._record(record)
            raise

    def _launch(self, request, blob=b"", mounts=None):
        self.recover()
        request_bytes = frame(request, blob)
        trusted_mounts = {}
        if mounts:
            if request["op"] != "evaluate" or not set(mounts) <= {
                    "/work", "/runner", "/suite", "/kit", "/kit/harness", "/kit/skeleton/tools"}:
                raise IsolationError("Invalid evaluator mounts")
            for destination, source in mounts.items():
                path = Path(source).resolve(strict=True)
                if "," in str(path) or not path.is_dir():
                    raise IsolationError("Invalid trusted evaluator directory")
                trusted_mounts[destination] = path
        operation = uuid.uuid4().hex
        labels = {"mve.owner": self.owner, "mve.operation": operation,
                  "mve.image": self.image, "mve.profile": request["op"]}
        cidfile = self.directory / "container.cid"
        record = {
            "status": "intent", "name": f"mve-isolated-{operation}",
            "labels": labels, "image": self.image, "cidfile": str(cidfile),
            "deadline_unix": time.time() + request["timeout"] + 15,
        }
        self._record(record)
        args = [
            "create", "--name", record["name"], "--cidfile", str(cidfile), "--interactive",
            "--network=none", "--read-only", "--cap-drop=ALL",
            "--cap-add=SETUID", "--cap-add=SETGID", "--cap-add=KILL", "--cap-add=DAC_OVERRIDE",
            "--security-opt=no-new-privileges", "--init", "--user=0:0",
            "--pids-limit=64", "--cpus=1", "--memory=512m", "--memory-swap=512m",
            "--ulimit=nofile=256:256", "--ulimit=core=0:0", "--log-driver=none",
            "--ipc=private", "--stop-timeout=1",
            "--tmpfs=/tmp:rw,nosuid,nodev,noexec,size=16m,mode=1777",
        ]
        if not mounts or "/work" not in mounts:
            args.append("--tmpfs=/work:rw,nosuid,nodev,exec,size=64m,mode=0755,uid=1001,gid=1001")
        for key, value in labels.items():
            args.extend(["--label", f"{key}={value}"])
        if trusted_mounts:
            for destination, path in sorted(trusted_mounts.items()):
                args.extend(["--mount", f"type=bind,src={path},dst={destination},readonly,bind-recursive=disabled"])
        args.append(self.image)
        result = self._docker(args, check=False)
        if result.returncode:
            # A failed client/create can still have created a container.
            self.recover()
            raise IsolationError("Docker create failed: " + result.stderr.decode()[:1024])
        info = self._verify(record, record["name"])
        if info is None or cidfile.read_text().strip() != info["Id"]:
            record["status"] = "ambiguous"
            self._record(record)
            raise IsolationError("Created container identity not established")
        record.update(id=info["Id"], status="created")
        self._record(record)
        process = subprocess.Popen(
            ["docker", "start", "--attach", "--interactive", info["Id"]],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        selector = selectors.DefaultSelector()
        for stream, event in ((process.stdin, selectors.EVENT_WRITE),
                              (process.stdout, selectors.EVENT_READ),
                              (process.stderr, selectors.EVENT_READ)):
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, event)
        position, stdout, stderr = 0, bytearray(), bytearray()
        deadline = time.monotonic() + request["timeout"] + 10
        try:
            while selector.get_map() or process.poll() is None:
                if time.monotonic() >= deadline:
                    raise IsolationError("Container wall deadline exceeded")
                for key, _ in selector.select(0.05):
                    if key.fileobj is process.stdin:
                        try:
                            position += os.write(key.fd, request_bytes[position:position + 65536])
                        except BrokenPipeError:
                            selector.unregister(key.fileobj)
                            process.stdin.close()
                            continue
                        if position == len(request_bytes):
                            selector.unregister(key.fileobj)
                            process.stdin.close()
                    else:
                        part = os.read(key.fd, 65536)
                        if not part:
                            selector.unregister(key.fileobj)
                            continue
                        output = stdout if key.fileobj is process.stdout else stderr
                        output.extend(part)
                        cap = HEADER_LIMIT + STATE_LIMIT + 1024 if output is stdout else OUTPUT_LIMIT
                        if len(output) > cap:
                            raise IsolationError("Container output exceeded")
            process.wait()
            if process.returncode:
                raise IsolationError("Container helper failed: " + stderr.decode("utf-8", "replace")[:2048])
            header, next_state = unframe(io.BytesIO(stdout))
            if not header.get("ok"):
                raise IsolationError(header.get("error", "Helper rejected request"))
            verify_identity(header["supervisor"]["before"], supervisor=True)
            verify_identity(header["supervisor"]["after"], supervisor=True)
            verify_identity(header["child_setup"])
            self.last_supervisor = header["supervisor"]
            self.last_child_setup = header["child_setup"]
            return header, next_state
        finally:
            selector.close()
            if process.poll() is None:
                process.kill()
            process.wait()
            for stream in (process.stdin, process.stdout, process.stderr):
                if not stream.closed:
                    stream.close()
            self.recover()

    def _state(self, token):
        metadata = json.loads(self.metadata.read_bytes())
        if token != metadata["token"]:
            raise IsolationError("Stale/unknown opaque state token")
        slot = metadata.get("slot", "latest.state")
        if slot not in ("latest.state", "pending.state"):
            raise IsolationError("Invalid opaque state slot")
        state = (self.directory / slot).read_bytes()
        if len(state) > STATE_LIMIT or hashlib.sha256(state).hexdigest() != metadata["sha256"]:
            raise IsolationError("Opaque state integrity failed")
        return metadata, state

    def _publish(self, state, metadata):
        if not state or len(state) > STATE_LIMIT:
            raise IsolationError("Invalid next state")
        previous = json.loads(self.metadata.read_bytes()) if self.metadata.exists() else {}
        old_slot = previous.get("slot", "latest.state")
        slot = "pending.state" if old_slot == "latest.state" else "latest.state"
        metadata = dict(metadata, token=uuid.uuid4().hex, slot=slot,
                        sha256=hashlib.sha256(state).hexdigest())
        # Publish one metadata pointer only after the new opaque slot is durable.
        # Until that atomic switch, any interruption leaves the old slot intact.
        fd = os.open(self.directory / slot, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(state)
            stream.flush()
            os.fsync(stream.fileno())
        atomic(self.metadata, canonical(metadata))
        (self.directory / old_slot).unlink(missing_ok=True)
        return metadata["token"]

    @fail_closed
    def seed(self, files, *, git_bundle=None):
        validated = regular_files(files)
        if git_bundle is not None and (
                not isinstance(git_bundle, bytes) or not 0 < len(git_bundle) <= STATE_LIMIT):
            raise IsolationError("Trusted seed bundle must be nonempty bounded bytes")
        result, state = self._launch(
            {"op": "seed", "files": files, "timeout": self.timeout_seconds},
            git_bundle or b"",
        )
        return self._publish(state, {
            "seed_head": result["seed_head"], "seed_manifest": manifest(validated),
        })

    @fail_closed
    def execute(self, state, command, timeoutSeconds=120, *, timeout=None):
        if timeout is not None:
            timeoutSeconds = timeout
        if (not isinstance(command, str) or not command or len(command.encode()) > 65536
                or type(timeoutSeconds) not in (int, float) or not 0 < timeoutSeconds <= 300):
            raise IsolationError("Invalid isolated command or timeout")
        metadata, blob = self._state(state)
        result, next_state = self._launch(
            {"op": "execute", "command": command, "timeout": timeoutSeconds}, blob,
        )
        token = self._publish(next_state, metadata)
        return {"state": token, "stdout": result["stdout"], "stderr": result["stderr"],
                "exit_code": result["exit_code"], "timed_out": False}

    @fail_closed
    def export(self, state, review=False):
        metadata, blob = self._state(state)
        result, _ = self._launch(
            {"op": "export", "review": bool(review), "timeout": self.timeout_seconds}, blob,
        )
        files = regular_files(result["files"])
        final = manifest(files)
        changed = set()
        if review:
            baseline = metadata["seed_manifest"]
            for path in set(baseline) | set(final):
                if final.get(path) != baseline.get(path):
                    changed.add(path)
            for path in result["work_changed_paths"]:
                changed.add(path_ok(path, git=False))
        if type(result["commit_count"]) is not int or result["commit_count"] < 1:
            raise IsolationError("Invalid isolated commit count")
        return {
            "files": result["files"], "head_changed": result["head"] != metadata["seed_head"],
            "commit_count": result["commit_count"], "review": result["review"] if review else None,
            "changed_paths": sorted(changed),
        }

    @fail_closed
    def evaluate(self, argv, *, mounts, timeoutSeconds=120, result_path=None,
                 timeout=None, env=None, output_file=None):
        allowed = {"/work", "/runner", "/suite", "/kit", "/kit/harness", "/kit/skeleton/tools"}
        if not isinstance(mounts, dict):
            raise IsolationError("Trusted evaluator mounts must be a mapping")
        if not set(mounts) <= allowed and set(mounts.values()) <= allowed:
            mounts = {destination: source for source, destination in mounts.items()}
        if "/work" not in mounts or not set(mounts) <= allowed:
            raise IsolationError("Trusted evaluation requires a readonly /work directory")
        if timeout is not None:
            timeoutSeconds = timeout
        if output_file is not None:
            if result_path is not None:
                raise IsolationError("Specify only one evaluator output file")
            result_path = output_file
        if (not isinstance(env or {}, dict) or not set(env or {}) <= EVALUATION_ENV_KEYS
                or any(not isinstance(value, str) or "\0" in value or len(value) > 65536
                       for value in (env or {}).values())):
            raise IsolationError("Invalid trusted evaluator environment")
        if type(timeoutSeconds) not in (int, float) or not 0 < timeoutSeconds <= 600:
            raise IsolationError("Invalid evaluator deadline")
        result, _ = self._launch(
            {"op": "evaluate", "argv": argv, "timeout": timeoutSeconds,
             "result_path": result_path, "env": env or {}}, mounts=mounts,
        )
        value = {key: result[key] for key in ("stdout", "stderr", "exit_code", "result")}
        value["output"] = (base64.b64decode(result["result"], validate=True).decode("utf-8")
                           if result["result"] is not None else None)
        return value

    def close(self):
        self.recover()
