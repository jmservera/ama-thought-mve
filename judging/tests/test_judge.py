"""Offline/reference validation of judging; never connect to the study VM or a model."""
from __future__ import annotations

import copy
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def judge(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "judging"))
    return importlib.import_module("judge")


def outcomes(judge, k, cr=False):
    return [{"scenario_id": scenario.id, "status": "passed", "error_type": None,
             "observations": [{"id": f"{scenario.id}:1", "action": "diagnostic observation",
                               "expected": 1, "actual": 1, "outcome": "passed"}]}
            for scenario in judge.eligible(k, cr)]


def record(arm, run_id, k, cr=False, commit="a" * 40):
    kind = "change_request" if cr else {"A": "feature", "B": "consolidation", "C": "review",
                                       "D": "feature", "E": "repair"}[arm]
    return {"step": "cr1-change" if cr else f"f{k:02d}-{kind}", "kind": kind, "k": k,
            "run_id": run_id, "arm": arm, "suite": "s1-retrofit",
            "measure": {"head": commit, "k": k, "cr": cr}}


@pytest.fixture
def archive(tmp_path):
    directory = tmp_path / "archive"
    directory.mkdir()
    cells = []
    for arm in "ABCDE":
        run_id = f"secret-dev-{arm}-01"
        cell = {"run_id": run_id, "arm": arm, "assigned_model": "secret-development-model",
                "features": 10, "change_request": True,
                "replicate": 1, "replicates_per_model_arm": 1, "status": "completed"}
        cells.append(cell)
        run = directory / "runs" / run_id
        run.mkdir(parents=True)
        records = [record(arm, run_id, k) for k in range(1, 11)] + [record(arm, run_id, 10, True)]
        (run / "steps.jsonl").write_text("".join(json.dumps(row) + "\n" for row in records))
    state = {"status": "completed", "identity": {"smoke": True, "study_id": "secret-study-id",
                                              "model_roster": ["secret-development-model"]}, "cells": cells}
    (directory / "state.json").write_text(json.dumps(state))
    return directory


@pytest.fixture
def bundle(judge, archive, tmp_path):
    output = tmp_path / "judging"
    judge.prepare(archive, output, "sha256:" + "1" * 64, diagnostic=True,
                  collector=lambda repo, commit, k, cr, image, scratch: outcomes(judge, k, cr))
    return output


def config(judge, *, credits=10, ceiling=1000):
    return {"schema": judge.SCHEMA,
            "judges": [{"id": "test-judge", "model": "diagnostic-model", "version": "diagnostic-v1",
                        "command": [sys.executable, "unused-diagnostic-command"]}],
            "repeats": 2, "timeout_seconds": 30, "per_call_credits": credits, "ceiling_credits": ceiling}


def response_for(request, credits=1):
    rows = []
    for scenario in request["specimen"]["scenarios"]:
        final = scenario["final"]
        value = None if final["status"] == "unavailable" else 4 if final["status"] == "passed" else 0
        citations = [row["id"] for row in final["observations"][:1]]
        if not citations and final["error_type"]:
            citations = [f"{scenario['id']}:error"]
        rows.append({"scenario_id": scenario["id"], "scores": {dimension: value for dimension in (
            "functional_completeness", "workflow_coherence", "error_recovery", "api_usability")},
                     "evidence_ids": citations, "rationale": "Diagnostic fixture, not an AI assessment."})
    return {"judge_id": request["judge"]["id"], "judge_version": request["judge"]["version"],
            "model": request["judge"]["model"],
            "usage": {"credits_complete": True, "totalNanoAiu": credits * 1_000_000_000},
            "verdict": {"scenarios": rows}}


def caller(command, request, directory, timeout):
    return response_for(request)


def test_given_allocated_archive_when_preparing_then_every_endpoint_is_blinded(judge, bundle):
    manifest, mapping, packets = judge.frozen_bundle(bundle)

    assert len(packets) == 10
    assert len(mapping["allocated_cells"]) == 5
    for packet in packets.values():
        public = json.dumps(packet)
        for forbidden in ("secret-dev", "secret-development-model", "secret-study-id", "assigned_model",
                          '"arm"', "DESIGN.md", "REVIEW.md", "a" * 40):
            assert forbidden not in public
    assert manifest["diagnostic"] is True


