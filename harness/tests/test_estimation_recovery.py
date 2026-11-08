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
