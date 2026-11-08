"""Adversarial regressions for the bounded analysis-adjudication overlay; no model calls."""
import copy
import hashlib
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
HELPER_SHA256 = hashlib.sha256((ROOT / "harness/failure_attribution.py").read_bytes()).hexdigest()

ORIGINAL_COMMIT = "a" * 40
CURRENT_COMMIT = "b" * 40
SNAPSHOT_HEAD = "c" * 40
RUNTIME_IMAGE = "sha256:" + "d" * 64
LIVE_IMAGE = "sha256:" + "0" * 64


def canonical_sha256(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def write_json(path, value):
    data = json.dumps(value).encode()
    path.write_bytes(data)
    return data


def make_record(step, outcomes, *, k=1, cr=False):
    """One whole steps.jsonl-shaped record, matching runner.py's recorded fields."""
    hidden = dict(outcomes)
    provenance = {}
    for test_id, outcome in hidden.items():
        if outcome == "error":
            provenance[test_id] = {"raw_outcome": "error", "outcome": "error",
                                   "attribution": "unknown", "diagnostic": "RuntimeError: boom"}
        else:
            provenance[test_id] = {"raw_outcome": outcome, "outcome": outcome,
                                   "attribution": "assertion" if outcome == "failed" else "runner_status",
                                   "diagnostic": ""}
    measure = {
        "head": SNAPSHOT_HEAD, "k": k, "cr": cr, "hidden": hidden, "hidden_provenance": provenance,
        "hidden_total": len(hidden), "hidden_passed": sum(value == "passed" for value in hidden.values()),
        "metrics": {"mean_ccn": 1.5, "share_ccn_over_10": 0.0, "dup_pct": 0.0, "lint_per_kloc": 0.0,
                   "backends": {"complexity": "lizard", "duplication": "jscpd", "lint": "ruff"}},
        "diff": {"src": {"added": 3, "removed": 1}, "tests": {"added": 1, "removed": 0},
                "docs": {"added": 0, "removed": 0}, "other": {"added": 0, "removed": 0}},
        "evaluation": {"execution": "isolated_container", "environment": "credential_minimal",
                       "os_isolated": True, "network_isolated": True,
                       "image": LIVE_IMAGE, "candidate_snapshot": SNAPSHOT_HEAD},
    }
    return {"run_id": "run-1", "arm": "B", "phase": "pilot-estimation", "suite": "s1-retrofit",
            "time": "2026-11-01T00:00:00+00:00", "step": step, "k": k, "kind": "feature",
            "delivered": True, "violations": [],
            "agent": {"seconds": 12.5, "usage": {"credits_complete": True, "totalNanoAiu": 500000000}},
            "measure": measure}


def candidate_evidence(outcome="failed", attribution="candidate_exception", source="/work/src/workbench/__init__.py"):
    return {"raw_outcome": "error", "outcome": outcome, "attribution": attribution,
            "diagnostic": "workbench.NotAllowed: declared candidate exception",
            "candidate": {"module": "workbench", "source": source}}


def make_audit(record, *, hidden=None, provenance=None, **overrides):
    measure = record["measure"]
    audit = {
        "head": measure["head"], "k": measure["k"], "cr": measure["cr"],
        "hidden": dict(measure["hidden"]) if hidden is None else hidden,
        "hidden_provenance": ({test_id: dict(value) for test_id, value in measure["hidden_provenance"].items()}
                              if provenance is None else provenance),
        "hidden_total": measure["hidden_total"], "hidden_passed": measure["hidden_passed"],
        "metrics": measure["metrics"], "diff": measure["diff"],
        "evaluation": {"execution": "isolated_container", "environment": "credential_minimal",
                       "os_isolated": True, "network_isolated": True, "image": RUNTIME_IMAGE,
                       "candidate_snapshot": measure["head"], "execution_source_commit": CURRENT_COMMIT,
                       "attribution_helper_sha256": HELPER_SHA256},
    }
    audit.update(overrides)
    return audit


def base_identity(*, commit, inputs_sha256, provenance_tag):
    return {"study_id": "pilot-estimation", "config": {"seed": 7}, "smoke": False,
            "phase": "pilot-estimation", "commit": commit, "inputs_sha256": inputs_sha256,
            "source_provenance": {"registration_status": "unregistered", "tag": provenance_tag},
            "analysis_design": "model-stratified-v2-five-arm",
            "model_roster": ["gpt-6.1-sol", "claude-sonnet-5.5", "gemini-4-argon"]}


def cell(attempts):
    return {"run_id": "run-1", "arm": "B", "features": 10, "change_request": True,
            "assigned_model": "gpt-6.1-sol", "analysis_design": "model-stratified-v2-five-arm",
            "replicate": 1, "replicates_per_model_arm": 12, "status": "running",
            "attempts": attempts, "checkpoint": None}


SCOPE_ATTEMPT = {"id": "run-1-f01-feature-1", "step": "f01-feature", "status": "completed",
                 "source_commit": ORIGINAL_COMMIT, "started": 1000, "seconds": 10}
EXTRA_ATTEMPT = {"id": "run-1-f01-feature-2", "step": "f01-feature", "status": "completed",
                 "source_commit": CURRENT_COMMIT, "started": 2000, "seconds": 5}


@pytest.fixture
def harness(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "harness"))
    module = importlib.import_module("analysis_adjudications")
    directory = tmp_path / "pilot-estimation"
    directory.mkdir()

    record = make_record("f01-feature", {"test_f01::test_a": "error", "test_f01::test_b": "passed"})
    audit = make_audit(record, hidden={**record["measure"]["hidden"], "test_f01::test_a": "failed"},
                      provenance={**record["measure"]["hidden_provenance"],
                                 "test_f01::test_a": candidate_evidence()})

    scope_state = {"identity": base_identity(commit=ORIGINAL_COMMIT, inputs_sha256="1" * 64, provenance_tag="old"),
                   "cells": [cell([SCOPE_ATTEMPT])]}
    state = {"identity": base_identity(commit=CURRENT_COMMIT, inputs_sha256="2" * 64, provenance_tag="new"),
            "cells": [cell([SCOPE_ATTEMPT, EXTRA_ATTEMPT])]}

    scope_bytes = write_json(directory / module.DEFAULT_SCOPE_STATE_NAME, scope_state)
    audits_dir = directory / "audits"
    audits_dir.mkdir()
    audit_path = audits_dir / "run-1-f01-feature.json"
    audit_bytes = write_json(audit_path, audit)

    entry = {"run_id": "run-1", "step": "f01-feature", "original_record_sha256": canonical_sha256(record),
             "snapshot_head": SNAPSHOT_HEAD, "audit_path": "audits/run-1-f01-feature.json",
             "audit_sha256": hashlib.sha256(audit_bytes).hexdigest()}
    manifest = {"schema": module.SCHEMA, "study_id": "pilot-estimation",
                "scope_state_sha256": hashlib.sha256(scope_bytes).hexdigest(),
                "execution_source_commit": CURRENT_COMMIT, "runtime_image": RUNTIME_IMAGE,
                "attribution_helper_sha256": HELPER_SHA256, "entries": [entry]}

    runs = [{"dir": str(directory / "runs/run-1"), "meta": {"run_id": "run-1"}, "recs": [record]}]
    return SimpleNamespace(module=module, directory=directory, state=state, scope_state=scope_state,
                          scope_bytes=scope_bytes, record=record, audit=audit, audit_path=audit_path,
                          audit_bytes=audit_bytes, entry=entry, manifest=manifest, runs=runs)


