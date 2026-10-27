"""Estimate prospective pilot outcomes; --legacy-proposal reproduces historical hypotheses.

Usage: python3 analyze.py --runs ../runs --phase first [--out ../results] [--seed 2026]

Unit of analysis: one run. End state: after the last feature and its post-feature step (before the
change request). Intervals: 95% bootstrap, resampling whole runs within arm and suite.
H6 uses conservative simultaneous exact-binomial bounds for success differences.
Missing cost accounting is unavailable, never zero or an automatic unit fallback.
H4 comprehension and the full H7 package contrast are not implemented.
"""
import argparse
import csv
import itertools
import json
import math
import os
import random
import statistics as st
from collections import defaultdict
from fractions import Fraction
from pathlib import Path

METRICS = ["mean_ccn", "share_ccn_over_10", "dup_pct", "lint_per_kloc"]


# --------------------------------------------------------------------- loading
def load_runs(runs_dir, phase):
    runs = []
    for metadata_path in sorted(Path(runs_dir).glob("*/run.json")):
        directory = metadata_path.parent
        with metadata_path.open(encoding="utf-8") as metadata:
            meta = json.load(metadata)
        if phase and meta.get("phase") != phase:
            continue
        records_path = directory / "steps.jsonl"
        recs = []
        if records_path.exists():
            with records_path.open(encoding="utf-8") as records:
                for line_number, line in enumerate(records, 1):
                    if not line.strip():
                        continue
                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError:
                        record = {"record_error": f"Invalid JSON at line {line_number}"}
                    if not isinstance(record, dict):
                        record = {"record_error": f"Non-object record at line {line_number}"}
                    recs.append(record)
        runs.append({"dir": str(directory), "meta": meta, "recs": recs})
    return runs


def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v) if math.isfinite(v) else None
    if isinstance(v, dict):
        for k in ("intValue", "doubleValue", "asInt", "asDouble", "value"):
            if k in v:
                return _num(v[k])
    if isinstance(v, str):
        try:
            value = float(v)
            return value if math.isfinite(value) else None
        except ValueError:
            return None
    return None


USAGE_UNITS = ("credits", "tokens", "premium", "seconds")


def step_usage(run_dir, rec):
    """Cost of one agent session, from the Copilot CLI --usage-output-file JSON.

    credits  = totalNanoAiu / 1e9: AI credits, the billed unit (the CLI prints the same figure as "AI Credits")
    tokens   = input + output + cache-read + cache-write tokens (tokenDetails)
    premium  = totalPremiumRequestCost (legacy billing; one per prompt, so not a cost measure on its own)
    seconds  = wall-clock time of the session, measured by the runner
    """
    agent = rec.get("agent")
    agent = agent if isinstance(agent, dict) else {}
    u = agent.get("usage") if isinstance(agent.get("usage"), dict) else {}
    seconds = _num(agent.get("seconds"))
    acc = {"seconds": seconds, "has_usage": bool(u),
           "seconds_complete": seconds is not None and seconds >= 0}
    nano = _num(u.get("totalNanoAiu")) if u else None
    acc["credits"] = nano / 1e9 if nano is not None else None
    td = u.get("tokenDetails")
    td = td if isinstance(td, dict) else {}
    parts = {k: _num(td[k].get("tokenCount")) if isinstance(td.get(k), dict) else None
             for k in ("input", "output", "cache_read", "cache_write")}
    acc.update({f"tokens_{k}": v for k, v in parts.items()})
    acc["tokens_complete"] = all(value is not None and value >= 0 for value in parts.values())
    acc["tokens"] = sum(parts.values()) if acc["tokens_complete"] else None
    acc["premium"] = _num(u.get("totalPremiumRequestCost"))
    acc["premium_complete"] = acc["premium"] is not None and acc["premium"] >= 0
    api_ms = _num(u.get("totalApiDurationMs"))
    acc["api_seconds"] = api_ms / 1000.0 if api_ms is not None else None
    acc["credits_complete"] = (u.get("credits_complete", u.get("aiCreditsStatus") == "complete") is True
                               and nano is not None and nano >= 0)
    models = u.get("modelMetrics")
    acc["models"] = sorted(models) if isinstance(models, dict) else []
    return acc


def cost_of(acc, unit):
    value = _num(acc.get(unit))
    return value if acc.get(f"{unit}_complete") and value is not None and value >= 0 else None


def complete_sum(values):
    """Return a total only when every contributing session is accounted for."""
    values = list(values)
    return sum(values) if values and all(value is not None for value in values) else None


# ------------------------------------------------------------------- per run
def feature_index(value):
    return value if isinstance(value, int) and not isinstance(value, bool) and value > 0 else None


def measurement_of(record):
    measurement = record.get("measure")
    return measurement if isinstance(measurement, dict) else {}


def measured_hidden(record):
    measurement = measurement_of(record)
    hidden = measurement.get("hidden")
    if not isinstance(hidden, dict) or not hidden:
        return None
    if any(not isinstance(test, str) or not isinstance(outcome, str)
           or outcome not in ("passed", "failed", "error", "skipped", "timeout")
           for test, outcome in hidden.items()):
        return None
    if (_num(measurement.get("hidden_total")) != len(hidden)
            or _num(measurement.get("hidden_passed")) != sum(outcome == "passed" for outcome in hidden.values())):
        return None
    return hidden


def measured_row(record, regressions=None):
    measurement = measurement_of(record)
    hidden = measured_hidden(record)
    metrics = measurement.get("metrics")
    metrics = metrics if isinstance(metrics, dict) else {}
    return {"k": feature_index(record.get("k")), "kind": record.get("kind"),
            "pass_rate": 100.0 * sum(outcome == "passed" for outcome in hidden.values()) / len(hidden) if hidden else None,
            "open_regressions": regressions, "nloc_src": _num(metrics.get("nloc_src")),
            "md_words": _num(metrics.get("md_words")), **{name: _num(metrics.get(name)) for name in METRICS}}


