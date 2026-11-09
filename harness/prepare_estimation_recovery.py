"""Prepare a separate, owner-authorized copy of the interrupted estimation study."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import stat
import time
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path

import study
from study_io import ROOT, StudyError, atomic_json, read_json


def digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def verify_approval(approval: dict, new_manifest: dict) -> None:
    expected = {"schema", "original_state_sha256", "original_commit", "target_commit", "attempt_id",
                "unknown_reservation_nano", "accept_unknown_hold", "accept_fresh_retry_reservation",
                "accept_fresh_retry_time_allowance", "accept_mid_study_source_change", "owner_approved",
                "approved_at", "disclosure_url"}
    incident = study.recovery_incident(approval.get("original_state_sha256"))
    if (set(approval) != expected or approval["schema"] != "estimation-incident-approval/v1"
            or approval["original_commit"] != incident["source"]
            or approval["target_commit"] != new_manifest.get("commit")
            or approval["target_commit"] == incident["source"]
            or approval["attempt_id"] != incident["attempt"]
            or type(approval["unknown_reservation_nano"]) is not int
            or approval["unknown_reservation_nano"] != incident["reserved_nano"]
            or any(approval[key] is not True for key in ("accept_unknown_hold",
                   "accept_fresh_retry_reservation", "accept_fresh_retry_time_allowance",
                   "accept_mid_study_source_change", "owner_approved"))
            or approval["disclosure_url"] != new_manifest.get("public_disclosure_url")):
        raise StudyError("Recovery approval must explicitly authorize the exact incident and source change")
    try:
        approved = datetime.fromisoformat(approval["approved_at"])
        disclosed = datetime.fromisoformat(new_manifest["disclosed_at"])
        if (approved.utcoffset() is None or disclosed.utcoffset() is None
                or approved.timestamp() > time.time() or approved < disclosed):
            raise ValueError("Invalid approval time")
    except (KeyError, TypeError, ValueError, OverflowError) as error:
        raise StudyError("Recovery approval requires a valid, nonfuture timezone-aware timestamp") from error


def verify_approval_after_attempt(approval: dict, attempt: dict) -> None:
    started, seconds = attempt.get("started"), attempt.get("seconds")
    if (type(started) not in (int, float) or not math.isfinite(started)
            or type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0
            or datetime.fromisoformat(approval["approved_at"]).timestamp() < started + seconds):
        raise StudyError("Recovery approval must follow the interrupted attempt")


def require_regular_tree(root: Path) -> None:
    def fail(error: OSError) -> None:
        raise StudyError("Cannot inspect the complete recovery tree") from error

    for base, directories, files in os.walk(root, followlinks=False, onerror=fail):
        for name in directories + files:
            mode = (Path(base) / name).lstat().st_mode
            if not (stat.S_ISDIR(mode) or stat.S_ISREG(mode)):
                raise StudyError("Recovery trees must not contain links or special files")


def verify_journal(directory: Path, attempt: dict, *, preserved_broker: bool = False) -> str:
    incidents = [study.recovery_incident(value) for value in study.recovery_state_hashes()]
    incident = next((item for item in incidents if item["attempt"] == attempt.get("id")), None)
    if incident is None:
        raise StudyError("Failed attempt is not one of the disclosed estimation interruptions")
    relative = attempt.get("directory")
    if (not isinstance(relative, str) or not relative or Path(relative).is_absolute()
            or ".." in Path(relative).parts):
        raise StudyError("Invalid failed attempt directory")
    path = directory / relative / "transport/events.jsonl"
    if (path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(directory.resolve())
            or path.stat().st_size > 64 * 1024 * 1024):
        raise StudyError("Failed attempt journal is missing or unsafe")
    payload = path.read_bytes()
    if not payload.endswith(b"\n"):
        raise StudyError("Failed attempt journal is incomplete")
    records = [json.loads(line) for line in payload.splitlines()]
    if any(not isinstance(record, dict) or (
        "event" in record and (not isinstance(record["event"], dict)
                              or not isinstance(record["event"].get("data"), dict))) for record in records):
        raise StudyError("Failed attempt journal contains invalid records")
    complete = [record for record in records if record.get("type") == "complete"]
    if incident["kind"] == "state_links":
        tools = [record for record in records if record.get("type") == "tool"]
        if complete or not tools or records[-1] is not tools[-1]:
            raise StudyError("Sandbox interruption must retain the incomplete final tool transaction")
        tool = tools[-1]
        arguments = tool.get("arguments")
        starts = [record["event"]["data"] for record in records
                  if record.get("event", {}).get("type") == "tool.execution_start"
                  and record["event"]["data"].get("toolCallId") == tool.get("id")]
        finishes = [record for record in records
                    if record.get("event", {}).get("type") == "tool.execution_complete"
                    and record["event"]["data"].get("toolCallId") == tool.get("id")]
        if (not isinstance(tool.get("id"), str) or not tool["id"] or len(starts) != 1
                or starts[0].get("toolName") != "isolated_exec" or finishes
                or any(key in starts[0] for key in ("mcpServerName", "mcpToolName", "namespacedName"))
                or not isinstance(arguments, dict) or set(arguments) != {"command", "timeoutSeconds"}
                or not isinstance(arguments["command"], str) or not arguments["command"]
                or arguments["timeoutSeconds"] != 120):
            raise StudyError("Sandbox interruption differs from the retained isolated tool request")
        broker = (directory / relative / "recovery-broker" if preserved_broker
                  else directory / "runs" / incident["run_id"] / "isolation")
        if (broker.is_symlink() or not broker.is_dir()
                or not broker.resolve().is_relative_to(directory.resolve())):
            raise StudyError("Retained sandbox state is missing or unsafe")
        files = {"state.json": incident["broker_metadata_sha256"],
                 "latest.state": incident["broker_state_sha256"],
                 "owner": incident["broker_owner_sha256"]}
        for name, expected in files.items():
            item = broker / name
            if (item.is_symlink() or not item.is_file() or item.stat().st_size > 64 * 1024 * 1024
                    or hashlib.sha256(item.read_bytes()).hexdigest() != expected):
                raise StudyError("Retained sandbox state differs from the disclosed rejection")
        metadata = read_json(broker / "state.json")
        if (metadata.get("slot") != "latest.state"
                or metadata.get("sha256") != incident["broker_state_sha256"]
                or any((broker / name).exists() or (broker / name).is_symlink()
                       for name in ("container.json", "container.cid"))):
            raise StudyError("Sandbox rejection lacks a preserved state and confirmed cleanup")
        value = hashlib.sha256(payload).hexdigest()
        if value != incident["journal_sha256"]:
            raise StudyError("Failed attempt journal differs from the disclosed incident")
        return value
    if len(complete) != 1:
        raise StudyError("Failed attempt lacks a unique terminal receipt")
    receipt = complete[0].get("receipt", {})
    if (not isinstance(receipt, dict) or not isinstance(receipt.get("usage"), dict)
            or complete[0].get("exit_code") != 1
            or receipt.get("failure_stage") != "session_send"
            or receipt.get("usage", {}).get("credits_complete") is not False
            or receipt.get("usage", {}).get("totalNanoAiu") is not None):
        raise StudyError("Failed attempt does not retain its terminal failure and unknown usage")
    events = [record["event"] for record in records if "event" in record]
    if incident["kind"] == "missing_edit":
        starts = [event["data"] for event in events if event["type"] == "tool.execution_start"
                  and event["data"].get("toolName") == "edit"]
        if len(starts) != 1:
            raise StudyError("Failed attempt lacks a unique edit call")
        start = starts[0]
        matches = [event["data"] for event in events if event["type"] == "tool.execution_complete"
                   and event["data"].get("toolCallId") == start.get("toolCallId")]
        if (not start.get("toolCallId")
                or any(key in start for key in ("mcpServerName", "mcpToolName", "namespacedName"))
                or len(matches) != 1 or matches[0].get("success") is not False
                or "result" in matches[0]
                or matches[0].get("error") != {"code": "failure", "message": "Tool 'edit' does not exist."}
                or receipt.get("protocol_error") != "unexpected_tool"):
            raise StudyError("Failed attempt does not match the retained edit failure and unknown usage")
    elif incident["kind"] == "websocket_closed_1001":
        failures = [event["data"] for event in events if event["type"] == "model.call_failure"]
        mirrors = [event["data"] for event in events if event["type"] == "model.model_call_failure"]
        if len(failures) != 1 or len(mirrors) != 1:
            raise StudyError("Close interruption lacks a unique modern/legacy event pair")
        failure, mirror = failures[0], mirrors[0]
        call = mirror.get("modelCall", {})
        message = failure.get("errorMessage")
        turn = str(mirror.get("turn"))
        starts = [index for index, event in enumerate(events) if event["type"] == "model.call_start"
                  and event["data"].get("turnId") == turn and event["data"].get("model") == "gpt-6.1-sol"]
        finishes = [event for event in events if event["type"] == "model.call_finished"
                    and event["data"].get("turnId") == turn]
        if (failure.get("model") != "gpt-6.1-sol" or failure.get("reasoningEffort") != "medium"
                or failure.get("failureKind") != "transport" or failure.get("transport") != "websocket"
                or failure.get("source") != "top_level" or failure.get("apiEndpoint") != "ws:/responses"
                or not isinstance(message, str)
                or re.fullmatch(r'"WebSocket closed unexpectedly \(request-id: [A-Za-z0-9_-]{1,200}\): 1001 please reconnect"',
                                message) is None
                or failure.get("rte") is not False
                or failure.get("isAuto") is not False or failure.get("isByok") is not False
                or failure.get("retryAttempt") != 0
                or any(key in failure for key in ("apiCallId", "serviceRequestId", "statusCode", "errorCode", "errorType"))
                or not isinstance(call, dict) or call.get("model") != failure["model"]
                or mirror.get("reasoningEffort") != "medium" or mirror.get("rte") is not False
                or call.get("failure_kind") != "transport" or call.get("transport") != "websocket"
                or call.get("rte") is not False or call.get("error") != message
                or call.get("api_endpoint") != failure["apiEndpoint"] or call.get("retry_attempt") != 0
                or any(key in call for key in ("api_id", "service_request_id", "status", "errorCode", "errorType"))
                or len(starts) != 1 or finishes
                or events[-1]["type"] != "model.model_call_failure"
                or receipt.get("protocol_error") != "unexpected_runtime_activity"
                or receipt.get("failure_stage") != "session_send"
                or receipt.get("actual_models") != ["gpt-6.1-sol"]
                or receipt.get("actual_reasoning_efforts") != ["medium"]
                or receipt.get("provider_failures") != [] or receipt.get("routing_changes") != []):
            raise StudyError("Close interruption differs from its pinned signature and unknown-usage receipt")
        failure_index = next(index for index, event in enumerate(events) if event["type"] == "model.call_failure")
        mirror_index = next(index for index, event in enumerate(events) if event["type"] == "model.model_call_failure")
        if not starts[0] < failure_index < mirror_index:
            raise StudyError("Close interruption lacks ordered start, failure and mirror")
    elif incident["kind"] == "websocket_reset":
        failures = [event["data"] for event in events if event["type"] == "model.call_failure"]
        mirrors = [event["data"] for event in events if event["type"] == "model.model_call_failure"]
        if len(failures) != 1 or len(mirrors) != 1:
            raise StudyError("Reset interruption lacks a unique correlated transport failure")
        failure, mirror = failures[0], mirrors[0]
        call = mirror.get("modelCall", {})
        message = '"WebSocket receive failed: WebSocket protocol error: Connection reset without closing handshake [ECONNRESET]"'
        turn = str(mirror.get("turn"))
        starts = [index for index, event in enumerate(events) if event["type"] == "model.call_start"
                  and event["data"].get("turnId") == turn and event["data"].get("model") == "gpt-6.1-sol"]
        finishes = [index for index, event in enumerate(events) if event["type"] == "model.call_finished"
                    and event["data"].get("turnId") == turn and event["data"].get("outcome") == "error"]
        if (failure.get("model") != "gpt-6.1-sol" or failure.get("reasoningEffort") != "medium"
                or failure.get("failureKind") != "transport" or failure.get("transport") != "websocket"
                or failure.get("rte") is not True or failure.get("source") != "top_level"
                or failure.get("apiEndpoint") != "ws:/responses" or failure.get("errorMessage") != message
                or any(key in failure for key in ("statusCode", "errorCode", "errorType"))
                or failure.get("isAuto") is not False or failure.get("isByok") is not False
                or failure.get("retryAttempt") != 0
                or any(not isinstance(failure.get(key), str) or not failure[key]
                       for key in ("apiCallId", "serviceRequestId"))
                or not isinstance(call, dict) or call.get("model") != failure["model"]
                or mirror.get("reasoningEffort") != "medium" or call.get("failure_kind") != "transport"
                or call.get("transport") != "websocket" or call.get("rte") is not True
                or call.get("error") != message or call.get("api_endpoint") != failure["apiEndpoint"]
                or call.get("api_id") != failure["apiCallId"]
                or call.get("service_request_id") != failure["serviceRequestId"]
                or call.get("retry_attempt") != 0
                or any(key in call for key in ("status", "errorCode", "errorType"))
                or len(starts) != 1 or len(finishes) != 1
                or receipt.get("protocol_error") != "unexpected_runtime_activity"
                or receipt.get("failure_stage") != "session_send"
                or receipt.get("actual_models") != ["gpt-6.1-sol"]
                or receipt.get("actual_reasoning_efforts") != ["medium"]
                or receipt.get("provider_failures") != [] or receipt.get("routing_changes") != []):
            raise StudyError("Reset interruption differs from its pinned transport/identity/unknown-usage signature")
        failure_index = next(index for index, event in enumerate(events) if event["type"] == "model.call_failure")
        mirror_index = next(index for index, event in enumerate(events) if event["type"] == "model.model_call_failure")
        if not starts[0] < failure_index < mirror_index < finishes[0]:
            raise StudyError("Reset interruption lacks ordered start, failure, mirror and terminal error")
    else:
        same_turn_retry = incident["kind"] == "backend_503_same_turn"
        status_code = 503 if same_turn_retry else 500
        error_code = "service_unavailable" if same_turn_retry else "internal_error"
        failures = [event["data"] for event in events if event["type"] == "model.call_failure"]
        mirrors = [event["data"] for event in events if event["type"] == "model.model_call_failure"]
        if len(failures) != 1 or len(mirrors) != 1:
            raise StudyError("Failed attempt lacks a unique correlated backend failure")
        failure, mirror = failures[0], mirrors[0]
        call = mirror.get("modelCall", {})
        turn = str(mirror.get("turn"))
        starts = [event["data"] for event in events if event["type"] == "model.call_start"
                  and event["data"].get("turnId") == turn]
        finished = [event["data"] for event in events if event["type"] == "model.call_finished"
                    and event["data"].get("turnId") == turn]
        if (failure.get("model") != "gpt-6.1-sol" or failure.get("reasoningEffort") != "medium"
                or failure.get("statusCode") != status_code or failure.get("failureKind") != "api"
                or failure.get("transport") != "websocket" or failure.get("errorCode") != error_code
                or failure.get("errorType") != "websocket_error" or failure.get("retryAttempt") != 0
                or failure.get("isAuto") is not False or failure.get("isByok") is not False
                or any(not isinstance(failure.get(key), str) or not failure[key]
                       for key in ("apiCallId", "serviceRequestId"))
                or not isinstance(call, dict) or call.get("model") != failure["model"]
                or mirror.get("reasoningEffort") != "medium" or call.get("status") != status_code
                or call.get("api_id") != failure["apiCallId"]
                or call.get("service_request_id") != failure["serviceRequestId"]
                or call.get("errorCode") != failure["errorCode"] or call.get("errorType") != failure["errorType"]
                or call.get("transport") != failure["transport"] or call.get("retry_attempt") != 0
                or len(starts) != (2 if same_turn_retry else 1)
                or any(start.get("model") != failure["model"] for start in starts)
                or (same_turn_retry and bool(finished))
                or (not same_turn_retry and (len(finished) != 1 or finished[0].get("outcome") != "error"))
                or receipt.get("protocol_error") != "unexpected_runtime_activity"):
            raise StudyError("Failed attempt differs from the retained backend signature and unknown usage")
        if same_turn_retry:
            start_indices = [index for index, event in enumerate(events)
                             if event["type"] == "model.call_start" and event["data"].get("turnId") == turn]
            failure_index = next(index for index, event in enumerate(events)
                                 if event["type"] == "model.call_failure")
            mirror_index = next(index for index, event in enumerate(events)
                                if event["type"] == "model.model_call_failure")
            if (not start_indices[0] < failure_index < mirror_index < start_indices[1]
                    or receipt.get("actual_models") != ["gpt-6.1-sol"]
                    or receipt.get("actual_reasoning_efforts") != ["medium"]
                    or receipt.get("provider_failures") != []
                    or receipt.get("routing_changes") != []):
                raise StudyError("Service interruption lacks the exact correlated same-turn retry and pinned identity")
    value = hashlib.sha256(payload).hexdigest()
    if value != incident["journal_sha256"]:
        raise StudyError("Failed attempt journal differs from the disclosed incident")
    return value


def prepare(source_root: Path, old_manifest: dict, new_manifest: dict, approval: dict, *,
            prior_source_root: Path | list[Path] | None = None, calibration_manifest: dict | None = None) -> Path:
    """Copy the stopped study; never alter its original state or release its hold."""
    verify_approval(approval, new_manifest)
    incident = study.recovery_incident(approval["original_state_sha256"])
    original_paid_lock, source = study.recovery_source_paths(
        source_root, expected_state_sha256=approval["original_state_sha256"])
    prior_roots = ([] if prior_source_root is None else [prior_source_root]
                   if isinstance(prior_source_root, Path) else prior_source_root)
    index = study.recovery_state_hashes().index(approval["original_state_sha256"])
    if not isinstance(prior_roots, list) or any(not isinstance(root, Path) for root in prior_roots):
        raise StudyError("Earlier recovery sources must be checkout paths")
    prior_hashes = study.recovery_state_hashes()[:index]
    if index and (len(prior_roots) != index or calibration_manifest is None):
        raise StudyError("Later recovery requires the first original and every earlier checkout and calibration manifest")
    if not index and (prior_roots or calibration_manifest is not None):
        raise StudyError("The first incident must not supply an unrelated recovery source")
    prior_locks = [path for root, state_sha in zip(prior_roots, prior_hashes)
                   for path in study.recovery_source_paths(root, expected_state_sha256=state_sha)]
    calibration_manifest = old_manifest if calibration_manifest is None else calibration_manifest
    calibration = source_root / ".study/excluded-short-calibration-toolfix"
    if any(path.is_symlink() or not path.is_dir()
           for path in (source_root / ".study", source, calibration)):
        raise StudyError("Original estimation or calibration directory is missing or unsafe")
    calibration_lock = calibration / "controller.lock"
    if calibration_lock.is_symlink() or not calibration_lock.is_file():
        raise StudyError("Original calibration lock is missing or unsafe")
    target_root = ROOT / ".study"
    if target_root.is_symlink():
        raise StudyError("Recovery target root must not be a symlink")
    target_root.mkdir(mode=0o700, parents=True, exist_ok=True)
    target = target_root / source.name
    target_calibration = target_root / calibration.name
    if target.exists() or target.is_symlink() or target_calibration.exists() or target_calibration.is_symlink():
        raise StudyError("Recovery never overwrites an existing study or calibration")
    with ExitStack() as locks:
        locks.enter_context(study.paid_study_lock())
        locks.enter_context(study.study_lock(original_paid_lock))
        locks.enter_context(study.study_lock(source))
        for path in prior_locks:
            locks.enter_context(study.study_lock(path))
        locks.enter_context(study.study_lock(calibration))
        study.recovery_source_paths(source_root, expected_state_sha256=approval["original_state_sha256"])
        for root, state_sha in zip(prior_roots, prior_hashes):
            study.recovery_source_paths(root, expected_state_sha256=state_sha)
        state_path = source / "state.json"
        if state_path.is_symlink() or not state_path.is_file():
            raise StudyError("Original state is missing or unsafe")
        original = state_path.read_bytes()
        if hashlib.sha256(original).hexdigest() != approval["original_state_sha256"]:
            raise StudyError("Original state differs from the disclosed stopped state")
        state = json.loads(original)
        identity = state["identity"]
        if (identity["commit"] != incident["source"] or identity["study_id"] != source.name
                or identity["phase"] != "pilot-estimation" or identity["smoke"] is not False
                or identity.get("replicates_per_model_arm") != 21
                or identity.get("source_provenance") != study.source_provenance(old_manifest)
                or old_manifest.get("commit") != incident["source"]
                or old_manifest.get("inputs_sha256") != identity["inputs_sha256"]
                or state.get("status") != "oracle_halt" or state.get("oracle_halt") is not True
                or state.get("stop_requested") or state.get("writer_pending") or state.get("writers")
                or state.get("writer_pid") or state["deadline"] <= time.time()):
            raise StudyError("Original study is not the expected stopped, inactive estimation")
        cfg = identity["config"]
        study.validate_recovery_state(state)
        previous = study.recovery_records(state)
        if index:
            if len(previous) != index:
                raise StudyError("Later recovery must preserve every earlier approved recovery")
            study.validate_recovery_evidence(source, state, old_manifest)
            if study.source_provenance(calibration_manifest)["manifest_sha256"] != previous[0]["prior_manifest_sha256"]:
                raise StudyError("Calibration manifest differs from the first original source")
        elif previous:
            raise StudyError("The first interrupted state must not already be recovered")
        errors = study.preflight(cfg, smoke=False, unregistered=new_manifest)
        if errors:
            raise StudyError("; ".join(errors))
        handoff = study.calibration_handoff(calibration, cfg, calibration_manifest)
        if handoff != state["ledger"].get("calibration_handoff"):
            raise StudyError("Original calibration handoff differs from the saved accounting")
        cells = state["cells"]
        attempts = [item for cell in cells for item in cell["attempts"]]
        entries = state["ledger"]["entries"]
        if (len(cells) != 315 or sum(cell.get("completed_steps", 0) for cell in cells) != incident["steps"]
                or len(attempts) != incident["attempts"]
                or len({item["id"] for item in attempts}) != incident["attempts"]
                or set(entries) != {item["id"] for item in attempts}
                or sum(item["status"] == "complete" for item in entries.values()) != incident["steps"]
                or sum(item["status"] == "unknown" for item in entries.values()) != 1
                or sum(item["status"] == "recovery_hold" for item in entries.values()) != len(previous)
                or sum(item["actual_nano"] for item in entries.values()
                       if item["status"] == "complete") != incident["known_nano"]):
            raise StudyError("Original attempt inventory differs from the disclosed interruption")
        attempt = next(item for item in attempts if item["id"] == incident["attempt"])
        cell = next(cell for cell in cells if attempt in cell["attempts"])
        entry = entries[incident["attempt"]]
        if (attempt.get("status") != "interrupted" or attempt.get("usage") is not None
                or attempt.get("measurement") or entry != {
                    "status": "unknown", "actual_nano": None, "reserved_nano": incident["reserved_nano"]}
                or (cell.get("checkpoint") or {}).get("step") != attempt["step"]
                or any(item["status"] == "running" for item in attempts)):
            raise StudyError("Failed attempt or held reservation is not recoverable")
        verify_approval_after_attempt(approval, attempt)
        journal_sha = verify_journal(source, attempt)
        require_regular_tree(source)
        require_regular_tree(calibration)
        shutil.copytree(source, target, symlinks=True)
        shutil.copytree(calibration, target_calibration, symlinks=True)
        require_regular_tree(target)
        require_regular_tree(target_calibration)
        if hashlib.sha256(state_path.read_bytes()).hexdigest() != approval["original_state_sha256"]:
            raise StudyError("Original state changed during copying; retain the partial recovery copy")
        if (target / "state.json").read_bytes() != original:
            raise StudyError("Copied state differs from the original; retain the partial recovery copy")
        if incident["kind"] == "state_links":
            archive = target / attempt["directory"] / "recovery-broker"
            if archive.exists() or archive.is_symlink():
                raise StudyError("Recovery must not overwrite retained sandbox evidence")
            archive.mkdir(mode=0o700)
            old_broker = target / "runs" / incident["run_id"] / "isolation"
            for name in ("state.json", "latest.state", "owner"):
                shutil.copyfile(old_broker / name, archive / name)
                (archive / name).chmod(0o600)
        if previous:
            suffix = f"-{len(previous):02d}"
            archives = [target / f"state.before-recovery{suffix}.json",
                        target / f"recovery-approval{suffix}.json",
                        target / f"recovery-manifest{suffix}.json"]
            if any(path.exists() or path.is_symlink() for path in archives):
                raise StudyError("Recovery must not overwrite prior approval or state evidence")
            (target / "state.before-recovery.json").rename(archives[0])
            (target / "recovery-approval.json").rename(archives[1])
            atomic_json(archives[2], old_manifest)
        snapshot = target / "state.before-recovery.json"
        with snapshot.open("xb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
        atomic_json(target / "recovery-approval.json", approval)
        prior_ids = [item["id"] for item in attempts]
        for item in attempts:
            item.setdefault("source_commit", incident["source"])
        attempt["status"] = "recovery_interrupted"
        entry["status"] = "recovery_hold"
        identity["commit"] = new_manifest["commit"]
        identity["inputs_sha256"] = new_manifest["inputs_sha256"]
        identity["source_provenance"] = study.source_provenance(new_manifest)
        if previous:
            state["recovery_history"] = previous
        state["recovery"] = {"schema": "estimation-incident-recovery/v1",
                             "original_state_sha256": approval["original_state_sha256"],
                             "original_commit": incident["source"], "target_commit": new_manifest["commit"],
                             "approval_sha256": digest(approval), "prior_manifest_sha256": digest(old_manifest),
                             "journal_sha256": journal_sha, "approved_at": approval["approved_at"],
                             "disclosure_url": approval["disclosure_url"], "prior_attempt_ids": prior_ids}
        state["oracle_halt"] = False
        state["status"] = "partial"
        study.validate_recovery_state(state)
        study.validate_recovery_evidence(target, state, new_manifest)
        atomic_json(target / "state.json", state)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--old-manifest", required=True, type=Path)
    parser.add_argument("--new-manifest", required=True, type=Path)
    parser.add_argument("--approval", required=True, type=Path)
    parser.add_argument("--prior-source-root", type=Path, action="append",
                        help="earlier original checkout; repeat in chronological recovery order")
    parser.add_argument("--calibration-manifest", type=Path,
                        help="first original owner manifest required for the preserved calibration")
    args = parser.parse_args()
    for path in (args.old_manifest, args.new_manifest, args.approval):
        if path.is_symlink() or not path.is_file():
            raise StudyError("Recovery evidence must be regular files, not symlinks")
    if args.calibration_manifest and (
            args.calibration_manifest.is_symlink() or not args.calibration_manifest.is_file()):
        raise StudyError("Calibration evidence must be a regular file, not a symlink")
    target = prepare(args.source_root, read_json(args.old_manifest), read_json(args.new_manifest),
                     read_json(args.approval), prior_source_root=args.prior_source_root,
                     calibration_manifest=read_json(args.calibration_manifest) if args.calibration_manifest else None)
    print(f"Prepared separate recovery copy: {target}; no model sessions were started.")


if __name__ == "__main__":
    try:
        main()
    except (StudyError, OSError, ValueError, KeyError, TypeError) as error:
        message = str(error) if isinstance(error, StudyError) else type(error).__name__
        raise SystemExit(f"Recovery stopped: {message}") from error
