"""Actual offline Docker canaries; receipt is evidence, never owner approval."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

try:
    from .isolation import IsolationError, SandboxBroker, atomic
except ImportError:
    from isolation import IsolationError, SandboxBroker, atomic


def file(path, data, mode=0o644):
    return {"path": path, "mode": mode, "content": base64.b64encode(data).decode()}


def python(code):
    return "exec /usr/local/bin/python3 -I -c " + shlex.quote(code)


def canaries(image, directory, receipt):
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    broker = SandboxBroker(image, directory / "broker")
    checks = receipt["checks"]
    state = broker.seed([
        file("source.py", b"seed\n"), file("tcr", b"#!/bin/sh\nprintf executable\n", 0o755),
        file(".gitignore", b"reports/\n__pycache__/\n*.pyc\n.pytest_cache/\n.venv/\n"),
    ])
    original = state
    host_marker = directory / "host-only-marker"
    host_marker.write_text(uuid.uuid4().hex)
    old_env = os.environ.get("ISOLATION_HOST_SENTINEL")
    os.environ["ISOLATION_HOST_SENTINEL"] = host_marker.read_text()
    try:
        command = python(f"""
import os, socket, pathlib, json, ctypes, resource
assert os.getuid() == os.getgid() == 1001
assert "ISOLATION_HOST_SENTINEL" not in os.environ
assert not pathlib.Path({str(host_marker.absolute())!r}).exists()
assert not pathlib.Path("/var/run/docker.sock").exists()
assert not any("TOKEN" in k or "SECRET" in k or "KEY" in k for k in os.environ)
try:
    pathlib.Path("/host-write").write_text("no")
    raise AssertionError("root filesystem writable")
except OSError: pass
s = socket.socket(); s.settimeout(1)
assert s.connect_ex(("1.1.1.1", 53)) != 0
s.close()
status = pathlib.Path("/proc/self/status").read_text()
caps = {{}}
for key in ("CapEff", "CapPrm", "CapInh", "CapAmb"):
    caps[key] = int(next(x for x in status.splitlines() if x.startswith(key + ":")).split()[1], 16)
    assert caps[key] == 0
caps["CapBnd"] = int(next(x for x in status.splitlines() if x.startswith("CapBnd:")).split()[1], 16)
assert "NoNewPrivs:\\t1" in status
extra_fds = []
for fd in range(3, 256):
    try:
        os.fstat(fd)
        extra_fds.append(fd)
    except OSError: pass
assert not extra_fds, extra_fds
print(json.dumps({{
    "boundary": "ok", "uid": list(os.getresuid()), "gid": list(os.getresgid()),
    "dumpability_after_exec": ctypes.CDLL(None).prctl(3, 0, 0, 0, 0),
    "no_new_privileges": ctypes.CDLL(None).prctl(39, 0, 0, 0, 0), "capabilities": caps,
    "extra_inherited_fds": extra_fds, "core_limit": list(resource.getrlimit(resource.RLIMIT_CORE)),
}}))
""")
        result = broker.execute(state, command, 10)
        assert result["exit_code"] == 0, result
        observed = json.loads(result["stdout"])
        assert observed["boundary"] == "ok", observed
        assert observed["no_new_privileges"] == 1 and observed["core_limit"] == [0, 0]
        receipt["child_dumpability_after_exec"] = observed["dumpability_after_exec"]
        receipt["child_after_exec"] = observed
        receipt["child_preexec"] = broker.last_child_setup
        receipt["protected_supervisor"] = broker.last_supervisor
        state = result["state"]
        checks["no_network_host_write_credentials_or_child_capabilities"] = True
        checks["supervisor_identity_caps_nnp_and_dumpability_verified"] = True
        checks["child_preexec_uid_caps_nnp_dumpability_verified"] = True
        checks["child_control_descriptors_closed_before_exec"] = True
        result = broker.execute(state, "./tcr", 10)
        assert result["stdout"] == "executable" and result["exit_code"] == 0, result
        state = result["state"]
        checks["work_executable_tcr"] = True
        result = broker.execute(state, python("""
