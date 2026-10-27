"""Descriptive pilot estimands; historical hypothesis decisions live in analyze.py."""
from __future__ import annotations

import json
import statistics as st
from pathlib import Path

from analyze import (
    boot_diff, complete_sum, cost_of, feature_index, measured_hidden, step_usage, success_difference,
    summarise_run,
)
from contract_panel import accepted, checked_panel

ROOT = Path(__file__).resolve().parents[1]
ROLES = {"pilot": "calibration", "calibration": "calibration",
         "first": "pilot-estimation", "pilot-estimation": "pilot-estimation",
         "dry": "diagnostic"}


def _read_protocol() -> dict:
    """Read the owner's protocol declaration directly; no caching, no study.py import."""
    return json.loads((ROOT / "protocol/pilot-estimation.json").read_text(encoding="utf-8"))


def load_roster() -> dict:
    """Read the authoritative model roster/per-cell counts; independent of study.py."""
    study = _read_protocol()["study"]
    return {"models": list(study["model_roster"]), "runs_per_arm": study["runs_per_arm"],
            "calibration_runs_per_arm": study["calibration_runs_per_arm"]}


def model_identity(meta: dict, roster: list[str]) -> str | None:
    """Return the assigned model slug unchanged; never infer identity from usage telemetry."""
    value = meta.get("assigned_model")
    if value is not None and value not in roster:
        raise ValueError("Unapproved model identity")
    return value


def collection_role(meta: dict) -> str:
    inferred = ROLES.get(meta.get("phase"), "unclassified")
    explicit = meta.get("collection_role")
    if explicit is not None and explicit != inferred:
        raise ValueError("Collection role disagrees with phase; never relabel historical data")
    return inferred


def load_panel() -> dict:
    return checked_panel(ROOT / "protocol/contract-panel.json", ROOT / "suites/s1-retrofit")


