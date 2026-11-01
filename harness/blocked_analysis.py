"""Prospective run-level, equal-model-weight final-coverage analysis."""
from __future__ import annotations

import math
import statistics as st

from analyze import binomial_bounds, boot_diff, complete_sum
from arms import ARMS, BLOCKED_DESIGN
from contract_panel import accepted
from feasibility import sample_size

COMPARISONS = (("B", "D"), ("B", "A"), ("B", "C"), ("E", "B"), ("E", "D"))


def coverage(run: dict) -> float | None:
    """Use only the final endpoint, not an earlier successful checkpoint."""
    return (run.get("end") or {}).get("pass_rate")


def pooled_within_cell(runs: list[dict], arms: list[str], models: list[str], expected: int) -> dict:
    """Pool run-level residual variance, reporting observed and planned degrees of freedom."""
    residual_ss = 0.0
    df = observed = 0
    cells = []
    for model in models:
        for arm in arms:
            rows = [run for run in runs if run["arm"] == arm and run["assigned_model"] == model]
            values = [coverage(run) for run in rows if coverage(run) is not None]
            observed += len(values)
            cell_df = max(0, len(values) - 1)
            if cell_df:
                residual_ss += sum((value - st.mean(values))**2 for value in values)
                df += cell_df
            cells.append({"arm": arm, "model": model, "allocated": expected,
                          "observed": len(values), "missing": expected - len(values),
                          "df": cell_df})
    variance = residual_ss / df if df else None
    return {
        "variance_pp_squared": variance, "sd_pp": math.sqrt(variance) if variance is not None else None,
        "residual_sum_squares": residual_ss if df else None, "df": df,
        "planned_complete_df": len(arms) * len(models) * (expected - 1),
        "observed_trajectories": observed, "allocated_trajectories": expected * len(arms) * len(models),
        "complete": observed == expected * len(arms) * len(models), "cells": cells,
        "scope": "Run-level within arm/model cells; partial observed variance is descriptive, never a resize rule",
        "feature_checkpoints_are_independent_replicates": False,
    }


def _cell(rows: list[dict], expected: int) -> dict:
    values = [coverage(run) for run in rows]
    successes = sum(run["cr_success"] is True for run in rows)
    observed_cr = sum(isinstance(run["cr_success"], bool) for run in rows)
    missing_cr = expected - observed_cr
    observed_coverage = sum(value is not None for value in values)
    bounds = [successes / expected, (successes + missing_cr) / expected]
    strata = {}
    for label in ("both", "not-both", "unknown"):
        selected = [run for run in rows if run["pre_cr1_prerequisite_acquisition"] == label]
        absent = expected - len(rows) if label == "unknown" else 0
        strata[label] = {
            "metadata_runs": len(selected), "unobserved_allocations": absent,
            "successes": sum(run["cr_success"] is True for run in selected),
            "observed_binary_outcomes": sum(isinstance(run["cr_success"], bool) for run in selected),
            "missing_binary_outcomes": sum(run["cr_success"] is None for run in selected) + absent,
            "graded_passed_observed": [run["cr1_graded"]["passed"] for run in selected],
            "graded_observed_denominators": [run["cr1_graded"]["observed_denominator"] for run in selected],
        }
    return {
        "allocated": expected, "metadata_runs": len(rows),
        "missing_replicates": sorted(set(range(1, expected + 1)) - {run["replicate"] for run in rows}),
        "coverage_values": values, "coverage_observed": observed_coverage,
        "coverage_missing": expected - observed_coverage,
        "coverage_mean": st.mean(values) if len(values) == expected and observed_coverage == expected else None,
        "successes": successes, "missing": missing_cr, "success_bounds": bounds,
        "cr1_binary_clopper_pearson_95": binomial_bounds(successes, expected, alpha=0.05)
            if missing_cr == 0 else (None, None),
        "cr1_interval_scope": "Per arm/model binary success proportion only; no simultaneous/family-wide or coverage-power claim",
        "cr1_prerequisite_strata": strata,
        "cr1_selection_limitation": "F9/F10 acquisition is post-treatment selection; conditional outcomes are descriptive, not causal repair effects",
        "cr1_all_attempt_cost": complete_sum(run["all_attempt_cr_cost"] for run in rows)
            if len(rows) == expected else None,
        "intervention": {label: sum(run["intervention"] == label for run in rows)
                         for label in ("unassisted", "assisted", "unknown")},
    }


