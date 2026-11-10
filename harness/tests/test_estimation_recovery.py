"""Offline tests for the narrowly scoped, explicitly authorized incident recovery."""
import csv
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


@pytest.fixture
def backend_incident(incident, tmp_path, monkeypatch):
    study, recovery, cfg, prior_root, prior, middle_root, first_manifest, middle_manifest, first_approval, handoff, first_original = incident
    middle = recovery.prepare(prior_root, first_manifest, middle_manifest, first_approval)
    state = study.read_json(middle / "state.json")
    extra_nano = study.credits("10470.87094") - study.credits("7794.8031")
    quotient, remainder = divmod(extra_nano, 227)
    for index in range(227):
        cell = state["cells"][index % len(state["cells"])]
        amount = quotient + (index < remainder)
        identity = f"backend-complete-{index}"
        cell["completed_steps"] = cell.get("completed_steps", 0) + 1
        cell["attempts"].append({"id": identity, "step": f"backend-step-{index}",
                                 "status": "agent_returned", "source_commit": middle_manifest["commit"],
                                 "usage": {"credits_complete": True, "totalNanoAiu": amount}, "seconds": 1})
        state["ledger"]["entries"][identity] = {
            "status": "complete", "reserved_nano": 300 * study.NANO, "actual_nano": amount}
    cell = next(cell for cell in state["cells"] if cell["assigned_model"] == "gpt-6.1-sol"
                and cell["arm"] == "E" and cell["replicate"] == 4)
    failed = {"id": study.BACKEND_RECOVERY_ATTEMPT, "step": "f08-feature", "status": "interrupted",
              "source_commit": middle_manifest["commit"], "usage": None,
              "started": 1767398400, "seconds": 49.6077,
              "directory": "runs/backend-failed/attempts/one"}
    cell["attempts"].append(failed)
    cell["checkpoint"] = {"step": failed["step"], "head": "checkpoint"}
    state["ledger"]["entries"][failed["id"]] = {
        "status": "unknown", "reserved_nano": 300 * study.NANO, "actual_nano": None}
    state.update(status="oracle_halt", oracle_halt=True, stop_requested=False)
    journal = middle / failed["directory"] / "transport/events.jsonl"
    journal.parent.mkdir(parents=True)
    failure = {"model": "gpt-6.1-sol", "reasoningEffort": "medium", "statusCode": 500,
               "failureKind": "api", "transport": "websocket", "errorCode": "internal_error",
               "errorType": "websocket_error", "retryAttempt": 0, "isAuto": False, "isByok": False,
               "apiCallId": "failed-api", "serviceRequestId": "failed-service"}
    mirror = {"turn": 2, "reasoningEffort": "medium", "modelCall": {
        "model": "gpt-6.1-sol", "status": 500, "api_id": "failed-api",
        "service_request_id": "failed-service", "transport": "websocket",
        "errorCode": "internal_error", "errorType": "websocket_error", "retry_attempt": 0}}
    records = [
        {"event": {"type": "model.call_start", "data": {"model": "gpt-6.1-sol", "turnId": "2"}}},
        {"event": {"type": "model.call_failure", "data": failure}},
        {"event": {"type": "model.model_call_failure", "data": mirror}},
        {"event": {"type": "model.call_finished", "data": {"turnId": "2", "outcome": "error"}}},
        {"type": "complete", "exit_code": 1, "receipt": {
            "protocol_error": "unexpected_runtime_activity", "failure_stage": "session_send",
            "usage": {"credits_complete": False, "totalNanoAiu": None}}},
    ]
    journal.write_text("".join(json.dumps(record) + "\n" for record in records))
    study.atomic_json(middle / "state.json", state)
    original = (middle / "state.json").read_bytes()
    new_root = tmp_path / "backend-new"
    new_root.mkdir()
    shutil.copytree(middle_root / "protocol", new_root / "protocol")
    shutil.copytree(middle_root / "harness", new_root / "harness")
    new_commit = "d" * 40
    new = {"commit": new_commit, "inputs_sha256": "3" * 64, "registration_status": "unregistered",
           "public_disclosure_url": f"https://github.com/jmservera/ama-thought-mve/commit/{new_commit}",
           "disclosed_at": "2026-01-03T00:00:00Z"}
    monkeypatch.setattr(study, "BACKEND_RECOVERY_SOURCE", middle_manifest["commit"])
    monkeypatch.setattr(study, "BACKEND_RECOVERY_STATE_SHA256", hashlib.sha256(original).hexdigest())
    monkeypatch.setattr(study, "BACKEND_RECOVERY_JOURNAL_SHA256", hashlib.sha256(journal.read_bytes()).hexdigest())
    monkeypatch.setattr(study, "ROOT", new_root)
    monkeypatch.setattr(recovery, "ROOT", new_root)
    monkeypatch.setattr(study, "fingerprint", lambda *args: new["inputs_sha256"])
    commits = {prior_root: first_manifest["commit"], middle_root: middle_manifest["commit"]}
    monkeypatch.setattr(study, "command", lambda args, **kwargs: commits.get(kwargs.get("cwd"), new_commit))
    approval = {**first_approval, "original_state_sha256": study.BACKEND_RECOVERY_STATE_SHA256,
                "original_commit": middle_manifest["commit"], "target_commit": new_commit,
                "attempt_id": study.BACKEND_RECOVERY_ATTEMPT, "approved_at": "2026-01-04T00:00:00Z",
                "disclosure_url": new["public_disclosure_url"]}
    return {"study": study, "recovery": recovery, "config": cfg, "source_root": middle_root,
            "source": middle, "prior_root": prior_root, "prior": prior, "target_root": new_root,
            "old": middle_manifest, "new": new, "calibration_manifest": first_manifest,
            "approval": approval, "handoff": handoff, "original": original,
            "first_original": first_original, "journal": journal, "failed": failed}


def prepare_backend_incident(case):
    return case["recovery"].prepare(case["source_root"], case["old"], case["new"], case["approval"],
                                    prior_source_root=case["prior_root"],
                                    calibration_manifest=case["calibration_manifest"])


def test_backend_copy_retains_both_holds_all_sources_and_a_fresh_retry(backend_incident, tmp_path):
    case = backend_incident
    study = case["study"]
    target = prepare_backend_incident(case)
    assert (case["source"] / "state.json").read_bytes() == case["original"]
    assert (case["prior"] / "state.json").read_bytes() == case["first_original"]
    assert (target / "state.before-recovery.json").read_bytes() == case["original"]
    assert (target / "state.before-recovery-01.json").read_bytes() == case["first_original"]
    state = study.read_json(target / "state.json")
    assert len(study.recovery_records(state)) == 2
    assert sum(cell.get("completed_steps", 0) for cell in state["cells"]) == 878
    assert len(state["ledger"]["entries"]) == 880
    for identity in (study.RECOVERY_ATTEMPT, study.BACKEND_RECOVERY_ATTEMPT):
        assert state["ledger"]["entries"][identity] == {
            "status": "recovery_hold", "reserved_nano": 300 * study.NANO, "actual_nano": None}
    assert study.read_json(target / "recovery-manifest-01.json") == case["old"]
    calibration_path = tmp_path / "first-manifest.json"
    calibration_path.write_text(json.dumps(case["calibration_manifest"]))
    assert study.recovery_calibration_manifest(target, calibration_path, case["new"]) == case["calibration_manifest"]
    controller = study.Controller(target, case["config"], smoke=False, phase="pilot-estimation",
                                  study_id="pilot-estimation", replicates=21,
                                  unregistered=case["new"], handoff=case["handoff"])
    cell = next(cell for cell in controller.state["cells"]
                if any(attempt["id"] == study.BACKEND_RECOVERY_ATTEMPT for attempt in cell["attempts"]))
    run = object.__new__(study.StudyRun)
    run.controller, run.cell, run.arm, run.current_step = controller, cell, cell["arm"], "f08-feature"
    assert run.remaining_allowance(1800) == (1800, 270 * study.NANO)
    retry = controller.new_attempt(cell, "f08-feature")
    assert retry["id"].endswith("-2") and retry["source_commit"] == case["new"]["commit"]
    assert controller.state["ledger"]["entries"][retry["id"]]["reserved_nano"] == 300 * study.NANO
    study.validate_recovery_state(controller.state)
    study.validate_recovery_evidence(target, controller.state, case["new"])


@pytest.mark.parametrize("damage", ["approval", "old-approval", "old-manifest", "old-snapshot",
                                   "snapshot", "journal", "prior-entry", "new-entry",
                                   "attempt-source", "history"])
def test_backend_recovery_rejects_changes_to_either_incident(backend_incident, damage):
    case = backend_incident
    study = case["study"]
    target = prepare_backend_incident(case)
    paths = {"approval": "recovery-approval.json", "old-approval": "recovery-approval-01.json",
             "old-manifest": "recovery-manifest-01.json", "old-snapshot": "state.before-recovery-01.json",
             "snapshot": "state.before-recovery.json",
             "journal": case["failed"]["directory"] + "/transport/events.jsonl"}
    if damage in paths:
        path = target / paths[damage]
        if "approval" in damage:
            value = study.read_json(path)
            value["owner_approved"] = False
            path.write_text(json.dumps(value))
        elif damage == "old-manifest":
            value = study.read_json(path)
            value["inputs_sha256"] = "changed"
            path.write_text(json.dumps(value))
        else:
            with path.open("ab") as stream:
                stream.write(b" ")
    else:
        state = study.read_json(target / "state.json")
        if damage == "prior-entry":
            state["ledger"]["entries"][study.RECOVERY_ATTEMPT]["reserved_nano"] = 0
        elif damage == "new-entry":
            state["ledger"]["entries"][study.BACKEND_RECOVERY_ATTEMPT]["actual_nano"] = 0
        elif damage == "attempt-source":
            state["cells"][0]["attempts"][0]["source_commit"] = case["new"]["commit"]
        else:
            state["recovery_history"][0]["target_commit"] = "f" * 40
        study.atomic_json(target / "state.json", state)
    with pytest.raises((study.StudyError, ValueError)):
        study.Controller(target, case["config"], smoke=False, phase="pilot-estimation",
                         study_id="pilot-estimation", replicates=21,
                         unregistered=case["new"], handoff=case["handoff"])
    assert (case["source"] / "state.json").read_bytes() == case["original"]
    assert (case["prior"] / "state.json").read_bytes() == case["first_original"]


