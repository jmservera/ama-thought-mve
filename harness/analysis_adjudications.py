"""Bounded reporting-time overlay correcting known-safe hidden-test attribution gaps.

A prior evaluator conservatively left some declared candidate exceptions raised from
``__getattr__``/``__getattribute__`` traps as an unattributed ``error`` instead of the
genuine ``failed`` outcome they represent (see failure_attribution.py). This module applies
a hash-bound, owner-supplied manifest of trusted, read-only historical reevaluations -
each reevaluation reruns only the hidden-test harness for one retained, immutable
candidate snapshot with the corrected helper, never the agent or the candidate itself -
and reclassifies exactly those matching ``error`` outcomes to ``failed`` in an in-memory
copy of the affected records. Original files, unrelated outcomes, costs, snapshots and
attempt history are never modified; everything else in a corrected record is preserved
byte-for-byte. Reevaluated metrics/diff are not independently recomputed: the trusted
audit preserves the original record's metrics/diff verbatim and only its hidden-test
outcomes and provenance are replaced, so this module validates that those fields stay
identical rather than claiming they were reevaluated. Without a manifest, this module
changes nothing - the only case that does not raise. A present manifest is applied
atomically: every structural/identity claim and every individual entry must be fully and
provably correct, or the whole call raises StudyError and nothing is applied; there is no
silent partial result and no silently skipped entry.
"""
from __future__ import annotations

import copy
import hashlib
import json
import posixpath
import re
from pathlib import Path, PurePosixPath

from study_io import StudyError

SCHEMA = "analysis-adjudications/v1"
REASON = "hidden-test attribution reevaluation; original metrics preserved"
MANIFEST_FILE = "analysis-adjudications.json"
DEFAULT_SCOPE_STATE_NAME = "state.before-recovery.json"
HELPER_PATH = Path(__file__).resolve().with_name("failure_attribution.py")
MAX_EVIDENCE_BYTES = 64 * 1024 * 1024

SHA256_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")
IMAGE_RE = re.compile(r"sha256:[0-9a-f]{64}")

REQUIRED_MANIFEST_KEYS = {"schema", "study_id", "scope_state_sha256", "execution_source_commit",
                          "runtime_image", "attribution_helper_sha256", "entries"}
OPTIONAL_MANIFEST_KEYS = {"scope_state_file"}
REQUIRED_ENTRY_KEYS = {"run_id", "step", "original_record_sha256", "snapshot_head", "audit_path", "audit_sha256"}
NONPASS_OUTCOMES = ("passed", "failed", "error", "skipped", "timeout")

# Identity fields a continuing, qualified-source study is explicitly allowed to differ in.
IDENTITY_VOLATILE_KEYS = ("commit", "inputs_sha256", "source_provenance")
# Fixed per-cell allocation; attempts/status/checkpoint evolve and are checked separately.
ALLOCATION_KEYS = ("run_id", "arm", "features", "change_request", "assigned_model",
                   "analysis_design", "replicate", "replicates_per_model_arm")


def matches(pattern: re.Pattern, value: object) -> bool:
    return isinstance(value, str) and pattern.fullmatch(value) is not None


def canonical_sha256(value: object) -> str:
    """Hash the canonical sorted compact JSON form, never raw source bytes or key order."""
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def regular_payload(path: Path, *, max_bytes: int = MAX_EVIDENCE_BYTES) -> bytes:
    """Require a bounded, non-symlinked regular file; never follow a link to read evidence."""
    if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
        raise StudyError("Analysis adjudication evidence must be a bounded regular file")
    return path.read_bytes()


def safe_relative_path(directory: Path, relative: object) -> Path | None:
    """Resolve contained regular evidence without following any symlink component."""
    if not isinstance(relative, str) or not relative:
        return None
    candidate = PurePosixPath(relative)
    if candidate.is_absolute() or ".." in candidate.parts or "\\" in relative:
        return None
    target = directory / relative
    try:
        component = directory
        for part in candidate.parts:
            component = component / part
            if component.is_symlink():
                return None
        if target.is_symlink() or not target.is_file():
            return None
        if not target.resolve().is_relative_to(directory.resolve()):
            return None
    except OSError:
        return None
    return target