def install(h, manifest=None):
    """Write (a possibly mutated) manifest to disk and return its exact written bytes."""
    return write_json(h.directory / h.module.MANIFEST_FILE, h.manifest if manifest is None else manifest)


def install_entry(h, *, audit=None, entry_overrides=None, path="audits/run-1-f01-feature.json"):
    """Write a fresh audit file (default: the fixture's valid one) and a matching manifest
    entry, with optional post-hash overrides to simulate a forged digest claim."""
    payload = h.audit if audit is None else audit
    data = write_json(h.directory / path, payload)
    entry = {**h.entry, "audit_path": path, "audit_sha256": hashlib.sha256(data).hexdigest()}
    if entry_overrides:
        entry.update(entry_overrides)
    manifest = {**h.manifest, "entries": [entry]}
    install(h, manifest)
    return entry


def legit_correction(harness, **extra_hidden):
    """A baseline audit claim that legitimately corrects test_a (error -> failed with
    proven candidate_exception evidence). A test that tampers with something else merges
    its own illegitimate claim into this via extra_hidden, so a correctly voided entry
    (nothing applied) can be told apart from an entry with nothing to apply in the first
    place - both would otherwise look identical from the outside."""
    hidden = {**harness.record["measure"]["hidden"], "test_f01::test_a": "failed", **extra_hidden}
    provenance = {**harness.record["measure"]["hidden_provenance"], "test_f01::test_a": candidate_evidence()}
    return hidden, provenance