def summarise_run(run, cost_unit):
    recs = [record if isinstance(record, dict) else {"record_error": "Non-object step record"}
            for record in run["recs"]]
    arm = run["meta"]["arm"]
    post_kind = {"A": "feature", "B": "consolidation", "C": "review"}[arm]
    scheduled_features = feature_index(run["meta"].get("features"))
    scheduled = set(range(1, scheduled_features + 1)) if scheduled_features is not None else set()
    required_kinds = ("feature",) if arm == "A" else ("feature", post_kind)
    required_steps = [(kind, index) for index in sorted(scheduled) for kind in required_kinds]
    delivery_records = [record for record in recs if record.get("kind") != "change_request"]
    observed_steps = [(record.get("kind"), feature_index(record.get("k"))) for record in delivery_records]
    sequence_complete = (scheduled_features is not None and observed_steps == required_steps
                         and recs[:len(required_steps)] == delivery_records)
    outcomes_complete = sequence_complete and all(measured_hidden(record) is not None for record in delivery_records)
    observed_features = {feature_index(record.get("k")) for record in delivery_records
                         if record.get("kind") == "feature" and feature_index(record.get("k")) is not None}
    by_k = {}
    for record in delivery_records:
        index = feature_index(record.get("k"))
        if record.get("kind") == post_kind and index is not None:
            by_k[index] = record
    missing_post = (scheduled | observed_features) - set(by_k)
    for index in missing_post:
        by_k[index] = {"k": index}
    ks = sorted(by_k)
    series = []
    ever_passed = set()
    open_reg_series = []
    regression_history_complete = True
    regressions_by_k = {}
    last_observed = None
    for rec in delivery_records:
        hidden = measured_hidden(rec)
        regression_history_complete &= hidden is not None
        regressions = None
        if regression_history_complete:
            regressions = sum(hidden.get(test) != "passed" for test in ever_passed)
            ever_passed |= {test for test, outcome in hidden.items() if outcome == "passed"}
        if measurement_of(rec):
            last_observed = measured_row(rec, regressions)
        index = feature_index(rec.get("k"))
        if rec is by_k.get(index):
            regressions_by_k[index] = regressions
    for index in ks:
        regressions = regressions_by_k.get(index)
        open_reg_series.append(regressions)
        series.append(measured_row(by_k[index], regressions))
    usages = [step_usage(run["dir"], r) for r in recs]
    costs = []
    per_feature_cost = defaultdict(list)
    implementation_cost = defaultdict(list)
    delivery_attempts = []
    cr_attempts = []
    end_hidden = measured_hidden(by_k[scheduled_features]) if outcomes_complete else None
    for rec, usage in zip(recs, usages):
        cost = cost_of(usage, cost_unit)
        index = feature_index(rec.get("k"))
        if rec.get("kind") != "change_request":
            costs.append(cost)
            delivery_attempts.append({"kind": rec.get("kind"), "k": rec.get("k"), "cost": cost,
                                      "hidden": measured_hidden(rec)})
            if index is not None:
                per_feature_cost[index].append(cost)
                if rec.get("kind") == "feature":
                    implementation_cost[index].append(cost)
            continue
        hidden = measured_hidden(rec)
        success = None
        if hidden and end_hidden and index == scheduled_features:
            cr_tests = {test: outcome for test, outcome in hidden.items()
                        if Path(test.split("::")[0]).name.startswith("test_cr")}
            passed_features = {test for test, outcome in end_hidden.items() if outcome == "passed"}
            no_regression = all(hidden.get(test) == "passed" for test in passed_features)
            if cr_tests and passed_features <= hidden.keys():
                success = all(outcome == "passed" for outcome in cr_tests.values()) and no_regression
        cr_attempts.append({"success": success, "cost": cost})
    change_request_planned = run["meta"].get("change_request")
    if not isinstance(change_request_planned, bool):
        change_request_planned = None
    cr_success = cr_attempts[0]["success"] if change_request_planned is True and len(cr_attempts) == 1 else None
    cr_cost = complete_sum(attempt["cost"] for attempt in cr_attempts)
    usage_quality = {"sessions": len(usages), "with_usage": sum(u["has_usage"] for u in usages),
                     "credits_complete": sum(u["credits_complete"] for u in usages),
                     "models": sorted({m for u in usages for m in u["models"]}),
                     "credits": sum(u["credits"] for u in usages if u["credits"] is not None),
                     "tokens": sum(u[f"tokens_{part}"] or 0 for u in usages
                                   for part in ("input", "output", "cache_read", "cache_write")),
                     "unavailable_sessions": {unit: sum(cost_of(usage, unit) is None for usage in usages)
                                              for unit in USAGE_UNITS},
                     "records": usages}
    violations = sum(len(r.get("violations") or []) for r in recs)
    leaks = sum(1 for record in recs if isinstance(record.get("agent"), dict) and record["agent"].get("possible_leak"))
    end = dict(series[-1]) if sequence_complete else None
    if end is not None and not outcomes_complete:
        end["pass_rate"] = None
    return {"run_id": run["meta"]["run_id"], "arm": arm, "suite": run["meta"]["suite"], "series": series,
            "scheduled_features": scheduled_features, "sequence_complete": sequence_complete,
            "outcomes_complete": outcomes_complete, "change_request_planned": change_request_planned,
            "finished": run["meta"].get("finished"),
            "record_errors": [{"record": index, "error": record["record_error"]}
                              for index, record in enumerate(recs, 1) if "record_error" in record],
            "missing_features": sorted(scheduled - observed_features),
            "last_observed": last_observed,
            "end": end, "delivery_attempts": delivery_attempts, "observed_delivery_cost": complete_sum(costs),
            "total_cost": complete_sum(costs) if sequence_complete else None,
            "per_feature_cost": {key: complete_sum(values) for key, values in per_feature_cost.items()},
            "per_feature_implementation_cost": {key: complete_sum(values) for key, values in implementation_cost.items()},
            "cr_success": cr_success, "cr_cost": cr_cost, "cr_attempts": cr_attempts,
            "violations": violations, "possible_leaks": leaks, "cost_unit": cost_unit,
            "usage_quality": usage_quality, "missing_post_features": sorted(missing_post),
            "slopes": {name: slope([r["k"] for r in series], [r[name] for r in series]) if sequence_complete else None
                       for name in METRICS + ["open_regressions", "nloc_src"]},
            "regression_auc": complete_sum(open_reg_series) if sequence_complete else None}


