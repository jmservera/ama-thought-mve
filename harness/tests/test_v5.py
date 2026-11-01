"""Prospective v5 execution, inference, missingness and source-bound gate regressions."""
import copy
import hashlib
import importlib
import json
import math
import re
import statistics
import sys
import tempfile
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "harness"))

from arms import ARMS, BLOCKED_DESIGN, MODELS, credit_multiplier, endpoint_kind, feature_seconds, planned_steps
from feasibility import calibration_projection, design_totals, report, sample_size
from mutation_adequacy import apply_mutation, mutation_outcome, mutations


def test_normal_planning_computes_fixed_sample_and_worst_case_sensitivity():
    planning = sample_size()
    expected = 2 * 25**2 * (statistics.NormalDist().inv_cdf(.975)
                           + statistics.NormalDist().inv_cdf(.8))**2 / (3 * 10**2)
    assert planning["unrounded_per_arm_model"] == pytest.approx(expected)
    assert planning["trajectories_per_arm_model"] == math.ceil(expected) == 33
    assert planning["total_trajectories"] == 495 and not planning["binary_cr1_powered"]
    assert [sample_size(sd_pp=sd)["trajectories_per_arm_model"] for sd in (15, 20, 25, 50)] == [12, 21, 33, 131]
    assert [sample_size(sd_pp=sd)["total_trajectories"] for sd in (15, 20, 25, 50)] == [180, 315, 495, 1965]
    assert "ASSUMPTION" in planning["sd_status"]


@pytest.mark.parametrize("kwargs", [{"sd_pp": 0}, {"sd_pp": 51}, {"sd_pp": None}, {"sd_pp": float("nan")},
                                   {"delta_pp": 0}, {"alpha": 0}, {"power": .5}, {"models": True}])
def test_invalid_planning_does_not_silently_default(kwargs):
    with pytest.raises(ValueError):
        sample_size(**kwargs)


def test_resource_totals_are_shared_with_actual_arm_steps():
    main = design_totals(per_cell=33)
    calibration = design_totals(per_cell=1, calibration=True)
    assert (main["trajectories"], main["sessions"], main["maximum_agent_hours"]) == (495, 8415, 3836.25)
    assert (calibration["trajectories"], calibration["sessions"], calibration["maximum_agent_hours"]) == (15, 240, 105)
    assert main["nominal_credit_caps_sum"] + calibration["nominal_credit_caps_sum"] == 2902500
    assert main["operational_soft_caps_sum"] + calibration["operational_soft_caps_sum"] == 2612250
    assert sum(planned_steps(arm, 10, True) for arm in ARMS) * 99 == 8415
    assert feature_seconds("D", {"feature": 1800, "post": 900}) == 2700
    assert endpoint_kind("D") == "feature" and endpoint_kind("E") == "repair"
    assert main["by_arm"]["D"]["sessions_per_trajectory"] == 11
    assert main["by_arm"]["D"]["nominal_credits_per_trajectory"] == 6300


def test_parallel_signed_build_stages_have_distinct_key_identity_prefixes():
    source = (ROOT / "harness/Dockerfile.isolated").read_text()
    stages = source.split("FROM ")[1:3]
    identities = []
    for stage in stages:
        match = re.search(r'^ENV PACKAGER="[^<]+<([^>]+)>"$', stage, re.M)
        assert match is not None and stage.index(match.group()) < stage.index("abuild-keygen -an")
        identities.append(match.group(1))

    assert len(set(identities)) == 2 and all(identities)


@pytest.mark.parametrize(("arm", "kind"), [("A", "repair"), ("D", "consolidation"), ("E", "review"),
                                        ("B", "repair"), ("unknown", "feature")])
def test_no_generic_arm_or_larger_cap_bypass(arm, kind):
    with pytest.raises(ValueError):
        credit_multiplier(arm, kind)


def calibration_fixture():
    return {
        "schema_version": 1, "analysis_design": BLOCKED_DESIGN,
        "inputs_sha256": "a" * 64, "source_commit": "b" * 40,
        "runs": [{"arm": arm, "assigned_model": model, "replicate": 1, "change_request": False,
                  "credits": 1, "seconds": 1, "credits_complete": True, "model_verified": True,
                  "assistance_complete": True, "evidence": "synthetic cost-only fixture"}
                 for model in MODELS for arm in ARMS],
        "cr1_forecast_credits_per_trajectory": 270, "cr1_forecast_seconds_per_trajectory": 2700,
        "cr1_forecast_evidence": "synthetic full original CR1 forecasts, not observed CR1",
        "deadline_remaining_seconds": 30 * 86400,
        "infrastructure": {"failed_steps": 0, "steps": 240},
        "primary_measurements_missing": 0, "oracle_contradictions": 0,
        "reference_evaluations": 33, "information_boundary_failures": 0,
    }


def test_cost_only_projection_includes_calibration_prior_holds_and_all_fixed_runs():
    cfg = json.loads((ROOT / "harness/study-config.json").read_text())
    cfg["study_timeout_seconds"] = 30 * 86400
    result = calibration_projection(calibration_fixture(), cfg)
    assert result["numerical_go"] and not result["launch_authorized"]
    assert float(result["projected_main_credits"]) == 33 * 15 * 1.25 + 495 * 270
    expected = 21.79019 + 1200 + 15 + 33 * 15 * 1.25 + 495 * 270 + 600
    assert float(result["projected_admission_including_calibration_prior_holds"]) == pytest.approx(expected)
    plan = report(cfg)
    assert not plan["worst_case_caps_fit_aggregate"] and plan["collection_blocked"]
    assert plan["remaining_before_calibration_credits"] == "268778.20981"
    assert plan["calibration_feasibility"] is None
    assert plan["combined_maximum_agent_hours"] == 3941.25