# --------------------------------------------------------------------- baseline behaviour

def test_missing_manifest_is_unavailable_and_returns_the_same_object(harness):
    result, provenance = harness.module.apply(harness.directory, harness.state, harness.runs)
    assert result is harness.runs
    assert provenance == {"status": "unavailable", "reason": harness.module.REASON}


def test_valid_manifest_corrects_only_the_proven_candidate_exception(harness):
    install(harness)
    original = copy.deepcopy(harness.runs)
    extra_run = {"dir": "elsewhere", "meta": {"run_id": "run-2"}, "recs": []}
    runs = [harness.runs[0], extra_run]
    result, provenance = harness.module.apply(harness.directory, harness.state, runs)

    assert runs == [original[0], extra_run]
    assert runs[0]["recs"][0] is harness.record
    assert result[1] is extra_run

    corrected = result[0]["recs"][0]
    assert corrected is not harness.record
    assert corrected["measure"]["hidden"] == {"test_f01::test_a": "failed", "test_f01::test_b": "passed"}
    assert corrected["measure"]["hidden_provenance"]["test_f01::test_a"]["attribution"] == "candidate_exception"
    assert corrected["measure"]["hidden_provenance"]["test_f01::test_b"] == \
        harness.record["measure"]["hidden_provenance"]["test_f01::test_b"]
    for key in ("head", "k", "cr", "hidden_total", "hidden_passed", "metrics", "diff", "evaluation"):
        assert corrected["measure"][key] == harness.record["measure"][key]
    for key in ("run_id", "arm", "phase", "suite", "time", "step", "kind", "delivered", "violations", "agent"):
        assert corrected[key] == harness.record[key]
    assert corrected["analysis_adjudication"]["corrected_tests"] == ["test_f01::test_a"]
    assert corrected["analysis_adjudication"]["run_id"] == "run-1"
    assert corrected["analysis_adjudication"]["step"] == "f01-feature"

    manifest_sha256 = hashlib.sha256(json.dumps(harness.manifest).encode()).hexdigest()
    assert provenance == {
        "status": "applied", "reason": harness.module.REASON, "study_id": "pilot-estimation",
        "manifest_sha256": manifest_sha256, "scope_state_sha256": harness.manifest["scope_state_sha256"],
        "execution_source_commit": CURRENT_COMMIT, "runtime_image": RUNTIME_IMAGE,
        "attribution_helper_sha256": HELPER_SHA256, "corrected_records": 1, "corrected_tests": 1,
    }
    assert "test_f01" not in json.dumps(provenance)
    assert "audits/" not in json.dumps(provenance)


def test_unmatched_audit_raises_instead_of_silently_confirming_unknown(harness):
    """A present entry whose reevaluation confirms the candidate exception remains unproven
    must stop the whole call; it is never a silent, partial "nothing to apply" success."""
    install_entry(harness, audit=make_audit(harness.record))
    original = copy.deepcopy(harness.runs)
    with pytest.raises(harness.module.StudyError):
        harness.module.apply(harness.directory, harness.state, harness.runs)
    assert harness.runs == original


def test_scope_state_file_override_is_honoured_when_safe(harness):
    alternate = harness.directory / "alt-scope.json"
    data = write_json(alternate, harness.scope_state)
    manifest = {**harness.manifest, "scope_state_file": "alt-scope.json",
                "scope_state_sha256": hashlib.sha256(data).hexdigest()}
    install(harness, manifest)
    result, provenance = harness.module.apply(harness.directory, harness.state, harness.runs)
    assert provenance["status"] == "applied" and provenance["corrected_records"] == 1
    assert result[0]["recs"][0]["measure"]["hidden"]["test_f01::test_a"] == "failed"


def test_disk_evidence_is_never_written_or_rewritten(harness):
    manifest_bytes = install(harness)
    result, _ = harness.module.apply(harness.directory, harness.state, harness.runs)
    assert result[0]["recs"][0]["measure"]["hidden"]["test_f01::test_a"] == "failed"
    assert (harness.directory / harness.module.MANIFEST_FILE).read_bytes() == manifest_bytes
    assert (harness.directory / harness.module.DEFAULT_SCOPE_STATE_NAME).read_bytes() == harness.scope_bytes
    assert harness.audit_path.read_bytes() == harness.audit_bytes
    assert harness.runs[0]["recs"][0] is harness.record