@pytest.mark.parametrize("field", ["owner_approved", "accept_unknown_hold", "accept_fresh_retry_reservation",
                                  "accept_fresh_retry_time_allowance", "accept_mid_study_source_change"])
def test_backend_incident_requires_new_explicit_owner_approval(backend_incident, field):
    case = backend_incident
    case["approval"][field] = False
    with pytest.raises(case["study"].StudyError, match="explicitly authorize"):
        prepare_backend_incident(case)
    assert (case["source"] / "state.json").read_bytes() == case["original"]
    assert not (case["target_root"] / ".study/pilot-estimation").exists()


def test_backend_preparation_requires_first_original_and_its_calibration_manifest(backend_incident):
    case = backend_incident
    study, recovery = case["study"], case["recovery"]
    with pytest.raises(study.StudyError, match="first original"):
        recovery.prepare(case["source_root"], case["old"], case["new"], case["approval"])
    with pytest.raises(study.StudyError, match="Calibration manifest differs"):
        recovery.prepare(case["source_root"], case["old"], case["new"], case["approval"],
                         prior_source_root=case["prior_root"], calibration_manifest=case["old"])
    with study.study_lock(case["prior_root"] / ".study/.paid-study-controller"), pytest.raises(
            study.StudyError, match="Another controller"):
        prepare_backend_incident(case)
    assert (case["source"] / "state.json").read_bytes() == case["original"]
    assert not (case["target_root"] / ".study/pilot-estimation").exists()


@pytest.mark.parametrize("damage", ["status", "model", "routing", "mirror", "finished", "duplicate"])
def test_backend_journal_requires_the_exact_correlated_500(backend_incident, monkeypatch, damage):
    case = backend_incident
    records = [json.loads(line) for line in case["journal"].read_bytes().splitlines()]
    if damage == "status":
        records[1]["event"]["data"]["statusCode"] = 429
        records[2]["event"]["data"]["modelCall"]["status"] = 429
    elif damage == "model":
        records[1]["event"]["data"]["model"] = "other"
    elif damage == "routing":
        records[1]["event"]["data"]["isAuto"] = True
    elif damage == "mirror":
        records[2]["event"]["data"]["modelCall"]["service_request_id"] = "other"
    elif damage == "finished":
        records[3]["event"]["data"]["outcome"] = "success"
    else:
        records.append(records[1])
    case["journal"].write_text("".join(json.dumps(record) + "\n" for record in records))
    monkeypatch.setattr(case["study"], "BACKEND_RECOVERY_JOURNAL_SHA256",
                        hashlib.sha256(case["journal"].read_bytes()).hexdigest())
    with pytest.raises(case["study"].StudyError, match="backend"):
        case["recovery"].verify_journal(case["source"], case["failed"])


def test_backend_dry_run_requires_both_original_checkouts_in_order(backend_incident, tmp_path, monkeypatch, capsys):
    case = backend_incident
    study = case["study"]
    prepare_backend_incident(case)
    paths = {}
    for key in ("config", "new", "calibration_manifest"):
        paths[key] = tmp_path / f"{key}.json"
        paths[key].write_text(json.dumps(case[key]))
    base = ["study.py", "--dry-run", "--study-id", "pilot-estimation", "--config", str(paths["config"]),
            "--unregistered-manifest", str(paths["new"]), "--calibration-study-id", case["handoff"]["study_id"],
            "--recovery-calibration-manifest", str(paths["calibration_manifest"])]
    monkeypatch.setattr(sys, "argv", base + ["--recovery-source-root", str(case["source_root"])])
    with pytest.raises(study.StudyError, match="every original checkout"):
        study.main()
    monkeypatch.setattr(sys, "argv", base + ["--recovery-source-root", str(case["source_root"]),
                                             "--recovery-source-root", str(case["prior_root"])])
    with pytest.raises(study.StudyError, match="unavailable or changed"):
        study.main()
    monkeypatch.setattr(sys, "argv", base + ["--recovery-source-root", str(case["prior_root"]),
                                             "--recovery-source-root", str(case["source_root"])])
    assert study.main() == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["calibration_handoff"] == case["handoff"] and preview["errors"] == []
    assert (case["source"] / "state.json").read_bytes() == case["original"]


def test_backend_reports_preserve_both_transitions_and_per_attempt_sources(backend_incident):
    case = backend_incident
    target = prepare_backend_incident(case)
    report = importlib.import_module("study_report")
    state = case["study"].read_json(target / "state.json")
    report.export(target, state, "pilot-estimation")
    provenance = case["study"].read_json(target / "results/provenance.json")
    assert provenance["source_transition"]["original_commit"] == case["old"]["commit"]
    assert provenance["source_transition"]["target_commit"] == case["new"]["commit"]
    assert provenance["source_transition_history"][0]["original_commit"] == case["calibration_manifest"]["commit"]
    assert provenance["source_transition_history"][0]["target_commit"] == case["old"]["commit"]
    with (target / "results/attempts.csv").open(newline="") as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 880
    assert sum(row["source_commit"] == case["calibration_manifest"]["commit"] for row in rows) == 652
    assert sum(row["source_commit"] == case["old"]["commit"] for row in rows) == 228
    assert sum(row["credits_status"] == "recovery_hold" and row["actual_nano"] == "" for row in rows) == 2
    assert report.package_results(target / "results", "pilot-estimation").is_file()


@pytest.fixture
def sandbox_incident(backend_incident, tmp_path, monkeypatch):
    case = backend_incident
    study, recovery = case["study"], case["recovery"]
    source = prepare_backend_incident(case)
    source_root = case["target_root"]
    state = study.read_json(source / "state.json")
    extra = study.credits("16961.29357") - study.credits("10470.87094")
    quotient, remainder = divmod(extra, 604)
    for index in range(604):
        cell = state["cells"][index % len(state["cells"])]
        identity = f"sandbox-complete-{index}"
        amount = quotient + (index < remainder)
        cell["completed_steps"] = cell.get("completed_steps", 0) + 1
        cell["attempts"].append({"id": identity, "step": f"sandbox-step-{index}",
                                 "status": "agent_returned", "seconds": 1,
                                 "source_commit": case["new"]["commit"],
                                 "usage": {"credits_complete": True, "totalNanoAiu": amount}})
        state["ledger"]["entries"][identity] = {
            "status": "complete", "reserved_nano": 300 * study.NANO, "actual_nano": amount}
    cell = next(cell for cell in state["cells"] if cell["assigned_model"] == "gpt-6.1-sol"
                and cell["arm"] == "B" and cell["replicate"] == 6)
    identity = study.SANDBOX_RECOVERY_ATTEMPT
    directory = f"runs/{cell['run_id']}/attempts/{identity}"
    failed = {"id": identity, "step": "f02-consolidation", "status": "interrupted",
              "source_commit": case["new"]["commit"], "usage": None,
              "started": 1767571200, "seconds": 111.5681, "directory": directory}
    cell["attempts"].append(failed)
    cell["checkpoint"] = {"step": failed["step"], "head": "checkpoint"}
    state["ledger"]["entries"][identity] = {
        "status": "unknown", "reserved_nano": 300 * study.NANO, "actual_nano": None}
    state.update(status="oracle_halt", oracle_halt=True, stop_requested=False)
    journal = source / directory / "transport/events.jsonl"
    journal.parent.mkdir(parents=True)
    records = [
        {"event": {"type": "tool.execution_start", "data": {
            "toolName": "isolated_exec", "toolCallId": "final-tool"}}},
        {"type": "tool", "id": "final-tool", "arguments": {
            "command": "ln -s missing unsupported-link", "timeoutSeconds": 120}},
    ]
    journal.write_text("".join(json.dumps(record) + "\n" for record in records))
    broker = source / "runs" / cell["run_id"] / "isolation"
    broker.mkdir()
    (broker / "latest.state").write_bytes(b"synthetic retained opaque state")
    state_sha = hashlib.sha256((broker / "latest.state").read_bytes()).hexdigest()
    (broker / "state.json").write_text(json.dumps({
        "slot": "latest.state", "sha256": state_sha, "token": "original-token"}))
    (broker / "owner").write_text("c" * 32)
    study.atomic_json(source / "state.json", state)
    original = (source / "state.json").read_bytes()
    target_root = tmp_path / "sandbox-new"
    target_root.mkdir()
    shutil.copytree(source_root / "protocol", target_root / "protocol")
    shutil.copytree(source_root / "harness", target_root / "harness")
    new_commit = "e" * 40
    new = {"commit": new_commit, "inputs_sha256": "4" * 64, "registration_status": "unregistered",
           "public_disclosure_url": f"https://github.com/jmservera/ama-thought-mve/commit/{new_commit}",
           "disclosed_at": "2026-01-05T00:00:00Z"}
    monkeypatch.setattr(study, "SANDBOX_RECOVERY_SOURCE", case["new"]["commit"])
    monkeypatch.setattr(study, "SANDBOX_RECOVERY_STATE_SHA256", hashlib.sha256(original).hexdigest())
    monkeypatch.setattr(study, "SANDBOX_RECOVERY_JOURNAL_SHA256", hashlib.sha256(journal.read_bytes()).hexdigest())
    monkeypatch.setattr(study, "SANDBOX_RECOVERY_BROKER_METADATA_SHA256",
                        hashlib.sha256((broker / "state.json").read_bytes()).hexdigest())
    monkeypatch.setattr(study, "SANDBOX_RECOVERY_BROKER_STATE_SHA256", state_sha)
    monkeypatch.setattr(study, "SANDBOX_RECOVERY_BROKER_OWNER_SHA256",
                        hashlib.sha256((broker / "owner").read_bytes()).hexdigest())
    monkeypatch.setattr(study, "ROOT", target_root)
    monkeypatch.setattr(recovery, "ROOT", target_root)
    monkeypatch.setattr(study, "fingerprint", lambda *args: new["inputs_sha256"])
    prior_roots = [case["prior_root"], case["source_root"]]
    commits = {case["prior_root"]: case["calibration_manifest"]["commit"],
               case["source_root"]: case["old"]["commit"], source_root: case["new"]["commit"]}
    monkeypatch.setattr(study, "command", lambda args, **kwargs: commits.get(kwargs.get("cwd"), new_commit))
    approval = {**case["approval"], "original_state_sha256": study.SANDBOX_RECOVERY_STATE_SHA256,
                "original_commit": case["new"]["commit"], "target_commit": new_commit,
                "attempt_id": identity, "approved_at": "2026-01-06T00:00:00Z",
                "disclosure_url": new["public_disclosure_url"]}
    return {**case, "source_root": source_root, "source": source, "target_root": target_root,
            "old": case["new"], "new": new, "approval": approval, "original": original,
            "journal": journal, "failed": failed, "broker": broker, "prior_roots": prior_roots}


