"""Analyse experiment runs against the pre-committed hypotheses.

Usage: python3 analyze.py --runs ../runs --phase first [--out ../results] [--seed 2026] [--comprehension file.csv]

Unit of analysis: one run. End state: after the last feature and its post-feature step (before the
change request). Intervals: 95% bootstrap, resampling whole runs within arm and suite. Exact
permutation p-values are reported for small samples. Verdicts use the HVE vocabulary.
"""
import argparse
import csv
import glob
import itertools
import json
import math
import os
import random
import re
import statistics as st
from collections import defaultdict

METRICS = ["mean_ccn", "share_ccn_over_10", "dup_pct", "lint_per_kloc"]


# --------------------------------------------------------------------- loading
def load_runs(runs_dir, phase):
    runs = []
    for p in sorted(glob.glob(os.path.join(runs_dir, "*", "steps.jsonl"))):
        d = os.path.dirname(p)
        meta = json.load(open(os.path.join(d, "run.json"), encoding="utf-8"))
        if phase and meta.get("phase") != phase:
            continue
        recs = [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]
        runs.append({"dir": d, "meta": meta, "recs": recs})
    return runs


def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, dict):
        for k in ("intValue", "doubleValue", "asInt", "asDouble", "value"):
            if k in v:
                try:
                    return float(v[k])
                except (TypeError, ValueError):
                    return None
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return None
    return None


def _walk_usage(obj, acc, path=""):
    """Collect numeric leaves whose key mentions credits, premium requests or tokens (heuristic)."""
    if isinstance(obj, dict):
        if isinstance(obj.get("key"), str) and "usage" in obj["key"] and "value" in obj:
            n = _num(obj["value"])
            if n is not None:
                acc["otel:" + obj["key"].split(".")[-1]] += n
            return
        for k, v in obj.items():
            p = f"{path}.{k}" if path else k
            n = _num(v) if not isinstance(v, (dict, list)) else None
            if n is not None and re.search(r"credit|premium|token|cost", k, re.I):
                acc[p] += n
            else:
                _walk_usage(v, acc, p)
    elif isinstance(obj, list):
        for v in obj:
            _walk_usage(v, acc, path)


def step_usage(run_dir, rec):
    acc = defaultdict(float)
    if rec.get("agent", {}).get("usage"):
        _walk_usage(rec["agent"]["usage"], acc)
    otel = os.path.join(run_dir, "steps", rec["step"], "otel.jsonl")
    if os.path.exists(otel):
        for line in open(otel, encoding="utf-8", errors="replace"):
            try:
                _walk_usage(json.loads(line), acc)
            except ValueError:
                pass
    acc["seconds"] = rec.get("agent", {}).get("seconds") or 0.0
    return acc


def cost_of(acc, unit):
    if unit == "seconds":
        return acc.get("seconds", 0.0)
    return sum(v for k, v in acc.items() if re.search(unit, k, re.I))