import os, pathlib, signal, ctypes, errno, json
parent = os.getppid()
observations = {"proc": {}, "signals": {}, "memory_calls": {}}
target_status = pathlib.Path(f"/proc/{parent}/status").read_text().splitlines()
observations["target_uid"] = [int(x) for x in next(x for x in target_status if x.startswith("Uid:")).split()[1:]]
assert observations["target_uid"] == [0, 0, 0, 0]
for relative in ("fd/0", "fd/1", "mem", "environ"):
    name = f"/proc/{parent}/{relative}"
    for mode in (os.O_RDONLY, os.O_WRONLY):
        try:
            fd = os.open(name, mode)
            os.close(fd)
            raise AssertionError("supervisor access: " + name)
        except OSError as exc:
            assert exc.errno in (errno.EACCES, errno.EPERM), exc
            observations["proc"][relative + (".read" if mode == os.O_RDONLY else ".write")] = exc.errno
for relative in ("root", "cwd"):
    try:
        os.readlink(f"/proc/{parent}/{relative}")
        raise AssertionError("supervisor link access")
    except OSError as exc:
        assert exc.errno in (errno.EACCES, errno.EPERM), exc
        observations["proc"][relative + ".readlink"] = exc.errno
try:
    fd = os.open("/opt/isolation_helper.py", os.O_WRONLY)
    os.close(fd)
    raise AssertionError("helper writable")
except OSError as exc:
    assert exc.errno in (errno.EACCES, errno.EROFS), exc
    observations["fixed_helper_write"] = exc.errno
for sig in (signal.SIGKILL, signal.SIGSTOP, signal.SIGTERM):
    try:
        os.kill(parent, sig)
        raise AssertionError("supervisor signal succeeded")
    except PermissionError as exc:
        observations["signals"][sig.name] = exc.errno
libc = ctypes.CDLL(None, use_errno=True)
ctypes.set_errno(0)
assert libc.ptrace(16, parent, None, None) == -1
observations["memory_calls"]["ptrace_attach"] = ctypes.get_errno()
assert observations["memory_calls"]["ptrace_attach"] == errno.EPERM
class Iovec(ctypes.Structure):
    _fields_ = [("base", ctypes.c_void_p), ("length", ctypes.c_size_t)]
buffer = ctypes.create_string_buffer(8)
local = Iovec(ctypes.cast(buffer, ctypes.c_void_p), 8)
remote = Iovec(1, 8)
for call in ("process_vm_readv", "process_vm_writev"):
    ctypes.set_errno(0)
    assert getattr(libc, call)(parent, ctypes.byref(local), 1, ctypes.byref(remote), 1, 0) == -1
    observations["memory_calls"][call] = ctypes.get_errno()
    assert observations["memory_calls"][call] == errno.EPERM