def prepare_sandbox_incident(case):
    return case["recovery"].prepare(case["source_root"], case["old"], case["new"], case["approval"],
                                    prior_source_root=case["prior_roots"],
                                    calibration_manifest=case["calibration_manifest"])


@pytest.mark.parametrize("damage", ["intact", "attempt-time", "attempt-source", "known-charge", "approval"])
def test_analysis_scope_accepts_only_authorized_sandbox_bookkeeping(sandbox_incident, damage):
    case = sandbox_incident
    target = prepare_sandbox_incident(case)
    analysis = importlib.import_module("analysis_adjudications")
    state = case["study"].read_json(target / "state.json")
    manifest = {"study_id": target.name, "execution_source_commit": case["new"]["commit"],
                "scope_state_sha256": hashlib.sha256(case["original"]).hexdigest(),
                "attribution_helper_sha256": analysis.current_helper_sha256()}
    attempt = next(item for cell in state["cells"] for item in cell["attempts"]
                   if item["id"] == case["failed"]["id"])
    attempt["cost_included_in_step"] = True
    if damage == "attempt-time":
        attempt["seconds"] += 1
    elif damage == "attempt-source":
        attempt["source_commit"] = case["new"]["commit"]
    elif damage == "known-charge":
        state["ledger"]["entries"][attempt["id"]]["actual_nano"] = 1
    elif damage == "approval":
        path = target / "recovery-approval.json"
        approval = case["study"].read_json(path)
        approval["owner_approved"] = False
        case["study"].atomic_json(path, approval)
    if damage == "intact":
        analysis.validate_trust_anchors(target, manifest, state)
    else:
        with pytest.raises(case["study"].StudyError):
            analysis.validate_trust_anchors(target, manifest, state)
    assert (case["source"] / "state.json").read_bytes() == case["original"]


def test_sandbox_copy_keeps_all_holds_history_and_immutable_broker_evidence(sandbox_incident):
    case = sandbox_incident
    study = case["study"]
    target = prepare_sandbox_incident(case)
    state = study.read_json(target / "state.json")
    assert len(study.recovery_records(state)) == 3
    assert len(state["ledger"]["entries"]) == 1485
    assert sum(cell.get("completed_steps", 0) for cell in state["cells"]) == 1482
    assert (case["source"] / "state.json").read_bytes() == case["original"]
    assert (target / "state.before-recovery.json").read_bytes() == case["original"]
    assert (target / "state.before-recovery-01.json").is_file()
    assert (target / "state.before-recovery-02.json").is_file()
    assert sum(entry["reserved_nano"] for entry in state["ledger"]["entries"].values()
               if entry["status"] == "recovery_hold") == 900 * study.NANO
    archive = target / case["failed"]["directory"] / "recovery-broker"
    for name in ("state.json", "latest.state", "owner"):
        assert (archive / name).read_bytes() == (case["broker"] / name).read_bytes()
    mutable = target / case["broker"].relative_to(case["source"])
    (mutable / "state.json").write_text("{}")
    (mutable / "latest.state").write_bytes(b"next runtime state")
    controller = study.Controller(target, case["config"], smoke=False, phase="pilot-estimation",
                                  study_id="pilot-estimation", replicates=21,
                                  unregistered=case["new"], handoff=case["handoff"])
    cell = next(cell for cell in controller.state["cells"]
                if any(a["id"] == study.SANDBOX_RECOVERY_ATTEMPT for a in cell["attempts"]))
    run = object.__new__(study.StudyRun)
    run.controller, run.cell, run.arm, run.current_step = controller, cell, cell["arm"], "f02-consolidation"
    assert run.remaining_allowance(900) == (900, 270 * study.NANO)
    retry = controller.new_attempt(cell, "f02-consolidation")
    assert retry["source_commit"] == case["new"]["commit"]
    assert controller.state["ledger"]["entries"][retry["id"]]["reserved_nano"] == 300 * study.NANO
    study.validate_recovery_evidence(target, controller.state, case["new"])


@pytest.mark.parametrize("damage", ["terminal", "tool-name", "completion", "broker", "owner", "container"])
def test_sandbox_recovery_requires_the_exact_incomplete_tool_and_preserved_state(sandbox_incident, damage):
    case = sandbox_incident
    if damage in ("terminal", "tool-name", "completion"):
        records = [json.loads(line) for line in case["journal"].read_bytes().splitlines()]
        if damage == "terminal":
            records.append({"type": "complete", "exit_code": 1})
        elif damage == "tool-name":
            records[0]["event"]["data"]["toolName"] = "create"
        else:
            records.insert(1, {"event": {"type": "tool.execution_complete", "data": {
                "toolCallId": "final-tool", "success": True}}})
        case["journal"].write_text("".join(json.dumps(record) + "\n" for record in records))
    elif damage == "broker":
        (case["broker"] / "latest.state").write_bytes(b"changed")
    elif damage == "owner":
        (case["broker"] / "owner").write_text("d" * 32)
    else:
        (case["broker"] / "container.json").write_text("{}")
    with pytest.raises(case["study"].StudyError):
        prepare_sandbox_incident(case)
    assert (case["source"] / "state.json").read_bytes() == case["original"]
    assert not (case["target_root"] / ".study/pilot-estimation").exists()


@pytest.mark.parametrize("damage", ["archive-state", "archive-metadata", "archive-owner", "older-approval"])
def test_sandbox_resume_never_falls_back_from_tampered_archival_evidence(sandbox_incident, damage):
    case = sandbox_incident
    target = prepare_sandbox_incident(case)
    archive = target / case["failed"]["directory"] / "recovery-broker"
    name = {"archive-state": archive / "latest.state", "archive-metadata": archive / "state.json",
            "archive-owner": archive / "owner", "older-approval": target / "recovery-approval-02.json"}[damage]
    name.unlink()
    with pytest.raises(case["study"].StudyError):
        case["study"].Controller(target, case["config"], smoke=False, phase="pilot-estimation",
                                 study_id="pilot-estimation", replicates=21,
                                 unregistered=case["new"], handoff=case["handoff"])


def test_sandbox_recovery_requires_all_three_source_roots_in_order(sandbox_incident):
    case = sandbox_incident
    target = prepare_sandbox_incident(case)
    state = case["study"].read_json(target / "state.json")
    roots = [*case["prior_roots"], case["source_root"]]
    assert len(case["study"].recovery_source_locks(state, roots)) == 6
    with pytest.raises(case["study"].StudyError, match="every original"):
        case["study"].recovery_source_locks(state, roots[1:])
    with pytest.raises(case["study"].StudyError, match="unavailable or changed"):
        case["study"].recovery_source_locks(state, list(reversed(roots)))


