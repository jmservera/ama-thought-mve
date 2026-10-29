"""Synthetic regression checks for interval decisions and usage integrity."""

import csv
import importlib.util
import json
import sys
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("analyze", Path(__file__).parents[1] / "analyze.py")
analysis = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(analysis)


@pytest.mark.parametrize("usage", [{}, {"totalNanoAiu": 2000000000},
                                  {"totalNanoAiu": 2000000000, "aiCreditsStatus": "partial"},
                                  {"aiCreditsStatus": "complete"},
                                  {"totalNanoAiu": 2000000000, "credits_complete": False}])
def test_given_missing_or_partial_credits_when_cost_selected_then_not_free(usage):
    accounting = analysis.step_usage("unused", {"agent": {"usage": usage}})

    assert analysis.cost_of(accounting, "credits") is None


@pytest.mark.parametrize("status", [{"aiCreditsStatus": "complete"}, {"credits_complete": True}])
def test_given_complete_credits_when_cost_selected_then_value_retained(status):
    accounting = analysis.step_usage("unused", {"agent": {"usage": {"totalNanoAiu": 2000000000, **status}}})

    assert analysis.cost_of(accounting, "credits") == 2.0


def test_given_partial_credit_value_when_unavailable_then_raw_diagnostic_retained():
    accounting = analysis.step_usage("unused", {"agent": {"usage": {"totalNanoAiu": 2000000000}}})

    assert accounting["credits"] == 2.0
    assert not accounting["credits_complete"]


@pytest.mark.parametrize("unit", analysis.USAGE_UNITS)
def test_given_absent_accounting_when_unit_selected_then_unavailable(unit):
    accounting = analysis.step_usage("unused", {})

    assert analysis.cost_of(accounting, unit) is None


def test_given_explicit_seconds_with_zero_when_accounted_then_zero_is_valid():
    accounting = analysis.step_usage("unused", {"agent": {"seconds": 0}})

    assert analysis.cost_of(accounting, "seconds") == 0.0


def test_given_complete_tokens_without_credits_when_tokens_selected_then_available():
    details = {name: {"tokenCount": 1} for name in ("input", "output", "cache_read", "cache_write")}
    accounting = analysis.step_usage("unused", {"agent": {"usage": {"tokenDetails": details}}})

    assert analysis.cost_of(accounting, "tokens") == 4.0
    assert analysis.cost_of(accounting, "credits") is None


def test_given_usage_telemetry_models_when_present_then_stays_descriptive_not_identity():
    """usage_quality['models'] is billed-session telemetry only; never an assigned-model identity."""
    accounting = analysis.step_usage("unused", {"agent": {"usage": {"modelMetrics": {"gpt-6.1-sol": {}}}}})

    assert accounting["models"] == ["gpt-6.1-sol"]
    run = {"dir": "unused", "meta": {"arm": "A", "suite": "S1", "run_id": "synthetic", "features": 1,
                                     "change_request": False},
           "recs": [make_record("feature", 1)]}
    run["recs"][0]["agent"]["usage"]["modelMetrics"] = {"claude-sonnet-5.5": {}}
    summary = analysis.summarise_run(run, "credits")
    assert summary["usage_quality"]["models"] == ["claude-sonnet-5.5"]
    assert "assigned_model" not in summary


def make_record(kind, index, *, hidden=None, credits=1.0, complete=True, metrics=None):
    hidden = {"test_f01.py::test_feature": "passed"} if hidden is None else hidden
    return {"kind": kind, "k": index,
            "agent": {"usage": {"totalNanoAiu": credits * 1e9, "credits_complete": complete}},
            "measure": {"hidden": hidden, "hidden_passed": sum(value == "passed" for value in hidden.values()),
                        "hidden_total": len(hidden), "metrics": metrics or {}}}


def make_run(records, arm="A", suite="S1", run_id="synthetic", *, features=1, change_request=True):
    return {"dir": "unused", "meta": {"arm": arm, "suite": suite, "run_id": run_id,
                                      "features": features, "change_request": change_request}, "recs": records}


def make_delivery_records(arm, features=3):
    records = []
    for index in range(1, features + 1):
        hidden = {f"test_f{number:02d}.py::test_feature": "passed" for number in range(1, index + 1)}
        metrics = {"nloc_src": 100, **dict.fromkeys(analysis.METRICS, index)}
        records.append(make_record("feature", index, hidden=hidden, metrics=metrics))
        if arm != "A":
            records.append(make_record("consolidation" if arm == "B" else "review", index,
                                       hidden=hidden, metrics=metrics))
    return records


@pytest.mark.parametrize("outcome", ["error", "skipped", "timeout"])
def test_unknown_coverage_preserves_raw_outcomes_and_neighboring_observations(outcome):
    records = []
    for index, second in enumerate(("failed", outcome, "passed"), 1):
        hidden = {"test_f01.py::test_feature": "passed", "test_f02.py::test_feature": second}
        for kind in ("feature", "consolidation"):
            records.append(make_record(kind, index, hidden=hidden, metrics={"mean_ccn": index}))
    summary = analysis.summarise_run(make_run(records, arm="B", features=3), "credits")

    assert [row["pass_rate"] for row in summary["series"]] == [50, None, 100]
    assert [row["mean_ccn"] for row in summary["series"]] == [1, 2, 3]
    assert summary["sequence_complete"] and len(summary["delivery_attempts"]) == 6
    for record, attempt in zip(records, summary["delivery_attempts"], strict=True):
        assert analysis.measured_hidden(record) == attempt["hidden"] == record["measure"]["hidden"]
        assert record["measure"]["hidden_total"] == 2
    assert records[3]["measure"]["hidden"]["test_f02.py::test_feature"] == outcome
    assert records[3]["measure"]["hidden_passed"] == 1


