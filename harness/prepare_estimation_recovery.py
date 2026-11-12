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
    quarantine_only = incident["kind"] == "fallback_metadata_quarantine"
    if quarantine_only:
        expected.add("accept_quarantine_only")
    if (set(approval) != expected or approval["schema"] != "estimation-incident-approval/v1"
            or approval["original_commit"] != incident["source"]
            or approval["target_commit"] != new_manifest.get("commit")
            or approval["target_commit"] == incident["source"]
            or approval["attempt_id"] != study.incident_attempt_ref(incident)
            or type(approval["unknown_reservation_nano"]) is not int
            or approval["unknown_reservation_nano"] != incident["reserved_nano"]
                 or any(approval[key] is not True for key in ("accept_unknown_hold",
                     "accept_mid_study_source_change", "owner_approved"))
                 or any(approval[key] is not (not quarantine_only) for key in (
                  "accept_fresh_retry_reservation", "accept_fresh_retry_time_allowance"))
                 or (quarantine_only and approval["accept_quarantine_only"] is not True)
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


def verify_fallback_quarantine(directory: Path, attempt: dict, receipt: dict, events: list[dict], terminal: dict) -> None:
    """Verify the pinned typed failure without reinterpreting unknown billing or accepting its work."""
    failures = [event["data"] for event in events if event["type"] == "model.call_failure"]
    mirrors = [event["data"] for event in events if event["type"] == "model.model_call_failure"]
    outcome = study.validate_attempt_outcome(receipt.get("outcome"))
    if (len(failures) != 2 or len(mirrors) != 2
            or receipt.get("sdk_version") != "1.0.28" or receipt.get("cli_version") != "1.0.105"
            or receipt.get("protocol_version") != 3 or receipt.get("protocol_error") != "unexpected_runtime_activity"
            or receipt.get("actual_models") != ["gpt-6.1-sol"]
            or receipt.get("actual_reasoning_efforts") != ["medium"] or receipt.get("routing_changes") != []
            or receipt.get("usage_lower_bound") is not None or attempt.get("usage") != receipt.get("usage")
            or outcome["work"] != "unavailable" or outcome["safety"] != "unverified"
            or outcome["quiescent"] is not True or outcome["accounting"] != "unknown"
            or outcome["failure"]["kind"] != "contract"
            or events[-1]["type"] != "model.call_finished" or events[-1]["data"].get("outcome") != "error"
            or any(event["type"] in ("session.idle", "session.shutdown") for event in events)):
        raise StudyError("Fallback quarantine lacks its pinned unmeasured, quiescent unknown-charge outcome")
    for retry, (failure, mirror) in enumerate(zip(failures, mirrors)):
        call = mirror.get("modelCall", {})
        if (failure.get("model") != "gpt-6.1-sol" or failure.get("reasoningEffort") != "medium"
                or failure.get("source") != "top_level" or failure.get("failureKind") != "transport"
                or failure.get("transport") != "websocket" or failure.get("retryAttempt") != retry
                or failure.get("isAuto") is not False or failure.get("isByok") is not False
                or failure.get("fusion") or mirror.get("reasoningEffort") != "medium"
                or call.get("model") != failure["model"] or call.get("transport") != failure["transport"]
                or call.get("failure_kind") != "transport" or call.get("error") != failure.get("errorMessage")
                or call.get("retry_attempt") != retry):
            raise StudyError("Fallback quarantine changed assigned identity or failure/mirror evidence")
    fallback = failures[-1]
    if (fallback.get("websocketFallbackAfterMs") != 58933
            or fallback.get("websocketFallbackErrorKind") != "connection_reset"
            or fallback.get("websocketFallbackReason") != "transport_failed"
            or fallback.get("websocketFallbackReconnectAttempted") is not False
            or fallback.get("websocketFallbackStartedThisCall") is not True):
        raise StudyError("Fallback quarantine differs from the documented fallback metadata")
    folder = directory / attempt["directory"]
    path = folder / "terminal.json"
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 2 * 1024 * 1024:
        raise StudyError("Fallback quarantine requires its retained terminal evidence")
    payload = path.read_bytes()
    saved = json.loads(payload)
    if (hashlib.sha256(payload).hexdigest() != attempt.get("terminal_sha256")
            or saved.get("source_commit") != attempt.get("source_commit")
            or saved.get("attempt_id") != attempt["id"] or saved.get("result") != terminal
            or saved.get("request_sha256") != attempt.get("request_sha256")
            or saved.get("events_sha256") != hashlib.sha256((folder / "transport/events.jsonl").read_bytes()).hexdigest()
            or hashlib.sha256((folder / "request.json").read_bytes()).hexdigest() != attempt.get("request_sha256")):
        raise StudyError("Fallback quarantine terminal or request differs from the original evidence")


def verify_journal(directory: Path, attempt: dict, *, preserved_broker: bool = False) -> str:
    incidents = [study.recovery_incident(value) for value in study.recovery_state_hashes()]
    incident = next((item for item in incidents if attempt.get("id") in study.incident_holds(item)), None)
    if incident is None:
        raise StudyError("Failed attempt is not one of the disclosed estimation interruptions")
    expected_journal = study.incident_holds(incident)[attempt["id"]]["journal_sha256"]
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
        if value != expected_journal:
            raise StudyError("Failed attempt journal differs from the disclosed incident")
        return value
    if len(complete) != 1:
        raise StudyError("Failed attempt lacks a unique terminal receipt")
    receipt = complete[0].get("receipt", {})
    unaccounted_retry = incident["kind"] == "websocket_retry_unaccounted"
    if (not isinstance(receipt, dict) or not isinstance(receipt.get("usage"), dict)
            or complete[0].get("exit_code") != 1
            or receipt.get("failure_stage") != (None if unaccounted_retry else "session_send")
            or receipt.get("usage", {}).get("credits_complete") is not False
            or receipt.get("usage", {}).get("totalNanoAiu") is not None):
        raise StudyError("Failed attempt does not retain its terminal failure and unknown usage")
    events = [record["event"] for record in records if "event" in record]
    if incident["kind"] == "fallback_metadata_quarantine":
        verify_fallback_quarantine(directory, attempt, receipt, events, complete[0])
    elif incident["kind"] == "missing_edit":
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
    elif incident["kind"] == "backend_mixed_boundaries":
        failures = [(index, event["data"]) for index, event in enumerate(events)
                    if event["type"] == "model.call_failure"]
        mirrors = [(index, event["data"]) for index, event in enumerate(events)
                   if event["type"] == "model.model_call_failure"]
        if len(failures) != 2 or len(mirrors) != 2:
            raise StudyError("Mixed retry interruption lacks its two failure/mirror pairs")
        turn = str(mirrors[0][1].get("turn"))
        starts = [index for index, event in enumerate(events) if event["type"] == "model.call_start"
                  and event["data"].get("turnId") == turn and event["data"].get("model") == "gpt-6.1-sol"]
        finishes = [(index, event["data"]) for index, event in enumerate(events)
                    if event["type"] == "model.call_finished" and event["data"].get("turnId") == turn]
        for retry, ((_, failure), (_, mirror)) in enumerate(zip(failures, mirrors)):
            call = mirror.get("modelCall", {})
            if (failure.get("model") != "gpt-6.1-sol" or failure.get("reasoningEffort") != "medium"
                    or failure.get("statusCode") != 500 or failure.get("failureKind") != "api"
                    or failure.get("transport") != "websocket" or failure.get("errorCode") != "internal_error"
                    or failure.get("errorType") != "websocket_error" or failure.get("retryAttempt") != retry
                    or failure.get("isAuto") is not False or failure.get("isByok") is not False
                    or any(not isinstance(failure.get(key), str) or not failure[key]
                           for key in ("apiCallId", "serviceRequestId"))
                    or str(mirror.get("turn")) != turn or mirror.get("reasoningEffort") != "medium"
                    or not isinstance(call, dict) or call.get("model") != failure["model"]
                    or call.get("api_id") != failure["apiCallId"]
                    or call.get("service_request_id") != failure["serviceRequestId"]
                    or call.get("status") != 500 or call.get("transport") != "websocket"
                    or call.get("errorCode") != "internal_error" or call.get("errorType") != "websocket_error"
                    or call.get("retry_attempt") != retry):
                raise StudyError("Mixed retry interruption differs from its pinned correlated API failures")
        if (len(starts) != 3 or len(finishes) != 1 or finishes[0][1].get("outcome") != "error"
                or not starts[0] < failures[0][0] < mirrors[0][0] < finishes[0][0] < starts[1]
                < failures[1][0] < mirrors[1][0] < starts[2]
                or len({failure["apiCallId"] for _, failure in failures}) != 2
                or len({failure["serviceRequestId"] for _, failure in failures}) != 2
                or receipt.get("protocol_error") != "unexpected_runtime_activity"
                or receipt.get("failure_stage") != "session_send"
                or receipt.get("actual_models") != ["gpt-6.1-sol"]
                or receipt.get("actual_reasoning_efforts") != ["medium"]
                or receipt.get("routing_changes") != []
                or receipt.get("provider_failures") != [{
                    "status_code": 500, "error_code": "internal_error", "transport": "websocket",
                    "retry_attempt": 0, "accounting_complete": False}]):
            raise StudyError("Mixed retry interruption lacks its exact ordered boundaries and unknown usage")
    elif incident["kind"] == "http_service_unavailable":
        failures = [(index, event["data"]) for index, event in enumerate(events)
                    if event["type"] == "model.call_failure"]
        mirrors = [(index, event["data"]) for index, event in enumerate(events)
                   if event["type"] == "model.model_call_failure"]
        if len(failures) != 1 or len(mirrors) != 1:
            raise StudyError("HTTP interruption lacks a unique failure and mirror")
        (failure_index, failure), (mirror_index, mirror) = failures[0], mirrors[0]
        call = mirror.get("modelCall")
        turn = str(mirror.get("turn"))
        starts = [index for index, event in enumerate(events) if event["type"] == "model.call_start"
                  and event["data"].get("turnId") == turn
                  and event["data"].get("model") == "gemini-4-argon"]
        finishes = [(index, event["data"]) for index, event in enumerate(events)
                    if event["type"] == "model.call_finished" and event["data"].get("turnId") == turn]
        if (failure.get("model") != "gemini-4-argon" or failure.get("reasoningEffort") != "medium"
                or failure.get("statusCode") != 503 or failure.get("failureKind") != "api"
                or failure.get("transport") != "http" or failure.get("apiEndpoint") != "/chat/completions"
                or failure.get("errorMessage") != '"503 Service Unavailable"'
                or failure.get("source") != "top_level" or failure.get("rte") is not False
                or failure.get("isAuto") is not False or failure.get("isByok") is not False
                or failure.get("fusion") or failure.get("retryAttempt") != 0
                or not isinstance(failure.get("providerCallId"), str)
                or not 1 <= len(failure["providerCallId"]) <= 200
                or any(key in failure for key in ("apiCallId", "serviceRequestId", "errorCode", "errorType"))
                or mirror.get("kind") != "model_call_failure" or mirror.get("reasoningEffort") != "medium"
                or mirror.get("rte") is not False or not isinstance(call, dict)
                or call.get("model") != failure["model"] or call.get("status") != 503
                or call.get("transport") != "http" or call.get("failure_kind") != "api"
                or call.get("request_id") != failure["providerCallId"]
                or call.get("api_endpoint") != failure["apiEndpoint"]
                or call.get("error") != failure["errorMessage"]
                or call.get("rte") is not False or call.get("retry_attempt") != 0
                or any(key in call for key in ("api_id", "service_request_id", "errorCode", "errorType"))
                or len(starts) != 1 or len(finishes) != 1 or finishes[0][1].get("outcome") != "error"
                or not starts[0] < failure_index < mirror_index < finishes[0][0]
                or finishes[0][0] != len(events) - 1
                or any(event["type"] in ("session.idle", "session.shutdown") for event in events)
                or receipt.get("sdk_version") != "1.0.28" or receipt.get("cli_version") != "1.0.105"
                or receipt.get("protocol_version") != 3
                or receipt.get("protocol_error") != "unexpected_runtime_activity"
                or receipt.get("actual_models") != ["gemini-4-argon"]
                or receipt.get("actual_reasoning_efforts") != ["medium"]
                or receipt.get("routing_changes") != [] or receipt.get("provider_failures") != []
                or receipt.get("usage_lower_bound") is not None):
            raise StudyError("HTTP interruption differs from its pinned correlated 503 and unknown-usage signature")
    elif incident["kind"] in ("http_stream_timeout", "resilience_bootstrap"):
        bootstrap = incident["kind"] == "resilience_bootstrap"
        duration_ms = 61506 if bootstrap else 600000
        failures = [(index, event["data"]) for index, event in enumerate(events)
                    if event["type"] == "model.call_failure"]
        mirrors = [(index, event["data"]) for index, event in enumerate(events)
                   if event["type"] == "model.model_call_failure"]
        if len(failures) != 1 or len(mirrors) != 1:
            raise StudyError("HTTP timeout lacks a unique failure and mirror")
        (failure_index, failure), (mirror_index, mirror) = failures[0], mirrors[0]
        call = mirror.get("modelCall")
        turn = str(mirror.get("turn"))
        starts = [index for index, event in enumerate(events) if event["type"] == "model.call_start"
                  and event["data"].get("turnId") == turn
                  and event["data"].get("model") == "gemini-4-argon"]
        finishes = [(index, event["data"]) for index, event in enumerate(events)
                    if event["type"] == "model.call_finished" and event["data"].get("turnId") == turn]
        if (failure.get("model") != "gemini-4-argon" or failure.get("reasoningEffort") != "medium"
                or failure.get("failureKind") != "transport" or failure.get("transport") != "http"
                or failure.get("apiEndpoint") != "/chat/completions" or failure.get("source") != "top_level"
                or not isinstance(failure.get("errorMessage"), str)
                or (not bootstrap and failure["errorMessage"] != '"Native model HTTP stream timed out"')
                or failure.get("durationMs") != duration_ms or failure.get("retryAttempt") != 0
                or failure.get("rte") is not False or failure.get("isAuto") is not False
                or failure.get("isByok") is not False or failure.get("fusion")
                or any(key in failure for key in ("providerCallId", "apiCallId", "serviceRequestId",
                                                  "statusCode", "errorCode", "errorType"))
                or mirror.get("kind") != "model_call_failure" or mirror.get("reasoningEffort") != "medium"
                or mirror.get("rte") is not False or mirror.get("modelCallDurationMs") != duration_ms
                or not isinstance(call, dict) or call.get("model") != failure["model"]
                or call.get("request_id") != "" or call.get("api_endpoint") != failure["apiEndpoint"]
                or call.get("transport") != "http" or call.get("failure_kind") != "transport"
                or call.get("error") != failure["errorMessage"]
                or call.get("rte") is not False or call.get("retry_attempt") != 0
                or any(key in call for key in ("api_id", "service_request_id", "status", "errorCode", "errorType"))
                or len(starts) != 1 or len(finishes) != 1 or finishes[0][1].get("outcome") != "error"
                or not starts[0] < failure_index < mirror_index < finishes[0][0]
                or finishes[0][0] != len(events) - 1
                or any(event["type"] in ("session.idle", "session.shutdown") for event in events)
                or receipt.get("sdk_version") != "1.0.28" or receipt.get("cli_version") != "1.0.105"
                or receipt.get("protocol_version") != 3
                or receipt.get("protocol_error") != "unexpected_runtime_activity"
                or receipt.get("actual_models") != ["gemini-4-argon"]
                or receipt.get("actual_reasoning_efforts") != ["medium"]
                or receipt.get("routing_changes") != [] or receipt.get("provider_failures") != []
                or receipt.get("usage_lower_bound") is not None):
            raise StudyError("HTTP timeout differs from its pinned uncorrelated timeout and unknown-usage signature")
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
    elif incident["kind"] in ("websocket_reset", "websocket_retry_unaccounted"):
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
                    and event["data"].get("turnId") == turn
                    and (unaccounted_retry or event["data"].get("outcome") == "error")]
        # The CLI may or may not emit an error finish between a reset and its same-turn retry.
        outcomes = [events[index]["data"].get("outcome") for index in finishes]
        bounded_finishes = (outcomes in (["error", "success"], ["success"]) if unaccounted_retry
                            else len(finishes) == 1)
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
                or len(starts) != (2 if unaccounted_retry else 1) or not bounded_finishes
                or receipt.get("protocol_error") != (
                    "provider_retry_usage_incomplete" if unaccounted_retry else "unexpected_runtime_activity")
                or receipt.get("actual_models") != ["gpt-6.1-sol"]
                or receipt.get("actual_reasoning_efforts") != ["medium"]
                or receipt.get("provider_failures") != ([{
                    "status_code": None, "error_code": None, "failure_kind": "transport",
                    "transport": "websocket", "retry_attempt": 0, "accounting_complete": False
                }] if unaccounted_retry else []) or receipt.get("routing_changes") != []):
            raise StudyError("Reset interruption differs from its pinned transport/identity/unknown-usage signature")
        failure_index = next(index for index, event in enumerate(events) if event["type"] == "model.call_failure")
        mirror_index = next(index for index, event in enumerate(events) if event["type"] == "model.model_call_failure")
        if not unaccounted_retry and not starts[0] < failure_index < mirror_index < finishes[0]:
            raise StudyError("Reset interruption lacks ordered start, failure, mirror and terminal error")
        if unaccounted_retry:
            shutdowns = [(index, event["data"]) for index, event in enumerate(events)
                         if event["type"] == "session.shutdown"]
            idle = [index for index, event in enumerate(events) if event["type"] == "session.idle"]
            usage = [event["data"] for event in events if event["type"] == "assistant.usage"]
            error_finish = finishes[:-1]
            if (not starts[0] < failure_index < mirror_index < starts[1] < finishes[-1]
                    or any(not mirror_index < index < starts[1] for index in error_finish)
                    or len(shutdowns) != 1 or shutdowns[0][1].get("shutdownType") != "routine"
                    or len(idle) != 1 or not finishes[-1] < idle[0] < shutdowns[0][0]
                    or not usage
                    or any(item.get("apiCallId") == failure["apiCallId"]
                           and item.get("serviceRequestId") == failure["serviceRequestId"]
                           for item in usage)):
                raise StudyError("Unaccounted retry lacks its successful finish and missing failed-request charge")
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
    if value != expected_journal:
        raise StudyError("Failed attempt journal differs from the disclosed incident")
    return value