def read_bounded(path: Path, *, max_bytes: int = MAX_EVIDENCE_BYTES) -> bytes | None:
    """Return bounded entry evidence; the caller rejects an unreadable entry explicitly."""
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > max_bytes:
            return None
        return path.read_bytes()
    except OSError:
        return None


def current_helper_sha256() -> str | None:
    """Hash the live, parent-owned attribution helper exactly as it stands on disk now."""
    try:
        payload = regular_payload(HELPER_PATH)
    except StudyError:
        return None
    return hashlib.sha256(payload).hexdigest()


def validate_manifest_shape(manifest: object) -> None:
    """Reject anything but the exact declared manifest shape; never guess at a looser schema."""
    if not isinstance(manifest, dict):
        raise StudyError("Analysis adjudication manifest must be an object")
    keys = set(manifest)
    if not REQUIRED_MANIFEST_KEYS.issubset(keys) or keys - REQUIRED_MANIFEST_KEYS - OPTIONAL_MANIFEST_KEYS:
        raise StudyError("Analysis adjudication manifest has missing or unknown fields")
    if (manifest["schema"] != SCHEMA
            or not isinstance(manifest["study_id"], str) or not manifest["study_id"]
            or not matches(SHA256_RE, manifest["scope_state_sha256"])
            or not matches(COMMIT_RE, manifest["execution_source_commit"])
            or not matches(IMAGE_RE, manifest["runtime_image"])
            or not matches(SHA256_RE, manifest["attribution_helper_sha256"])
            or not isinstance(manifest["entries"], list)):
        raise StudyError("Analysis adjudication manifest fields have an invalid shape or type")
    if "scope_state_file" in manifest and not (isinstance(manifest["scope_state_file"], str)
                                               and manifest["scope_state_file"]):
        raise StudyError("Analysis adjudication manifest scope_state_file must be a nonempty string")


def validate_entries_shape(entries: list) -> None:
    """Reject malformed or ambiguous entries before any are individually evaluated."""
    seen = set()
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != REQUIRED_ENTRY_KEYS:
            raise StudyError("Analysis adjudication entry has missing or unknown fields")
        if (not isinstance(entry["run_id"], str) or not entry["run_id"]
                or not isinstance(entry["step"], str) or not entry["step"]
                or not matches(SHA256_RE, entry["original_record_sha256"])
                or not matches(COMMIT_RE, entry["snapshot_head"])
                or not isinstance(entry["audit_path"], str) or not entry["audit_path"]
                or not matches(SHA256_RE, entry["audit_sha256"])):
            raise StudyError("Analysis adjudication entry fields have an invalid shape or type")
        key = (entry["run_id"], entry["step"])
        if key in seen:
            raise StudyError("Analysis adjudication manifest has duplicate run_id/step entries")
        seen.add(key)


def load_scope_state(directory: Path, manifest: dict) -> dict:
    """Read the exact preserved pre-recovery snapshot the manifest claims to be scoped to."""
    name = manifest.get("scope_state_file", DEFAULT_SCOPE_STATE_NAME)
    if not isinstance(name, str) or not name:
        raise StudyError("Analysis adjudication scope snapshot path is unsafe")
    candidate = PurePosixPath(name)
    if candidate.is_absolute() or ".." in candidate.parts or "\\" in name:
        raise StudyError("Analysis adjudication scope snapshot path is unsafe")
    path = safe_relative_path(directory, name)
    if path is None:
        raise StudyError("Analysis adjudication scope snapshot is missing or unsafe")
    payload = regular_payload(path)
    if hashlib.sha256(payload).hexdigest() != manifest["scope_state_sha256"]:
        raise StudyError("Analysis adjudication scope snapshot differs from the manifest")
    try:
        scope_state = json.loads(payload)
    except ValueError as error:
        raise StudyError("Analysis adjudication scope snapshot is not valid JSON") from error
    if not isinstance(scope_state, dict):
        raise StudyError("Analysis adjudication scope snapshot must be an object")
    return scope_state