@pytest.mark.parametrize(("field", "value"), [
    ("primary_measurements_missing", 1), ("oracle_contradictions", 1),
    ("reference_evaluations", 32), ("information_boundary_failures", 1),
    ("deadline_remaining_seconds", 14 * 86400),
])
def test_proposed_feasibility_failures_halt_without_sample_reduction(field, value):
    evidence = calibration_fixture()
    evidence[field] = value
    cfg = dict(json.loads((ROOT / "harness/study-config.json").read_text()), study_timeout_seconds=30 * 86400)
    result = calibration_projection(evidence, cfg)
    assert not result["numerical_go"] and "never reduce" in result["action_if_no_go"]
    assert sample_size()["total_trajectories"] == 495


def test_5_percent_threshold_and_unknown_evidence_are_not_success_shaped():
    cfg = json.loads((ROOT / "harness/study-config.json").read_text())
    cfg["study_timeout_seconds"] = 30 * 86400
    evidence = calibration_fixture()
    evidence["infrastructure"]["failed_steps"] = 12
    assert calibration_projection(evidence, cfg)["numerical_go"]
    evidence["infrastructure"]["failed_steps"] = 13
    assert not calibration_projection(evidence, cfg)["numerical_go"]
    evidence = calibration_fixture()
    evidence["runs"][0]["assistance_complete"] = False
    assert not calibration_projection(evidence, cfg)["numerical_go"]
    evidence["runs"][0]["credits"] = None
    with pytest.raises(ValueError, match="explicit"):
        calibration_projection(evidence, cfg)


def test_calibration_cannot_contain_outcomes_missing_cells_or_historical_identity():
    cfg = json.loads((ROOT / "harness/study-config.json").read_text())
    for mutate in (
        lambda data: data["runs"].pop(),
        lambda data: data["runs"][0].update(final_coverage=100),
        lambda data: data["runs"][0].update(change_request=True),
        lambda data: data.update(analysis_design="model-stratified-v1"),
        lambda data: data["runs"].__setitem__(1, copy.deepcopy(data["runs"][0])),
    ):
        evidence = calibration_fixture()
        mutate(evidence)
        with pytest.raises(ValueError):
            calibration_projection(evidence, cfg)


def summary_cohort():
    rows = []
    for index, model in enumerate(MODELS):
        for arm in ARMS:
            for replicate in range(1, 34):
                baseline = 10 + index * 10 + replicate - 1
                gain = (3, 6, 21)[index] if arm == "B" else 0
                rows.append({
                    "run_id": f"synthetic-{model}-{arm}-{replicate}", "assigned_model": model,
                    "arm": arm, "replicate": replicate, "suite": "synthetic", "scheduled_features": 10,
                    "change_request_planned": True, "intervention": "unassisted",
                    "end": {"pass_rate": baseline + gain, "open_regressions": 0},
                    "cr_success": True, "all_attempt_delivery_cost": 1, "all_attempt_cr_cost": 1,
                    "regression_auc": 0, "pre_cr1_prerequisite_acquisition": "both",
                    "cr1_graded": {"passed": 15, "observed_denominator": 15},
                })
    return rows


def blocked(rows):
    module = importlib.import_module("blocked_analysis")
    return module.analyze_blocked(rows, panel={"suite": "synthetic", "review": {"accepted": False}},
                                  seed=2027, n=25, role="pilot-estimation", cost_unit="credits",
                                  roster={"models": list(MODELS), "runs_per_arm": 33,
                                          "calibration_runs_per_arm": 1})


def test_equal_model_weight_primary_whole_run_inference_and_variance_df():
    result = blocked(summary_cohort())
    primary = result["endpoints"]["H1"]["B-D"]
    assert primary["difference"] == 10 and primary["primary_eligible"]
    assert primary["ci"][0] <= 10 <= primary["ci"][1]
    assert set(result["endpoints"]["H1"]) == {"B-D", "B-A", "B-C", "E-B", "E-D"}
    assert result["pooled_within_cell_final_coverage"]["df"] == 480
    assert result["pooled_within_cell_B_D_final_coverage"]["df"] == 192
    assert result["pooled_within_cell_final_coverage"]["variance_pp_squared"] == statistics.variance(range(33))
    assert result["arms"]["B"][MODELS[0]]["cr1_binary_clopper_pearson_95"][1] == 1
    assert "secondary" in result["methods"]["cr1"]
    assert not result["endpoints"]["H1"]["E-B"]["primary_eligible"]