@pytest.fixture
def service_incident(sandbox_incident, tmp_path, monkeypatch):
    case = {**sandbox_incident, "new": {**sandbox_incident["new"], "runtime_image": "sha256:" + "d" * 64}}
    study, recovery = case["study"], case["recovery"]
    source = prepare_sandbox_incident(case)
    source_root = case["target_root"]
    state = study.read_json(source / "state.json")
    extra = study.credits("23969.42938") - study.credits("16961.29357")
    quotient, remainder = divmod(extra, 600)
    for index in range(600):
        cell = state["cells"][index % len(state["cells"])]
        identity = f"service-complete-{index}"
        amount = quotient + (index < remainder)
        cell["completed_steps"] = cell.get("completed_steps", 0) + 1
        cell["attempts"].append({"id": identity, "step": f"service-step-{index}",
                                 "status": "agent_returned", "seconds": 1,
                                 "source_commit": case["new"]["commit"],
                                 "usage": {"credits_complete": True, "totalNanoAiu": amount}})
        state["ledger"]["entries"][identity] = {
            "status": "complete", "reserved_nano": 300 * study.NANO, "actual_nano": amount}
    cell = next(cell for cell in state["cells"] if cell["assigned_model"] == "gpt-6.1-sol"
                and cell["arm"] == "A" and cell["replicate"] == 9)
    identity = study.SERVICE_RECOVERY_ATTEMPT
    directory = f"runs/{cell['run_id']}/attempts/{identity}"
    failed = {"id": identity, "step": "f02-feature", "status": "interrupted",
              "source_commit": case["new"]["commit"], "usage": None,
              "started": 1767744000, "seconds": 44.2488, "directory": directory}
    cell["attempts"].append(failed)
    cell["checkpoint"] = {"step": failed["step"], "head": "checkpoint"}
    state["ledger"]["entries"][identity] = {
        "status": "unknown", "reserved_nano": 300 * study.NANO, "actual_nano": None}
    state.update(status="oracle_halt", oracle_halt=True, stop_requested=False)
    failure = {"model": "gpt-6.1-sol", "reasoningEffort": "medium", "statusCode": 503,
               "failureKind": "api", "transport": "websocket", "errorCode": "service_unavailable",
               "errorType": "websocket_error", "retryAttempt": 0, "isAuto": False, "isByok": False,
               "apiCallId": "failed-api", "serviceRequestId": "failed-service"}
    records = [
        {"event": {"type": "model.call_start", "data": {"model": failure["model"], "turnId": "3"}}},
        {"event": {"type": "model.call_failure", "data": failure}},
        {"event": {"type": "model.model_call_failure", "data": {
            "turn": 3, "reasoningEffort": "medium", "modelCall": {
                "model": failure["model"], "status": 503, "api_id": failure["apiCallId"],
                "service_request_id": failure["serviceRequestId"], "transport": "websocket",
                "errorCode": "service_unavailable", "errorType": "websocket_error", "retry_attempt": 0}}}},
        {"event": {"type": "model.call_start", "data": {"model": failure["model"], "turnId": "3"}}},
        {"type": "complete", "exit_code": 1, "receipt": {
            "failure_stage": "session_send", "protocol_error": "unexpected_runtime_activity",
            "actual_models": [failure["model"]], "actual_reasoning_efforts": ["medium"],
            "provider_failures": [], "routing_changes": [],
            "usage": {"credits_complete": False, "totalNanoAiu": None}}},
    ]
    journal = source / directory / "transport/events.jsonl"
    journal.parent.mkdir(parents=True)
    journal.write_text("".join(json.dumps(record) + "\n" for record in records))
    study.atomic_json(source / "state.json", state)
    original = (source / "state.json").read_bytes()
    target_root = tmp_path / "service-new"
    target_root.mkdir()
    shutil.copytree(source_root / "protocol", target_root / "protocol")
    shutil.copytree(source_root / "harness", target_root / "harness")
    new_commit = "f" * 40
    new = {**case["new"], "commit": new_commit, "inputs_sha256": "5" * 64,
           "public_disclosure_url": f"https://github.com/jmservera/ama-thought-mve/commit/{new_commit}",
           "disclosed_at": "2026-01-08T00:00:00Z"}
    monkeypatch.setattr(study, "SERVICE_RECOVERY_SOURCE", case["new"]["commit"])
    monkeypatch.setattr(study, "SERVICE_RECOVERY_STATE_SHA256", hashlib.sha256(original).hexdigest())
    monkeypatch.setattr(study, "SERVICE_RECOVERY_JOURNAL_SHA256", hashlib.sha256(journal.read_bytes()).hexdigest())
    monkeypatch.setattr(study, "ROOT", target_root)
    monkeypatch.setattr(recovery, "ROOT", target_root)
    monkeypatch.setattr(study, "fingerprint", lambda *args: new["inputs_sha256"])
    prior_roots = [*case["prior_roots"], case["source_root"]]
    commits = {root: study.read_json(root / ".study/pilot-estimation/state.json")["identity"]["commit"]
               for root in [*prior_roots, source_root]}
    monkeypatch.setattr(study, "command", lambda args, **kwargs: commits.get(kwargs.get("cwd"), new_commit))
    approval = {**case["approval"], "original_state_sha256": study.SERVICE_RECOVERY_STATE_SHA256,
                "original_commit": case["new"]["commit"], "target_commit": new_commit,
                "attempt_id": identity, "approved_at": "2026-01-09T00:00:00Z",
                "disclosure_url": new["public_disclosure_url"]}
    return {**case, "source_root": source_root, "source": source, "target_root": target_root,
            "old": case["new"], "new": new, "approval": approval, "original": original,
            "journal": journal, "failed": failed, "prior_roots": prior_roots}


def prepare_service_incident(case):
    return case["recovery"].prepare(case["source_root"], case["old"], case["new"], case["approval"],
                                    prior_source_root=case["prior_roots"],
                                    calibration_manifest=case["calibration_manifest"])


def test_service_copy_retains_four_holds_and_full_feature_allowance(service_incident):
    case = service_incident
    study = case["study"]
    target = prepare_service_incident(case)
    state = study.read_json(target / "state.json")
    assert len(study.recovery_records(state)) == 4 and len(state["ledger"]["entries"]) == 2086
    assert sum(c.get("completed_steps", 0) for c in state["cells"]) == 2082
    assert sum(e["reserved_nano"] for e in state["ledger"]["entries"].values()
               if e["status"] == "recovery_hold") == 1200 * study.NANO
    assert (case["source"] / "state.json").read_bytes() == case["original"]
    assert (target / "state.before-recovery-03.json").is_file()
    assert state["started"] == study.read_json(case["source"] / "state.json")["started"]
    assert state["deadline"] == study.read_json(case["source"] / "state.json")["deadline"]
    controller = study.Controller(target, case["config"], smoke=False, phase="pilot-estimation",
                                  study_id="pilot-estimation", replicates=21,
                                  unregistered=case["new"], handoff=case["handoff"])
    cell = next(c for c in state["cells"] if any(a["id"] == case["failed"]["id"] for a in c["attempts"]))
    run = object.__new__(study.StudyRun)
    run.controller, run.cell, run.arm, run.current_step = controller, cell, "A", "f02-feature"
    assert run.remaining_allowance(1800) == (1800, 270 * study.NANO)
    study.validate_recovery_evidence(target, state, case["new"])
    assert len(study.recovery_source_locks(state, [*case["prior_roots"], case["source_root"]])) == 8


@pytest.mark.parametrize("damage", ["code", "status", "turn", "order", "usage", "identity"])
def test_service_recovery_requires_exact_retained_retry_and_unknown_receipt(service_incident, damage):
    case = service_incident
    records = [json.loads(line) for line in case["journal"].read_bytes().splitlines()]
    if damage == "code":
        records[1]["event"]["data"]["errorCode"] = "internal_error"
    elif damage == "status":
        records[1]["event"]["data"]["statusCode"] = 500
    elif damage == "turn":
        records[3]["event"]["data"]["turnId"] = "4"
    elif damage == "order":
        records[2], records[3] = records[3], records[2]
    elif damage == "usage":
        records[-1]["receipt"]["usage"]["totalNanoAiu"] = 0
    else:
        records[-1]["receipt"]["actual_models"] = ["other-model"]
    case["journal"].write_text("".join(json.dumps(record) + "\n" for record in records))
    with pytest.raises(case["study"].StudyError):
        prepare_service_incident(case)
    assert (case["source"] / "state.json").read_bytes() == case["original"]


@pytest.mark.parametrize("damage", ["intact", "scope", "approval", "source", "image", "next-state", "helper"])
def test_original_audit_authority_survives_only_intact_archived_recovery(service_incident, damage):
    case = service_incident
    analysis = importlib.import_module("analysis_adjudications")
    manifest = {"schema": "analysis-adjudications/v1", "study_id": "pilot-estimation",
                "scope_state_sha256": case["study"].SANDBOX_RECOVERY_STATE_SHA256,
                "execution_source_commit": case["old"]["commit"],
                "runtime_image": case["old"]["runtime_image"],
                "attribution_helper_sha256": analysis.current_helper_sha256(), "entries": []}
    source_manifest = case["source"] / "analysis-adjudications.json"
    case["study"].atomic_json(source_manifest, manifest)
    before = source_manifest.read_bytes()
    target = prepare_service_incident(case)
    state = case["study"].read_json(target / "state.json")
    if damage == "scope":
        (target / "state.before-recovery-03.json").unlink()
    elif damage == "approval":
        (target / "recovery-approval-03.json").write_text("{}")
    elif damage in ("source", "image"):
        path = target / "recovery-manifest-03.json"
        retained = case["study"].read_json(path)
        retained["commit" if damage == "source" else "runtime_image"] = \
            "b" * 40 if damage == "source" else "sha256:" + "b" * 64
        case["study"].atomic_json(path, retained)
    elif damage == "next-state":
        (target / "state.before-recovery.json").write_text("{}")
    elif damage == "helper":
        manifest["attribution_helper_sha256"] = "0" * 64
    if damage == "intact":
        analysis.validate_trust_anchors(target, manifest, state)
        assert state["identity"]["commit"] != manifest["execution_source_commit"]
        assert (target / "analysis-adjudications.json").read_bytes() == before
    else:
        with pytest.raises(case["study"].StudyError):
            analysis.validate_trust_anchors(target, manifest, state)
    assert source_manifest.read_bytes() == before
    assert (case["source"] / "state.json").read_bytes() == case["original"]