# --------------------------------------------------------------------- tier 1: manifest/scope/identity forgery


MANIFEST_DAMAGE = [
    "symlinked-manifest",
    "manifest-not-object",
    "missing-field",
    "unknown-field",
    "wrong-schema",
    "bad-study-id-type",
    "study-id-mismatch-state",
    "study-id-mismatch-directory",
    "bad-scope-hash-format",
    "bad-commit-format",
    "bad-image-format",
    "bad-helper-hash-format",
    "forged-execution-commit",
    "forged-image-not-sha256-form",
    "forged-helper-hash",
    "forged-scope-hash",
    "scope-missing",
    "scope-is-symlink",
    "scope-not-object",
    "scope-identity-diverges",
    "scope-allocation-diverges",
    "scope-attempts-not-retained",
    "execution-commit-equals-scope-commit",
    "duplicate-entries",
    "entry-missing-field",
    "entry-unknown-field",
    "entry-wrong-type",
    "entry-unhashable-step",
    "scope-state-file-unsafe",
]


@pytest.mark.parametrize("damage", MANIFEST_DAMAGE)
def test_manifest_or_scope_forgery_raises_study_error(harness, damage):
    manifest = copy.deepcopy(harness.manifest)
    state = harness.state
    if damage == "symlinked-manifest":
        real = harness.directory / "real-manifest.json"
        write_json(real, manifest)
        (harness.directory / harness.module.MANIFEST_FILE).symlink_to(real)
        with pytest.raises(harness.module.StudyError):
            harness.module.apply(harness.directory, state, harness.runs)
        return
    if damage == "manifest-not-object":
        install(harness, manifest=[manifest])
        with pytest.raises(harness.module.StudyError):
            harness.module.apply(harness.directory, state, harness.runs)
        return
    if damage == "missing-field":
        del manifest["entries"]
    elif damage == "unknown-field":
        manifest["unexpected"] = True
    elif damage == "wrong-schema":
        manifest["schema"] = "analysis-adjudications/v2"
    elif damage == "bad-study-id-type":
        manifest["study_id"] = 7
    elif damage == "study-id-mismatch-state":
        manifest["study_id"] = "different-study"
    elif damage == "study-id-mismatch-directory":
        # manifest/state agree with each other but not with the actual directory name.
        state = copy.deepcopy(harness.state)
        state["identity"]["study_id"] = "renamed-elsewhere"
        manifest["study_id"] = "renamed-elsewhere"
    elif damage == "bad-scope-hash-format":
        manifest["scope_state_sha256"] = "not-hex"
    elif damage == "bad-commit-format":
        manifest["execution_source_commit"] = "short"
    elif damage == "bad-image-format":
        manifest["runtime_image"] = "latest"
    elif damage == "bad-helper-hash-format":
        manifest["attribution_helper_sha256"] = "zz" * 32
    elif damage == "forged-execution-commit":
        manifest["execution_source_commit"] = "f" * 40
    elif damage == "forged-image-not-sha256-form":
        manifest["runtime_image"] = "registry.example/mve@sha256:" + "d" * 64
    elif damage == "forged-helper-hash":
        manifest["attribution_helper_sha256"] = "0" * 64
    elif damage == "forged-scope-hash":
        manifest["scope_state_sha256"] = "1" * 64
    elif damage == "scope-missing":
        (harness.directory / harness.module.DEFAULT_SCOPE_STATE_NAME).unlink()
    elif damage == "scope-is-symlink":
        (harness.directory / harness.module.DEFAULT_SCOPE_STATE_NAME).unlink()
        (harness.directory / harness.module.DEFAULT_SCOPE_STATE_NAME).symlink_to("/tmp")
    elif damage == "scope-not-object":
        data = write_json(harness.directory / harness.module.DEFAULT_SCOPE_STATE_NAME, [1, 2, 3])
        manifest["scope_state_sha256"] = hashlib.sha256(data).hexdigest()
    elif damage == "scope-identity-diverges":
        scope = copy.deepcopy(harness.scope_state)
        scope["identity"]["phase"] = "calibration"
        data = write_json(harness.directory / harness.module.DEFAULT_SCOPE_STATE_NAME, scope)
        manifest["scope_state_sha256"] = hashlib.sha256(data).hexdigest()
    elif damage == "scope-allocation-diverges":
        scope = copy.deepcopy(harness.scope_state)
        scope["cells"][0]["features"] = 3
        data = write_json(harness.directory / harness.module.DEFAULT_SCOPE_STATE_NAME, scope)
        manifest["scope_state_sha256"] = hashlib.sha256(data).hexdigest()
    elif damage == "scope-attempts-not-retained":
        scope = copy.deepcopy(harness.scope_state)
        scope["cells"][0]["attempts"][0]["seconds"] = 99999
        data = write_json(harness.directory / harness.module.DEFAULT_SCOPE_STATE_NAME, scope)
        manifest["scope_state_sha256"] = hashlib.sha256(data).hexdigest()
    elif damage == "execution-commit-equals-scope-commit":
        scope = copy.deepcopy(harness.scope_state)
        data = write_json(harness.directory / harness.module.DEFAULT_SCOPE_STATE_NAME, scope)
        manifest["scope_state_sha256"] = hashlib.sha256(data).hexdigest()
        manifest["execution_source_commit"] = ORIGINAL_COMMIT
        state = copy.deepcopy(harness.state)
        state["identity"]["commit"] = ORIGINAL_COMMIT
    elif damage == "duplicate-entries":
        manifest["entries"] = [harness.entry, dict(harness.entry)]
    elif damage == "entry-missing-field":
        manifest["entries"] = [{key: value for key, value in harness.entry.items() if key != "step"}]
    elif damage == "entry-unknown-field":
        manifest["entries"] = [{**harness.entry, "extra": "x"}]
    elif damage == "entry-wrong-type":
        manifest["entries"] = [{**harness.entry, "step": 1}]
    elif damage == "entry-unhashable-step":
        # An unhashable claimed step must still fail as a clean StudyError from shape
        # validation, never an uncaught TypeError from a later dict lookup.
        manifest["entries"] = [{**harness.entry, "step": ["unhashable"]}]
    elif damage == "scope-state-file-unsafe":
        manifest["scope_state_file"] = "../outside.json"
    else:  # pragma: no cover - guards against an unhandled parameter id
        raise AssertionError(f"Unhandled damage case: {damage}")

    install(harness, manifest)
    with pytest.raises(harness.module.StudyError):
        harness.module.apply(harness.directory, state, harness.runs)



