"""Deterministic paper exports and bounded, derived-results-only publication."""
from __future__ import annotations

import csv
import html
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from analyze import (
    METRICS,
    analyze_hypotheses,
    complete_sum,
    cost_of,
    load_runs,
    step_usage,
    summarise_run,
)
from pilot_analysis import analyze_pilot
from arms import BLOCKED_DESIGN
from feasibility import sample_size
from study_io import ROOT, StudyError, atomic_json, command, read_json

EXPORTS = (
    "summary.json", "summary.md", "series.csv", "hypotheses.csv", "intervals.csv",
    "runs.csv", "attempts.csv", "availability.json", "report.md", "trajectories.svg",
    "hypotheses.tex", "trajectories.tex", "provenance.json", "retention.csv", "episodes.csv",
    "cr1.csv", "fidelity.csv", "timing.csv", "planning.json",
)
UNAVAILABLE = {
    "H4": "Formal joint size/accuracy/time claim deferred; comprehension include/defer decision pending.",
    "H7": "Formal dependent half-gap claim deferred, not a threshold to invent.",
    "HIR": "Explicitly excluded from this pilot by owner decision; assistance logging still required, not zero.",
    "IDR": "Explicitly excluded from this pilot by owner decision; help-demand logging still required, not zero.",
    "decay_amendment": "F/P diagnostics implemented; independent panel/oracle acceptance still required.",
    "mixed_effects": "Not claimed for this estimation pilot.",
    "currency": "No verified AI-credit-to-currency conversion.",
    "hard_billing": "CLI credit limits are soft; owner accepts residual overshoot risk with operational buffers. "
                    "No study-specific provider hard cap or guaranteed billed ceiling is claimed.",
    "provider_active_time": "SDK request/dispatch latency and host tool/send wait are not active compute; provider-active/rate-limit components are unknown.",
    "review_repairs": "Only external C annotations with genuine review/diff locators can be observed; file overlap alone proves no repair.",
}


def flat_values(value: dict, prefix: str = "") -> list[tuple[str, object]]:
    """Flatten estimates and interval endpoints without discarding unavailable values."""
    rows = []
    for key, item in sorted(value.items()):
        path = f"{prefix}.{key}" if prefix else key
        if isinstance(item, dict):
            rows.extend(flat_values(item, path))
        elif isinstance(item, (list, tuple)):
            for index, part in enumerate(item):
                if not isinstance(part, (dict, list, tuple)):
                    rows.append((f"{path}.{index}", part))
        else:
            rows.append((path, item))
    return rows


def write_csv(path: Path, columns: list[str], rows: list[dict]) -> None:
    """Write a stable explicit table schema."""
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(rows)
    path.write_text(stream.getvalue(), encoding="utf-8")


def tex(value: object) -> str:
    """Escape all TeX-sensitive characters in generated text."""
    escapes = {"\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$",
               "#": r"\#", "_": r"\_", "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}",
               "^": r"\textasciicircum{}"}
    return "".join(escapes.get(char, char) for char in str(value))


def fmt(value: object) -> str:
    """Expose missing numbers instead of displaying them as zero."""
    if value is None:
        return "unavailable"
    return f"{value:.4g}" if isinstance(value, float) else str(value)


