"""Offline semantic tests for accounting, gates, timeouts and durable recovery."""
import importlib
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def study(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "harness"))
    return importlib.import_module("study")


@pytest.fixture
def config():
    return json.loads((ROOT / "harness/study-config.json").read_text())


def controller(study, config, path):
    return study.Controller(path, config, smoke=True, phase="first", study_id="test-study")


@pytest.mark.parametrize("bad", [None, True, -1, "nan", "Infinity", "0.0000000001", "bad"])
def test_invalid_credits_never_default_to_zero(study, bad):
    with pytest.raises(study.StudyError):
        study.credits(bad)


def test_exact_credit_boundary_prior_all_attempts_and_overrun(study):
    ledger = {"ceiling_nano": study.MAX_CREDITS, "prior_nano": study.MAX_CREDITS - 500 * study.NANO, "entries": {}}
    study.reserve(ledger, "failed", 300 * study.NANO)
    study.reconcile(ledger, "failed", {"totalNanoAiu": 100 * study.NANO, "credits_complete": True})
    study.reserve(ledger, "retry", 400 * study.NANO)  # Exact remaining boundary.
    with pytest.raises(study.StudyError, match="ceiling"):
        study.reserve(ledger, "extra", 1)
    with pytest.raises(study.StudyError, match="exceeded reservation"):
        study.reconcile(ledger, "retry", {"totalNanoAiu": 401 * study.NANO, "credits_complete": True})
    assert ledger["entries"]["retry"]["actual_nano"] == 401 * study.NANO
    with pytest.raises(study.StudyError):
        study.reserve(ledger, "after-overrun", 1)


@pytest.mark.parametrize("usage", [None, {}, {"totalNanoAiu": 0}, {"totalNanoAiu": -1, "credits_complete": True},
                                   {"totalNanoAiu": True, "credits_complete": True},
                                   {"totalNanoAiu": 0, "credits_complete": False, "aiCreditsStatus": "complete"}])
def test_unknown_usage_holds_reservation_and_blocks(study, usage):
    ledger = {"ceiling_nano": study.MAX_CREDITS, "prior_nano": 0, "entries": {}}
    study.reserve(ledger, "attempt", study.NANO)
    study.reconcile(ledger, "attempt", usage)
    assert ledger["entries"]["attempt"]["status"] == "unknown"
    assert ledger["entries"]["attempt"]["reserved_nano"] == study.NANO
    with pytest.raises(study.StudyError, match="Unknown usage"):
        study.reserve(ledger, "next", 0)


def test_ceiling_cannot_be_raised_or_prior_spend_assumed(study, config):
    with pytest.raises(study.StudyError, match="explicit"):
        study.validate_config(config, smoke=False)
    config["prior_credits"] = 0
    config["ceiling_credits"] = 300001
    with pytest.raises(study.StudyError, match="300,000"):
        study.validate_config(config, smoke=False)


def test_unknown_config_cannot_smuggle_credentials_into_state(study, config):
    config["token"] = "synthetic-only"
    with pytest.raises(study.StudyError, match="unknown fields"):
        study.validate_config(config, smoke=True)


def test_interrupted_repository_setup_preserves_zero_step_metadata(study, config, tmp_path, monkeypatch):
    def interrupted_copy(*args, **kwargs):
        raise OSError("Synthetic disk interruption")

    monkeypatch.setattr(study.shutil, "copytree", interrupted_copy)
    current = controller(study, config, tmp_path)
    assert not current.go()
    assert len(list((tmp_path / "runs").glob("*/run.json"))) == 3
    summary = study.read_json(tmp_path / "results/summary.json")
    assert len(summary["runs"]) == 3 and all(run["end"] is None for run in summary["runs"])