def prepare(source_root: Path, old_manifest: dict, new_manifest: dict, approval: dict, *,
            prior_source_root: Path | list[Path] | None = None, calibration_manifest: dict | None = None) -> Path:
    """Copy the stopped study; never alter its original state or release its hold."""
    verify_approval(approval, new_manifest)
    incident = study.recovery_incident(approval["original_state_sha256"])
    holds = study.incident_holds(incident)
    quarantine_only = incident["kind"] == "fallback_metadata_quarantine"
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
        study.validate_supervisor_state(source, state, old_manifest)
        previous = study.recovery_records(state)
        previous_holds = sum(len(study.incident_holds(study.recovery_incident(item["original_state_sha256"])))
                             for item in previous)
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
                or sum(item["status"] in ("complete", study.RETRY_HOLD) for item in entries.values())
                != incident["steps"]
                or sum(item["status"] == "unknown" for item in entries.values()) != len(holds)
                or sum(item["status"] == "recovery_hold" for item in entries.values()) != previous_holds
                or sum(item["actual_nano"] if item["status"] == "complete" else item.get("lower_bound_nano", 0)
                       for item in entries.values()
                       if item["status"] in ("complete", study.RETRY_HOLD)) != incident["known_nano"]):
            raise StudyError("Original attempt inventory differs from the disclosed interruption")
        held_attempts = {}
        for held_id, hold in holds.items():
            attempt = next(item for item in attempts if item["id"] == held_id)
            cell = next(cell for cell in cells if attempt in cell["attempts"])
            if (attempt.get("status") != "interrupted"
                    or (attempt.get("usage") is not None and not quarantine_only)
                    or attempt.get("measurement") or entries[held_id] != {
                        "status": "unknown", "actual_nano": None, "reserved_nano": hold["reserved_nano"]}
                    or (cell.get("checkpoint") or {}).get("step") != attempt["step"]
                    or any(item["status"] == "running" for item in attempts)):
                raise StudyError("Failed attempt or held reservation is not recoverable")
            verify_approval_after_attempt(approval, attempt)
            held_attempts[held_id] = attempt
        verified = {held_id: verify_journal(source, held) for held_id, held in held_attempts.items()}
        journal_sha = study.incident_journal_digest(incident, verified)
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
            attempt = held_attempts[incident["attempt"]]
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
        for held_id in holds:
            held_attempts[held_id]["status"] = "recovery_interrupted"
            entries[held_id]["status"] = "recovery_hold"
            if quarantine_only:
                cell = next(cell for cell in cells if held_attempts[held_id] in cell["attempts"])
                cell["status"] = "quarantined"
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
        study.validate_supervisor_state(target, state, new_manifest)
        atomic_json(target / "state.json", state)
    return target