def figure(runs: list[dict], out: Path, *, diagnostic: bool) -> None:
    """Create SVG and a package-free LaTeX picture from the same observed series."""
    title = "STUB DIAGNOSTIC - not study evidence" if diagnostic else "Exploratory trajectories"
    svg = ['<svg xmlns="http://www.w3.org/2000/svg" width="900" height="340" viewBox="0 0 900 340">',
           '<rect width="900" height="340" fill="white"/>',
           f'<text x="30" y="22" font-size="14">{html.escape(title)}</text>']
    latex = [r"\begingroup", r"\setlength{\unitlength}{0.15mm}",
             r"\begin{picture}(900,340)",
             r"\put(30,320){\makebox(0,0)[l]{\scriptsize " + tex(title) + "}}"]
    colours = {"A": "#c0392b", "B": "#2471a3", "C": "#666666", "D": "#956000", "E": "#27643c"}
    for panel, (metric, label) in enumerate((("pass_rate", "Hidden pass rate (%)"),
                                           ("mean_ccn", "Complexity (backend recorded; fidelity)"))):
        left, top, width, height = 60 + 440 * panel, 65, 350, 210
        values = [row[metric] for run in runs for row in run["series"] if row.get(metric) is not None]
        ymax = 100 if metric == "pass_rate" else max(values + [1]) * 1.1
        max_k = max([run.get("scheduled_features") or 1 for run in runs] + [1])
        svg += [f'<text x="{left}" y="48" font-size="12">{label}</text>',
                f'<path d="M{left},{top} V{top+height} H{left+width}" fill="none" stroke="black"/>',
                f'<text x="{left-40}" y="{top+10}" font-size="10">{ymax:.3g}</text>',
                f'<text x="{left-15}" y="{top+height}" font-size="10">0</text>',
                f'<text x="{left}" y="305" font-size="10">Feature 1 to {max_k}</text>']
        latex += [rf"\put({left},292){{\makebox(0,0)[l]{{\scriptsize {tex(label)}}}}}",
                  rf"\put({left},65){{\line(1,0){{{width}}}}}",
                  rf"\put({left},65){{\line(0,1){{{height}}}}}",
                  rf"\put({left},35){{\makebox(0,0)[l]{{\scriptsize Feature 1 to {max_k}; y: 0 to {ymax:.3g}}}}}"]
        for run in runs:
            for row in run["series"]:
                if row.get(metric) is None:
                    continue
                x = left + width * (row["k"] - 1) / max(max_k - 1, 1)
                y = top + height * (1 - row[metric] / ymax)
                svg.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2" fill="{colours[run["arm"]]}"/>')
                latex.append(r"\put({:.2f},{:.2f}){{\makebox(0,0){{\tiny {}}}}}".format(x, 340-y, run["arm"]))
            # Only connect consecutive observed checkpoints; gaps are not interpolated.
            for first, second in zip(run["series"], run["series"][1:]):
                if first.get(metric) is not None and second.get(metric) is not None:
                    x1 = left + width * (first["k"] - 1) / max(max_k - 1, 1)
                    x2 = left + width * (second["k"] - 1) / max(max_k - 1, 1)
                    y1 = top + height * (1 - first[metric] / ymax)
                    y2 = top + height * (1 - second[metric] / ymax)
                    svg.append(f'<path d="M{x1:.2f},{y1:.2f} L{x2:.2f},{y2:.2f}" '
                               f'stroke="{colours[run["arm"]]}" fill="none"/>')
    svg.append('<text x="60" y="330" font-size="11">A: red; B: blue; C: grey; D: ochre; E: green. Missing checkpoints are not imputed.</text></svg>')
    latex += [r"\end{picture}", r"\endgroup"]
    (out / "trajectories.svg").write_text("\n".join(svg) + "\n", encoding="utf-8")
    (out / "trajectories.tex").write_text("\n".join(latex) + "\n", encoding="utf-8")


def historical_budget_provenance(ledger: dict) -> dict:
    """Expose the historical budget hold without claiming a measured charge."""
    provisions = ledger.get("historical_credit_provisions", [])
    return {
        "historical_credit_provisions": provisions,
        "historical_reserved_nano": sum(item["reserved_nano"] for item in provisions),
        "historical_usage_complete": not bool(provisions),
    }


