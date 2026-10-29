"""Trusted controller side of the isolated Copilot runtime."""
from __future__ import annotations

import base64
import hashlib
import json
import math
import os
import re
import selectors
import shutil
import signal
import subprocess
import time
from pathlib import Path, PurePosixPath

from runner import git, head
from study_io import ROOT, RetryableError, StudyError, atomic_json, read_json

NANO = 1_000_000_000
RECORD_LIMIT = 8 * 1024 * 1024
JOURNAL_LIMIT = 64 * 1024 * 1024
LOG_LIMIT = 1024 * 1024
FILE_LIMIT = 2 * 1024 * 1024
TREE_LIMIT = 16 * 1024 * 1024
BRIDGE = ROOT / "harness/copilot-sdk/transport.mjs"
CANARY = ROOT / ".study/runtime-canary.json"
CANARY_CHECKS = {
    "C_ignores_untracked_quality_and_cache_artifacts",
    "bounded_tmpfs",
    "child_control_descriptors_closed_before_exec",
    "child_preexec_uid_caps_nnp_dumpability_verified",
    "committed_symlink_rejected_by_object_export",
    "controller_death_recovery_probed_no_owned_orphan",
    "deadline_doublefork_exact_cleanup_preserves_unrelated",
    "durable_create_recovery_exact_identity",
    "empty_commit_preserves_head_delivery_observation",
    "hostile_git_config_attributes_contained",
    "image_fixed_helper_matches_source",
    "inspected_kernel_resource_and_container_profile",
    "installed_pinned_external_tools",
    "links_special_files_oversize_and_output_rejected_prior_state_preserved",
    "memory_bound_and_exact_cleanup",
    "no_network_host_write_credentials_or_child_capabilities",
    "opaque_git_worktree_head_and_C_review_semantics",
    "protected_supervisor_interference_and_framing",
    "readonly_evaluation_private_result_no_hidden_writeback",
    "readonly_evaluation_trusted_kit_mounts",
    "supervisor_identity_caps_nnp_and_dumpability_verified",
    "supervisor_proc_control_memory_and_signals_denied",
    "trusted_evaluation_600s_profile_accepted",
    "trusted_seed_bundle_preserves_prompt_refs_and_history",
    "work_executable_tcr",
}


def regular_files(directory: Path) -> list[dict]:
    """Serialize only controller-owned regular content, never Git metadata."""
    files = []
    for path in sorted(directory.rglob("*")):
        relative = path.relative_to(directory)
        if ".git" in relative.parts:
            continue
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise StudyError("Trusted checkpoint contains nonregular content")
        if path.is_file():
            files.append({"path": relative.as_posix(),
                          "mode": 0o755 if path.stat().st_mode & 0o111 else 0o644,
                          "content": base64.b64encode(path.read_bytes()).decode("ascii")})
    validate_files(files)
    return files