def test_complete_nominal_freeze_cannot_bypass_soft_billing_stop(study, config, monkeypatch):
    config["prior_credits"] = 0
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "synthetic-token-never-output")
    monkeypatch.setattr(study.shutil, "which", lambda tool: f"/tools/{tool}")
    monkeypatch.setattr(study, "freeze_errors", lambda *args: [])
    versions = {"copilot": "GitHub Copilot CLI 1.0.105.\nRun 'copilot update' to check for updates.",
                "ruff": "0.17.3", "lizard": "1.24.3", "jscpd": "5.4.1"}
    def version_output(args, **kwargs):
        if args[0] == "copilot":
            assert args == ["copilot", "--no-auto-update", "--version"]
        return versions.get(args[0], "")
    monkeypatch.setattr(study, "command", version_output)
    errors = study.preflight(config, smoke=False)
    assert len(errors) == 1
    assert "provider-enforced hard billing" in errors[0]
    assert "synthetic-token" not in str(errors)


@pytest.mark.parametrize(("output", "accepted"), [
    ("1.0.105", True),
    ("GitHub Copilot CLI 1.0.105", True),
    ("GitHub Copilot CLI 1.0.105.\nRun 'copilot update' to check for updates.", True),
    ("GitHub Copilot CLI 1.0.104.", False),
    ("GitHub Copilot CLI 1.0.1050.", False),
    ("GitHub Copilot CLI 1.0.105.1", False),
    ("GitHub Copilot CLI 1.0.105-beta", False),
    ("not a version\nGitHub Copilot CLI 1.0.105.", False),
    ("", False),
])
def test_cli_version_requires_exact_release_and_retains_paid_stop(
        study, config, monkeypatch, output, accepted):
    config["prior_credits"] = 0
    monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "synthetic-token-never-output")
    monkeypatch.setattr(study.shutil, "which", lambda tool: f"/tools/{tool}")
    monkeypatch.setattr(study, "freeze_errors", lambda *args: [])
    versions = {"copilot": output, "ruff": "0.17.3", "lizard": "1.24.3", "jscpd": "5.4.1"}
    monkeypatch.setattr(study, "command", lambda args, **kwargs: versions.get(args[0], ""))
    errors = study.preflight(config, smoke=False)
    assert ("copilot must be pinned to 1.0.105" not in errors) is accepted
    assert any("provider-enforced hard billing" in error for error in errors)


def test_missing_freeze_and_legacy_tag_are_not_authorisation(study, config, tmp_path):
    assert "Missing owner-approved" in study.freeze_errors(config, tmp_path)[0]
    (tmp_path / "protocol").mkdir()
    (tmp_path / "protocol/freeze.json").write_text(json.dumps({"tag": "protocol-frozen"}))
    errors = study.freeze_errors(config, tmp_path)
    assert any("legacy protocol-frozen" in error for error in errors)
    for gate in ("local_runtime_evidence", "contract_panel_review", "oracle_stability",
                 "cr1_estimands", "secondary_scope", "outage_assistance_policy"):
        assert any(gate in error for error in errors)
    assert any("registration" in error for error in errors)