def legacy_export(directory: Path, state: dict, study_id: str) -> None:
    """Project scheduled cells, not attempts, into the existing corrected analyzer."""
    out = directory / "results"
    out.mkdir(exist_ok=True)
    phase = state["identity"]["phase"]
    runs = [summarise_run(run, "credits") for run in load_runs(directory / "runs", phase)]
    if {run["run_id"] for run in runs} != {cell["run_id"] for cell in state["cells"]}:
        raise StudyError("Analyzer sampling frame differs from immutable scheduled cells")
    hypotheses = analyze_hypotheses(runs, seed=state["identity"]["config"]["seed"])
    diagnostic = state["identity"]["smoke"]
    # Never carry the legacy analyzer's component verdicts as confirmatory claims.
    for name, reason in (("H4", UNAVAILABLE["H4"]), ("H7", UNAVAILABLE["H7"])):
        hypotheses[name]["verdict"] = "not evaluable"
        hypotheses[name]["reason"] = reason
    provenance = {"study_id": study_id, "diagnostic_stub": diagnostic,
                  "phase": phase, "source_commit": state["identity"]["commit"],
                  "inputs_sha256": state["identity"]["inputs_sha256"],
                  "seed": state["identity"]["config"]["seed"],
                  "registered_or_frozen_by_runner": False,
                  "inference": "stub diagnostic only" if diagnostic else "exploratory only",
                  "ceiling_nano": state["ledger"]["ceiling_nano"],
                  "prior_nano": state["ledger"]["prior_nano"],
                  **historical_budget_provenance(state["ledger"])}
    atomic_json(out / "provenance.json", provenance)
    atomic_json(out / "availability.json", {"unavailable": UNAVAILABLE,
                                           "diagnostic_stub": diagnostic,
                                           "zero_intervention_inferred": False})
    atomic_json(out / "planning.json", {"status": "historical-proposal-diagnostics-not-v2",
                                                                  "normal_planning": None, "source": provenance})
    hypothesis_rows = []
    interval_rows = []
    for name, result in sorted(hypotheses.items()):
        for field, value in flat_values(result):
            row = {"hypothesis": name, "field": field, "value": value, "available": value is not None,
                   "interpretation": "diagnostic" if diagnostic else "exploratory"}
            hypothesis_rows.append(row)
            parts = field.split(".")
            if "ci" in parts or "intervals" in parts or any(part.endswith("_ci") for part in parts):
                interval_rows.append(row)
    columns = ["hypothesis", "field", "value", "available", "interpretation"]
    write_csv(out / "hypotheses.csv", columns, hypothesis_rows)
    write_csv(out / "intervals.csv", columns, interval_rows)
    series = [dict(run_id=run["run_id"], arm=run["arm"], **row) for run in runs for row in run["series"]]
    write_csv(out / "series.csv", ["run_id", "arm", "k", "kind", "pass_rate", "open_regressions",
                                   "nloc_src", "md_words"] + METRICS, series)
    by_id = {run["run_id"]: run for run in runs}
    dispositions = []
    attempt_rows = []
    for cell in state["cells"]:
        run = by_id[cell["run_id"]]
        end = run.get("end") or {}
        attempted = {attempt["step"] for attempt in cell["attempts"] if attempt["step"].endswith("-feature")}
        usage = [step_usage("", {"agent": attempt}) for attempt in cell["attempts"]]
        dispositions.append({"run_id": cell["run_id"], "arm": cell["arm"], "status": cell["status"],
                             "stop_reason": cell.get("stop_reason"),
                             "scheduled_features": cell["features"], "attempted_cycles": len(attempted),
                             "unattempted_cycles": cell["features"] - len(attempted),
                             "sequence_complete": run["sequence_complete"],
                             "outcomes_complete": run["outcomes_complete"],
                             "end_pass_rate": end.get("pass_rate"), "cr_success": run["cr_success"],
                             "observed_delivery_credits": run["observed_delivery_cost"],
                             "scheduled_delivery_credits": run["total_cost"],
                             "all_attempt_credits_including_unmeasured": complete_sum(
                                 cost_of(item, "credits") for item in usage),
                             "all_attempt_tokens": complete_sum(cost_of(item, "tokens") for item in usage),
                             "all_attempt_seconds": complete_sum(cost_of(item, "seconds") for item in usage),
                             "missing_features": ";".join(map(str, run["missing_features"])),
                             "violations": run["violations"], "possible_leaks": run["possible_leaks"],
                             "HIR": None, "IDR": None})
        for attempt in cell["attempts"]:
            entry = state["ledger"]["entries"][attempt["id"]]
            attempt_rows.append({"run_id": cell["run_id"], "step": attempt["step"],
                                 "attempt_id": attempt["id"], "status": attempt["status"],
                                 "seconds": attempt.get("seconds"), "credits_status": entry["status"],
                                 "cost_included_in_step": attempt.get("cost_included_in_step", False),
                                 "actual_nano": entry["actual_nano"], "reserved_nano": entry["reserved_nano"]})
    atomic_json(out / "summary.json", {"provenance": provenance, "hypotheses": hypotheses,
                                      "cost_unit": "credits", "runs": runs,
                                      "dispositions": dispositions, "attempts": attempt_rows,
                                      "ledger": state["ledger"], "availability": UNAVAILABLE})
    write_csv(out / "runs.csv", list(dispositions[0]), dispositions)
    write_csv(out / "attempts.csv",
              ["run_id", "step", "attempt_id", "status", "seconds", "credits_status",
               "cost_included_in_step", "actual_nano", "reserved_nano"],
              attempt_rows)
    heading = "STUB DIAGNOSTIC: NOT STUDY RESULTS" if diagnostic else "Exploratory study report"
    lines = [f"# {heading}", "", f"Study `{study_id}`; scheduled cells: {len(runs)}; status: {state['status']}.",
             "Attempts are not independent replicates. Failed and zero-step cells remain included.",
             "Costs: AI credits primary; missing accounting is unavailable, not free. No currency conversion.",
             "Intervals: existing 10,000 whole-run stratified bootstrap; H6 conservative simultaneous binomial bounds.",
             "Slopes: per-run OLS, not mixed effects. H4/H7 require owner decisions; no confirmatory verdicts.", "",
             "| Hypothesis | Provisional comparison (diagnostic/exploratory only) |",
             "| --- | --- |"]
    latex = [r"% Generated diagnostic/exploratory comparisons; not confirmatory study verdicts.",
             r"\begin{tabular}{ll}", r"Hypothesis & Provisional comparison \\ \hline"]
    for name, result in sorted(hypotheses.items()):
        lines.append(f"| {name} | {result['verdict']} |")
        latex.append(rf"{tex(name)} & {tex(result['verdict'])} \\")
    latex.append(r"\end{tabular}")
    quantities = [
        ("H1", "Hidden pass B-A (pp)", "diff_points", "ci"),
        ("H2", "A open-loss slope", "A_slope_mean", "A_slope_ci"),
        ("H2", "End loss reduction", "end_reduction", "end_reduction_ci"),
        ("H4", "Non-test lines B/A", "nloc_ratio_B_over_A", "ci"),
        ("H5", "Delivery credits B/A", "cost_ratio_B_over_A", "ci"),
        ("H5", "Late feature saving", "late_feature_saving", "late_feature_saving_ci"),
        ("H6", "CR success B-A (pp)", "diff_points", "success_ci"),
        ("H6", "CR successful cost B/A", "successful_cost_ratio_B_over_A", "successful_cost_ratio_ci"),
    ]
    estimates = [(name, label, hypotheses[name].get(point), hypotheses[name].get(interval))
                 for name, label, point, interval in quantities]
    for metric in METRICS:
        component = hypotheses["H3"]["metrics"][metric]
        for arm in ("A", "B"):
            estimates.append(("H3", f"{metric}: {arm} slope",
                              component[f"{arm}_slope"], component[f"{arm}_slope_ci"]))
    estimates.append(("H7", "Descriptive hidden pass B-C", hypotheses["H7"].get("B_minus_C"),
                      hypotheses["H7"].get("intervals", {}).get("B_minus_C")))
    lines += ["", "| Hypothesis | Quantity | Estimate | 95% interval |", "| --- | --- | --- | --- |"]
    latex += [r"\par\smallskip", r"\begingroup\scriptsize", r"\begin{tabular}{llll}",
              r"Hypothesis & Quantity & Estimate & 95\% interval \\ \hline"]
    for name, label, point, interval in estimates:
        bounds = (f"[{fmt(interval[0])}, {fmt(interval[1])}]"
                  if interval and all(value is not None for value in interval) else "unavailable")
        lines.append(f"| {name} | {label} | {fmt(point)} | {bounds} |")
        latex.append(rf"{tex(name)} & {tex(label)} & {tex(fmt(point))} & {tex(bounds)} \\")
    latex += [r"\end{tabular}", r"\endgroup"]
    (out / "hypotheses.tex").write_text("\n".join(latex) + "\n", encoding="utf-8")
    lines += ["", "## Unavailable measures and gates", ""] + [
        f"- **{name}**: {reason}" for name, reason in UNAVAILABLE.items()]
    lines += ["", "## Run dispositions", "",
              "| Run | Status | Complete sequence | Endpoint (%) | CR1 |",
              "| --- | --- | --- | --- | --- |"]
    lines += [f"| {row['run_id']} | {row['status']} | {row['sequence_complete']} | "
              f"{fmt(row['end_pass_rate'])} | {fmt(row['cr_success'])} |" for row in dispositions]
    lines += ["", "See `hypotheses.csv` / `intervals.csv` for all estimates and interval endpoints;",
              "`runs.csv` / `attempts.csv` for coverage, missingness and all attempt accounting.",
              "Include `hypotheses.tex` and `trajectories.tex` with LaTeX `\\input{...}`;",
              "`trajectories.svg` is a dependency-free figure. No raw logs are published.", ""]
    for name in ("summary.md", "report.md"):
        (out / name).write_text("\n".join(lines), encoding="utf-8")
    figure(runs, out, diagnostic=diagnostic)


