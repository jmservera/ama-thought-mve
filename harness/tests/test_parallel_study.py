"""Offline tests for concurrency, restart recovery, and calibration accounting."""
import importlib
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def study(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "harness"))
    return importlib.import_module("study")


@pytest.fixture
def config(study):
    return dict(study.read_json(ROOT / "harness/study-config.json"),
                prior_credits=14.54324, historical_credit_provisions=[])


def unregistered_manifest(study):
    commit = study.command(["git", "rev-parse", "HEAD"])
    return dict(
        {gate: "owner-reviewed evidence" for gate in study.GATES},
        registration_status="unregistered", commit=commit, inputs_sha256=study.fingerprint(),
        public_disclosure_url=f"https://github.com/jmservera/ama-thought-mve/commit/{commit}",
        owner_confirms_public_disclosure=True, disclosed_at="2026-11-07T16:46:29Z",
    )


def test_parallel_scheduler_really_overlaps_and_respects_limit(study, config, tmp_path, monkeypatch):
    report = importlib.import_module("study_report")
    current = study.Controller(tmp_path, config, smoke=False, phase="calibration", study_id="parallel",
                               short_calibration=True, parallelism=4)
    barrier = threading.Barrier(4)
    guard = threading.Lock()
    running = set()
    peak = []
    seen = []

    def run_cell(cell):
        with guard:
            assert cell["run_id"] not in running
            running.add(cell["run_id"])
            seen.append(cell["run_id"])
            peak.append(len(running))
            first = len(seen) <= 4
        if first:
            barrier.wait(timeout=10)
        time.sleep(0.01)
        with guard:
            running.remove(cell["run_id"])
        current.update(cell, status="completed")

    monkeypatch.setattr(current, "run_cell", run_cell)
    monkeypatch.setattr(report, "export", lambda *args: None)
    monkeypatch.setattr(study, "show_progress", lambda *args: None)
    assert current.go()
    assert max(peak) == 4 and len(set(seen)) == 15
    assert study.read_json(current.path)["parallelism_history"][-1]["parallelism"] == 4
    resumed = study.Controller(tmp_path, config, smoke=False, phase="calibration", study_id="parallel",
                               short_calibration=True, parallelism=2)
    assert [entry["parallelism"] for entry in resumed.state["parallelism_history"]] == [4, 2]


def test_parallel_reservations_cannot_oversubscribe_exact_ceiling(study, config, tmp_path):
    current = study.Controller(tmp_path, config, smoke=False, phase="calibration", study_id="reservation",
                               short_calibration=True, parallelism=3)
    current.state["ledger"]["prior_nano"] = current.state["ledger"]["ceiling_nano"] - 600 * study.NANO
    cells = [cell for cell in current.state["cells"] if cell["arm"] == "A"]
    barrier = threading.Barrier(3)

    def reserve(cell):
        barrier.wait(timeout=10)
        try:
            return current.new_attempt(cell, "f01-feature")["id"]
        except study.StudyError:
            return None

    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(reserve, cells))
    assert sum(value is not None for value in results) == 2
    entries = study.read_json(current.path)["ledger"]["entries"]
    assert len(entries) == 2
    assert sum(entry["reserved_nano"] for entry in entries.values()) == 600 * study.NANO


def test_distinct_paid_controllers_cannot_run_concurrently(study, tmp_path, monkeypatch):
    monkeypatch.setattr(study, "ROOT", tmp_path)
    with (study.paid_study_lock(), pytest.raises(study.StudyError, match="Another controller"),
          study.paid_study_lock()):
        pytest.fail("A second paid controller acquired the checkout lock")
    with study.paid_study_lock():
        pass