@pytest.fixture
def transport_incident(service_incident, tmp_path, monkeypatch):
    case = service_incident
    study, recovery = case["study"], case["recovery"]
    source = prepare_service_incident(case)
    source_root = case["target_root"]
    state = study.read_json(source / "state.json")
    extra = study.credits("26552.15674") - study.credits("23969.42938")
    quotient, remainder = divmod(extra, 207)
    for index in range(207):
        cell = state["cells"][index % len(state["cells"])]
        identity = f"transport-complete-{index}"
        amount = quotient + (index < remainder)
        cell["completed_steps"] = cell.get("completed_steps", 0) + 1
        cell["attempts"].append({"id": identity, "step": f"transport-step-{index}",
                                "status": "agent_returned", "seconds": 1,
                                "source_commit": case["new"]["commit"],
                                "usage": {"credits_complete": True, "totalNanoAiu": amount}})
        state["ledger"]["entries"][identity] = {
            "status": "complete", "reserved_nano": 300 * study.NANO, "actual_nano": amount}
    cell = next(cell for cell in state["cells"] if cell["assigned_model"] == "gpt-6.1-sol"
                and cell["arm"] == "D" and cell["replicate"] == 10)
    identity = study.TRANSPORT_RECOVERY_ATTEMPT
    directory = f"runs/{cell['run_id']}/attempts/{identity}"
    failed = {"id": identity, "step": "f07-feature", "status": "interrupted",
              "source_commit": case["new"]["commit"], "usage": None,
              "started": 1768003200, "seconds": 102.7977, "seconds_limit": 2700,
              "credit_limit_nano": 540 * study.NANO, "directory": directory}
    cell["attempts"].append(failed)
    cell["checkpoint"] = {"step": failed["step"], "head": "checkpoint"}
    state["ledger"]["entries"][identity] = {
        "status": "unknown", "reserved_nano": 600 * study.NANO, "actual_nano": None}
    state.update(status="oracle_halt", oracle_halt=True, stop_requested=False)
    message = '"WebSocket receive failed: WebSocket protocol error: Connection reset without closing handshake [ECONNRESET]"'
    failure = {"model": "gpt-6.1-sol", "reasoningEffort": "medium", "failureKind": "transport",
               "transport": "websocket", "rte": True, "source": "top_level", "apiEndpoint": "ws:/responses",
               "errorMessage": message, "retryAttempt": 0, "isAuto": False, "isByok": False,
               "apiCallId": "failed-api", "serviceRequestId": "failed-service"}
    records = [
        {"event": {"type": "model.call_start", "data": {"model": failure["model"], "turnId": "5"}}},
        {"event": {"type": "model.call_failure", "data": failure}},
        {"event": {"type": "model.model_call_failure", "data": {
            "turn": 5, "reasoningEffort": "medium", "modelCall": {
                "model": failure["model"], "api_id": failure["apiCallId"],
                "service_request_id": failure["serviceRequestId"], "transport": "websocket",
                "failure_kind": "transport", "rte": True, "api_endpoint": "ws:/responses",
                "error": message, "retry_attempt": 0}}}},
        {"event": {"type": "model.call_finished", "data": {"turnId": "5", "outcome": "error"}}},
        {"type": "complete", "exit_code": 1, "receipt": {
            "failure_stage": "session_send", "protocol_error": "unexpected_runtime_activity",
            "actual_models": [failure["model"]], "actual_reasoning_efforts": ["medium"],
            "provider_failures": [], "routing_changes": [],
            "usage": {"credits_complete": False, "totalNanoAiu": None}}},
    ]
    journal = source / directory / "transport/events.jsonl"
    journal.parent.mkdir(parents=True)
    journal.write_text("".join(json.dumps(record) + "\n" for record in records))
    study.atomic_json(source / "state.json", state)
    original = (source / "state.json").read_bytes()
    target_root = tmp_path / "transport-new"
    target_root.mkdir()
    shutil.copytree(source_root / "protocol", target_root / "protocol")
    shutil.copytree(source_root / "harness", target_root / "harness")
    new_commit = "8" * 40
    new = {**case["new"], "commit": new_commit, "inputs_sha256": "6" * 64,
           "public_disclosure_url": f"https://github.com/jmservera/ama-thought-mve/commit/{new_commit}",
           "disclosed_at": "2026-01-11T00:00:00Z"}
    monkeypatch.setattr(study, "TRANSPORT_RECOVERY_SOURCE", case["new"]["commit"])
    monkeypatch.setattr(study, "TRANSPORT_RECOVERY_STATE_SHA256", hashlib.sha256(original).hexdigest())
    monkeypatch.setattr(study, "TRANSPORT_RECOVERY_JOURNAL_SHA256", hashlib.sha256(journal.read_bytes()).hexdigest())
    monkeypatch.setattr(study, "ROOT", target_root)
    monkeypatch.setattr(recovery, "ROOT", target_root)
    monkeypatch.setattr(study, "fingerprint", lambda *args: new["inputs_sha256"])
    prior_roots = [*case["prior_roots"], case["source_root"]]
    commits = {root: study.read_json(root / ".study/pilot-estimation/state.json")["identity"]["commit"]
               for root in [*prior_roots, source_root]}
    monkeypatch.setattr(study, "command", lambda args, **kwargs: commits.get(kwargs.get("cwd"), new_commit))
    approval = {**case["approval"], "original_state_sha256": study.TRANSPORT_RECOVERY_STATE_SHA256,
                "original_commit": case["new"]["commit"], "target_commit": new_commit,
                "attempt_id": identity, "unknown_reservation_nano": 600 * study.NANO,
                "approved_at": "2026-01-12T00:00:00Z", "disclosure_url": new["public_disclosure_url"]}
    return {**case, "source_root": source_root, "source": source, "target_root": target_root,
            "old": case["new"], "new": new, "approval": approval, "original": original,
            "journal": journal, "failed": failed, "prior_roots": prior_roots}


def prepare_transport_incident(case):
    return case["recovery"].prepare(case["source_root"], case["old"], case["new"], case["approval"],
                                    prior_source_root=case["prior_roots"],
                                    calibration_manifest=case["calibration_manifest"])


def test_transport_copy_preserves_five_holds_and_full_longer_delivery_allowance(transport_incident):
    case, study = transport_incident, transport_incident["study"]
    target = prepare_transport_incident(case)
    state = study.read_json(target / "state.json")
    assert len(study.recovery_records(state)) == 5 and len(state["ledger"]["entries"]) == 2294
    assert sum(cell.get("completed_steps", 0) for cell in state["cells"]) == 2289
    assert sum(entry["reserved_nano"] for entry in state["ledger"]["entries"].values()
               if entry["status"] == "recovery_hold") == 1800 * study.NANO
    assert (case["source"] / "state.json").read_bytes() == case["original"]
    assert (target / "state.before-recovery-04.json").is_file()
    assert state["started"] == study.read_json(case["source"] / "state.json")["started"]
    assert state["deadline"] == study.read_json(case["source"] / "state.json")["deadline"]
    controller = study.Controller(target, case["config"], smoke=False, phase="pilot-estimation",
                                  study_id="pilot-estimation", replicates=21,
                                  unregistered=case["new"], handoff=case["handoff"])
    cell = next(c for c in controller.state["cells"] if any(a["id"] == case["failed"]["id"] for a in c["attempts"]))
    run = object.__new__(study.StudyRun)
    run.controller, run.cell, run.arm, run.current_step = controller, cell, "D", "f07-feature"
    assert run.remaining_allowance(2700) == (2700, 540 * study.NANO)
    retry = controller.new_attempt(cell, "f07-feature", 600 * study.NANO)
    assert controller.state["ledger"]["entries"][retry["id"]]["reserved_nano"] == 600 * study.NANO
    assert controller.state["ledger"]["entries"][case["failed"]["id"]]["actual_nano"] is None
    study.validate_recovery_evidence(target, controller.state, case["new"])
    assert len(study.recovery_source_locks(state, [*case["prior_roots"], case["source_root"]])) == 10


def test_transport_approval_cannot_shrink_the_unknown_longer_delivery_hold(transport_incident):
    case = transport_incident
    approval = {**case["approval"], "unknown_reservation_nano": 300 * case["study"].NANO}
    with pytest.raises(case["study"].StudyError, match="exact incident"):
        case["recovery"].verify_approval(approval, case["new"])


@pytest.mark.parametrize("damage", ["message", "retryable", "status", "endpoint", "mirror", "order", "usage"])
def test_transport_recovery_requires_the_exact_reset_journal_and_unknown_receipt(transport_incident, damage):
    case = transport_incident
    records = [json.loads(line) for line in case["journal"].read_bytes().splitlines()]
    if damage == "message":
        records[1]["event"]["data"]["errorMessage"] = "[ECONNRESET]"
    elif damage == "retryable":
        records[1]["event"]["data"]["rte"] = False
    elif damage == "status":
        records[1]["event"]["data"]["statusCode"] = 500
    elif damage == "endpoint":
        records[1]["event"]["data"]["apiEndpoint"] = "ws:/other"
    elif damage == "mirror":
        records[2]["event"]["data"]["modelCall"]["service_request_id"] = "wrong"
    elif damage == "order":
        records[2], records[3] = records[3], records[2]
    else:
        records[-1]["receipt"]["usage"] = {"credits_complete": True, "totalNanoAiu": 0}
    case["journal"].write_text("".join(json.dumps(record) + "\n" for record in records))
    with pytest.raises(case["study"].StudyError):
        case["recovery"].verify_journal(case["source"], case["failed"])


def test_fifth_copy_preserves_the_original_analysis_audit_authority(transport_incident):
    case = transport_incident
    analysis = importlib.import_module("analysis_adjudications")
    authority = case["study"].read_json(case["source"] / "recovery-manifest-03.json")
    manifest = {"schema": "analysis-adjudications/v1", "study_id": "pilot-estimation",
                "scope_state_sha256": case["study"].SANDBOX_RECOVERY_STATE_SHA256,
                "execution_source_commit": authority["commit"],
                "runtime_image": authority["runtime_image"],
                "attribution_helper_sha256": analysis.current_helper_sha256(), "entries": []}
    source_manifest = case["source"] / "analysis-adjudications.json"
    case["study"].atomic_json(source_manifest, manifest)
    before = source_manifest.read_bytes()
    target = prepare_transport_incident(case)
    state = case["study"].read_json(target / "state.json")
    analysis.validate_trust_anchors(target, manifest, state)
    assert (target / "analysis-adjudications.json").read_bytes() == before
    assert source_manifest.read_bytes() == before