print("ISOLATED1\\n forged child framing")
pathlib.Path("after-interference").write_text("normal state survived")
print(json.dumps(observations, sort_keys=True))
"""), 10)
        assert result["exit_code"] == 0 and result["stdout"].startswith("ISOLATED1"), result
        receipt["supervisor_interference"] = json.loads(result["stdout"].splitlines()[-1])
        state = result["state"]
        assert not broker.export(state)["head_changed"]
        checks["protected_supervisor_interference_and_framing"] = True
        checks["supervisor_proc_control_memory_and_signals_denied"] = True
        result = broker.execute(state, (
            "mkdir -p reports; printf 'committed report\\n' > reports/committed.md; "
            "git add -f reports/committed.md; "
            "printf 'committed\\n' > source.py; git add source.py; "
            "git -c user.name=Canary -c user.email=canary@invalid commit -qm change; "
            "printf 'uncommitted\\n' > source.py; printf 'review\\n' > REVIEW.md; "
            "mkdir -p reports __pycache__ .pytest_cache .venv; "
            "printf 'quality\\n' > reports/quality.md; printf cache > __pycache__/x.pyc; "
            "printf cache > .pytest_cache/cache; printf cache > .venv/cache"
        ), 10)
        assert result["exit_code"] == 0, result
        state = result["state"]
        exported = broker.export(state, review=True)
        content = {entry["path"]: base64.b64decode(entry["content"]) for entry in exported["files"]}
        assert content["source.py"] == b"committed\n"
        assert "REVIEW.md" not in content and exported["head_changed"]
        assert base64.b64decode(exported["review"]) == b"review\n"
        assert {"source.py", "REVIEW.md"} <= set(exported["changed_paths"])
        assert "reports/committed.md" in exported["changed_paths"]
        assert not any(path != "reports/committed.md"
                       and path.startswith(("reports/", "__pycache__/", ".pytest_cache/", ".venv/"))
                       for path in exported["changed_paths"]), exported
        assert exported["commit_count"] == 2, exported
        result = broker.execute(state, "cat source.py; test -f after-interference", 10)
        assert result["stdout"] == "uncommitted\n" and result["exit_code"] == 0, result
        state = result["state"]
        checks["opaque_git_worktree_head_and_C_review_semantics"] = True
        checks["C_ignores_untracked_quality_and_cache_artifacts"] = True
        result = broker.execute(state, (
            "git config core.fsmonitor '/bin/sh -c \"touch /tmp/git-hook-fired\"'; "
            "git config core.hooksPath /tmp/hostile-hooks; "
            "mkdir -p /tmp/hostile-hooks; printf '#!/bin/sh\\ntouch /tmp/git-hook-fired\\n' "
            "> /tmp/hostile-hooks/post-checkout; chmod +x /tmp/hostile-hooks/post-checkout; "
            "printf '* export-ignore\\n' > .gitattributes"
        ), 10)
        assert result["exit_code"] == 0, result
        state = result["state"]
        assert broker.export(state)["head_changed"]
        checks["hostile_git_config_attributes_contained"] = True
        for attack in ("ln -s /etc/passwd bad-link", "ln source.py hard-link",
                       "mkfifo fifo", "dd if=/dev/zero of=too-large bs=1048576 count=3 2>/dev/null",
                       python("print('x' * 1100000)"),
                       python("import os; os.write(1, b'\\xff' * 400000)")):
            try:
                broker.execute(state, attack, 10)
            except IsolationError:
                pass
            else:
                raise AssertionError("Unsafe state/output accepted: " + attack)
            broker.export(state)
        checks["links_special_files_oversize_and_output_rejected_prior_state_preserved"] = True
        result = broker.execute(state, python("""
import errno, pathlib
p = pathlib.Path("/tmp/fill")
try:
    with p.open("wb") as stream:
        for _ in range(32): stream.write(b"x" * 1048576); stream.flush()
    raise AssertionError("tmpfs not bounded")
except OSError as exc:
    assert exc.errno == errno.ENOSPC, exc
finally:
    p.unlink(missing_ok=True)
print("bounded")
"""), 10)
        assert result["exit_code"] == 0 and result["stdout"].strip() == "bounded", result
        state = result["state"]
        checks["bounded_tmpfs"] = True
        unrelated_name = "mve-unrelated-canary-" + uuid.uuid4().hex
        unrelated = subprocess.run(
            ["docker", "create", "--name", unrelated_name, "--network=none",
             "--entrypoint=/bin/true", image], check=True, capture_output=True, text=True,
        ).stdout.strip()
        try:
            started = time.monotonic()
            try:
                broker.execute(state, python("""
import os, time
if os.fork() == 0:
    os.setsid()
    if os.fork() == 0:
        while True: time.sleep(1)
    os._exit(0)