def write_pilot(out: Path, result: dict, *, provenance: dict | None = None,
                dispositions: list[dict] | None = None, attempts: list[dict] | None = None) -> None:
    """Write estimation-only outputs through the existing publication boundary."""
    out.mkdir(parents=True, exist_ok=True)
    runs = result["runs"]
    diagnostic = result["collection_role"] == "diagnostic"
    description = result.get("design_description") or (
        "Current model-stratified frame" if result.get("frame") == "model-stratified-v1" else
        "Unassigned diagnostic frame; not study results" if diagnostic else
        "Historical unmarked frame; non-current study design")
    provenance = provenance or {"diagnostic_stub": diagnostic,
                                "collection_role": result["collection_role"],
                                "registered_or_frozen_by_runner": False}
    if result.get("frame") == BLOCKED_DESIGN:
        provenance = dict(provenance, analysis_design=BLOCKED_DESIGN,
                          allocated_trajectories=495 if result["collection_role"] == "pilot-estimation" else 15)
    dispositions = dispositions if dispositions is not None else [
        {"run_id": run["run_id"], "arm": run["arm"],
         "model": run.get("assigned_model"), "replicate": run.get("replicate"),
         "sequence_complete": run["sequence_complete"], "intervention": run["intervention"],
         "end_pass_rate": (run["end"] or {}).get("pass_rate"),
         "cr_success": run["cr_success"], "HIR": None, "IDR": None} for run in runs]
    attempts = attempts or []
    summary = dict(result, design_description=description,
                   provenance=provenance, dispositions=dispositions, attempts=attempts)
    atomic_json(out / "summary.json", summary)
    atomic_json(out / "provenance.json", provenance)
    atomic_json(out / "availability.json", {"unavailable": UNAVAILABLE,
                "panel_accepted": result["panel_accepted"], "diagnostic_stub": diagnostic,
                "primary_estimates_available": result["primary_estimates_available"],
                "zero_intervention_inferred": False})
    atomic_json(out / "planning.json", {"analysis_design": result.get("frame"),
                "normal_planning": sample_size() if result.get("frame") == BLOCKED_DESIGN else None,
                "historical_v1_runs_per_arm_model": 2 if result.get("frame") == "model-stratified-v1" else None,
                "scope": "Never apply prospective 33/cell or five arms to historical data",
                "source": provenance})
    estimates = [dict(hypothesis=name, field=field, value=value,
                      available=value is not None, interpretation="estimate-only")
                 for name, endpoint in result["endpoints"].items()
                 for field, value in flat_values(endpoint)]
    columns = ["hypothesis", "field", "value", "available", "interpretation"]
    write_csv(out / "hypotheses.csv", columns, estimates)
    write_csv(out / "intervals.csv", columns, [row for row in estimates
              if ".ci." in row["field"] or "bounds" in row["field"]])
    write_csv(out / "runs.csv", list(dispositions[0]) if dispositions else ["run_id"], dispositions)
    write_csv(out / "attempts.csv", list(attempts[0]) if attempts else ["run_id", "step", "attempt_id",
              "status", "seconds", "credits_status", "cost_included_in_step", "actual_nano", "reserved_nano"], attempts)
    series = [dict(run_id=run["run_id"], arm=run["arm"], model=run.get("assigned_model"),
                  replicate=run.get("replicate"), **row) for run in runs for row in run["series"]]
    write_csv(out / "series.csv", ["run_id", "arm", "model", "replicate", "k", "kind", "pass_rate",
              "open_regressions", "nloc_src", "md_words"] + METRICS, series)
    paired = []
    episodes = []
    for run in runs:
        for row in run["retention"]["rows"]:
            paired.append({**row, "run_id": run["run_id"], "arm": run["arm"],
                           "model": run.get("assigned_model"), "replicate": run.get("replicate"),
                           "groups": json.dumps(row["groups"], sort_keys=True, separators=(",", ":"))})
        episodes += [dict(run_id=run["run_id"], arm=run["arm"], model=run.get("assigned_model"),
                          replicate=run.get("replicate"), **row)
                     for row in run["retention"]["episodes"]]
    write_csv(out / "retention.csv", ["run_id", "arm", "model", "replicate", "k", "checkpoint", "eligible",
              "ever_passed", "never_passed", "currently_passing", "risk_set", "risk_complete", "open_losses",
              "observed_risk_set", "missing_risk_set", "observed_open_losses", "density", "full_risk_density",
              "same_cycle_post_losses", "observation_complete", "groups"], paired)
    write_csv(out / "episodes.csv", ["run_id", "arm", "model", "replicate", "contract", "feature", "onset_cycle",
              "onset_checkpoint", "recovery_cycle", "recovery_checkpoint", "recurrence",
              "duration_cycles", "uncertain", "censored"], episodes)
    cr_rows = [
        {"run_id": run["run_id"], "arm": run["arm"], "model": run.get("assigned_model"),
         "replicate": run.get("replicate"), "binary_success": run["cr_success"],
         "F9_F10_pre_CR1_stratum": run["pre_cr1_prerequisite_acquisition"],
         "F9_F10_P10_availability": run["pre_cr1_prerequisite_availability"],
         **{f"graded_{key}": value for key, value in run["cr1_graded"].items() if key != "scope"},
         **{f"retained_{key}": value for key, value in run["cr1_retained_losses"].items()}}
        for run in runs]
    write_csv(out / "cr1.csv", list(cr_rows[0]) if cr_rows else ["run_id"], cr_rows)
    fidelity_rows = [
        {"run_id": run["run_id"], "arm": run["arm"], "model": run.get("assigned_model"),
         "replicate": run.get("replicate"), "step": item["step"], "k": item["k"], "kind": item["kind"],
         "classification": "treatment-fidelity-not-independent-efficacy",
         "external_metrics": json.dumps(item["fidelity"], sort_keys=True),
         "visible_change_evidence": json.dumps(item["visible_change_evidence"], sort_keys=True),
         "C_follow_through": json.dumps(run["review_follow_through"], sort_keys=True)}
        for run in runs for item in run["treatment_fidelity"]]
    write_csv(out / "fidelity.csv", list(fidelity_rows[0]) if fidelity_rows else ["run_id"], fidelity_rows)
    timing_rows = [
        {"run_id": run["run_id"], "arm": run["arm"], "model": run.get("assigned_model"),
         "step": item["step"], "observations": json.dumps(item["observed"], sort_keys=True),
         "provider_active_compute_ms": None, "provider_rate_limit_wait_ms": None,
         "scope": "observable SDK/host latency, not active compute"}
        for run in runs for item in run["timing"]]
    write_csv(out / "timing.csv", list(timing_rows[0]) if timing_rows else ["run_id"], timing_rows)
    heading = ("STUB DIAGNOSTIC: NOT STUDY RESULTS" if diagnostic else
               "Prospective five-arm coverage report" if result.get("frame") == BLOCKED_DESIGN else
               "Historical pilot / estimation diagnostics")
    lines = [f"# {heading}", "", f"Design: {description}.",
             f"Collection role: {result['collection_role']}; allocated metadata: {len(runs)}.",
             f"Cost unit: {result['cost_unit']}; no automatic unit fallback or currency conversion.",
             "All allocations retained, including assisted, incomplete and zero-step trajectories.",
             "B-D final coverage is the sole prospective v2 primary comparison; per-model and B-A/B-C/E-B/E-D are descriptive secondary.",
             "Binary CR1 is secondary, not powered by the coverage calculation. Structural metrics are fidelity checks, not independent efficacy.",
             "Each primary contrast requires its full allocated unassisted frame; unknown assistance is not unassisted.",
             "H2 paired F/P values from an unaccepted panel are diagnostics only.",
             "Missing observations/accounting are unavailable, never zero or last-observed final values.",
             "CR1 bounds include all allocations; intervals are per comparison, not family-wide.",
             "", "| Endpoint | Quantity | Estimate / bound |", "| --- | --- | --- |"]
    latex = [r"% Pilot estimates only; not confirmatory.", f"% Design: {description}", r"\begin{tabular}{lll}",
             r"Endpoint & Quantity & Estimate / bound \\ \hline"]
    for row in estimates:
        if isinstance(row["value"], bool):
            continue
        lines.append(f"| {row['hypothesis']} | {row['field']} | {fmt(row['value'])} |")
        latex.append(rf"{tex(row['hypothesis'])} & {tex(row['field'])} & {tex(fmt(row['value']))} \\")
    latex.append(r"\end{tabular}")
    (out / "hypotheses.tex").write_text("\n".join(latex) + "\n", encoding="utf-8")
    lines += ["", "## Methods and unavailable scope", ""]
    lines += [f"* {key}: {value}" for key, value in result["methods"].items()]
    lines += [f"* {key}: {value}" for key, value in UNAVAILABLE.items()]
    if result.get("pooled_within_cell_final_coverage"):
        variance = result["pooled_within_cell_final_coverage"]
        lines += ["", "## Run-level within-cell planning variance", "",
                  f"Pooled variance: {fmt(variance['variance_pp_squared'])} pp squared; "
                  f"SD: {fmt(variance['sd_pp'])} pp; residual df: {variance['df']}; "
                  f"planned complete df: {variance['planned_complete_df']}.",
                  f"Observed {variance['observed_trajectories']}/{variance['allocated_trajectories']} trajectories; "
                  "partial variance is descriptive and never changes the fixed sample."]
    lines += ["", "## All run values and dispositions", "",
              "| Run | Arm | Model | Replicate | Intervention | Coverage (%) | CR1 | Delivery cost | CR1 cost |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    lines += [f"| {run['run_id']} | {run['arm']} | {fmt(run.get('assigned_model'))} | "
              f"{fmt(run.get('replicate'))} | {run['intervention']} | "
              f"{fmt((run['end'] or {}).get('pass_rate'))} | {fmt(run['cr_success'])} | "
              f"{fmt(run['all_attempt_delivery_cost'])} | {fmt(run['all_attempt_cr_cost'])} |" for run in runs]
    lines += ["", "See retention.csv and episodes.csv for paired losses and uncertainty; "
              "cr1.csv includes tests passed/15, lost pre-CR1-passed contracts and observed/missing risk denominators. "
              "F9/F10 conditional strata are selected post-treatment, not randomized causal comparisons. "
              "fidelity.csv/timing.csv preserve observed/unknown coverage. "
              "runs.csv and attempts.csv preserve dispositions/accounting. No raw logs are published.", ""]
    for name in ("summary.md", "report.md"):
        (out / name).write_text("\n".join(lines), encoding="utf-8")
    figure(runs, out, diagnostic=diagnostic)