def test_given_fixed_panel_when_checking_eligibility_then_future_contracts_are_not_baselines(judge):
    assert [item.id for item in judge.eligible(1)] == ["registration"]
    assert len(judge.eligible(10)) == 11
    assert len(judge.eligible(10, True)) == 12
    assert all("cr1" not in item.features for item in judge.eligible(10))


@pytest.mark.parametrize(("final", "history", "expected"), [
    ("failed", ["passed", "failed"], "observed_loss"),
    ("passed", ["passed", "unavailable"], "retained"),
    ("failed", ["failed", "failed"], "never_observed_pass"),
    ("failed", [], "never_observed_pass"),
    ("failed", ["unavailable"], "no_prior_pass_observed_incomplete_history"),
    ("unavailable", ["passed"], "unavailable"),
    ("passed", ["failed"], "passing_without_prior_witness"),
])
def test_given_temporal_observations_when_classifying_then_acquisition_and_loss_stay_distinct(
        judge, final, history, expected):
    assert judge.retention({"status": final}, [{"status": item} for item in history]) == expected


@pytest.mark.parametrize("change", ["omit", "duplicate", "float", "boolean", "invented-citation", "uncited", "extra"])
def test_given_malformed_rating_when_validating_then_it_is_rejected(judge, bundle, change):
    _, _, packets = judge.frozen_bundle(bundle)
    packet = next(iter(packets.values()))
    request = judge.request_for(packet, config(judge)["judges"][0], config(judge))
    verdict = response_for(request)["verdict"]
    row = verdict["scenarios"][0]
    if change == "omit":
        verdict["scenarios"].pop()
    elif change == "duplicate":
        verdict["scenarios"].append(copy.deepcopy(row))
    elif change in ("float", "boolean"):
        row["scores"]["api_usability"] = 3.0 if change == "float" else True
    elif change == "invented-citation":
        row["evidence_ids"] = ["made-up:999"]
    elif change == "uncited":
        row["evidence_ids"] = []
    else:
        row["arm_guess"] = "A"

    with pytest.raises(judge.StudyError):
        judge.validate_verdict(verdict, packet)


def test_given_unknown_endpoint_when_judging_then_scores_cannot_be_imputed(judge):
    packet = {"scenarios": [{"id": "registration", "final": {
        "status": "unavailable", "observations": [], "error_type": None}}]}
    row = {"scenario_id": "registration", "scores": {dimension: None for dimension in judge.DIMENSIONS},
           "evidence_ids": [], "rationale": "No execution evidence."}
    judge.validate_verdict({"scenarios": [row]}, packet)
    row["scores"]["api_usability"] = 0

    with pytest.raises(judge.StudyError, match="Unavailable"):
        judge.validate_verdict({"scenarios": [row]}, packet)

def test_given_demonstrated_failure_when_judge_claims_perfect_fulfilment_then_it_is_rejected(judge):
    packet = {"scenarios": [{"id": "registration", "final": {
        "status": "failed", "error_type": None,
        "observations": [{"id": "registration:1", "actual": 0, "expected": 1, "outcome": "failed"}]}}]}
    row = {"scenario_id": "registration", "scores": {dimension: 4 for dimension in judge.DIMENSIONS},
           "evidence_ids": ["registration:1"], "rationale": "Contradictory perfect fulfilment."}

    with pytest.raises(judge.StudyError, match="contradicts"):
        judge.validate_verdict({"scenarios": [row]}, packet)


def test_given_changed_packet_or_mapping_when_resuming_then_seal_stops_judging(judge, bundle):
    path = bundle / "private/mapping.json"
    mapping = judge.read_json(path)
    mapping["specimens"][next(iter(mapping["specimens"]))]["arm"] = "C"
    path.write_text(json.dumps(mapping))

    with pytest.raises(judge.StudyError, match="changed"):
        judge.frozen_bundle(bundle)