def verify_operational_approval(approval: dict, state: dict, manifest: dict, payload: bytes) -> None:
    """Bind same-source recovery to one stopped state and an explicit prospective policy."""
    fields = {"schema", "state_sha256", "source_commit", "manifest_sha256", "attempts",
              "owner_approved", "approval", "approved_at"}
    if (set(approval) != fields or approval["schema"] != "study-operational-approval/v1"
            or approval["owner_approved"] is not True
            or approval["state_sha256"] != hashlib.sha256(payload).hexdigest()
            or approval["source_commit"] != state["identity"]["commit"]
            or approval["source_commit"] != manifest.get("commit")
            or approval["manifest_sha256"] != digest(manifest)
            or state["identity"].get("source_provenance") != study.source_provenance(manifest)
            or not isinstance(approval["approval"], str) or not approval["approval"].strip()
            or not isinstance(approval["attempts"], dict) or not approval["attempts"]
            or any(not isinstance(key, str) or not isinstance(value, str)
                   or re.fullmatch(r"[0-9a-f]{64}", value) is None
                   for key, value in approval["attempts"].items())
            or not study.resilience_policy(manifest)):
        raise StudyError("Same-source recovery requires exact state, manifest, terminal hashes and owner approval")
    try:
        approved = datetime.fromisoformat(approval["approved_at"])
        if approved.utcoffset() is None or approved.timestamp() > time.time():
            raise ValueError("Invalid approval time")
    except (TypeError, ValueError, OverflowError) as error:
        raise StudyError("Operational recovery requires a nonfuture timezone-aware approval") from error


