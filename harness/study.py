"""Offline-safe, resumable study controller. Current Copilot billing is soft-capped."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import time
from contextlib import contextmanager
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import SimpleNamespace

from analyze import step_usage
from runner import Run, git, head
from study_io import ROOT, StudyError, atomic_json, command, read_json

NANO = 1_000_000_000
MAX_CREDITS = 2500 * NANO
INPUTS = ("protocol", "harness", "skeleton", "suites", "run-study.sh", "scripts")
GATES = (
    "independent_suite_review", "access_probe", "docker_amendment",
    "missing_feature_policy", "retry_policy", "evaluator_information_policy",
    "analysis_reconciliation", "h4_definition", "h7_definition",
    "telemetry_coverage", "prior_data_disclosure", "budget_calibration",
)


class RetryableError(RuntimeError):
    """An unmeasured infrastructure failure, never a measured task failure."""


def credits(value: object) -> int:
    """Convert nonnegative credits to exact integer nano-credits."""
    if value is None or isinstance(value, bool):
        raise StudyError("Credit amounts must be explicit nonnegative numbers")
    try:
        amount = Decimal(str(value)) * NANO
    except InvalidOperation as error:
        raise StudyError("Invalid credit amount") from error
    if not amount.is_finite() or amount < 0 or amount != amount.to_integral_value():
        raise StudyError("Credit amounts must be finite, nonnegative nano-credit multiples")
    return int(amount)


def validate_config(cfg: dict, *, smoke: bool) -> None:
    """Reject unaffordable, unknown or unbounded controller settings."""
    expected = {"seed", "ceiling_credits", "prior_credits", "session_reserve_credits",
                "max_attempts", "study_timeout_seconds", "min_disk_gib", "freeze_manifest"}
    if set(cfg) != expected:
        raise StudyError("Configuration has missing or unknown fields; never put credentials in config")
    if not 0 < credits(cfg["ceiling_credits"]) <= MAX_CREDITS:
        raise StudyError("Aggregate ceiling must be positive and at most 2,500 AI credits")
    prior = 0 if smoke else credits(cfg["prior_credits"])
    if prior > credits(cfg["ceiling_credits"]):
        raise StudyError("Prior pilot spending exceeds aggregate ceiling")
    if not 0 < credits(cfg["session_reserve_credits"]) <= credits(cfg["ceiling_credits"]):
        raise StudyError("Session reservation must fit the aggregate ceiling")
    for name, upper in (("max_attempts", 10), ("study_timeout_seconds", 30 * 86400),
                        ("min_disk_gib", 10000)):
        if type(cfg[name]) is not int or not 1 <= cfg[name] <= upper:
            raise StudyError(f"{name} must be an integer in 1..{upper}")
    if type(cfg["seed"]) is not int:
        raise StudyError("seed must be an integer")
    if not isinstance(cfg["freeze_manifest"], str):
        raise StudyError("freeze_manifest must be a relative path")


def fingerprint(root: Path = ROOT) -> str:
    """Hash all execution inputs, including untracked changes but excluding caches."""
    digest = hashlib.sha256()
    for target in INPUTS:
        source = root / target
        if source.is_symlink():
            raise StudyError("Execution inputs must not contain symlinks")
        for path in [source] if source.is_file() else sorted(source.rglob("*")):
            if "__pycache__" in path.parts or ".pytest_cache" in path.parts:
                continue
            if path.is_symlink():
                raise StudyError("Execution inputs must not contain symlinks")
            if path.is_file() and path != root / "protocol/freeze.json":
                digest.update(path.relative_to(root).as_posix().encode() + b"\0")
                digest.update(b"x" if path.stat().st_mode & 0o111 else b"-")
                digest.update(path.read_bytes())
    return digest.hexdigest()


def schedule(smoke: bool, phase: str, seed: int) -> list[dict]:
    """Randomise arm order in fixed replicate blocks; smoke is never study data."""
    rng = random.Random(seed)
    cells = []
    for replicate in range(1, 2 if smoke or phase == "pilot" else 5):
        arms = list("ABC")
        rng.shuffle(arms)
        for arm in arms:
            cells.append({"run_id": f"{'smoke' if smoke else phase}-{arm}-{replicate:02d}",
                          "arm": arm, "features": 1 if smoke else 10,
                          "change_request": not smoke and phase != "pilot"})
    return cells


def reserve(ledger: dict, attempt: str, amount: int) -> None:
    """Hard admission rule: reconciled spend plus outstanding reservations fits."""
    if type(amount) is not int or amount < 0:
        raise StudyError("Reservation must be nonnegative integer nano-credits")
    if attempt in ledger["entries"]:
        raise StudyError("Attempt reservation already exists")
    entries = ledger["entries"].values()
    if any(entry["status"] == "unknown" for entry in entries):
        raise StudyError("Unknown usage holds its reservation and blocks new work")
    if any(entry["status"] == "complete" and entry["actual_nano"] > entry["reserved_nano"] for entry in entries):
        raise StudyError("Actual credits exceeded a reservation; new work stays blocked")
    used = ledger["prior_nano"] + sum(
        entry["actual_nano"] if entry["status"] == "complete" else entry["reserved_nano"]
        for entry in ledger["entries"].values())
    if used + amount > ledger["ceiling_nano"]:
        raise StudyError("Aggregate credit admission ceiling exhausted; no new work launched")
    ledger["entries"][attempt] = {"reserved_nano": amount, "actual_nano": None, "status": "reserved"}


def accounted_nano(usage: dict | None) -> int | None:
    """Use the same explicit completeness precedence as the corrected analyzer."""
    nano = usage.get("totalNanoAiu") if isinstance(usage, dict) else None
    complete = isinstance(usage, dict) and usage.get(
        "credits_complete", usage.get("aiCreditsStatus") == "complete") is True
    if not complete or type(nano) is not int or nano < 0:
        return None
    return nano


def reconcile(ledger: dict, attempt: str, usage: dict | None) -> None:
    """Keep missing accounting unknown; record and stop on reservation overruns."""
    entry = ledger["entries"][attempt]
    nano = accounted_nano(usage)
    if nano is None:
        entry["status"] = "unknown"
        return
    entry.update(actual_nano=nano, status="complete")
    if nano > entry["reserved_nano"]:
        raise StudyError("Actual credits exceeded reservation; billing bound is not enforced")


def freeze_errors(cfg: dict, root: Path = ROOT) -> list[str]:
    """Verify owner-supplied provenance and gates; never create or move a tag."""
    manifest_path = (root / cfg["freeze_manifest"]).resolve()
    if not manifest_path.is_relative_to(root / "protocol") or not manifest_path.is_file():
        return ["Missing owner-approved protocol/freeze.json (no protocol is declared frozen)"]
    manifest = read_json(manifest_path)
    errors = []
    commit = manifest.get("commit", "")
    tag = manifest.get("tag", "")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        errors.append("Freeze requires a full commit SHA")
    elif command(["git", "rev-parse", "HEAD"], cwd=root) != commit:
        # A subsequent manifest-only commit avoids a self-referential commit SHA.
        differences = command(["git", "diff", "--name-only", commit, "HEAD"], cwd=root).splitlines()
        if differences != [manifest_path.relative_to(root).as_posix()]:
            errors.append("HEAD differs from authorised freeze beyond its provenance manifest")
    if not isinstance(tag, str) or not re.fullmatch(r"protocol-frozen-v[0-9]+", tag):
        errors.append("Freeze requires a new owner-authorised versioned tag, not legacy protocol-frozen")
    elif command(["git", "rev-parse", f"refs/tags/{tag}^{{commit}}"], cwd=root) != commit:
        errors.append("Freeze tag does not resolve to authorised commit")
    if manifest.get("inputs_sha256") != fingerprint(root):
        errors.append("Protocol/suite/prompts/runtime/analysis input hash mismatch")
    if not isinstance(manifest.get("registration_url"), str) or not manifest["registration_url"].startswith("https://"):
        errors.append("Prospective registration URL missing")
    if not manifest.get("registration_date"):
        errors.append("Prospective registration date missing")
    for gate in GATES:
        if not isinstance(manifest.get(gate), str) or not manifest[gate].strip():
            errors.append(f"Owner evidence missing: {gate}")
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", str(manifest.get("image_digest", ""))):
        errors.append("Immutable Docker image digest missing")
    return errors


def preflight(cfg: dict, *, smoke: bool, root: Path = ROOT) -> list[str]:
    """Check prerequisites without launching a model, changing git or printing tokens."""
    errors = []
    try:
        validate_config(cfg, smoke=smoke)
    except (StudyError, KeyError) as error:
        errors.append(str(error))
    if sys.version_info < (3, 11):  # noqa: UP036 - check the VM, not just the development interpreter.
        errors.append("Python 3.11+ required")
    for tool in (("git", "make") if smoke else ("git", "make", "docker", "copilot", "gh", "ruff", "lizard", "jscpd")):
        if not shutil.which(tool):
            errors.append(f"Required tool missing: {tool}")
    minimum = cfg.get("min_disk_gib")
    if type(minimum) is int and shutil.disk_usage(root).free < minimum * 1024**3:
        errors.append(f"Insufficient disk: require {minimum} GiB free")
    if not smoke:
        if not os.environ.get("COPILOT_GITHUB_TOKEN"):
            errors.append("COPILOT_GITHUB_TOKEN is not present (value never displayed)")
        if shutil.which("git") and command(["git", "status", "--porcelain"], cwd=root):
            errors.append("Live execution requires a clean git worktree")
        for tool, args, version in (
            ("copilot", ["copilot", "--version"], "1.0.103"),
            ("ruff", ["ruff", "--version"], "0.17.2"),
            ("lizard", ["lizard", "--version"], "1.24.3"),
            ("jscpd", ["jscpd", "--version"], "5.4.1"),
        ):
            if shutil.which(tool) and not re.search(rf"(?<![\d.]){re.escape(version)}(?![\d.])", command(args)):
                errors.append(f"{tool} must be pinned to {version}")
        if shutil.which("docker"):
            try:
                command(["docker", "info", "--format", "{{.ServerVersion}}"])
            except (StudyError, subprocess.TimeoutExpired):
                errors.append("Docker daemon unavailable to current user; no sudo attempted")
        if isinstance(cfg.get("freeze_manifest"), str):
            try:
                errors.extend(freeze_errors(cfg, root))
            except (StudyError, OSError, ValueError, subprocess.TimeoutExpired):
                errors.append("Freeze evidence unreadable or tag verification failed")
        errors.append("Paid execution disabled: Copilot 1.0.103 has only soft credit caps; "
                      "a provider-enforced hard billing boundary is required")
    return errors


@contextmanager
def study_lock(directory: Path):
    """Allow only one writer per durable study, including recovery and publication."""
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / "controller.lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise StudyError("Another controller owns this study") from error
        yield


def group_alive(pid: int) -> bool:
    """Conservatively refuse recovery while a recorded writer group still exists."""
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return False
    return True


def docker_command(repo: Path, session: Path, image: str, prompt: str, cap: int,
                   name: str) -> list[str]:
    """Prepare a restricted fresh session; this is not a hard-billing backend."""
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise StudyError("Agent image must use an immutable sha256 digest")
    if not re.fullmatch(r"mve-[a-z0-9-]+", name):
        raise StudyError("Invalid owned container name")
    if type(cap) is not int or cap <= 0:
        raise StudyError("Session cap must be a positive integer")
    return [
        "docker", "run", "--rm", "--init", "--name", name,
        "--user", f"{os.getuid()}:{os.getgid()}",
        "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "--pids-limit=256", "--memory=4g", "--cpus=2",
        "--tmpfs", "/tmp:rw,nosuid,size=128m",
        "--mount", f"type=bind,src={repo.resolve()},dst=/work",
        "--mount", f"type=bind,src={session.resolve()},dst=/session",
        "--workdir", "/work", "-e", "COPILOT_GITHUB_TOKEN",
        "-e", "HOME=/session/home", "-e", "COPILOT_HOME=/session/copilot-home",
        "-e", "COPILOT_AUTO_UPDATE=false", image,
        "copilot", "-C", "/work", "-p", prompt, "--model", "claude-sonnet-5.5",
        "--reasoning-effort", "medium", "--allow-all-tools", "--no-ask-user",
        "--no-custom-instructions", "--disable-builtin-mcps", "--no-auto-update",
        "--deny-tool", "shell(git push)", "--deny-tool", "url",
        "--deny-tool", "shell(curl)", "--deny-tool", "shell(wget)",
        "--deny-tool", "shell(pip)", "--deny-tool", "shell(pip3)",
        "--output-format", "json", "--usage-output-file", "/session/usage.json",
        "--max-ai-credits", str(cap), "--log-dir", "/session/logs",
    ]


def terminate(process: subprocess.Popen) -> None:
    """Stop and reap our subprocess group before recovery is allowed."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
    # The group leader can exit while descendants continue writing.
    if group_alive(process.pid):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def aggregate_usage(attempts: list[dict]) -> dict:
    """All attempts of one step contribute cost exactly once; unknown stays unknown."""
    values = [accounted_nano(attempt.get("usage")) for attempt in attempts]
    complete = bool(values) and all(value is not None for value in values)
    result = {"totalNanoAiu": sum(value for value in values if value is not None) if complete else None,
              "credits_complete": complete}
    token_usages = [step_usage("", {"agent": attempt}) for attempt in attempts]
    if token_usages and all(usage["tokens_complete"] for usage in token_usages):
        result["tokenDetails"] = {
            name: {"tokenCount": sum(usage[f"tokens_{name}"] for usage in token_usages)}
            for name in ("input", "output", "cache_read", "cache_write")}
    return result