def test_given_completed_ratings_when_resuming_then_no_call_is_replayed(judge, bundle):
    calls = []

    def track(command, request, directory, timeout):
        calls.append(request)
        return response_for(request)

    first = judge.run_judges(bundle, config(judge), caller=track)
    second = judge.run_judges(bundle, config(judge), caller=track)
    summary = judge.report(bundle)

    assert first == second
    assert len(calls) == 20
    assert len(summary["runs"]) == 10
    assert all(item["difference"] == 0 for item in summary["contrasts"].values())
    assert (bundle / "report.csv").is_file()
    assert summary["diagnostic"] is True


def test_given_unknown_charge_when_resuming_then_original_reservation_blocks_admission(judge, bundle):
    calls = []

    def unknown(command, request, directory, timeout):
        calls.append(request)
        response = response_for(request)
        response["usage"] = {"credits_complete": False, "totalNanoAiu": None}
        return response

    with pytest.raises(judge.StudyError, match="unknown"):
        judge.run_judges(bundle, config(judge), caller=unknown)
    with pytest.raises(judge.StudyError, match="reconciliation"):
        judge.run_judges(bundle, config(judge), caller=unknown)

    ledger = judge.read_json(bundle / "private/judges.json")
    assert len(calls) == 1
    call = next(iter(ledger["calls"].values()))
    assert call["actual_nano"] is None and call["reserved_nano"] == 10 * 1_000_000_000
    assert call["status"] == "blocked"


def test_given_credit_ceiling_when_admitting_then_no_extra_call_is_started(judge, bundle):
    calls = []

    def track(command, request, directory, timeout):
        calls.append(request)
        return response_for(request, credits=10)

    with pytest.raises(judge.StudyError, match="ceiling"):
        judge.run_judges(bundle, config(judge, ceiling=10), caller=track)
    assert len(calls) == 1


def test_given_adapter_overspend_when_admitting_then_further_calls_stop(judge, bundle):
    with pytest.raises(judge.StudyError, match="reservation"):
        judge.run_judges(bundle, config(judge), caller=lambda command, request, directory, timeout:
                         response_for(request, credits=11))

    call = next(iter(judge.read_json(bundle / "private/judges.json")["calls"].values()))
    assert call["actual_nano"] == 11 * 1_000_000_000
    assert call["status"] == "blocked"


def test_given_changed_judge_config_when_resuming_then_new_models_are_not_substituted(judge, bundle):
    cfg = config(judge)
    judge.run_judges(bundle, cfg, caller=caller)
    cfg["judges"][0]["model"] = "substituted-model"

    with pytest.raises(judge.StudyError, match="configuration"):
        judge.run_judges(bundle, cfg, caller=caller)


def test_given_exclusive_writer_when_starting_second_command_then_it_stops_before_spending(judge, bundle):
    with judge.judging_lock(bundle):
        with pytest.raises(judge.StudyError, match="Another"):
            judge.run_judges(bundle, config(judge), caller=caller)

    assert not (bundle / "private/judges.json").exists()


def test_given_missing_final_step_when_reporting_then_no_last_observed_endpoint_is_substituted(
        judge, archive, tmp_path):
    path = archive / "runs/secret-dev-A-01/steps.jsonl"
    records = [json.loads(line) for line in path.read_text().splitlines()]
    path.write_text("".join(json.dumps(row) + "\n" for row in records if row["step"] != "f10-feature"))
    output = tmp_path / "partial-judging"
    judge.prepare(archive, output, "sha256:" + "1" * 64, diagnostic=True,
                  collector=lambda repo, commit, k, cr, image, scratch: outcomes(judge, k, cr))
    judge.run_judges(output, config(judge), caller=caller)
    summary = judge.report(output)

    row = next(row for row in summary["runs"] if row["arm"] == "A" and row["endpoint"] == "p10")
    assert all(value["final"] == "unavailable" for value in row["scenario_outcomes"].values())
    assert row["scores"]["functional_completeness"]["mean"] is None
    assert row["previously_passing_scenarios"] > 0
    assert row["risk_set_unavailable_scenarios"] > 0
    assert row["loss_density"] is None
    assert summary["contrasts"]["p10:B-A:functional_completeness"]["difference"] is None
    assert summary["contrasts"]["cr1:B-A:functional_completeness"]["difference"] == 0