def retention(run: dict, panel: dict) -> dict:
    """Track only inherited P-passed unchanged contracts, with paired observations."""
    meta = run["meta"]
    n = feature_index(meta.get("features")) or 0
    post_kind = {"A": "feature", "B": "consolidation", "C": "review"}[meta["arm"]]
    records = {}
    malformed = False
    for record in run["recs"]:
        if not isinstance(record, dict):
            malformed = True
            continue
        malformed |= "record_error" in record
        key = record.get("kind"), record.get("k")
        if key in records:
            malformed = True
        records[key] = record
    contracts = [item for item in panel["contracts"] if item["role"] == "feature"]
    rows, episodes = [], []
    ever, uncertain_acquisition, active, occurrences = set(), set(), {}, {}
    complete = n > 0 and not malformed
    for k in range(1, n + 1):
        eligible = {item["id"]: item for item in contracts
                    if item["unchanged"] is True and item["from_cycle"] <= k <= item["through_cycle"]}
        risk = ever & eligible.keys()
        cohort_complete = not (uncertain_acquisition & eligible.keys())
        f = measured_hidden(records.get(("feature", k), {}))
        p = measured_hidden(records.get((post_kind, k), {}))
        for checkpoint, observed in (("F", f), ("P", p)):
            known = {test: observed.get(test) if observed else None for test in eligible}
            valid = not malformed and all(outcome in ("passed", "failed") for outcome in known.values())
            complete &= valid and cohort_complete
            losses = sum(known[test] == "failed" for test in risk) if valid and cohort_complete else None
            same_cycle = (sum(f.get(test) == "passed" and known[test] == "failed"
                              for test in eligible.keys() - risk)
                          if checkpoint == "P" and valid and f is not None
                          and all(f.get(test) in ("passed", "failed") for test in eligible) else None)
            groups = {}
            for feature in sorted({item["feature"] for item in eligible.values()}):
                ids = {test for test, item in eligible.items() if item["feature"] == feature}
                groups[feature] = {
                    "eligible": len(ids), "ever_passed": len(ids & ever),
                    "never_passed": len(ids - ever) if cohort_complete else None,
                    "currently_passing": sum(known[test] == "passed" for test in ids) if valid else None,
                    "risk_set": len(ids & risk),
                    "open_losses": sum(known[test] == "failed" for test in ids & risk)
                    if valid and cohort_complete else None,
                }
            rows.append({"k": k, "checkpoint": checkpoint, "eligible": len(eligible),
                         "ever_passed": len(ever & eligible.keys()),
                         "never_passed": len(eligible.keys() - ever) if cohort_complete else None,
                         "currently_passing": sum(value == "passed" for value in known.values()) if valid else None,
                         "risk_set": len(risk), "risk_complete": cohort_complete,
                         "open_losses": losses,
                         "density": losses / len(risk) if losses is not None and risk else None,
                         "same_cycle_post_losses": same_cycle, "groups": groups,
                         "observation_complete": valid, "oracle_versions": sorted({
                             item["oracle_version"] for item in eligible.values()})})
            for test in list(active):
                if test not in eligible:
                    active[test]["censored"] = True
                    active.pop(test)
            for test in risk:
                outcome = known[test]
                if malformed or outcome not in ("passed", "failed"):
                    if test in active:
                        active[test]["uncertain"] = True
                    continue
                if outcome == "failed" and test not in active:
                    occurrences[test] = occurrences.get(test, 0) + 1
                    episode = {"contract": test, "feature": eligible[test]["feature"],
                               "onset_cycle": k, "onset_checkpoint": checkpoint,
                               "recovery_cycle": None, "recovery_checkpoint": None,
                               "recurrence": occurrences[test] > 1, "duration_cycles": None,
                               "uncertain": not complete, "censored": True}
                    episodes.append(episode)
                    active[test] = episode
                elif outcome == "passed" and test in active:
                    episode = active.pop(test)
                    episode.update(recovery_cycle=k, recovery_checkpoint=checkpoint, censored=False)
                    if not episode["uncertain"]:
                        episode["duration_cycles"] = k - episode["onset_cycle"]
        if not malformed:
            for test in eligible:
                outcome = p.get(test) if p else None
                if outcome == "passed":
                    ever.add(test)
                    uncertain_acquisition.discard(test)
                elif outcome not in ("passed", "failed") and test not in ever:
                    uncertain_acquisition.add(test)
    return {"rows": rows, "episodes": episodes, "history_complete": complete,
            "panel_accepted": accepted(panel),
            "post_loss_test_cycles": complete_sum(row["open_losses"] for row in rows
                                                  if row["checkpoint"] == "P") if complete else None}


def intervention(meta: dict) -> str:
    evidence = meta.get("intervention") or {}
    if (evidence.get("coverage_complete") is True and evidence.get("evidence")
            and isinstance(evidence.get("assisted"), bool)):
        return "assisted" if evidence["assisted"] else "unassisted"
    return "unknown"