@pytest.fixture
def close_incident(transport_incident, tmp_path, monkeypatch):
    case = transport_incident
    study, recovery = case["study"], case["recovery"]
    source = prepare_transport_incident(case)
    source_root = case["target_root"]
    state = study.read_json(source / "state.json")
    extra = study.credits("27814.55969") - study.credits("26552.15674")
    quotient, remainder = divmod(extra, 113)
    for index in range(113):
        cell = state["cells"][index % len(state["cells"])]
        identity = f"close-complete-{index}"
        amount = quotient + (index < remainder)
        cell["completed_steps"] = cell.get("completed_steps", 0) + 1
        cell["attempts"].append({"id": identity, "step": f"close-step-{index}",
                                "status": "agent_returned", "seconds": 1,
                                "source_commit": case["new"]["commit"],
                                "usage": {"credits_complete": True, "totalNanoAiu": amount}})
        state["ledger"]["entries"][identity] = {
            "status": "complete", "reserved_nano": 300 * study.NANO, "actual_nano": amount}
    cell = next(cell for cell in state["cells"] if cell["assigned_model"] == "gpt-6.1-sol"
                and cell["arm"] == "E" and cell["replicate"] == 10)
    identity = study.CLOSE_RECOVERY_ATTEMPT
    directory = f"runs/{cell['run_id']}/attempts/{identity}"
    failed = {"id": identity, "step": "f05-feature", "status": "interrupted",
              "source_commit": case["new"]["commit"], "usage": None,
              "started": 1768176000, "seconds": 74.6676, "seconds_limit": 1800,
              "credit_limit_nano": 270 * study.NANO, "directory": directory}
    cell["attempts"].append(failed)
    cell["checkpoint"] = {"step": failed["step"], "head": "checkpoint"}
    state["ledger"]["entries"][identity] = {
        "status": "unknown", "reserved_nano": 300 * study.NANO, "actual_nano": None}
    state.update(status="oracle_halt", oracle_halt=True, stop_requested=False)
    message = '"WebSocket closed unexpectedly (request-id: opaque-reference): 1001 please reconnect"'
    failure = {"model": "gpt-6.1-sol", "reasoningEffort": "medium", "failureKind": "transport",
               "transport": "websocket", "rte": False, "source": "top_level", "apiEndpoint": "ws:/responses",
               "errorMessage": message, "retryAttempt": 0, "isAuto": False, "isByok": False}
    records = [
        {"event": {"type": "model.call_start", "data": {"model": failure["model"], "turnId": "5"}}},
        {"event": {"type": "model.call_failure", "data": failure}},
        {"event": {"type": "model.model_call_failure", "data": {
            "turn": 5, "reasoningEffort": "medium", "rte": False, "modelCall": {
                "model": failure["model"], "transport": "websocket",
                "failure_kind": "transport", "rte": False, "api_endpoint": "ws:/responses",
                "error": message, "retry_attempt": 0}}}},
        {"type": "complete", "exit_code": 1, "receipt": {
            "failure_stage": "session_send", "protocol_error": "unexpected_runtime_activity",
            "actual_models": [failure["model"]], "actual_reasoning_efforts": ["medium"],
            "provider_failures": [], "routing_changes": [],
            "usage": {"credits_complete": False, "totalNanoAiu": None}}},
    ]
    journal = source / directory / "transport/events.jsonl"
    journal.parent.mkdir(parents=True)
    journal.write_text("".join(json.dumps(record) + "\n" for record in records))
    study.atomic_json(source / "state.json", state)
    original = (source / "state.json").read_bytes()
    target_root = tmp_path / "close-new"
    target_root.mkdir()
    shutil.copytree(source_root / "protocol", target_root / "protocol")
    shutil.copytree(source_root / "harness", target_root / "harness")
    new_commit = "9" * 40
    new = {**case["new"], "commit": new_commit, "inputs_sha256": "7" * 64,
           "public_disclosure_url": f"https://github.com/jmservera/ama-thought-mve/commit/{new_commit}",
           "disclosed_at": "2026-01-13T00:00:00Z"}
    monkeypatch.setattr(study, "CLOSE_RECOVERY_SOURCE", case["new"]["commit"])
    monkeypatch.setattr(study, "CLOSE_RECOVERY_STATE_SHA256", hashlib.sha256(original).hexdigest())
    monkeypatch.setattr(study, "CLOSE_RECOVERY_JOURNAL_SHA256", hashlib.sha256(journal.read_bytes()).hexdigest())
    monkeypatch.setattr(study, "ROOT", target_root)
    monkeypatch.setattr(recovery, "ROOT", target_root)
    monkeypatch.setattr(study, "fingerprint", lambda *args: new["inputs_sha256"])
    prior_roots = [*case["prior_roots"], case["source_root"]]
    commits = {root: study.read_json(root / ".study/pilot-estimation/state.json")["identity"]["commit"]
               for root in [*prior_roots, source_root]}
    monkeypatch.setattr(study, "command", lambda args, **kwargs: commits.get(kwargs.get("cwd"), new_commit))
    approval = {**case["approval"], "original_state_sha256": study.CLOSE_RECOVERY_STATE_SHA256,
                "original_commit": case["new"]["commit"], "target_commit": new_commit,
                "attempt_id": identity, "unknown_reservation_nano": 300 * study.NANO,
                "approved_at": "2026-01-14T00:00:00Z", "disclosure_url": new["public_disclosure_url"]}
    return {**case, "source_root": source_root, "source": source, "target_root": target_root,
            "old": case["new"], "new": new, "approval": approval, "original": original,
            "journal": journal, "failed": failed, "prior_roots": prior_roots}


def prepare_close_incident(case):
    return case["recovery"].prepare(case["source_root"], case["old"], case["new"], case["approval"],
                                    prior_source_root=case["prior_roots"],
                                    calibration_manifest=case["calibration_manifest"])


def test_close_copy_preserves_six_holds_and_ordinary_feature_allowance(close_incident):
    case, study = close_incident, close_incident["study"]
    target = prepare_close_incident(case)
    state = study.read_json(target / "state.json")
    assert len(study.recovery_records(state)) == 6 and len(state["ledger"]["entries"]) == 2408
    assert sum(cell.get("completed_steps", 0) for cell in state["cells"]) == 2402
    assert sum(entry["reserved_nano"] for entry in state["ledger"]["entries"].values()
               if entry["status"] == "recovery_hold") == 2100 * study.NANO
    assert (case["source"] / "state.json").read_bytes() == case["original"]
    assert (target / "state.before-recovery-05.json").is_file()
    controller = study.Controller(target, case["config"], smoke=False, phase="pilot-estimation",
                                  study_id="pilot-estimation", replicates=21,
                                  unregistered=case["new"], handoff=case["handoff"])
    cell = next(c for c in controller.state["cells"] if any(a["id"] == case["failed"]["id"] for a in c["attempts"]))
    run = object.__new__(study.StudyRun)
    run.controller, run.cell, run.arm, run.current_step = controller, cell, "E", "f05-feature"
    assert run.remaining_allowance(1800) == (1800, 270 * study.NANO)
    retry = controller.new_attempt(cell, "f05-feature")
    assert controller.state["ledger"]["entries"][retry["id"]]["reserved_nano"] == 300 * study.NANO
    assert controller.state["ledger"]["entries"][case["failed"]["id"]]["actual_nano"] is None
    study.validate_recovery_evidence(target, controller.state, case["new"])
    assert len(study.recovery_source_locks(state, [*case["prior_roots"], case["source_root"]])) == 12


@pytest.mark.parametrize("damage", ["message", "treatment", "invented-id", "mirror", "order", "usage"])
def test_close_recovery_requires_exact_retained_signature_and_unknown_usage(close_incident, damage):
    case = close_incident
    records = [json.loads(line) for line in case["journal"].read_bytes().splitlines()]
    if damage == "message":
        records[1]["event"]["data"]["errorMessage"] = "1001 please reconnect"
    elif damage == "treatment":
        records[1]["event"]["data"]["rte"] = True
    elif damage == "invented-id":
        records[1]["event"]["data"]["apiCallId"] = "guessed-from-message"
    elif damage == "mirror":
        records[2]["event"]["data"]["modelCall"]["error"] = "different error"
    elif damage == "order":
        records[0], records[1] = records[1], records[0]
    else:
        records[-1]["receipt"]["usage"] = {"credits_complete": True, "totalNanoAiu": 0}
    case["journal"].write_text("".join(json.dumps(record) + "\n" for record in records))
    with pytest.raises(case["study"].StudyError):
        case["recovery"].verify_journal(case["source"], case["failed"])


def test_sixth_copy_preserves_original_analysis_audit_authority(close_incident):
    case = close_incident
    analysis = importlib.import_module("analysis_adjudications")
    authority = case["study"].read_json(case["source"] / "recovery-manifest-03.json")
    manifest = {"schema": "analysis-adjudications/v1", "study_id": "pilot-estimation",
                "scope_state_sha256": case["study"].SANDBOX_RECOVERY_STATE_SHA256,
                "execution_source_commit": authority["commit"], "runtime_image": authority["runtime_image"],
                "attribution_helper_sha256": analysis.current_helper_sha256(), "entries": []}
    path = case["source"] / "analysis-adjudications.json"
    case["study"].atomic_json(path, manifest)
    before = path.read_bytes()
    target = prepare_close_incident(case)
    state = case["study"].read_json(target / "state.json")
    analysis.validate_trust_anchors(target, manifest, state)
    assert (target / "analysis-adjudications.json").read_bytes() == before
    assert path.read_bytes() == before