def test_given_real_regression_when_preparing_then_earlier_pass_supplies_loss_witness(judge, archive, tmp_path):
    def regress(repo, commit, k, cr, image, scratch):
        rows = outcomes(judge, k, cr)
        if k == 10:
            rows[0]["status"] = "failed"
            rows[0]["observations"][0].update(actual=0, outcome="failed")
        return rows

    output = tmp_path / "regressed-judging"
    judge.prepare(archive, output, "sha256:" + "1" * 64, diagnostic=True, collector=regress)
    _, _, packets = judge.frozen_bundle(output)

    for packet in packets.values():
        scenario = packet["scenarios"][0]
        assert scenario["retention"] == "observed_loss"
        assert scenario["earlier_passing_witness"]["status"] == "passed"


@pytest.mark.parametrize("status", ["running", "partial"])
def test_given_active_or_unapproved_incomplete_archive_when_preparing_then_it_is_refused(
        judge, archive, tmp_path, status):
    path = archive / "state.json"
    state = json.loads(path.read_text())
    state["status"] = status
    path.write_text(json.dumps(state))

    with pytest.raises(judge.StudyError):
        judge.prepare(archive, tmp_path / "refused", "sha256:" + "1" * 64, diagnostic=True)
    assert not (tmp_path / "refused").exists()


def test_given_linked_source_or_nested_output_when_preparing_then_archive_is_not_touched(judge, archive):
    with pytest.raises(judge.StudyError, match="separate"):
        judge.prepare(archive, archive / "judging", "sha256:" + "1" * 64, diagnostic=True)


def test_given_duplicate_or_nonfinite_json_when_reading_then_it_is_refused(judge, tmp_path):
    path = tmp_path / "malformed.json"
    for data in ('{"a":1,"a":2}', '{"a":NaN}', '[]'):
        path.write_text(data)
        with pytest.raises(judge.StudyError):
            judge.read_json(path)

def test_given_large_metadata_when_reading_then_reply_limits_remain_strict(judge, tmp_path):
    path = tmp_path / "large-metadata.json"
    value = {"padding": "x" * (judge.LIMIT + 4096)}
    path.write_text(json.dumps(value))

    assert judge.read_json(path, limit=judge.METADATA_LIMIT) == value
    with pytest.raises(judge.StudyError, match="oversized"):
        judge.read_json(path)
    with pytest.raises(judge.StudyError, match="oversized"):
        judge.read_json(path, limit=1024)


def test_given_full_study_metadata_when_preparing_then_private_mapping_is_not_truncated(judge, archive, tmp_path):
    path = archive / "state.json"
    state = json.loads(path.read_text())
    state["identity"]["private_diagnostic_padding"] = "x" * (judge.LIMIT + 4096)
    path.write_text(json.dumps(state))
    output = tmp_path / "large-study-bundle"
    judge.prepare(archive, output, "sha256:" + "1" * 64, diagnostic=True,
                  collector=lambda repo, commit, k, cr, image, scratch: outcomes(judge, k, cr))
    _, mapping, packets = judge.frozen_bundle(output)

    assert mapping["identity"]["private_diagnostic_padding"] == state["identity"]["private_diagnostic_padding"]
    assert (output / "private/mapping.json").stat().st_size > judge.LIMIT
    assert all("private_diagnostic_padding" not in json.dumps(packet) for packet in packets.values())
    judge.run_judges(output, config(judge), caller=caller)
    assert len(judge.report(output)["runs"]) == 10


def test_given_completed_judgments_when_storing_then_ledger_has_only_hash_bound_response_references(judge, bundle):
    judge.run_judges(bundle, config(judge), caller=caller)
    ledger = judge.read_json(bundle / "private/judges.json", limit=judge.METADATA_LIMIT)

    for key, call in ledger["calls"].items():
        assert "response" not in call
        response = judge.read_json(bundle / "private" / key / "validated-response.json")
        assert call["response_sha256"] == judge.digest(response)
    assert (bundle / "private/judges.json").stat().st_size < sum(
        (bundle / "private" / key / "validated-response.json").stat().st_size for key in ledger["calls"])
    judge.run_judges(bundle, config(judge), caller=lambda *args: pytest.fail("No completed call may be replayed"))