def summarise_pilot(run: dict, panel: dict, cost_unit: str = "credits", cell: dict | None = None) -> dict:
    summary = summarise_run(run, cost_unit)
    history = retention(run, panel)
    summary.update(collection_role=collection_role(run["meta"]), intervention=intervention(run["meta"]),
                   retention=history)
    roster = load_roster()["models"]
    summary["assigned_model"] = model_identity(run["meta"], roster)
    summary["analysis_design"] = run["meta"].get("analysis_design")
    summary["replicate"] = run["meta"].get("replicate")
    n = summary["scheduled_features"] or 0
    expected_features = {item["id"] for item in panel["contracts"]
                         if item["role"] == "feature" and item["from_cycle"] <= n <= item["through_cycle"]}
    post_kind = {"A": "feature", "B": "consolidation", "C": "review"}[summary["arm"]]
    endpoints = [record for record in run["recs"] if isinstance(record, dict)
                 and record.get("kind") == post_kind and record.get("k") == n]
    final_hidden = measured_hidden(endpoints[0]) if len(endpoints) == 1 else None
    final_valid = (summary["sequence_complete"] and bool(expected_features) and final_hidden is not None
                   and set(final_hidden) == expected_features
                   and all(value in ("passed", "failed") for value in final_hidden.values()))
    if summary["end"]:
        summary["end"]["pass_rate"] = (100 * sum(value == "passed" for value in final_hidden.values())
                                       / len(expected_features) if final_valid else None)
    cr_records = [record for record in run["recs"] if isinstance(record, dict)
                  and record.get("kind") == "change_request"]
    cr_hidden = measured_hidden(cr_records[0]) if len(cr_records) == 1 else None
    expected_cr = {item["id"] for item in panel["contracts"] if item["role"] == "cr1"}
    summary["cr_success"] = None
    if (final_valid and summary["change_request_planned"] is True and expected_cr
            and cr_hidden is not None and set(cr_hidden) == expected_cr | expected_features
            and all(value in ("passed", "failed") for value in cr_hidden.values())
            and cr_records[0].get("k") == n and run["recs"][-1] is cr_records[0]):
        retained = {test for test, outcome in final_hidden.items() if outcome == "passed"}
        summary["cr_success"] = all(cr_hidden[test] == "passed" for test in expected_cr | retained)
    if len(summary["cr_attempts"]) == 1:
        summary["cr_attempts"][0]["success"] = summary["cr_success"]
    post = {row["k"]: row for row in history["rows"] if row["checkpoint"] == "P"}
    for row in summary["series"]:
        row["open_regressions"] = post.get(row["k"], {}).get("open_losses")
    if summary["end"]:
        summary["end"]["open_regressions"] = post[summary["scheduled_features"]]["open_losses"]
    summary["regression_auc"] = history["post_loss_test_cycles"]
    # Do not expose the legacy F-ever-passed slopes as current decay estimands.
    summary.pop("slopes", None)
    adjudication = run["meta"].get("cr1_disposition") or {}
    if summary["cr_success"] is None and (summary["change_request_planned"] is True
            and adjudication.get("cause") == "agent" and adjudication.get("terminal") is True
            and adjudication.get("evidence")):
        summary["cr_success"] = False
    summary["cr1_cause"] = adjudication.get("cause", "observed" if summary["cr_success"] is not None else "unknown")
    if cell is not None:
        attempts = cell["attempts"]
        delivery = [item for item in attempts if not item["step"].endswith("-change")]
        cr = [item for item in attempts if item["step"].endswith("-change")]

        def total(items):
            return complete_sum(cost_of(step_usage("", {"agent": item}), cost_unit) for item in items)
        summary["all_attempt_delivery_cost"] = total(delivery)
        summary["all_attempt_cr_cost"] = total(cr)
    else:
        summary["all_attempt_delivery_cost"] = None
        summary["all_attempt_cr_cost"] = None
    if (not summary["cr_attempts"] and (cell is None or not cr)
            and adjudication.get("no_billable_session") is True and adjudication.get("evidence")):
        summary["all_attempt_cr_cost"] = 0.0
    summary["observed_cr_cost"] = summary["cr_cost"]
    summary["attempt_journal_supplied"] = cell is not None
    summary["cr_cost"] = summary["all_attempt_cr_cost"]
    return summary


