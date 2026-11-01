"""Deterministic prospective sample and cost-only feasibility; no model calls."""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from decimal import Decimal, InvalidOperation
from pathlib import Path
from statistics import NormalDist

from arms import ARMS, BLOCKED_DESIGN, MODELS, descriptors, planned_steps
from study_io import ROOT, StudyError, atomic_json, command, read_json

PLANNING_SD_PP = 25.0
DELTA_PP = 10.0
ALPHA = 0.05
POWER = 0.80
SENSITIVITY_SD_PP = (15.0, 20.0, 25.0, 50.0)
COST_MULTIPLIER = Decimal("1.25")
REQUIRED_GATES = (
    "exact_source_scientific_review", "five_arm_runtime_boundary_review",
    "triplicate_reference_oracle", "bounded_mutation_review",
    "billing_model_assistance_evidence", "cost_only_full_sample_feasibility",
    "owner_repository_privacy_attestations", "operator_access_readback",
    "prospective_osf_amendment", "owner_exact_source_freeze_and_launch",
)


def sample_size(*, sd_pp: float = PLANNING_SD_PP, delta_pp: float = DELTA_PP,
                alpha: float = ALPHA, power: float = POWER, models: int = 3) -> dict:
    """Normal planning for equal-model-weight B-D, not binary CR1 power."""
    if (type(models) is not int or models < 1
            or any(type(value) not in (float, int) or not math.isfinite(value)
                   for value in (sd_pp, delta_pp, alpha, power))
            or not 0 < sd_pp <= 50 or not 0 < delta_pp <= 100
            or not 0 < alpha < 1 or not 0.5 < power < 1):
        raise ValueError("Planning needs bounded positive SD/delta and valid alpha/power/model count")
    normal = NormalDist()
    z_alpha = normal.inv_cdf(1 - alpha / 2)
    z_power = normal.inv_cdf(power)
    unrounded = 2 * sd_pp**2 * (z_alpha + z_power)**2 / (models * delta_pp**2)
    per_cell = math.ceil(unrounded)
    return {
        "formula": "ceil(2 * SD_pp^2 * (z_(1-alpha/2) + z_power)^2 / (M * delta_pp^2))",
        "comparison": "equal-model-weight blocked final-coverage B-D",
        "sd_pp": sd_pp, "sd_status": "planning ASSUMPTION, not observed variance",
        "delta_pp": delta_pp, "alpha_two_sided": alpha, "power": power,
        "models": models, "z_alpha": z_alpha, "z_power": z_power,
        "unrounded_per_arm_model": unrounded, "trajectories_per_arm_model": per_cell,
        "arms": len(ARMS), "total_trajectories": per_cell * models * len(ARMS),
        "pooled_within_cell_df_all_five_arms_if_complete": models * len(ARMS) * (per_cell - 1),
        "pooled_within_cell_df_B_D_if_complete": models * 2 * (per_cell - 1),
        "binary_cr1_powered": False,
    }


def design_totals(*, per_cell: int, models: int = 3, calibration: bool = False) -> dict:
    """Compute session/time/cap arithmetic from the same descriptors as execution."""
    if type(per_cell) is not int or per_cell < 1 or type(models) is not int or models < 1:
        raise ValueError("Resource totals require positive integer cell/model counts")
    packages = descriptors()
    cells = per_cell * models
    cr = not calibration
    nominal = soft = seconds = sessions = 0
    by_arm = {}
    for arm, package in packages.items():
        count = planned_steps(arm, 10, cr)
        arm_seconds = 10 * (package["feature_seconds"] + package["post_seconds"])
        arm_nominal = 10 * (package["feature_nominal_credits"] + package["post_nominal_credits"])
        arm_soft = 10 * (package["feature_operational_soft_credits"]
                         + package["post_operational_soft_credits"])
        if cr:
            arm_seconds += package["change_request_seconds"]
            arm_nominal += package["change_request_nominal_credits"]
            arm_soft += package["change_request_operational_soft_credits"]
        by_arm[arm] = {"trajectories": cells, "sessions_per_trajectory": count,
                       "seconds_per_trajectory": arm_seconds,
                       "nominal_credits_per_trajectory": arm_nominal,
                       "soft_credits_per_trajectory": arm_soft}
        sessions += cells * count
        seconds += cells * arm_seconds
        nominal += cells * arm_nominal
        soft += cells * arm_soft
    return {"trajectories": cells * len(ARMS), "sessions": sessions,
            "maximum_agent_hours": seconds / 3600, "nominal_credit_caps_sum": nominal,
            "operational_soft_caps_sum": soft, "by_arm": by_arm,
            "soft_caps_are_billing_guarantees": False}