def slope(x, y):
    if len(x) != len(y) or any(_num(value) is None for value in x + y):
        return None
    pts = list(zip(x, y))
    if len(pts) < 2:
        return None
    mx = st.mean(a for a, _ in pts)
    my = st.mean(b for _, b in pts)
    sxx = sum((a - mx) ** 2 for a, _ in pts)
    return sum((a - mx) * (b - my) for a, b in pts) / sxx if sxx else None


# ------------------------------------------------------------------ statistics
def boot_effects(groups, statistic, n=10000, seed=2026):
    """Bootstrap named effects by whole run within each arm/suite.

    Compound effects share the same sampled records, preserving covariance.
    Undefined replicates make that effect's interval unavailable, not a
    conditional interval obtained by silently dropping those replicates.
    """
    if n < 2 or not groups:
        return {}, {}
    suites = set(next(iter(groups.values())))
    if not suites or any(set(arm) != suites or any(not rows for rows in arm.values())
                         for arm in groups.values()):
        return {}, {}
    point = statistic(groups)
    if any(len(rows) < 2 for strata in groups.values() for rows in strata.values()):
        return point, {name: (None, None) for name in point}
    draws = {name: [] for name in point}
    unavailable = {name for name, value in point.items() if _num(value) is None}
    if len(unavailable) == len(point):
        return point, {name: (None, None) for name in point}
    rng = random.Random(seed)
    for _ in range(n):
        sample = {arm: {suite: rng.choices(rows, k=len(rows)) for suite, rows in sorted(strata.items())}
                  for arm, strata in sorted(groups.items())}
        for name, value in statistic(sample).items():
            if _num(value) is None:
                unavailable.add(name)
            else:
                draws[name].append(value)
    intervals = {}
    for name, values in draws.items():
        values.sort()
        intervals[name] = ((None, None) if name in unavailable or not values else
                           (values[int(0.025 * n)], values[int(0.975 * n) - 1]))
    return point, intervals


def suite_mean(groups, value=lambda row: row):
    """Equal-suite mean, unavailable if any contributing run lacks the metric."""
    means = []
    for rows in groups.values():
        values = [value(row) for row in rows]
        if not values or any(_num(item) is None for item in values):
            return None
        means.append(st.mean(values))
    return st.mean(means) if means else None


def ratio(numerator, denominator):
    return numerator / denominator if numerator is not None and denominator is not None and denominator > 0 else None


def boot_diff(groups_a, groups_b, stat=st.mean, n=10000, seed=2026):
    """Stratified bootstrap of stat(B) - stat(A); groups_* map suite -> list of values."""
    def estimate(sample):
        if any(_num(value) is None for arm in sample.values() for rows in arm.values() for value in rows):
            return {"difference": None}
        return {"difference": st.mean(stat(sample["B"][suite]) - stat(sample["A"][suite])
                                      for suite in sample["A"])}
    point, intervals = boot_effects({"A": groups_a, "B": groups_b}, estimate, n=n, seed=seed)
    return point.get("difference"), intervals.get("difference", (None, None))


def boot_ratio(groups_a, groups_b, n=10000, seed=2026):
    """Ratio of equal-suite means with stratified whole-run resampling."""
    point, intervals = boot_effects(
        {"A": groups_a, "B": groups_b},
        lambda sample: {"ratio": ratio(suite_mean(sample["B"]), suite_mean(sample["A"]))}, n=n, seed=seed)
    return point.get("ratio"), intervals.get("ratio", (None, None))


def binomial_bounds(successes, total, alpha=0.05):
    """Two-sided Clopper-Pearson bounds by binomial-tail inversion (stdlib)."""
    if total <= 0 or not 0 <= successes <= total:
        return None, None

    def invert(tail, increasing):
        lower, upper = 0.0, 1.0
        for _ in range(80):
            middle = (lower + upper) / 2
            probability = math.fsum(math.comb(total, count) * middle ** count * (1 - middle) ** (total - count)
                                    for count in tail)
            if (probability < alpha / 2) == increasing:
                lower = middle
            else:
                upper = middle
        return (lower + upper) / 2

    lower = invert(range(successes, total + 1), True) if successes else 0.0
    upper = invert(range(successes + 1), False) if successes < total else 1.0
    return lower, upper


