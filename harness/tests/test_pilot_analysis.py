"""Synthetic prospective-estimand regressions; no model sessions."""
import copy
import importlib
import json
import sys
from pathlib import Path

import pytest


@pytest.fixture
def pilot(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    return importlib.import_module("pilot_analysis")


@pytest.fixture
def panel():
    return {"suite": "synthetic", "review": {"accepted": True, "evidence": "synthetic review"},
            "contracts": [{"id": name, "feature": feature, "role": role, "from_cycle": start,
                           "through_cycle": end, "unchanged": True, "oracle_version": "v1"}
                          for name, feature, role, start, end in (
                              ("test_f01::test_x", "f01", "feature", 1, 10),
                              ("test_f02::test_y", "f02", "feature", 2, 10),
                              ("test_cr1::test_cr", "cr1", "cr1", 11, 11))]}


def rec(kind, k, x="passed", y="passed", cr=None):
    hidden = {"test_f01::test_x": x}
    if k >= 2:
        hidden["test_f02::test_y"] = y
    if cr is not None:
        hidden["test_cr1::test_cr"] = cr
    return {"kind": kind, "k": k, "measure": {"hidden": hidden, "hidden_total": len(hidden),
            "hidden_passed": sum(value == "passed" for value in hidden.values())},
            "agent": {"seconds": 1, "usage": {"credits_complete": True, "totalNanoAiu": 1000000000}}}


def raw(records, arm="B", features=3, run_id="synthetic",
        assigned_model=None, analysis_design=None, replicate=None):
    meta = {"arm": arm, "features": features, "run_id": run_id,
            "suite": "synthetic", "phase": "pilot-estimation", "change_request": True,
            "intervention": {"coverage_complete": True, "assisted": False, "evidence": "fixture"}}
    if assigned_model is not None:
        meta["assigned_model"] = assigned_model
    if analysis_design is not None:
        meta["analysis_design"] = analysis_design
    if replicate is not None:
        meta["replicate"] = replicate
    return {"dir": "", "meta": meta, "recs": records}


def cohort():
    runs = []
    for arm in "ABC":
        for index in range(4):
            records = []
            for k in range(1, 11):
                records.append(rec("feature", k))
                if arm != "A":
                    records.append(rec("consolidation" if arm == "B" else "review", k))
            records.append(rec("change_request", 10, cr="passed"))
            runs.append(raw(records, arm, 10, f"{arm}-{index}"))
    return runs


def cells_for(runs):
    cells = []
    for run in runs:
        attempts = []
        for index, record in enumerate(run["recs"]):
            step = "cr1-change" if record["kind"] == "change_request" else f"f{record['k']:02}-{record['kind']}"
            attempt_id = f"{run['meta']['run_id']}-{index}"
            record["attempts"] = [attempt_id]
            attempts.append({"id": attempt_id, "step": step, **record["agent"]})
        cells.append({key: run["meta"][key] for key in (
            "run_id", "arm", "features", "change_request", "assigned_model", "analysis_design", "replicate")
            if key in run["meta"]} | {"attempts": attempts})
    return cells


def test_inherited_cohort_requires_earlier_p_not_current_f(pilot, panel):
    run = raw([rec("feature", 1), rec("consolidation", 1, x="failed"),
               rec("feature", 2, x="failed"), rec("consolidation", 2, x="failed")], features=2)
    history = pilot.retention(run, panel)
    assert [row["risk_set"] for row in history["rows"]] == [0, 0, 0, 0]
    assert history["rows"][1]["same_cycle_post_losses"] == 1
    assert all(row["density"] is None for row in history["rows"])
    assert history["rows"][2]["never_passed"] == 2


def test_paired_losses_repair_recurrence_and_duration(pilot, panel):
    records = [rec("feature", 1), rec("consolidation", 1),
               rec("feature", 2, x="failed"), rec("consolidation", 2),
               rec("feature", 3, x="failed"), rec("consolidation", 3, x="failed")]
    history = pilot.retention(raw(records), panel)
    assert [row["open_losses"] for row in history["rows"]] == [0, 0, 1, 0, 1, 1]
    assert history["post_loss_test_cycles"] == 1
    first, second = history["episodes"]
    assert first["duration_cycles"] == 0 and first["recovery_checkpoint"] == "P"
    assert second["recurrence"] and second["censored"]
    assert history["rows"][2]["groups"]["f02"]["risk_set"] == 0


@pytest.mark.parametrize("outcome", ["error", "skipped", "timeout"])
def test_unknown_observations_do_not_create_losses_or_recoveries(pilot, panel, outcome):
    records = [rec("feature", 1), rec("consolidation", 1),
               rec("feature", 2, x="failed"), rec("consolidation", 2, x=outcome),
               rec("feature", 3), rec("consolidation", 3)]
    history = pilot.retention(raw(records), panel)
    assert history["rows"][3]["open_losses"] is None
    assert history["episodes"][0]["uncertain"]
    assert history["episodes"][0]["duration_cycles"] is None
    assert history["post_loss_test_cycles"] is None


def test_missing_p_leaves_acquisition_membership_uncertain(pilot, panel):
    history = pilot.retention(raw([rec("feature", 1), rec("feature", 2),
                                  rec("consolidation", 2)], features=2), panel)
    assert history["rows"][2]["risk_set"] == 0
    assert history["rows"][2]["risk_complete"] is False
    assert history["rows"][2]["never_passed"] is None


def test_ineligible_changed_contract_is_not_a_regression(pilot, panel):
    panel["contracts"][0]["through_cycle"] = 1
    history = pilot.retention(raw([rec("feature", 1), rec("consolidation", 1),
                                  rec("feature", 2, x="failed"), rec("consolidation", 2, x="failed")],
                                 features=2), panel)
    assert history["rows"][-1]["eligible"] == 1
    assert history["rows"][-1]["open_losses"] == 0


def test_never_passed_is_acquisition_failure_not_decay(pilot, panel):
    run = raw([rec("feature", k, x="failed", y="failed") for k in range(1, 4)], arm="A")
    history = pilot.retention(run, panel)
    assert history["episodes"] == []
    assert all(row["open_losses"] == 0 and row["density"] is None for row in history["rows"])


def test_complete_allocation_has_run_level_estimates_and_exact_cr_intervals(pilot, panel):
    result = pilot.analyze_pilot(cohort(), panel=panel, n=100)
    assert result["allocation_complete"] and result["primary_estimates_available"]
    assert result["endpoints"]["H1"]["B-A"]["difference"] == 0
    assert result["endpoints"]["H6"]["B-C"]["difference_points"] == 0
    assert result["endpoints"]["H6"]["B-A"]["ci"][0] < 0
    assert result["arms"]["A"]["success_bounds"] == [1, 1]
    assert "verdict" not in json.dumps(result) and '"p"' not in json.dumps(result)


def test_missing_cr_uses_all_allocated_bounds_not_complete_cases(pilot, panel):
    runs = cohort()
    runs[0]["recs"].pop()
    result = pilot.analyze_pilot(runs, panel=panel, n=100)
    assert result["arms"]["A"]["success_bounds"] == [.75, 1]
    assert result["arms"]["A"]["missing"] == 1
    assert result["endpoints"]["H6"]["B-A"]["difference_points"] is None
    assert result["endpoints"]["H6"]["B-A"]["identification_bounds_points"] == [0, 25]
    assert result["arms"]["A"]["cr1_all_attempt_cost"] is None


def test_agent_terminal_failure_differs_from_infrastructure_and_zero_needs_evidence(pilot, panel):
    run = raw([], features=10)
    assert pilot.summarise_pilot(run, panel)["cr_success"] is None
    run["meta"]["cr1_disposition"] = {"cause": "infrastructure", "terminal": True, "evidence": "fixture"}
    assert pilot.summarise_pilot(run, panel)["cr_success"] is None
    run["meta"]["cr1_disposition"].update(cause="agent", no_billable_session=True)
    summary = pilot.summarise_pilot(run, panel)
    assert summary["cr_success"] is False and summary["all_attempt_cr_cost"] == 0


def test_assisted_and_unknown_intervention_runs_remain_but_disable_primary(pilot, panel):
    runs = cohort()
    runs[0]["meta"]["intervention"]["assisted"] = True
    runs[1]["meta"].pop("intervention")
    result = pilot.analyze_pilot(runs, panel=panel, n=100)
    assert len(result["runs"]) == 12
    assert result["arms"]["A"]["intervention"] == {"assisted": 1, "unknown": 1, "unassisted": 2}
    assert result["endpoints"]["H1"]["B-A"]["difference"] is None


def test_unreviewed_panel_cannot_supply_primary_decay_estimate(pilot, panel):
    panel["review"]["accepted"] = False
    result = pilot.analyze_pilot(cohort(), panel=panel, n=100)
    assert result["endpoints"]["H2"]["B-A"]["final_P10_count"]["difference"] is None
    assert result["runs"][0]["retention"]["rows"]


def test_stage_aliases_and_mixed_roles_are_not_pooled(pilot, panel):
    assert pilot.collection_role({"phase": "pilot"}) == "calibration"
    assert pilot.collection_role({"phase": "first"}) == "pilot-estimation"
    runs = cohort()[:2]
    runs[1]["meta"]["phase"] = "calibration"
    with pytest.raises(ValueError, match="Mixed collection"):
        pilot.analyze_pilot(runs, panel=panel)
    with pytest.raises(ValueError, match="disagrees"):
        pilot.collection_role({"phase": "pilot", "collection_role": "pilot-estimation"})


def test_all_attempt_cost_keeps_failed_unknown_and_stopped_sessions(pilot, panel):
    run = raw([], features=10)
    attempts = [{"step": "f01-feature", "seconds": 1,
                 "usage": {"credits_complete": True, "totalNanoAiu": 2000000000}},
                {"step": "cr1-change", "seconds": 2, "usage": None},
                {"step": "cr1-change", "seconds": 3,
                 "usage": {"credits_complete": True, "totalNanoAiu": 3000000000}}]
    result = pilot.summarise_pilot(run, panel, cell={"attempts": attempts})
    assert result["all_attempt_delivery_cost"] == 2
    assert result["all_attempt_cr_cost"] is None
    attempts[1]["usage"] = {"credits_complete": True, "totalNanoAiu": 4000000000}
    assert pilot.summarise_pilot(run, panel, cell={"attempts": attempts})["all_attempt_cr_cost"] == 7


def test_zero_success_conditional_cost_is_undefined(pilot, panel):
    runs = cohort()
    for run in runs:
        run["recs"][-1] = rec("change_request", 10, cr="failed")
    result = pilot.analyze_pilot(runs, panel=panel, n=100, cells=cells_for(runs))
    assert result["arms"]["B"]["cr1_successful_only_mean_cost"] is None
    assert result["arms"]["B"]["cr1_all_attempt_cost"] == 4
    assert result["arms"]["B"]["success_bounds"] == [0, 0]


def test_missing_cr_contract_and_duplicate_checkpoint_are_unavailable(pilot, panel):
    run = cohort()[0]
    run["recs"][-1] = rec("change_request", 10)
    assert pilot.summarise_pilot(run, panel)["cr_success"] is None
    run["recs"].insert(0, copy.deepcopy(run["recs"][0]))
    assert pilot.summarise_pilot(run, panel)["retention"]["history_complete"] is False
    run = cohort()[0]
    run["recs"].append({"record_error": "Synthetic malformed JSON"})
    assert pilot.summarise_pilot(run, panel)["retention"]["post_loss_test_cycles"] is None


def test_missing_feature_plan_and_oracle_errors_are_unknown_not_failure(pilot, panel):
    run = raw([rec("feature", 1)], arm="A")
    run["meta"]["features"] = None
    summary = pilot.summarise_pilot(run, panel)
    assert summary["end"] is None and summary["series"][0]["open_regressions"] is None
    run = cohort()[0]
    run["recs"][-1] = rec("change_request", 10, cr="error")
    assert pilot.summarise_pilot(run, panel)["cr_success"] is None
    run["recs"][-2] = rec("feature", 10, x="timeout")
    assert pilot.summarise_pilot(run, panel)["end"]["pass_rate"] is None


def test_default_cli_writes_estimates_and_paired_exports(pilot, panel, monkeypatch, tmp_path):
    analysis = importlib.import_module("analyze")
    importlib.import_module("study_report")
    monkeypatch.setattr(analysis, "load_runs", lambda *_: cohort())
    monkeypatch.setattr(pilot, "load_panel", lambda: panel)
    monkeypatch.setattr(sys, "argv", ["analyze.py", "--runs", "synthetic", "--out", str(tmp_path)])
    analysis.main()
    result = json.loads((tmp_path / "summary.json").read_text())
    assert result["mode"] == "pilot-estimation" and len(result["runs"]) == 12
    assert "verdict" not in (tmp_path / "hypotheses.csv").read_text()
    assert (tmp_path / "retention.csv").is_file() and (tmp_path / "episodes.csv").is_file()


def test_h2_final_count_does_not_substitute_accumulated_losses(pilot, panel):
    runs = cohort()
    for run in runs:
        if run["meta"]["arm"] == "A":
            run["recs"][-2] = rec("feature", 10, x="failed")
        if run["meta"]["arm"] == "B":
            run["recs"][2:4] = [rec("feature", 2, x="failed"), rec("consolidation", 2, x="failed")]
    result = pilot.analyze_pilot(runs, panel=panel, n=100)
    h2 = result["endpoints"]["H2"]["B-A"]
    assert h2["final_P10_count"]["difference"] == -1
    assert h2["final_P10_count"]["ci"] == (-1, -1)
    assert h2["descriptive_accumulated_test_cycles"]["difference"] == 0


def test_final_outcomes_are_independent_of_missing_earlier_measurement(pilot, panel):
    for arm in "ABC":
        run = next(run for run in cohort() if run["meta"]["arm"] == arm)
        run["recs"][0].pop("measure")
        summary = pilot.summarise_pilot(run, panel)
        assert summary["end"]["pass_rate"] == 100 and summary["cr_success"] is True
        assert summary["retention"]["post_loss_test_cycles"] is None
        run["recs"][-2].pop("measure")
        summary = pilot.summarise_pilot(run, panel)
        assert summary["end"]["pass_rate"] is None and summary["cr_success"] is None


def test_raw_or_empty_attempt_accounting_is_unavailable_without_zero_evidence(pilot, panel):
    run = raw([rec("feature", 1)], arm="A", features=1)
    summary = pilot.summarise_pilot(run, panel)
    assert summary["observed_delivery_cost"] == 1
    assert summary["all_attempt_delivery_cost"] is None
    assert summary["all_attempt_cr_cost"] is None
    summary = pilot.summarise_pilot(run, panel, cell={"attempts": []})
    assert summary["all_attempt_delivery_cost"] is None and summary["all_attempt_cr_cost"] is None
    run["meta"]["cr1_disposition"] = {"no_billable_session": True, "evidence": "Synthetic billing record"}
    assert pilot.summarise_pilot(run, panel, cell={"attempts": []})["all_attempt_cr_cost"] == 0


def test_cli_journal_retains_unmeasured_costs_and_validates_phase_frame(pilot, panel, monkeypatch, tmp_path):
    analysis = importlib.import_module("analyze")
    importlib.import_module("study_report")
    runs = [raw([rec("feature", 1)], arm="A", features=10)]
    cells = cells_for(runs)
    cells[0]["attempts"].append({"id": "stopped", "step": "f02-feature", "seconds": 1,
                                "usage": {"credits_complete": True, "totalNanoAiu": 9000000000}})
    state = {"identity": {"phase": "pilot-estimation"}, "cells": cells}
    path = tmp_path / "journal.json"
    path.write_text(json.dumps(state))
    monkeypatch.setattr(analysis, "load_runs", lambda *_: runs)
    monkeypatch.setattr(pilot, "load_panel", lambda: panel)
    argv = ["analyze.py", "--runs", "synthetic", "--phase", "first", "--out", str(tmp_path / "report")]
    monkeypatch.setattr(sys, "argv", argv)
    analysis.main()
    assert json.loads((tmp_path / "report/summary.json").read_text())["runs"][0]["all_attempt_delivery_cost"] is None
    argv += ["--study-state", str(path)]
    analysis.main()
    result = json.loads((tmp_path / "report/summary.json").read_text())
    assert result["runs"][0]["all_attempt_delivery_cost"] == 10
    cells[0]["arm"] = "B"
    path.write_text(json.dumps(state))
    with pytest.raises(SystemExit) as stopped:
        analysis.main()
    assert stopped.value.code == 2
    state["identity"]["phase"] = "calibration"
    path.write_text(json.dumps(state))
    with pytest.raises(SystemExit) as stopped:
        analysis.main()
    assert stopped.value.code == 2


def test_journal_rejects_missing_or_duplicate_attempt_provenance(pilot, panel):
    runs = [raw([rec("feature", 1)], arm="A", features=1)]
    cells = cells_for(runs)
    cells[0]["attempts"].append(copy.deepcopy(cells[0]["attempts"][0]))
    with pytest.raises(ValueError, match="Duplicate attempt"):
        pilot.analyze_pilot(runs, panel=panel, cells=cells)
    cells[0]["attempts"] = []
    with pytest.raises(ValueError, match="absent"):
        pilot.analyze_pilot(runs, panel=panel, cells=cells)
    with pytest.raises(ValueError, match="allocation"):
        pilot.analyze_pilot(runs, panel=panel, cells=[])


MODEL_ROSTER = ["gpt-6.1-sol", "claude-sonnet-5.5", "gemini-4-argon"]


def stratified_run(model, arm, replicate, run_id=None):
    records = []
    for k in range(1, 11):
        records.append(rec("feature", k))
        if arm != "A":
            records.append(rec("consolidation" if arm == "B" else "review", k))
    records.append(rec("change_request", 10, cr="passed"))
    return raw(records, arm, 10, run_id or f"{model}-{arm}-{replicate}",
               assigned_model=model, analysis_design="model-stratified-v1", replicate=replicate)


def model_cohort():
    return [stratified_run(model, arm, replicate)
            for model in MODEL_ROSTER for arm in "ABC" for replicate in (1, 2)]


def test_legacy_unmarked_runs_keep_existing_frame_and_shape(pilot, panel):
    result = pilot.analyze_pilot(cohort(), panel=panel, n=100)
    assert "frame" not in result
    assert result["allocation_complete"] and len(result["runs"]) == 12
    assert result["arms"]["A"]["allocated"] == 4
    assert all(run["assigned_model"] is None and run["analysis_design"] is None for run in result["runs"])


def test_assigned_model_identity_is_read_from_meta_not_usage_telemetry(pilot, panel):
    run = stratified_run("claude-sonnet-5.5", "B", 1)
    run["recs"][0]["agent"]["usage"]["modelMetrics"] = {"gpt-6.1-sol": {}}
    summary = pilot.summarise_pilot(run, panel)
    assert summary["assigned_model"] == "claude-sonnet-5.5"
    assert summary["usage_quality"]["models"] == ["gpt-6.1-sol"]


def test_unapproved_model_identity_raises(pilot, panel):
    run = stratified_run("not-a-roster-model", "B", 1)
    with pytest.raises(ValueError, match="Unapproved model identity"):
        pilot.summarise_pilot(run, panel)


def test_missing_model_identity_in_marked_run_raises(pilot, panel):
    run = stratified_run("claude-sonnet-5.5", "B", 1)
    run["meta"]["assigned_model"] = None
    with pytest.raises(ValueError, match="Unapproved or missing model identity"):
        pilot.analyze_pilot([run], panel=panel, n=100)


def test_mixed_model_stratified_and_legacy_runs_raises(pilot, panel):
    runs = [stratified_run("claude-sonnet-5.5", "B", 1), cohort()[0]]
    with pytest.raises(ValueError, match="analyse separately"):
        pilot.analyze_pilot(runs, panel=panel, n=100)


def test_model_stratified_pilot_frame_requires_18_two_per_cell(pilot, panel):
    runs = model_cohort()
    result = pilot.analyze_pilot(runs, panel=panel, n=100)
    assert result["frame"] == "model-stratified-v1"
    assert result["allocation_complete"] and result["primary_estimates_available"]
    assert len(result["runs"]) == 18
    assert set(result["arms"]["B"]) == set(MODEL_ROSTER)
    assert result["arms"]["B"]["claude-sonnet-5.5"]["allocated"] == 2
    runs.pop()
    result = pilot.analyze_pilot(runs, panel=panel, n=100)
    assert result["allocation_complete"] is False
    assert result["arms"]["C"]["gemini-4-argon"]["missing"] == 1


def test_duplicate_model_identity_in_same_cell_raises(pilot, panel):
    runs = model_cohort()
    runs.append(stratified_run("claude-sonnet-5.5", "B", 1, run_id="dup"))
    with pytest.raises(ValueError, match="Duplicate model identity"):
        pilot.analyze_pilot(runs, panel=panel, n=100)


def test_model_specific_endpoints_are_primary_and_no_pooled_overall(pilot, panel):
    result = pilot.analyze_pilot(model_cohort(), panel=panel, n=100)
    assert set(result["endpoints"]) == set(MODEL_ROSTER)
    assert "exploratory_overall" not in result["endpoints"]
    assert result["overall_summary"] == (
        "Exploratory only; equal model weights; do not silently pool model-specific runs")
    assert result["endpoints"]["claude-sonnet-5.5"]["H1"]["B-A"]["difference"] == 0


def test_model_eligibility_does_not_depend_on_other_model_missingness_or_assistance(pilot, panel):
    for scenario in ("missing", "assisted"):
        runs = model_cohort()
        if scenario == "missing":
            runs.pop()
        else:
            runs[-1]["meta"]["intervention"]["assisted"] = True
        result = pilot.analyze_pilot(runs, panel=panel, n=100)
        assert result["primary_estimates_available"] is True
        assert result["primary_unassisted_frame_complete"] is False
        assert result["model_frames"]["gemini-4-argon"]["primary_estimates_available"] is False
        assert result["endpoints"]["gemini-4-argon"]["H1"]["B-A"]["difference"] is None
        for model in MODEL_ROSTER[:2]:
            assert result["model_frames"][model]["primary_estimates_available"] is True
            assert result["endpoints"][model]["H1"]["B-A"]["difference"] == 0
            assert result["endpoints"][model]["H2"]["B-A"]["final_P10_count"]["difference"] == 0
            assert result["endpoints"][model]["H6"]["B-A"]["difference_points"] == 0
        if scenario == "missing":
            assert result["arms"]["C"]["gemini-4-argon"]["missing"] == 1
            assert result["allocation_complete"] is False
        else:
            assert result["arms"]["C"]["gemini-4-argon"]["intervention"]["assisted"] == 1
            assert result["allocation_complete"] is True


def test_current_journal_requires_complete_matching_identity_but_preserves_legacy(pilot, panel):
    for side in ("raw", "journal"):
        for key in ("assigned_model", "analysis_design", "replicate"):
            runs = [stratified_run("gpt-6.1-sol", "A", 1)]
            cells = cells_for(runs)
            target = runs[0]["meta"] if side == "raw" else cells[0]
            del target[key]
            with pytest.raises(ValueError):
                pilot.analyze_pilot(runs, panel=panel, cells=cells, n=100)
        for key, wrong in (("analysis_design", "wrong-design"), ("assigned_model", "gemini-4-argon"),
                           ("replicate", 2)):
            runs = [stratified_run("gpt-6.1-sol", "A", 1)]
            cells = cells_for(runs)
            target = runs[0]["meta"] if side == "raw" else cells[0]
            target[key] = wrong
            with pytest.raises(ValueError):
                pilot.analyze_pilot(runs, panel=panel, cells=cells, n=100)
    for key in ("assigned_model", "analysis_design", "replicate"):
        run = stratified_run("gpt-6.1-sol", "A", 1)
        del run["meta"][key]
        with pytest.raises(ValueError):
            pilot.analyze_pilot([run], panel=panel, n=100)
    for bad in (True, 0, 3, None):
        run = stratified_run("gpt-6.1-sol", "A", 1)
        run["meta"]["replicate"] = bad
        with pytest.raises(ValueError):
            pilot.analyze_pilot([run], panel=panel, cells=cells_for([run]), n=100)
    for bad in (True, 1.0):
        run = stratified_run("gpt-6.1-sol", "A", 1)
        cells = cells_for([run])
        cells[0]["replicate"] = bad
        with pytest.raises(ValueError):
            pilot.analyze_pilot([run], panel=panel, cells=cells, n=100)
    runs = model_cohort()
    assert pilot.analyze_pilot(runs, panel=panel, cells=cells_for(runs), n=100)["allocation_complete"]
    runs = cohort()
    legacy = pilot.analyze_pilot(runs, panel=panel, cells=cells_for(runs), n=100)
    assert legacy["allocation_complete"] and "frame" not in legacy


def test_journal_cross_validates_assigned_model_between_cell_and_meta(pilot, panel):
    runs = [stratified_run("claude-sonnet-5.5", "A", 1, run_id="run-a")]
    cells = cells_for(runs)
    cells[0]["assigned_model"] = "gpt-6.1-sol"
    cells[0]["replicate"] = 1
    with pytest.raises(ValueError, match="differ from run metadata"):
        pilot.analyze_pilot(runs, panel=panel, cells=cells)