class StudyRun(Run):
    """Reuse integrity enforcement while journaling disposable-repository steps."""

    def __init__(self, args: SimpleNamespace, controller: Controller, cell: dict):
        super().__init__(args)
        self.controller = controller
        self.cell = cell
        self.current_step = ""

    def setup(self) -> None:
        """Initialise only the owned disposable repository, preserving scheduled metadata."""
        metadata = Path(self.dir) / "run.json"
        if Path(self.repo).exists():
            if "config" not in read_json(metadata):
                raise StudyError("Incomplete repository initialisation retained; manual recovery required")
            return
        super().setup(existing_metadata=True)
        meta = read_json(metadata)
        meta.update(diagnostic=True, study_id=self.controller.study_id)
        atomic_json(metadata, meta)

    def bounded_process(self, args: list[str], cwd: Path, env: dict, out: Path,
                        err: Path, timeout: float) -> tuple[int, bool, float]:
        """Persist the process identity, bound its lifetime and retain capped logs."""
        start = time.time()
        remaining = self.controller.state["deadline"] - start
        if remaining <= 0:
            raise StudyError("Study deadline reached; no new process launched")
        self.controller.state["writer_pending"] = True
        self.controller.save()
        with out.open("wb") as stdout, err.open("wb") as stderr:
            process = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                       stdout=stdout, stderr=stderr, start_new_session=True)
            self.controller.state["writer_pid"] = process.pid
            self.controller.state["writer_pending"] = False
            timed_out = False
            try:
                self.controller.save()
                process.wait(timeout=min(timeout, remaining))
            except subprocess.TimeoutExpired:
                timed_out = True
            finally:
                terminate(process)
                self.controller.state["writer_pid"] = None
                self.controller.save()
        for path in (out, err):
            if path.stat().st_size > 1024 * 1024:
                with path.open("r+b") as stream:
                    stream.truncate(1024 * 1024)
        return process.returncode, timed_out, time.time() - start

    def run_agent(self, prompt: str, step_dir: str, budget: int) -> dict:
        """Only the built-in stub can execute until real hard billing is supported."""
        controller = self.controller
        if not controller.smoke:
            raise StudyError("No hard-bounded paid backend implemented")
        attempt = controller.new_attempt(self.cell, self.current_step)
        directory = Path(self.dir) / "attempts" / attempt["id"]
        directory.mkdir(parents=True, mode=0o700)
        attempt["directory"] = str(directory.relative_to(controller.directory))
        controller.save()
        env = {"PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""),
               "HOME": str(directory),
               "TEST_CMD": self.env_extra["TEST_CMD"], "MVE_HARNESS": str(ROOT / "harness"),
               "MVE_COMPLEXITY": "internal", "MVE_DUPLICATION": "internal", "MVE_LINT": "none",
               "PYTHONDONTWRITEBYTECODE": "1"}
        status, timed_out, seconds = self.bounded_process(
            [sys.executable, str(ROOT / "harness/fake_agent.py"), "--prompt", prompt,
             "--repo", self.repo, "--suite", self.suite_dir],
            Path(self.repo), env, directory / "stdout.txt", directory / "stderr.txt", budget)
        usage = {"totalNanoAiu": 0, "credits_complete": True,
                 "tokenDetails": {name: {"tokenCount": 0}
                                  for name in ("input", "output", "cache_read", "cache_write")}}
        attempt.update(status="timeout" if timed_out else "agent_returned", exit_code=status,
                       seconds=round(seconds, 4), usage=usage)
        controller.settle_attempt(attempt["id"], usage)
        return {"exit_code": status, "timed_out": timed_out, "seconds": seconds,
                "usage": usage, "possible_leak": False, "diagnostic_stub": True}

    def is_green(self) -> bool:
        """Bound visible-test writers under the same absolute study deadline."""
        from evaluation_env import evaluation_environment
        directory = Path(self.dir) / "attempts" / self.cell["attempts"][-1]["id"] / "checks"
        directory.mkdir(parents=True, exist_ok=True)
        with evaluation_environment() as env:
            env["TEST_CMD"] = self.env_extra["TEST_CMD"]
            code, timed_out, _ = self.bounded_process(
                ["make", "-s", "test"], Path(self.repo), env,
                directory / "visible.stdout", directory / "visible.stderr", 600)
        if timed_out:
            raise RetryableError("Visible-test infrastructure timeout; unmeasured cell retained")
        return code == 0

    def measure(self, k: int, step_dir: str, prev_ref: str, cr: bool = False) -> dict:
        """Bound external evaluation as well as the agent."""
        from evaluation_env import evaluation_environment
        directory = Path(self.dir) / "attempts" / self.cell["attempts"][-1]["id"] / "evaluation"
        directory.mkdir(parents=True, exist_ok=True)
        output = directory / "measure.json"
        args = [sys.executable, "-B", str(ROOT / "harness/measure.py"), "--repo", self.repo,
                "--suite", self.suite_dir, "--k", str(k), "--out", str(output),
                "--runner", "stdlib", "--complexity", "internal", "--duplication", "internal", "--lint", "none"]
        if prev_ref:
            args += ["--prev-ref", prev_ref]
        if cr:
            args += ["--cr"]
        with evaluation_environment() as env:
            code, timed_out, _ = self.bounded_process(args, Path(self.repo), env,
                                                      directory / "evaluator.stdout",
                                                      directory / "evaluator.stderr", 600)
        if code or timed_out:
            raise RetryableError("Evaluator failed or timed out; partial cell retained")
        return read_json(output)

    def record(self, rec: dict) -> None:
        """Fsync the canonical step before marking it complete in controller state."""
        attempts = [attempt for attempt in self.cell["attempts"] if attempt["step"] == rec["step"]]
        rec["agent"]["usage"] = aggregate_usage(attempts)
        rec["agent"]["seconds"] = (sum(attempt["seconds"] for attempt in attempts)
                                    if all(attempt.get("seconds") is not None for attempt in attempts) else None)
        rec["attempts"] = [attempt["id"] for attempt in attempts]
        super().record(rec)
        with open(self.steps_path, "a", encoding="utf-8") as stream:
            stream.flush()
            os.fsync(stream.fileno())
        for attempt in attempts:
            attempt["cost_included_in_step"] = True
        self.controller.save()