def analyze_blocked(runs: list[dict], *, panel: dict, seed: int, n: int, role: str,
                    cost_unit: str, roster: dict) -> dict:
    """Keep the fixed five-arm allocation and primary B-D model blocking explicit."""
    models = roster["models"]
    expected = roster["runs_per_arm"] if role == "pilot-estimation" else roster["calibration_runs_per_arm"]
    if expected != (sample_size()["trajectories_per_arm_model"] if role == "pilot-estimation" else 1):
        raise ValueError("Prospective allocation differs from the computed sample; never shrink after outcomes")
    if role not in ("pilot-estimation", "calibration"):
        raise ValueError("Model-blocked-v2 is an explicit prospective collection identity")
    seen = set()
    for run in runs:
        identity = run["assigned_model"], run["arm"], run["replicate"]
        if (run["assigned_model"] not in models or run["arm"] not in ARMS
                or type(run["replicate"]) is not int or not 1 <= run["replicate"] <= expected):
            raise ValueError("Invalid prospective model/arm/replicate identity")
        if identity in seen:
            raise ValueError("Duplicate prospective model/arm/replicate identity")
        seen.add(identity)
    full = (len(runs) == len(models) * len(ARMS) * expected
            and {run["suite"] for run in runs} == {panel["suite"]}
            and all(run["scheduled_features"] == 10
                    and run["change_request_planned"] is (role == "pilot-estimation") for run in runs))
    arms = {
        arm: {model: _cell([run for run in runs if run["arm"] == arm and run["assigned_model"] == model],
                          expected) for model in models} for arm in ARMS
    }

    def contrast(left: str, right: str, field=coverage, *, primary: bool = False, resource: bool = False) -> dict:
        left_rows = [run for run in runs if run["arm"] == left]
        right_rows = [run for run in runs if run["arm"] == right]
        left_groups = {model: [field(run) for run in left_rows if run["assigned_model"] == model]
                       for model in models}
        right_groups = {model: [field(run) for run in right_rows if run["assigned_model"] == model]
                        for model in models}
        measured = full and (role == "pilot-estimation" or resource) and all(
                                len(values) == expected and all(value is not None for value in values)
                                for groups in (left_groups, right_groups) for values in groups.values())
        unassisted = measured and all(run["intervention"] == "unassisted"
                                     for run in left_rows + right_rows)
        point = (st.mean(st.mean(left_groups[model]) - st.mean(right_groups[model]) for model in models)
                 if measured else None)
        interval = (None, None)
        if role == "pilot-estimation" and unassisted:
            _, interval = boot_diff(right_groups, left_groups, seed=seed, n=n)
        return {
            "difference": point, "ci": interval,
            "available": measured, "primary_eligible": primary and role == "pilot-estimation" and unassisted,
            "all_allocations_retained": True, "content_assistance_compromises_interpretation": measured and not unassisted,
            "scope": "primary equal-model-weight B-D" if primary else "descriptive secondary; no family-wide inference",
        }

    final = {f"{left}-{right}": contrast(left, right, primary=(left, right) == ("B", "D"))
             for left, right in COMPARISONS}
    resources = {
        f"{left}-{right}": {
            "delivery": contrast(left, right, lambda run: run["all_attempt_delivery_cost"], resource=True),
            "cr1": contrast(left, right, lambda run: run["all_attempt_cr_cost"], resource=True),
        } for left, right in COMPARISONS
    }
    retention = {
        f"{left}-{right}": {
            "final_P10_count": contrast(left, right, lambda run: (run["end"] or {}).get("open_regressions")),
            "descriptive_accumulated_test_cycles": contrast(left, right, lambda run: run["regression_auc"]),
        } for left, right in COMPARISONS
    }
    per_model = {}
    for model in models:
        per_model[model] = {
            f"{left}-{right}": {
                "difference": (arms[left][model]["coverage_mean"] - arms[right][model]["coverage_mean"]
                               if role == "pilot-estimation" and arms[left][model]["coverage_mean"] is not None
                               and arms[right][model]["coverage_mean"] is not None else None),
                "scope": "descriptive per-model secondary, not powered by the pooled coverage calculation",
            } for left, right in COMPARISONS
        }
    eligibility = final["B-D"]["primary_eligible"]
    return {
        "mode": "prospective-five-arm", "frame": BLOCKED_DESIGN, "collection_role": role,
        "cost_unit": cost_unit, "design_description": "Prospective fixed 33/cell five-arm model-blocked-v2; historical v1 never pooled",
        "allocation_complete": full, "primary_unassisted_frame_complete": eligibility,
        "primary_estimates_available": eligibility, "panel_accepted": accepted(panel),
        "endpoints": {"H1": final, "H2": retention, "resources": resources,
                      "per_model_secondary": per_model},
        "primary_comparison": "B-D", "arms": arms, "runs": runs,
        "pooled_within_cell_final_coverage": pooled_within_cell(runs, list(ARMS), models, expected)
            if role == "pilot-estimation" else None,
        "pooled_within_cell_B_D_final_coverage": pooled_within_cell(runs, ["B", "D"], models, expected)
            if role == "pilot-estimation" else None,
        "methods": {
            "primary": "Absolute final hidden-contract coverage gain B-D, equal weights 1/3 for the three fixed models; delta=10 percentage points",
            "bootstrap": f"{n} pointwise 95% percentile draws, seed {seed}; whole trajectories within each arm/model; equal model weights; not independent feature checkpoints",
            "planning": "Normal approximation: alpha=.05 two-sided, power=.80, within-cell SD=25pp ASSUMPTION; 33/cell fixed before outcomes, not observed variance",
            "variance": "Pooled within-cell run variance/SD and actual residual degrees of freedom reported; complete five-arm df=480, B/D df=192; never resize from outcomes",
            "secondary": "Per-model coverage; B-A, B-C, E-B/E-D; retained-loss counts/density and resources are descriptive secondary",
            "cr1": "Binary CR1 is secondary and not powered by coverage planning; exact 95% Clopper-Pearson per arm/model when all allocated binary outcomes known; missing allocations retain identification bounds",
            "cr1_graded": "Tests passed/current fixed 15 and pre-CR1-passed contracts lost include observed/missing denominators; no imputation",
            "cr1_selection": "Report both/not-both/unknown F9/F10 pre-CR1 strata; acquisition is post-treatment selection, conditional effects are not causal",
            "fidelity": "Ruff, distinct Lizard complexity/jscpd duplication, suppressions/config changes and external C follow-through annotations are treatment-fidelity checks, not independent efficacy endpoints",
            "timing": "Observable SDK request latency, host wall/send wait and isolated tool roundtrips only; provider-active compute/rate-limit waits remain unknown",
            "missing": "All fixed allocations and assistance dispositions retained. Missing final measurements are unavailable, not failures, previous values or replacement trajectories",
            "costs": "All attempt journals required for complete credits; historical holds and overshoot/missing-accounting stops retained",
        },
    }