def test_given_tampered_per_call_response_when_resuming_then_no_new_spend_or_report_is_allowed(judge, bundle):
    judge.run_judges(bundle, config(judge), caller=caller)
    ledger = judge.read_json(bundle / "private/judges.json", limit=judge.METADATA_LIMIT)
    key = next(iter(ledger["calls"]))
    path = bundle / "private" / key / "validated-response.json"
    response = judge.read_json(path)
    response["verdict"]["scenarios"][0]["scores"]["api_usability"] = 0
    path.write_text(json.dumps(response))

    with pytest.raises(judge.StudyError, match="response changed"):
        judge.run_judges(bundle, config(judge), caller=lambda *args: pytest.fail("No new call permitted"))
    with pytest.raises(judge.StudyError, match="response changed"):
        judge.report(bundle)

def test_given_missing_declared_model_when_preparing_then_survivor_frame_is_refused(judge, archive, tmp_path):
    path = archive / "state.json"
    state = json.loads(path.read_text())
    state["identity"]["model_roster"].append("missing-development-model")
    path.write_text(json.dumps(state))

    with pytest.raises(judge.StudyError, match="roster"):
        judge.prepare(archive, tmp_path / "missing-model", "sha256:" + "1" * 64, diagnostic=True)


def test_given_missing_allocated_replicate_when_preparing_then_frame_is_refused(judge, archive, tmp_path):
    path = archive / "state.json"
    state = json.loads(path.read_text())
    state["identity"]["analysis_design"] = "model-stratified-v2-five-arm"
    state["cells"].pop()
    path.write_text(json.dumps(state))

    with pytest.raises(judge.StudyError, match="replicate frame"):
        judge.prepare(archive, tmp_path / "missing-cell", "sha256:" + "1" * 64, diagnostic=True)


def test_given_edited_actual_charge_when_resuming_then_no_fresh_spend_is_admitted(judge, bundle):
    judge.run_judges(bundle, config(judge), caller=caller)
    path = bundle / "private/judges.json"
    ledger = judge.read_json(path)
    next(iter(ledger["calls"].values()))["actual_nano"] = 0
    path.write_text(json.dumps(ledger))

    with pytest.raises(judge.StudyError, match="consumption changed"):
        judge.run_judges(bundle, config(judge), caller=caller)


def test_given_failed_adapter_when_invoked_then_bounded_private_diagnostics_are_retained(judge, tmp_path):
    directory = tmp_path / "failed-adapter"
    command = [sys.executable, "-c",
               "import sys; print('partial output'); sys.stderr.write('safe startup diagnostic\\n'); sys.exit(2)"]

    with pytest.raises(judge.StudyError, match="consumption must be reconciled"):
        judge.invoke(command, {"diagnostic": True}, directory, 10)

    assert (directory / "adapter.stdout").read_text() == "partial output\n"
    assert (directory / "adapter.stderr").read_text() == "safe startup diagnostic\n"
    saved = judge.read_json(directory / "adapter-exit.json")
    assert saved["return_code"] == 2 and saved["response_recorded"] is False
    assert saved["stdout_bytes"] <= judge.LIMIT and saved["stderr_bytes"] <= judge.LIMIT
    assert (directory / "adapter.stderr").stat().st_mode & 0o777 == 0o600


def test_given_resilience_policy_when_verdict_slip_recovers_then_all_attempt_charges_are_accounted(judge, bundle):
    cfg = config(judge)
    cfg["resilience"] = {
        "max_attempts_per_call": 2, "max_quarantined_calls": 2,
        "max_quarantined_credits": 20, "retry_backoff_seconds": 0,
    }
    cfg["workers"] = 4
    first_seen = set()

    def flaky(command, request, directory, timeout):
        directory.mkdir(parents=True, exist_ok=True)
        resp = response_for(request, credits=1)
        spec_id = request["specimen"]["specimen_id"]
        if spec_id not in first_seen and len(first_seen) == 0:
            first_seen.add(spec_id)
            resp["verdict"]["scenarios"][0].pop("evidence_ids")
        return resp

    result = judge.run_judges(bundle, cfg, caller=flaky)
    summary = judge.report(bundle)

    assert result["completed_calls"] == 20
    assert result["quarantined_calls"] == 0
    assert result["actual_nano"] == 21 * 1_000_000_000
    assert summary["judging_consumption"]["known_actual_nano"] == 21 * 1_000_000_000
    assert summary["judging_consumption"]["failed_retry_attempts"] == 1