def amount(value: object, name: str) -> Decimal:
    """Read explicit nonnegative money/time amounts, never invent missing zeros."""
    if value is None or isinstance(value, bool):
        raise ValueError(f"{name} must be an explicit nonnegative amount")
    try:
        number = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError(f"{name} is not a number") from error
    if not number.is_finite() or number < 0:
        raise ValueError(f"{name} must be finite and nonnegative")
    return number


def calibration_projection(calibration: dict, cfg: dict) -> dict:
    """Project all fixed trajectories using excluded, outcome-free calibration."""
    from study import validate_config
    validate_config(cfg, smoke=False)
    required = {"schema_version", "analysis_design", "inputs_sha256", "source_commit", "runs",
                "cr1_forecast_credits_per_trajectory", "cr1_forecast_seconds_per_trajectory",
                "cr1_forecast_evidence", "deadline_remaining_seconds", "infrastructure",
                "primary_measurements_missing", "oracle_contradictions",
                "reference_evaluations", "information_boundary_failures"}
    if set(calibration) != required or calibration["schema_version"] != 1:
        raise ValueError("Feasibility evidence needs the exact outcome-free calibration schema")
    if calibration["analysis_design"] != BLOCKED_DESIGN:
        raise ValueError("Historical calibration is not v5 cost-only calibration")
    if not (isinstance(calibration["inputs_sha256"], str)
            and len(calibration["inputs_sha256"]) == 64
            and isinstance(calibration["source_commit"], str)
            and len(calibration["source_commit"]) == 40):
        raise ValueError("Calibration requires exact source bindings")
    runs = calibration["runs"]
    fields = {"arm", "assigned_model", "replicate", "change_request", "credits", "seconds",
              "credits_complete", "model_verified", "assistance_complete", "evidence"}
    if not isinstance(runs, list) or len(runs) != 15:
        raise ValueError("Calibration must include all 15 fixed arm/model cells, no substitutions")
    identities = set()
    cost = duration = Decimal(0)
    complete = True
    for run in runs:
        if not isinstance(run, dict) or set(run) != fields:
            raise ValueError("Calibration rows cannot contain outcomes, hints or unknown fields")
        identity = run["arm"], run["assigned_model"]
        if (identity[0] not in ARMS or identity[1] not in MODELS or identity in identities
                or type(run["replicate"]) is not int or run["replicate"] != 1
                or run["change_request"] is not False):
            raise ValueError("Calibration identity/CR1 differs from the fixed excluded design")
        identities.add(identity)
        complete &= (all(run[key] is True for key in
                         ("credits_complete", "model_verified", "assistance_complete"))
                     and isinstance(run["evidence"], str) and bool(run["evidence"].strip()))
        cost += amount(run["credits"], "calibration credits")
        duration += amount(run["seconds"], "calibration seconds")
    count = sample_size()["trajectories_per_arm_model"]
    cr_cost = amount(calibration["cr1_forecast_credits_per_trajectory"], "CR1 cost forecast")
    cr_time = amount(calibration["cr1_forecast_seconds_per_trajectory"], "CR1 time forecast")
    if not 270 <= cr_cost <= 300 or cr_time < 2700 or not calibration["cr1_forecast_evidence"]:
        raise ValueError("Calibration excludes CR1; reserve its full soft/nominal forecast and time ceiling")
    holds = sum((amount(item["reserved_credits"], "historical hold")
                 for item in cfg.get("historical_credit_provisions", [])), Decimal(0))
    prior = amount(cfg["prior_credits"], "known prior")
    admission = amount(cfg["ceiling_credits"], "local admission")
    main_cost = count * cost * COST_MULTIPLIER + Decimal(495) * cr_cost
    main_seconds = count * duration * COST_MULTIPLIER + Decimal(495) * cr_time
    # The controller is sequential; leave room for its largest original reservation.
    projected_admission = prior + holds + cost + main_cost + Decimal(600)
    remaining_time = amount(calibration["deadline_remaining_seconds"], "remaining deadline")
    usable_time = min(remaining_time, amount(cfg["study_timeout_seconds"], "prospective deadline ceiling"))
    infrastructure = calibration["infrastructure"]
    if (not isinstance(infrastructure, dict) or set(infrastructure) != {"failed_steps", "steps"}
            or any(type(infrastructure[key]) is not int or infrastructure[key] < 0
                   for key in infrastructure) or infrastructure["steps"] == 0
            or infrastructure["failed_steps"] > infrastructure["steps"]):
        raise ValueError("Infrastructure needs observed failed/total original steps")
    for field in ("primary_measurements_missing", "oracle_contradictions",
                  "reference_evaluations", "information_boundary_failures"):
        if type(calibration[field]) is not int or calibration[field] < 0:
            raise ValueError(f"{field} must be an observed nonnegative integer")
    criteria = {
        "failed_infrastructure_steps_at_most_5_percent":
            infrastructure["failed_steps"] / infrastructure["steps"] <= 0.05,
        "missing_primary_measurements_zero": calibration["primary_measurements_missing"] == 0,
        "oracle_contradictions_zero": calibration["oracle_contradictions"] == 0,
        "required_triplicate_references_complete": calibration["reference_evaluations"] == 33,
        "information_boundary_failures_zero": calibration["information_boundary_failures"] == 0,
        "billing_model_assistance_evidence_complete": complete,
        "all_495_affordable_within_remaining_admission": projected_admission <= admission,
        "all_495_within_remaining_sequential_deadline": main_seconds <= usable_time,
    }
    return {
        "cost_multiplier": str(COST_MULTIPLIER),
        "cost_multiplier_status": "prospective conservative ASSUMPTION, not an observed uncertainty bound",
        "calibration_actual_credits": str(cost), "calibration_actual_seconds": str(duration),
        "known_prior_credits": str(prior), "historical_holds_credits": str(holds),
        "projected_main_credits": str(main_cost), "largest_reservation_headroom_credits": 600,
        "projected_admission_including_calibration_prior_holds": str(projected_admission),
        "projected_main_seconds": str(main_seconds), "deadline_remaining_seconds": str(remaining_time),
        "deadline_usable_seconds": str(usable_time),
        "criteria": criteria, "numerical_go": all(criteria.values()),
        "projection_is_financial_guarantee": False, "launch_authorized": False,
        "action_if_no_go": "Halt and prospectively amend before collection; never reduce or replace n",
    }