def success_difference(groups_a, groups_b):
    """At-least-95% difference bounds from simultaneous exact binomial bounds.

    Bonferroni allocates 0.05 across both arms and every suite. Subtracting
    opposite endpoints and equally averaging suites is conservative; this is
    not a narrow exact interval for a difference. One Bernoulli CR per run is
    required, and the planned small samples can leave very wide intervals.
    """
    suites = sorted(set(groups_a) | set(groups_b))
    if not suites or set(groups_a) != set(groups_b):
        return None, (None, None)
    differences, lowers, uppers = [], [], []
    for suite in suites:
        arm_a, arm_b = groups_a[suite], groups_b[suite]
        if not arm_a or not arm_b or any(not isinstance(value, bool) for value in arm_a + arm_b):
            return None, (None, None)
        lower_a, upper_a = binomial_bounds(sum(arm_a), len(arm_a), alpha=0.05 / (2 * len(suites)))
        lower_b, upper_b = binomial_bounds(sum(arm_b), len(arm_b), alpha=0.05 / (2 * len(suites)))
        differences.append(100 * (Fraction(sum(arm_b), len(arm_b)) - Fraction(sum(arm_a), len(arm_a))))
        lowers.append(100.0 * (lower_b - upper_a))
        uppers.append(100.0 * (upper_b - lower_a))
    return float(st.mean(differences)), (st.mean(lowers), st.mean(uppers))


def perm_p(a, b, max_exact=200000, n=20000, seed=2026):
    """Two-sided permutation test on the difference in means (exact when feasible)."""
    if not a or not b:
        return None
    pooled = a + b
    obs = abs(st.mean(b) - st.mean(a))
    na = len(a)
    total = math.comb(len(pooled), na)
    if total <= max_exact:
        idx = range(len(pooled))
        hits = 0
        for comb in itertools.combinations(idx, na):
            s = set(comb)
            ga = [pooled[i] for i in idx if i in s]
            gb = [pooled[i] for i in idx if i not in s]
            hits += abs(st.mean(gb) - st.mean(ga)) >= obs - 1e-12
        return hits / total
    rng = random.Random(seed)
    hits = 0
    for _ in range(n):
        rng.shuffle(pooled)
        hits += abs(st.mean(pooled[na:]) - st.mean(pooled[:na])) >= obs - 1e-12
    return (hits + 1) / (n + 1)


def a12(a, b):
    """Vargha-Delaney A12: probability that a value from b exceeds one from a."""
    if not a or not b:
        return None
    gt = sum(1 for x in a for y in b if y > x)
    eq = sum(1 for x in a for y in b if y == x)
    return (gt + 0.5 * eq) / (len(a) * len(b))


def verdict(point, ci, right_min, wrong_max):
    """Require a beneficial interval to validate, or a ruled-out minimum to invalidate."""
    if point is None or any(bound is None for bound in ci):
        return "not evaluable"
    if point >= right_min and ci[0] > 0:
        return "validated"
    if ci[1] < wrong_max:
        return "invalidated"
    return "inconclusive"


def has_interval(interval):
    return all(_num(bound) is not None for bound in interval)