def validate_operational_recoveries(directory: Path, state: dict, manifest: dict) -> None:
    """Require every same-source transition's original state and immutable owner authorization."""
    seen = set()
    for index, record in enumerate(state["operational_recoveries"]):
        original_sha = record.get("state_sha256")
        if (record.get("schema") != "study-operational-recovery/v1"
                or not isinstance(original_sha, str) or re.fullmatch(r"[0-9a-f]{64}", original_sha) is None
                or original_sha in seen or record.get("source_commit") != state["identity"]["commit"]):
            raise StudyError("Invalid same-source operational recovery history")
        seen.add(original_sha)
        root = directory / "operational-recovery" / original_sha
        paths = (root.parent, root, root / "before.json", root / "approval.json")
        if any(path.is_symlink() or not path.exists() for path in paths):
            raise StudyError("Operational recovery audit evidence is missing or unsafe")
        payload = (root / "before.json").read_bytes()
        before, approval = json.loads(payload), read_json(root / "approval.json")
        verify_operational_approval(approval, before, manifest, payload)
        if (record.get("approval_sha256") != digest(approval)
                or record.get("attempts") != approval["attempts"]
            or before.get("operational_recoveries", []) != state["operational_recoveries"][:index]
                or before["identity"] != state["identity"] or before["started"] != state["started"]
                or before["deadline"] != state["deadline"]
                or any(before["ledger"].get(key) != state["ledger"].get(key)
                       for key in ("ceiling_nano", "prior_nano", "historical_credit_provisions", "calibration_handoff"))):
            raise StudyError("Operational recovery changed source, budget, calibration or deadline")
        if len(before["cells"]) != len(state["cells"]):
            raise StudyError("Operational recovery changed the original allocation")
        for old_cell, current_cell in zip(before["cells"], state["cells"]):
            fixed = ("run_id", "arm", "features", "change_request", "assigned_model", "replicate", "analysis_design")
            if (any(old_cell.get(key) != current_cell.get(key) for key in fixed)
                    or current_cell.get("completed_steps", 0) < old_cell.get("completed_steps", 0)
                    or (old_cell["status"] == "completed" and current_cell["status"] != "completed")
                    or len(current_cell["attempts"]) < len(old_cell["attempts"])):
                raise StudyError("Operational recovery lost original progress or attempts")
            for old_attempt, current_attempt in zip(old_cell["attempts"], current_cell["attempts"]):
                key = old_attempt["id"]
                immutable = ("id", "step", "started", "seconds_limit", "credit_limit_nano", "directory",
                             "request_sha256", "source_commit", "parallelism")
                if any(old_attempt.get(field) != current_attempt.get(field) for field in immutable):
                    raise StudyError("Operational recovery changed an original attempt or allowance")
                old_entry = before["ledger"]["entries"][key]
                new_entry = state["ledger"]["entries"][key]
                if (old_entry["reserved_nano"] != new_entry["reserved_nano"]
                        or (key not in approval["attempts"] and old_entry != new_entry)
                        or (old_attempt.get("cost_included_in_step") and not current_attempt.get("cost_included_in_step"))):
                    raise StudyError("Operational recovery changed an original reservation or included cost")