def validate_files(files: object) -> dict[str, tuple[int, bytes]]:
    """Validate an isolated export completely before changing trusted staging."""
    if not isinstance(files, list) or len(files) > 4096:
        raise StudyError("Invalid isolated regular-file export")
    result = {}
    total = 0
    for entry in files:
        if not isinstance(entry, dict) or set(entry) != {"path", "mode", "content"}:
            raise StudyError("Malformed isolated file record")
        name, mode, content = entry["path"], entry["mode"], entry["content"]
        if not isinstance(name, str) or not name:
            raise StudyError("Invalid isolated file path")
        try:
            encoded_name = name.encode("utf-8")
        except UnicodeError as error:
            raise StudyError("Isolated path is not valid UTF-8") from error
        if len(encoded_name) > 1024:
            raise StudyError("Invalid isolated file path")
        path = PurePosixPath(name)
        if (path.is_absolute() or path.as_posix() != name
                or any(part in (".", "..", ".git") for part in path.parts)
                or any(ord(char) < 32 or ord(char) == 127 for char in name)
                or name in result):
            raise StudyError("Unsafe or duplicate isolated file path")
        if type(mode) is not int or mode not in (0o644, 0o755):
            raise StudyError("Unsupported isolated file mode")
        if not isinstance(content, str) or len(content) > 4 * ((FILE_LIMIT + 2) // 3):
            raise StudyError("Isolated file exceeds limit")
        try:
            data = base64.b64decode(content, validate=True)
        except (ValueError, UnicodeError) as error:
            raise StudyError("Malformed isolated file content") from error
        total += len(data)
        if len(data) > FILE_LIMIT or total > TREE_LIMIT:
            raise StudyError("Isolated export exceeds resource limits")
        if any(parent.as_posix() in result for parent in path.parents if parent != PurePosixPath(".")):
            raise StudyError("Isolated file conflicts with a directory")
        result[name] = (mode, data)
    if any(parent.as_posix() in result for name in result
           for parent in PurePosixPath(name).parents if parent != PurePosixPath(".")):
        raise StudyError("Isolated file conflicts with a directory")
    return result


def replace_tree(directory: Path, files: object) -> None:
    """Publish validated regular content without accepting candidate metadata."""
    validated = validate_files(files)
    if not (directory / ".git").is_dir() or (directory / ".git").is_symlink():
        raise StudyError("Missing controller-owned trusted Git directory")
    for path in directory.iterdir():
        if path.name == ".git":
            continue
        if path.is_symlink():
            raise StudyError("Unexpected link in trusted staging")
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    for name, (mode, data) in validated.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(data)
        path.chmod(mode)


def check_host_auth(root: Path = ROOT) -> None:
    """Verify the signed-in host user before reserving credits."""
    cli = shutil.which("copilot")
    if not cli:
        raise StudyError("Copilot CLI is missing; install the pinned version and sign in on this host")
    base = root / ".study/host-auth-check"
    if base.is_symlink():
        raise StudyError("Host authentication scratch must not be symlinked")
    from study_io import command
    try:
        status = json.loads(command([
            "node", str(root / "harness/copilot-sdk/transport.mjs"), "--check-runtime",
            "--cli-path", str(Path(cli).resolve()), "--base-directory", str(base.resolve()),
        ], cwd=root, timeout=40))
    except (StudyError, ValueError) as error:
        raise StudyError("Cannot verify Copilot sign-in; check the pinned CLI/SDK and sign in on this host") from error
    if (not isinstance(status, dict) or status.get("isAuthenticated") is not True
            or status.get("userAuthentication") is not True):
        raise StudyError("Copilot user sign-in required on this host; never copy credentials into Docker")


def runtime_receipt(root: Path = ROOT) -> dict:
    """Require source-bound offline evidence, not an arbitrary image setting."""
    from study import fingerprint

    receipt_path = root / ".study/runtime-canary.json"
    try:
        receipt = read_json(receipt_path)
    except (OSError, ValueError, StudyError) as error:
        raise StudyError("The isolated live backend requires an exact-source offline runtime canary receipt") from error
    if (receipt.get("schema") != "isolated-runtime-canary/v1" or receipt.get("success") is not True
            or not re.fullmatch(r"sha256:[0-9a-f]{64}", str(receipt.get("image", "")))):
        raise StudyError("Invalid isolated live backend image receipt")
    checks = receipt.get("checks")
    if (not isinstance(checks, dict) or not CANARY_CHECKS.issubset(checks)
            or any(checks[name] is not True for name in CANARY_CHECKS)):
        raise StudyError("The isolated live backend has incomplete containment canaries")
    sources = {
        name: hashlib.sha256((root / "harness" / name).read_bytes()).hexdigest()
        for name in ("Dockerfile.isolated", "isolation.py", "isolation_helper.py",
                     "isolation_canary.py", "tests/test_isolation.py")
    }
    if (receipt.get("source_inputs") != sources
            or receipt.get("image_helper_sha256") != sources["isolation_helper.py"]):
        raise StudyError("Isolated canary/helper image inputs differ from the execution source")
    if receipt.get("inputs_sha256") != fingerprint(root):
        raise StudyError("Isolated runtime canary evidence does not match the execution source")
    return receipt


def runtime_errors(cfg: dict, root: Path = ROOT) -> list[str]:
    """Validate runtime setup without creating a session or running a model."""
    try:
        receipt = runtime_receipt(root)
        package = read_json(root / "harness/copilot-sdk/node_modules/@github/copilot-sdk/package.json")
        if package.get("version") != "1.0.28":
            raise StudyError("Repository-local Copilot SDK must be pinned to 1.0.28; run npm ci")
        freeze = read_json(root / cfg["freeze_manifest"])
        receipt_digest = hashlib.sha256((root / ".study/runtime-canary.json").read_bytes()).hexdigest()
        if (freeze.get("runtime_image") != receipt["image"]
                or freeze.get("runtime_canary_sha256") != receipt_digest):
            raise StudyError("Owner freeze must bind the exact runtime image and canary receipt")
    except (OSError, ValueError, StudyError) as error:
        return [str(error) if isinstance(error, StudyError) else "Isolated live backend setup evidence unreadable"]
    return []


def live_runtime(run):
    if not hasattr(run, "_isolated_runtime"):
        run._isolated_runtime = LiveRuntime(run)
    return run._isolated_runtime


class LiveRuntime:
    """Keep candidate execution separate from the controller-owned repository."""

    def __init__(self, run):
        self.run = run
        self.receipt = runtime_receipt()
        from isolation import SandboxBroker

        self.directory = Path(run.dir) / "isolation"
        self.broker = SandboxBroker(self.receipt["image"], self.directory)
        self.state = None
        self.last_export = None
        self.last_checkpoint = None

    def broker_call(self, operation: str, *args, **kwargs):
        from isolation import IsolationError

        try:
            return getattr(self.broker, operation)(*args, **kwargs)
        except IsolationError as error:
            self.run.controller.state["oracle_halt"] = True
            self.run.controller.save()
            raise StudyError("Isolated runtime failed; reconcile exact owned resources before resuming") from error

    def run_agent(self, prompt: str, step_dir: str, budget: int) -> dict:
        run = self.run
        controller = run.controller
        errors = runtime_errors(controller.cfg)
        if errors:
            raise StudyError("; ".join(errors))
        seconds_limit, credit_limit = run.remaining_allowance(budget)
        buffer = (controller.cfg["session_reserve_credits"]
                  - controller.cfg["session_soft_limit_credits"]) * NANO
        attempt = controller.new_attempt(run.cell, run.current_step, credit_limit + buffer)
        attempt.update(seconds_limit=seconds_limit, credit_limit_nano=credit_limit)
        directory = Path(run.dir) / "attempts" / attempt["id"]
        directory.mkdir(parents=True, mode=0o700)
        attempt["directory"] = str(directory.relative_to(controller.directory))
        controller.save()
        started = time.monotonic()
        usage = None
        result = None

        def writer_started(pid):
            controller.state.update(writer_pid=pid, writer_pending=False)
            controller.save()

        def writer_stopped():
            controller.state.update(writer_pid=None, writer_pending=False)
            controller.save()

        def tool(arguments, remaining):
            outcome = self.broker_call(
                "execute", self.state, arguments["command"], min(arguments["timeoutSeconds"], remaining, 300))
            self.state = outcome["state"]
            return {key: outcome[key] for key in ("stdout", "stderr", "exit_code") if key in outcome}

        try:
            seed = directory / "seed.bundle"
            git(run.repo, "bundle", "create", str(seed), "--all")
            if seed.stat().st_size > TREE_LIMIT:
                raise StudyError("Trusted seed history exceeds runtime limit")
            self.state = self.broker_call("seed", regular_files(Path(run.repo)), git_bundle=seed.read_bytes())
            request = {
                "model": run.assigned_model, "reasoningEffort": "medium", "prompt": prompt,
                "remainingSeconds": min(seconds_limit - (time.monotonic() - started),
                                        controller.state["deadline"] - time.time()),
                "maxAiCredits": credit_limit / NANO, "cliPath": shutil.which("copilot"),
                "baseDirectory": str(directory / "sdk"),
            }
            if request["remainingSeconds"] <= 0:
                raise StudyError("Original step allowance exhausted before SDK startup")
            atomic_json(directory / "request.json", request)
            attempt["request_sha256"] = hashlib.sha256((directory / "request.json").read_bytes()).hexdigest()
            controller.state["writer_pending"] = True
            controller.save()
            result = run_bridge(request, directory / "transport", tool,
                                on_start=writer_started, on_stop=writer_stopped)
            receipt = result.get("receipt")
            if not isinstance(receipt, dict):
                raise StudyError("SDK did not produce a usage receipt")
            usage = receipt.get("usage")
            if (not isinstance(usage, dict) or usage.get("credits_complete") is not True
                    or type(usage.get("totalNanoAiu")) is not int or usage["totalNanoAiu"] < 0):
                raise StudyError("SDK usage is incomplete; reservation retained")
            if (receipt.get("sdk_version") != "1.0.28" or receipt.get("cli_version") != "1.0.105"
                    or receipt.get("protocol_version") != 3 or receipt.get("protocol_error") is not None
                    or result.get("exit_code") != 0
                    or receipt.get("actual_models") != [run.assigned_model]
                    or receipt.get("actual_reasoning_efforts") != ["medium"]):
                controller.state["oracle_halt"] = True
                controller.save()
                raise StudyError("SDK actual model/effort evidence differs from the assigned treatment")
            self.last_export = self.broker_call("export", self.state, review=run.current_step.endswith("-review"))
            if not run.current_step.endswith("-review"):
                self.publish_committed(self.last_export)
            return {"exit_code": result.get("exit_code", 0), "timed_out": False,
                    "seconds": time.monotonic() - started, "usage": usage,
                    "possible_leak": False, "diagnostic_stub": False,
                    "runtime": {"sdk": "1.0.28", "cli": "1.0.105",
                                "image": self.receipt["image"], "isolated_tools": True},
                    "actual_models": receipt["actual_models"],
                    "actual_reasoning_efforts": receipt["actual_reasoning_efforts"]}
        except (RuntimeError, OSError):
            controller.state["oracle_halt"] = True
            controller.save()
            raise
        finally:
            attempt.update(seconds=round(time.monotonic() - started, 4), usage=usage,
                           status="agent_returned" if result is not None else "interrupted")
            controller.settle_attempt(attempt["id"], usage)

    def publish_committed(self, exported: dict) -> None:
        if not isinstance(exported, dict) or type(exported.get("head_changed")) is not bool:
            raise StudyError("Invalid isolated committed-HEAD evidence")
        files = exported.get("files")
        validated = validate_files(files)
        if not exported["head_changed"]:
            if validate_files(regular_files(Path(self.run.repo))) != validated:
                raise StudyError("Unchanged candidate HEAD has inconsistent committed content")
            return
        replace_tree(Path(self.run.repo), files)
        info = Path(self.run.repo) / ".git/info"
        info.mkdir(exist_ok=True)
        (info / "attributes").write_text("* -text -ident -filter -working-tree-encoding\n", encoding="ascii")
        git(self.run.repo, "add", "-f", "-A")
        git(self.run.repo, "commit", "-q", "--allow-empty", "-m", "broker: retained candidate HEAD")
        self.last_checkpoint = head(self.run.repo)

    def review_step(self, k: int) -> None:
        from runner import fmt_minutes, load_prompt, render

        run = self.run
        before = head(run.repo)
        step = f"f{k:02d}-review"
        step_dir = str(Path(run.dir) / "steps" / step)
        prompt = render(load_prompt("review-only-step.prompt.md"),
                        {"consolidation_budget": fmt_minutes(run.budgets["post"])})
        result = self.run_agent(prompt, step_dir, run.budgets["post"])
        exported = self.last_export
        if not isinstance(exported, dict) or not isinstance(exported.get("changed_paths"), list):
            raise StudyError("Missing isolated review scope evidence")
        changes = exported["changed_paths"]
        if any(not isinstance(path, str) or not path for path in changes):
            raise StudyError("Malformed isolated review scope evidence")
        changes = set(changes) - {"REVIEW.md"}
        violations = ([f"review step changed other files: {', '.join(sorted(changes))[:300]}"]
                      if changes else [])
        review = exported.get("review")
        if review is not None:
            parsed = validate_files([{"path": "REVIEW.md", "mode": 0o644, "content": review}])
            try:
                content = parsed["REVIEW.md"][1].decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
            except UnicodeError as error:
                raise StudyError("Isolated review is not UTF-8 text") from error
            (Path(run.repo) / "REVIEW.md").write_text(content, encoding="utf-8")
            git(run.repo, "add", "REVIEW.md")
            git(run.repo, "commit", "-q", "-m", "runner: review notes", check=False)
        measurement = run.measure(k, step_dir, before)
        count = int(git(run.repo, "rev-list", "--count", f"{before}..HEAD").stdout.strip())
        run.record({"step": step, "k": k, "kind": "review", "agent": result,
                    "violations": violations, "measure": measurement, "commits": count})

    def evaluator_inputs(self, k: int | None = None, cr: bool = False) -> dict:
        """Mount only frozen trusted harness and a private read-only snapshot."""
        run = self.run
        attempt = run.cell["attempts"][-1]
        root = Path(run.dir) / "attempts" / attempt["id"] / "evaluation-inputs"
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        snapshot = root / ("snapshot-" + head(run.repo))
        if not snapshot.exists():
            shutil.copytree(run.repo, snapshot)
        kit = root / "kit"
        harness = kit / "harness"
        tools = kit / "skeleton/tools"
        harness.mkdir(parents=True, exist_ok=True)
        tools.mkdir(parents=True, exist_ok=True)
        for name in ("measure.py", "stdlib_tests.py", "failure_attribution.py", "evaluation_env.py"):
            shutil.copyfile(ROOT / "harness" / name, harness / name)
        shutil.copyfile(ROOT / "skeleton/tools/metrics_core.py", tools / "metrics_core.py")
        mounts = {snapshot: "/work", kit: "/kit"}
        if k is not None:
            suite_root = root / f"suite-{k}-{'cr' if cr else 'features'}"
            suite_root.mkdir(parents=True, exist_ok=True)
            suite = dict(run.suite)
            suite["features"] = run.suite["features"][:k]
            if not cr:
                suite.pop("change_request", None)
            atomic_json(suite_root / "suite.json", suite)
            (suite_root / "suite.json").chmod(0o644)
            items = [(feature, "features") for feature in suite["features"]]
            if cr:
                items.append((suite["change_request"], ""))
            for item, prefix in items:
                for kind in ("examples", "hidden"):
                    destination = suite_root / prefix / item["id"] / kind
                    destination.mkdir(parents=True, exist_ok=True)
                    for source in (Path(run.suite_dir) / prefix / item["id"] / kind).glob("*.py"):
                        shutil.copyfile(source, destination / source.name)
            mounts[suite_root] = "/suite"
        return mounts

    def visible(self) -> bool:
        outcome = self.broker_call(
            "evaluate", ["/usr/bin/make", "-s", "test"], mounts=self.evaluator_inputs(),
            timeout=min(600, self.run.controller.state["deadline"] - time.time()),
            env={"PYTHONDONTWRITEBYTECODE": "1"}, output_file=None)
        return outcome["exit_code"] == 0

    def measure(self, k: int, step_dir: str, prev_ref: str, cr: bool = False) -> dict:
        from measure import diff_stats, expected_tests

        run = self.run
        mounts = self.evaluator_inputs(k, cr)
        bootstrap = ("import runpy,sys; sys.path.insert(0,'/kit/harness'); "
                     "runpy.run_path('/kit/harness/measure.py',run_name='__main__')")
        args = ["/usr/local/bin/python3", "-I", "-B", "-c", bootstrap, "--repo", "/work",
                "--suite", "/suite", "--k", str(k), "--out", "/tmp/measurement.json",
                "--scratch-dir", "/tmp", "--runner", run.cfg["measure"]["test_runner"],
                "--complexity", "lizard", "--duplication", "jscpd", "--lint", "ruff"]
        if prev_ref:
            args += ["--prev-ref", prev_ref]
        if cr:
            args.append("--cr")
        outcome = self.broker_call(
            "evaluate", args, mounts=mounts, timeout=min(600, run.controller.state["deadline"] - time.time()),
            env={"PYTHONDONTWRITEBYTECODE": "1"}, output_file="/tmp/measurement.json")
        if outcome["exit_code"]:
            raise RetryableError("Isolated evaluator failed; retained snapshot requires recovery")
        data = outcome.get("output")
        if not isinstance(data, str) or len(data.encode()) > RECORD_LIMIT:
            raise StudyError("Isolated evaluator returned invalid or excessive output")
        try:
            result = json.loads(data)
        except ValueError as error:
            raise StudyError("Isolated evaluator returned malformed JSON") from error
        suite = next(source for source, target in mounts.items() if target == "/suite")
        hidden_files = sorted(suite.glob("features/*/hidden/*.py"))
        if cr:
            hidden_files += sorted(suite.glob("cr*/hidden/*.py"))
        expected = set(expected_tests([str(path) for path in hidden_files]))
        hidden = result.get("hidden") if isinstance(result, dict) else None
        if (not isinstance(hidden, dict) or set(hidden) != expected or not expected
                or any(status not in ("passed", "failed", "error", "skipped", "timeout")
                       for status in hidden.values())
                or result.get("hidden_total") != len(expected)
                or result.get("hidden_passed") != sum(status == "passed" for status in hidden.values())
                or result.get("head") != head(run.repo) or result.get("k") != k or result.get("cr") is not cr
                or result.get("diff") != diff_stats(run.repo, prev_ref)
                or not isinstance(result.get("metrics"), dict)
                or result["metrics"].get("backends") != {
                    "complexity": "lizard", "duplication": "jscpd", "lint": "ruff"}):
            raise StudyError("Isolated evaluator result identity, denominator or metrics do not match")
        result["evaluation"] = {"execution": "isolated_container", "environment": "credential_minimal",
                                "os_isolated": True, "network_isolated": True,
                                "image": self.receipt["image"], "candidate_snapshot": head(run.repo)}
        directory = Path(step_dir)
        directory.mkdir(parents=True, exist_ok=True)
        atomic_json(directory / "measure.json", result)
        return result


def run_bridge(request: dict, directory: Path, tool, *, on_start=None, on_stop=None) -> dict:
    """Drive the trusted bridge with bounded durable events and owned cleanup."""
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    deadline = time.monotonic() + request["remainingSeconds"]
    process = subprocess.Popen(
        ["node", str(BRIDGE)], cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, start_new_session=True,
    )
    selector = selectors.DefaultSelector()
    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    total = 0
    receipt = None
    seen_session = None
    seen_tools = set()
    try:
        if on_start:
            on_start(process.pid)
        for name in buffers:
            stream = getattr(process, name)
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        initial = (json.dumps(request) + "\n").encode()
        if len(initial) > RECORD_LIMIT:
            raise StudyError("SDK request exceeds control limit")
        process.stdin.write(initial)
        process.stdin.flush()
        with (directory / "events.jsonl").open("xb") as events:
            while selector.get_map():
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise StudyError("Original SDK session deadline reached")
                for key, _ in selector.select(min(remaining, 0.2)):
                    name = key.data
                    chunk = os.read(key.fileobj.fileno(), 65536)
                    if not chunk:
                        selector.unregister(key.fileobj)
                        continue
                    buffers[name].extend(chunk)
                    if name == "stderr":
                        if len(buffers[name]) > LOG_LIMIT:
                            raise StudyError("SDK diagnostic limit reached")
                        continue
                    if len(buffers[name]) > RECORD_LIMIT and b"\n" not in buffers[name]:
                        raise StudyError("SDK control record limit reached")
                    while b"\n" in buffers[name]:
                        raw, _, tail = buffers[name].partition(b"\n")
                        buffers[name] = bytearray(tail)
                        total += len(raw) + 1
                        if len(raw) > RECORD_LIMIT or total > JOURNAL_LIMIT:
                            raise StudyError("SDK receipt evidence limit reached")
                        events.write(raw + b"\n")
                        events.flush()
                        os.fsync(events.fileno())
                        try:
                            record = json.loads(raw)
                        except (ValueError, UnicodeError) as error:
                            raise StudyError("Malformed SDK control record") from error
                        if not isinstance(record, dict):
                            raise StudyError("Malformed SDK control record")
                        kind = record.get("type")
                        if receipt is not None:
                            raise StudyError("Unexpected SDK record after completion")
                        if kind == "event":
                            session = record.get("sessionId")
                            if not isinstance(session, str) or not session:
                                raise StudyError("Missing SDK event session identity")
                            if seen_session is not None and session != seen_session:
                                raise StudyError("SDK event session identity changed")
                            seen_session = session
                        elif kind == "tool":
                            identity, arguments = record.get("id"), record.get("arguments")
                            if (not isinstance(identity, str) or not identity or identity in seen_tools
                                    or not isinstance(arguments, dict)
                                    or set(arguments) != {"command", "timeoutSeconds"}
                                    or not isinstance(arguments["command"], str)
                                    or not arguments["command"]
                                    or len(arguments["command"].encode()) > 65536
                                    or type(arguments["timeoutSeconds"]) not in (int, float)
                                    or not math.isfinite(arguments["timeoutSeconds"])
                                    or not 0 < arguments["timeoutSeconds"] <= request["remainingSeconds"]):
                                raise StudyError("Unsupported isolated tool request")
                            seen_tools.add(identity)
                            result = tool(arguments, max(0, deadline - time.monotonic()))
                            reply = (json.dumps({"type": "tool_result", "id": identity, "result": result}) + "\n").encode()
                            if len(reply) > RECORD_LIMIT:
                                raise StudyError("Isolated tool reply exceeds control limit")
                            process.stdin.write(reply)
                            process.stdin.flush()
                        elif kind == "complete":
                            receipt = record
                        else:
                            raise StudyError("Unexpected SDK control record")
            process.wait(timeout=max(0.01, deadline - time.monotonic()))
            if buffers["stdout"] or process.returncode or receipt is None or seen_session is None:
                raise StudyError("SDK session lacks complete correlated terminal evidence")
            terminal = receipt.get("receipt")
            if not isinstance(terminal, dict) or terminal.get("session_id") != seen_session:
                raise StudyError("SDK terminal receipt belongs to a different session")
        return receipt
    except UnicodeError as error:
        raise StudyError("SDK control text is not valid UTF-8") from error
    finally:
        selector.close()
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()
        (directory / "stderr.txt").write_bytes(buffers["stderr"])
        if on_stop:
            on_stop()