while True: time.sleep(1)
"""), 1)
            except IsolationError as exc:
                assert "deadline" in str(exc).lower(), str(exc)
            else:
                raise AssertionError("Timeout accepted")
            assert time.monotonic() - started < 20
            assert not broker.journal.exists()
            assert broker._inspect(unrelated)["Id"] == unrelated
            broker.export(state)
            checks["deadline_doublefork_exact_cleanup_preserves_unrelated"] = True
            # Reconcile a controller interrupted after create but before ID publish.
            operation = uuid.uuid4().hex
            name = "mve-isolated-recovery-" + operation
            labels = {"mve.owner": broker.owner, "mve.operation": operation,
                      "mve.image": image, "mve.profile": "execute"}
            record = {"status": "intent", "name": name, "image": image, "labels": labels,
                      "cidfile": str(broker.directory / "container.cid"), "deadline_unix": time.time()}
            broker._record(record)
            args = ["docker", "create", "--name", name, "--cidfile", record["cidfile"]]
            for key, value in labels.items():
                args += ["--label", f"{key}={value}"]
            args += ["--network=none", "--entrypoint=/bin/true", image]
            owned = subprocess.run(args, check=True, capture_output=True, text=True).stdout.strip()
            broker.recover()
            assert broker._inspect(owned) is None and broker._inspect(unrelated) is not None
            checks["durable_create_recovery_exact_identity"] = True
            controller_script = (
                "import sys; from pathlib import Path; "
                f"sys.path.insert(0, {str(Path(__file__).parent.resolve())!r}); "
                "from isolation import SandboxBroker; "
                f"b=SandboxBroker({image!r}, Path({str(broker.directory.absolute())!r})); "
                f"b.execute({state!r}, 'sleep 120', 120)"
            )
            controller = subprocess.Popen([sys.executable, "-c", controller_script])
            controller_container = None
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    if broker.journal.exists():
                        pending = json.loads(broker.journal.read_bytes())
                        if pending.get("id"):
                            running = broker._inspect(pending["id"])
                            if running and running["State"]["Running"]:
                                config = running["HostConfig"]
                                assert config["ReadonlyRootfs"] and config["NetworkMode"] == "none"
                                assert config["Memory"] == config["MemorySwap"] == 512 * 1024 * 1024
                                assert config["PidsLimit"] == 64 and config["NanoCpus"] == 1_000_000_000
                                assert config["LogConfig"]["Type"] == "none" and not config["Binds"]
                                assert config["CapDrop"] == ["ALL"]
                                assert "no-new-privileges" in config["SecurityOpt"]
                                controller_container = running["Id"]
                                break
                    time.sleep(0.05)
                assert controller_container is not None, "Controller canary never reached running"
                controller.kill()
                controller.wait(timeout=5)
                broker.recover()
                assert broker._inspect(controller_container) is None
                assert broker._inspect(unrelated) is not None
                checks["controller_death_recovery_probed_no_owned_orphan"] = True
                checks["inspected_kernel_resource_and_container_profile"] = True
            finally:
                if controller.poll() is None:
                    controller.kill()
                    controller.wait()
                broker.recover()
        finally:
            subprocess.run(["docker", "rm", "--force", unrelated], check=True, capture_output=True)
        work, runner, suite, tools = (directory / name for name in ("work", "runner", "suite", "tools"))
        for path in (work, runner, suite, tools):
            path.mkdir(mode=0o755, exist_ok=True)
        sentinel = uuid.uuid4().hex
        (work / "candidate.py").write_text("pass\n")
        (suite / "hidden").write_text(sentinel)
        (tools / "fixed").write_text("trusted-kit\n")
        script = """
import pathlib, json, os
secret = pathlib.Path("/suite/hidden").read_text()
assert pathlib.Path("/work/candidate.py").read_text() == "pass\\n"
assert pathlib.Path("/kit/harness/evaluate.py").is_file()
assert pathlib.Path("/kit/skeleton/tools/fixed").read_text() == "trusted-kit\\n"
assert os.environ["MVE_COMPLEXITY"] == "lizard"
for path in ("/work/hidden-leak", "/runner/hidden-leak", "/suite/hidden-leak",
             "/kit/harness/hidden-leak", "/kit/skeleton/tools/hidden-leak"):
    try:
        pathlib.Path(path).write_text(secret)
        raise AssertionError("readonly evaluation input writable")
    except OSError: pass