def journal_cells(raw_runs: list[dict], cells: list[dict]) -> dict:
    if not isinstance(cells, list) or any(not isinstance(cell, dict) for cell in cells):
        raise ValueError("Attempt journal cells must be an allocation list")
    by_id = {cell.get("run_id"): cell for cell in cells}
    if len(by_id) != len(cells) or set(by_id) != {run["meta"]["run_id"] for run in raw_runs}:
        raise ValueError("Attempt journal allocation differs from selected trajectories")
    attempt_ids = []
    for run in raw_runs:
        cell = by_id[run["meta"]["run_id"]]
        identity = ("assigned_model", "analysis_design", "replicate")
        current = any(key in source for source in (cell, run["meta"]) for key in identity)
        if current and (any(key not in source for source in (cell, run["meta"]) for key in identity)
                        or cell["analysis_design"] != "model-stratified-v1"
                        or type(cell["replicate"]) is not int):
            raise ValueError("Attempt journal allocation fields lack complete current model identity")
        keys = ["arm", "features", "change_request"] + (list(identity) if current else [])
        if any(cell.get(key) != run["meta"].get(key) for key in keys):
            raise ValueError("Attempt journal allocation fields differ from run metadata")
        attempts = cell.get("attempts")
        if not isinstance(attempts, list) or any(not isinstance(item, dict)
                or not isinstance(item.get("id"), str) or not isinstance(item.get("step"), str) for item in attempts):
            raise ValueError("Attempt journal entries lack explicit identities/steps")
        ids = {item["id"] for item in attempts}
        attempt_ids += [item["id"] for item in attempts]
        for record in run["recs"]:
            if isinstance(record, dict) and record.get("attempts") and not set(record["attempts"]) <= ids:
                raise ValueError("Measured attempt absent from supplied journal")
        kinds = {record.get("kind") for record in run["recs"] if isinstance(record, dict)}
        if ("change_request" in kinds and not any(item["step"].endswith("-change") for item in attempts)
                or kinds - {"change_request"} and not any(not item["step"].endswith("-change") for item in attempts)):
            raise ValueError("Measured sessions absent from supplied journal")
    if len(set(attempt_ids)) != len(attempt_ids):
        raise ValueError("Duplicate attempt identity in supplied journal")
    return by_id


def _range(values):
    observed = [value for value in values if value is not None]
    return [min(observed), max(observed)] if observed else [None, None]