def report(cfg: dict, calibration: dict | None = None) -> dict:
    """Return the full plan even when prospective feasibility evidence is absent."""
    from study import validate_config
    validate_config(cfg, smoke=False)
    planning = sample_size()
    if planning["trajectories_per_arm_model"] != 33:
        raise StudyError("Computed planning sample differs from the prospective fixed 33/cell")
    main = design_totals(per_cell=planning["trajectories_per_arm_model"])
    excluded = design_totals(per_cell=1, calibration=True)
    prior = amount(cfg["prior_credits"], "known prior")
    holds = sum((amount(item["reserved_credits"], "historical hold")
                 for item in cfg.get("historical_credit_provisions", [])), Decimal(0))
    admission = amount(cfg["ceiling_credits"], "local admission")
    return {
        "schema_version": 1, "status": "offline-v5-candidate-not-reviewed-not-frozen",
        "analysis_design": BLOCKED_DESIGN, "planning": planning,
        "sensitivity": [sample_size(sd_pp=sd) for sd in SENSITIVITY_SD_PP],
        "fixed_sample_before_outcomes": True, "outcome_driven_additions_or_replacements": False,
        "main": main, "excluded_calibration": excluded,
        "registered_envelope_credits": 300000, "local_admission_credits": str(admission),
        "known_prior_credits": str(prior), "historical_holds_credits": str(holds),
        "remaining_before_calibration_credits": str(admission - prior - holds),
        "combined_nominal_caps_plus_prior_holds": str(
            prior + holds + main["nominal_credit_caps_sum"] + excluded["nominal_credit_caps_sum"]),
        "combined_soft_caps_plus_prior_holds": str(
            prior + holds + main["operational_soft_caps_sum"] + excluded["operational_soft_caps_sum"]),
        "worst_case_caps_fit_aggregate": False,
        "combined_maximum_agent_hours": main["maximum_agent_hours"] + excluded["maximum_agent_hours"],
        "sequential_deadline_hours": cfg["study_timeout_seconds"] / 3600,
        "calibration_feasibility": calibration_projection(calibration, cfg) if calibration else None,
        "calibration_feasibility_status": "provided-projection-not-approval" if calibration else
            "unavailable: no new 15-cell cost-only calibration evidence or deadline readback",
        "required_source_bound_gates": list(REQUIRED_GATES),
        "launch_authorized": False, "collection_blocked": True,
        "financial_conversion": None,
    }