def prepare_operational(directory: Path, manifest: dict, approval: dict, *, apply: bool = False) -> dict:
    """Validate or commit same-source failure supervision without copying data or calling a model."""
    if directory.is_symlink() or directory.absolute() != directory.resolve():
        raise StudyError("Operational recovery directory must not contain symlink components")
    with ExitStack() as locks:
        if apply:
            locks.enter_context(study.paid_study_lock())
            locks.enter_context(study.study_lock(directory))
        state_path = directory / "state.json"
        if state_path.is_symlink() or not state_path.is_file():
            raise StudyError("Operational recovery requires the original regular state file")
        payload = state_path.read_bytes()
        state = json.loads(payload)
        verify_operational_approval(approval, state, manifest, payload)
        if (state["identity"]["smoke"] is not False
                or manifest.get("commit") != study.command(["git", "rev-parse", "HEAD"])
                or state["identity"]["inputs_sha256"] != manifest.get("inputs_sha256")
                or manifest.get("inputs_sha256") != study.fingerprint()
                or state.get("oracle_halt") or state.get("stop_requested")
                or state.get("writer_pending") or state.get("writer_pid")
                or state.get("status") not in ("partial", "interrupted") or time.time() >= state["deadline"]):
            raise StudyError("Same-source recovery cannot override safety, source, stop or deadline gates")
        selected = approval["attempts"]
        inventory = {attempt["id"]: (cell, attempt) for cell in state["cells"] for attempt in cell["attempts"]}
        if (set(inventory) != set(state["ledger"]["entries"]) or not set(selected).issubset(inventory)
                or any(attempt["status"] == "running" and key not in selected
                       for key, (cell, attempt) in inventory.items())):
            raise StudyError("Operational recovery must preserve and reconcile every interrupted attempt")
        selected_cells = {inventory[key][0]["run_id"] for key in selected}
        if len(selected_cells) != len(selected):
            raise StudyError("Operational recovery selects at most the latest attempt of each cell")
        for key, writer in state.get("writers", {}).items():
            if (key not in selected_cells or writer.get("pending") is not False
                    or type(writer.get("pid")) is not int or writer["pid"] <= 0
                    or study.group_alive(writer["pid"])):
                raise StudyError("Operational recovery requires quiescent, independently identified writers")
        actions = []
        for key, terminal_sha in selected.items():
            cell, attempt = inventory[key]
            if (attempt is not cell["attempts"][-1] or attempt.get("measurement")
                    or attempt.get("cost_included_in_step") or attempt.get("supervision")
                    or attempt.get("status") not in ("running", "interrupted", "infra_failed")
                    or (cell.get("checkpoint") or {}).get("step") != attempt["step"]):
                raise StudyError("Operational recovery cannot discard returned or measured work")
            terminal = study.supervised_terminal(directory, attempt, cell["assigned_model"],
                                                  state["identity"]["commit"], expected_sha256=terminal_sha)
            receipt = terminal["result"]["receipt"]
            if receipt["outcome"]["work"] == "complete":
                raise StudyError("Completed work requires retained-snapshot measurement recovery, never agent replay")
            verify_approval_after_attempt(approval, dict(attempt, seconds=terminal["seconds"]))
            seconds = attempt.get("seconds")
            if seconds is None:
                seconds = terminal["seconds"]
            elif type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < terminal["seconds"]:
                raise StudyError("Operational recovery cannot reduce the original attempt duration")
            attempt.update(status="infra_failed", usage=receipt.get("usage"), seconds=seconds,
                           outcome=receipt["outcome"], terminal_sha256=terminal_sha)
            study.reconcile(state["ledger"], key, attempt["usage"])
            state.setdefault("writers", {}).pop(cell["run_id"], None)
            cell["status"] = "partial"
            study.supervise_failure_state(directory, state, manifest, cell, attempt)
            actions.append({"attempt_id": key, "action": attempt["supervision"]["action"]})
        record = {"schema": "study-operational-recovery/v1", "state_sha256": approval["state_sha256"],
                  "source_commit": approval["source_commit"], "approval_sha256": digest(approval),
                  "attempts": selected}
        state.setdefault("operational_recoveries", []).append(record)
        state["status"] = "partial"
        summary = {"schema": "study-operational-recovery-preview/v1", "applied": apply,
                   "state_sha256": approval["state_sha256"], "actions": actions}
        if not apply:
            return summary
        archive = directory / "operational-recovery" / approval["state_sha256"]
        if archive.parent.is_symlink() or archive.is_symlink():
            raise StudyError("Operational audit directory must not be a symlink")
        archive.mkdir(parents=True, mode=0o700, exist_ok=True)
        for name, contents in (("before.json", payload),
                               ("approval.json", (json.dumps(approval, sort_keys=True) + "\n").encode())):
            path = archive / name
            if path.exists() or path.is_symlink():
                if path.is_symlink() or not path.is_file() or path.read_bytes() != contents:
                    raise StudyError("Operational recovery never overwrites different audit evidence")
                continue
            with path.open("xb") as stream:
                os.fchmod(stream.fileno(), 0o600)
                stream.write(contents)
                stream.flush()
                os.fsync(stream.fileno())
        for path in (archive, archive.parent):
            descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
        study.validate_supervisor_state(directory, state, manifest)
        if state_path.read_bytes() != payload:
            raise StudyError("Stopped state changed during operational recovery")
        atomic_json(state_path, state)
        return summary