@pytest.mark.parametrize(("hypothesis", "estimate"), [("H1", "diff_points"), ("H5", "cost_ratio_B_over_A")])
def test_given_scheduled_ten_features_interrupted_after_one_when_evaluated_then_not_evaluable(hypothesis, estimate):
    summaries = []
    for arm in ("A", "B"):
        hidden = {"test_f01.py::test_one": "passed",
                  "test_f01.py::test_two": "failed" if arm == "A" else "passed"}
        for index in range(4):
            records = [make_record("feature", 1, hidden=hidden, credits=10 if arm == "A" else 3)]
            if arm == "B":
                records.append(make_record("consolidation", 1, hidden=hidden, credits=8))
            run = make_run(records, arm=arm, run_id=f"{arm}-{index}")
            run["meta"].update({"features": 10, "change_request": True})
            summaries.append(analysis.summarise_run(run, "credits"))

    result = analysis.analyze_hypotheses(summaries, n=200)[hypothesis]

    assert result["verdict"] == "not evaluable"
    assert result[estimate] is None


def test_given_metadata_without_first_record_when_loading_then_empty_and_absent_steps_retained(tmp_path):
    for name in ("with-empty-steps", "without-steps"):
        directory = tmp_path / name
        directory.mkdir()
        metadata = {"run_id": name, "arm": "A", "suite": "S1", "phase": "first", "features": 10}
        (directory / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
    (tmp_path / "with-empty-steps" / "steps.jsonl").write_text("", encoding="utf-8")

    runs = analysis.load_runs(str(tmp_path), "first")

    assert [run["meta"]["run_id"] for run in runs] == ["with-empty-steps", "without-steps"]
    assert all(run["recs"] == [] for run in runs)


@pytest.mark.parametrize("features", [None, True, 0, -1, 2.5, "3"])
def test_given_invalid_scheduled_metadata_when_summarised_then_observed_data_only(features):
    summary = analysis.summarise_run(make_run(make_delivery_records("A"), features=features), "credits")

    assert not summary["sequence_complete"]
    assert summary["end"] is None
    assert summary["total_cost"] is None
    assert summary["last_observed"]["k"] == 3
    assert summary["last_observed"]["pass_rate"] == 100
    assert all(value is None for value in summary["slopes"].values())
    assert analysis.last_third(summary) is None


@pytest.mark.parametrize("arm", ["A", "B", "C"])
@pytest.mark.parametrize("defect", ["missing_first", "missing_middle", "missing_last", "duplicate",
                                   "out_of_order", "extra", "invalid_index", "boolean_index", "wrong_kind", "nonobject"])
def test_given_malformed_scheduled_trajectory_when_summarised_then_no_complete_endpoint_or_total(arm, defect):
    records = make_delivery_records(arm)
    if defect.startswith("missing_"):
        missing_index = {"missing_first": 1, "missing_middle": 2, "missing_last": 3}[defect]
        records = [record for record in records if (record["kind"], record["k"]) != ("feature", missing_index)]
    elif defect == "duplicate":
        records.insert(1, records[0].copy())
    elif defect == "out_of_order":
        records.reverse()
    elif defect == "extra":
        records.append(make_record("feature", 4))
    elif defect in ("invalid_index", "boolean_index"):
        records[0]["k"] = "1" if defect == "invalid_index" else True
    elif defect == "wrong_kind":
        records[0]["kind"] = "unexpected"
    else:
        records.append(None)

    summary = analysis.summarise_run(make_run(records, arm=arm, features=3), "credits")

    assert not summary["sequence_complete"]
    assert summary["end"] is None
    assert summary["total_cost"] is None
    assert len(summary["delivery_attempts"]) == len(records)
    assert all(value is None for value in summary["slopes"].values())
    assert analysis.last_third(summary) is None


@pytest.mark.parametrize("arm", ["B", "C"])
def test_given_missing_middle_assigned_post_when_summarised_then_final_record_cannot_hide_gap(arm):
    records = [record for record in make_delivery_records(arm)
               if not (record["kind"] != "feature" and record["k"] == 2)]

    summary = analysis.summarise_run(make_run(records, arm=arm, features=3), "credits")

    assert summary["missing_post_features"] == [2]
    assert summary["last_observed"]["k"] == 3
    assert summary["end"] is None
    assert summary["total_cost"] is None


@pytest.mark.parametrize("arm", ["B", "C"])
def test_given_interruption_before_assigned_post_when_reported_then_latest_feature_stays_descriptive(arm):
    records = make_delivery_records(arm, features=2)[:-1]

    summary = analysis.summarise_run(make_run(records, arm=arm, features=2), "credits")

    assert summary["end"] is None
    assert summary["last_observed"]["k"] == 2
    assert summary["last_observed"]["kind"] == "feature"
    assert summary["last_observed"]["pass_rate"] == 100
    assert summary["last_observed"]["nloc_src"] == 100
    assert summary["series"][-1]["pass_rate"] is None


@pytest.mark.parametrize("arm", ["A", "B", "C"])
def test_given_complete_scheduled_delivery_when_summarised_then_endpoint_and_costs_available(arm):
    records = make_delivery_records(arm, features=10)

    summary = analysis.summarise_run(make_run(records, arm=arm, features=10, change_request=False), "credits")

    assert summary["sequence_complete"]
    assert summary["end"]["k"] == 10
    assert summary["end"]["pass_rate"] == 100
    assert summary["total_cost"] == len(records)
    assert summary["missing_features"] == []
    assert summary["missing_post_features"] == []
    assert analysis.last_third(summary) == 1
    assert summary["cr_success"] is None


def test_given_malformed_step_line_when_loading_then_run_and_other_attempts_retained(tmp_path):
    directory = tmp_path / "malformed"
    directory.mkdir()
    metadata = make_run([], features=3)["meta"]
    (directory / "run.json").write_text(json.dumps(metadata), encoding="utf-8")
    records = make_delivery_records("A")
    (directory / "steps.jsonl").write_text(json.dumps(records[0]) + "\n{truncated\n" + json.dumps(records[2]),
                                          encoding="utf-8")

    runs = analysis.load_runs(str(tmp_path), None)
    summary = analysis.summarise_run(runs[0], "credits")

    assert len(runs) == 1
    assert len(runs[0]["recs"]) == 3
    assert summary["usage_quality"]["sessions"] == 3
    assert summary["usage_quality"]["unavailable_sessions"]["credits"] == 1
    assert len(summary["record_errors"]) == 1
    assert summary["last_observed"]["k"] == 3
    assert summary["total_cost"] is None


@pytest.mark.parametrize("arm", ["A", "B", "C"])
def test_given_unknown_early_cost_when_late_window_computed_then_scheduled_tail_still_available(arm):
    records = make_delivery_records(arm, features=10)
    for record in records:
        record["agent"]["usage"]["totalNanoAiu"] = record["k"] * 1e9
    records[0]["agent"]["usage"]["credits_complete"] = False

    summary = analysis.summarise_run(make_run(records, arm=arm, features=10), "credits")

    assert summary["sequence_complete"]
    assert summary["total_cost"] is None
    assert analysis.last_third(summary) == 9


@pytest.mark.parametrize("arm", ["B", "C"])
def test_given_unknown_late_post_cost_when_late_window_computed_then_feature_cost_is_independent(arm):
    records = make_delivery_records(arm, features=10)
    records[-1]["agent"]["usage"]["credits_complete"] = False

    summary = analysis.summarise_run(make_run(records, arm=arm, features=10), "credits")

    assert summary["total_cost"] is None
    assert analysis.last_third(summary) == 1


@pytest.mark.parametrize("missing_index", [9, 10])
def test_given_missing_scheduled_late_feature_when_window_computed_then_not_replaced_by_earlier_cost(missing_index):
    summary = {"scheduled_features": 10, "sequence_complete": True,
               "per_feature_implementation_cost": {index: 1 for index in range(1, 11) if index != missing_index}}

    assert analysis.last_third(summary) is None


@pytest.mark.parametrize("outcome", [None, "unknown", {}])
def test_given_unknown_feature_outcome_when_summarised_then_final_success_not_inferred(outcome):
    records = make_delivery_records("A")
    records[0]["measure"]["hidden"]["test_f01.py::test_feature"] = outcome
    records.append(make_record("change_request", 3,
                               hidden={**records[-1]["measure"]["hidden"], "test_cr1.py::test_change": "passed"}))

    summary = analysis.summarise_run(make_run(records, features=3), "credits")

    assert summary["end"]["pass_rate"] is None
    assert summary["last_observed"]["pass_rate"] == 100
    assert summary["cr_success"] is None
    assert summary["cr_attempts"] == [{"success": None, "cost": 1.0}]
    assert summary["total_cost"] == 3


@pytest.mark.parametrize("planned", [True, False, None])
@pytest.mark.parametrize("attempts", [0, 1, 2])
def test_given_planned_or_unplanned_cr_when_summarised_then_all_attempts_retained_without_default_success(planned, attempts):
    records = make_delivery_records("A")
    hidden = {**records[-1]["measure"]["hidden"], "test_cr1.py::test_change": "passed"}
    records += [make_record("change_request", 3, hidden=hidden) for _ in range(attempts)]

    summary = analysis.summarise_run(make_run(records, features=3, change_request=planned), "credits")

    assert summary["change_request_planned"] is planned
    assert summary["cr_success"] is (True if planned is True and attempts == 1 else None)
    assert summary["cr_attempts"] == [{"success": True, "cost": 1.0}] * attempts
    assert summary["cr_cost"] == (attempts if attempts else None)


@pytest.mark.parametrize("defect", ["early_request", "wrong_index", "missing_feature_outcome"])
def test_given_malformed_cr_endpoint_when_summarised_then_attempt_unknown_not_measured_failure(defect):
    records = make_delivery_records("A")
    hidden = {**records[-1]["measure"]["hidden"], "test_cr1.py::test_change": "passed"}
    request = make_record("change_request", 3, hidden=hidden)
    if defect == "early_request":
        records.insert(1, request)
    else:
        records.append(request)
        if defect == "wrong_index":
            request["k"] = 2
        else:
            del request["measure"]["hidden"]["test_f01.py::test_feature"]

    summary = analysis.summarise_run(make_run(records, features=3), "credits")

    assert summary["cr_success"] is None
    assert summary["cr_attempts"] == [{"success": None, "cost": 1.0}]


def test_given_one_unaccounted_session_when_summarising_then_total_cost_unavailable():
    run = make_run([make_record("feature", 1), make_record("feature", 2, complete=False)], features=2)

    summary = analysis.summarise_run(run, "credits")

    assert summary["total_cost"] is None
    assert summary["per_feature_cost"] == {1: 1.0, 2: None}
    assert summary["usage_quality"]["credits"] == 2.0
    assert summary["usage_quality"]["unavailable_sessions"]["credits"] == 1


def test_given_consolidation_overhead_when_summarising_then_implementation_cost_stays_separate():
    run = make_run([make_record("feature", 1, credits=2),
                    make_record("consolidation", 1, credits=3)], arm="B")

    summary = analysis.summarise_run(run, "credits")

    assert summary["per_feature_cost"] == {1: 5.0}
    assert summary["per_feature_implementation_cost"] == {1: 2.0}
    assert summary["total_cost"] == 5.0


def test_given_empty_hidden_denominator_when_summarising_then_pass_rate_unknown():
    summary = analysis.summarise_run(make_run([make_record("feature", 1, hidden={})]), "credits")

    assert summary["end"]["pass_rate"] is None
    assert summary["end"]["open_regressions"] is None


def test_given_missing_measurements_when_summarising_then_retains_incomplete_run():
    run = make_run([{"kind": "feature", "k": 1}])

    summary = analysis.summarise_run(run, "credits")

    assert summary["end"]["pass_rate"] is None
    assert summary["end"]["nloc_src"] is None
    assert summary["total_cost"] is None
    assert all(value is None for value in summary["slopes"].values())


def test_given_no_records_when_summarising_then_no_free_or_successful_run():
    summary = analysis.summarise_run(make_run([]), "credits")

    assert summary["end"] is None
    assert summary["total_cost"] is None
    assert summary["cr_success"] is None


def test_given_regressed_feature_when_cr_passes_then_request_still_fails():
    records = [make_record("feature", 1),
               make_record("change_request", 1, hidden={"test_f01.py::test_feature": "failed",
                                                       "test_cr1.py::test_change": "passed"})]

    summary = analysis.summarise_run(make_run(records), "credits")

    assert summary["cr_success"] is False
    assert summary["cr_attempts"] == [{"success": False, "cost": 1.0}]


def test_given_failed_then_successful_cr_when_summarising_then_both_attempts_retained():
    records = [make_record("feature", 1),
               make_record("change_request", 1, hidden={"test_f01.py::test_feature": "passed",
                                                       "test_cr1.py::test_change": "failed"}),
               make_record("change_request", 1, hidden={"test_f01.py::test_feature": "passed",
                                                       "test_cr1.py::test_change": "passed"})]

    summary = analysis.summarise_run(make_run(records), "credits")

    assert [attempt["success"] for attempt in summary["cr_attempts"]] == [False, True]
    assert summary["cr_success"] is None
    assert summary["cr_cost"] == 2.0


def test_given_missing_quality_step_when_slope_computed_then_not_silently_dropped():
    assert analysis.slope([1, 2, 3], [1.0, None, 3.0]) is None


@pytest.mark.parametrize(("point", "interval", "expected"),
                         [(12, (-2, 26), "inconclusive"), (10, (1, 20), "validated"),
                          (4, (1, 4.9), "invalidated"), (7, (5, 9), "inconclusive"),
                          (None, (None, None), "not evaluable")])
def test_given_h1_interval_when_deciding_then_preserves_ten_five_point_rules(point, interval, expected):
    assert analysis.verdict(point, interval, 10, 5) == expected


@pytest.mark.parametrize("helper", [analysis.boot_diff, analysis.boot_ratio])
@pytest.mark.parametrize(("arm_a", "arm_b"), [({}, {}), ({"S1": []}, {"S1": [1]}),
                                              ({"S1": [None]}, {"S1": [1]}),
                                              ({"S1": [1]}, {"S2": [1]})])
def test_given_absent_or_incomplete_strata_when_bootstrapped_then_unavailable(helper, arm_a, arm_b):
    assert helper(arm_a, arm_b, n=100) == (None, (None, None))


def test_given_unequal_suite_counts_when_ratio_bootstrapped_then_not_pooled_across_suites():
    arm_a = {"S1": [1000] * 2, "S2": [1] * 6}
    arm_b = {"S1": [1000] * 6, "S2": [1] * 2}

    assert analysis.boot_ratio(arm_a, arm_b, n=100) == (1.0, (1.0, 1.0))


@pytest.mark.parametrize("baseline", [[0], [0, 1]])
def test_given_zero_bootstrap_denominators_when_ratio_computed_then_interval_unavailable(baseline):
    _, interval = analysis.boot_ratio({"S1": baseline}, {"S1": [1]}, n=100)

    assert interval == (None, None)


def test_given_correlated_metrics_when_bootstrapped_then_whole_run_covariance_preserved():
    rows = [{"cost": 1, "late": 10}, {"cost": 3, "late": 30}]
    groups = {"A": {"S1": rows}}

    point, intervals = analysis.boot_effects(
        groups, lambda sample: {"paired": analysis.suite_mean(sample["A"],
                                                              lambda run: run["late"] - 10 * run["cost"])}, n=100)

    assert point["paired"] == 0
    assert intervals["paired"] == (0, 0)


@pytest.mark.parametrize("successes", [0, 4])
def test_given_boundary_binomial_counts_when_bounded_then_matches_exact_tail_formula(successes):
    lower, upper = analysis.binomial_bounds(successes, 4)

    if successes:
        assert lower == pytest.approx(0.025 ** (1 / 4))
        assert upper == 1
    else:
        assert lower == 0
        assert upper == pytest.approx(1 - 0.025 ** (1 / 4))


def test_given_one_of_four_extra_successes_when_bounded_then_estimate_is_not_proof():
    point, interval = analysis.success_difference({"S1": [False, True, True, True]},
                                                 {"S1": [True, True, True, True]})

    assert point == 25
    assert interval[0] < 0 < interval[1]


def test_given_two_suites_when_success_bounded_then_coverage_adjusts_for_all_four_strata():
    arm_a = {"S1": [False] * 5, "S2": [False] * 5}
    arm_b = {"S1": [True] * 5, "S2": [True] * 5}

    point, interval = analysis.success_difference(arm_a, arm_b)
    expected_lower = 100 * (2 * (0.05 / 8) ** (1 / 5) - 1)

    assert point == 100
    assert interval == pytest.approx((expected_lower, 100))


def test_given_missing_cr_outcome_when_bounded_then_not_dropped_from_success_denominator():
    assert analysis.success_difference({"S1": [False, None]}, {"S1": [True, True]}) == (None, (None, None))


def make_summary(arm, index, **overrides):
    success = overrides.pop("cr_success", True)
    cr_cost = overrides.pop("cr_cost", 20 if arm == "A" else 10)
    summary = {"run_id": f"{arm}-{index}", "arm": arm, "suite": "S1", "cost_unit": "credits",
               "scheduled_features": 1, "sequence_complete": True, "outcomes_complete": True,
               "change_request_planned": True,
               "end": {"pass_rate": 50 if arm == "A" else 70,
                       "open_regressions": 10 if arm == "A" else 4, "nloc_src": 100 if arm == "A" else 70},
               "slopes": {name: 1 if arm == "A" else 0.4 for name in analysis.METRICS},
               "regression_auc": 20, "total_cost": 100 if arm == "A" else 110,
               "per_feature_implementation_cost": {1: 10 if arm == "A" else 5},
               "cr_success": success, "cr_cost": cr_cost,
               "cr_attempts": [{"success": success, "cost": cr_cost}]}
    summary["slopes"]["open_regressions"] = 1 if arm == "A" else 0
    summary.update(overrides)
    return summary


@pytest.fixture
def balanced_runs():
    return [make_summary(arm, index) for arm in ("A", "B") for index in range(4)]


@pytest.fixture
def evaluate():
    return lambda runs: analysis.analyze_hypotheses(runs, n=200, seed=2026)


@pytest.mark.parametrize("arm", ["A", "B"])
def test_given_incomplete_comparison_frame_when_evaluated_then_no_partial_validation_or_invalidation(arm, balanced_runs, evaluate):
    balanced_runs.append(make_summary(arm, 4, sequence_complete=False))
    for run in balanced_runs:
        run["slopes"]["open_regressions"] = -1
    runs = balanced_runs + [make_summary("C", index, end={"pass_rate": 60}) for index in range(4)]

    results = evaluate(runs)

    assert all(result["verdict"] == "not evaluable" for result in results.values())
    assert results["H4"]["volume_verdict"] == "not evaluable"
    assert results["H7"]["H1_component_verdict"] == "not evaluable"
    assert results["H6"]["attempts"][arm]["attempted"] == 5


def test_given_missing_summary_completeness_when_evaluated_then_not_assumed_complete(balanced_runs, evaluate):
    for run in balanced_runs:
        del run["sequence_complete"]

    results = evaluate(balanced_runs)

    assert all(result["verdict"] == "not evaluable" for result in results.values())


def test_given_incomplete_control_delivery_when_package_evaluated_then_no_h1_component(balanced_runs, evaluate):
    for run in balanced_runs[4:]:
        run["end"]["pass_rate"] = 80
    controls = [make_summary("C", index, end={"pass_rate": 60}, sequence_complete=index != 0) for index in range(4)]

    result = evaluate(balanced_runs + controls)["H7"]

    assert result["H1_component_verdict"] == "not evaluable"
    assert result["B_minus_C"] is None


def test_given_supported_h1_h2_h3_h5_when_evaluated_then_validate_without_changing_thresholds(balanced_runs, evaluate):
    results = evaluate(balanced_runs)

    assert {name: results[name]["verdict"] for name in ("H1", "H2", "H3", "H5")} == {
        name: "validated" for name in ("H1", "H2", "H3", "H5")}


def test_given_good_auc_but_bad_regression_endpoint_when_h2_evaluated_then_endpoint_controls(balanced_runs, evaluate):
    for run in balanced_runs:
        run["end"]["open_regressions"] = 4 if run["arm"] == "A" else 3
        run["regression_auc"] = 100 if run["arm"] == "A" else 10

    result = evaluate(balanced_runs)["H2"]

    assert result["auc_ratio_B_over_A"] == 0.1
    assert result["end_reduction"] == 0.25
    assert result["verdict"] == "invalidated"


def test_given_positive_but_uncertain_a_slope_when_h2_evaluated_then_inconclusive(balanced_runs, evaluate):
    for run, value in zip(balanced_runs[:4], [-10, -5, 5, 20]):
        run["slopes"]["open_regressions"] = value

    result = evaluate(balanced_runs)["H2"]

    assert result["A_slope_mean"] > 0
    assert result["A_slope_ci"][0] < 0 < result["A_slope_ci"][1]
    assert result["verdict"] == "inconclusive"


def test_given_large_but_uncertain_endpoint_reduction_when_h2_evaluated_then_inconclusive(balanced_runs, evaluate):
    for run, value in zip(balanced_runs[4:], [0, 0, 0, 14]):
        run["end"]["open_regressions"] = value

    result = evaluate(balanced_runs)["H2"]

    assert result["end_reduction"] >= 0.5
    assert result["end_reduction_ci"][0] <= 0
    assert result["verdict"] == "inconclusive"


@pytest.mark.parametrize("slopes", [[-5, -1, 4, 6], [-4, -1, 1, 2]])
def test_given_uncertain_quality_slopes_when_h3_evaluated_then_points_prove_neither_outcome(balanced_runs, evaluate, slopes):
    for run, value in zip(balanced_runs[:4], slopes):
        run["slopes"].update({name: value for name in analysis.METRICS})

    result = evaluate(balanced_runs)["H3"]

    assert result["interval_supported"] == 0
    assert result["interval_ruled_out"] == 0
    assert result["verdict"] == "inconclusive"


def test_given_only_two_possible_quality_measures_when_h3_evaluated_then_pattern_ruled_out(balanced_runs, evaluate):
    for run in balanced_runs[:4]:
        run["slopes"].update({name: -1 for name in analysis.METRICS[:2]})

    result = evaluate(balanced_runs)["H3"]

    assert result["interval_ruled_out"] == 2
    assert result["verdict"] == "invalidated"


def test_given_missing_quality_metrics_when_h3_evaluated_then_not_evaluable(balanced_runs, evaluate):
    balanced_runs[0]["slopes"].update({name: None for name in analysis.METRICS[:2]})

    assert evaluate(balanced_runs)["H3"]["verdict"] == "not evaluable"


def test_given_twenty_percent_less_code_without_human_data_when_h4_evaluated_then_full_verdict_unavailable(balanced_runs, evaluate):
    for run in balanced_runs[4:]:
        run["end"]["nloc_src"] = 80

    result = evaluate(balanced_runs)["H4"]

    assert result["volume_verdict"] == "validated"
    assert result["verdict"] == "not evaluable"
    assert not result["full_verdict_available"]
    assert "comprehension" in result["reason"]


def test_given_point_late_savings_with_uncertain_interval_when_h5_evaluated_then_inconclusive(balanced_runs, evaluate):
    for run, cost in zip(balanced_runs[4:], [0, 0, 0, 30]):
        run["per_feature_implementation_cost"] = {1: cost}

    result = evaluate(balanced_runs)["H5"]

    assert result["late_feature_saving"] > 0
    assert result["late_feature_saving_ci"][0] < 0 < result["late_feature_saving_ci"][1]
    assert result["verdict"] == "inconclusive"


@pytest.mark.parametrize("costs", [[50, 80, 130, 220], [50, 100, 200, 300]])
def test_given_uncertain_total_cost_ratio_when_h5_evaluated_then_point_alone_is_insufficient(balanced_runs, evaluate, costs):
    for run, cost in zip(balanced_runs[4:], costs):
        run["total_cost"] = cost

    result = evaluate(balanced_runs)["H5"]

    assert result["ci"][0] < 1.5 < result["ci"][1]
    assert result["verdict"] == "inconclusive"


def test_given_whole_cost_interval_above_ceiling_and_no_late_savings_when_h5_evaluated_then_invalidated(balanced_runs, evaluate):
    for run in balanced_runs[4:]:
        run["total_cost"] = 160
        run["per_feature_implementation_cost"] = {1: 15}

    assert evaluate(balanced_runs)["H5"]["verdict"] == "invalidated"


def test_given_one_missing_cost_when_h5_evaluated_then_not_zero_or_excluded(balanced_runs, evaluate):
    balanced_runs[0]["total_cost"] = None

    result = evaluate(balanced_runs)["H5"]

    assert result["cost_ratio_B_over_A"] is None
    assert result["verdict"] == "not evaluable"


def test_given_equal_success_and_supported_cost_savings_when_h6_evaluated_then_cost_alternative_validates(balanced_runs, evaluate):
    result = evaluate(balanced_runs)["H6"]

    assert result["diff_points"] == 0
    assert result["success_ci"][0] < 0 < result["success_ci"][1]
    assert result["cost_saving"] == 0.5
    assert result["verdict"] == "validated"
    assert result["validated_by"] == "cost saving at no lower observed success"


def test_given_twenty_five_point_small_n_gain_when_h6_evaluated_then_not_validated_from_point_estimate(evaluate):
    runs = [make_summary("A", index, cr_success=index > 0, cr_cost=20) for index in range(4)]
    runs += [make_summary("B", index, cr_cost=20) for index in range(4)]

    result = evaluate(runs)["H6"]

    assert result["diff_points"] == 25
    assert result["success_ci"][0] < 0
    assert result["success_component_verdict"] == "inconclusive"
    assert result["verdict"] != "validated"


def test_given_cheap_failed_cr_when_h6_evaluated_then_failure_stays_and_cannot_create_cost_win(evaluate):
    runs = [make_summary("A", index) for index in range(4)]
    runs += [make_summary("B", index, cr_success=index > 0, cr_cost=0.01 if index == 0 else 10)
             for index in range(4)]

    result = evaluate(runs)["H6"]

    assert result["success_B"] == "3/4"
    assert result["diff_points"] == -25
    assert result["successful_cost_ratio_B_over_A"] == 0.5
    assert result["attempts"]["B"]["failed_attempt_cost"] == 0.01
    assert result["verdict"] != "validated"


def test_given_all_failed_cheap_crs_when_h6_evaluated_then_no_successful_cost_ratio(evaluate):
    runs = [make_summary("A", index) for index in range(4)]
    runs += [make_summary("B", index, cr_success=False, cr_cost=0.01) for index in range(4)]

    result = evaluate(runs)["H6"]

    assert result["success_B"] == "0/4"
    assert result["attempts"]["B"]["failed"] == 4
    assert result["successful_cost_ratio_B_over_A"] is None
    assert result["verdict"] != "validated"


def test_given_uncertain_quarter_cost_saving_when_h6_evaluated_then_inconclusive(balanced_runs, evaluate):
    for run, cost in zip(balanced_runs[4:], [0, 0, 0, 60]):
        run["cr_cost"] = cost
        run["cr_attempts"][0]["cost"] = cost

    result = evaluate(balanced_runs)["H6"]

    assert result["cost_saving"] == 0.25
    assert result["cost_saving_ci"][0] < 0 < result["cost_saving_ci"][1]
    assert result["verdict"] == "inconclusive"


def test_given_supported_success_gain_but_missing_costs_when_h6_evaluated_then_success_alternative_still_validates(evaluate):
    runs = [make_summary("A", index, cr_success=False, cr_cost=None) for index in range(40)]
    runs += [make_summary("B", index, cr_success=True, cr_cost=None) for index in range(40)]

    result = evaluate(runs)["H6"]

    assert result["success_ci"][0] > 0
    assert result["verdict"] == "validated"
    assert result["validated_by"] == "success gain"


def test_given_both_minimum_cr_benefits_ruled_out_when_h6_evaluated_then_invalidated(evaluate):
    runs = [make_summary(arm, index, cr_cost=20) for arm in ("A", "B") for index in range(40)]

    result = evaluate(runs)["H6"]

    assert result["success_ci"][1] < 20
    assert result["cost_saving_ci"][1] < 0.25
    assert result["verdict"] == "invalidated"


def test_given_one_missing_cr_when_h6_evaluated_then_not_silently_excluded(balanced_runs, evaluate):
    balanced_runs[0].update({"cr_success": None, "cr_cost": None, "cr_attempts": []})

    result = evaluate(balanced_runs)["H6"]

    assert result["diff_points"] is None
    assert result["verdict"] == "not evaluable"


def test_given_h1_package_win_without_h3_comparison_when_h7_evaluated_then_full_verdict_unavailable(balanced_runs, evaluate):
    for run in balanced_runs[4:]:
        run["end"]["pass_rate"] = 80
    control = [make_summary("C", index, end={"pass_rate": 60}) for index in range(4)]

    result = evaluate(balanced_runs + control)["H7"]

    assert result["H1_component_verdict"] == "validated"
    assert result["H3_component_verdict"] == "not evaluable"
    assert result["verdict"] == "not evaluable"
    assert not result["full_verdict_available"]


@pytest.mark.parametrize("arms", [[], ["A"], ["B"]])
def test_given_absent_required_arms_when_hypotheses_evaluated_then_no_traceback_or_false_pass(arms, evaluate):
    results = evaluate([make_summary(arm, 0) for arm in arms])

    assert all(result["verdict"] == "not evaluable" for result in results.values())


def test_given_zero_baseline_cost_and_regressions_when_evaluated_then_no_false_validation(balanced_runs, evaluate):
    for run in balanced_runs[:4]:
        run["total_cost"] = 0
        run["end"]["open_regressions"] = 0
        run["cr_cost"] = 0
        run["cr_attempts"][0]["cost"] = 0

    results = evaluate(balanced_runs)

    assert all(results[name]["verdict"] == "not evaluable" for name in ("H2", "H5", "H6"))


@pytest.mark.parametrize("unit", ["credits", "tokens", "seconds"])
def test_given_synthetic_cli_input_when_reported_then_declared_unit_and_incomplete_runs_retained(tmp_path, monkeypatch, unit):
    record = make_record("feature", 1, complete=False)
    record["agent"]["seconds"] = 5
    record["agent"]["usage"]["tokenDetails"] = {name: {"tokenCount": 1}
                                                for name in ("input", "output", "cache_read", "cache_write")}
    runs = [make_run([record], arm="A"), make_run([], arm="B", run_id="incomplete")]
    monkeypatch.setattr(analysis, "load_runs", lambda *_: runs)
    original = analysis.analyze_hypotheses
    monkeypatch.setattr(analysis, "analyze_hypotheses", lambda runs, seed: original(runs, seed=seed, n=100))
    monkeypatch.setitem(sys.modules, "matplotlib", None)
    monkeypatch.setattr(sys, "argv", ["analyze.py", "--legacy-proposal", "--runs", str(tmp_path / "synthetic-only"),
                                      "--out", str(tmp_path / "reports"), "--cost-unit", unit])

    analysis.main()
    report = json.loads((tmp_path / "reports" / "summary.json").read_text())
    markdown = (tmp_path / "reports" / "summary.md").read_text()

    assert report["cost_unit"] == unit
    assert len(report["runs"]) == 2
    assert report["runs"][0]["total_cost"] == {"credits": None, "tokens": 4, "seconds": 5}[unit]
    assert report["runs"][1]["end"] is None
    assert "no automatic cost-unit fallback" in markdown
    assert "comprehension unavailable" in markdown


def test_given_missing_final_consolidation_when_summarised_then_prior_feature_is_not_end_state():
    records = [make_record("feature", 1), make_record("consolidation", 1), make_record("feature", 2)]

    summary = analysis.summarise_run(make_run(records, arm="B", features=2), "credits")

    assert summary["end"] is None
    assert summary["series"][-1]["k"] == 2
    assert summary["series"][-1]["pass_rate"] is None
    assert summary["missing_post_features"] == [2]
    assert summary["total_cost"] is None


def test_given_test_lost_during_consolidation_when_regressions_counted_then_earlier_feature_pass_is_remembered():
    failed = {"test_f01.py::test_feature": "failed"}
    records = [make_record("feature", 1), make_record("consolidation", 1, hidden=failed),
               make_record("feature", 2, hidden=failed), make_record("consolidation", 2, hidden=failed)]

    summary = analysis.summarise_run(make_run(records, arm="B", features=2), "credits")

    assert [row["open_regressions"] for row in summary["series"]] == [1, 1]
    assert summary["regression_auc"] == 2


@pytest.mark.parametrize(("arm", "post_kind"), [("B", "consolidation"), ("C", "review")])
def test_given_different_feature_and_post_states_when_summarised_then_h1_uses_post_state(arm, post_kind):
    failed = {"test_f01.py::test_feature": "failed"}
    records = [make_record("feature", 1), make_record(post_kind, 1, hidden=failed)]

    summary = analysis.summarise_run(make_run(records, arm=arm), "credits")

    assert summary["end"]["pass_rate"] == 0


def test_given_scoped_cr_node_ids_when_summarised_then_change_tests_recognised():
    hidden = {"test_f01.py::test_feature": "passed", "synthetic/test_cr1.py::test_change": "passed"}
    records = [make_record("feature", 1), make_record("change_request", 1, hidden=hidden)]

    assert analysis.summarise_run(make_run(records), "credits")["cr_success"] is True


def test_given_no_collected_cr_tests_when_summarised_then_outcome_unknown_not_measured_failure():
    records = [make_record("feature", 1), make_record("change_request", 1)]

    summary = analysis.summarise_run(make_run(records), "credits")

    assert summary["cr_success"] is None
    assert summary["cr_attempts"] == [{"success": None, "cost": 1.0}]


def test_given_repeated_crs_when_h6_evaluated_then_all_failures_reported_but_independent_run_verdict_unavailable(balanced_runs, evaluate):
    balanced_runs[0]["cr_attempts"].insert(0, {"success": False, "cost": 1})
    balanced_runs[0]["cr_success"] = None

    result = evaluate(balanced_runs)["H6"]

    assert result["success_A"] == "4/5"
    assert result["attempts"]["A"]["failed"] == 1
    assert result["attempts"]["A"]["runs_with_repeated_cr"] == 1
    assert result["diff_points"] is None
    assert result["verdict"] == "not evaluable"


def test_given_exact_twenty_point_gain_when_success_estimated_then_threshold_not_lost_to_rounding():
    point, _ = analysis.success_difference({"S1": [True, True, False, False, False]},
                                           {"S1": [True, True, True, False, False]})

    assert point == 20


def test_given_complete_synthetic_cli_input_when_default_resampling_used_then_report_is_generated(tmp_path, monkeypatch):
    records = [make_record("feature", index, metrics={"nloc_src": 100, **dict.fromkeys(analysis.METRICS, 1)})
               for index in (1, 2)]
    records.append(make_record("change_request", 2, hidden={"test_f01.py::test_feature": "passed",
                                                          "test_cr1.py::test_change": "passed"}))
    raw_runs = [make_run(records, arm="A", run_id=f"A-{index}", features=2) for index in range(4)]
    raw_runs += [make_run([*records[:1], make_record("consolidation", 1), *records[1:2],
                          make_record("consolidation", 2), records[-1]], arm="B", run_id=f"B-{index}", features=2)
                 for index in range(4)]
    monkeypatch.setattr(analysis, "load_runs", lambda *_: raw_runs)
    monkeypatch.setitem(sys.modules, "matplotlib", None)
    monkeypatch.setattr(sys, "argv", ["analyze.py", "--legacy-proposal", "--runs", str(tmp_path / "synthetic-only"),
                                      "--out", str(tmp_path / "reports")])

    analysis.main()
    report = json.loads((tmp_path / "reports" / "summary.json").read_text())

    assert len(report["runs"]) == 8
    assert "10000 whole-run resamples" in report["methods"]["bootstrap"]
    assert report["hypotheses"]["H4"]["verdict"] == "not evaluable"
    assert report["hypotheses"]["H7"]["verdict"] == "not evaluable"


def test_given_partial_and_zero_step_runs_when_reported_then_all_runs_and_observed_data_visible(tmp_path, monkeypatch):
    raw_runs = [make_run([make_record("feature", 1)], run_id="partial", features=10),
                make_run([], run_id="empty", features=10),
                make_run([], arm="B", run_id="absent", features=10)]
    for run in raw_runs:
        directory = tmp_path / "runs" / run["meta"]["run_id"]
        directory.mkdir(parents=True)
        (directory / "run.json").write_text(json.dumps(run["meta"]), encoding="utf-8")
        if run["meta"]["run_id"] != "absent":
            (directory / "steps.jsonl").write_text("\n".join(json.dumps(record) for record in run["recs"]),
                                                   encoding="utf-8")
    original = analysis.analyze_hypotheses
    monkeypatch.setattr(analysis, "analyze_hypotheses", lambda runs, seed: original(runs, seed=seed, n=100))
    monkeypatch.setitem(sys.modules, "matplotlib", None)
    monkeypatch.setattr(sys, "argv", ["analyze.py", "--legacy-proposal", "--runs", str(tmp_path / "runs"),
                                      "--out", str(tmp_path / "reports")])

    analysis.main()
    report = json.loads((tmp_path / "reports" / "summary.json").read_text())
    markdown = (tmp_path / "reports" / "summary.md").read_text()
    with (tmp_path / "reports" / "series.csv").open(newline="", encoding="utf-8") as series_file:
        series = list(csv.DictReader(series_file))

    assert {run["run_id"] for run in report["runs"]} == {"partial", "empty", "absent"}
    assert all(run["end"] is None and run["total_cost"] is None for run in report["runs"])
    assert all(result["verdict"] == "not evaluable" for result in report["hypotheses"].values())
    partial = next(run for run in report["runs"] if run["run_id"] == "partial")
    assert partial["last_observed"]["pass_rate"] == 100
    assert partial["observed_delivery_cost"] == 1
    assert any(row["run_id"] == "partial" and row["k"] == "1" and float(row["pass_rate"]) == 100 for row in series)
    assert "Runs analysed: 3" in markdown
    assert "Sequence complete" in markdown
    assert "Last observed" in markdown