def test_missingness_and_assistance_keep_all_allocations_and_block_primary_interpretation():
    rows = summary_cohort()
    rows.pop(next(index for index, row in enumerate(rows) if row["arm"] == "D"))
    result = blocked(rows)
    assert not result["allocation_complete"] and not result["primary_estimates_available"]
    assert result["arms"]["D"][MODELS[0]]["allocated"] == 33
    assert result["arms"]["D"][MODELS[0]]["coverage_missing"] == 1
    assert result["endpoints"]["H1"]["B-D"]["difference"] is None
    rows = summary_cohort()
    next(row for row in rows if row["arm"] == "B")["intervention"] = "assisted"
    result = blocked(rows)
    assert len(result["runs"]) == 495 and not result["primary_estimates_available"]
    assert result["endpoints"]["H1"]["B-D"]["difference"] == 10
    assert result["endpoints"]["H1"]["B-D"]["ci"] == (None, None)
    assert result["endpoints"]["H1"]["B-D"]["content_assistance_compromises_interpretation"]


def test_v2_duplicate_out_of_sample_and_historical_rows_are_rejected():
    for value in (0, 34, True):
        rows = summary_cohort()
        rows[0]["replicate"] = value
        with pytest.raises(ValueError):
            blocked(rows)
    rows = summary_cohort()
    rows.append(copy.deepcopy(rows[0]))
    with pytest.raises(ValueError, match="Duplicate"):
        blocked(rows)


def record(kind, k, outcomes):
    return {"kind": kind, "k": k, "measure": {"hidden": dict(outcomes), "hidden_total": len(outcomes),
             "hidden_passed": sum(value == "passed" for value in outcomes.values())}}


def risk_fixture():
    contracts = [{"id": f"test_f{feature:02d}::contract", "feature": f"f{feature:02d}", "role": "feature",
                  "from_cycle": 1, "through_cycle": 10, "unchanged": True, "oracle_version": "synthetic"}
                 for feature in (1, 9, 10)]
    contracts += [{"id": f"test_cr1::contract{index}", "feature": "cr1", "role": "cr1",
                   "from_cycle": 11, "through_cycle": 11, "unchanged": True, "oracle_version": "synthetic"}
                  for index in range(15)]
    panel = {"suite": "synthetic", "review": {"accepted": False}, "contracts": contracts}
    passing = {entry["id"]: "passed" for entry in contracts if entry["role"] == "feature"}
    return panel, passing


def raw_risk(arm, records, features=2):
    return {"dir": "", "meta": {"run_id": "synthetic", "arm": arm, "suite": "synthetic", "features": features,
                               "phase": "pilot-estimation", "change_request": True},
            "recs": records}


def test_missing_inherited_outcome_is_never_a_not_lost_denominator():
    pilot = importlib.import_module("pilot_analysis")
    panel, passed = risk_fixture()
    missing = dict(passed, **{"test_f01::contract": "failed", "test_f09::contract": "error"})
    history = pilot.retention(raw_risk("E", [record("feature", 1, passed), record("repair", 1, passed),
                                            record("feature", 2, missing), record("repair", 2, missing)]), panel)
    row = history["rows"][-1]
    assert row["risk_set"] == 3 and row["observed_risk_set"] == 2 and row["missing_risk_set"] == 1
    assert row["observed_open_losses"] == 1 and row["density"] == .5
    assert row["open_losses"] is None and row["full_risk_density"] is None
    assert not history["history_complete"] and history["post_loss_test_cycles"] is None
    all_missing = {key: "error" for key in passed}
    history = pilot.retention(raw_risk("E", [record("feature", 1, passed), record("repair", 1, passed),
                                            record("feature", 2, all_missing), record("repair", 2, all_missing)]), panel)
    assert history["rows"][-1]["density"] is None and history["rows"][-1]["observed_risk_set"] == 0


def test_cr1_grade_retained_missing_risk_and_prerequisite_selection():
    pilot = importlib.import_module("pilot_analysis")
    panel, passed = risk_fixture()
    records = [record("feature", k, passed) for k in range(1, 11)]
    cr = {entry["id"]: "passed" for entry in panel["contracts"]}
    cr["test_cr1::contract0"] = "failed"
    cr["test_cr1::contract1"] = "error"
    cr["test_f01::contract"] = "failed"
    cr["test_f09::contract"] = "error"
    summary = pilot.summarise_pilot(raw_risk("D", records + [record("change_request", 10, cr)], 10), panel)
    assert summary["cr1_graded"]["passed"] == 13 and summary["cr1_graded"]["contracts_total"] == 15
    assert summary["cr1_graded"]["observed_denominator"] == 14 and summary["cr1_graded"]["missing_denominator"] == 1
    assert summary["cr1_graded"]["passed_fraction"] is None and summary["cr_success"] is None
    assert summary["cr1_retained_losses"]["pre_passed_risk_set"] == 3
    assert summary["cr1_retained_losses"]["observed_risk_set"] == 2
    assert summary["cr1_retained_losses"]["missing_risk_set"] == 1
    assert summary["cr1_retained_losses"]["lost_observed"] == 1
    assert summary["pre_cr1_prerequisite_acquisition"] == "both"
    records[-1]["measure"]["hidden"]["test_f10::contract"] = "failed"
    records[-1]["measure"]["hidden_passed"] = 2
    summary = pilot.summarise_pilot(raw_risk("D", records + [record("change_request", 10, cr)], 10), panel)
    assert summary["pre_cr1_prerequisite_acquisition"] == "not-both"
    records[-1]["measure"]["hidden"]["test_f10::contract"] = "passed"
    records[-1]["measure"]["hidden"]["test_f09::contract"] = "failed"
    summary = pilot.summarise_pilot(raw_risk("D", records + [record("change_request", 10, cr)], 10), panel)
    assert summary["pre_cr1_prerequisite_acquisition"] == "both"
    assert summary["pre_cr1_prerequisite_availability"] == "not-both"