def export(directory: Path, state: dict, study_id: str) -> None:
    raw = load_runs(directory / "runs", state["identity"]["phase"])
    if {run["meta"]["run_id"] for run in raw} != {cell["run_id"] for cell in state["cells"]}:
        raise StudyError("Analyzer sampling frame differs from immutable scheduled cells")
    result = analyze_pilot(raw, seed=state["identity"]["config"]["seed"], cells=state["cells"])
    dispositions, attempts = [], []
    by_id = {run["run_id"]: run for run in result["runs"]}
    for cell in state["cells"]:
        run = by_id[cell["run_id"]]
        attempted = {item["step"] for item in cell["attempts"] if item["step"].endswith("-feature")}
        dispositions.append({"run_id": cell["run_id"], "arm": cell["arm"], "status": cell["status"],
             "model": run.get("assigned_model"), "replicate": run.get("replicate"),
             "stop_reason": cell.get("stop_reason"), "scheduled_features": cell["features"],
             "attempted_cycles": len(attempted), "unattempted_cycles": cell["features"] - len(attempted),
             "sequence_complete": run["sequence_complete"], "intervention": run["intervention"],
             "end_pass_rate": (run["end"] or {}).get("pass_rate"), "cr_success": run["cr_success"],
             "F9_F10_pre_CR1_stratum": run["pre_cr1_prerequisite_acquisition"],
             "F9_F10_P10_availability": run["pre_cr1_prerequisite_availability"],
             "CR1_passed": run["cr1_graded"]["passed"],
             "CR1_observed_denominator": run["cr1_graded"]["observed_denominator"],
             "CR1_missing_denominator": run["cr1_graded"]["missing_denominator"],
             "all_attempt_delivery_cost": run["all_attempt_delivery_cost"],
             "all_attempt_cr_cost": run["all_attempt_cr_cost"], "HIR": None, "IDR": None})
        for attempt in cell["attempts"]:
            entry = state["ledger"]["entries"][attempt["id"]]
            attempts.append({"run_id": cell["run_id"], "step": attempt["step"],
                             "attempt_id": attempt["id"], "status": attempt["status"],
                             "seconds": attempt.get("seconds"), "credits_status": entry["status"],
                             "cost_included_in_step": attempt.get("cost_included_in_step", False),
                             "actual_nano": entry["actual_nano"], "reserved_nano": entry["reserved_nano"]})
    provenance = {"study_id": study_id, "diagnostic_stub": state["identity"]["smoke"],
                  "phase": state["identity"]["phase"], "collection_role": result["collection_role"],
                  "source_commit": state["identity"]["commit"],
                  "analysis_design": state["identity"].get("analysis_design"),
                  "allocated_trajectories": len(state["cells"]),
                  "primary_comparison": "B-D" if state["identity"].get("analysis_design") == BLOCKED_DESIGN else None,
                  "inputs_sha256": state["identity"]["inputs_sha256"],
                  "seed": state["identity"]["config"]["seed"], "registered_or_frozen_by_runner": False,
                  "inference": "diagnostic" if state["identity"]["smoke"] else "pilot estimates only",
                  "ceiling_nano": state["ledger"]["ceiling_nano"], "prior_nano": state["ledger"]["prior_nano"],
                  **historical_budget_provenance(state["ledger"]),
                  "session_soft_limit_credits": state["identity"]["config"].get("session_soft_limit_credits", 300),
                  "D_feature_soft_limit_credits": 2 * state["identity"]["config"].get("session_soft_limit_credits", 300),
                  "billing_limit_kind": "local admission plus per-session soft caps; not guaranteed billed consumption"}
    write_pilot(directory / "results", result, provenance=provenance, dispositions=dispositions, attempts=attempts)