pathlib.Path("/tmp/private-result.json").write_text(json.dumps({"secret": secret}))
print("evaluator-private")
"""
        (runner / "evaluate.py").write_text(script)
        evaluated = broker.evaluate(
            ["/usr/local/bin/python3", "-I", "/kit/harness/evaluate.py"],
            mounts={work: "/work", runner: "/kit/harness", suite: "/suite", tools: "/kit/skeleton/tools"},
            timeout=600, env={"MVE_COMPLEXITY": "lizard"}, output_file="/tmp/private-result.json",
        )
        assert evaluated["exit_code"] == 0, evaluated
        assert json.loads(base64.b64decode(evaluated["result"])) == {"secret": sentinel}
        assert json.loads(evaluated["output"]) == {"secret": sentinel}
        assert not any(path.name == "hidden-leak" for root in (work, runner, suite, tools) for path in root.iterdir())
        result = broker.execute(state, "test ! -e /tmp/private-result.json; test ! -e hidden-leak", 10)
        assert result["exit_code"] == 0 and sentinel not in result["stdout"], result
        state = result["state"]
        checks["readonly_evaluation_private_result_no_hidden_writeback"] = True
        checks["readonly_evaluation_trusted_kit_mounts"] = True
        checks["trusted_evaluation_600s_profile_accepted"] = True
        try:
            result = broker.execute(state, python("x = bytearray(700 * 1024 * 1024)"), 15)
            assert result["exit_code"] != 0, "Container memory limit not enforced"
            state = result["state"]
        except IsolationError:
            broker.export(state)
        assert not broker.journal.exists()
        checks["memory_bound_and_exact_cleanup"] = True
        result = broker.execute(state, (
            "python3 --version; git --version; ruff --version; "
            "python3 -c 'import importlib.metadata as m; print(m.version(\"lizard\")); "
            "print(m.version(\"pytest\"))'; jscpd --version; "
            "test -x /usr/local/bin/python3 && test -x /usr/bin/make || exit 99; "
            "/usr/bin/sha256sum /opt/isolation_helper.py"
        ), 10)
        assert result["exit_code"] == 0, result
        assert all(version in result["stdout"] for version in ("3.12.3", "0.17.3", "1.24.3", "5.4.1"))
        helper_digest = hashlib.sha256((Path(__file__).parent / "isolation_helper.py").read_bytes()).hexdigest()
        assert helper_digest + "  /opt/isolation_helper.py" in result["stdout"]
        receipt["image_helper_sha256"] = helper_digest
        receipt["executables"] = {"python3": "/usr/local/bin/python3", "make": "/usr/bin/make"}
        state = result["state"]
        receipt["tool_versions"] = result["stdout"]
        checks["installed_pinned_external_tools"] = True
        checks["image_fixed_helper_matches_source"] = True
        result = broker.execute(state, (
            "ln -s /etc/passwd committed-link; git add committed-link; "
            "git -c user.name=Canary -c user.email=c@invalid commit -qm bad-link; rm committed-link"
        ), 10)
        assert result["exit_code"] == 0, result
        try:
            broker.export(result["state"])
        except IsolationError as exc:
            assert "Nonregular committed tree" in str(exc)
        else:
            raise AssertionError("Committed symlink accepted")
        checks["committed_symlink_rejected_by_object_export"] = True
        # A fresh seed with an empty commit still changes HEAD with an equal tree.
        state = broker.seed([file("same", b"same\n")])
        result = broker.execute(
            state, "git -c user.name=Canary -c user.email=c@invalid commit --allow-empty -qm empty", 10,
        )
        exported = broker.export(result["state"])
        assert exported["head_changed"] and exported["commit_count"] == 2
        assert exported["files"] == [file("same", b"same\n")]
        checks["empty_commit_preserves_head_delivery_observation"] = True
        canonical_repo = directory / "canonical-repo"
        canonical_repo.mkdir()

        def trusted_git(*args):
            return subprocess.run(
                ["git", "-c", "user.name=Canary", "-c", "user.email=c@invalid", *args],
                cwd=canonical_repo, check=True, capture_output=True,
                env={"PATH": os.environ["PATH"], "HOME": str(canonical_repo),
                     "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null"},
            ).stdout

        trusted_git("init", "--initial-branch=main")
        (canonical_repo / "source.py").write_text("before\n")
        trusted_git("add", "source.py")
        trusted_git("commit", "-m", "start")
        trusted_git("branch", "feature-start")
        (canonical_repo / "source.py").write_text("after\n")
        trusted_git("commit", "-am", "feature")
        trusted_git("branch", "feature-end")
        bundle_path = directory / "trusted.bundle"
        trusted_git("bundle", "create", str(bundle_path.absolute()), "--all")
        state = broker.seed([file("source.py", b"after\n")], git_bundle=bundle_path.read_bytes())
        result = broker.execute(
            state, "git diff feature-start feature-end; git remote; git status --porcelain", 10,
        )
        assert result["exit_code"] == 0 and "-before" in result["stdout"] and "+after" in result["stdout"], result
        assert "??" not in result["stdout"] and "origin" not in result["stdout"]
        exported = broker.export(result["state"])
        assert not exported["head_changed"] and exported["commit_count"] == 2
        checks["trusted_seed_bundle_preserves_prompt_refs_and_history"] = True
        receipt["dumpability_disposition"] = {
            "status": "distinct_supervisor_authority_verified",
            "persistent_child_zero": False,
            "explanation": (
                "Ordinary Linux execve resets child dumpability to 1. The supervisor never execs "
                "candidate code and remains distinct UID0, dumpability0, no-new-privileges1. "
                "UID1001 with zero effective/permitted/inheritable/ambient capabilities cannot "
                "access its protected proc/control/memory or signal it. Persistent child zero "
                "is not claimed; requiring that separately needs an architecture decision."
            ),
            "sources": [
                "https://man7.org/linux/man-pages/man2/execve.2.html",
                "https://man7.org/linux/man-pages/man2/PR_SET_DUMPABLE.2const.html",
                "https://man7.org/linux/man-pages/man5/proc_pid_fd.5.html",
                "https://man7.org/linux/man-pages/man2/kill.2.html",
            ],
        }
        assert original != state and host_marker.read_text() == os.environ["ISOLATION_HOST_SENTINEL"]
    finally:
        broker.close()
        if old_env is None:
            os.environ.pop("ISOLATION_HOST_SENTINEL", None)
        else:
            os.environ["ISOLATION_HOST_SENTINEL"] = old_env


def main():
    try:
        from .study import ROOT, fingerprint
    except ImportError:
        from study import ROOT, fingerprint

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Inspected local sha256 image content ID")
    parser.add_argument("--out", type=Path, default=Path(".study/runtime-canary.json"))
    args = parser.parse_args()
    root = args.out.parent
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    directory = root / ("isolation-canary-" + uuid.uuid4().hex)
    source = Path(__file__).parent
    fingerprints = {
        name: hashlib.sha256((source / name).read_bytes()).hexdigest()
        for name in ("isolation.py", "isolation_helper.py", "Dockerfile.isolated",
                     "isolation_canary.py", "tests/test_isolation.py")
    }
    receipt = {"schema": "isolated-runtime-canary/v1", "image": args.image,
               "inputs_sha256": fingerprint(ROOT),
               "checks": {}, "source_inputs": fingerprints, "success": False,
               "started_unix": time.time(), "directory": str(directory),
               "limitations": [
                   "Evidence is offline containment evidence, not owner approval or live billing validation.",
                   "Child observations are adversarial input; this is not a tamper-proof Python test oracle.",
                   ("Child dumpability is disabled before exec; Linux can reset it on exec. "
                    "Supervisor dumpability and separate identity protect the control channel."),
                   "Fresh calls preserve bounded regular filesystem/Git state, not daemon/process memory.",
                   ("Base and primary tools are pinned; transitive registry/apt inputs are captured by "
                    "the built image content ID, not a fully locked reproducible build."),
               ]}
    try:
        canaries(args.image, directory, receipt)
        receipt["success"] = True
    except Exception as exc:
        receipt["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        receipt["finished_unix"] = time.time()
        if receipt["success"]:
            shutil.rmtree(directory)
            receipt["scratch_removed"] = True
        atomic(args.out, json.dumps(receipt, sort_keys=True, indent=2).encode() + b"\n")
        print(json.dumps({"image": args.image, "receipt": str(args.out), "success": receipt["success"]}))


if __name__ == "__main__":
    main()