@pytest.mark.parametrize("arm", list(ARMS))
def test_each_arm_stages_only_released_immutable_specifications_and_examples(tmp_path, arm):
    module = importlib.import_module("visible_specifications")
    suite = json.loads((ROOT / "suites/s1-retrofit/suite.json").read_text())
    files = module.visible_files(ROOT / "suites/s1-retrofit", suite["features"][:2])
    assert set(path.split("/")[1] for path in files if path.endswith(".md")) == {"f01.md", "f02.md"}
    assert all(not any(marker in path for marker in ("f03", "f09", "f10", "cr1", "hidden", "reference"))
               for path in files)
    repo = tmp_path / arm
    repo.mkdir()
    module.stage(repo, files)
    (repo / "specifications/f01.md").write_text("invented defect specification")
    (repo / "specifications/f10.md").write_text("invented future")
    changed = module.restore(repo, files)
    assert changed == ["specifications/f01.md", "specifications/f10.md"]
    assert not (repo / "specifications/f10.md").exists()
    assert (repo / "specifications/f01.md").read_bytes() == files["specifications/f01.md"]


def test_specification_bound_test_correction_is_separate_E_not_B(tmp_path):
    runner = importlib.import_module("runner")
    visible = importlib.import_module("visible_specifications")
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    runner.git(repo, "init", "-q")
    runner.git(repo, "config", "user.name", "synthetic")
    runner.git(repo, "config", "user.email", "synthetic@example.invalid")
    path = repo / "tests/test_pin.py"
    old = "def test_pin():\n    assert 1 == 0\n"
    new = "def test_pin():\n    assert 1 == 1\n"
    path.write_text(old)
    runner.git(repo, "add", "-A")
    runner.git(repo, "commit", "-qm", "synthetic old test")
    before = runner.head(repo)
    feature = {"id": "f01", "title": "Synthetic", "story": "Synthetic rule", "rules": ["One equals one"], "api": []}
    spec = visible.specification_bytes(feature)
    files = {"specifications/f01.md": spec}
    path.write_text(new)
    evidence = {"changes": [{"path": "tests/test_pin.py",
                            "before_sha256": hashlib.sha256(old.encode()).hexdigest(),
                            "after_sha256": hashlib.sha256(new.encode()).hexdigest(),
                            "specification": "specifications/f01.md",
                            "spec_sha256": hashlib.sha256(spec).hexdigest(), "rule": 1,
                            "rationale": "Synthetic old expectation contradicts immutable rule1; corrected expectation is one"}]}
    (repo / "REPAIR_EVIDENCE.json").write_text(json.dumps(evidence))
    (repo / "TEST_EVIDENCE.json").write_text(json.dumps(evidence))
    runner.git(repo, "add", "-A")
    runner.git(repo, "commit", "-qm", "synthetic specification correction")
    violations, summary = visible.intervention_evidence(repo, before, "repair", files, [feature], runner.git)
    assert not violations and summary["observed_paths"] == ["tests/test_pin.py"]
    assert "unreviewed" in summary["semantic_review"]
    violations, _ = visible.intervention_evidence(repo, before, "consolidation", files, [feature], runner.git)
    assert any("accepted" in value for value in violations)
    evidence["changes"][0]["specification"] = "specifications/f10.md"
    (repo / "REPAIR_EVIDENCE.json").write_text(json.dumps(evidence))
    violations, _ = visible.intervention_evidence(repo, before, "repair", files, [feature], runner.git)
    assert violations


@pytest.mark.parametrize(("path_name", "old", "new"), [
    ("tests/test_pin.py", "EXPECTED = 1\ndef test_pin():\n    assert 1 == EXPECTED\n",
     "EXPECTED = 2\ndef test_pin():\n    assert 1 == EXPECTED\n"),
    ("tests/test_pin.py", "class TestPin:\n    expected = 1\n    def test_pin(self):\n        assert 1 == self.expected\n",
     "class TestPin:\n    expected = 2\n    def test_pin(self):\n        assert 1 == self.expected\n"),
    ("tests/conftest.py", "EXPECTED = 1\ndef fixture_value():\n    return EXPECTED\n",
     "EXPECTED = 2\ndef fixture_value():\n    return EXPECTED\n"),
    ("tests/test_pin.py", "def test_pin():\n    assert 1 == 1\n",
     "def test_pin():\n    assert 1 == 1\n\ndef test_added():\n    assert True\n"),
])
def test_accepted_file_context_cannot_be_weakened_or_extended(tmp_path, path_name, old, new):
    runner = importlib.import_module("runner")
    visible = importlib.import_module("visible_specifications")
    repo = tmp_path / "repo"
    path = repo / path_name
    path.parent.mkdir(parents=True)
    runner.git(repo, "init", "-q")
    runner.git(repo, "config", "user.name", "synthetic")
    runner.git(repo, "config", "user.email", "synthetic@example.invalid")
    path.write_text(old)
    runner.git(repo, "add", "-A")
    runner.git(repo, "commit", "-qm", "synthetic accepted file")
    before = runner.head(repo)
    path.write_text(new)
    runner.git(repo, "add", "-A")
    runner.git(repo, "commit", "-qm", "synthetic context change")

    paths, modified = visible.test_changes(repo, before, runner.git)

    assert paths == [path_name] and modified == [path_name]