# ------------------------------------------------------------------- per run
def summarise_run(run, cost_unit):
    recs = run["recs"]
    arm = run["meta"]["arm"]
    post_kind = {"A": "feature", "B": "consolidation", "C": "review"}[arm]
    by_k = {}
    for r in recs:
        if r["kind"] == post_kind or (arm == "A" and r["kind"] == "feature"):
            by_k[r["k"]] = r
    ks = sorted(by_k)
    series = []
    ever_passed = set()
    open_reg_series = []
    for k in ks:
        m = by_k[k]["measure"]
        hidden = m["hidden"]
        regressions = [t for t in ever_passed if hidden.get(t) != "passed"]
        open_reg_series.append(len(regressions))
        ever_passed |= {t for t, o in hidden.items() if o == "passed"}
        row = {"k": k, "pass_rate": 100.0 * m["hidden_passed"] / m["hidden_total"] if m["hidden_total"] else 0.0,
               "open_regressions": len(regressions), "nloc_src": m["metrics"]["nloc_src"],
               "md_words": m["metrics"]["md_words"]}
        for name in METRICS:
            row[name] = m["metrics"].get(name)
        series.append(row)
    costs = [cost_of(step_usage(run["dir"], r), cost_unit) for r in recs if r["kind"] != "change_request"]
    per_feature_cost = defaultdict(float)
    for r in recs:
        if r["kind"] != "change_request":
            per_feature_cost[r["k"]] += cost_of(step_usage(run["dir"], r), cost_unit)
    cr = [r for r in recs if r["kind"] == "change_request"]
    cr_success = cr_cost = None
    if cr:
        h = cr[0]["measure"]["hidden"]
        cr_tests = {t: o for t, o in h.items() if t.split("::")[0].startswith("test_cr")}
        feature_tests = {t: o for t, o in h.items() if t not in cr_tests}
        end_hidden = by_k[ks[-1]]["measure"]["hidden"] if ks else {}
        no_regression = all(feature_tests.get(t) == "passed" for t, o in end_hidden.items() if o == "passed")
        cr_success = bool(cr_tests) and all(o == "passed" for o in cr_tests.values()) and no_regression
        cr_cost = cost_of(step_usage(run["dir"], cr[0]), cost_unit)
    violations = sum(len(r.get("violations") or []) for r in recs)
    leaks = sum(1 for r in recs if r.get("agent", {}).get("possible_leak"))
    return {"run_id": run["meta"]["run_id"], "arm": arm, "suite": run["meta"]["suite"], "series": series,
            "end": series[-1] if series else None, "total_cost": sum(costs), "per_feature_cost": dict(per_feature_cost),
            "cr_success": cr_success, "cr_cost": cr_cost, "violations": violations, "possible_leaks": leaks,
            "slopes": {name: slope([r["k"] for r in series], [r[name] for r in series]) for name in METRICS + ["open_regressions", "nloc_src"]},
            "regression_auc": sum(open_reg_series)}


def slope(x, y):
    pts = [(a, b) for a, b in zip(x, y) if b is not None]
    if len(pts) < 2:
        return None
    mx = st.mean(a for a, _ in pts)
    my = st.mean(b for _, b in pts)
    sxx = sum((a - mx) ** 2 for a, _ in pts)
    return sum((a - mx) * (b - my) for a, b in pts) / sxx if sxx else None


# ------------------------------------------------------------------ statistics
def boot_diff(groups_a, groups_b, stat=st.mean, n=10000, seed=2026):
    """Stratified bootstrap of stat(B) - stat(A); groups_* map suite -> list of values."""
    rng = random.Random(seed)
    suites = sorted(set(groups_a) & set(groups_b))
    if not suites:
        return None, (None, None)

    def est(ga, gb):
        return st.mean(stat(gb[s]) - stat(ga[s]) for s in suites)
    point = est(groups_a, groups_b)
    draws = []
    for _ in range(n):
        ga = {s: [rng.choice(groups_a[s]) for _ in groups_a[s]] for s in suites}
        gb = {s: [rng.choice(groups_b[s]) for _ in groups_b[s]] for s in suites}
        draws.append(est(ga, gb))
    draws.sort()
    return point, (draws[int(0.025 * n)], draws[int(0.975 * n) - 1])


def boot_ratio(groups_a, groups_b, n=10000, seed=2026):
    rng = random.Random(seed)
    a = [v for vs in groups_a.values() for v in vs]
    b = [v for vs in groups_b.values() for v in vs]
    if not a or not b or st.mean(a) == 0:
        return None, (None, None)
    draws = []
    for _ in range(n):
        ra = [rng.choice(a) for _ in a]
        rb = [rng.choice(b) for _ in b]
        if st.mean(ra):
            draws.append(st.mean(rb) / st.mean(ra))
    draws.sort()
    return st.mean(b) / st.mean(a), (draws[int(0.025 * len(draws))], draws[int(0.975 * len(draws)) - 1])


def perm_p(a, b, max_exact=200000, n=20000, seed=2026):
    """Two-sided permutation test on the difference in means (exact when feasible)."""
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
    """validated: estimate >= right_min and interval excludes 0; invalidated: interval entirely below wrong_max;
    otherwise inconclusive. (The protocol as drafted treated 'interval includes zero' as invalidation;
    absence of evidence is reported here as inconclusive.)"""
    if point is None or ci[0] is None:
        return "not evaluable"
    if point >= right_min and ci[0] > 0:
        return "validated"
    if ci[1] < wrong_max:
        return "invalidated"
    return "inconclusive"