@pytest.fixture
def mixed_incident(close_incident, tmp_path, monkeypatch):
    case = close_incident
    study, recovery = case["study"], case["recovery"]
    source = prepare_close_incident(case)
    source_root = case["target_root"]
    state = study.read_json(source / "state.json")
    extra = study.credits("29220.13966") - study.credits("27814.55969")
    quotient, remainder = divmod(extra, 124)
    for index in range(124):
        cell = state["cells"][index % len(state["cells"])]
        identity = f"mixed-complete-{index}"
        amount = quotient + (index < remainder)
        cell["completed_steps"] = cell.get("completed_steps", 0) + 1
        cell["attempts"].append({"id": identity, "step": f"mixed-step-{index}",
                                "status": "agent_returned", "seconds": 1,
                                "source_commit": case["new"]["commit"],
                                "usage": {"credits_complete": True, "totalNanoAiu": amount}})
        state["ledger"]["entries"][identity] = {
            "status": "complete", "reserved_nano": 300 * study.NANO, "actual_nano": amount}
    cell = next(cell for cell in state["cells"] if cell["assigned_model"] == "gpt-6.1-sol"
                and cell["arm"] == "E" and cell["replicate"] == 10)
    identity = study.MIXED_RECOVERY_ATTEMPT
    directory = f"runs/{cell['run_id']}/attempts/{identity}"
    failed = {"id": identity, "step": "f10-feature", "status": "interrupted",
              "source_commit": case["new"]["commit"], "usage": None,
              "started": 1768348800, "seconds": 135.7199, "seconds_limit": 1800,
              "credit_limit_nano": 270 * study.NANO, "directory": directory}
    cell["attempts"].append(failed)
    cell["checkpoint"] = {"step": failed["step"], "head": "checkpoint"}
    state["ledger"]["entries"][identity] = {
        "status": "unknown", "reserved_nano": 300 * study.NANO, "actual_nano": None}
    state.update(status="oracle_halt", oracle_halt=True, stop_requested=False)
    records = [{"event": {"type": "model.call_start", "data": {"model": "gpt-6.1-sol", "turnId": "6"}}}]
    for retry in range(2):
        failure = {"model": "gpt-6.1-sol", "reasoningEffort": "medium", "failureKind": "api",
                   "transport": "websocket", "statusCode": 500, "errorCode": "internal_error",
                   "errorType": "websocket_error", "retryAttempt": retry, "isAuto": False, "isByok": False,
                   "apiCallId": f"api-{retry}", "serviceRequestId": f"service-{retry}"}
        records.extend([
            {"event": {"type": "model.call_failure", "data": failure}},
            {"event": {"type": "model.model_call_failure", "data": {
                "turn": 6, "reasoningEffort": "medium", "modelCall": {
                    "model": failure["model"], "api_id": failure["apiCallId"],
                    "service_request_id": failure["serviceRequestId"], "transport": "websocket",
                    "status": 500, "errorCode": "internal_error", "errorType": "websocket_error",
                    "retry_attempt": retry}}}},
        ])
        if retry == 0:
            records.append({"event": {"type": "model.call_finished", "data": {"turnId": "6", "outcome": "error"}}})
        records.append({"event": {"type": "model.call_start", "data": {"model": "gpt-6.1-sol", "turnId": "6"}}})
    records.append({"type": "complete", "exit_code": 1, "receipt": {
        "failure_stage": "session_send", "protocol_error": "unexpected_runtime_activity",
        "actual_models": ["gpt-6.1-sol"], "actual_reasoning_efforts": ["medium"], "routing_changes": [],
        "provider_failures": [{"status_code": 500, "error_code": "internal_error", "transport": "websocket",
                               "retry_attempt": 0, "accounting_complete": False}],
        "usage": {"credits_complete": False, "totalNanoAiu": None}}})
    journal = source / directory / "transport/events.jsonl"
    journal.parent.mkdir(parents=True)
    journal.write_text("".join(json.dumps(record) + "\n" for record in records))
    study.atomic_json(source / "state.json", state)
    original = (source / "state.json").read_bytes()
    target_root = tmp_path / "mixed-new"
    target_root.mkdir()
    shutil.copytree(source_root / "protocol", target_root / "protocol")
    shutil.copytree(source_root / "harness", target_root / "harness")
    new_commit = "6" * 40
    new = {**case["new"], "commit": new_commit, "inputs_sha256": "9" * 64,
           "public_disclosure_url": f"https://github.com/jmservera/ama-thought-mve/commit/{new_commit}",
           "disclosed_at": "2026-01-15T00:00:00Z"}
    monkeypatch.setattr(study, "MIXED_RECOVERY_SOURCE", case["new"]["commit"])
    monkeypatch.setattr(study, "MIXED_RECOVERY_STATE_SHA256", hashlib.sha256(original).hexdigest())
    monkeypatch.setattr(study, "MIXED_RECOVERY_JOURNAL_SHA256", hashlib.sha256(journal.read_bytes()).hexdigest())
    monkeypatch.setattr(study, "ROOT", target_root)
    monkeypatch.setattr(recovery, "ROOT", target_root)
    monkeypatch.setattr(study, "fingerprint", lambda *args: new["inputs_sha256"])
    prior_roots = [*case["prior_roots"], case["source_root"]]
    commits = {root: study.read_json(root / ".study/pilot-estimation/state.json")["identity"]["commit"]
               for root in [*prior_roots, source_root]}
    monkeypatch.setattr(study, "command", lambda args, **kwargs: commits.get(kwargs.get("cwd"), new_commit))
    approval = {**case["approval"], "original_state_sha256": study.MIXED_RECOVERY_STATE_SHA256,
                "original_commit": case["new"]["commit"], "target_commit": new_commit,
                "attempt_id": identity, "approved_at": "2026-01-16T00:00:00Z",
                "disclosure_url": new["public_disclosure_url"]}
    return {**case, "source_root": source_root, "source": source, "target_root": target_root,
            "old": case["new"], "new": new, "approval": approval, "original": original,
            "journal": journal, "failed": failed, "prior_roots": prior_roots}


def prepare_mixed_incident(case):
    return case["recovery"].prepare(case["source_root"], case["old"], case["new"], case["approval"],
                                    prior_source_root=case["prior_roots"],
                                    calibration_manifest=case["calibration_manifest"])


def test_mixed_copy_preserves_seven_holds_and_full_feature_allowance(mixed_incident):
    case, study = mixed_incident, mixed_incident["study"]
    target = prepare_mixed_incident(case)
    state = study.read_json(target / "state.json")
    assert len(study.recovery_records(state)) == 7 and len(state["ledger"]["entries"]) == 2533
    assert sum(cell.get("completed_steps", 0) for cell in state["cells"]) == 2526
    assert sum(entry["reserved_nano"] for entry in state["ledger"]["entries"].values()
               if entry["status"] == "recovery_hold") == 2400 * study.NANO
    assert (case["source"] / "state.json").read_bytes() == case["original"]
    assert (target / "state.before-recovery-06.json").is_file()
    controller = study.Controller(target, case["config"], smoke=False, phase="pilot-estimation",
                                  study_id="pilot-estimation", replicates=21,
                                  unregistered=case["new"], handoff=case["handoff"])
    cell = next(c for c in controller.state["cells"] if any(a["id"] == case["failed"]["id"] for a in c["attempts"]))
    run = object.__new__(study.StudyRun)
    run.controller, run.cell, run.arm, run.current_step = controller, cell, "E", "f10-feature"
    assert run.remaining_allowance(1800) == (1800, 270 * study.NANO)
    retry = controller.new_attempt(cell, "f10-feature")
    assert controller.state["ledger"]["entries"][retry["id"]]["reserved_nano"] == 300 * study.NANO
    study.validate_recovery_evidence(target, controller.state, case["new"])
    assert len(study.recovery_source_locks(state, [*case["prior_roots"], case["source_root"]])) == 14


@pytest.mark.parametrize("damage", ["index", "finish", "turn", "mirror", "usage"])
def test_mixed_recovery_requires_exact_boundary_order_and_original_unknown_receipt(mixed_incident, damage):
    case = mixed_incident
    records = [json.loads(line) for line in case["journal"].read_bytes().splitlines()]
    if damage == "index":
        records[5]["event"]["data"]["retryAttempt"] = 0
    elif damage == "finish":
        records[3]["event"]["data"]["outcome"] = "success"
    elif damage == "turn":
        records[4]["event"]["data"]["turnId"] = "7"
    elif damage == "mirror":
        records[6]["event"]["data"]["modelCall"]["api_id"] = "unmatched"
    else:
        records[-1]["receipt"]["usage"] = {"credits_complete": True, "totalNanoAiu": 0}
    case["journal"].write_text("".join(json.dumps(record) + "\n" for record in records))
    with pytest.raises(case["study"].StudyError):
        case["recovery"].verify_journal(case["source"], case["failed"])


def test_seventh_copy_preserves_original_analysis_audit_authority(mixed_incident):
    case = mixed_incident
    analysis = importlib.import_module("analysis_adjudications")
    authority = case["study"].read_json(case["source"] / "recovery-manifest-03.json")
    manifest = {"schema": "analysis-adjudications/v1", "study_id": "pilot-estimation",
                "scope_state_sha256": case["study"].SANDBOX_RECOVERY_STATE_SHA256,
                "execution_source_commit": authority["commit"], "runtime_image": authority["runtime_image"],
                "attribution_helper_sha256": analysis.current_helper_sha256(), "entries": []}
    path = case["source"] / "analysis-adjudications.json"
    case["study"].atomic_json(path, manifest)
    before = path.read_bytes()
    target = prepare_mixed_incident(case)
    analysis.validate_trust_anchors(target, manifest, case["study"].read_json(target / "state.json"))
    assert (target / "analysis-adjudications.json").read_bytes() == before
    assert path.read_bytes() == before