# --------------------------------------------------------------------- tier 2: per-entry
# failures now raise too; a present entry is proven in full or the whole call stops.


def disk_snapshot(directory):
    """A conservative content fingerprint of every regular file reachable under directory
    (symlinks are followed for comparison, never rewritten), to prove nothing changed."""
    return {str(path.relative_to(directory)): path.read_bytes()
            for path in sorted(directory.rglob("*")) if path.is_file()}


def assert_raises_without_mutation(harness, *, state=None):
    """Any present invalid/unmatched/ineligible entry must stop the whole call with an
    explicit StudyError - never a silent skip, never a partial success, never a disk write,
    never an input mutation. This is the single shared assertion for every tier-2 case."""
    original_runs = copy.deepcopy(harness.runs)
    before = disk_snapshot(harness.directory)
    with pytest.raises(harness.module.StudyError) as excinfo:
        harness.module.apply(harness.directory, harness.state if state is None else state, harness.runs)
    assert harness.runs == original_runs
    assert disk_snapshot(harness.directory) == before
    return str(excinfo.value)


def test_foreign_run_id_raises(harness):
    install_entry(harness, entry_overrides={"run_id": "run-does-not-exist"})
    assert_raises_without_mutation(harness)


def test_foreign_step_raises(harness):
    install_entry(harness, entry_overrides={"step": "f99-feature"})
    assert_raises_without_mutation(harness)


def test_forged_original_record_digest_raises(harness):
    install_entry(harness, entry_overrides={"original_record_sha256": "2" * 64})
    assert_raises_without_mutation(harness)


def test_forged_audit_digest_raises(harness):
    entry = install_entry(harness)
    tampered_entry = {**entry, "audit_sha256": "3" * 64}
    install(harness, {**harness.manifest, "entries": [tampered_entry]})
    assert_raises_without_mutation(harness)


def test_mismatched_snapshot_head_raises(harness):
    other_head = "e" * 40
    hidden, provenance = legit_correction(harness)
    install_entry(harness, entry_overrides={"snapshot_head": other_head},
                 audit=make_audit(harness.record, head=other_head, hidden=hidden, provenance=provenance))
    assert_raises_without_mutation(harness)


