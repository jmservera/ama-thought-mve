"""Prepare a separate, owner-authorized copy of the interrupted estimation study."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
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
    if (set(approval) != expected or approval["schema"] != "estimation-incident-approval/v1"
            or approval["original_state_sha256"] != study.RECOVERY_STATE_SHA256
            or approval["original_commit"] != study.RECOVERY_SOURCE
            or approval["target_commit"] != new_manifest.get("commit")
            or approval["target_commit"] == study.RECOVERY_SOURCE
            or approval["attempt_id"] != study.RECOVERY_ATTEMPT
            or type(approval["unknown_reservation_nano"]) is not int
            or approval["unknown_reservation_nano"] != 300 * study.NANO
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


def verify_journal(directory: Path, attempt: dict) -> str:
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
    starts = [record["event"]["data"] for record in records
              if record.get("event", {}).get("type") == "tool.execution_start"
              and record["event"].get("data", {}).get("toolName") == "edit"]
    complete = [record for record in records if record.get("type") == "complete"]
    if len(starts) != 1 or len(complete) != 1:
        raise StudyError("Failed attempt lacks a unique edit call and terminal receipt")
    start = starts[0]
    matches = [record["event"]["data"] for record in records
               if record.get("event", {}).get("type") == "tool.execution_complete"
               and record["event"].get("data", {}).get("toolCallId") == start.get("toolCallId")]
    receipt = complete[0].get("receipt", {})
    if (not start.get("toolCallId")
            or any(key in start for key in ("mcpServerName", "mcpToolName", "namespacedName"))
            or len(matches) != 1 or matches[0].get("success") is not False
            or "result" in matches[0]
            or matches[0].get("error") != {"code": "failure", "message": "Tool 'edit' does not exist."}
            or complete[0].get("exit_code") != 1
            or receipt.get("protocol_error") != "unexpected_tool"
            or receipt.get("failure_stage") != "session_send"
            or receipt.get("usage", {}).get("credits_complete") is not False
            or receipt.get("usage", {}).get("totalNanoAiu") is not None):
        raise StudyError("Failed attempt does not match the retained edit failure and unknown usage")
    value = hashlib.sha256(payload).hexdigest()
    if value != study.RECOVERY_JOURNAL_SHA256:
        raise StudyError("Failed attempt journal differs from the disclosed incident")
    return value


def prepare(source_root: Path, old_manifest: dict, new_manifest: dict, approval: dict) -> Path:
    """Copy the stopped study; never alter its original state or release its hold."""
    verify_approval(approval, new_manifest)
    original_paid_lock, source = study.recovery_source_paths(source_root)
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
        locks.enter_context(study.study_lock(calibration))
        study.recovery_source_paths(source_root)
        state_path = source / "state.json"
        if state_path.is_symlink() or not state_path.is_file():
            raise StudyError("Original state is missing or unsafe")
        original = state_path.read_bytes()
        if hashlib.sha256(original).hexdigest() != study.RECOVERY_STATE_SHA256:
            raise StudyError("Original state differs from the disclosed stopped state")
        state = json.loads(original)
        identity = state["identity"]
        if (identity["commit"] != study.RECOVERY_SOURCE or identity["study_id"] != source.name
                or identity["phase"] != "pilot-estimation" or identity["smoke"] is not False
                or identity.get("replicates_per_model_arm") != 21
                or identity.get("source_provenance") != study.source_provenance(old_manifest)
                or old_manifest.get("commit") != study.RECOVERY_SOURCE
                or old_manifest.get("inputs_sha256") != identity["inputs_sha256"]
                or state.get("status") != "oracle_halt" or state.get("oracle_halt") is not True
                or state.get("stop_requested") or state.get("writer_pending") or state.get("writers")
                or state.get("writer_pid") or state["deadline"] <= time.time()):
            raise StudyError("Original study is not the expected stopped, inactive estimation")
        cfg = identity["config"]
        errors = study.preflight(cfg, smoke=False, unregistered=new_manifest)
        if errors:
            raise StudyError("; ".join(errors))
        handoff = study.calibration_handoff(calibration, cfg, old_manifest)
        if handoff != state["ledger"].get("calibration_handoff"):
            raise StudyError("Original calibration handoff differs from the saved accounting")
        cells = state["cells"]
        attempts = [item for cell in cells for item in cell["attempts"]]
        entries = state["ledger"]["entries"]
        if (len(cells) != 315 or sum(cell.get("completed_steps", 0) for cell in cells) != 651
                or len(attempts) != 652 or len({item["id"] for item in attempts}) != 652
                or set(entries) != {item["id"] for item in attempts}
                or sum(item["status"] == "complete" for item in entries.values()) != 651
                or sum(item["status"] == "unknown" for item in entries.values()) != 1
                or sum(item["actual_nano"] for item in entries.values()
                       if item["status"] == "complete") != study.credits("7794.8031")):
            raise StudyError("Original attempt inventory differs from the disclosed interruption")
        attempt = next(item for item in attempts if item["id"] == study.RECOVERY_ATTEMPT)
        cell = next(cell for cell in cells if attempt in cell["attempts"])
        entry = entries[study.RECOVERY_ATTEMPT]
        if (attempt.get("status") != "interrupted" or attempt.get("usage") is not None
                or attempt.get("measurement") or entry != {
                    "status": "unknown", "actual_nano": None, "reserved_nano": 300 * study.NANO}
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
        if hashlib.sha256(state_path.read_bytes()).hexdigest() != study.RECOVERY_STATE_SHA256:
            raise StudyError("Original state changed during copying; retain the partial recovery copy")
        if (target / "state.json").read_bytes() != original:
            raise StudyError("Copied state differs from the original; retain the partial recovery copy")
        snapshot = target / "state.before-recovery.json"
        with snapshot.open("xb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(original)
            stream.flush()
            os.fsync(stream.fileno())
        atomic_json(target / "recovery-approval.json", approval)
        prior_ids = [item["id"] for item in attempts]
        for item in attempts:
            item["source_commit"] = study.RECOVERY_SOURCE
        attempt["status"] = "recovery_interrupted"
        entry["status"] = "recovery_hold"
        identity["commit"] = new_manifest["commit"]
        identity["inputs_sha256"] = new_manifest["inputs_sha256"]
        identity["source_provenance"] = study.source_provenance(new_manifest)
        state["recovery"] = {"schema": "estimation-incident-recovery/v1",
                             "original_state_sha256": study.RECOVERY_STATE_SHA256,
                             "original_commit": study.RECOVERY_SOURCE, "target_commit": new_manifest["commit"],
                             "approval_sha256": digest(approval), "prior_manifest_sha256": digest(old_manifest),
                             "journal_sha256": journal_sha, "approved_at": approval["approved_at"],
                             "disclosure_url": approval["disclosure_url"], "prior_attempt_ids": prior_ids}
        state["oracle_halt"] = False
        state["status"] = "partial"
        study.validate_recovery_state(state)
        atomic_json(target / "state.json", state)
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--old-manifest", required=True, type=Path)
    parser.add_argument("--new-manifest", required=True, type=Path)
    parser.add_argument("--approval", required=True, type=Path)
    args = parser.parse_args()
    for path in (args.old_manifest, args.new_manifest, args.approval):
        if path.is_symlink() or not path.is_file():
            raise StudyError("Recovery evidence must be regular files, not symlinks")
    target = prepare(args.source_root, read_json(args.old_manifest), read_json(args.new_manifest),
                     read_json(args.approval))
    print(f"Prepared separate recovery copy: {target}; no model sessions were started.")


if __name__ == "__main__":
    try:
        main()
    except (StudyError, OSError, ValueError, KeyError, TypeError) as error:
        message = str(error) if isinstance(error, StudyError) else type(error).__name__
        raise SystemExit(f"Recovery stopped: {message}") from error
