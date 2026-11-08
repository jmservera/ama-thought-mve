"""Operator evidence is explicit, scoped, and never a default unassisted label."""
import copy
import hashlib
import importlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def coverage_case(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "harness"))
    module = importlib.import_module("intervention_coverage")
    state = {"identity": {"study_id": "pilot-estimation", "smoke": False, "phase": "pilot-estimation",
                          "config": {}, "commit": "a" * 40, "inputs_sha256": "b" * 64},
             "cells": [{"run_id": "closed-a", "status": "completed", "completed_steps": 1,
                        "attempts": [{"id": "a", "started": 1767225600, "seconds": 1}]},
                       {"run_id": "closed-b", "status": "completed", "completed_steps": 1,
                        "attempts": [{"id": "b", "started": 1767225600, "seconds": 2}]},
                       {"run_id": "pending-c", "status": "pending", "completed_steps": 0, "attempts": []}]}
    payload = json.dumps(state).encode()
    coverage = {"schema": "intervention-coverage/v1", "study_id": "pilot-estimation",
                "state_sha256": hashlib.sha256(payload).hexdigest(), "owner_attested": True,
                "attested_at": "2026-01-02T00:00:00Z", "evidence_reference": "synthetic operator evidence",
                "unassisted_run_ids": ["closed-a"], "assisted_run_ids": ["closed-b"]}
    runs = [{"meta": {"run_id": cell["run_id"]}, "recs": []} for cell in state["cells"]]
    return module, tmp_path, state, payload, coverage, runs


def install(case):
    module, directory, _, payload, coverage, _ = case
    (directory / module.SCOPE_FILE).write_bytes(payload)
    (directory / module.COVERAGE_FILE).write_text(json.dumps(coverage))


def test_missing_coverage_remains_unavailable_and_does_not_mutate_metadata(coverage_case):
    module, directory, state, _, _, runs = coverage_case
    result, provenance = module.apply(directory, state, runs)
    assert result is runs and provenance["status"] == "unavailable"
    assert all("intervention" not in run["meta"] for run in runs)


def test_owner_coverage_applies_only_to_scoped_completed_observations(coverage_case):
    module, directory, state, _, _, runs = coverage_case
    install(coverage_case)
    original = copy.deepcopy(runs)
    result, provenance = module.apply(directory, state, runs)
    assert runs == original
    assert result[0]["meta"]["intervention"]["assisted"] is False
    assert result[1]["meta"]["intervention"]["assisted"] is True
    assert "intervention" not in result[2]["meta"]
    assert provenance["covered_trajectories"] == 2 and provenance["assisted_trajectories"] == 1
    later = copy.deepcopy(state)
    later["identity"].update(commit="c" * 40, inputs_sha256="d" * 64)
    assert module.apply(directory, later, runs)[1]["status"] == "owner-attested"


@pytest.mark.parametrize("damage", ["owner", "scope", "duplicate", "overlap", "omission", "pending",
                                   "naive-time", "future-time", "before-attempt", "identity"])
def test_invalid_or_selective_attestation_is_rejected(coverage_case, damage):
    module, _directory, state, payload, coverage, _runs = coverage_case
    if damage == "owner":
        coverage["owner_attested"] = False
    elif damage == "scope":
        coverage["state_sha256"] = "0" * 64
    elif damage == "duplicate":
        coverage["unassisted_run_ids"] *= 2
    elif damage == "overlap":
        coverage["unassisted_run_ids"].append("closed-b")
    elif damage == "omission":
        coverage["assisted_run_ids"] = []
    elif damage == "pending":
        coverage["unassisted_run_ids"].append("pending-c")
    elif damage == "naive-time":
        coverage["attested_at"] = "2026-01-02T00:00:00"
    elif damage == "future-time":
        coverage["attested_at"] = "2999-01-01T00:00:00Z"
    elif damage == "before-attempt":
        coverage["attested_at"] = "2026-01-01T00:00:00Z"
    else:
        coverage["study_id"] = "different-study"
    with pytest.raises(module.StudyError):
        module.validate(coverage, payload, state)


def test_new_observations_and_erased_assistance_cannot_be_covered(coverage_case):
    module, directory, state, _, _, runs = coverage_case
    install(coverage_case)
    changed = copy.deepcopy(state)
    changed["cells"][0]["attempts"].append({"id": "extra", "started": 1767225600, "seconds": 1})
    with pytest.raises(module.StudyError, match="new or changed"):
        module.apply(directory, changed, runs)
    changed = copy.deepcopy(state)
    changed["cells"][0]["attempts"][0]["seconds"] = 2
    with pytest.raises(module.StudyError, match="new or changed"):
        module.apply(directory, changed, runs)
    runs[0]["meta"]["intervention"] = {"assisted": True, "coverage_complete": True, "evidence": "actual log"}
    with pytest.raises(module.StudyError, match="erase"):
        module.apply(directory, state, runs)


def test_links_partial_evidence_and_tampered_snapshots_are_rejected(coverage_case):
    module, directory, state, _, _, runs = coverage_case
    install(coverage_case)
    scope = directory / module.SCOPE_FILE
    scope.write_bytes(scope.read_bytes() + b" ")
    with pytest.raises(module.StudyError, match="exact snapshot"):
        module.apply(directory, state, runs)
    scope.unlink()
    with pytest.raises(module.StudyError, match="regular file"):
        module.apply(directory, state, runs)
    scope.symlink_to("/tmp")
    with pytest.raises(module.StudyError, match="regular file"):
        module.apply(directory, state, runs)


def test_record_keeps_state_immutable_and_refuses_overwrite(coverage_case, tmp_path):
    module, directory, state, payload, coverage, _ = coverage_case
    (directory / "state.json").write_bytes(payload)
    source = tmp_path / "owner.json"
    source.write_text(json.dumps(coverage))
    module.record(directory, source)
    assert (directory / "state.json").read_bytes() == payload
    assert module.apply(directory, state, coverage_case[-1])[1]["status"] == "owner-attested"
    with pytest.raises(module.StudyError, match="never overwrite"):
        module.record(directory, source)