def test_reboot_retains_all_unknown_reservations_and_fresh_allowance(study, config, tmp_path, monkeypatch):
    old_boot = "00000000-0000-0000-0000-000000000001"
    new_boot = "00000000-0000-0000-0000-000000000002"
    monkeypatch.setattr(study, "boot_id", lambda: old_boot)
    current = study.Controller(tmp_path, config, smoke=False, phase="calibration", study_id="restart",
                               short_calibration=True, parallelism=4)
    cells = [cell for cell in current.state["cells"] if cell["arm"] == "A"][:2]
    for cell in cells:
        current.update(cell, checkpoint={"step": "f01-feature", "head": "checkpoint"})
        current.new_attempt(cell, "f01-feature")
        current.writer_pending(cell)
    with pytest.raises(study.StudyError, match="Ambiguous writer"):
        study.Controller(tmp_path, config, smoke=False, phase="calibration", study_id="restart",
                         short_calibration=True)
    monkeypatch.setattr(study, "boot_id", lambda: new_boot)
    resumed = study.Controller(tmp_path, config, smoke=False, phase="calibration", study_id="restart",
                               short_calibration=True, parallelism=2)
    assert len(resumed.state["restart_history"][-1]["interrupted_attempts"]) == 2
    assert all(entry["status"] == "restart_hold" and entry["actual_nano"] is None
               for entry in resumed.state["ledger"]["entries"].values())
    cell = next(cell for cell in resumed.state["cells"] if cell["run_id"] == cells[0]["run_id"])
    run = object.__new__(study.StudyRun)
    run.controller, run.cell, run.arm, run.current_step = resumed, cell, cell["arm"], "f01-feature"
    assert run.remaining_allowance(900) == (900, 270 * study.NANO)
    new_attempt = resumed.new_attempt(cell, "f01-feature")
    assert new_attempt["id"].endswith("-2") and new_attempt["parallelism"] == 2
    assert sum(entry["reserved_nano"] for entry in resumed.state["ledger"]["entries"].values()) == 900 * study.NANO


def test_same_boot_attempt_without_writer_never_receives_restart_hold(study, config, tmp_path):
    current = study.Controller(tmp_path, config, smoke=False, phase="calibration", study_id="same-boot",
                               short_calibration=True)
    cell = current.state["cells"][0]
    current.update(cell, checkpoint={"step": "f01-feature", "head": "checkpoint"})
    attempt = current.new_attempt(cell, "f01-feature")
    with pytest.raises(study.StudyError, match="Same-boot interrupted"):
        study.Controller(tmp_path, config, smoke=False, phase="calibration", study_id="same-boot",
                         short_calibration=True)
    assert study.read_json(current.path)["ledger"]["entries"][attempt["id"]]["status"] == "reserved"


def test_terminal_receipt_after_reboot_preserves_attempt_for_manual_recovery(study, config, tmp_path, monkeypatch):
    monkeypatch.setattr(study, "boot_id", lambda: "00000000-0000-0000-0000-000000000001")
    current = study.Controller(tmp_path, config, smoke=False, phase="calibration", study_id="receipt",
                               short_calibration=True)
    cell = current.state["cells"][0]
    current.update(cell, checkpoint={"step": "f01-feature", "head": "checkpoint"})
    attempt = current.new_attempt(cell, "f01-feature")
    current.update(attempt, directory="attempts/example")
    journal = tmp_path / "attempts/example/transport/events.jsonl"
    journal.parent.mkdir(parents=True)
    journal.write_text('{"type":"complete","receipt":{"usage":{"totalNanoAiu":1}}}\n', encoding="utf-8")
    monkeypatch.setattr(study, "boot_id", lambda: "00000000-0000-0000-0000-000000000002")
    with pytest.raises(study.StudyError, match="terminal SDK receipt"):
        study.Controller(tmp_path, config, smoke=False, phase="calibration", study_id="receipt",
                         short_calibration=True)
    assert journal.is_file()
    assert study.read_json(current.path)["ledger"]["entries"][attempt["id"]]["status"] == "reserved"


def test_completed_agent_outputs_are_preserved_before_recovery(study, config, tmp_path):
    current = study.Controller(tmp_path, config, smoke=True, phase="first", study_id="preserve")
    cell = current.state["cells"][0]
    args = study.SimpleNamespace(config=str(current.runtime_config), suite=str(ROOT / "suites/s1-retrofit"),
                                 arm=cell["arm"], run_id=cell["run_id"], phase="dry", features=1,
                                 no_cr=True, allow_draft=False)
    run = study.StudyRun(args, current, cell)
    run.setup()
    current.update(cell, checkpoint={"step": "f01-feature", "head": study.head(run.repo)})
    attempt = current.new_attempt(cell, "f01-feature")
    current.update(attempt, status="agent_returned")
    retained = Path(run.repo) / "retained-output.txt"
    retained.write_text("completed agent output", encoding="utf-8")
    with pytest.raises(study.StudyError, match="retained outputs will not be discarded"):
        current.run_cell(cell)
    assert retained.read_text(encoding="utf-8") == "completed agent output"