def main() -> int:
    """Write a deterministic hash-bound local planning receipt, never upload it."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "harness/study-config.json")
    parser.add_argument("--calibration", type=Path)
    parser.add_argument("--calibration-state", type=Path)
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    from study import fingerprint

    calibration = read_json(args.calibration) if args.calibration else None
    result = report(read_json(args.config), calibration)
    result["source"] = {"commit": command(["git", "rev-parse", "HEAD"], cwd=ROOT),
                        "inputs_sha256": fingerprint(ROOT),
                        "working_tree_dirty": bool(command(["git", "status", "--porcelain"], cwd=ROOT)),
                        "config_sha256": hashlib.sha256(args.config.read_bytes()).hexdigest()}
    if calibration and any(calibration[field] != result["source"][key]
                           for field, key in (("source_commit", "commit"),
                                              ("inputs_sha256", "inputs_sha256"))):
        raise StudyError("Calibration evidence belongs to different execution inputs")
    if calibration:
        if args.calibration_state is None:
            raise StudyError("A projected go requires the complete actual calibration attempt/accounting journal")
        from study import calibration_budget
        cfg = read_json(args.config)
        expected_state = ROOT / cfg.get("calibration_state", "")
        if args.calibration_state.resolve() != expected_state.resolve():
            raise StudyError("Calibration journal path differs from the prospective configuration")
        binding = calibration_budget(cfg)
        if amount(result["calibration_feasibility"]["calibration_actual_credits"], "calibration credits") != (
                Decimal(binding["actual_calibration_nano"]) / Decimal(1_000_000_000)):
            raise StudyError("Projection omits or changes actual calibration billing")
        by_identity = {(item["arm"], item["assigned_model"]): item for item in binding["cells"]}
        for run in calibration["runs"]:
            actual = by_identity[(run["arm"], run["assigned_model"])]
            if (amount(run["credits"], "cell credits") * Decimal(1_000_000_000) != actual["actual_nano"]
                    or amount(run["seconds"], "cell seconds") != Decimal(str(actual["seconds"]))):
                raise StudyError("Projection changed one fixed calibration cell's actual resources")
        result["calibration_state_sha256"] = binding["state_sha256"]
        result["calibration_binding"] = binding
        result["calibration_source_evidence"] = calibration
    if args.out:
        destination = args.out.absolute()
        if not destination.resolve().is_relative_to(ROOT / ".study") or destination.exists():
            raise StudyError("Planning output must be a new local .study/ file; preserve prior receipts")
        atomic_json(destination, result)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (StudyError, ValueError, OSError, KeyError) as error:
        raise SystemExit(f"Feasibility refused: {error}") from error