# ---------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    ap.add_argument("--phase", default=None)
    ap.add_argument("--out", default="results")
    ap.add_argument("--cost-unit", default="credit|premium", help="regex over usage keys, or 'seconds'")
    ap.add_argument("--seed", type=int, default=2026)
    a = ap.parse_args()
    runs = [summarise_run(r, a.cost_unit) for r in load_runs(a.runs, a.phase)]
    runs = [r for r in runs if r["end"]]
    os.makedirs(a.out, exist_ok=True)
    if not runs:
        print("no runs found")
        return
    unit = a.cost_unit
    if all(r["total_cost"] == 0 for r in runs) and unit != "seconds":
        unit = "seconds"
        runs = [summarise_run(r2, unit) for r2 in load_runs(a.runs, a.phase)]
        runs = [r for r in runs if r["end"]]

    def groups(arm, f):
        g = defaultdict(list)
        for r in runs:
            v = f(r)
            if r["arm"] == arm and v is not None:
                g[r["suite"]].append(v)
        return g

    def flat(g):
        return [v for vs in g.values() for v in vs]

    arms = sorted({r["arm"] for r in runs})
    counts = ", ".join(f"{x}: {sum(1 for r in runs if r['arm'] == x)}" for x in arms)
    lines = ["# Results", "", f"Runs analysed: {len(runs)} ({counts}); phase: {a.phase or 'all'}; cost unit: {unit}.", ""]
    res = {}
    # H1
    pa, pb = groups("A", lambda r: r["end"]["pass_rate"]), groups("B", lambda r: r["end"]["pass_rate"])
    d, ci = boot_diff(pa, pb, seed=a.seed)
    res["H1"] = {"diff_points": d, "ci": ci, "p": perm_p(flat(pa), flat(pb)) if flat(pa) and flat(pb) else None,
                 "a12": a12(flat(pa), flat(pb)), "verdict": verdict(d, ci, 10, 5)}
    # H2
    sa = groups("A", lambda r: r["slopes"]["open_regressions"])
    auc_ratio, auc_ci = boot_ratio(groups("A", lambda r: r["regression_auc"]), groups("B", lambda r: r["regression_auc"]), seed=a.seed)
    a_slope = flat(sa)
    res["H2"] = {"A_slope_mean": st.mean(a_slope) if a_slope else None, "auc_ratio_B_over_A": auc_ratio, "auc_ratio_ci": auc_ci}
    res["H2"]["verdict"] = ("validated" if a_slope and st.mean(a_slope) > 0 and auc_ratio is not None and auc_ci[1] is not None and auc_ratio <= 0.5
                            else "inconclusive" if a_slope else "not evaluable")
    # H3
    h3 = {}
    positive = 0
    halved = 0
    for name in METRICS:
        ga = flat(groups("A", lambda r, n=name: r["slopes"][n]))
        gb = flat(groups("B", lambda r, n=name: r["slopes"][n]))
        ma = st.mean(ga) if ga else None
        mb = st.mean(gb) if gb else None
        h3[name] = {"A_slope": ma, "B_slope": mb}
        if ma is not None and ma > 0:
            positive += 1
            if mb is not None and mb <= ma / 2:
                halved += 1
    res["H3"] = {"metrics": h3, "A_positive": positive, "B_at_most_half": halved,
                 "verdict": "validated" if positive >= 3 and halved >= 3 else "invalidated" if positive == 0 else "inconclusive"}
    # H4 (code volume part; comprehension is evaluated separately)
    r4, ci4 = boot_ratio(groups("A", lambda r: r["end"]["nloc_src"]), groups("B", lambda r: r["end"]["nloc_src"]), seed=a.seed)
    res["H4"] = {"nloc_ratio_B_over_A": r4, "ci": ci4,
                 "verdict": "validated (volume only)" if r4 is not None and ci4[1] is not None and r4 <= 0.8 else "inconclusive" if r4 else "not evaluable"}
    # H5
    r5, ci5 = boot_ratio(groups("A", lambda r: r["total_cost"]), groups("B", lambda r: r["total_cost"]), seed=a.seed)

    def last_third(r):
        ks = sorted(r["per_feature_cost"])
        tail = ks[-max(1, len(ks) // 3):]
        return st.mean(r["per_feature_cost"][k] for k in tail)
    lt_a, lt_b = flat(groups("A", last_third)), flat(groups("B", last_third))
    res["H5"] = {"cost_ratio_B_over_A": r5, "ci": ci5, "last_third_A": st.mean(lt_a) if lt_a else None,
                 "last_third_B": st.mean(lt_b) if lt_b else None}
    res["H5"]["verdict"] = ("validated" if r5 is not None and r5 <= 1.25 and lt_a and lt_b and st.mean(lt_b) < st.mean(lt_a)
                            else "invalidated" if r5 is not None and r5 > 1.5 and lt_a and lt_b and st.mean(lt_b) >= st.mean(lt_a)
                            else "inconclusive" if r5 is not None else "not evaluable")
    # H6
    ca = [r["cr_success"] for r in runs if r["arm"] == "A" and r["cr_success"] is not None]
    cb = [r["cr_success"] for r in runs if r["arm"] == "B" and r["cr_success"] is not None]
    if ca and cb:
        diff6 = 100.0 * (sum(cb) / len(cb) - sum(ca) / len(ca))
        res["H6"] = {"success_A": f"{sum(ca)}/{len(ca)}", "success_B": f"{sum(cb)}/{len(cb)}", "diff_points": diff6,
                     "verdict": "validated" if diff6 >= 20 else "inconclusive"}
    else:
        res["H6"] = {"verdict": "not evaluable"}
    # H7
    pc = groups("C", lambda r: r["end"]["pass_rate"])
    if flat(pc) and flat(pa) and flat(pb):
        gap_ba = st.mean(flat(pb)) - st.mean(flat(pa))
        gap_bc = st.mean(flat(pb)) - st.mean(flat(pc))
        res["H7"] = {"B_minus_A": gap_ba, "B_minus_C": gap_bc,
                     "verdict": "validated" if gap_ba > 0 and gap_bc >= 0.5 * gap_ba else "inconclusive"}
    else:
        res["H7"] = {"verdict": "not evaluable"}

    def f(x):
        return "n/a" if x is None else f"{x:.2f}" if isinstance(x, float) else str(x)
    lines += ["| Hypothesis | Estimate | Verdict |", "| --- | --- | --- |",
              f"| H1 working software | B-A end-state hidden pass rate {f(res['H1']['diff_points'])} points, 95% CI [{f(res['H1']['ci'][0])}, {f(res['H1']['ci'][1])}], permutation p {f(res['H1']['p'])}, A12 {f(res['H1']['a12'])} | {res['H1']['verdict']} |",
              f"| H2 compounding errors | A slope of open regressions {f(res['H2']['A_slope_mean'])} per feature; regression load B/A {f(res['H2']['auc_ratio_B_over_A'])} | {res['H2']['verdict']} |",
              f"| H3 internal quality | A slopes positive on {positive}/4; B at most half of A on {halved} | {res['H3']['verdict']} |",
              f"| H4 less to review | non-test lines B/A {f(r4)} [{f(ci4[0])}, {f(ci4[1])}] | {res['H4']['verdict']} |",
              f"| H5 pays for itself | total cost B/A {f(r5)} [{f(ci5[0])}, {f(ci5[1])}]; last third A {f(res['H5']['last_third_A'])}, B {f(res['H5']['last_third_B'])} | {res['H5']['verdict']} |",
              f"| H6 changeability | {res['H6'].get('success_A', 'n/a')} vs {res['H6'].get('success_B', 'n/a')} change requests succeeded | {res['H6']['verdict']} |",
              f"| H7 refactoring, not a second look | {f(res['H7'].get('B_minus_C'))} vs {f(res['H7'].get('B_minus_A'))} | {res['H7']['verdict']} |", ""]
    lines += ["## Runs", "", "| Run | Arm | Suite | End pass rate | Open regressions | Mean CC | Dup % | Cost | CR | Violations | Possible leaks |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in sorted(runs, key=lambda r: r["run_id"]):
        e = r["end"]
        lines.append(f"| {r['run_id']} | {r['arm']} | {r['suite']} | {e['pass_rate']:.1f} | {e['open_regressions']} | {f(e['mean_ccn'])} | "
                     f"{f(e['dup_pct'])} | {r['total_cost']:.1f} | {r['cr_success']} | {r['violations']} | {r['possible_leaks']} |")
    lines += ["", "Small samples: with 3 runs per arm no two-sided rank test can reach p < 0.10; treat intervals, not p-values, as the result.", ""]
    open(os.path.join(a.out, "summary.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    json.dump({"hypotheses": res, "runs": [{k: v for k, v in r.items() if k != "series"} for r in runs]},
              open(os.path.join(a.out, "summary.json"), "w", encoding="utf-8"), indent=1, default=str)
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