def test_new_test_file_is_allowed_without_changing_accepted_file(tmp_path):
    runner = importlib.import_module("runner")
    visible = importlib.import_module("visible_specifications")
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    runner.git(repo, "init", "-q")
    runner.git(repo, "config", "user.name", "synthetic")
    runner.git(repo, "config", "user.email", "synthetic@example.invalid")
    (repo / "tests/test_accepted.py").write_text("def test_accepted():\n    assert True\n")
    runner.git(repo, "add", "-A")
    runner.git(repo, "commit", "-qm", "synthetic accepted file")
    before = runner.head(repo)
    (repo / "tests/test_added.py").write_text("def test_added():\n    assert True\n")
    runner.git(repo, "add", "-A")
    runner.git(repo, "commit", "-qm", "synthetic added file")

    paths, modified = visible.test_changes(repo, before, runner.git)

    assert paths == ["tests/test_added.py"] and modified == []


def test_D_retry_shares_original_single_45_minute_540_credit_allowance(tmp_path):
    study = importlib.import_module("study")
    cfg = json.loads((ROOT / "harness/study-config.json").read_text())
    current = study.Controller(tmp_path, cfg, smoke=True, phase="first", study_id="synthetic-D")
    cell = next(cell for cell in current.state["cells"] if cell["arm"] == "D")
    args = SimpleNamespace(config=str(current.runtime_config), suite=str(ROOT / "suites/s1-retrofit"),
                           arm="D", run_id=cell["run_id"], phase="dry", features=1, no_cr=True, allow_draft=False)
    run = study.StudyRun(args, current, cell)
    run.current_step = "f01-feature"
    current.smoke = False
    assert run.remaining_allowance(2700) == (2700, 540 * study.NANO)
    attempt = current.new_attempt(cell, "f01-feature")
    assert current.state["ledger"]["entries"][attempt["id"]]["reserved_nano"] == 600 * study.NANO
    usage = {"credits_complete": True, "totalNanoAiu": 250 * study.NANO}
    attempt.update(seconds=300, usage=usage)
    current.settle_attempt(attempt["id"], usage)
    seconds, credit = run.remaining_allowance(2700)
    assert (seconds, credit) == (2400, 290 * study.NANO)
    retry = current.new_attempt(cell, "f01-feature", credit + 60 * study.NANO)
    assert current.state["ledger"]["entries"][retry["id"]]["reserved_nano"] == 350 * study.NANO
    retry.update(seconds=2400, usage={"credits_complete": True, "totalNanoAiu": 290 * study.NANO})
    with pytest.raises(study.StudyError, match="exhausted"):
        run.remaining_allowance(2700)


def test_current_schedule_and_readiness_do_not_reuse_v4_approvals():
    study = importlib.import_module("study")
    registration = importlib.import_module("prepare_registration")
    config = json.loads((ROOT / "protocol/pilot-estimation.json").read_text())
    cells = study.schedule(False, "first", 2027)
    assert len(cells) == 495 and all(cell["analysis_design"] == BLOCKED_DESIGN for cell in cells)
    assert all(sum(cell["arm"] == arm and cell["assigned_model"] == model for cell in cells) == 33
               for arm in ARMS for model in MODELS)
    assert len(study.schedule(False, "calibration", 2027)) == 15
    readiness = registration.readiness(config, {"review": {"accepted": False}})
    assert readiness["draft_complete"] and readiness["registration_recorded"]
    assert not readiness["prospective_amendment_recorded"] and not readiness["author_submission_ready"]
    assert not readiness["execution_ready"]
    assert len([item for item in readiness["collection_unresolved"] if item.startswith("candidate_requirements.")]) == 10
    assert config["historical_v4_owner_approval"]["approved"] and not config["owner_approval"]["approved"]
    freeze = json.loads((ROOT / "protocol/freeze.json").read_text())
    assert study.fingerprint() != freeze["inputs_sha256"]
    assert not (ROOT / "protocol/freeze-v5.json").exists()


def test_historical_v1_variance_df_and_pairwise_diagnostics_are_not_33_cell_planning():
    from test_pilot_analysis import model_cohort
    pilot = importlib.import_module("pilot_analysis")
    panel = {"suite": "synthetic", "review": {"accepted": False},
             "contracts": [{"id": name, "feature": feature, "role": role, "from_cycle": start,
                            "through_cycle": end, "unchanged": True, "oracle_version": "synthetic"}
                           for name, feature, role, start, end in (
                               ("test_f01::test_x", "f01", "feature", 1, 10),
                               ("test_f02::test_y", "f02", "feature", 2, 10),
                               ("test_cr1::test_cr", "cr1", "cr1", 11, 11))]}
    result = pilot.analyze_pilot(model_cohort(), panel=panel, n=25)
    assert len(result["runs"]) == 18 and result["pooled_within_cell_final_coverage"]["df"] == 9
    contrast = result["endpoints"][MODELS[0]]["H1"]["B-A"]
    assert contrast["four_pairwise_differences"] == [0, 0, 0, 0]
    assert contrast["ci"] == (None, None) and "no nominal" in contrast["interval_scope"]
    assert result["arms"]["A"][MODELS[0]]["allocated"] == 2