def create_parser() -> argparse.ArgumentParser:
    """Keep historical copy recovery separate from explicit same-source operational recovery."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--old-manifest", type=Path)
    parser.add_argument("--new-manifest", type=Path)
    parser.add_argument("--approval", required=True, type=Path)
    parser.add_argument("--operational-study", type=Path, help="same-source study; validation only unless --apply")
    parser.add_argument("--manifest", type=Path, help="unchanged prospective owner manifest")
    parser.add_argument("--apply", action="store_true", help="commit the approved same-source data transition")
    parser.add_argument("--prior-source-root", type=Path, action="append",
                        help="earlier original checkout; repeat in chronological recovery order")
    parser.add_argument("--calibration-manifest", type=Path,
                        help="first original owner manifest required for the preserved calibration")
    return parser


def main() -> None:
    parser = create_parser()
    args = parser.parse_args()
    if args.operational_study:
        if (not args.manifest or args.source_root or args.old_manifest or args.new_manifest
                or args.prior_source_root or args.calibration_manifest):
            parser.error("--operational-study requires --manifest and cannot change source or calibration")
        for path in (args.manifest, args.approval):
            if path.is_symlink() or not path.is_file():
                raise StudyError("Operational recovery evidence must be regular files")
        print(json.dumps(prepare_operational(args.operational_study, read_json(args.manifest),
                                              read_json(args.approval), apply=args.apply), indent=2))
        return
    if not all((args.source_root, args.old_manifest, args.new_manifest)) or args.manifest or args.apply:
        parser.error("Historical recovery requires --source-root, --old-manifest and --new-manifest")
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