def analyze_pilot(raw_runs: list[dict], *, panel: dict | None = None, seed: int = 2027,
                  n: int = 10000, cells: list[dict] | None = None, cost_unit: str = "credits") -> dict:
    panel = load_panel() if panel is None else panel
    for run in raw_runs:
        meta = run["meta"]
        identity = ("assigned_model", "analysis_design", "replicate")
        if (any(key in meta for key in identity)
                and (any(key not in meta for key in identity)
                     or meta["analysis_design"] != "model-stratified-v1")):
            raise ValueError("Invalid or partial current model identity; never treat it as historical")
    roles = {collection_role(run["meta"]) for run in raw_runs}
    if len(roles) > 1:
        raise ValueError("Mixed collection roles: analyse calibration, estimation and diagnostics separately")
    role = next(iter(roles), "unclassified")
    by_id = journal_cells(raw_runs, cells) if cells is not None else {}
    runs = [summarise_pilot(run, panel, cost_unit, cell=by_id.get(run["meta"]["run_id"])) for run in raw_runs]
    if len({run["run_id"] for run in runs}) != len(runs):
        raise ValueError("Duplicate trajectory identities")
    stratified = [run for run in runs if run["analysis_design"] == "model-stratified-v1"]
    legacy = [run for run in runs if run["analysis_design"] != "model-stratified-v1"]
    if stratified and legacy:
        raise ValueError("Mixed model-stratified and legacy-identity runs; analyse separately")
    if stratified:
        return _analyze_pilot_model_stratified(stratified, panel, seed, n, role, cost_unit)
    expected = 4 if role == "pilot-estimation" else 1
    frame = (len(runs) == 3 * expected and {run["suite"] for run in runs} == {panel["suite"]}
             and (role != "pilot-estimation" or all(run["scheduled_features"] == 10
                  and run["change_request_planned"] is True for run in runs))
             and all(sum(run["arm"] == arm for run in runs) == expected for arm in "ABC"))
    unassisted = frame and all(run["intervention"] == "unassisted" for run in runs)
    primary = role == "pilot-estimation" and unassisted
    arms = {}
    for arm in "ABC":
        rows = [run for run in runs if run["arm"] == arm]
        denominator = max(expected, len(rows))
        successes = sum(run["cr_success"] is True for run in rows)
        missing = denominator - sum(isinstance(run["cr_success"], bool) for run in rows)
        coverage = [(run["end"] or {}).get("pass_rate") for run in rows]
        costs = [run["all_attempt_cr_cost"] for run in rows]
        succeeded = [run["all_attempt_cr_cost"] for run in rows if run["cr_success"] is True]
        arms[arm] = {"allocated": denominator, "metadata_runs": len(rows),
                     "coverage_values": coverage, "coverage_range": _range(coverage),
                     "successes": successes, "missing": missing,
                     "success_bounds": [successes / denominator, (successes + missing) / denominator],
                     "cr1_all_attempt_cost": complete_sum(costs) if len(rows) == denominator else None,
                     "cr1_successful_only_mean_cost": st.mean(succeeded)
                     if succeeded and missing == 0 and all(value is not None for value in succeeded) else None,
                     "intervention": {label: sum(run["intervention"] == label for run in rows)
                                      for label in ("unassisted", "assisted", "unknown")}}

    def contrast(field, other, available=primary):
        a = [field(run) for run in runs if run["arm"] == other]
        b = [field(run) for run in runs if run["arm"] == "B"]
        point, ci = boot_diff({panel["suite"]: a}, {panel["suite"]: b}, n=n, seed=seed) if available else (None, (None, None))
        return {"difference": point, "ci": ci, "available": point is not None}

    endpoints = {"H1": {}, "H2": {}, "H6": {}, "resources": {}}
    for other in "AC":
        key = f"B-{other}"
        endpoints["H1"][key] = contrast(lambda run: (run["end"] or {}).get("pass_rate"), other)
        endpoints["H2"][key] = {
            "final_P10_count": contrast(lambda run: (run["end"] or {}).get("open_regressions"), other,
                                       primary and accepted(panel)),
            "descriptive_accumulated_test_cycles": contrast(
                lambda run: run["retention"]["post_loss_test_cycles"], other, primary and accepted(panel)),
        }
        a, b = arms[other], arms["B"]
        outcomes_a = [run["cr_success"] for run in runs if run["arm"] == other]
        outcomes_b = [run["cr_success"] for run in runs if run["arm"] == "B"]
        point, ci = (success_difference({panel["suite"]: outcomes_a}, {panel["suite"]: outcomes_b})
                     if primary else (None, (None, None)))
        endpoints["H6"][key] = {"difference_points": point, "ci": ci,
                                "identification_bounds_points": [
                                    100 * (b["success_bounds"][0] - a["success_bounds"][1]),
                                    100 * (b["success_bounds"][1] - a["success_bounds"][0])],
                                "available": point is not None}
        endpoints["resources"][key] = {
            "delivery": contrast(lambda run: run["all_attempt_delivery_cost"], other),
            "cr1": contrast(lambda run: run["all_attempt_cr_cost"], other)}
    description = ("Unassigned diagnostic frame; not study results" if role == "diagnostic"
                   else "Historical unmarked frame; non-current study design")
    return {"mode": "pilot-estimation", "collection_role": role, "cost_unit": cost_unit,
            "design_description": description,
            "allocation_complete": frame, "primary_unassisted_frame_complete": unassisted,
            "primary_estimates_available": primary,
            "panel_accepted": accepted(panel), "endpoints": endpoints, "arms": arms, "runs": runs,
            "methods": {"design": description,
                        "bootstrap": f"{n} whole-run stratified draws; seed {seed}; pointwise 95%; undefined draws retained as unavailable",
                        "H2": "Final P10 open-loss count is primary; accumulated test-cycle losses are descriptive companions",
                        "costs": "All-attempt consumption requires an explicit matching journal; measured-step costs alone are descriptive; empty attempts are not presumed free",
                        "cr1": "97.5% equal-tailed Clopper-Pearson components; opposite endpoints; at least 95% per comparison, not family-wide",
                        "HIR_IDR": "Unavailable without verified attempted-cycle coverage and adjudication; never inferred as zero",
                        "reference_gaps": "Unavailable without accepted compatible reference metrics and complete feature coverage",
                        "H4_H7": "Formal claims deferred; no pilot hypothesis decisions",
                        "missing": "All allocations retained; no complete-case substitution; no last-observed final endpoints"}}