@pytest.mark.parametrize("name,relative", [
    ("traversal", "../outside.json"),
    ("absolute", "/etc/passwd"),
    ("nested-traversal", "audits/../../outside.json"),
])
def test_path_traversal_audit_paths_raise(harness, name, relative):
    outside = harness.directory.parent / "outside.json"
    write_json(outside, harness.audit)
    install_entry(harness, entry_overrides={"audit_path": relative})
    assert_raises_without_mutation(harness)


def test_symlinked_audit_path_raises(harness):
    real = harness.directory / "real-audit.json"
    write_json(real, harness.audit)
    link = harness.directory / "audits" / "link.json"
    link.symlink_to(real)
    install_entry(harness, entry_overrides={"audit_path": "audits/link.json",
                                           "audit_sha256": hashlib.sha256(real.read_bytes()).hexdigest()})
    assert_raises_without_mutation(harness)


def test_audit_path_escaping_through_a_symlinked_directory_raises(harness):
    """No ".." and no symlinked final component, but an intermediate directory symlinks
    outside the study directory; containment must still catch this, not just the other
    two checks."""
    outside = harness.directory.parent / "outside-dir"
    outside.mkdir()
    write_json(outside / "audit.json", harness.audit)
    (harness.directory / "escape").symlink_to(outside)
    install_entry(harness, entry_overrides={
        "audit_path": "escape/audit.json",
        "audit_sha256": hashlib.sha256((outside / "audit.json").read_bytes()).hexdigest()})
    assert_raises_without_mutation(harness)


def test_scope_snapshot_escaping_through_a_symlinked_directory_raises(harness):
    outside = harness.directory.parent / "outside-scope-dir"
    outside.mkdir()
    data = write_json(outside / "scope.json", harness.scope_state)
    (harness.directory / "escape").symlink_to(outside)
    manifest = {**harness.manifest, "scope_state_file": "escape/scope.json",
               "scope_state_sha256": hashlib.sha256(data).hexdigest()}
    install(harness, manifest)
    with pytest.raises(harness.module.StudyError):
        harness.module.apply(harness.directory, harness.state, harness.runs)


@pytest.mark.parametrize("field,value", [
    ("head", "f" * 40),
    ("k", 2),
    ("cr", True),
    ("hidden_total", 99),
    ("hidden_passed", 99),
    ("metrics", {"mean_ccn": 999.0}),
    ("diff", {"src": {"added": 999, "removed": 0}}),
])
def test_audit_metadata_metrics_or_head_changes_raise(harness, field, value):
    hidden, provenance = legit_correction(harness)
    install_entry(harness, audit=make_audit(harness.record, hidden=hidden, provenance=provenance, **{field: value}))
    assert_raises_without_mutation(harness)


def test_audit_image_mismatch_raises(harness):
    hidden, provenance = legit_correction(harness)
    audit = make_audit(harness.record, hidden=hidden, provenance=provenance)
    audit["evaluation"] = {**audit["evaluation"], "image": "sha256:" + "9" * 64}
    install_entry(harness, audit=audit)
    assert_raises_without_mutation(harness)


def test_audit_self_inconsistent_candidate_snapshot_raises(harness):
    hidden, provenance = legit_correction(harness)
    audit = make_audit(harness.record, hidden=hidden, provenance=provenance)
    audit["evaluation"] = {**audit["evaluation"], "candidate_snapshot": "9" * 40}
    install_entry(harness, audit=audit)
    assert_raises_without_mutation(harness)


def test_audit_introducing_a_new_test_identity_raises(harness):
    hidden, provenance = legit_correction(harness, **{"test_f01::test_new": "passed"})
    install_entry(harness, audit=make_audit(harness.record, hidden=hidden, provenance=provenance))
    assert_raises_without_mutation(harness)


@pytest.mark.parametrize("test_id,new_outcome", [
    ("test_f01::test_b", "failed"),
    ("test_f01::test_b", "error"),
])
def test_promoting_or_demoting_an_already_known_outcome_raises(harness, test_id, new_outcome):
    # test_a carries a simultaneous, otherwise-legitimate correction so that an
    # implementation which merely skipped the bad test_id (instead of raising for the whole
    # entry) would still be caught applying test_a's change.
    hidden, provenance = legit_correction(harness, **{test_id: new_outcome})
    install_entry(harness, audit=make_audit(harness.record, hidden=hidden, provenance=provenance))
    assert_raises_without_mutation(harness)