def check_credentials(text: str) -> None:
    secrets = [value for name, value in os.environ.items()
               if any(marker in name.upper() for marker in ("TOKEN", "SECRET", "PASSWORD", "API_KEY"))
               and len(value) >= 8]
    if any(secret in text for secret in secrets) or re.search(
            r"(?i)(?:github_pat_|gh[pousr]_)[A-Za-z0-9_]{12,}|-----BEGIN [A-Z ]*PRIVATE KEY-----", text):
        raise StudyError("Possible credential in result; publication refused")


def validated_artifacts(directory: Path) -> list[Path]:
    """Only allow bounded generated files, never logs, symlinks or credentials."""
    if directory.is_symlink() or not directory.is_dir():
        raise StudyError("Results directory must be a real directory")
    if {path.name for path in directory.iterdir()} != set(EXPORTS):
        raise StudyError("Results contain missing or non-allowlisted files")
    paths = [directory / name for name in EXPORTS]
    total = 0
    provenance = read_provenance(directory)
    large_design = provenance.get("analysis_design") == BLOCKED_DESIGN
    allocation = provenance.get("allocated_trajectories")
    if large_design and (type(allocation) is not int or allocation not in (15, 495)):
        raise StudyError("v2 result bounds require the exact prospective 15/495 allocation, not a generic cap bypass")
    per_run = {"summary.json": 512 * 1024, "retention.csv": 128 * 1024, "episodes.csv": 128 * 1024,
               "series.csv": 32 * 1024, "fidelity.csv": 64 * 1024, "timing.csv": 64 * 1024,
               "attempts.csv": 32 * 1024}
    for path in paths:
        limit = max(512 * 1024, allocation * per_run.get(path.name, 0)) if large_design else 512 * 1024
        if path.is_symlink() or not path.is_file() or path.stat().st_size > limit:
            raise StudyError("Result is linked, non-regular, or exceeds its source-bound derived-file cap")
        payload = path.read_bytes()
        total += len(payload)
        text = payload.decode("utf-8")
        check_credentials(text)
    aggregate_limit = 512 * 1024 * 1024 if large_design else 4 * 1024 * 1024
    if total > aggregate_limit:
        raise StudyError("Results exceed the bounded aggregate publication cap")
    if provenance.get("registered_or_frozen_by_runner") is not False:
        raise StudyError("Invalid result provenance")
    return paths