def stable_identity(identity: dict) -> dict:
    return {key: value for key, value in identity.items() if key not in IDENTITY_VOLATILE_KEYS}


def cell_allocation(cell: dict) -> dict:
    return {key: cell[key] for key in ALLOCATION_KEYS if key in cell}


def scope_matches_current(scope_state: dict, current_state: dict, recovery_attempt: str | None = None) -> bool:
    """The live study may only have moved on in commit/input/provenance and in appended
    attempts; its allocation, config, study ID and every originally retained attempt must
    be exactly the ones the preserved scope snapshot recorded."""
    scope_identity, current_identity = scope_state.get("identity"), current_state.get("identity")
    if not isinstance(scope_identity, dict) or not isinstance(current_identity, dict):
        return False
    if stable_identity(scope_identity) != stable_identity(current_identity):
        return False
    scope_cells, current_cells_list = scope_state.get("cells"), current_state.get("cells")
    if not isinstance(scope_cells, list) or not isinstance(current_cells_list, list):
        return False
    current_cells = {}
    for cell in current_cells_list:
        if not isinstance(cell, dict) or not isinstance(cell.get("run_id"), str):
            return False
        current_cells[cell["run_id"]] = cell
    if len(current_cells) != len(current_cells_list) or len(scope_cells) != len(current_cells):
        return False
    for cell in scope_cells:
        if not isinstance(cell, dict) or not isinstance(cell.get("run_id"), str):
            return False
        current_cell = current_cells.get(cell["run_id"])
        if current_cell is None or cell_allocation(cell) != cell_allocation(current_cell):
            return False
        scope_attempts, current_attempts = cell.get("attempts"), current_cell.get("attempts")
        if not isinstance(scope_attempts, list) or not isinstance(current_attempts, list):
            return False
        if len(current_attempts) < len(scope_attempts):
            return False
        for before, after in zip(scope_attempts, current_attempts):
            if before == after:
                continue
            if not isinstance(before, dict) or not isinstance(after, dict) \
                    or before.get("id") != recovery_attempt:
                return False
            before, after = dict(before), dict(after)
            if before.get("status") != "interrupted" or after.get("status") != "recovery_interrupted":
                return False
            after["status"] = "interrupted"
            old_included = before.pop("cost_included_in_step", False)
            new_included = after.pop("cost_included_in_step", False)
            if (type(old_included) is not bool or type(new_included) is not bool
                    or (old_included and not new_included) or before != after):
                return False
    return True


def verified_recovery_attempt(directory: Path, manifest: dict, state: dict, scope_state: dict) -> str | None:
    """Allow only bookkeeping for the exact incident with retained, validated owner approval."""
    recovery = state.get("recovery")
    if recovery is None:
        return None
    if (not isinstance(recovery, dict)
            or recovery.get("original_state_sha256") != manifest["scope_state_sha256"]
            or recovery.get("original_commit") != scope_state["identity"]["commit"]
            or recovery.get("target_commit") != state["identity"]["commit"]):
        raise StudyError("Analysis adjudication scope differs from the approved recovery")
    from prepare_estimation_recovery import (
        verify_approval,
        verify_approval_after_attempt,
    )
    from study import validate_recovery_state

    validate_recovery_state(state)
    try:
        approval = json.loads(regular_payload(directory / "recovery-approval.json"))
    except ValueError as error:
        raise StudyError("Analysis adjudication recovery approval is invalid") from error
    if not isinstance(approval, dict) or canonical_sha256(approval) != recovery.get("approval_sha256"):
        raise StudyError("Analysis adjudication recovery approval differs from the retained authorization")
    provenance = state["identity"].get("source_provenance") or {}
    verify_approval(approval, {"commit": state["identity"]["commit"],
                              "public_disclosure_url": provenance.get("public_disclosure_url"),
                              "disclosed_at": provenance.get("disclosed_at_owner_reported")})
    attempt = next((item for cell in scope_state["cells"] for item in cell["attempts"]
                    if item.get("id") == approval["attempt_id"]), None)
    if attempt is None:
        raise StudyError("Analysis adjudication scope lacks the approved interrupted attempt")
    verify_approval_after_attempt(approval, attempt)
    return approval["attempt_id"]