class Controller:
    """Own one immutable schedule and exactly one analysis unit per cell."""

    def __init__(self, directory: Path, cfg: dict, *, smoke: bool, phase: str, study_id: str):
        self.directory = directory
        self.cfg = cfg
        self.smoke = smoke
        self.phase = "dry" if smoke else phase
        self.study_id = study_id
        self.path = directory / "state.json"
        identity = {"study_id": study_id, "config": cfg, "smoke": smoke, "phase": self.phase,
                    "inputs_sha256": fingerprint(),
                    "commit": command(["git", "rev-parse", "HEAD"])}
        if self.path.exists():
            self.state = read_json(self.path)
            if self.state["identity"] != identity:
                raise StudyError("Resume inputs/config/git commit changed; preserve study and use a new study ID")
        else:
            started = time.time()
            self.state = {"identity": identity, "started": started,
                          "deadline": started + cfg["study_timeout_seconds"],
                          "writer_pid": None, "status": "prepared", "errors": [],
                          "writer_pending": False,
                          "ledger": {"ceiling_nano": credits(cfg["ceiling_credits"]),
                                     "prior_nano": 0 if smoke else credits(cfg["prior_credits"]), "entries": {}},
                          "cells": [dict(cell, status="pending", attempts=[], checkpoint=None)
                                    for cell in schedule(smoke, phase, cfg["seed"])]}
            self.save()
        if (self.state["ledger"]["ceiling_nano"] != credits(cfg["ceiling_credits"])
                or self.state["ledger"]["prior_nano"] != (0 if smoke else credits(cfg["prior_credits"]))
                or self.state["deadline"] > self.state["started"] + cfg["study_timeout_seconds"]):
            raise StudyError("Stored budget, prior spending or deadline differs from immutable limits")
        pid = self.state.get("writer_pid")
        if self.state.get("writer_pending"):
            raise StudyError("Ambiguous writer startup; inspect private state before any recovery")
        if pid and group_alive(pid):
            raise StudyError("Recorded writer group may still be alive; stop it before resuming")
        self.state["writer_pid"] = None
        self.runtime_config = directory / "runtime.json"
        runtime = read_json(ROOT / "harness/config.dry-run.json")
        runtime["runs_dir"] = str(directory / "runs")
        runtime["version_commands"] = {}
        atomic_json(self.runtime_config, runtime)
        for cell in self.state["cells"]:
            run_dir = directory / "runs" / cell["run_id"]
            metadata = run_dir / "run.json"
            if not metadata.exists():
                atomic_json(metadata, {"run_id": cell["run_id"], "arm": cell["arm"],
                                      "suite": "s1-retrofit", "phase": self.phase,
                                      "features": cell["features"], "change_request": cell["change_request"],
                                      "diagnostic": smoke, "study_id": study_id})

    def save(self) -> None:
        """Persist all lifecycle and accounting transitions."""
        atomic_json(self.path, self.state)

    def new_attempt(self, cell: dict, step: str) -> dict:
        """Reserve before launch, counting every infrastructure retry."""
        previous = [attempt for attempt in cell["attempts"] if attempt["step"] == step]
        if len(previous) >= self.cfg["max_attempts"]:
            raise StudyError("Bounded attempt limit reached; partial cell retained")
        attempt_id = f"{cell['run_id']}-{step}-{len(previous) + 1}"
        amount = 0 if self.smoke else credits(self.cfg["session_reserve_credits"])
        reserve(self.state["ledger"], attempt_id, amount)
        attempt = {"id": attempt_id, "step": step, "status": "running",
                   "started": time.time(), "seconds": None, "usage": None}
        cell["attempts"].append(attempt)
        self.save()
        return attempt

    def settle_attempt(self, attempt: str, usage: dict | None) -> None:
        """Persist unknown accounting and overruns even when reconciliation stops."""
        try:
            reconcile(self.state["ledger"], attempt, usage)
        finally:
            self.save()

    def run_cell(self, cell: dict) -> None:
        """Resume only unmeasured work, never retry a recorded task failure."""
        args = SimpleNamespace(config=str(self.runtime_config), suite=str(ROOT / "suites/s1-retrofit"),
                               arm=cell["arm"], run_id=cell["run_id"], phase=self.phase,
                               features=cell["features"], no_cr=not cell["change_request"], allow_draft=False)
        run = StudyRun(args, self, cell)
        run.setup()
        records = []
        path = Path(run.steps_path)
        if path.exists():
            text = path.read_text()
            if text and not text.endswith("\n"):
                raise StudyError("Journal lacks final newline: preserve partial run for manual recovery")
            for line in text.splitlines():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as error:
                    raise StudyError("Torn step record: preserve partial run for manual recovery") from error
        done = [record["step"] for record in records]
        if len(done) != len(set(done)):
            raise StudyError("Duplicate durable steps; refuse ambiguous recovery")
        checkpoint = cell.get("checkpoint")
        if checkpoint and checkpoint["step"] not in done:
            for attempt in cell["attempts"]:
                if attempt["step"] == checkpoint["step"] and attempt["status"] == "running":
                    attempt.update(status="interrupted", usage={"totalNanoAiu": 0, "credits_complete": True}
                                   if self.smoke else None)
                    self.settle_attempt(attempt["id"], attempt["usage"])
            self.save()
            git(run.repo, "reset", "-q", "--hard", checkpoint["head"])
            git(run.repo, "clean", "-qfd")
        if records and head(run.repo) != records[-1]["measure"]["head"]:
            raise StudyError("Retained repository HEAD differs from last durable measurement")
        if git(run.repo, "status", "--porcelain").stdout.strip():
            raise StudyError("Unexpected uncheckpointed work in retained repository")
        steps = []
        for k, feature in enumerate(run.features, 1):
            steps.append((f"f{k:02d}-feature", run.feature_step, (k, feature)))
            if run.arm != "A":
                kind = "consolidation" if run.arm == "B" else "review"
                steps.append((f"f{k:02d}-{kind}", run.post_step, (k,)))
        if run.do_cr:
            steps.append((f"{run.suite['change_request']['id']}-change", run.change_request, ()))
        if done != [step[0] for step in steps[:len(done)]]:
            raise StudyError("Durable step order differs from frozen schedule")
        cell["status"] = "running"
        self.save()
        for step, function, params in steps:
            if step in done:
                continue
            if time.time() >= self.state["deadline"]:
                raise StudyError("Study deadline reached; no new cell/step launched")
            cell["checkpoint"] = {"step": step, "head": head(run.repo)}
            self.save()
            run.current_step = step
            function(*params)
            cell["checkpoint"] = None
            self.save()
        cell["status"] = "completed"
        meta = read_json(Path(run.dir) / "run.json")
        meta["finished"] = time.time()
        atomic_json(Path(run.dir) / "run.json", meta)
        self.save()

    def go(self) -> bool:
        """Keep failures and unattempted cells, then always produce a complete report."""
        self.state["status"] = "running"
        self.save()
        try:
            for cell in self.state["cells"]:
                if cell["status"] == "completed":
                    continue
                if time.time() >= self.state["deadline"]:
                    self.state["status"] = "deadline"
                    self.state["stop_reason"] = "Absolute study deadline reached"
                    break
                for _ in range(self.cfg["max_attempts"]):
                    try:
                        self.run_cell(cell)
                        break
                    except (StudyError, RuntimeError, OSError, subprocess.TimeoutExpired) as error:
                        cell["status"] = "partial"
                        cell["error"] = type(error).__name__
                        cell["stop_reason"] = (str(error) if isinstance(error, (StudyError, RetryableError))
                                               else "Infrastructure failure; inspect private attempt logs")
                        self.save()
                        step = (cell.get("checkpoint") or {}).get("step")
                        attempts = [attempt for attempt in cell["attempts"] if attempt["step"] == step]
                        if (not self.smoke or not attempts or len(attempts) >= self.cfg["max_attempts"]
                                or not isinstance(error, RetryableError)):
                            break
        except KeyboardInterrupt:
            self.state["status"] = "interrupted"
            self.save()
            raise
        success = all(cell["status"] == "completed" for cell in self.state["cells"])
        self.state["status"] = "completed" if success else "partial"
        self.save()
        from study_report import export
        export(self.directory, self.state, self.study_id)
        return success