def test_bounded_mutation_generation_and_unavailability_denominators():
    source = "def f(x):\n    return x == 0 if True else x != 1\n"
    generated = mutations(source)
    assert generated == mutations(source) and 0 < len(generated) <= 24
    assert all(apply_mutation(source, item) != source for item in generated)
    assert mutation_outcome({"a": "passed", "b": "failed"}, {"a", "b"}) == "killed"
    assert mutation_outcome({"a": "passed", "b": "passed"}, {"a", "b"}) == "survived"
    assert mutation_outcome({"a": "passed", "b": "error"}, {"a", "b"}) == "unavailable"
    assert mutation_outcome({"a": "passed"}, {"a", "b"}) == "unavailable"
    with pytest.raises(ValueError):
        mutations(source, 25)


def test_private_publication_pending_and_no_missing_feasibility_launch(tmp_path):
    study = importlib.import_module("study")
    reporter = importlib.import_module("study_report")
    cfg = json.loads((ROOT / "harness/study-config.json").read_text())
    assert study.feasibility_errors(cfg)
    with pytest.raises(study.StudyError, match="calibration state unavailable"):
        study.calibration_budget(cfg)
    with pytest.raises(study.StudyError, match="publication is pending"):
        reporter.publish(tmp_path, "synthetic")


def test_owner_public_development_permission_does_not_release_research_or_collection():
    registration = importlib.import_module("prepare_registration")
    config = json.loads((ROOT / "protocol/pilot-estimation.json").read_text())
    sharing = config["sharing"]
    decision = sharing["interim_public_development"]
    assert config["study"]["title"] == "Feature-Driven Decay in an Agentic Coding Loop"
    assert decision["owner_selection"] == "public-pr-now"
    assert decision["development_source_PRs_authorized_for_parent"] is True
    assert decision["collection_authorized"] is False
    assert decision["OSF_mutation_authorized"] is False
    assert decision["researcher_archive_or_study_result_release_authorized"] is False
    assert sharing["publication_release_authorized"] is False
    assert sharing["owner_privacy_attestations_completed"] is False
    assert sharing["operator_access_readback_completed"] is False
    assert config["historical_exports_policy"]["status"] == "owner-deferred"
    assert config["historical_exports_policy"]["prospective_complete_billing_model_assistance_requirements_waived"] is False
    assert config["owner_approval"]["approved"] is False
    assert config["registration"]["prospective_amendment_completed"] is False
    assert registration.readiness(config, {"review": {"accepted": False}})["execution_ready"] is False


def test_new_source_files_are_in_registration_bundle_and_sdk_caches_are_not_inputs():
    registration = importlib.import_module("prepare_registration")
    assert {"harness/arms.py", "harness/feasibility.py", "harness/mutation_adequacy.py",
            "harness/prompts/repair-step.prompt.md", "protocol/change-request-pool.json",
            "protocol/prospective-v5-2026-11-01.md"} <= set(registration.SUBMISSION_FILES)
    assert all((ROOT / path).is_file() for path in registration.SUBMISSION_FILES)