def _analyze_pilot_model_stratified(stratified: list[dict], panel: dict, seed: int, n: int,
                                    role: str, cost_unit: str) -> dict:
    """Model-stratified-v1 primary analysis: per-model only, never pooled, never inferred."""
    roster = load_roster()
    models = roster["models"]
    expected_per_cell = roster["runs_per_arm"] if role == "pilot-estimation" else roster["calibration_runs_per_arm"]
    valid_replicates = {1, 2} if role == "pilot-estimation" else {1}
    for run in stratified:
        if run["assigned_model"] is None or run["assigned_model"] not in models:
            raise ValueError("Unapproved or missing model identity in model-stratified run")
        replicate = run["replicate"]
        if not isinstance(replicate, int) or isinstance(replicate, bool) or replicate not in valid_replicates:
            raise ValueError("Invalid or missing replicate for model-stratified run")
    total_expected = len(models) * 3 * expected_per_cell
    frame = (len(stratified) == total_expected and {run["suite"] for run in stratified} == {panel["suite"]}
             and (role != "pilot-estimation" or all(run["scheduled_features"] == 10
                  and run["change_request_planned"] is True for run in stratified))
             and all(sum(1 for run in stratified if run["arm"] == arm and run["assigned_model"] == model)
                     == expected_per_cell for arm in "ABC" for model in models))
    unassisted = frame and all(run["intervention"] == "unassisted" for run in stratified)
    arms = {arm: {} for arm in "ABC"}
    endpoints = {}
    model_frames = {}
    seen = set()
    for model in models:
        model_runs = [run for run in stratified if run["assigned_model"] == model]
        model_frame = (len(model_runs) == 3 * expected_per_cell
                       and {run["suite"] for run in model_runs} == {panel["suite"]}
                       and (role != "pilot-estimation" or all(run["scheduled_features"] == 10
                            and run["change_request_planned"] is True for run in model_runs))
                       and all(sum(run["arm"] == arm for run in model_runs) == expected_per_cell for arm in "ABC"))
        model_unassisted = model_frame and all(run["intervention"] == "unassisted" for run in model_runs)
        primary = role == "pilot-estimation" and model_unassisted
        model_frames[model] = {"allocation_complete": model_frame,
                               "primary_unassisted_frame_complete": model_unassisted,
                               "primary_estimates_available": primary}
        for arm in "ABC":
            rows = [run for run in model_runs if run["arm"] == arm]
            for run in rows:
                triple = (arm, model, run["replicate"])
                if triple in seen:
                    raise ValueError("Duplicate model identity in (arm, model) cell")
                seen.add(triple)
            if len(rows) > expected_per_cell:
                raise ValueError("Duplicate model identity in (arm, model) cell")
            denominator = max(expected_per_cell, len(rows))
            successes = sum(run["cr_success"] is True for run in rows)
            missing = denominator - sum(isinstance(run["cr_success"], bool) for run in rows)
            coverage = [(run["end"] or {}).get("pass_rate") for run in rows]
            costs = [run["all_attempt_cr_cost"] for run in rows]
            succeeded = [run["all_attempt_cr_cost"] for run in rows if run["cr_success"] is True]
            arms[arm][model] = {"allocated": denominator, "metadata_runs": len(rows),
                         "coverage_values": coverage, "coverage_range": _range(coverage),
                         "successes": successes, "missing": missing,
                         "success_bounds": [successes / denominator, (successes + missing) / denominator],
                         "cr1_all_attempt_cost": complete_sum(costs) if len(rows) == denominator else None,
                         "cr1_successful_only_mean_cost": st.mean(succeeded)
                         if succeeded and missing == 0 and all(value is not None for value in succeeded) else None,
                         "intervention": {label: sum(run["intervention"] == label for run in rows)
                                          for label in ("unassisted", "assisted", "unknown")}}

        def contrast(field, other, available=primary, _runs=model_runs):
            a = [field(run) for run in _runs if run["arm"] == other]
            b = [field(run) for run in _runs if run["arm"] == "B"]
            point, ci = (boot_diff({panel["suite"]: a}, {panel["suite"]: b}, n=n, seed=seed)
                        if available else (None, (None, None)))
            return {"difference": point, "ci": ci, "available": point is not None}

        model_endpoints = {"H1": {}, "H2": {}, "H6": {}, "resources": {}}
        for other in "AC":
            key = f"B-{other}"
            model_endpoints["H1"][key] = contrast(lambda run: (run["end"] or {}).get("pass_rate"), other)
            model_endpoints["H2"][key] = {
                "final_P10_count": contrast(lambda run: (run["end"] or {}).get("open_regressions"), other,
                                           primary and accepted(panel)),
                "descriptive_accumulated_test_cycles": contrast(
                    lambda run: run["retention"]["post_loss_test_cycles"], other, primary and accepted(panel)),
            }
            a, b = arms[other][model], arms["B"][model]
            outcomes_a = [run["cr_success"] for run in model_runs if run["arm"] == other]
            outcomes_b = [run["cr_success"] for run in model_runs if run["arm"] == "B"]
            point, ci = (success_difference({panel["suite"]: outcomes_a}, {panel["suite"]: outcomes_b})
                         if primary else (None, (None, None)))
            model_endpoints["H6"][key] = {"difference_points": point, "ci": ci,
                                    "identification_bounds_points": [
                                        100 * (b["success_bounds"][0] - a["success_bounds"][1]),
                                        100 * (b["success_bounds"][1] - a["success_bounds"][0])],
                                    "available": point is not None}
            model_endpoints["resources"][key] = {
                "delivery": contrast(lambda run: run["all_attempt_delivery_cost"], other),
                "cr1": contrast(lambda run: run["all_attempt_cr_cost"], other)}
        endpoints[model] = model_endpoints
    overall_summary = _read_protocol()["analysis"]["overall_summary"]
    return {"mode": "pilot-estimation", "collection_role": role, "cost_unit": cost_unit,
            "frame": "model-stratified-v1",
            "design_description": "Current model-stratified frame",
            "allocation_complete": frame, "primary_unassisted_frame_complete": unassisted,
            "primary_estimates_available": any(value["primary_estimates_available"] for value in model_frames.values()),
            "model_frames": model_frames,
            "panel_accepted": accepted(panel), "endpoints": endpoints, "arms": arms, "runs": stratified,
            "overall_summary": overall_summary,
            "methods": {"bootstrap": f"{n} whole-run stratified draws; seed {seed}; pointwise 95%; undefined draws retained as unavailable",
                        "H2": "Final P10 open-loss count is primary; accumulated test-cycle losses are descriptive companions",
                        "costs": "All-attempt consumption requires an explicit matching journal; measured-step costs alone are descriptive; empty attempts are not presumed free",
                        "cr1": "97.5% equal-tailed Clopper-Pearson components; opposite endpoints; at least 95% per comparison, not family-wide",
                        "HIR_IDR": "Unavailable without verified attempted-cycle coverage and adjudication; never inferred as zero",
                        "reference_gaps": "Unavailable without accepted compatible reference metrics and complete feature coverage",
                        "H4_H7": "Formal claims deferred; no pilot hypothesis decisions",
                        "missing": "All allocations retained; no complete-case substitution; no last-observed final endpoints",
                        "model_stratification": "Primary eligibility is per full allocated unassisted model frame; "
                                                "model_frames records each model and primary_estimates_available means "
                                                "at least one eligible model. Overall allocation/unassisted flags audit "
                                                "the full design. No pooled/overall numeric endpoint is computed "
                                                "(see overall_summary); never borrow runs across models"}}