def validate_trust_anchors(directory: Path, manifest: dict, state: dict) -> None:
    """Bind the manifest to the live helper, the live identity and the preserved scope,
    never to a string the manifest merely asserts about itself."""
    if not isinstance(state, dict) or not isinstance(state.get("identity"), dict):
        raise StudyError("Analysis adjudication requires the current study identity")
    identity = state["identity"]
    if manifest["study_id"] != identity.get("study_id") or manifest["study_id"] != directory.name:
        raise StudyError("Analysis adjudication study ID differs from the current study")
    if manifest["execution_source_commit"] != identity.get("commit"):
        raise StudyError("Analysis adjudication execution source commit differs from the current study")
    helper_sha256 = current_helper_sha256()
    if helper_sha256 is None or helper_sha256 != manifest["attribution_helper_sha256"]:
        raise StudyError("Analysis adjudication helper hash differs from the live attribution helper")
    scope_state = load_scope_state(directory, manifest)
    scope_identity = scope_state.get("identity")
    if not isinstance(scope_identity, dict):
        raise StudyError("Analysis adjudication scope snapshot has no identity")
    if manifest["execution_source_commit"] == scope_identity.get("commit"):
        raise StudyError("Analysis adjudication execution source commit must differ from the original scope")
    recovery_attempt = verified_recovery_attempt(directory, manifest, state, scope_state)
    if not scope_matches_current(scope_state, state, recovery_attempt):
        raise StudyError("Analysis adjudication scope differs from the current study beyond commit/input/provenance")


def index_runs(runs: list) -> dict:
    """Map run_id/step to a position only when unambiguous; duplicates stay unmatched."""
    positions, ambiguous = {}, set()
    for position, run in enumerate(runs):
        if not isinstance(run, dict):
            continue
        meta = run.get("meta")
        run_id = meta.get("run_id") if isinstance(meta, dict) else None
        if not isinstance(run_id, str) or not run_id:
            continue
        if run_id in positions:
            ambiguous.add(run_id)
        else:
            positions[run_id] = position
    for run_id in ambiguous:
        positions.pop(run_id, None)
    index = {}
    for run_id, position in positions.items():
        recs = runs[position].get("recs")
        steps, ambiguous_steps = {}, set()
        if isinstance(recs, list):
            for record_position, record in enumerate(recs):
                if not isinstance(record, dict):
                    continue
                step = record.get("step")
                if not isinstance(step, str) or not step:
                    continue
                if step in steps:
                    ambiguous_steps.add(step)
                else:
                    steps[step] = record_position
        for step in ambiguous_steps:
            steps.pop(step, None)
        index[run_id] = (position, steps)
    return index


def valid_candidate_provenance(record: object) -> bool:
    """A declared product exception raised from the candidate's own source under /work/src,
    never a bare string match on a name or message."""
    if (not isinstance(record, dict) or record.get("outcome") != "failed"
            or record.get("attribution") != "candidate_exception"
            or record.get("raw_outcome") not in ("failed", "error")):
        return False
    candidate = record.get("candidate")
    if not isinstance(candidate, dict):
        return False
    module, source = candidate.get("module"), candidate.get("source")
    if not isinstance(module, str) or not module or not isinstance(source, str) or not source:
        return False
    normalized = posixpath.normpath(source)
    return normalized.startswith("/work/src/")