def test_short_calibration_metadata_survives_setup_and_resume(study, config, tmp_path):
    current = study.Controller(tmp_path, config, smoke=False, phase="calibration", study_id="short-metadata",
                               short_calibration=True)
    cell = current.state["cells"][0]
    args = study.SimpleNamespace(config=str(current.runtime_config), suite=str(ROOT / "suites/s1-retrofit"),
                                 arm=cell["arm"], run_id=cell["run_id"], phase="calibration", features=1,
                                 no_cr=True, allow_draft=False, assigned_model=cell["assigned_model"],
                                 analysis_design=cell["analysis_design"], replicate=cell["replicate"])
    run = study.StudyRun(args, current, cell)
    run.setup()
    assert study.read_json(Path(run.dir) / "run.json")["calibration_plan"] == "one-feature-per-model-arm"
    resumed = study.Controller(tmp_path, config, smoke=False, phase="calibration", study_id="short-metadata",
                               short_calibration=True)
    assert resumed.state["identity"]["calibration_plan"] == "one-feature-per-model-arm"


def test_unregistered_source_gate_is_explicit_and_exact(study, config):
    manifest = unregistered_manifest(study)
    assert study.freeze_errors(config, unregistered=manifest) == []
    for changed in (
        dict(manifest, registration_status="registered"),
        dict(manifest, owner_confirms_public_disclosure=False),
        dict(manifest, commit="0" * 40),
        dict(manifest, public_disclosure_url="https://example.com/"),
        dict(manifest, disclosed_at="not a timestamp"),
        dict(manifest, inputs_sha256="0" * 64),
        dict(manifest, budget_calibration=""),
    ):
        assert study.freeze_errors(config, unregistered=changed)


def test_unregistered_estimation_defaults_to_selected_21_and_keeps_resume_identity(study, tmp_path):
    args = study.SimpleNamespace(smoke=False, phase="pilot-estimation", replicates=None, dry_run=True,
                                 check_vm=False, unregistered_manifest=Path("/private/owner.json"))
    assert study.launch_replicates(args, tmp_path) == 21
    args.unregistered_manifest = None
    assert study.launch_replicates(args, tmp_path) == 12


@pytest.mark.parametrize("phase", ["pilot", "calibration"])
def test_unregistered_long_calibration_fails_closed(study, tmp_path, monkeypatch, capsys, phase):
    manifest = tmp_path / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(study, "preflight", lambda *args, **kwargs: [])
    monkeypatch.setattr(sys, "argv", ["study.py", "--dry-run", "--phase", phase,
                                      "--unregistered-manifest", str(manifest)])
    assert study.main() == 2
    preview = json.loads(capsys.readouterr().out)
    assert any("short calibration plan" in error for error in preview["errors"])


def test_short_calibration_handoff_counts_known_spend_and_restart_holds(study, config, tmp_path):
    manifest = unregistered_manifest(study)
    directory = tmp_path / "short-calibration"
    current = study.Controller(directory, config, smoke=False, phase="calibration",
                               study_id=directory.name, short_calibration=True, unregistered=manifest)
    restart_done = False
    for cell in current.state["cells"]:
        steps = ["f01-feature"]
        if study.POST_KINDS[cell["arm"]] is not None:
            steps.append(f"f01-{study.POST_KINDS[cell['arm']]}")
        records = []
        for step in steps:
            if not restart_done and cell["arm"] == "A":
                interrupted = current.new_attempt(cell, step)
                interrupted.update(status="restart_interrupted", cost_included_in_step=True,
                                   interrupted_boot_id="before", recovered_boot_id="after")
                current.state["ledger"]["entries"][interrupted["id"]]["status"] = "restart_hold"
                current.state["restart_history"].append(
                    {"previous_boot_id": "before", "boot_id": "after",
                     "interrupted_attempts": [interrupted["id"]]})
                restart_done = True
            attempt = current.new_attempt(cell, step)
            usage = {"credits_complete": True, "totalNanoAiu": study.NANO}
            attempt.update(status="agent_returned", usage=usage, cost_included_in_step=True)
            current.settle_attempt(attempt["id"], usage)
            records.append({"step": step, "attempts": [
                item["id"] for item in cell["attempts"] if item["step"] == step]})
        cell["status"] = "completed"
        journal = directory / "runs" / cell["run_id"] / "steps.jsonl"
        journal.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    current.state["status"] = "completed"
    current.save()
    handoff = study.calibration_handoff(directory, config, manifest)
    assert handoff["known_nano"] == 24 * study.NANO
    assert handoff["held_nano"] == 300 * study.NANO
    ledger = {"ceiling_nano": 325 * study.NANO, "prior_nano": 0, "entries": {},
              "calibration_handoff": handoff}
    study.reserve(ledger, "last-credit", study.NANO)
    with pytest.raises(study.StudyError, match="ceiling"):
        study.reserve(ledger, "over", 1)
    current.state["ledger"]["entries"][attempt["id"]]["status"] = "unknown"
    current.save()
    with pytest.raises(study.StudyError, match="Unresolved calibration accounting"):
        study.calibration_handoff(directory, config, manifest)
