"""Owner-attested intervention coverage for completed trajectories; never inferred."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import time
from datetime import datetime
from pathlib import Path

from study_io import StudyError, atomic_json

SCOPE_FILE = "intervention-scope-state.json"
COVERAGE_FILE = "intervention-coverage.json"


def regular_payload(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 64 * 1024 * 1024:
        raise StudyError("Intervention evidence must be a bounded regular file")
    return path.read_bytes()


def validate(coverage: dict, payload: bytes, current: dict) -> dict[str, bool]:
    keys = {"schema", "study_id", "state_sha256", "owner_attested", "attested_at",
            "evidence_reference", "unassisted_run_ids", "assisted_run_ids"}
    if (set(coverage) != keys or coverage["schema"] != "intervention-coverage/v1"
            or coverage["owner_attested"] is not True
            or coverage["state_sha256"] != hashlib.sha256(payload).hexdigest()
            or not isinstance(coverage["evidence_reference"], str)
            or not coverage["evidence_reference"].strip()):
        raise StudyError("Intervention coverage requires explicit owner evidence for the exact snapshot")
    snapshot = json.loads(payload)
    if not isinstance(snapshot, dict):
        raise StudyError("Invalid intervention scope snapshot")
    old_identity, new_identity = dict(snapshot["identity"]), dict(current["identity"])
    for key in ("commit", "inputs_sha256", "source_provenance"):
        old_identity.pop(key, None)
        new_identity.pop(key, None)
    if (old_identity != new_identity or snapshot["identity"]["smoke"] is not False
            or coverage["study_id"] != current["identity"]["study_id"]):
        raise StudyError("Intervention evidence differs from the study allocation or identity")
    try:
        attested = datetime.fromisoformat(coverage["attested_at"])
        if attested.utcoffset() is None or attested.timestamp() > time.time():
            raise ValueError("Invalid attestation time")
    except (TypeError, ValueError, OverflowError) as error:
        raise StudyError("Intervention attestation requires a nonfuture timezone-aware time") from error
    mapping = {}
    for key, assisted in (("unassisted_run_ids", False), ("assisted_run_ids", True)):
        values = coverage[key]
        if (not isinstance(values, list) or any(not isinstance(value, str)
                or ".." in value
                or not re.fullmatch(r"[a-z][A-Za-z0-9.-]{0,127}", value) for value in values)):
            raise StudyError("Invalid intervention trajectory inventory")
        for value in values:
            if value in mapping:
                raise StudyError("Intervention inventories must be disjoint and unique")
            mapping[value] = assisted
    completed = {cell["run_id"]: cell for cell in snapshot["cells"] if cell["status"] == "completed"}
    if not completed or set(mapping) != set(completed):
        raise StudyError("Every completed trajectory in the scope must have an explicit disposition")
    cells = {cell["run_id"]: cell for cell in current["cells"]}
    for identity, before in completed.items():
        after = cells.get(identity)
        if (after is None or after["status"] != "completed"
                or before.get("completed_steps") != after.get("completed_steps")
                or before["attempts"] != after["attempts"]):
            raise StudyError("Intervention scope cannot cover new or changed trajectory observations")
        for attempt in before["attempts"]:
            started, seconds = attempt.get("started"), attempt.get("seconds")
            if (type(started) not in (int, float) or type(seconds) not in (int, float)
                    or not math.isfinite(started) or not math.isfinite(seconds) or seconds < 0
                    or started + seconds > attested.timestamp()):
                raise StudyError("Intervention attestation must follow all covered attempts")
    return mapping


def apply(directory: Path, state: dict, runs: list[dict]) -> tuple[list[dict], dict]:
    coverage_path, scope_path = directory / COVERAGE_FILE, directory / SCOPE_FILE
    if not coverage_path.exists() and not scope_path.exists() \
            and not coverage_path.is_symlink() and not scope_path.is_symlink():
        return runs, {"status": "unavailable", "reason": "No operator intervention attestation supplied"}
    payload = regular_payload(scope_path)
    coverage_payload = regular_payload(coverage_path)
    coverage = json.loads(coverage_payload)
    if not isinstance(coverage, dict):
        raise StudyError("Intervention coverage must be an object")
    mapping = validate(coverage, payload, state)
    digest = hashlib.sha256(coverage_payload).hexdigest()
    augmented = []
    seen = set()
    for run in runs:
        meta = run["meta"]
        identity = meta["run_id"]
        if identity in mapping:
            seen.add(identity)
            old = meta.get("intervention") or {}
            assisted = mapping[identity]
            if old.get("assisted") is True and assisted is False:
                raise StudyError("Owner coverage must not erase logged content assistance")
            meta = {**meta, "intervention": {"coverage_complete": True, "assisted": assisted,
                                            "evidence": f"{COVERAGE_FILE} SHA-256 {digest}"}}
            run = {**run, "meta": meta}
        augmented.append(run)
    if seen != set(mapping):
        raise StudyError("Intervention scope differs from the raw reporting frame")
    return augmented, {"status": "owner-attested", "manifest_sha256": digest,
                       "scope_state_sha256": coverage["state_sha256"],
                       "attested_at": coverage["attested_at"], "covered_trajectories": len(mapping),
                       "assisted_trajectories": sum(mapping.values())}


def record(directory: Path, attestation: Path) -> None:
    from study import study_lock

    if directory.is_symlink() or not directory.is_dir():
        raise StudyError("Intervention study directory is missing or unsafe")
    coverage = json.loads(regular_payload(attestation))
    if not isinstance(coverage, dict):
        raise StudyError("Intervention attestation must be an object")
    with study_lock(directory):
        payload = regular_payload(directory / "state.json")
        validate(coverage, payload, json.loads(payload))
        scope, target = directory / SCOPE_FILE, directory / COVERAGE_FILE
        if any(path.exists() or path.is_symlink() for path in (scope, target)):
            raise StudyError("Retain existing intervention evidence; never overwrite it")
        with scope.open("xb") as stream:
            os.fchmod(stream.fileno(), 0o600)
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        atomic_json(target, coverage)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study-directory", required=True, type=Path)
    parser.add_argument("--attestation", required=True, type=Path)
    args = parser.parse_args()
    record(args.study_directory, args.attestation)
    print("Owner intervention coverage recorded; original observations are unchanged. No model calls started.")


if __name__ == "__main__":
    try:
        main()
    except (StudyError, OSError, ValueError, KeyError, TypeError) as error:
        message = str(error) if isinstance(error, StudyError) else type(error).__name__
        raise SystemExit(f"Intervention coverage stopped: {message}") from error