def read_provenance(directory: Path) -> dict:
    """Require an object-shaped generated publication provenance."""
    return read_json(directory / "provenance.json")


def package_results(directory: Path, study_id: str) -> Path:
    """Create a deterministic, private ZIP from the existing publication allowlist."""
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", study_id):
        raise StudyError("Invalid shareable-results study ID")
    paths = validated_artifacts(directory)
    if read_provenance(directory).get("study_id") != study_id:
        raise StudyError("Study ID differs from result provenance")
    target = directory.parent / f"{study_id}-results.zip"
    with tempfile.NamedTemporaryFile(dir=directory.parent, prefix="results-", delete=False) as stream:
        temporary = Path(stream.name)
        try:
            with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in paths:
                    info = zipfile.ZipInfo(f"{study_id}/{path.name}", date_time=(1980, 1, 1, 0, 0, 0))
                    info.compress_type = zipfile.ZIP_DEFLATED
                    info.external_attr = 0o600 << 16
                    archive.writestr(info, path.read_bytes())
            stream.flush()
            os.fsync(stream.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
    return target


def publish(directory: Path, study_id: str, root: Path = ROOT) -> str:
    """Commit only fixed results in a temporary worktree, push normally, upsert PR."""
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", study_id):
        raise StudyError("Invalid publication study ID")
    protocol_path = root / "protocol/pilot-estimation.json"
    if protocol_path.is_file() and read_json(protocol_path)["study"].get("analysis_design") == BLOCKED_DESIGN:
        if read_json(protocol_path).get("sharing", {}).get("publication_release_authorized") is not True:
            raise StudyError("v5 publication is pending collection, paper release and explicit owner authorization")
    paths = validated_artifacts(directory)
    provenance = read_provenance(directory)
    if provenance.get("study_id") != study_id:
        raise StudyError("Study ID differs from result provenance")
    source = command(["git", "branch", "--show-current"], cwd=root)
    if not source or source.startswith("results/"):
        raise StudyError("Publish from a named source branch, not detached/results HEAD")
    command(["gh", "auth", "status"], cwd=root)
    branch = f"results/{study_id}"
    existing = subprocess.run(["git", "ls-remote", "--exit-code", "--heads", "origin", branch],
                              cwd=root, capture_output=True, text=True, timeout=60, check=False)
    if existing.returncode not in (0, 2):
        raise StudyError("Cannot inspect remote results branch; no changes pushed")
    source_head = command(["git", "rev-parse", "HEAD"], cwd=root)
    base = source_head
    if existing.returncode == 0:
        command(["git", "fetch", "--quiet", "origin", f"refs/heads/{branch}"], cwd=root)
        base = command(["git", "rev-parse", "FETCH_HEAD"], cwd=root)
    with tempfile.TemporaryDirectory(prefix="mve-results-") as temp:
        worktree = Path(temp) / "checkout"
        command(["git", "worktree", "add", "--quiet", "--detach", str(worktree), base], cwd=root)
        try:
            target = worktree / "results" / study_id
            if (worktree / "results").is_symlink() or target.is_symlink():
                raise StudyError("Remote result destination must not be a symlink")
            if target.exists():
                shutil.rmtree(target)
            target.mkdir(parents=True)
            for path in paths:
                shutil.copyfile(path, target / path.name)
            command(["git", "add", "--", f"results/{study_id}"], cwd=worktree)
            changed = command(["git", "diff", "--cached", "--name-only"], cwd=worktree).splitlines()
            if any(not name.startswith(f"results/{study_id}/") for name in changed):
                raise StudyError("Staged files outside result-only boundary")
            if changed:
                message = (f"data(study): publish {study_id} derived results\n\n"
                           "Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>")
                command(["git", "commit", "--quiet", "-m", message], cwd=worktree)
            proposed = command(["git", "diff", "--name-only", f"{source_head}...HEAD"], cwd=worktree).splitlines()
            if any(not name.startswith(f"results/{study_id}/") for name in proposed):
                raise StudyError("Results branch history contains files outside result-only boundary")
            command(["git", "push", "--quiet", "origin", f"HEAD:refs/heads/{branch}"], cwd=worktree)
        finally:
            command(["git", "worktree", "remove", "--force", str(worktree)], cwd=root)
    prs = json.loads(command(["gh", "pr", "list", "--head", branch, "--base", source,
                              "--state", "open", "--json", "number,url"], cwd=root))
    body = ("Derived artifacts only; no raw logs, credentials or study repositories.\n\n"
            f"Source: `{provenance['source_commit']}`. "
            + ("**Stub diagnostic, not study evidence.**" if provenance["diagnostic_stub"]
               else "**Exploratory results; unresolved measures remain unavailable.**"))
    title = f"data(study): {study_id} results"
    if prs:
        command(["gh", "pr", "edit", str(prs[0]["number"]), "--title", title, "--body", body], cwd=root)
        url = prs[0]["url"]
    else:
        url = command(["gh", "pr", "create", "--head", branch, "--base", source,
                       "--title", title, "--body", body], cwd=root)
    print(f"Results PR: {url}")
    return url