def main() -> int:
    """Check, preview, run the stub pipeline, or explicitly publish derived results."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "harness/study-config.json")
    parser.add_argument("--study-id", default="stub-smoke")
    parser.add_argument("--smoke", action="store_true", help="one feature per A/B/C, built-in fake agent only")
    parser.add_argument("--dry-run", action="store_true", help="read-only preflight and schedule")
    parser.add_argument("--check-vm", action="store_true", help="check prerequisites; never install or run agents")
    parser.add_argument("--phase", choices=["pilot", "first", "confirmatory"], default="first")
    parser.add_argument("--publish", action="store_true", help="push only derived results and create/update a PR")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", args.study_id):
        raise StudyError("study-id must be lowercase letters/digits/hyphens, at most 64 characters")
    cfg = read_json(args.config)
    errors = preflight(cfg, smoke=args.smoke)
    preview = {"mode": "stub-smoke" if args.smoke else args.phase,
               "inputs_sha256": fingerprint(),
               "schedule": (schedule(args.smoke, args.phase, cfg["seed"])
                            if type(cfg.get("seed")) is int else []),
               "token_present": bool(os.environ.get("COPILOT_GITHUB_TOKEN")),
               "hard_billing_supported": False, "errors": errors}
    if args.dry_run or args.check_vm:
        print(json.dumps(preview, indent=2))
        return 2 if errors else 0
    if errors:
        raise StudyError("; ".join(errors))
    directory = ROOT / ".study" / args.study_id
    if (ROOT / ".study").is_symlink() or directory.is_symlink():
        raise StudyError("Study state must not be symlinked")
    with study_lock(directory):
        controller = Controller(directory, cfg, smoke=args.smoke, phase=args.phase, study_id=args.study_id)
        success = controller.go()
        if args.publish:
            from study_report import publish
            publish(directory / "results", args.study_id)
    print(f"{'Completed diagnostic pipeline' if success else 'Partial diagnostic pipeline retained'}: "
          f".study/{args.study_id}/results/report.md")
    return 0 if success else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (StudyError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        # Do not echo raw tool output, prompts or arbitrary config contents.
        message = str(error) if isinstance(error, StudyError) else type(error).__name__
        print(f"Study stopped: {message}", file=sys.stderr)
        raise SystemExit(2)