def test_valid_freeze_hash_tag_and_commit_are_checked(study, config, tmp_path, monkeypatch):
    (tmp_path / "protocol").mkdir()
    commit = "a" * 40
    manifest = dict(commit=commit, tag="protocol-frozen-v2", inputs_sha256="digest",
                    registration_url="https://example.org/registration", registration_date="2026-10-26",
                    **{gate: "Owner evidence record" for gate in study.GATES})
    (tmp_path / "protocol/freeze.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(study, "fingerprint", lambda root: "digest")
    monkeypatch.setattr(study, "command", lambda *args, **kwargs: commit)
    assert study.freeze_errors(config, tmp_path) == []
    for gate in ("local_runtime_evidence", "contract_panel_review", "oracle_stability",
                 "cr1_estimands", "secondary_scope", "outage_assistance_policy"):
        missing = dict(manifest)
        missing.pop(gate)
        (tmp_path / "protocol/freeze.json").write_text(json.dumps(missing))
        assert any(gate in error for error in study.freeze_errors(config, tmp_path))
    manifest["inputs_sha256"] = "wrong"
    (tmp_path / "protocol/freeze.json").write_text(json.dumps(manifest))
    assert any("hash mismatch" in error for error in study.freeze_errors(config, tmp_path))


def test_schedule_matches_model_matrix_and_excludes_calibration_cr(study):
    cells = study.schedule(False, "first", 2027)
    assert len(cells) == 18
    assert sum(cell["features"] * (1 if cell["arm"] == "A" else 2) + cell["change_request"]
               for cell in cells) == 318
    assert len(study.schedule(False, "pilot", 2027)) == 9
    assert not any(cell["change_request"] for cell in study.schedule(False, "pilot", 2027))
    for alias, legacy in (("calibration", "pilot"), ("pilot-estimation", "first")):
        actual = study.schedule(False, alias, 2027)
        original = study.schedule(False, legacy, 2027)
        assert [dict(cell, run_id="") for cell in actual] == [dict(cell, run_id="") for cell in original]
    assert study.schedule(False, "first", 2027) == cells
    for model in ("gpt-6.1-sol", "claude-sonnet-5.5", "gemini-4-argon"):
        for arm in "ABC":
            selected = [cell for cell in cells if cell["assigned_model"] == model and cell["arm"] == arm]
            assert {cell["replicate"] for cell in selected} == {1, 2}
            assert all(cell["analysis_design"] == "model-stratified-v1" for cell in selected)
    assert len({cell["run_id"] for cell in cells}) == 18


def test_lock_is_exclusive(study, tmp_path):
    with (study.study_lock(tmp_path),
          pytest.raises(study.StudyError, match="Another controller"),
          study.study_lock(tmp_path)):
        pytest.fail("Concurrent writer admitted")


def test_resume_refuses_changed_budget_prior_spend_and_inputs(study, config, tmp_path):
    current = controller(study, config, tmp_path)
    deadline = current.state["deadline"]
    assert controller(study, config, tmp_path).state["deadline"] == deadline
    for key, value in (("ceiling_credits", 2400), ("prior_credits", 1)):
        altered = dict(config, **{key: value})
        with pytest.raises(study.StudyError, match="Resume inputs"):
            controller(study, altered, tmp_path)


@pytest.mark.parametrize("field", ["ceiling_nano", "prior_nano", "deadline"])
def test_resume_rejects_tampered_aggregate_limits(study, config, tmp_path, field):
    current = controller(study, config, tmp_path)
    if field == "deadline":
        current.state[field] += 1
    else:
        current.state["ledger"][field] += 1
    current.save()
    with pytest.raises(study.StudyError, match="immutable limits"):
        controller(study, config, tmp_path)

def test_zero_step_cells_retained_on_persistent_deadline(study, config, tmp_path):
    current = controller(study, config, tmp_path)
    current.state["deadline"] = time.time() - 1
    current.save()
    assert not current.go()
    assert len(list((tmp_path / "runs").glob("*/run.json"))) == 3
    summary = json.loads((tmp_path / "results/summary.json").read_text())
    assert len(summary["runs"]) == 3
    assert all(run["end"] is None and run["total_cost"] is None for run in summary["runs"])
    assert all(not cell["attempts"] for cell in current.state["cells"])
    assert not controller(study, config, tmp_path).go()


def test_bounded_attempts_and_all_attempt_cost_projection(study, config, tmp_path):
    current = controller(study, config, tmp_path)
    cell = current.state["cells"][0]
    first = current.new_attempt(cell, "f01-feature")
    second = current.new_attempt(cell, "f01-feature")
    first["usage"] = {"credits_complete": True, "totalNanoAiu": 3}
    second["usage"] = {"credits_complete": True, "totalNanoAiu": 7}
    assert study.aggregate_usage(cell["attempts"]) == {"totalNanoAiu": 10, "credits_complete": True}
    with pytest.raises(study.StudyError, match="attempt limit"):
        current.new_attempt(cell, "f01-feature")
    first["usage"] = None
    assert study.aggregate_usage(cell["attempts"])["credits_complete"] is False


def test_overrun_is_persisted_before_stop(study, config, tmp_path):
    current = controller(study, config, tmp_path)
    attempt = current.new_attempt(current.state["cells"][0], "f01-feature")
    with pytest.raises(study.StudyError, match="exceeded reservation"):
        current.settle_attempt(attempt["id"], {"credits_complete": True, "totalNanoAiu": 1})
    saved = study.read_json(tmp_path / "state.json")
    assert saved["ledger"]["entries"][attempt["id"]]["actual_nano"] == 1

def test_hung_child_is_terminated_and_reaped(study, config, tmp_path):
    current = controller(study, config, tmp_path)
    run = study.StudyRun.__new__(study.StudyRun)
    run.controller = current
    start = time.monotonic()
    code, timed_out, _ = run.bounded_process(
        [sys.executable, "-c", "import signal,time; signal.signal(signal.SIGTERM, signal.SIG_IGN); time.sleep(60)"],
        tmp_path, {"PATH": os.environ["PATH"]}, tmp_path / "stdout", tmp_path / "stderr", 0.2)
    assert timed_out and code != 0 and time.monotonic() - start < 8
    assert current.state["writer_pid"] is None


def test_resume_refuses_live_writer(study, config, tmp_path):
    current = controller(study, config, tmp_path)
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"], start_new_session=True)
    try:
        current.state["writer_pid"] = child.pid
        current.save()
        with pytest.raises(study.StudyError, match="writer group"):
            controller(study, config, tmp_path)
    finally:
        os.killpg(child.pid, signal.SIGKILL)
        child.wait()


def test_ambiguous_writer_startup_is_not_silently_retried(study, config, tmp_path):
    current = controller(study, config, tmp_path)
    current.state["writer_pending"] = True
    current.save()
    with pytest.raises(study.StudyError, match="Ambiguous writer"):
        controller(study, config, tmp_path)


def test_measured_non_delivery_is_retained_and_not_retried(study, config, tmp_path, monkeypatch):
    def no_work(run, prompt, step_dir, budget):
        attempt = run.controller.new_attempt(run.cell, run.current_step)
        usage = {"credits_complete": True, "totalNanoAiu": 0}
        attempt.update(status="agent_returned", seconds=0, usage=usage)
        study.reconcile(run.controller.state["ledger"], attempt["id"], usage)
        run.controller.save()
        Path(step_dir).mkdir(parents=True, exist_ok=True)
        return {"seconds": 0, "usage": usage, "exit_code": 1, "timed_out": False}

    monkeypatch.setattr(study.StudyRun, "run_agent", no_work)
    current = controller(study, config, tmp_path)
    assert current.go()
    records = [json.loads(line) for path in (tmp_path / "runs").glob("*/steps.jsonl")
               for line in path.read_text().splitlines()]
    assert sum(len(cell["attempts"]) for cell in current.state["cells"]) == 5
    assert all(record["delivered"] is False for record in records if record["kind"] == "feature")
    assert all(record["measure"]["hidden_total"] == 12 for record in records)
    assert all(record["measure"]["hidden_passed"] == 0 for record in records)


def test_recorded_step_survives_crash_before_controller_checkpoint_clear(study, config, tmp_path, monkeypatch):
    original = study.StudyRun.record
    crashed = []

    def record_then_crash(run, rec):
        original(run, rec)
        if not crashed:
            crashed.append(True)
            raise study.StudyError("Simulated controller interruption")

    monkeypatch.setattr(study.StudyRun, "record", record_then_crash)
    current = controller(study, config, tmp_path)
    assert not current.go()
    monkeypatch.setattr(study.StudyRun, "record", original)
    resumed = controller(study, config, tmp_path)
    assert resumed.go()
    assert sum(len(cell["attempts"]) for cell in resumed.state["cells"]) == 5
    assert sum(len(path.read_text().splitlines()) for path in (tmp_path / "runs").glob("*/steps.jsonl")) == 5


def test_docker_has_only_repo_and_session_mounts_and_no_token_argument(study, tmp_path):
    args = study.docker_command(tmp_path / "repo", tmp_path / "attempt", "sha256:" + "a" * 64,
                                "fixed prompt", 300, "mve-test")
    assert args.count("--mount") == 2
    assert not any("suites" in arg or "docker.sock" in arg for arg in args)
    assert "--no-ask-user" in args and "--no-auto-update" in args and "-p" in args
    assert "COPILOT_GITHUB_TOKEN" in args and not any(arg.startswith("COPILOT_GITHUB_TOKEN=") for arg in args)
    assert "--read-only" in args and "--security-opt=no-new-privileges" in args
    with pytest.raises(study.StudyError, match="immutable"):
        study.docker_command(tmp_path, tmp_path, "mutable:latest", "", 300, "mve-test")


def test_stub_pipeline_resume_deduplicates_steps_and_never_creates_tags(study, config, tmp_path):
    current = controller(study, config, tmp_path)
    assert current.go()
    before = {path: path.read_bytes() for path in (tmp_path / "runs").glob("*/steps.jsonl")}
    assert len(before) == 3
    assert sum(len(text.splitlines()) for text in before.values()) == 5
    assert controller(study, config, tmp_path).go()
    assert all(path.read_bytes() == text for path, text in before.items())
    assert all(not list((path.parent / "repo/.git/refs/tags").glob("*")) for path in before)
    summary = json.loads((tmp_path / "results/summary.json").read_text())
    assert len(summary["runs"]) == 3
    assert set(summary["endpoints"]) == {"H1", "H2", "H6", "resources"}
    assert "verdict" not in json.dumps(summary)
    assert summary["provenance"]["diagnostic_stub"] is True
    assert not list(tmp_path.rglob("*.env"))


def test_interrupted_unmeasured_attempt_retries_without_adding_replicates(study, config, tmp_path, monkeypatch):
    original = study.StudyRun._measure_once
    interrupted = []

    def fail_once(run, *args, **kwargs):
        if not interrupted:
            interrupted.append(True)
            raise study.RetryableError("Synthetic evaluator outage")
        return original(run, *args, **kwargs)

    monkeypatch.setattr(study.StudyRun, "_measure_once", fail_once)
    current = controller(study, config, tmp_path)
    assert current.go()
    assert sum(len(cell["attempts"]) for cell in current.state["cells"]) == 5
    assert sum(attempt["measurement"]["calls"] for cell in current.state["cells"]
               for attempt in cell["attempts"]) == 6
    summary = json.loads((tmp_path / "results/summary.json").read_text())
    assert len(summary["runs"]) == 3
    records = [json.loads(line) for path in (tmp_path / "runs").glob("*/steps.jsonl")
               for line in path.read_text().splitlines()]
    assert len(records) == 5
    assert sum(len(record["attempts"]) for record in records) == 5


def test_dry_run_is_read_only_and_live_refusal_never_calls_agent(study, monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["study", "--smoke", "--dry-run"])
    monkeypatch.setattr(study.Controller, "__init__", lambda *args, **kwargs: pytest.fail("Dry-run wrote state"))
    assert study.main() == 0
    preview = json.loads(capsys.readouterr().out)
    assert len(preview["schedule"]) == 3 and not preview["hard_billing_supported"]
    monkeypatch.setattr(sys, "argv", ["study", "--dry-run"])
    assert study.main() == 2
    assert "soft credit caps" in capsys.readouterr().out


def test_recorded_overrun_blocks_admission_even_with_aggregate_room(study):
    ledger = {"ceiling_nano": study.MAX_CREDITS, "prior_nano": 0, "entries": {}}
    study.reserve(ledger, "first", 300 * study.NANO)
    with pytest.raises(study.StudyError, match="exceeded reservation"):
        study.reconcile(ledger, "first", {"totalNanoAiu": 301 * study.NANO, "credits_complete": True})
    with pytest.raises(study.StudyError, match="stays blocked"):
        study.reserve(ledger, "second", 300 * study.NANO)


def test_setup_metadata_write_is_atomic(study, config, tmp_path, monkeypatch):
    current = controller(study, config, tmp_path)
    runner = importlib.import_module("runner")
    real_replace = os.replace

    def interrupted(src, dst):
        if str(dst).endswith("run.json") and '"config"' in Path(src).read_text():
            raise OSError("Synthetic interruption")
        return real_replace(src, dst)

    monkeypatch.setattr(runner.os, "replace", interrupted)
    assert not current.go()
    for path in (tmp_path / "runs").glob("*/run.json"):
        assert "run_id" in json.loads(path.read_text())


@pytest.mark.parametrize("failure", ["serialize", "replace"])
def test_setup_interruption_preserves_exact_scheduled_metadata(study, config, tmp_path, monkeypatch, failure):
    current = controller(study, config, tmp_path)
    runner = importlib.import_module("runner")
    cell = current.state["cells"][0]
    args = study.SimpleNamespace(config=str(current.runtime_config), suite=str(ROOT / "suites/s1-retrofit"),
                                 arm=cell["arm"], run_id=cell["run_id"], phase=current.phase,
                                 features=cell["features"], no_cr=not cell["change_request"], allow_draft=False)
    run = study.StudyRun(args, current, cell)
    path = Path(run.dir) / "run.json"
    previous = path.read_bytes()
    real_dump, real_replace = runner.json.dump, runner.os.replace

    def interrupted_dump(value, stream, **kwargs):
        if stream.name == str(path) + ".tmp":
            stream.write('{"run_id":')
            raise OSError("Synthetic serialization interruption")
        return real_dump(value, stream, **kwargs)

    def interrupted_replace(source, destination):
        if destination == str(path):
            assert json.loads(Path(source).read_text())["run_id"] == cell["run_id"]
            raise OSError("Synthetic replacement interruption")
        return real_replace(source, destination)

    if failure == "serialize":
        monkeypatch.setattr(runner.json, "dump", interrupted_dump)
    else:
        monkeypatch.setattr(runner.os, "replace", interrupted_replace)

    with pytest.raises(OSError, match="Synthetic"):
        run.setup()

    assert path.read_bytes() == previous
    assert json.loads(previous)["run_id"] == cell["run_id"]


def test_journal_without_final_newline_is_refused_before_resume(study, config, tmp_path):
    current = controller(study, config, tmp_path)
    assert current.go()
    path = next((tmp_path / "runs").glob("*/steps.jsonl"))
    torn = path.read_text().rstrip("\n")
    path.write_text(torn)
    cell = next(c for c in current.state["cells"] if c["run_id"] == path.parent.name)
    with pytest.raises(study.StudyError, match="final newline"):
        current.run_cell(cell)
    assert path.read_text() == torn


def study_run(study, current, cell=None):
    cell = cell or current.state["cells"][0]
    args = study.SimpleNamespace(
        config=str(current.runtime_config), suite=str(ROOT / "suites/s1-retrofit"),
        arm=cell["arm"], run_id=cell["run_id"], phase=current.phase,
        features=cell["features"], no_cr=not cell["change_request"], allow_draft=False,
        assigned_model=cell.get("assigned_model"), analysis_design=cell.get("analysis_design"),
        replicate=cell.get("replicate"), study_id=current.study_id, diagnostic=current.smoke)
    run = study.StudyRun(args, current, cell)
    run.current_step = "f01-feature"
    return run


def test_current_model_identity_survives_atomic_setup(study, config, tmp_path):
    current = study.Controller(tmp_path, dict(config, prior_credits=0), smoke=False,
                               phase="pilot-estimation", study_id="planned")
    for model in ("gpt-6.1-sol", "claude-sonnet-5.5", "gemini-4-argon"):
        cell = next(cell for cell in current.state["cells"] if cell["assigned_model"] == model)
        run = study_run(study, current, cell)
        run.setup()
        meta = json.loads((Path(run.dir) / "run.json").read_text())
        assert meta["assigned_model"] == meta["config"]["agent_values"]["model"] == model
        assert meta["analysis_design"] == "model-stratified-v1"
        assert meta["replicate"] == cell["replicate"] and meta["diagnostic"] is False
    assert study.Controller(tmp_path, dict(config, prior_credits=0), smoke=False,
                            phase="pilot-estimation", study_id="planned").state["identity"]["model_roster"]


def test_resume_rejects_tampered_model_allocation_and_raw_identity(study, config, tmp_path):
    for kind in ("roster", "cell", "metadata"):
        directory = tmp_path / kind
        cfg = dict(config, prior_credits=0)
        current = study.Controller(directory, cfg, smoke=False, phase="first", study_id="planned")
        if kind == "roster":
            current.state["identity"]["model_roster"][0] = "unapproved-model"
            current.save()
        elif kind == "cell":
            current.state["cells"][0]["assigned_model"] = "unapproved-model"
            current.save()
        else:
            path = directory / "runs" / current.state["cells"][0]["run_id"] / "run.json"
            meta = json.loads(path.read_text())
            meta["replicate"] = 99
            path.write_text(json.dumps(meta))
        with pytest.raises(study.StudyError, match="Resume inputs|immutable"):
            study.Controller(directory, cfg, smoke=False, phase="first", study_id="planned")


def test_current_budget_and_retry_configuration_boundaries(study, config):
    config["prior_credits"] = 0
    study.validate_config(config, smoke=False)
    for key, wrong in (("ceiling_credits", 300001), ("max_attempts", 3),
                       ("session_reserve_credits", 301)):
        changed = dict(config, **{key: wrong})
        with pytest.raises(study.StudyError):
            study.validate_config(changed, smoke=False)
    assert 133.5 * 3600 < config["study_timeout_seconds"] <= 30 * 86400


def test_agent_retry_uses_remaining_original_time_and_credits(study, config, tmp_path, monkeypatch):
    current = controller(study, config, tmp_path)
    run = study_run(study, current)
    run.setup()
    previous = current.new_attempt(run.cell, run.current_step)
    previous.update(seconds=40, usage={"totalNanoAiu": 200 * study.NANO, "credits_complete": True})
    seen = []

    def bounded(args, cwd, env, out, err, timeout):
        seen.append(timeout)
        return 0, False, 0.1

    monkeypatch.setattr(run, "bounded_process", bounded)
    run.run_agent("synthetic", str(tmp_path / "session"), 120)
    assert seen == [80]
    assert run.cell["attempts"][-1]["credit_limit_nano"] == 100 * study.NANO
    assert len(run.cell["attempts"]) == 2


def test_unknown_duration_never_becomes_a_free_retry(study, config, tmp_path, monkeypatch):
    current = controller(study, config, tmp_path)
    run = study_run(study, current)
    previous = current.new_attempt(run.cell, run.current_step)
    previous["usage"] = {"totalNanoAiu": 0, "credits_complete": True}
    monkeypatch.setattr(run, "bounded_process", lambda *_: pytest.fail("Unknown duration launched work"))
    for duration in (None, -1, True, float("nan")):
        previous["seconds"] = duration
        with pytest.raises(study.StudyError, match="Unknown"):
            run.run_agent("synthetic", "unused", 120)
    assert len(run.cell["attempts"]) == 1


def test_exhausted_step_allowance_never_launches_another_attempt(study, config, tmp_path, monkeypatch):
    current = controller(study, config, tmp_path)
    run = study_run(study, current)
    previous = current.new_attempt(run.cell, run.current_step)
    monkeypatch.setattr(run, "bounded_process", lambda *_: pytest.fail("Exhausted allowance launched work"))
    for seconds, nano in ((120, 0), (0, 300 * study.NANO)):
        previous.update(seconds=seconds, usage={"totalNanoAiu": nano, "credits_complete": True})
        with pytest.raises(study.StudyError, match="exhausted"):
            run.run_agent("synthetic", "unused", 120)
    previous.update(seconds=0, usage=None)
    with pytest.raises(study.StudyError, match="Unknown"):
        run.run_agent("synthetic", "unused", 120)
    assert len(run.cell["attempts"]) == 1


def test_measurement_exhaustion_is_durable_and_never_replays_agent(study, config, tmp_path, monkeypatch):
    current = controller(study, config, tmp_path)
    run = study_run(study, current)
    run.setup()
    attempt = current.new_attempt(run.cell, run.current_step)
    attempt.update(seconds=1, usage={"totalNanoAiu": 0, "credits_complete": True})
    seen = []

    def failed(*args):
        seen.append(True)
        raise study.RetryableError("Synthetic evaluator outage")

    monkeypatch.setattr(study.StudyRun, "_measure_once", failed)
    with pytest.raises(study.StudyError, match="exhausted"):
        run.measure(1, "unused", "")
    assert len(seen) == 2 and attempt["measurement"]["status"] == "exhausted"
    resumed = study_run(study, controller(study, config, tmp_path))
    with pytest.raises(study.StudyError, match="retry limit"):
        resumed.measure(1, "unused", "")
    for status in ("pending", "running", "infrastructure_failure", "complete", "exhausted", "snapshot_changed"):
        resumed.cell["attempts"][0]["measurement"]["status"] = status
        with pytest.raises(study.StudyError, match="replay"):
            resumed.run_agent("synthetic", "unused", 120)
    assert len(seen) == 2 and len(resumed.cell["attempts"]) == 1


def test_evaluator_snapshot_mismatch_halts_future_collection(study, config, tmp_path, monkeypatch):
    current = controller(study, config, tmp_path)
    run = study_run(study, current)
    run.setup()
    current.new_attempt(run.cell, run.current_step)
    monkeypatch.setattr(run, "_measure_once", lambda *_: {"head": "wrong-snapshot"})
    with pytest.raises(study.StudyError, match="snapshot"):
        run.measure(1, "unused", "")
    assert current.state["oracle_halt"] is True
    monkeypatch.setattr(study.StudyRun, "run_agent", lambda *_: pytest.fail("Halted oracle launched work"))
    assert not controller(study, config, tmp_path).go()
    recovery = controller(study, config, tmp_path / "recovery")
    retained = study_run(study, recovery)
    retained.setup()
    attempt = recovery.new_attempt(retained.cell, retained.current_step)
    attempt["measurement"] = {"head": "wrong-retained-snapshot", "calls": 1, "status": "infrastructure_failure"}
    with pytest.raises(study.StudyError, match="snapshot"):
        retained.measure(1, "unused", "")
    assert recovery.state["oracle_halt"] is True


def test_prepared_command_selects_only_an_approved_model(study, tmp_path):
    for model in ("gpt-6.1-sol", "claude-sonnet-5.5", "gemini-4-argon"):
        args = study.docker_command(tmp_path, tmp_path, "sha256:" + "a" * 64,
                                   "synthetic", 300, "mve-test", model=model)
        assert args[args.index("--model") + 1] == model
    with pytest.raises(study.StudyError, match="Unapproved"):
        study.docker_command(tmp_path, tmp_path, "sha256:" + "a" * 64,
                             "synthetic", 300, "mve-test", model="unapproved-model")


def test_smoke_never_claims_an_experimental_model(study, config, tmp_path):
    current = controller(study, config, tmp_path)
    assert len(current.state["cells"]) == 3
    assert "model_roster" not in current.state["identity"]
    for cell in current.state["cells"]:
        assert "assigned_model" not in cell and "analysis_design" not in cell
        meta = json.loads((tmp_path / "runs" / cell["run_id"] / "run.json").read_text())
        assert meta["diagnostic"] is True and "assigned_model" not in meta