def evaluate_entry(directory: Path, manifest: dict, entry: dict, index: dict, runs: list) -> dict | None:
    """Bind one manifest entry to its exact original record and trusted audit; return the
    accepted per-test corrections, or None when any part of the binding cannot be trusted or
    there is no actual eligible error-to-failed correction. A present entry is never silently
    dropped: the caller must treat None as a hard failure for the whole call, not a skip."""
    located = index.get(entry["run_id"])
    if located is None:
        return None
    run_position, steps = located
    record_position = steps.get(entry["step"])
    if record_position is None:
        return None
    record = runs[run_position]["recs"][record_position]
    if not isinstance(record, dict) or canonical_sha256(record) != entry["original_record_sha256"]:
        return None
    measure = record.get("measure")
    if not isinstance(measure, dict):
        return None
    head = measure.get("head")
    k, cr = measure.get("k"), measure.get("cr")
    hidden = measure.get("hidden")
    hidden_total, hidden_passed = measure.get("hidden_total"), measure.get("hidden_passed")
    if (not matches(COMMIT_RE, head) or head != entry["snapshot_head"]
            or type(k) is not int or type(cr) is not bool
            or not isinstance(hidden, dict) or not hidden
            or type(hidden_total) is not int or type(hidden_passed) is not int
            or hidden_total != len(hidden) or hidden_passed != sum(value == "passed" for value in hidden.values())
            or "metrics" not in measure or "diff" not in measure
            or any(value not in NONPASS_OUTCOMES for value in hidden.values())):
        return None
    evaluation = measure.get("evaluation")
    if (isinstance(evaluation, dict) and "candidate_snapshot" in evaluation
            and evaluation["candidate_snapshot"] != head):
        return None

    audit_file = safe_relative_path(directory, entry["audit_path"])
    if audit_file is None:
        return None
    audit_bytes = read_bounded(audit_file)
    if audit_bytes is None or hashlib.sha256(audit_bytes).hexdigest() != entry["audit_sha256"]:
        return None
    try:
        audit = json.loads(audit_bytes)
    except ValueError:
        return None
    if not isinstance(audit, dict):
        return None
    audit_evaluation = audit.get("evaluation")
    if (audit.get("head") != entry["snapshot_head"] or audit.get("k") != k or audit.get("cr") != cr
            or type(audit.get("k")) is not int or type(audit.get("cr")) is not bool
            or type(audit.get("hidden_total")) is not int or type(audit.get("hidden_passed")) is not int
            or not isinstance(audit_evaluation, dict)
            or audit_evaluation.get("candidate_snapshot") != audit.get("head")
            or audit_evaluation.get("image") != manifest["runtime_image"]
            or audit_evaluation.get("execution_source_commit") != manifest["execution_source_commit"]
            or audit_evaluation.get("attribution_helper_sha256") != manifest["attribution_helper_sha256"]
            or audit_evaluation.get("execution") != "isolated_container"
            or audit_evaluation.get("environment") != "credential_minimal"
            or audit_evaluation.get("os_isolated") is not True
            or audit_evaluation.get("network_isolated") is not True
            or audit.get("hidden_total") != hidden_total or audit.get("hidden_passed") != hidden_passed
            or audit.get("metrics") != measure["metrics"] or audit.get("diff") != measure["diff"]):
        return None
    audit_hidden, audit_provenance = audit.get("hidden"), audit.get("hidden_provenance")
    if (not isinstance(audit_hidden, dict) or set(audit_hidden) != set(hidden)
            or not isinstance(audit_provenance, dict)):
        return None

    changed = {}
    for test_id, original_outcome in hidden.items():
        new_outcome = audit_hidden.get(test_id)
        if original_outcome != "error":
            if new_outcome != original_outcome:
                return None
            continue
        if new_outcome not in ("error", "failed"):
            return None
        if new_outcome == "error":
            continue
        provenance_record = audit_provenance.get(test_id)
        original_provenance = (measure.get("hidden_provenance") or {}).get(test_id)
        if (not valid_candidate_provenance(provenance_record)
                or not isinstance(original_provenance, dict)
                or provenance_record["raw_outcome"] != original_provenance.get("raw_outcome")):
            return None
        changed[test_id] = provenance_record
    if not changed:
        return None
    return {"run_position": run_position, "record_position": record_position, "entry": entry, "changed": changed}