def test_given_persistent_malformed_call_under_resilience_when_within_bounds_then_it_quarantines_without_halting(
        judge, bundle):
    cfg = config(judge)
    cfg["resilience"] = {
        "max_attempts_per_call": 2, "max_quarantined_calls": 1,
        "max_quarantined_credits": 20, "retry_backoff_seconds": 0,
    }
    target = next(iter(judge.frozen_bundle(bundle)[2]))

    def quarantine_one(command, request, directory, timeout):
        directory.mkdir(parents=True, exist_ok=True)
        resp = response_for(request, credits=1)
        if request["specimen"]["specimen_id"] == target and directory.name.endswith("-1") or (
                request["specimen"]["specimen_id"] == target and "-1-attempt-" in directory.name):
            resp["verdict"]["scenarios"][0].pop("evidence_ids")
        return resp

    result = judge.run_judges(bundle, cfg, caller=quarantine_one)
    resumed = judge.run_judges(bundle, cfg, caller=lambda *args: pytest.fail("Quarantined calls must not auto-replay"))
    summary = judge.report(bundle)

    assert result == resumed
    assert result["completed_calls"] == 19
    assert result["quarantined_calls"] == 1
    assert summary["judging_consumption"]["complete"] is False
    assert summary["judging_consumption"]["quarantined_calls"] == 1


def test_given_real_json_command_adapter_when_running_then_stdin_and_report_work(judge, bundle, tmp_path):
    script = tmp_path / "adapter.py"
    script.write_text(
        "import json,sys\n"
        f"sys.path.insert(0,{str(Path(__file__).parent)!r})\n"
        "from test_judge import response_for\n"
        "request=json.load(sys.stdin)\n"
        "print(json.dumps(response_for(request,credits=0)))\n")
    cfg = config(judge)
    cfg["judges"][0]["command"] = [sys.executable, str(script)]

    result = judge.run_judges(bundle, cfg)
    summary = judge.report(bundle)

    assert result["actual_nano"] == 0
    assert len(summary["runs"]) == 10


def test_given_no_paid_authorization_when_cli_runs_then_it_stops_without_an_adapter(judge, bundle, tmp_path):
    result = subprocess.run([sys.executable, str(ROOT / "judging/judge.py"), "run",
                             "--output", str(bundle), "--config", str(tmp_path / "not-even-read.json")],
                            capture_output=True, text=True, timeout=10)

    assert result.returncode == 1
    assert "no model was called" in result.stderr
    assert not (bundle / "private/judges.json").exists()


@pytest.mark.parametrize("snapshot", [f"f{k:02d}" for k in range(1, 11)] + ["cr1"])
def test_given_trusted_reference_when_exercising_panel_then_all_eligible_workflows_pass(judge, tmp_path, snapshot):
    k = 10 if snapshot == "cr1" else int(snapshot[1:])
    path = tmp_path / "reference-evidence.json"
    result = subprocess.run([sys.executable, str(ROOT / "judging/execute.py"),
                             "--src", str(ROOT / "suites/s1-retrofit/reference" / snapshot),
                             "--k", str(k), "--out", str(path), *(["--cr"] if snapshot == "cr1" else [])],
                            capture_output=True, text=True, timeout=15)

    assert result.returncode == 0, result.stderr
    rows = judge.validate_evidence(judge.read_json(path), k, snapshot == "cr1")
    assert all(row["status"] == "passed" for row in rows), rows


def test_given_missing_candidate_package_when_executing_then_it_is_failure_not_unavailable(judge, tmp_path):
    source = tmp_path / "empty-source"
    source.mkdir()
    path = tmp_path / "missing-package.json"
    subprocess.run([sys.executable, str(ROOT / "judging/execute.py"), "--src", str(source),
                    "--k", "1", "--out", str(path)], check=True, timeout=15)
    result = judge.validate_evidence(judge.read_json(path), 1, False)[0]

    assert result["status"] == "failed"
    assert result["error_type"] == "ModuleNotFoundError"


def git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True,
                            check=True, timeout=15)
    return result.stdout.strip()