@pytest.mark.parametrize("new_outcome", ["passed", "skipped", "timeout"])
def test_promoting_error_directly_to_a_non_failed_outcome_raises(harness, new_outcome):
    # The per-test provenance plausibly claims a proven candidate exception (outcome
    # "failed") even though the top-level hidden outcome itself is not "failed"; both must
    # agree, so this isolates the hidden-outcome restriction from the provenance-shape check.
    hidden = {**harness.record["measure"]["hidden"], "test_f01::test_a": new_outcome}
    provenance = {**harness.record["measure"]["hidden_provenance"], "test_f01::test_a": candidate_evidence()}
    install_entry(harness, audit=make_audit(harness.record, hidden=hidden, provenance=provenance))
    assert_raises_without_mutation(harness)


@pytest.mark.parametrize("name,evidence", [
    ("wrong-attribution", candidate_evidence(attribution="mandatory_import")),
    ("wrong-attribution-syntax", candidate_evidence(attribution="candidate_syntax")),
    ("wrong-outcome-in-record", candidate_evidence(outcome="error")),
    ("source-outside-work-src", candidate_evidence(source="/kit/harness/evil.py")),
    ("source-boundary-trick", candidate_evidence(source="/work/srcEVIL/x.py")),
    ("source-traversal-trick", candidate_evidence(source="/work/src/../../etc/passwd")),
    ("source-directory", candidate_evidence(source="/work/src")),
    ("raw-passed", {**candidate_evidence(), "raw_outcome": "passed"}),
    ("changed-raw-failure", {**candidate_evidence(), "raw_outcome": "failed"}),
    ("missing-candidate", {"raw_outcome": "error", "outcome": "failed", "attribution": "candidate_exception",
                           "diagnostic": "x"}),
    ("non-string-module", {"raw_outcome": "error", "outcome": "failed", "attribution": "candidate_exception",
                           "diagnostic": "x", "candidate": {"module": 1, "source": "/work/src/a.py"}}),
])
def test_claimed_failed_without_proven_candidate_exception_evidence_raises(harness, name, evidence):
    hidden = {**harness.record["measure"]["hidden"], "test_f01::test_a": "failed"}
    provenance = {**harness.record["measure"]["hidden_provenance"], "test_f01::test_a": evidence}
    install_entry(harness, audit=make_audit(harness.record, hidden=hidden, provenance=provenance))
    assert_raises_without_mutation(harness)


def test_partial_entry_corruption_raises_instead_of_dropping_one_test_id(harness):
    """One record can have several hidden tests; a single bad claim must void the whole
    entry (and so the whole call), never just the one bad test_id."""
    record = make_record("f02-feature", {"test_f02::test_a": "error", "test_f02::test_b": "error"}, k=2)
    good_hidden = {"test_f02::test_a": "failed", "test_f02::test_b": "failed"}
    good_provenance = {"test_f02::test_a": candidate_evidence(), "test_f02::test_b": "BAD-NON-DICT-PROVENANCE"}
    audit = make_audit(record, hidden=good_hidden, provenance=good_provenance)
    entry = {"run_id": "run-1", "step": "f02-feature", "original_record_sha256": canonical_sha256(record),
             "snapshot_head": SNAPSHOT_HEAD, "audit_path": "audits/f02.json", "audit_sha256": ""}
    data = write_json(harness.directory / "audits" / "f02.json", audit)
    entry["audit_sha256"] = hashlib.sha256(data).hexdigest()
    install(harness, {**harness.manifest, "entries": [entry]})
    runs = [{"dir": "d", "meta": {"run_id": "run-1"}, "recs": [record]}]
    original = copy.deepcopy(runs)
    with pytest.raises(harness.module.StudyError):
        harness.module.apply(harness.directory, harness.state, runs)
    assert runs == original


# ----------------------------------------------------------- mixed/atomic manifests and message safety


def test_mixed_valid_and_invalid_entries_fail_atomically_with_no_mutation(harness):
    """One legitimate entry plus one foreign/invalid entry must raise for the whole call;
    the legitimate correction must NOT be partially applied, and nothing on disk changes."""
    foreign = {"run_id": "run-does-not-exist", "step": "f01-feature",
              "original_record_sha256": "4" * 64, "snapshot_head": SNAPSHOT_HEAD,
              "audit_path": "audits/does-not-exist.json", "audit_sha256": "5" * 64}
    manifest = {**harness.manifest, "entries": [harness.entry, foreign]}
    install(harness, manifest)
    assert_raises_without_mutation(harness)