def test_old_gate_strings_cannot_approve_v5_or_omit_source_bound_independent_review(tmp_path, monkeypatch):
    study = importlib.import_module("study")
    (tmp_path / "protocol").mkdir()
    (tmp_path / "protocol/pilot-estimation.json").write_text(json.dumps({
        "study": {"analysis_design": BLOCKED_DESIGN}}))
    cfg = json.loads((ROOT / "harness/study-config.json").read_text())
    sha = "a" * 40
    digest = "b" * 64
    manifest = {"tag": "protocol-frozen-v4", "commit": sha, "inputs_sha256": digest,
                "registration_url": "https://example.org/synthetic", "registration_date": "synthetic",
                **{gate: "synthetic legacy evidence" for gate in study.GATES}}
    (tmp_path / "protocol/freeze-v5.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(study, "fingerprint", lambda root=ROOT: digest)
    monkeypatch.setattr(study, "command", lambda *args, **kwargs: sha)
    errors = study.freeze_errors(cfg, tmp_path)
    assert any("v4 does not authorize" in error for error in errors)
    assert sum("Pending v5 exact-source" in error for error in errors) == 10
    from feasibility import REQUIRED_GATES
    manifest.update(tag="protocol-frozen-v5", analysis_design=BLOCKED_DESIGN,
                    prospective_amendment_completed=True, owner_launch_authorized=True,
                    authorized_phases=["pilot-estimation"],
                    candidate_evidence={gate: {"accepted": True, "date": "synthetic",
                        "evidence": "synthetic fixture, not actual approval", "source_commit": sha,
                        "inputs_sha256": digest, "independent": True, "reviewer": "synthetic reviewer"}
                        for gate in REQUIRED_GATES})
    (tmp_path / "protocol/freeze-v5.json").write_text(json.dumps(manifest))
    assert study.freeze_errors(cfg, tmp_path) == []
    manifest["candidate_evidence"]["exact_source_scientific_review"]["independent"] = False
    (tmp_path / "protocol/freeze-v5.json").write_text(json.dumps(manifest))
    assert any("independent reviewer" in error for error in study.freeze_errors(cfg, tmp_path))
    manifest["candidate_evidence"]["exact_source_scientific_review"]["inputs_sha256"] = "wrong"
    (tmp_path / "protocol/freeze-v5.json").write_text(json.dumps(manifest))
    assert any("exact_source_scientific_review" in error for error in study.freeze_errors(cfg, tmp_path))


def test_real_fixed_ruff_ignores_noqa_and_candidate_config(tmp_path):
    sys.path.insert(0, str(ROOT / "skeleton/tools"))
    metrics = importlib.import_module("metrics_core")
    repo = tmp_path / "repo"
    (repo / "src").mkdir(parents=True)
    (repo / "src/code.py").write_text("import os  # noqa: F401\n")
    (repo / "pyproject.toml").write_text("[tool.ruff.lint]\nignore = ['F401']\n")
    (repo / ".gitignore").write_text("src/\n")
    measured = metrics.lint(str(repo / "src"), "ruff", config_root=str(repo))
    assert measured["by_code"]["F401"] == 1 and measured["warnings"] > 0


def test_external_C_locator_coverage_is_not_file_overlap_or_repair_proof(tmp_path):
    runner = importlib.import_module("runner")
    fidelity = importlib.import_module("fidelity")
    repo = tmp_path / "repo"
    repo.mkdir()
    runner.git(repo, "init", "-q")
    runner.git(repo, "config", "user.name", "synthetic")
    runner.git(repo, "config", "user.email", "synthetic@example.invalid")
    (repo / "REVIEW.md").write_text("Synthetic finding: code.py line1 names are unclear.\n")
    (repo / "code.py").write_text("x = 1\n")
    runner.git(repo, "add", "-A")
    runner.git(repo, "commit", "-qm", "synthetic review")
    reviewed = runner.head(repo)
    (repo / "code.py").write_text("case_count = 1\n")
    runner.git(repo, "add", "-A")
    runner.git(repo, "commit", "-qm", "synthetic later feature")
    feature = runner.head(repo)
    run = {"dir": str(tmp_path), "meta": {"arm": "C", "features": 2}, "recs": [
        {"kind": "review", "k": 1, "measure": {"head": reviewed}},
        {"kind": "feature", "k": 2, "measure": {"head": feature}}]}
    assert fidelity.review_follow_through(run)["unknown_reviews"] == 1
    annotation = {"cycle": 1, "review_head": reviewed, "review_path": "REVIEW.md", "review_lines": [1, 1],
                  "later_feature_head": feature, "diff_path": "code.py", "diff_hunk": "@@ -1 +1 @@",
                  "assessment": "implemented", "reviewer": "synthetic external annotator",
                  "evidence": "synthetic semantic judgment, not independent study evidence"}
    run["meta"]["review_follow_through_annotations"] = [annotation]
    observed = fidelity.review_follow_through(run)
    assert observed["observed_reviews"] == 1 and observed["unknown_reviews"] == 0
    assert not observed["repair_effect_proven"] and observed["coverage_complete"]
    annotation["diff_hunk"] = "@@ -99 +99 @@"
    assert fidelity.review_follow_through(run)["observed_reviews"] == 0


def publication_fixture(directory):
    reporter = importlib.import_module("study_report")
    directory.mkdir()
    for name in reporter.EXPORTS:
        (directory / name).write_text("{}\n" if name.endswith(".json")
                                      else "Synthetic bounded-sharing fixture; not study data.\n")
    provenance = {"analysis_design": BLOCKED_DESIGN, "allocated_trajectories": 495,
                  "registered_or_frozen_by_runner": False, "study_id": "v5-synthetic-stress"}
    (directory / "provenance.json").write_text(json.dumps(provenance))
    return reporter


def test_complete_fixed_allocation_worst_case_episode_csv_is_shareable(tmp_path):
    directory = tmp_path / "results"
    reporter = publication_fixture(directory)
    panel = json.loads((ROOT / "protocol/contract-panel.json").read_text())
    contracts = [item for item in panel["contracts"] if item["role"] == "feature"]
    fields = ["run_id", "arm", "model", "replicate", "contract", "feature", "onset_cycle",
              "onset_checkpoint", "recovery_cycle", "recovery_checkpoint", "recurrence",
              "duration_cycles", "uncertain", "censored"]

    def episodes():
        for model in MODELS:
            for arm in ARMS:
                for replicate in range(1, 34):
                    for contract in contracts:
                        single_checkpoint = arm in ("A", "D")
                        starts = range(contract["from_cycle"] + 1, contract["through_cycle"] + 1,
                                       2 if single_checkpoint else 1)
                        for occurrence, onset in enumerate(starts):
                            recovery = onset + int(single_checkpoint)
                            censored = recovery > contract["through_cycle"]
                            yield {
                                "run_id": f"pilot-estimation-{model}-{arm}-{replicate:02d}",
                                "arm": arm, "model": model, "replicate": replicate,
                                "contract": contract["id"], "feature": contract["feature"],
                                "onset_cycle": onset, "onset_checkpoint": "F",
                                "recovery_cycle": None if censored else recovery,
                                "recovery_checkpoint": None if censored else ("F" if single_checkpoint else "P"),
                                "recurrence": occurrence > 0,
                                "duration_cycles": None if censored else int(single_checkpoint),
                                "uncertain": False, "censored": censored,
                            }

    reporter.write_csv(directory / "episodes.csv", fields, episodes())

    assert (directory / "episodes.csv").stat().st_size > 4 * 1024 * 1024
    assert len(reporter.validated_artifacts(directory)) == len(reporter.EXPORTS)
    archive = reporter.package_results(directory, "v5-synthetic-stress")
    assert archive.is_file() and archive.stat().st_mode & 0o077 == 0


@pytest.mark.parametrize("invalid", ["credential", "allocation", "symlink"])
def test_v2_size_policy_does_not_waive_privacy_or_identity_checks(tmp_path, invalid):
    directory = tmp_path / "results"
    reporter = publication_fixture(directory)
    if invalid == "credential":
        (directory / "episodes.csv").write_text("ghp_" + "A" * 40)
    elif invalid == "allocation":
        provenance = json.loads((directory / "provenance.json").read_text())
        provenance["allocated_trajectories"] = 496
        (directory / "provenance.json").write_text(json.dumps(provenance))
    else:
        (directory / "episodes.csv").unlink()
        (directory / "episodes.csv").symlink_to(directory / "series.csv")

    with pytest.raises(importlib.import_module("study_io").StudyError):
        reporter.validated_artifacts(directory)


@pytest.fixture
def operator_tmp_path() -> Iterator[Path]:
    """Provide an owned fixture for source-root-relative controller receipts."""
    directory = ROOT / ".study"
    directory.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="v5-controller-test-", dir=directory) as name:
        yield Path(name)


