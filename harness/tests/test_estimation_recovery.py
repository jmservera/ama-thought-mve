"""Offline tests for the narrowly scoped, explicitly authorized incident recovery."""
import hashlib
import importlib
import json
import shutil
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def incident(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "harness"))
    study = importlib.import_module("study")
    recovery = importlib.import_module("prepare_estimation_recovery")
    cfg = dict(study.read_json(ROOT / "harness/study-config.json"),
               prior_credits=14.54324, historical_credit_provisions=[])
    old_commit, new_commit = "a" * 40, "b" * 40
    old = {"commit": old_commit, "inputs_sha256": "1" * 64, "registration_status": "unregistered",
           "public_disclosure_url": f"https://github.com/jmservera/ama-thought-mve/commit/{old_commit}",
           "disclosed_at": "2026-01-01T00:00:00Z"}
    new = {"commit": new_commit, "inputs_sha256": "2" * 64, "registration_status": "unregistered",
           "public_disclosure_url": f"https://github.com/jmservera/ama-thought-mve/commit/{new_commit}",
           "disclosed_at": "2026-01-01T00:00:00Z"}
    source_root, target_root = tmp_path / "old", tmp_path / "new"
    source = source_root / ".study/pilot-estimation"
    calibration = source_root / ".study/excluded-short-calibration-toolfix"
    calibration.mkdir(parents=True)
    (calibration / "controller.lock").touch()
    paid = source_root / ".study/.paid-study-controller"
    paid.mkdir()
    (paid / "controller.lock").touch()
    target_root.mkdir()
    shutil.copytree(ROOT / "protocol", target_root / "protocol")
    (target_root / "harness").mkdir()
    shutil.copy(ROOT / "harness/config.json", target_root / "harness/config.json")
    handoff = {"study_id": calibration.name, "known_nano": study.credits("219.92594"),
               "held_nano": 0, "entries": [], "state_sha256": "c" * 64}
    controller = study.Controller(source, cfg, smoke=False, phase="pilot-estimation",
                                  study_id=source.name, replicates=21, unregistered=old, handoff=handoff)
    (source / "controller.lock").touch()
    state = controller.state
    state["identity"]["commit"] = old_commit
    state["identity"]["inputs_sha256"] = old["inputs_sha256"]
    state.update(status="oracle_halt", oracle_halt=True, stop_requested=False)
    total = study.credits("7794.8031")
    quotient, remainder = divmod(total, 651)
    for index in range(651):
        cell = state["cells"][index // 3]
        cell["completed_steps"] = cell.get("completed_steps", 0) + 1
        amount = quotient + (index < remainder)
        name = f"synthetic-{index}"
        cell["attempts"].append({"id": name, "step": f"step-{index}", "status": "agent_returned",
                                 "usage": {"credits_complete": True, "totalNanoAiu": amount},
                                 "seconds": 1})
        state["ledger"]["entries"][name] = {
            "status": "complete", "reserved_nano": 300 * study.NANO, "actual_nano": amount}
    failed_cell = state["cells"][-1]
    attempt = {"id": study.RECOVERY_ATTEMPT, "step": "f03-repair", "status": "interrupted",
               "usage": None, "started": 1767225600, "seconds": 41.5,
               "directory": "runs/failed/attempts/one"}
    failed_cell["attempts"].append(attempt)
    failed_cell["checkpoint"] = {"step": "f03-repair", "head": "checkpoint"}
    state["ledger"]["entries"][attempt["id"]] = {
        "status": "unknown", "reserved_nano": 300 * study.NANO, "actual_nano": None}
    journal = source / attempt["directory"] / "transport/events.jsonl"
    journal.parent.mkdir(parents=True)
    records = [
        {"type": "event", "event": {"type": "tool.execution_start", "data": {
            "toolName": "edit", "toolCallId": "id"}}},
        {"type": "event", "event": {"type": "tool.execution_complete", "data": {
            "toolCallId": "id", "success": False,
            "error": {"code": "failure", "message": "Tool 'edit' does not exist."}}}},
        {"type": "complete", "exit_code": 1, "receipt": {
            "protocol_error": "unexpected_tool", "failure_stage": "session_send",
            "usage": {"credits_complete": False, "totalNanoAiu": None}}},
    ]
    journal.write_text("".join(json.dumps(record) + "\n" for record in records))
    controller.save()
    original = (source / "state.json").read_bytes()
    monkeypatch.setattr(study, "RECOVERY_STATE_SHA256", hashlib.sha256(original).hexdigest())
    monkeypatch.setattr(study, "RECOVERY_SOURCE", old_commit)
    monkeypatch.setattr(study, "RECOVERY_JOURNAL_SHA256", hashlib.sha256(journal.read_bytes()).hexdigest())
    monkeypatch.setattr(study, "ROOT", target_root)
    monkeypatch.setattr(recovery, "ROOT", target_root)
    monkeypatch.setattr(study, "fingerprint", lambda *args: new["inputs_sha256"])
    monkeypatch.setattr(study, "command", lambda args, **kwargs: (
        old_commit if kwargs.get("cwd") == source_root else new_commit))
    monkeypatch.setattr(study, "preflight", lambda *args, **kwargs: [])
    monkeypatch.setattr(study, "calibration_handoff", lambda *args: handoff)
    approval = {"schema": "estimation-incident-approval/v1",
                "original_state_sha256": study.RECOVERY_STATE_SHA256, "original_commit": old_commit,
                "target_commit": new_commit, "attempt_id": study.RECOVERY_ATTEMPT,
                "unknown_reservation_nano": 300 * study.NANO, "accept_unknown_hold": True,
                "accept_fresh_retry_reservation": True, "accept_fresh_retry_time_allowance": True,
                "accept_mid_study_source_change": True,
                "owner_approved": True, "approved_at": "2026-01-02T00:00:00Z",
                "disclosure_url": new["public_disclosure_url"]}
    return study, recovery, cfg, source_root, source, target_root, old, new, approval, handoff, original


def test_authorized_copy_preserves_original_and_accounts_for_fresh_retry(incident):
    study, recovery, cfg, source_root, source, root, old, new, approval, handoff, original = incident
    target = recovery.prepare(source_root, old, new, approval)
    assert (source / "state.json").read_bytes() == original
    assert (target / "state.before-recovery.json").read_bytes() == original
    state = study.read_json(target / "state.json")
    entry = state["ledger"]["entries"][study.RECOVERY_ATTEMPT]
    assert entry == {"status": "recovery_hold", "actual_nano": None, "reserved_nano": 300 * study.NANO}
    assert state["recovery"]["original_commit"] == old["commit"]
    assert state["recovery"]["target_commit"] == new["commit"]
    assert sum(cell.get("completed_steps", 0) for cell in state["cells"]) == 651
    controller = study.Controller(target, cfg, smoke=False, phase="pilot-estimation",
                                  study_id="pilot-estimation", replicates=21,
                                  unregistered=new, handoff=handoff)
    cell = next(cell for cell in controller.state["cells"]
                if any(item["id"] == study.RECOVERY_ATTEMPT for item in cell["attempts"]))
    run = object.__new__(study.StudyRun)
    run.controller, run.cell, run.arm, run.current_step = controller, cell, cell["arm"], "f03-repair"
    assert run.remaining_allowance(900) == (900, 270 * study.NANO)
    retry = controller.new_attempt(cell, "f03-repair")
    assert retry["id"].endswith("-2") and retry["source_commit"] == new["commit"]
    assert controller.state["ledger"]["entries"][retry["id"]]["reserved_nano"] == 300 * study.NANO
    assert controller.state["ledger"]["entries"][study.RECOVERY_ATTEMPT]["actual_nano"] is None
    ledger = controller.state["ledger"]
    used = (ledger["prior_nano"] + handoff["known_nano"] + handoff["held_nano"]
            + sum(item["reserved_nano"] for item in ledger["historical_credit_provisions"])
            + sum(item["actual_nano"] if item["status"] == "complete" else item["reserved_nano"]
                  for item in ledger["entries"].values()))
    ledger["ceiling_nano"] = used + 299 * study.NANO
    with pytest.raises(study.StudyError, match="ceiling"):
        study.reserve(ledger, "no-free-hold", 300 * study.NANO)


@pytest.mark.parametrize("field", ["owner_approved", "accept_unknown_hold",
                                   "accept_fresh_retry_reservation", "accept_fresh_retry_time_allowance",
                                   "accept_mid_study_source_change"])
def test_recovery_requires_each_explicit_approval(incident, field):
    _, recovery, _, source_root, source, root, old, new, approval, _, original = incident
    approval[field] = False
    with pytest.raises(recovery.StudyError, match="explicitly authorize"):
        recovery.prepare(source_root, old, new, approval)
    assert (source / "state.json").read_bytes() == original
    assert not (root / ".study/pilot-estimation").exists()


def test_unbound_recovery_hold_never_opens_admission(incident):
    study, _, _, _, _, _, _, _, _, _, _ = incident
    state = {"ledger": {"entries": {study.RECOVERY_ATTEMPT: {
        "status": "recovery_hold", "actual_nano": None, "reserved_nano": 300 * study.NANO}}},
        "cells": []}
    with pytest.raises(study.StudyError, match="authorization"):
        study.validate_recovery_state(state)


@pytest.mark.parametrize("damage", ["state", "approval", "journal"])
def test_changed_recovery_evidence_blocks_resume(incident, damage):
    study, recovery, cfg, source_root, _, _, old, new, approval, handoff, _ = incident
    target = recovery.prepare(source_root, old, new, approval)
    if damage == "state":
        path = target / "state.before-recovery.json"
    elif damage == "approval":
        path = target / "recovery-approval.json"
    else:
        path = target / "runs/failed/attempts/one/transport/events.jsonl"
    if damage == "approval":
        value = json.loads(path.read_text())
        value["owner_approved"] = False
        path.write_text(json.dumps(value))
    else:
        with path.open("ab") as stream:
            stream.write(b" ")
    with pytest.raises((study.StudyError, ValueError)):
        study.Controller(target, cfg, smoke=False, phase="pilot-estimation", study_id="pilot-estimation",
                         replicates=21, unregistered=new, handoff=handoff)


def test_links_are_rejected_without_touching_original(incident):
    _, recovery, _, source_root, source, root, old, new, approval, _, original = incident
    (source / "unexpected-link").symlink_to("/tmp")
    with pytest.raises(recovery.StudyError, match="links or special files"):
        recovery.prepare(source_root, old, new, approval)
    assert (source / "state.json").read_bytes() == original
    assert not (root / ".study/pilot-estimation").exists()


def test_approval_cannot_predate_the_interrupted_attempt(incident):
    _, recovery, _, source_root, source, root, old, new, approval, _, original = incident
    approval["approved_at"] = "2026-01-01T00:00:00Z"
    with pytest.raises(recovery.StudyError, match="follow the interrupted attempt"):
        recovery.prepare(source_root, old, new, approval)
    assert (source / "state.json").read_bytes() == original
    assert not (root / ".study/pilot-estimation").exists()


def test_inaccessible_tree_is_not_silently_skipped(incident, monkeypatch):
    _, recovery, _, _, source, _, _, _, _, _, _ = incident

    def failed_walk(root, *, followlinks, onerror):
        onerror(PermissionError("synthetic"))
        yield root, [], []

    monkeypatch.setattr(recovery.os, "walk", failed_walk)
    with pytest.raises(recovery.StudyError, match="complete recovery tree"):
        recovery.require_regular_tree(source)


def test_original_source_and_prior_calibration_are_required(incident, tmp_path):
    study, recovery, _, source_root, source, _, old, new, approval, _, original = incident
    target = recovery.prepare(source_root, old, new, approval)
    old_path = tmp_path / "old-manifest.json"
    old_path.write_text(json.dumps(old))
    assert study.recovery_calibration_manifest(target, old_path, new) == old
    paid_lock, original_lock = study.recovery_source_paths(source_root)
    with study.study_lock(paid_lock), pytest.raises(study.StudyError, match="Another controller"):
        with study.study_lock(paid_lock):
            pytest.fail("A second paid controller acquired the original lock")
    assert original_lock == source
    old["inputs_sha256"] = "changed"
    old_path.write_text(json.dumps(old))
    with pytest.raises(study.StudyError, match="differs from the original"):
        study.recovery_calibration_manifest(target, old_path, new)
    (source / "state.json").write_bytes(original + b" ")
    with pytest.raises(study.StudyError, match="unavailable or changed"):
        study.recovery_source_paths(source_root)


def test_unrelated_original_attempt_cannot_be_modified(incident):
    study, recovery, cfg, source_root, _, _, old, new, approval, handoff, _ = incident
    target = recovery.prepare(source_root, old, new, approval)
    state = study.read_json(target / "state.json")
    first = state["cells"][0]["attempts"][0]
    state["ledger"]["entries"][first["id"]]["actual_nano"] += 1
    study.atomic_json(target / "state.json", state)
    with pytest.raises(study.StudyError, match="changed an original attempt or ledger"):
        study.Controller(target, cfg, smoke=False, phase="pilot-estimation", study_id="pilot-estimation",
                         replicates=21, unregistered=new, handoff=handoff)


@pytest.mark.parametrize("damage", ["transition", "new-manifest"])
def test_source_transition_and_manifest_are_bound_to_approval(incident, damage):
    study, recovery, cfg, source_root, _, _, old, new, approval, handoff, _ = incident
    target = recovery.prepare(source_root, old, new, approval)
    if damage == "transition":
        state = study.read_json(target / "state.json")
        state["recovery"]["approved_at"] = "2026-01-01T00:00:00Z"
        study.atomic_json(target / "state.json", state)
    else:
        new["disclosed_at"] = "2026-01-01T01:00:00Z"
    with pytest.raises(study.StudyError, match="authorization|Resume inputs"):
        study.Controller(target, cfg, smoke=False, phase="pilot-estimation", study_id="pilot-estimation",
                         replicates=21, unregistered=new, handoff=handoff)


def test_recovery_dry_run_requires_original_source_and_calibration(incident, tmp_path, monkeypatch, capsys):
    study, recovery, cfg, source_root, _, _, old, new, approval, handoff, _ = incident
    recovery.prepare(source_root, old, new, approval)
    cfg_path, old_path, new_path = (tmp_path / name for name in ("config.json", "old.json", "new.json"))
    cfg_path.write_text(json.dumps(cfg))
    old_path.write_text(json.dumps(old))
    new_path.write_text(json.dumps(new))
    base = ["study.py", "--dry-run", "--study-id", "pilot-estimation", "--config", str(cfg_path),
            "--unregistered-manifest", str(new_path), "--calibration-study-id", handoff["study_id"]]
    monkeypatch.setattr(sys, "argv", base)
    with pytest.raises(study.StudyError, match="original checkout"):
        study.main()
    monkeypatch.setattr(sys, "argv", base + ["--recovery-source-root", str(source_root)])
    with pytest.raises(study.StudyError, match="original calibration manifest"):
        study.main()
    monkeypatch.setattr(sys, "argv", base + ["--recovery-source-root", str(source_root),
                                             "--recovery-calibration-manifest", str(old_path)])
    assert study.main() == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["calibration_handoff"] == handoff and preview["errors"] == []