def apply(directory: Path, state: dict, runs: list[dict]) -> tuple[list[dict], dict]:
    """Overlay trusted hidden-test reattribution onto retained step records for reporting.

    Reads directory/analysis-adjudications.json (schema analysis-adjudications/v1). With no
    manifest, returns (runs, {"status": "unavailable", ...}) unchanged - same objects, zero
    copies; this is the only case that does not raise. A manifest that is present but fails
    any structural, identity or scope check raises StudyError; nothing is applied. Once the
    manifest's own trust anchors (live attribution_helper_sha256, current study/commit
    identity, and the preserved state.before-recovery.json scope - or an explicit safe
    relative scope_state_file - all bind), every entry is independently bound to its exact
    original record (by run_id/step and a canonical whole-record digest) and its trusted
    audit file (by a bounded, contained, non-symlinked relative path and digest). Only
    candidate_exception-attributed, /work/src-sourced reclassifications of a prior hidden
    outcome of "error" to "failed" are ever applied, for the exact same measured candidate
    snapshot (head), k, cr, hidden-test identities, counts, metrics and diff. A present entry
    is never silently dropped: any entry that cannot be fully bound, that claims any other
    change, or that yields no actual eligible correction raises StudyError for the whole call
    - a manifest is applied atomically, in full, or not at all; there is no partial success.
    The raised message never includes candidate source paths, diagnostics or test identities.
    Only the runs containing an applied change are copied; every other run/record keeps its
    original object identity, and no file on disk is ever written.
    """
    directory = Path(directory)
    manifest_path = directory / MANIFEST_FILE
    if not manifest_path.exists() and not manifest_path.is_symlink():
        return runs, {"status": "unavailable", "reason": REASON}

    manifest_bytes = regular_payload(manifest_path)
    try:
        manifest = json.loads(manifest_bytes)
    except ValueError as error:
        raise StudyError("Analysis adjudication manifest is not valid JSON") from error
    validate_manifest_shape(manifest)
    validate_entries_shape(manifest["entries"])
    validate_trust_anchors(directory, manifest, state)

    index = index_runs(runs)
    accepted = []
    for entry in manifest["entries"]:
        outcome = evaluate_entry(directory, manifest, entry, index, runs)
        if outcome is None:
            # A present entry that cannot be proven is a hard stop, never a silent partial
            # result: no candidate path, diagnostic or test identity belongs in this message.
            raise StudyError(
                f"Analysis adjudication entry run_id={entry['run_id']!r} step={entry['step']!r} "
                "is invalid, unmatched, or has no eligible correction; nothing was applied"
            )
        accepted.append(outcome)

    helper_sha256 = manifest["attribution_helper_sha256"]
    provenance = {"status": "applied", "reason": REASON, "study_id": manifest["study_id"],
                 "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                 "scope_state_sha256": manifest["scope_state_sha256"],
                 "execution_source_commit": manifest["execution_source_commit"],
                 "runtime_image": manifest["runtime_image"], "attribution_helper_sha256": helper_sha256,
                 "corrected_records": len(accepted),
                 "corrected_tests": sum(len(item["changed"]) for item in accepted)}
    if not accepted:
        return runs, provenance

    by_run = {}
    for item in accepted:
        by_run.setdefault(item["run_position"], []).append(item)
    augmented = list(runs)
    for run_position, items in by_run.items():
        new_run = copy.deepcopy(runs[run_position])
        for item in items:
            record = new_run["recs"][item["record_position"]]
            measure = record["measure"]
            hidden = measure["hidden"]
            record_provenance = measure.setdefault("hidden_provenance", {})
            for test_id, audit_record in item["changed"].items():
                hidden[test_id] = "failed"
                record_provenance[test_id] = copy.deepcopy(audit_record)
            record["analysis_adjudication"] = {
                "schema": SCHEMA, "run_id": item["entry"]["run_id"], "step": item["entry"]["step"],
                "corrected_tests": sorted(item["changed"]),
                "original_record_sha256": item["entry"]["original_record_sha256"],
                "snapshot_head": item["entry"]["snapshot_head"],
                "audit_path": item["entry"]["audit_path"], "audit_sha256": item["entry"]["audit_sha256"],
                "scope_state_sha256": manifest["scope_state_sha256"],
                "execution_source_commit": manifest["execution_source_commit"],
                "runtime_image": manifest["runtime_image"], "attribution_helper_sha256": helper_sha256,
            }
        augmented[run_position] = new_run
    return augmented, provenance