def test_multiple_valid_entries_apply_atomically_together(harness):
    """Two independently legitimate entries across two different records both apply in the
    same call, proving atomic success is not limited to a single entry."""
    second_record = make_record("f02-feature", {"test_f02::test_a": "error"}, k=2)
    second_audit = make_audit(second_record, hidden={"test_f02::test_a": "failed"},
                             provenance={"test_f02::test_a": candidate_evidence()})
    second_data = write_json(harness.directory / "audits" / "f02.json", second_audit)
    second_entry = {"run_id": "run-1", "step": "f02-feature",
                    "original_record_sha256": canonical_sha256(second_record),
                    "snapshot_head": SNAPSHOT_HEAD, "audit_path": "audits/f02.json",
                    "audit_sha256": hashlib.sha256(second_data).hexdigest()}
    manifest = {**harness.manifest, "entries": [harness.entry, second_entry]}
    install(harness, manifest)
    runs = [{"dir": "d", "meta": {"run_id": "run-1"}, "recs": [harness.record, second_record]}]
    result, provenance = harness.module.apply(harness.directory, harness.state, runs)
    assert provenance["status"] == "applied"
    assert provenance["corrected_records"] == 2 and provenance["corrected_tests"] == 2
    assert result[0]["recs"][0]["measure"]["hidden"]["test_f01::test_a"] == "failed"
    assert result[0]["recs"][1]["measure"]["hidden"]["test_f02::test_a"] == "failed"


def test_entry_failure_message_is_safe_and_identifies_the_entry(harness):
    """The raised message may name the failing run_id/step (ordinary scheduling identifiers,
    already public within the study) but never a hidden test identity, a candidate source
    path, or raw diagnostic text."""
    install_entry(harness, entry_overrides={"run_id": "run-does-not-exist"})
    message = assert_raises_without_mutation(harness)
    assert "run-does-not-exist" in message and "f01-feature" in message
    for leak in ("test_f01", "/work/src", "workbench.NotAllowed", "Traceback", "audits/"):
        assert leak not in message


@pytest.mark.parametrize("field,value", [
    ("execution_source_commit", "f" * 40),
    ("attribution_helper_sha256", "f" * 64),
    ("execution", "local_subprocess"),
    ("environment", "inherited_host"),
    ("os_isolated", False),
    ("network_isolated", False),
])
def test_audit_runtime_evidence_must_bind_exact_source_helper_and_isolation(harness, field, value):
    audit = copy.deepcopy(harness.audit)
    audit["evaluation"][field] = value
    install_entry(harness, audit=audit)
    assert_raises_without_mutation(harness)


@pytest.mark.parametrize("field,value", [("k", True), ("cr", 0), ("hidden_passed", True)])
def test_audit_integer_and_boolean_fields_are_not_interchangeable(harness, field, value):
    audit = copy.deepcopy(harness.audit)
    audit[field] = value
    install_entry(harness, audit=audit)
    assert_raises_without_mutation(harness)


def test_audit_path_must_not_follow_an_inside_scope_directory_symlink(harness):
    (harness.directory / "alias").symlink_to(harness.directory / "audits", target_is_directory=True)
    install(harness, {**harness.manifest, "entries": [
        {**harness.entry, "audit_path": "alias/run-1-f01-feature.json"}]})
    assert_raises_without_mutation(harness)


def test_pytest_raw_failure_is_preserved_when_its_attribution_is_corrected(harness):
    record = copy.deepcopy(harness.record)
    record["measure"]["hidden_provenance"]["test_f01::test_a"]["raw_outcome"] = "failed"
    audit = make_audit(record, hidden={**record["measure"]["hidden"], "test_f01::test_a": "failed"},
                      provenance={**record["measure"]["hidden_provenance"],
                                  "test_f01::test_a": {**candidate_evidence(), "raw_outcome": "failed"}})
    install_entry(harness, audit=audit, entry_overrides={"original_record_sha256": canonical_sha256(record)})
    runs = [{**harness.runs[0], "recs": [record]}]
    corrected, _ = harness.module.apply(harness.directory, harness.state, runs)
    assert corrected[0]["recs"][0]["measure"]["hidden_provenance"]["test_f01::test_a"]["raw_outcome"] == "failed"
    assert record["measure"]["hidden"]["test_f01::test_a"] == "error"