def test_complete_cost_journal_is_carried_once_and_metadata_changes_invalidate_resume(operator_tmp_path, monkeypatch):
    tmp_path = operator_tmp_path
    study = importlib.import_module("study")
    from feasibility import report as plan_report
    digest, sha = "c" * 64, "d" * 40
    monkeypatch.setattr(study, "fingerprint", lambda root=ROOT: digest)
    monkeypatch.setattr(study, "command", lambda args, **kwargs: sha if "rev-parse" in args else "")
    cfg = json.loads((ROOT / "harness/study-config.json").read_text())
    cfg["study_timeout_seconds"] = 30 * 86400
    cfg["calibration_state"] = (tmp_path / "calibration/state.json").relative_to(ROOT).as_posix()
    cfg["feasibility_receipt"] = (tmp_path / "feasibility.json").relative_to(ROOT).as_posix()
    calibration = study.Controller(tmp_path / "calibration", cfg, smoke=False,
                                   phase="calibration", study_id="synthetic-calibration")
    for cell in calibration.state["cells"]:
        cell.update(status="completed", completed_steps=planned_steps(cell["arm"], 10, False),
                    host_invocation_seconds=[float(planned_steps(cell["arm"], 10, False))])
        for k in range(1, 11):
            for kind in importlib.import_module("arms").cycle_kinds(cell["arm"]):
                attempt = calibration.new_attempt(cell, f"f{k:02d}-{kind}")
                usage = {"credits_complete": True, "totalNanoAiu": study.NANO}
                attempt.update(status="agent_returned", seconds=1, usage=usage,
                               actual_models=[cell["assigned_model"]], actual_reasoning_efforts=["medium"])
                calibration.settle_attempt(attempt["id"], usage)
        metadata_path = calibration.directory / "runs" / cell["run_id"] / "run.json"
        metadata = study.read_json(metadata_path)
        metadata["intervention"] = {"coverage_complete": True, "assisted": False,
                                    "evidence": "synthetic unit-test evidence, no real collection"}
        study.atomic_json(metadata_path, metadata)
    calibration.state["status"] = "completed"
    calibration.save()
    binding = study.calibration_budget(cfg)
    assert binding["actual_calibration_nano"] == 240 * study.NANO and binding["attempt_count"] == 240
    evidence = calibration_fixture()
    evidence.update(inputs_sha256=digest, source_commit=sha)
    by_cell = {(item["arm"], item["assigned_model"]): item for item in binding["cells"]}
    for row in evidence["runs"]:
        actual = by_cell[(row["arm"], row["assigned_model"])]
        row.update(credits=actual["actual_nano"] / study.NANO, seconds=actual["seconds"])
    receipt = plan_report(cfg, evidence)
    receipt.update(source={"commit": sha, "inputs_sha256": digest, "working_tree_dirty": False},
                   calibration_binding=binding, calibration_state_sha256=binding["state_sha256"],
                   calibration_source_evidence=evidence)
    study.atomic_json(ROOT / cfg["feasibility_receipt"], receipt)
    assert study.feasibility_errors(cfg) == []
    monkeypatch.setattr(study, "freeze_errors", lambda *args, **kwargs: [])
    current = study.Controller(tmp_path / "main", cfg, smoke=False, phase="first", study_id="synthetic-main")
    for cell in current.state["cells"]:
        cell["status"] = "completed"
    monkeypatch.setattr(importlib.import_module("study_report"), "export", lambda *args: None)
    assert current.go()
    expected = study.credits(cfg["prior_credits"]) + 240 * study.NANO
    assert current.state["ledger"]["prior_nano"] == expected
    resumed = study.Controller(tmp_path / "main", cfg, smoke=False, phase="first", study_id="synthetic-main")
    assert resumed.go() and resumed.state["ledger"]["prior_nano"] == expected
    metadata_path = next((calibration.directory / "runs").glob("*/run.json"))
    metadata = study.read_json(metadata_path)
    metadata["intervention"]["evidence"] = "changed synthetic intervention metadata"
    study.atomic_json(metadata_path, metadata)
    assert study.feasibility_errors(cfg)
    with pytest.raises(study.StudyError, match="calibration budget/source binding changed"):
        study.Controller(tmp_path / "main", cfg, smoke=False, phase="first", study_id="synthetic-main")