def last_third(run):
    """Mean feature-session cost in the final floor(N/3) features, at least one."""
    scheduled_features = feature_index(run.get("scheduled_features"))
    if scheduled_features is None or run.get("sequence_complete") is not True:
        return None
    costs = run.get("per_feature_implementation_cost") or {}
    tail = range(scheduled_features - max(1, scheduled_features // 3) + 1, scheduled_features + 1)
    values = [_num(costs.get(index)) for index in tail]
    total = complete_sum(value if value is not None and value >= 0 else None for value in values)
    return total / len(tail) if total is not None else None


def cr_outcome(run):
    if (run.get("sequence_complete") is not True or run.get("outcomes_complete") is not True
            or run.get("change_request_planned") is not True or len(run.get("cr_attempts", [])) != 1):
        return None
    success = run.get("cr_success")
    return success if isinstance(success, bool) else None


def cr_cost_mean(groups):
    """Successful-attempt cost, retaining failures in the run resampling frame."""
    means = []
    for rows in groups.values():
        if any(cr_outcome(run) is None or run.get("cr_cost") is None for run in rows):
            return None
        costs = [run["cr_cost"] for run in rows if run["cr_success"]]
        if not costs:
            return None
        means.append(st.mean(costs))
    return st.mean(means) if means else None


def cr_accounting(runs, arm):
    arm_runs = [run for run in runs if run["arm"] == arm]
    attempts = [attempt for run in arm_runs for attempt in run.get("cr_attempts", [])]
    succeeded = [attempt for attempt in attempts if attempt["success"] is True]
    failed = [attempt for attempt in attempts if attempt["success"] is False]
    return {"attempted": len(attempts), "succeeded": len(succeeded), "failed": len(failed),
            "unknown": len(attempts) - len(succeeded) - len(failed),
            "runs_with_planned_cr": sum(run.get("change_request_planned") is True for run in arm_runs),
            "runs_with_unplanned_cr": sum(run.get("change_request_planned") is False and bool(run.get("cr_attempts"))
                          for run in arm_runs),
            "runs_with_unknown_cr_plan": sum(run.get("change_request_planned") is None for run in arm_runs),
            "runs_without_cr": sum(not run.get("cr_attempts") for run in arm_runs),
            "runs_with_repeated_cr": sum(len(run.get("cr_attempts", [])) > 1 for run in arm_runs),
            "all_attempt_cost": complete_sum(attempt["cost"] for attempt in attempts),
            "successful_attempt_cost": complete_sum(attempt["cost"] for attempt in succeeded) if succeeded else None,
            "failed_attempt_cost": complete_sum(attempt["cost"] for attempt in failed) if failed else 0.0}


def analyze_hypotheses(runs, seed=2026, n=10000):
    """Evaluate the root H1-H7 contract without dropping incomplete runs."""
    def groups(arm, value=lambda run: run):
        grouped = defaultdict(list)
        for run in runs:
            if run["arm"] == arm:
                grouped[run["suite"]].append(value(run))
        return grouped

    def end_value(run, name):
        if (run.get("sequence_complete") is not True
                or name in ("pass_rate", "open_regressions") and run.get("outcomes_complete") is not True):
            return None
        return (run.get("end") or {}).get(name)

    def slope_value(run, name):
        if (run.get("sequence_complete") is not True
                or name == "open_regressions" and run.get("outcomes_complete") is not True):
            return None
        return (run.get("slopes") or {}).get(name)

    def flat(grouped):
        return [value for values in grouped.values() for value in values]

    paired = {arm: groups(arm) for arm in ("A", "B")}
    pa, pb = groups("A", lambda run: end_value(run, "pass_rate")), groups("B", lambda run: end_value(run, "pass_rate"))
    difference, interval = boot_diff(pa, pb, n=n, seed=seed)
    results = {"H1": {"diff_points": difference, "ci": interval,
                      "p": perm_p(flat(pa), flat(pb), seed=seed) if difference is not None else None,
                      "a12": a12(flat(pa), flat(pb)) if difference is not None else None,
                      "verdict": verdict(difference, interval, 10, 5)}}

    def regression_effects(sample):
        slope_a = suite_mean(sample["A"], lambda run: slope_value(run, "open_regressions"))
        end_a = suite_mean(sample["A"], lambda run: end_value(run, "open_regressions"))
        end_b = suite_mean(sample["B"], lambda run: end_value(run, "open_regressions"))
        end_ratio = ratio(end_b, end_a)
        return {"A_slope": slope_a, "end_ratio": end_ratio,
                "reduction": 1 - end_ratio if end_ratio is not None else None}

    point2, intervals2 = boot_effects(paired, regression_effects, n=n, seed=seed)
    slope_ci = intervals2.get("A_slope", (None, None))
    reduction_ci = intervals2.get("reduction", (None, None))
    h2_verdict = "not evaluable"
    regression_frame_complete = all(run.get("sequence_complete") is True and run.get("outcomes_complete") is True
                                    for run in runs if run["arm"] in ("A", "B"))
    if regression_frame_complete and (has_interval(slope_ci) and slope_ci[1] <= 0
                                     or has_interval(reduction_ci) and reduction_ci[1] < 0.5):
        h2_verdict = "invalidated"
    elif regression_frame_complete and has_interval(slope_ci) and has_interval(reduction_ci):
        if slope_ci[0] > 0 and point2["reduction"] >= 0.5 and reduction_ci[0] > 0:
            h2_verdict = "validated"
        else:
            h2_verdict = "inconclusive"
    results["H2"] = {"A_slope_mean": point2.get("A_slope"), "A_slope_ci": slope_ci,
                     "end_ratio_B_over_A": point2.get("end_ratio"),
                     "end_ratio_ci": intervals2.get("end_ratio", (None, None)),
                     "end_reduction": point2.get("reduction"), "end_reduction_ci": reduction_ci,
                     "auc_ratio_B_over_A": ratio(suite_mean(groups("B", lambda run: run.get("regression_auc")
                                                                     if run.get("sequence_complete") is True else None)),
                                                 suite_mean(groups("A", lambda run: run.get("regression_auc")
                                                                    if run.get("sequence_complete") is True else None))),
                     "verdict": h2_verdict}

    def quality_effects(sample):
        effects = {}
        for name in METRICS:
            slope_a = suite_mean(sample["A"], lambda run, metric=name: slope_value(run, metric))
            slope_b = suite_mean(sample["B"], lambda run, metric=name: slope_value(run, metric))
            complete = slope_a is not None and slope_b is not None
            effects.update({f"{name}:A": slope_a, f"{name}:B": slope_b,
                            f"{name}:benefit": slope_a - slope_b if complete else None,
                            f"{name}:half_margin": slope_a / 2 - slope_b if complete else None})
        return effects

    point3, intervals3 = boot_effects(paired, quality_effects, n=n, seed=seed)
    metrics = {}
    positive = halved = supported = ruled_out = evaluable = 0
    for name in METRICS:
        slope_a, slope_b = point3.get(f"{name}:A"), point3.get(f"{name}:B")
        ci_a = intervals3.get(f"{name}:A", (None, None))
        ci_b = intervals3.get(f"{name}:B", (None, None))
        benefit_ci = intervals3.get(f"{name}:benefit", (None, None))
        half_ci = intervals3.get(f"{name}:half_margin", (None, None))
        is_positive = slope_a is not None and slope_a > 0
        is_halved = is_positive and slope_b is not None and slope_b <= slope_a / 2
        positive += is_positive
        halved += is_halved
        component = "not evaluable"
        if all(has_interval(bounds) for bounds in (ci_a, ci_b, benefit_ci, half_ci)):
            evaluable += 1
            if is_halved and ci_a[0] > 0 and benefit_ci[0] > 0:
                supported += 1
                component = "validated"
            elif ci_a[1] <= 0 or half_ci[1] < 0:
                ruled_out += 1
                component = "invalidated"
            else:
                component = "inconclusive"
        metrics[name] = {"A_slope": slope_a, "B_slope": slope_b, "A_slope_ci": ci_a, "B_slope_ci": ci_b,
                         "benefit": point3.get(f"{name}:benefit"), "benefit_ci": benefit_ci,
                         "half_slope_margin": point3.get(f"{name}:half_margin"), "half_slope_margin_ci": half_ci,
                         "verdict": component}
    results["H3"] = {"metrics": metrics, "A_positive": positive, "B_at_most_half": halved,
                     "interval_supported": supported, "interval_ruled_out": ruled_out,
                     "verdict": "validated" if supported >= 3 else "invalidated" if ruled_out >= 2 else
                     "not evaluable" if evaluable < 4 else "inconclusive"}

    volume_ratio, volume_ci = boot_ratio(groups("A", lambda run: end_value(run, "nloc_src")),
                                        groups("B", lambda run: end_value(run, "nloc_src")), n=n, seed=seed)
    volume_reduction = 1 - volume_ratio if volume_ratio is not None else None
    volume_reduction_ci = (1 - volume_ci[1], 1 - volume_ci[0]) if has_interval(volume_ci) else (None, None)
    volume_verdict = "not evaluable"
    if volume_ratio is not None and has_interval(volume_ci):
        volume_verdict = ("validated" if volume_ratio <= 0.8 and volume_ci[1] < 1 else
                          "invalidated" if volume_ci[0] > 0.9 else "inconclusive")
    results["H4"] = {"nloc_ratio_B_over_A": volume_ratio, "ci": volume_ci,
                     "volume_reduction": volume_reduction, "volume_reduction_ci": volume_reduction_ci,
                     "volume_verdict": volume_verdict,
                     "verdict": "not evaluable", "full_verdict_available": False,
                     "reason": "Blinded comprehension time and accuracy are not supplied or implemented; volume alone is insufficient."}

    def cost_effects(sample):
        total_a = suite_mean(sample["A"], lambda run: run.get("total_cost") if run.get("sequence_complete") is True else None)
        total_b = suite_mean(sample["B"], lambda run: run.get("total_cost") if run.get("sequence_complete") is True else None)
        late_a, late_b = suite_mean(sample["A"], last_third), suite_mean(sample["B"], last_third)
        cost_ratio = ratio(total_b, total_a)
        return {"ratio": cost_ratio, "headroom": 1.5 - cost_ratio if cost_ratio is not None else None,
                "late_A": late_a, "late_B": late_b,
                "late_saving": late_a - late_b if late_a is not None and late_b is not None else None}

    point5, intervals5 = boot_effects(paired, cost_effects, n=n, seed=seed)
    cost_ci = intervals5.get("ratio", (None, None))
    headroom_ci = intervals5.get("headroom", (None, None))
    late_ci = intervals5.get("late_saving", (None, None))
    h5_verdict = "not evaluable"
    if all(has_interval(bounds) for bounds in (cost_ci, headroom_ci, late_ci)):
        if point5["ratio"] <= 1.25 and headroom_ci[0] > 0 and late_ci[0] > 0:
            h5_verdict = "validated"
        elif cost_ci[0] > 1.5 and late_ci[1] <= 0:
            h5_verdict = "invalidated"
        else:
            h5_verdict = "inconclusive"
    results["H5"] = {"cost_ratio_B_over_A": point5.get("ratio"), "ci": cost_ci,
                     "headroom_below_150_percent": point5.get("headroom"), "headroom_ci": headroom_ci,
                     "last_third_A": point5.get("late_A"), "last_third_B": point5.get("late_B"),
                     "late_feature_saving": point5.get("late_saving"), "late_feature_saving_ci": late_ci,
                     "verdict": h5_verdict}

    difference6, success_ci = success_difference(groups("A", cr_outcome), groups("B", cr_outcome))

    def change_cost_effects(sample):
        cost_ratio = ratio(cr_cost_mean(sample["B"]), cr_cost_mean(sample["A"]))
        return {"ratio": cost_ratio, "saving": 1 - cost_ratio if cost_ratio is not None else None}

    point6, intervals6 = boot_effects(paired, change_cost_effects, n=n, seed=seed)
    saving_ci = intervals6.get("saving", (None, None))
    accounting = {arm: cr_accounting(runs, arm) for arm in ("A", "B")}
    h6_verdict, validated_by = "not evaluable", None
    if difference6 is not None and has_interval(success_ci):
        if difference6 >= 20 and success_ci[0] > 0:
            h6_verdict, validated_by = "validated", "success gain"
        elif (has_interval(saving_ci) and point6["saving"] >= 0.25
              and saving_ci[0] > 0 and difference6 >= 0):
            h6_verdict, validated_by = "validated", "cost saving at no lower observed success"
        elif success_ci[1] < 20 and (success_ci[1] < 0 or has_interval(saving_ci) and saving_ci[1] < 0.25):
            h6_verdict = "invalidated"
        elif has_interval(saving_ci):
            h6_verdict = "inconclusive"
    results["H6"] = {"success_A": f"{accounting['A']['succeeded']}/{accounting['A']['attempted']}",
                     "success_B": f"{accounting['B']['succeeded']}/{accounting['B']['attempted']}",
                     "diff_points": difference6, "success_ci": success_ci,
                     "success_component_verdict": verdict(difference6, success_ci, 20, 20),
                     "successful_cost_ratio_B_over_A": point6.get("ratio"),
                     "successful_cost_ratio_ci": intervals6.get("ratio", (None, None)),
                     "cost_saving": point6.get("saving"), "cost_saving_ci": saving_ci,
                     "attempts": accounting, "validated_by": validated_by, "verdict": h6_verdict,
                     "success_interval_method": "Conservative Clopper-Pearson binomial-tail inversion with Bonferroni across both arms and suites; at least 95% simultaneous coverage.",
                     "cost_method": "Whole-run bootstrap of successful-attempt mean costs; failures remain in success counts and are reported separately. Undefined resamples make the cost interval unavailable.",
                     "no_lower_success": "Observed success-rate constraint, not demonstrated statistical non-inferiority.",
                     "limitations": "Small samples can give wide success bounds; missing outcomes, repeated CRs, incomplete costs or no successful attempt in a resample prevent the affected comparison."}

    def package_effects(sample):
        means = {arm: suite_mean(strata, lambda run: end_value(run, "pass_rate")) for arm, strata in sample.items()}
        if any(value is None for value in means.values()):
            return {"B_minus_A": None, "B_minus_C": None, "half_gap_margin": None}
        gap_ba, gap_bc = means["B"] - means["A"], means["B"] - means["C"]
        return {"B_minus_A": gap_ba, "B_minus_C": gap_bc, "half_gap_margin": gap_bc - gap_ba / 2}

    point7, intervals7 = boot_effects({arm: groups(arm) for arm in ("A", "B", "C")}, package_effects, n=n, seed=seed)
    gap_ci = intervals7.get("B_minus_A", (None, None))
    half_gap_ci = intervals7.get("half_gap_margin", (None, None))
    component7 = "not evaluable"
    if has_interval(gap_ci) and has_interval(half_gap_ci):
        if gap_ci[0] <= 0:
            component7 = "inconclusive"
        else:
            component7 = verdict(point7["half_gap_margin"], half_gap_ci, 0, 0)
    results["H7"] = {**point7, "intervals": intervals7, "H1_component_verdict": component7,
                     "H3_component_verdict": "not evaluable", "full_verdict_available": False,
                     "verdict": "not evaluable",
                     "reason": "Full H7 requires both H1 and H3 package comparisons; the H3 B-C half-gap comparison is not implemented."}
    return results


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--phase", default=None)
    ap.add_argument("--legacy-proposal", action="store_true",
                    help="Explicit historical seven-hypothesis proposal, not current pilot inference")
    ap.add_argument("--study-state", type=Path,
                    help="Explicit controller journal for complete all-attempt accounting")
    ap.add_argument("--out", default="results")
    ap.add_argument("--cost-unit", default="credits", choices=USAGE_UNITS,
                    help="credits (AI credits, default), tokens, premium (requests) or seconds")
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()
    if a.seed is None:
        a.seed = 2026 if a.legacy_proposal else 2027
    if not a.legacy_proposal:
        from pilot_analysis import ROLES, analyze_pilot
        from study_report import write_pilot

        raw = load_runs(a.runs, None)
        if a.phase:
            target = ROLES.get(a.phase, "unclassified")
            raw = [run for run in raw if ROLES.get(run["meta"].get("phase"), "unclassified") == target]
        try:
            cells = None
            if a.study_state:
                with a.study_state.open(encoding="utf-8") as source:
                    state = json.load(source)
                phase = state["identity"]["phase"]
                if (a.phase and ROLES.get(phase, "unclassified") != ROLES.get(a.phase, "unclassified")
                        or any(run["meta"].get("phase") != phase for run in raw)):
                    ap.error("Attempt journal phase differs from selected collection")
                cells = state["cells"]
            result = analyze_pilot(raw, seed=a.seed, cost_unit=a.cost_unit, cells=cells)
        except (ValueError, KeyError, TypeError, OSError) as error:
            ap.error(str(error))
        write_pilot(Path(a.out), result)
        print((Path(a.out) / "summary.md").read_text(encoding="utf-8"))
        return
    if a.study_state:
        ap.error("--study-state is for current estimation analysis, not historical proposal reproduction")
    runs = [summarise_run(r, a.cost_unit) for r in load_runs(a.runs, a.phase)]
    os.makedirs(a.out, exist_ok=True)
    unit = a.cost_unit
    arms = sorted({r["arm"] for r in runs})
    counts = ", ".join(f"{x}: {sum(1 for r in runs if r['arm'] == x)}" for x in arms)
    uq = [r["usage_quality"] for r in runs]
    sessions = sum(q["sessions"] for q in uq)
    models = sorted({m for q in uq for m in q["models"]})
    lines = ["# Results", "", f"Runs analysed: {len(runs)} ({counts}); phase: {a.phase or 'all'}; cost unit: {unit}.",
             (f"Recorded agent sessions: {sessions}; with a usage file: {sum(q['with_usage'] for q in uq)}; "
             f"with complete credit accounting: {sum(q['credits_complete'] for q in uq)}; "
             f"recorded AI credits (may be partial): {sum(q['credits'] for q in uq):.2f}; "
             f"recorded tokens (may be partial): {sum(q['tokens'] for q in uq):,.0f}; "
             f"models: {', '.join(models) or 'none recorded'}."),
             (f"Recorded sessions unavailable in the declared {unit} unit: {sum(q['unavailable_sessions'][unit] for q in uq)}. "
             "Missing accounting is unknown, not free; no automatic cost-unit fallback is applied."),
             (f"Runs without complete scheduled delivery: {sum(not run['sequence_complete'] for run in runs)}. "
              "Observed partial data is descriptive, not a final endpoint or scheduled total."), ""]
    res = analyze_hypotheses(runs, seed=a.seed)
    positive, halved = res["H3"]["A_positive"], res["H3"]["B_at_most_half"]
    r4, ci4 = res["H4"]["nloc_ratio_B_over_A"], res["H4"]["ci"]
    r5, ci5 = res["H5"]["cost_ratio_B_over_A"], res["H5"]["ci"]

    def f(x):
        return "n/a" if x is None else f"{x:.2f}" if isinstance(x, float) else str(x)
    lines += ["| Hypothesis | Estimate | Verdict |", "| --- | --- | --- |",
              f"| H1 working software | B-A end-state hidden pass rate {f(res['H1']['diff_points'])} points, 95% CI [{f(res['H1']['ci'][0])}, {f(res['H1']['ci'][1])}], permutation p {f(res['H1']['p'])}, A12 {f(res['H1']['a12'])} | {res['H1']['verdict']} |",
              f"| H2 compounding errors | A open-regression slope {f(res['H2']['A_slope_mean'])}, CI {res['H2']['A_slope_ci']}; end-state reduction {f(res['H2']['end_reduction'])}, CI {res['H2']['end_reduction_ci']} | {res['H2']['verdict']} |",
              f"| H3 internal quality | A slopes positive on {positive}/4; B at most half on {halved}; interval-supported measures {res['H3']['interval_supported']}/4 | {res['H3']['verdict']} |",
              f"| H4 less to review | non-test lines B/A {f(r4)} [{f(ci4[0])}, {f(ci4[1])}]; volume component: {res['H4']['volume_verdict']}; comprehension unavailable | {res['H4']['verdict']} |",
              f"| H5 pays for itself | total cost B/A {f(r5)} [{f(ci5[0])}, {f(ci5[1])}]; headroom CI {res['H5']['headroom_ci']}; late implementation saving {f(res['H5']['late_feature_saving'])}, CI {res['H5']['late_feature_saving_ci']} | {res['H5']['verdict']} |",
              f"| H6 changeability | {res['H6']['success_A']} vs {res['H6']['success_B']} CR successes; gain {f(res['H6']['diff_points'])} points, CI {res['H6']['success_ci']}; successful-attempt cost saving {f(res['H6']['cost_saving'])}, CI {res['H6']['cost_saving_ci']} | {res['H6']['verdict']} |",
              f"| H7 consolidation package vs review-only | B-C {f(res['H7'].get('B_minus_C'))} vs B-A {f(res['H7'].get('B_minus_A'))}; H1 component: {res['H7']['H1_component_verdict']}; H3 comparison unavailable | {res['H7']['verdict']} |", ""]
    methods = {"bootstrap": "95% percentile intervals, 10000 whole-run resamples within arm/suite; equal-suite weighting; compound metrics sampled together; undefined draws are not discarded.",
               "completeness": "All metadata-bearing runs remain in the sampling frame, including absent/empty or malformed step records. Scheduled features and assigned post-steps must be complete and ordered; unknown outcomes and costs remain unavailable for affected comparisons. Observed costs cover recorded sessions only, not missing sessions. CR attempts are reported even when unplanned or not evaluable.",
               "slopes": "Per-run OLS slopes averaged within suite, not the proposed mixed-effects models; reconcile and freeze before execution.",
               "H5": "Delivery total requires every scheduled feature and assigned post-feature session, excluding CR; late implementation cost requires the scheduled last floor(N/3) feature sessions (at least one), independently of missing costs outside that window.",
               "H6_success": res["H6"]["success_interval_method"],
               "H6_cost": res["H6"]["cost_method"],
               "H6_no_lower_success": res["H6"]["no_lower_success"],
               "limits": "Bootstrap intervals are marginal and approximate, with limited small-sample precision; no mixed model or across-hypothesis multiplicity correction is claimed. H4 and full H7 are unavailable."}
    lines += ["## Methods And Limits", ""] + [f"* {name}: {description}" for name, description in methods.items()]
    lines += ["", "CR attempt accounting (failed attempts are never removed from success counts):",
              f"* A: {res['H6']['attempts']['A']}", f"* B: {res['H6']['attempts']['B']}", ""]
    lines += ["## Runs", "", "| Run | Arm | Suite | Scheduled features | Sequence complete | Last observed k/pass rate | End pass rate | Open regressions | Mean CC | Dup % | Observed cost | Delivery cost | CR | Violations | Possible leaks |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in sorted(runs, key=lambda r: r["run_id"]):
        e = r["end"] or {}
        observed = r["last_observed"] or {}
        lines.append(f"| {r['run_id']} | {r['arm']} | {r['suite']} | {f(r['scheduled_features'])} | {'yes' if r['sequence_complete'] else 'no'} | "
                     f"{f(observed.get('k'))}/{f(observed.get('pass_rate'))} | {f(e.get('pass_rate'))} | {f(e.get('open_regressions'))} | {f(e.get('mean_ccn'))} | "
                     f"{f(e.get('dup_pct'))} | {f(r['observed_delivery_cost'])} | {f(r['total_cost'])} | {r['cr_success']} | {r['violations']} | {r['possible_leaks']} |")
    lines += ["", "Small samples: with 3 runs per arm no two-sided rank test can reach p < 0.10; treat intervals, not p-values, as the result.", ""]
    with open(os.path.join(a.out, "summary.md"), "w", encoding="utf-8") as summary_file:
        summary_file.write("\n".join(lines) + "\n")
    with open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8") as summary_file:
        json.dump({"hypotheses": res, "cost_unit": unit, "methods": methods,
                   "runs": [{k: v for k, v in r.items() if k != "series"} for r in runs]},
                  summary_file, indent=1, default=str)
    with open(os.path.join(a.out, "series.csv"), "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        cols = ["k", "pass_rate", "open_regressions", "nloc_src", "md_words"] + METRICS
        w.writerow(["run_id", "arm", "suite"] + cols)
        for r in runs:
            for row in r["series"]:
                w.writerow([r["run_id"], r["arm"], r["suite"]] + [row[c] for c in cols])
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 3, figsize=(11, 3.2))
        colours = {"A": "#c0392b", "B": "#2471a3", "C": "#7d7d7d"}
        for ax, col, title in zip(axes, ["pass_rate", "open_regressions", "mean_ccn"],
                                  ["Cumulative hidden pass rate (%)", "Open regressions", "Mean cyclomatic complexity"]):
            for r in runs:
                ax.plot([x["k"] for x in r["series"]], [x[col] for x in r["series"]], color=colours[r["arm"]], alpha=0.6, lw=1)
            ax.set_title(title, fontsize=9)
            ax.set_xlabel("Feature", fontsize=8)
        for arm, c in colours.items():
            if arm in arms:
                axes[0].plot([], [], color=c, label=f"Arm {arm}")
        axes[0].legend(fontsize=7)
        fig.tight_layout()
        fig.savefig(os.path.join(a.out, "trajectories.png"), dpi=200)
    except ImportError:
        pass
    print("\n".join(lines))


if __name__ == "__main__":
    main()