@pytest.fixture
def unaccounted_incident(mixed_incident, tmp_path, monkeypatch):
    case = mixed_incident
    study, recovery = case["study"], case["recovery"]
    source = prepare_mixed_incident(case)
    source_root = case["target_root"]
    state = study.read_json(source / "state.json")
    extra = study.credits("30927.78079") - study.credits("29220.13966")
    quotient, remainder = divmod(extra, 165)
    for index in range(165):
        cell = state["cells"][index % len(state["cells"])]
        identity = f"unaccounted-complete-{index}"
        amount = quotient + (index < remainder)
        cell["completed_steps"] = cell.get("completed_steps", 0) + 1
        cell["attempts"].append({"id": identity, "step": f"unaccounted-step-{index}",
                                "status": "agent_returned", "seconds": 1,
                                "source_commit": case["new"]["commit"],
                                "usage": {"credits_complete": True, "totalNanoAiu": amount}})
        state["ledger"]["entries"][identity] = {
            "status": "complete", "reserved_nano": 300 * study.NANO, "actual_nano": amount}
    cell = next(cell for cell in state["cells"] if cell["assigned_model"] == "gpt-6.1-sol"
                and cell["arm"] == "D" and cell["replicate"] == 11)
    identity = study.UNACCOUNTED_RECOVERY_ATTEMPT
    directory = f"runs/{cell['run_id']}/attempts/{identity}"
    failed = {"id": identity, "step": "f06-feature", "status": "interrupted",
              "source_commit": case["new"]["commit"], "usage": None,
              "started": 1768694400, "seconds": 162.0114, "seconds_limit": 2700,
              "credit_limit_nano": 540 * study.NANO, "directory": directory}
    cell["attempts"].append(failed)
    cell["checkpoint"] = {"step": failed["step"], "head": "checkpoint"}
    state["ledger"]["entries"][identity] = {
        "status": "unknown", "reserved_nano": 600 * study.NANO, "actual_nano": None}
    state.update(status="oracle_halt", oracle_halt=True, stop_requested=False)
    message = '"WebSocket receive failed: WebSocket protocol error: Connection reset without closing handshake [ECONNRESET]"'
    failure = {"model": "gpt-6.1-sol", "reasoningEffort": "medium", "failureKind": "transport",
               "transport": "websocket", "rte": True, "source": "top_level", "apiEndpoint": "ws:/responses",
               "errorMessage": message, "retryAttempt": 0, "isAuto": False, "isByok": False,
               "apiCallId": "failed-api", "serviceRequestId": "failed-service"}
    records = [
        {"event": {"type": "model.call_start", "data": {"model": failure["model"], "turnId": "5"}}},
        {"event": {"type": "model.call_failure", "data": failure}},
        {"event": {"type": "model.model_call_failure", "data": {
            "turn": 5, "reasoningEffort": "medium", "modelCall": {
                "model": failure["model"], "api_id": failure["apiCallId"],
                "service_request_id": failure["serviceRequestId"], "transport": "websocket",
                "failure_kind": "transport", "rte": True, "api_endpoint": "ws:/responses",
                "error": message, "retry_attempt": 0}}}},
        {"event": {"type": "model.call_finished", "data": {"turnId": "5", "outcome": "error"}}},
        {"event": {"type": "model.call_start", "data": {"model": failure["model"], "turnId": "5"}}},
        {"event": {"type": "assistant.usage", "data": {
            "apiCallId": "successful-api", "serviceRequestId": "successful-service",
            "aiCreditsStatus": "complete", "copilotUsage": {"totalNanoAiu": 123}}}},
        {"event": {"type": "model.call_finished", "data": {"turnId": "5", "outcome": "success"}}},
        {"event": {"type": "session.idle", "data": {}}},
        {"event": {"type": "session.shutdown", "data": {"shutdownType": "routine", "totalNanoAiu": 123}}},
        {"type": "complete", "exit_code": 1, "receipt": {
            "failure_stage": None, "protocol_error": "provider_retry_usage_incomplete",
            "actual_models": [failure["model"]], "actual_reasoning_efforts": ["medium"],
            "routing_changes": [], "provider_failures": [{
                "status_code": None, "error_code": None, "failure_kind": "transport",
                "transport": "websocket", "retry_attempt": 0, "accounting_complete": False}],
            "usage": {"credits_complete": False, "totalNanoAiu": None}}},
    ]
    journal = source / directory / "transport/events.jsonl"
    journal.parent.mkdir(parents=True)
    journal.write_text("".join(json.dumps(record) + "\n" for record in records))
    study.atomic_json(source / "state.json", state)
    original = (source / "state.json").read_bytes()
    target_root = tmp_path / "unaccounted-new"
    target_root.mkdir()
    shutil.copytree(source_root / "protocol", target_root / "protocol")
    shutil.copytree(source_root / "harness", target_root / "harness")
    new_commit = "f0" * 20
    new = {**case["new"], "commit": new_commit, "inputs_sha256": "af" * 32,
           "public_disclosure_url": f"https://github.com/jmservera/ama-thought-mve/commit/{new_commit}",
           "disclosed_at": "2026-01-18T00:00:00Z"}
    monkeypatch.setattr(study, "UNACCOUNTED_RECOVERY_SOURCE", case["new"]["commit"])
    monkeypatch.setattr(study, "UNACCOUNTED_RECOVERY_STATE_SHA256", hashlib.sha256(original).hexdigest())
    monkeypatch.setattr(study, "UNACCOUNTED_RECOVERY_JOURNAL_SHA256", hashlib.sha256(journal.read_bytes()).hexdigest())
    monkeypatch.setattr(study, "ROOT", target_root)
    monkeypatch.setattr(recovery, "ROOT", target_root)
    monkeypatch.setattr(study, "fingerprint", lambda *args: new["inputs_sha256"])
    prior_roots = [*case["prior_roots"], case["source_root"]]
    commits = {root: study.read_json(root / ".study/pilot-estimation/state.json")["identity"]["commit"]
               for root in [*prior_roots, source_root]}
    monkeypatch.setattr(study, "command", lambda args, **kwargs: commits.get(kwargs.get("cwd"), new_commit))
    approval = {**case["approval"], "original_state_sha256": study.UNACCOUNTED_RECOVERY_STATE_SHA256,
                "original_commit": case["new"]["commit"], "target_commit": new_commit,
                "attempt_id": identity, "unknown_reservation_nano": 600 * study.NANO,
                "approved_at": "2026-01-19T00:00:00Z", "disclosure_url": new["public_disclosure_url"]}
    return {**case, "source_root": source_root, "source": source, "target_root": target_root,
            "old": case["new"], "new": new, "approval": approval, "original": original,
            "journal": journal, "failed": failed, "prior_roots": prior_roots}


def prepare_unaccounted_incident(case):
    return case["recovery"].prepare(case["source_root"], case["old"], case["new"], case["approval"],
                                    prior_source_root=case["prior_roots"],
                                    calibration_manifest=case["calibration_manifest"])


def test_unaccounted_copy_preserves_eight_holds_and_full_longer_delivery_allowance(unaccounted_incident):
    case, study = unaccounted_incident, unaccounted_incident["study"]
    target = prepare_unaccounted_incident(case)
    state = study.read_json(target / "state.json")
    assert len(study.recovery_records(state)) == 8 and len(state["ledger"]["entries"]) == 2699
    assert sum(cell.get("completed_steps", 0) for cell in state["cells"]) == 2691
    assert sum(entry["reserved_nano"] for entry in state["ledger"]["entries"].values()
               if entry["status"] == "recovery_hold") == 3000 * study.NANO
    assert (case["source"] / "state.json").read_bytes() == case["original"]
    assert (target / "state.before-recovery-07.json").is_file()
    for key in ("started", "deadline"):
        assert state[key] == json.loads(case["original"])[key]
    assert state["identity"]["config"] == json.loads(case["original"])["identity"]["config"]
    assert state["ledger"]["calibration_handoff"] == case["handoff"]
    controller = study.Controller(target, case["config"], smoke=False, phase="pilot-estimation",
                                  study_id="pilot-estimation", replicates=21,
                                  unregistered=case["new"], handoff=case["handoff"])
    cell = next(c for c in controller.state["cells"] if any(a["id"] == case["failed"]["id"] for a in c["attempts"]))
    run = object.__new__(study.StudyRun)
    run.controller, run.cell, run.arm, run.current_step = controller, cell, "D", "f06-feature"
    assert run.remaining_allowance(2700) == (2700, 540 * study.NANO)
    retry = controller.new_attempt(cell, "f06-feature")
    assert controller.state["ledger"]["entries"][retry["id"]]["reserved_nano"] == 600 * study.NANO
    assert controller.state["ledger"]["entries"][case["failed"]["id"]]["actual_nano"] is None
    study.validate_recovery_evidence(target, controller.state, case["new"])
    assert len(study.recovery_source_locks(state, [*case["prior_roots"], case["source_root"]])) == 16


@pytest.mark.parametrize("damage", ["mirror", "retry_turn", "retry_finish", "shutdown", "idle",
                                   "failed_charge", "stage", "protocol", "provider_charge", "usage", "hash"])
def test_unaccounted_recovery_requires_exact_successful_retry_and_missing_charge(
        unaccounted_incident, monkeypatch, damage):
    case = unaccounted_incident
    records = [json.loads(line) for line in case["journal"].read_bytes().splitlines()]
    if damage == "mirror":
        records[2]["event"]["data"]["modelCall"]["api_id"] = "unmatched"
    elif damage == "retry_turn":
        records[4]["event"]["data"]["turnId"] = "6"
    elif damage == "retry_finish":
        records[6]["event"]["data"]["outcome"] = "error"
    elif damage == "shutdown":
        records[8]["event"]["data"]["shutdownType"] = "abnormal"
    elif damage == "idle":
        records[7]["event"]["type"] = "assistant.idle"
    elif damage == "failed_charge":
        records[5]["event"]["data"].update(apiCallId="failed-api", serviceRequestId="failed-service")
    elif damage == "stage":
        records[-1]["receipt"]["failure_stage"] = "session_send"
    elif damage == "protocol":
        records[-1]["receipt"]["protocol_error"] = "unexpected_runtime_activity"
    elif damage == "provider_charge":
        records[-1]["receipt"]["provider_failures"][0]["accounting_complete"] = True
    elif damage == "usage":
        records[-1]["receipt"]["usage"] = {"credits_complete": True, "totalNanoAiu": 0}
    else:
        records[1]["event"]["data"]["durationMs"] = 1
    case["journal"].write_text("".join(json.dumps(record) + "\n" for record in records))
    if damage != "hash":
        monkeypatch.setattr(case["study"], "UNACCOUNTED_RECOVERY_JOURNAL_SHA256",
                            hashlib.sha256(case["journal"].read_bytes()).hexdigest())
    with pytest.raises(case["study"].StudyError):
        case["recovery"].verify_journal(case["source"], case["failed"])


def test_unaccounted_recovery_rejects_smaller_hold_approval(unaccounted_incident):
    case = unaccounted_incident
    approval = {**case["approval"], "unknown_reservation_nano": 300 * case["study"].NANO}
    with pytest.raises(case["study"].StudyError, match="exact incident"):
        case["recovery"].verify_approval(approval, case["new"])


def test_eighth_copy_preserves_original_analysis_audit_authority(unaccounted_incident):
    case = unaccounted_incident
    analysis = importlib.import_module("analysis_adjudications")
    authority = case["study"].read_json(case["source"] / "recovery-manifest-03.json")
    manifest = {"schema": "analysis-adjudications/v1", "study_id": "pilot-estimation",
                "scope_state_sha256": case["study"].SANDBOX_RECOVERY_STATE_SHA256,
                "execution_source_commit": authority["commit"], "runtime_image": authority["runtime_image"],
                "attribution_helper_sha256": analysis.current_helper_sha256(), "entries": []}
    path = case["source"] / "analysis-adjudications.json"
    case["study"].atomic_json(path, manifest)
    before = path.read_bytes()
    target = prepare_unaccounted_incident(case)
    analysis.validate_trust_anchors(target, manifest, case["study"].read_json(target / "state.json"))
    assert (target / "analysis-adjudications.json").read_bytes() == before
    assert path.read_bytes() == before