def make_real_archive(archive):
    state_path = archive / "state.json"
    state = json.loads(state_path.read_text())
    state["cells"] = [state["cells"][0]]
    state_path.write_text(json.dumps(state))
    cell = state["cells"][0]
    directory = archive / "runs" / cell["run_id"]
    repo = directory / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "diagnostic")
    git(repo, "config", "user.email", "diagnostic@example.invalid")
    package = repo / "src/workbench"
    package.mkdir(parents=True)
    (repo / "runtime-config.json").write_text('{"synthetic_runtime_asset":true}')
    (repo / "runtime-helper").write_text("#!/bin/sh\nexit 0\n")
    (repo / "runtime-helper").chmod(0o755)
    records = []
    for snapshot in [f"f{k:02d}" for k in range(1, 11)] + ["cr1"]:
        code = (ROOT / "suites/s1-retrofit/reference" / snapshot / "workbench/__init__.py").read_bytes()
        (package / "__init__.py").write_bytes(code)
        (repo / "DESIGN.md").write_text("secret arm A and development model, never show a judge")
        git(repo, "add", "-A")
        git(repo, "commit", "-qm", "diagnostic reference snapshot")
        cr = snapshot == "cr1"
        records.append(record("A", cell["run_id"], 10 if cr else int(snapshot[1:]), cr,
                              git(repo, "rev-parse", "HEAD")))
    (directory / "steps.jsonl").write_text("".join(json.dumps(row) + "\n" for row in records))
    return repo, records


def test_given_canonical_repository_when_exporting_then_runtime_assets_are_preserved_without_git_metadata(
        judge, archive, tmp_path):
    repo, records = make_real_archive(archive)
    before = git(repo, "rev-parse", "HEAD")
    output = tmp_path / "export"
    output.mkdir()
    judge.export_source(repo, records[0]["measure"]["head"], output)

    assert (output / "src/workbench/__init__.py").read_bytes() == (
        ROOT / "suites/s1-retrofit/reference/f01/workbench/__init__.py").read_bytes()
    assert (output / "runtime-config.json").read_bytes() == (repo / "runtime-config.json").read_bytes()
    assert (output / "runtime-helper").stat().st_mode & 0o111
    assert (output / "DESIGN.md").read_bytes() == (repo / "DESIGN.md").read_bytes()
    assert not (output / ".git").exists()
    assert git(repo, "rev-parse", "HEAD") == before
    assert git(repo, "status", "--porcelain") == ""


def test_given_committed_source_symlink_when_exporting_then_it_is_rejected(judge, archive, tmp_path):
    repo, _ = make_real_archive(archive)
    (repo / "src/host-link").symlink_to("/etc/passwd")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "diagnostic hostile link")
    output = tmp_path / "export-link"
    output.mkdir()

    with pytest.raises(judge.StudyError, match="nonregular"):
        judge.export_source(repo, git(repo, "rev-parse", "HEAD"), output)
    assert not (output / "src/host-link").exists()


@pytest.mark.skipif(not os.environ.get("JUDGING_TEST_IMAGE"), reason="explicit local isolated image not supplied")
def test_given_isolated_reference_archive_when_preparing_then_pipeline_preserves_source_and_detects_retention(
        judge, archive, tmp_path):
    repo, _ = make_real_archive(archive)
    before = git(repo, "rev-parse", "HEAD")
    state_before = (archive / "state.json").read_bytes()
    source_before = (repo / "src/workbench/__init__.py").read_bytes()
    output = tmp_path / "isolated-judging"
    result = judge.prepare(archive, output, os.environ["JUDGING_TEST_IMAGE"], diagnostic=True)
    judge.run_judges(output, config(judge), caller=caller)
    summary = judge.report(output)

    assert result["unavailable_checkpoints"] == 0
    assert len(summary["runs"]) == 2
    assert all(row["observed_losses"] == 0 for row in summary["runs"])
    assert all(value["final"] == "passed" for row in summary["runs"]
               for value in row["scenario_outcomes"].values())
    assert (archive / "state.json").read_bytes() == state_before
    assert (repo / "src/workbench/__init__.py").read_bytes() == source_before
    assert git(repo, "rev-parse", "HEAD") == before
    assert git(repo, "status", "--porcelain") == ""
