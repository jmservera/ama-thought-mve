---
title: "Whitepaper Empirical Handoff: Multi-Model Five-Arm Consolidation Study and Blinded S1 Judging"
description: "Complete methods, audited tables, mechanistic findings, limitations, and draft whitepaper sections for the 315-trajectory pilot-estimation experiment and post-collection evaluation"
author: "MVE Research Team"
ms.date: 2026-11-13
ms.topic: reference
---

## Executive Overview for the Paper Writer

This document packages the complete empirical record, methodology disclosures, summary tables, mechanistic findings, and draft manuscript text for the five-arm software-consolidation study on suite `S1` (`s1-retrofit`). Every statistic in this handoff is derived directly from the committed artifacts in [pilot-estimation/](pilot-estimation/) and [pilot-estimation-judging/](pilot-estimation-judging/).

### Core Empirical Takeaways

1. Near-ceiling baseline correctness on a ten-feature horizon: Across `313` completed ten-feature trajectories (`5,341 / 5,355` scheduled steps), `claude-sonnet-5.5` and `gemini-4-argon` achieved `99.18%` to `99.74%` mean cumulative hidden-test pass rates at the end of feature delivery (`P10`), with almost zero open regressions (`1` open regression across all `313` completed endpoints). Ten sequential features of clean specification did not induce runaway functional collapse in frontier models when tests ran inside an isolated harness.
2. Consolidation eliminated structural complexity hotspots and lint debt across all three models: Scheduled post-feature consolidation (`Arm B`) drove the share of functions exceeding cyclomatic complexity `10` to `0.00%` in all `63` `Arm B` trajectories across all three models, reduced `claude-sonnet-5.5` lint density by `92%` (`2.26` vs `28.15` warnings per kLOC in `Arm A` and `28.84` in equal-budget `Arm D`), and reduced `gpt-6.1-sol` lint density by `100%` (`0.00` vs `16.04` in `Arm A` and `13.01` in `Arm D`), with only `4%` to `7%` more source lines of code.
3. Consolidation mitigated self-inflicted test over-specification in `gpt-6.1-sol` and yielded positive complete-pair gains across all `63 vs 63` allocated runs: Under strict test-file immutability, `gpt-6.1-sol` frequently over-specified its own `F8` role-visibility allowlist test, blocking `F9` priority ranking on views. In `18` `f09-feature` sessions, `gpt-6.1-sol` halted uncommitted to ask permission to edit that test. Interleaved consolidation (`Arm B`) and explicit repair (`Arm E`) each raised full `100%` `P10` suite completion from `5 / 21` (`Arm A`) and `6 / 21` (`Arm D`) to `12 / 21`. Across all `63 vs 63` complete unassisted trajectories (`3` models x `21` runs), equal-weight `P10` hidden pass-rate differences were `+1.19` percentage points for `B - D` (`95%` bootstrap CI `[+0.10, +2.22]`) and `+1.41` points for `B - A` (`95%` bootstrap CI `[+0.33, +2.45]`), with blinded AI-judged `P10` functional completeness gains of `+0.0577` (`95%` CI `[+0.0007, +0.1097]`) on `B - D` and `+0.0729` (`95%` CI `[+0.0173, +0.1248]`) on `B - A`.
4. Review-only notes (`Arm C`) outperformed code refactoring (`Arm B`) on an architectural extension trap in `gemini-4-argon`: At `CR1` (regional access control and cross-region handoff approval), `gemini-4-argon` dropped to `6 / 21` (`Arm A`), `7 / 21` (`Arm D`), and `8 / 21` (`Arm B`) full hidden-suite success because its `F8` contractor views used a narrow method blocklist that failed to block newly added `CR1` write methods (`57` trajectories failed `test_h08_every_write_is_refused_on_a_view` and `test_hcr1_user_views_are_read_only`). Read-only architectural review (`Arm C`, maintaining `REVIEW.md`) achieved `16 / 21` `CR1` success on `gemini-4-argon`, double `Arm B`.
5. Extra single-session budget (`Arm D`) behaved like baseline `Arm A`, whereas separate post-feature sessions (`Arms B, C, E`) doubled cost: Giving the feature session `45` minutes and `540` soft credits (`Arm D`) instead of `30` minutes and `270` soft credits (`Arm A`) produced almost identical runtime, credit spend, structural metrics, and pass rates because agents exited as soon as visible tests passed. Separate post-feature sessions (`B`, `C`, `E`) roughly doubled delivery AI credits (`2.04x` to `2.25x` in `B` vs `A`) and wall-clock time without lowering `CR1` implementation cost.

### Mandatory Reporting Guardrails for the Manuscript

> [!IMPORTANT]
> Preserve the following four methodological disclosures verbatim in substance whenever citing these numbers in the whitepaper:
> 1. Unregistered five-arm amendment: The original three-arm protocol was registered on OSF (<https://osf.io/ywsrv/overview>), whereas the executed five-arm model-stratified design (`model-stratified-v2-five-arm`, `21` replicates per model-arm cell) was publicly committed in Git prior to execution (`a9d76bb6...` following mid-study resilience recoveries) because the OSF registration could not be amended in place. Present all findings as exploratory estimation, never as preregistered confirmatory hypothesis verdicts.
> 2. Operator intervention attestation and whole-frame vs complete-pair gates: Operator intervention coverage (`intervention-coverage/v1`, SHA-256 `66b09885...`) is owner-attested across all `313` completed trajectories, corroborated by the `5,357 / 5,357` SDK journal audit. This unlocks `claude-sonnet-5.5` (`105 / 105` complete) directly in [pilot-estimation/report.md](pilot-estimation/report.md) and [pilot-estimation/hypotheses.tex](pilot-estimation/hypotheses.tex). Because `gemini-4-argon` and `gpt-6.1-sol` each retain `1` quarantined partial trajectory (`E-15` in `Arm E` and `C-20` in `Arm C`), the automated five-arm gate keeps `primary_estimates_available = false` at whole-study level even for arm pairs (`B - D`, `B - A`) that are `100%` (`63 / 63`) complete and unassisted. Companion complete-pair `seed = 2027` bootstrap CIs and exact full-allocation Manski identification bounds (`[0, 100]%` and `[0, 4]`) are extracted in [pilot-estimation-judging/extracted-contrasts.json](pilot-estimation-judging/extracted-contrasts.json) and Tables 1b and 3b below.
> 3. Incomplete billing holds: `5,303` of `5,357` study attempts have complete billing (`62,052.61` settled AI credits). `54` attempts (`38` native-retry holds, `15` recovery-interrupted holds, `1` quarantine hold) retain `18,900` reserved credits with unknown final provider charges (`783.16` credits certified as a partial lower bound). Report settled delivery/CR1 means over fully accounted trajectories (`n` shown per cell) and state study-wide holds separately; never convert AI credits to currency or treat missing charges as zero.
> 4. Supplementary judging posture: The `12`-scenario workflow replay (`630` endpoints) and blinded `gpt-6-luna` evaluation (`1,252` calls) were designed and run after collection. `gpt-6-luna` shares a provider/model family with `gpt-6.1-sol`. Human calibration (`jmservera`, `90` rows, `16` distinct scorable contexts) used `human-calibration-guidance/v3` authored after initial AI scoring and disclosed AI-assisted triage to focus human inspection on failure/mismatch cases (`review_status = in_progress`).

## Experimental Design and Protocol Summary

### Task Suite and Isolation Architecture

All trajectories implemented the synthetic Python domain package `workbench` from `suites/s1-retrofit` (municipal residential retrofit case management, in-memory standard-library Python). Each trajectory started from the identical skeleton repository (`skeleton/`) containing `Makefile`, `pyproject.toml` (`max-complexity = 10`), `./tcr` (`make test` commit-or-revert wrapper), and `tools/quality.py`.

Features arrived sequentially from `F1` through `F10`, followed by a held-out architectural change request (`CR1`):

* `F1`: Home registration (numeric UPRN, normalized postcode), single-measure case creation (`C-0001`, `C-0002`, ...), filtering, and all-or-nothing CSV import.
* `F2`: Six-stage forward-only case lifecycle (`candidate` through `handed_over`), actor-stamped history, and zero-inclusive stage counts.
* `F3`: Explicit single-owner assignment and pending handoff request/accept/decline workflow.
* `F4`: Backward rework (`return_to`) and post-handover `reopen` with chronological notes and pending-handoff cancellation.
* `F5`: Building-safety hazard holds blocking forward moves and handoffs while permitting rework and role-restricted release.
* `F6`: Resident consent state machine (`not_required`, `required`, `given`, `withdrawn`), installation guard, withdrawal pause, and hold-over-pause exception precedence.
* `F7`: Offered/confirmed `datetime.date` appointments, verified no-access escalation (`> 5` visits), and active-count reset upon `reopen`.
* `F8`: Role-scoped live read-only views (`view_as`), redacting resident `vulnerability` and `contact` fields for `contractor` callers and rejecting all write calls with `NotAllowed`.
* `F9`: Deterministic priority ranking (`rank_cases`, policy `v1` points and ordered reason codes) exposed on both `Workbench` and views, excluding `handed_over` cases.
* `F10`: Tamper-evident SHA-256 hash-chained write audit trail (`audit_log`, `verify_audit`) and role-redacted CSV export (`export_cases_csv`).
* `CR1` (held-out change request): Postcode-prefix regional partitioning (`define_region`, longest-prefix `region_of`), region-scoped user views (`add_user`, `view_for`), and manager-approved cross-region handoffs (`handoff_needs_approval`, `approve_handoff`).

Each agent session executed inside the pinned GitHub Copilot SDK (`1.0.28`) and Copilot CLI (`1.0.105`, protocol `3`) with `reasoningEffort = medium`, config/skill/MCP discovery disabled, built-in and MCP tools excluded, and a single custom tool (`isolated_exec`) backed by a rootless, network-disabled, read-only-root Alpine container (`sha256:61a8adc8e9764d1746e0277c4fb39b27512f972ece2a9c5696246c027e9fe4fb`). Hidden acceptance tests (`127` cumulative feature tests at `P10`; `142` total tests including `15` `CR1` tests after `CR1`) were never mounted into agent containers and were evaluated externally after each step alongside `lizard 1.24.3` (complexity), `jscpd 5.4.1` (duplication, min `50` tokens / `5` lines), and `ruff 0.17.3` (`--isolated --select E,F,W,C90,B,SIM`). Accepted visible test files from earlier steps were enforced as immutable in full (except narrowly scoped literal RHS assertion repairs in `Arm E`).

### Five Experimental Arms and Model Stratification

Three frontier models were crossed factorially with five delivery arms at `21` allocated trajectories per cell (`3 x 5 x 21 = 315` independent trajectories): `claude-sonnet-5.5`, `gemini-4-argon`, and `gpt-6.1-sol`.

| Arm | Structure per feature (`k = 1..10`) | Feature budget | Post-step budget | Architectural artifacts & test rules | Scheduled sessions per run (incl. `CR1`) |
| --- | --- | --- | --- | --- | --- |
| `A` | Feature delivery only | `30` min / `270` soft (`300` reserved) credits | None | Visible tests immutable; new tests in new files | `11` |
| `B` | Feature + TCR consolidation | `30` min / `270` soft credits | `15` min / `270` soft credits | Refactor under `./tcr` to quality budget (`CCN <= 10`, `dup < 3%`, `0` lint warnings), add pinning tests in new files, rewrite `DESIGN.md` | `21` |
| `C` | Feature + read-only review | `30` min / `270` soft credits | `15` min / `270` soft credits | Cannot modify `src/` or `tests/`; writes handover `REVIEW.md` only | `21` |
| `D` | Equal-budget uninterrupted feature | `45` min / `540` soft (`600` reserved) credits | None | Matches `B`/`C`/`E` nominal `45`-minute per-feature time allowance in a single session; no `DESIGN.md`/`REVIEW.md` | `11` |
| `E` | Feature + visible-spec repair | `30` min / `270` soft credits | `15` min / `270` soft credits | Fix defects observable from visible specs/tests (no hidden-test access); may revise literal RHS expected values in agent-authored tests with recorded spec quote | `21` |

In all five arms, `CR1` received one `45`-minute session (`270` soft / `300` reserved credits). Across `315` trajectories (`126` single-stage runs in `A, D` at `11` steps + `189` two-stage runs in `B, C, E` at `21` steps), the full allocation comprised `5,355` scheduled steps.

## Collection Completeness, Resilience, and Resource Ledger

* Trajectory and step completion: `313 / 315` (`99.37%`) trajectories completed all scheduled delivery and `CR1` steps, yielding `5,341 / 5,355` (`99.74%`) measured steps.
* Quarantined trajectories (`2 / 315`): Under the prospective `study-resilience-policy/v1` supervisor (which quarantines unfinished unknown-charge transport failures rather than replaying uncertain state or halting unrelated trajectories), two trajectories remained incomplete and were retained in all denominators:
  * `pilot-estimation-gemini-4-argon-E-15`: `10 / 21` steps measured (`11` steps unattempted after an HTTP stream timeout interruption).
  * `pilot-estimation-gpt-6.1-sol-C-20`: `18 / 21` steps measured (`3` steps unattempted, including `P10` and `CR1`, after a WebSocket fallback transport interruption).
* Hidden-test attribution audit: An immutable read-only re-evaluation (`analysis-adjudications/v1`) verified `87` step records (`98` individual test outcomes) where candidate code raised uncaught domain/runtime exceptions that the raw runner initially labeled `error`, reclassifying proven candidate failures to `failed` without altering original metrics or rerunning agents. Two `CR1` trajectories (`gpt-6.1-sol-B-08` and `gpt-6.1-sol-C-14`) retained an unadjudicated `error` on `test_f09_hidden::test_h09_same_state_same_ranking` and are conservatively treated as missing (`null`) in `CR1` success counts, widening their identification bounds.
* Study credit ledger (`5,357` total attempts):
  * `5,303` attempts settled with complete telemetry totaling `62,052.6069` AI credits.
  * `54` attempts had incomplete provider billing (`38` `retry_hold` where native WebSocket retries succeeded after an unaccounted reset, `15` historical `recovery_hold` interruptions across source-pinned operational recoveries, and `1` `quarantine_hold`), holding `18,900.0` nominal reserved credits (`783.16186` credits certified as a partial lower bound on the successful retry turns).

## Primary and Secondary Benchmark Results (`H1`, `H2`, `H6`)

### Table 1: End-of-Delivery Correctness (`P10`), Regression Retention (`H2`), and Change-Request Absorbability (`CR1`)

All `21` allocated trajectories per model-arm cell are retained. `P10` hidden pass rate is the percentage of `127` hidden feature acceptance tests passing after `F10` (and its post-step in `B, C, E`). `Open Regressions` counts previously `P`-passing unchanged contracts from `protocol/contract-panel.json` failing at `P10`; `Loss Cycles` sums open contract losses across `P1..P10`. `CR1 Bounds` give the exact allocation-wide success-rate interval `[successes / 21, (successes + missing) / 21]`.

| Model | Arm | Complete / Alloc | `P10` Pass Mean (%) | `P10` Pass Median (%) | `P10` Pass Min (%) | `P10` `100%` Runs | `P10` Open Regressions (Runs > 0) | Mean Loss Cycles (`P1..P10`) | `CR1` Pass / Fail / Miss | `CR1` Success Bounds (%) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `claude-sonnet-5.5` | `A` | `21 / 21` | `99.44` | `100.00` | `96.85` | `12 / 21` | `0.000` (`0`) | `0.000` | `21 / 0 / 0` | `[100.0, 100.0]` |
| `claude-sonnet-5.5` | `B` | `21 / 21` | `99.66` | `100.00` | `98.43` | `13 / 21` | `0.000` (`0`) | `0.000` | `21 / 0 / 0` | `[100.0, 100.0]` |
| `claude-sonnet-5.5` | `C` | `21 / 21` | `99.59` | `100.00` | `97.64` | `12 / 21` | `0.000` (`0`) | `0.000` | `21 / 0 / 0` | `[100.0, 100.0]` |
| `claude-sonnet-5.5` | `D` | `21 / 21` | `99.40` | `100.00` | `96.85` | `11 / 21` | `0.000` (`0`) | `0.000` | `20 / 1 / 0` | `[95.2, 95.2]` |
| `claude-sonnet-5.5` | `E` | `21 / 21` | `99.74` | `100.00` | `97.64` | `16 / 21` | `0.000` (`0`) | `0.000` | `20 / 1 / 0` | `[95.2, 95.2]` |
| `gemini-4-argon` | `A` | `21 / 21` | `99.18` | `99.21` | `96.06` | `6 / 21` | `0.000` (`0`) | `0.000` | `6 / 15 / 0` | `[28.6, 28.6]` |
| `gemini-4-argon` | `B` | `21 / 21` | `99.51` | `99.21` | `99.21` | `8 / 21` | `0.000` (`0`) | `0.000` | `8 / 13 / 0` | `[38.1, 38.1]` |
| `gemini-4-argon` | `C` | `21 / 21` | `99.70` | `100.00` | `96.85` | `16 / 21` | `0.000` (`0`) | `0.000` | `16 / 5 / 0` | `[76.2, 76.2]` |
| `gemini-4-argon` | `D` | `21 / 21` | `99.36` | `99.21` | `96.85` | `7 / 21` | `0.000` (`0`) | `0.000` | `7 / 14 / 0` | `[33.3, 33.3]` |
| `gemini-4-argon` | `E` | `20 / 21` | `99.53` | `99.21` | `98.43` | `9 / 20` | `0.050` (`1`) | `0.200` | `10 / 10 / 1` | `[47.6, 52.4]` |
| `gpt-6.1-sol` | `A` | `21 / 21` | `91.60` | `88.98` | `88.98` | `5 / 21` | `0.000` (`0`) | `0.000` | `19 / 2 / 0` | `[90.5, 90.5]` |
| `gpt-6.1-sol` | `B` | `21 / 21` | `95.28` | `100.00` | `88.98` | `12 / 21` | `0.000` (`0`) | `0.000` | `17 / 3 / 1` | `[81.0, 85.7]` |
| `gpt-6.1-sol` | `C` | `20 / 21` | `92.83` | `88.98` | `88.98` | `7 / 20` | `0.000` (`0`) | `0.000` | `16 / 3 / 2` | `[76.2, 85.7]` |
| `gpt-6.1-sol` | `D` | `21 / 21` | `92.13` | `88.98` | `88.98` | `6 / 21` | `0.000` (`0`) | `0.000` | `19 / 2 / 0` | `[90.5, 90.5]` |
| `gpt-6.1-sol` | `E` | `21 / 21` | `95.28` | `100.00` | `88.98` | `12 / 21` | `0.000` (`0`) | `0.000` | `20 / 1 / 0` | `[95.2, 95.2]` |

### Within-Model `CR1` Identification Bounds (`H6`, Percentage Points)

From [pilot-estimation/report.md](pilot-estimation/report.md), exact worst-case/best-case identification bounds for `CR1` success-rate differences across all `21` allocated runs per arm (accounting for missing/unadjudicated outcomes without imputation) are:

* `claude-sonnet-5.5`: `B - D = [+4.76, +4.76]` pts; `B - A = [0.00, 0.00]` pts; `B - C = [0.00, 0.00]` pts; `E - B = [-4.76, -4.76]` pts.
* `gemini-4-argon`: `B - D = [+4.76, +4.76]` pts; `B - A = [+9.52, +9.52]` pts; `B - C = [-38.10, -38.10]` pts; `E - B = [+9.52, +14.29]` pts.
* `gpt-6.1-sol`: `B - D = [-9.52, -4.76]` pts; `B - A = [-9.52, -4.76]` pts; `B - C = [-4.76, +9.52]` pts; `E - B = [+9.52, +14.29]` pts. (Note: `CR1` success requires preserving *only* the feature tests that already passed at `P10` plus passing `test_cr*`; because `gpt-6.1-sol` `Arms A` and `D` left `F9` unimplemented at `P10` in `16/21` and `15/21` runs, `F9` tests were not in their `P10`-passing retention baseline during `CR1`, whereas `Arm B` carried `12/21` `F9`-passing runs into `CR1`.)

### Table 1b: Complete-Pair Unassisted Contrasts (`seed = 2027`, `10,000` Draws) and Full-Allocation Identification Bounds

With `intervention-coverage/v1` attested across all `313` completed trajectories, every contrast where both compared arms have `100%` complete unassisted trajectories (`63 vs 63` pooled, or `21 vs 21` within model) has an exact point difference and `95%` interval computed via `analyze.boot_diff` (`H1`) and `analyze.success_difference` (`H6`, simultaneous `97.5%` Clopper-Pearson bounds). Contrasts affected by one of the two quarantined runs (`gpt-6.1-sol-C-20` or `gemini-4-argon-E-15`) or the two unadjudicated `CR1` test errors (`gpt-6.1-sol-B-08`, `gpt-6.1-sol-C-14`) report exact worst/best-case Manski bounds over the full allocation (`[0, 100]%`).

| Scope | Contrast | `H1` (`P10` Pass Rate) Complete Pair | `H1` Point Diff (pts) | `H1` `95%` Bootstrap CI | `H1` Exact Full-Allocation Bounds | `H6` (`CR1` Success) Point Diff (pts) | `H6` Conservative Exact `95%` CI | `H6` Exact Full-Allocation Bounds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Pooled 3-Model | `B - D` (primary) | `63/63` vs `63/63` | `+1.19` | `[+0.10, +2.22]` | `[+1.19, +1.19]` | `n/a` (1 `B` CR1 err) | `n/a` | `[0.00, +1.59]` |
| Pooled 3-Model | `B - A` | `63/63` vs `63/63` | `+1.41` | `[+0.33, +2.45]` | `[+1.41, +1.41]` | `n/a` (1 `B` CR1 err) | `n/a` | `[0.00, +1.59]` |
| Pooled 3-Model | `B - C` | `63/63` vs `62/63` | `n/a` | `n/a` | `[+0.66, +2.25]` | `n/a` | `n/a` | `[-14.29, -9.52]` |
| Pooled 3-Model | `E - B` | `62/63` vs `63/63` | `n/a` | `n/a` | `[-1.55, +0.04]` | `n/a` | `n/a` | `[+4.76, +7.94]` |
| `claude-sonnet-5.5` | `B - D` | `21/21` vs `21/21` | `+0.26` | `[-0.15, +0.75]` | `[+0.26, +0.26]` | `+4.76` | `[-18.77, +26.77]` | `[+4.76, +4.76]` |
| `claude-sonnet-5.5` | `B - A` | `21/21` vs `21/21` | `+0.22` | `[-0.19, +0.71]` | `[+0.22, +0.22]` | `0.00` | `[-18.83, +18.83]` | `[0.00, 0.00]` |
| `claude-sonnet-5.5` | `B - C` | `21/21` vs `21/21` | `+0.07` | `[-0.22, +0.41]` | `[+0.07, +0.07]` | `0.00` | `[-18.83, +18.83]` | `[0.00, 0.00]` |
| `claude-sonnet-5.5` | `E - B` | `21/21` vs `21/21` | `+0.07` | `[-0.26, +0.37]` | `[+0.07, +0.07]` | `-4.76` | `[-26.77, +18.77]` | `[-4.76, -4.76]` |
| `gemini-4-argon` | `B - D` | `21/21` vs `21/21` | `+0.15` | `[-0.15, +0.52]` | `[+0.15, +0.15]` | `+4.76` | `[-43.88, +51.67]` | `[+4.76, +4.76]` |
| `gemini-4-argon` | `B - A` | `21/21` vs `21/21` | `+0.34` | `[-0.07, +0.82]` | `[+0.34, +0.34]` | `+9.52` | `[-39.16, +54.73]` | `[+9.52, +9.52]` |
| `gemini-4-argon` | `B - C` | `21/21` vs `21/21` | `-0.19` | `[-0.49, +0.19]` | `[-0.19, -0.19]` | `-38.10` | `[-77.05, +14.69]` | `[-38.10, -38.10]` |
| `gemini-4-argon` | `E - B` | `20/21` vs `21/21` | `n/a` | `n/a` | `[-4.72, +0.04]` | `n/a` | `n/a` | `[+9.52, +14.29]` |
| `gpt-6.1-sol` | `B - D` | `21/21` vs `21/21` | `+3.15` | `[0.00, +6.30]` | `[+3.15, +3.15]` | `n/a` (1 `B` CR1 err) | `n/a` | `[-9.52, -4.76]` |
| `gpt-6.1-sol` | `B - A` | `21/21` vs `21/21` | `+3.67` | `[+0.52, +6.82]` | `[+3.67, +3.67]` | `n/a` (1 `B` CR1 err) | `n/a` | `[-9.52, -4.76]` |
| `gpt-6.1-sol` | `B - C` | `21/21` vs `20/21` | `n/a` | `n/a` | `[+2.10, +6.86]` | `n/a` | `n/a` | `[-4.76, +9.52]` |
| `gpt-6.1-sol` | `E - B` | `21/21` vs `21/21` | `0.00` | `[-3.15, +3.15]` | `[0.00, 0.00]` | `n/a` (1 `B` CR1 err) | `n/a` | `[+9.52, +14.29]` |

### Three Distinct Failure Mechanisms Behind the Numbers

1. Minimal decay in `claude-sonnet-5.5`: Across all `105` trajectories, the sole recurring hidden-test miss at `P10` was a subtle audit-target convention edge case in `F10` (`test_f10_hidden::test_h10_targets_and_actors`, missed in `8` `A`, `7` `B`, `8` `C`, `9` `D`, and `4` `E` runs, lowering those trajectories from `100%` to `99.21%`, or `126 / 127` tests).
2. Self-locking test immutability in `gpt-6.1-sol` (`88.98%` plateau = `113 / 127` tests): Every `88.98%` trajectory missed all `14` `F9` ranking hidden tests. Inspection of step diffs and SDK journals shows why: during `F8`, `gpt-6.1-sol` routinely authored a unit test asserting that *every* attribute on a view outside a hardcoded `F8` `READ_METHODS` set raises `NotAllowed`. When `F9` required `view.rank_cases()`, the harness's immutable-test rule forbade editing the `F8` test file. `Arm A` (`5 / 21` `100%`) and `Arm D` (`6 / 21` `100%`) remained stuck at `88.98%` whenever `F8` had been written that way, whereas `Arm B` (`12 / 21` `100%`, median `100.0%`) and `Arm E` (`12 / 21` `100%`, median `100.0%`) avoided or repaired the lock in more than half of trajectories.
3. Read-only view blocklist debt in `gemini-4-argon` (`99.21%` at `P10` -> `CR1` failure): In `57` trajectories across arms (`15` `A`, `14` `D`, `13` `B`, `10` `E`, `5` `C`), `gemini-4-argon` missed `1` hidden test at `P10` (`test_f08_hidden::test_h08_every_write_is_refused_on_a_view`, yielding `126 / 127 = 99.21%`) because its `View` proxy explicitly blocked earlier write methods rather than denying unknown mutators by default. When `CR1` added `define_region`, `add_user`, and `approve_handoff`, those same `57` trajectories failed `test_cr1_hidden::test_hcr1_user_views_are_read_only`. Notably, `Arm C`'s dedicated read-only review step (`REVIEW.md`) flagged the proxy-forwarding risk during `F8..F10` far more reliably (`only 5 / 21` failures; `76.2%` `CR1` success) than metric-driven TCR refactoring in `Arm B` (`13 / 21` failures; `38.1%` `CR1` success), because `Arm B`'s quality budget (`CCN <= 10`, `dup < 3%`, `ruff = 0`) was already satisfied (`mean_ccn = 2.68`, `dup = 0.0%`, `lint = 0.08/kLOC` even in `Arm A`!). This is a textbook empirical demonstration of the Goodhart / structural-proxy limitation anticipated in [vetting.md](../vetting.md): when static metrics are already green, metric-guided consolidation stops early, whereas explicit defect-oriented code review (`Arm C`) inspects semantic invariants.

## Structural Quality, Code Volume, and Cost (`H3`, `H4`, `H5`)

### Table 2: `P10` Structural Metrics, Repository Size, AI Credits, and Wall-Clock Duration

Metrics are means across measured `P10` checkpoints (`n = 21` in all cells except `gemini-4-argon:E` and `gpt-6.1-sol:C`, where `n = 20`). Delivery and `CR1` credit means include only trajectories with `100%` complete session billing (`n` shown in parentheses), per `complete_sum` in [harness/analyze.py](../harness/analyze.py).

| Model | Arm | Mean CCN | Funcs `> 10` CCN (%) | Duplication (%) | Lint / kLOC | `src` NLOC | Markdown Words | Delivery Credits (`n`) | `CR1` Credits (`n`) | Delivery Min | `CR1` Min |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `claude-sonnet-5.5` | `A` | `2.79` | `1.10` | `0.33` | `28.15` | `439.6` | `106.0` | `54.52` (`21`) | `11.07` (`21`) | `7.36` | `1.09` |
| `claude-sonnet-5.5` | `B` | `2.66` | `0.00` | `0.05` | `2.26` | `463.2` | `351.3` | `115.02` (`21`) | `12.07` (`21`) | `16.94` | `1.15` |
| `claude-sonnet-5.5` | `C` | `2.78` | `0.95` | `0.25` | `21.14` | `449.5` | `378.8` | `110.89` (`21`) | `11.85` (`21`) | `15.92` | `1.12` |
| `claude-sonnet-5.5` | `D` | `2.80` | `1.10` | `0.31` | `28.84` | `435.6` | `106.0` | `53.70` (`21`) | `11.14` (`21`) | `7.32` | `1.12` |
| `claude-sonnet-5.5` | `E` | `2.79` | `1.44` | `0.26` | `28.23` | `438.0` | `106.0` | `104.10` (`20`) | `11.05` (`21`) | `14.89` | `1.07` |
| `gemini-4-argon` | `A` | `2.68` | `0.33` | `0.00` | `0.08` | `600.6` | `106.0` | `112.66` (`20`) | `27.10` (`21`) | `24.56` | `5.01` |
| `gemini-4-argon` | `B` | `2.26` | `0.00` | `0.00` | `0.00` | `620.1` | `403.1` | `253.03` (`17`) | `30.79` (`21`) | `55.64` | `5.54` |
| `gemini-4-argon` | `C` | `1.78` | `0.00` | `0.00` | `0.06` | `778.5` | `371.7` | `239.55` (`18`) | `40.53` (`20`) | `49.70` | `7.31` |
| `gemini-4-argon` | `D` | `2.63` | `0.08` | `0.05` | `0.09` | `596.5` | `106.0` | `116.29` (`17`) | `28.02` (`21`) | `26.32` | `5.38` |
| `gemini-4-argon` | `E` | `2.73` | `0.50` | `0.00` | `0.00` | `605.2` | `106.0` | `237.66` (`17`) | `30.16` (`19`) | `51.07` | `5.46` |
| `gpt-6.1-sol` | `A` | `2.55` | `3.42` | `0.00` | `16.04` | `519.7` | `1747.1` | `155.93` (`18`) | `39.32` (`20`) | `25.33` | `6.45` |
| `gpt-6.1-sol` | `B` | `2.49` | `0.00` | `0.00` | `0.00` | `557.0` | `2002.4` | `286.78` (`16`) | `38.46` (`21`) | `51.54` | `6.36` |
| `gpt-6.1-sol` | `C` | `2.58` | `3.33` | `0.11` | `12.78` | `519.1` | `2030.2` | `278.14` (`13`) | `40.39` (`20`) | `46.63` | `6.63` |
| `gpt-6.1-sol` | `D` | `2.56` | `3.42` | `0.11` | `13.01` | `520.2` | `1732.2` | `161.28` (`17`) | `38.51` (`21`) | `26.27` | `6.18` |
| `gpt-6.1-sol` | `E` | `2.60` | `3.32` | `0.05` | `20.73` | `545.6` | `1859.1` | `300.18` (`15`) | `39.88` (`20`) | `54.33` | `6.68` |

### Structural and Cost Observations

* Quality-budget compliance (`H3`): `Arm B` consistently enforced its explicit refactoring targets across all three models (`0.00%` functions above complexity `10`, `0.00%` to `0.05%` duplication, and `0.00` to `2.26` lint warnings per kLOC).
* Documentation habits (`H4` proxy): `claude-sonnet-5.5` and `gemini-4-argon` left the `106`-word skeleton `README.md` untouched in `Arms A, D, E` and wrote concise ~`250` to `300`-word `DESIGN.md` / `REVIEW.md` artifacts in `Arms B, C`. By contrast, `gpt-6.1-sol` spontaneously expanded `README.md` to ~`1,730` to `1,860` words even in `Arms A, D, E`.
* Affordability (`H5`): Across all three models, `Arm B` cost `1.84x` (`gpt-6.1-sol`), `2.11x` (`claude-sonnet-5.5`), and `2.25x` (`gemini-4-argon`) the delivery credits of `Arm A`, because starting a second fresh agent session per feature re-incurs context ingestion and test-execution turns. Within this `10`-feature horizon, consolidation did not pay for itself in downstream feature or `CR1` credit savings.

## Supplementary Post-Collection Workflow Replay and Blinded AI Judging

To evaluate behavioral workflow coherence, error recovery, and caller-facing API usability without exposing development arm or model identity, we executed the supplementary evaluation in [../judging/README.md](../judging/README.md) against a frozen post-collection archive of all `315` trajectories.

### Replay Coverage and Zero Witnessed Endpoint Losses

Twelve synthetic public-specification API workflows (`registration`, `lifecycle`, `handoff`, `rework`, `safety`, `consent`, `appointments`, `privacy`, `ranking`, `audit-export`, `delivery-journey`, plus `regions` at `CR1`) were replayed in isolated containers across `3,457` recorded end-of-cycle (`P1..P10`) and `CR1` commits, producing `630` anonymized specimen packets (`315` `P10` + `315` `CR1`; `4` packets wholly unavailable from the `2` quarantined trajectories).

* Across all `626` evaluable endpoint packets (`6,886` scenario evaluations), **witnessed capability loss (`observed_loss`) was `0` in every model and arm**. Every endpoint scenario failure was `never_observed_pass` (primarily `gpt-6.1-sol` failing `ranking` and `delivery-journey` because `F9` was never committed). Once a workflow passed at an end-of-cycle `P_k` checkpoint, it remained passing at `P10` and `CR1` (`retained`), with `1` `claude-sonnet-5.5` `Arm E` run failing only the newly introduced `CR1` `regions` scenario (`20 / 21` all-pass at `CR1`).

### Blinded AI Judge Execution (`gpt-6-luna`, Assessment v3)

Each of the `626` evaluable anonymized packets was rated twice in fresh, tool-disabled sessions (`1,252` total scheduled calls) by `gpt-6-luna` at `medium` reasoning effort (`sdk1.0.28-cli1.0.105-judge3`, enforcing a strict JSON Schema over scenario IDs, `0..4` or `null` ordinal scores, and allowed final observation citations).

* Credit lineage across assessments: Assessment v1 stopped on call `1` prior to prompt dispatch due to a CommonJS/ESM SDK filter mismatch (`0` settled credits, `30` reserved credits held). Assessment v2 completed `15` calls (`5.282763` settled credits) and stopped on call `16` when free-form JSON omitted `evidence_ids` on one scenario (`30` reserved credits held; `0.3196095` diagnostic credits). Assessment v3 completed all `1,252 / 1,252` calls cleanly (`0` failed retries, `0` quarantined/blocked calls) for `418.635894` settled AI credits inside the `2,934`-credit remaining ceiling (`3,000`-credit total envelope).

### Table 3: Complete-Frame Equal-Weight AI Judge Contrasts (`0` to `4` Ordinal Scale)

Per [../judging/judge.py](../judging/judge.py), a complete-frame contrast is reported only when *every* allocated trajectory in both compared arms across all three models has complete non-null ratings across all scheduled scenarios (`11` at `P10`, `12` at `CR1`). Contrasts involving `C` or `E` are `unavailable` at complete-frame level due to the single quarantined trajectory in `gpt-6.1-sol:C` and `gemini-4-argon:E`; `workflow_coherence` and `error_recovery` are `unavailable` at complete-frame level because crashed `ranking` workflows have `null` (`NA`) abstentions on unobserved recovery/coherence.

| Endpoint | Contrast | `functional_completeness` | `workflow_coherence` | `error_recovery` | `api_usability` |
| --- | --- | --- | --- | --- | --- |
| `P10` | `B - D` (equal-budget primary) | `+0.0577` | `unavailable` | `unavailable` | `+0.0599` |
| `P10` | `B - A` (unmatched budget) | `+0.0729` | `unavailable` | `unavailable` | `+0.0722` |
| `CR1` | `B - D` (equal-budget primary) | `+0.0351` | `unavailable` | `unavailable` | `+0.0357` |
| `CR1` | `B - A` (unmatched budget) | `+0.0357` | `unavailable` | `unavailable` | `+0.0370` |
| `P10` & `CR1` | `B - C`, `E - B` | `unavailable` | `unavailable` | `unavailable` | `unavailable` |

### Table 3b: Resolving Every `unavailable` Cell in Table 3 / Whitepaper Table 12 (Exact Manski Bounds + Observed-Scenario Contrasts)

Every `unavailable` entry in Table 3 (`Table 12` in the whitepaper draft) arises from `judge.py`'s all-or-nothing gate rather than missing judge calls (`1,252 / 1,252` judge calls succeeded):

1. `workflow_coherence` and `error_recovery` columns: When an unimplemented `F9` `ranking` scenario crashes immediately (`AttributeError`, `0` observation rows), the rubric requires `null` (`NA`) on unobserved recovery/coherence rather than `0`. Every evaluable trajectory (`626 / 626`) still has a valid run-level mean across its remaining `10` to `11` observed scenarios, while `judge.py` withholds the strict column to flag potential survivorship bias. Pairing the observed-scenario run-mean difference with the trajectory `NA`-abstention counts (`focal / 63` vs `comparator / 63`) resolves that ambiguity completely: `Arm B` cut `error_recovery` crash-abstentions nearly in half (`9 / 63` vs `16 / 63` in `D` and `17 / 63` in `A` at `P10`; `8 / 63` vs `16 / 63` in `D` and `18 / 63` in `A` at `CR1`).
2. `B - C` and `E - B` rows: Only `1` of `63` trajectories in `Arm C` (`gpt-6.1-sol-C-20`) and `1` of `63` in `Arm E` (`gemini-4-argon-E-15`) were quarantined. Imputing the full `[0, 4]` scale endpoints (`0.0` worst case, `4.0` best case, weight `1 / 63 = 0.0635`) yields exact non-parametric Manski identification bounds over all `63 vs 63` allocated trajectories, proving that `B - C` is strictly positive across the entire `315`-run allocation on both `functional_completeness` (`[+0.0382, +0.1017]` at `P10`; `[+0.0218, +0.0853]` at `CR1`) and `api_usability` (`[+0.0375, +0.1010]` at `P10`; `[+0.0231, +0.0866]` at `CR1`).

All values below are extracted directly in [pilot-estimation-judging/extracted-contrasts.json](pilot-estimation-judging/extracted-contrasts.json) (`seed = 2027`, `10,000` stratified bootstrap draws):

| Endpoint | Contrast (`n_focal` vs `n_comp`) | `Func. completeness` Diff (`95%` CI) / `[Bounds]` | `Workflow coherence` Obs Diff (`95%` CI) / `NA` Runs | `Error recovery` Obs Diff (`95%` CI) / `NA` Runs | `API usability` Diff (`95%` CI) / `[Bounds]` |
| --- | --- | --- | --- | --- | --- |
| `P10` | `B - D` (`63` vs `63`) | `+0.0577` (`[+0.0007, +0.1097]`) | `+0.0180` (`[-0.0327, +0.0663]`) · `NA: 2 vs 8` | `+0.0039` (`[-0.0234, +0.0307]`) · `NA: 9 vs 16` | `+0.0599` (`[0.0000, +0.1154]`) |
| `P10` | `B - A` (`63` vs `63`) | `+0.0729` (`[+0.0173, +0.1248]`) | `+0.0559` (`[+0.0019, +0.1060]`) · `NA: 2 vs 4` | `+0.0068` (`[-0.0213, +0.0355]`) · `NA: 9 vs 17` | `+0.0722` (`[+0.0137, +0.1263]`) |
| `P10` | `B - C` (`63` vs `62`) | `+0.0442` · Bounds `[+0.0382, +0.1017]` | `+0.0288` · Bounds `[+0.0240, +0.0875]` · `NA: 2 vs 5` | `+0.0009` · Bounds `[-0.0009, +0.0626]` · `NA: 9 vs 13` | `+0.0437` · Bounds `[+0.0375, +0.1010]` |
| `P10` | `E - B` (`62` vs `63`) | `-0.0036` · Bounds `[-0.0671, -0.0036]` | `+0.0024` · Bounds `[-0.0611, +0.0024]` · `NA: 2 vs 2` | `+0.0116` · Bounds `[-0.0514, +0.0121]` · `NA: 11 vs 9` | `+0.0051` · Bounds `[-0.0584, +0.0051]` |
| `CR1` | `B - D` (`63` vs `63`) | `+0.0351` (`[-0.0046, +0.0741]`) | `+0.0376` (`[+0.0016, +0.0728]`) · `NA: 2 vs 1` | `-0.0112` (`[-0.0265, +0.0022]`) · `NA: 8 vs 16` | `+0.0357` (`[-0.0040, +0.0747]`) |
| `CR1` | `B - A` (`63` vs `63`) | `+0.0357` (`[-0.0013, +0.0728]`) | `+0.0425` (`[+0.0073, +0.0767]`) · `NA: 2 vs 0` | `-0.0069` (`[-0.0227, +0.0079]`) · `NA: 8 vs 18` | `+0.0370` (`[-0.0007, +0.0747]`) |
| `CR1` | `B - C` (`63` vs `62`) | `+0.0258` · Bounds `[+0.0218, +0.0853]` | `+0.0278` · Bounds `[+0.0242, +0.0877]` · `NA: 2 vs 1` | `-0.0035` · Bounds `[-0.0043, +0.0592]` · `NA: 8 vs 13` | `+0.0271` · Bounds `[+0.0231, +0.0866]` |
| `CR1` | `E - B` (`62` vs `63`) | `+0.0040` · Bounds `[-0.0595, +0.0040]` | `+0.0001` · Bounds `[-0.0634, +0.0001]` · `NA: 1 vs 2` | `+0.0067` · Bounds `[-0.0563, +0.0072]` · `NA: 9 vs 8` | `+0.0046` · Bounds `[-0.0589, +0.0046]` |

#### Drop-in LaTeX Replacement for Whitepaper Table 12

```latex
\begin{table}[t]
\centering
\caption{Equal-weight AI judge contrasts on the 0--4 ordinal scale across all 315 allocated trajectories (63 per arm across three models). Complete 63-vs-63 pairs report exact differences; pairs with 1 quarantined trajectory ($B-C$, $E-B$) report evaluable differences above exact $[0,4]$ Manski identification bounds. Columns with rubric \texttt{NA} abstentions on crashed scenarios ($\dagger$) report observed-scenario run-mean differences alongside counts of trajectories having $\ge 1$ \texttt{NA} scenario.}
\label{tab:ai-judge-contrasts}
\small
\begin{tabular}{llcccc}
\toprule
Endpoint & Contrast & Func.\ completeness & Workflow coherence$^\dagger$ & Error recovery$^\dagger$ & API usability \\
\midrule
$P_{10}$ & B -- D (equal-budget) & $+0.0577$ & $+0.0180$ {\scriptsize(NA: 2 vs 8)} & $+0.0039$ {\scriptsize(NA: 9 vs 16)} & $+0.0599$ \\
$P_{10}$ & B -- A (unmatched)    & $+0.0729$ & $+0.0559$ {\scriptsize(NA: 2 vs 4)} & $+0.0068$ {\scriptsize(NA: 9 vs 17)} & $+0.0722$ \\
$P_{10}$ & B -- C (63 vs 62)     & $+0.0442$ {\scriptsize$[+0.0382,+0.1017]$} & $+0.0288$ {\scriptsize(NA: 2 vs 5)} & $+0.0009$ {\scriptsize(NA: 9 vs 13)} & $+0.0437$ {\scriptsize$[+0.0375,+0.1010]$} \\
$P_{10}$ & E -- B (62 vs 63)     & $-0.0036$ {\scriptsize$[-0.0671,-0.0036]$} & $+0.0024$ {\scriptsize(NA: 2 vs 2)} & $+0.0116$ {\scriptsize(NA: 11 vs 9)} & $+0.0051$ {\scriptsize$[-0.0584,+0.0051]$} \\
\midrule
CR1      & B -- D (equal-budget) & $+0.0351$ & $+0.0376$ {\scriptsize(NA: 2 vs 1)} & $-0.0112$ {\scriptsize(NA: 8 vs 16)} & $+0.0357$ \\
CR1      & B -- A (unmatched)    & $+0.0357$ & $+0.0425$ {\scriptsize(NA: 2 vs 0)} & $-0.0069$ {\scriptsize(NA: 8 vs 18)} & $+0.0370$ \\
CR1      & B -- C (63 vs 62)     & $+0.0258$ {\scriptsize$[+0.0218,+0.0853]$} & $+0.0278$ {\scriptsize(NA: 2 vs 1)} & $-0.0035$ {\scriptsize(NA: 8 vs 13)} & $+0.0271$ {\scriptsize$[+0.0231,+0.0866]$} \\
CR1      & E -- B (62 vs 63)     & $+0.0040$ {\scriptsize$[-0.0595,+0.0040]$} & $+0.0001$ {\scriptsize(NA: 1 vs 2)} & $+0.0067$ {\scriptsize(NA: 9 vs 8)}  & $+0.0046$ {\scriptsize$[-0.0589,+0.0046]$} \\
\bottomrule
\end{tabular}
\end{table}
```

### Table 4: Descriptive AI Judge Cell Means Over Evaluable Specimens (`0` to `4` Scale)

To show all five arms transparently alongside missingness, Table 4 reports the mean of run-level scenario means across evaluable specimens (`n = 21`, except `n = 20` for `gemini-4-argon:E` and `gpt-6.1-sol:C`), together with the count of evaluable runs passing all synthetic scenarios.

| Model | Arm | Evaluable | `P10` All-Pass | `P10` Func | `P10` Coher | `P10` Recov | `P10` API | `CR1` All-Pass | `CR1` Func | `CR1` Coher | `CR1` Recov | `CR1` API |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `claude-sonnet-5.5` | `A` | `21` | `20` | `3.985` | `3.991` | `3.972` | `3.987` | `20` | `3.990` | `3.990` | `3.976` | `3.990` |
| `claude-sonnet-5.5` | `B` | `21` | `21` | `3.998` | `4.000` | `3.974` | `4.000` | `21` | `4.000` | `4.000` | `3.966` | `4.000` |
| `claude-sonnet-5.5` | `C` | `21` | `21` | `4.000` | `4.000` | `3.974` | `4.000` | `21` | `4.000` | `4.000` | `3.970` | `4.000` |
| `claude-sonnet-5.5` | `D` | `21` | `20` | `3.989` | `3.991` | `3.965` | `3.987` | `20` | `3.984` | `3.986` | `3.962` | `3.984` |
| `claude-sonnet-5.5` | `E` | `21` | `21` | `4.000` | `4.000` | `3.961` | `4.000` | `20` | `3.992` | `3.992` | `3.964` | `3.992` |
| `gemini-4-argon` | `A` | `21` | `20` | `3.991` | `3.994` | `3.948` | `3.991` | `20` | `3.992` | `3.992` | `3.958` | `3.992` |
| `gemini-4-argon` | `B` | `21` | `21` | `4.000` | `4.000` | `3.968` | `4.000` | `21` | `4.000` | `4.000` | `3.968` | `4.000` |
| `gemini-4-argon` | `C` | `21` | `21` | `4.000` | `4.000` | `3.965` | `4.000` | `21` | `4.000` | `4.000` | `3.976` | `4.000` |
| `gemini-4-argon` | `D` | `21` | `21` | `4.000` | `4.000` | `3.972` | `4.000` | `21` | `4.000` | `4.000` | `3.974` | `4.000` |
| `gemini-4-argon` | `E` | `20` | `20` | `4.000` | `4.000` | `3.968` | `4.000` | `20` | `4.000` | `4.000` | `3.969` | `4.000` |
| `gpt-6.1-sol` | `A` | `21` | `5` | `3.563` | `3.633` | `3.893` | `3.548` | `5` | `3.740` | `3.746` | `3.976` | `3.738` |
| `gpt-6.1-sol` | `B` | `21` | `12` | `3.760` | `3.785` | `3.892` | `3.742` | `12` | `3.829` | `3.856` | `3.955` | `3.831` |
| `gpt-6.1-sol` | `C` | `20` | `7` | `3.625` | `3.699` | `3.891` | `3.611` | `7` | `3.752` | `3.772` | `3.954` | `3.750` |
| `gpt-6.1-sol` | `D` | `21` | `6` | `3.595` | `3.740` | `3.885` | `3.576` | `6` | `3.740` | `3.757` | `3.987` | `3.740` |
| `gpt-6.1-sol` | `E` | `21` | `12` | `3.747` | `3.793` | `3.939` | `3.758` | `12` | `3.849` | `3.864` | `3.977` | `3.853` |

Notice how `gemini-4-argon` scored `4.000` across `Arms B, C, D, E` in the `12`-scenario workflow panel even when `57` of its trajectories failed the exhaustive hidden suite's `test_hcr1_user_views_are_read_only`. That contrast is methodologically instructive for the paper: a representative happy-path + single-rejection scenario panel (`view.open_case` in `privacy:3`) misses exhaustive permission-surface regressions (`view.define_region` / `view.approve_handoff`), demonstrating why black-box scenario judging complements rather than replaces exhaustive property/invariant test suites.

## Human Calibration Spot-Check (`S01..S08`)

Before AI scoring began, `8` blinded endpoint packets (`90` scenario rows: `6` `P10` packets x `11` scenarios + `2` `CR1` packets x `12` scenarios; `4` from the incomplete/failing stratum and `4` from the passing stratum, with `0` observed-loss packets available in the population) were frozen for human calibration via the reproducible offline interface in [../judging/human-review/](../judging/human-review/).

### Calibration Structure, Disclosures, and Agreement

* Sample structure: `S01` (`11` rows) had an unavailable final checkpoint (`NA` across all four dimensions). Across the `79` scorable rows (`158` paired human-vs-AI repeat comparisons per dimension), `69` rows passed every check cleanly, yielding `16` distinct requirement-and-final-evidence contexts (`S02` and `S03` shared identical final evidence, as did `S05, S06, S08`).
* Reviewer provenance and disclosures: Study author `jmservera` scored the `90`-row pack under `human-calibration-guidance/v3` and explicitly recorded `review_status = in_progress` (`review_completed_yes_no = no`) with the disclosure: *"I used AI for identifying the cases with failures or mismatches instead of reviewing all the successful ones."* Because `guidance/v3` was clarified after an AI usability dry run and after original AI judge execution began, these figures serve as a transparent spot-check rather than an independent multi-rater reliability estimate.

| Dimension | Scorable Paired Comparisons | Raw `79`-Row Exact | Raw `79`-Row Within `1` | Equal-Context (`16`) Exact | Equal-Context (`16`) Within `1` | Unavailable `NA` Match | `NA` vs Numeric Pairs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `functional_completeness` | `158` | `98.7%` | `100.0%` | `96.9%` | `100.0%` | `11 / 11` | `0` |
| `workflow_coherence` | `158` | `97.5%` | `98.7%` | `93.8%` | `96.9%` | `11 / 11` | `2` |
| `error_recovery` | `158` | `94.3%` | `98.7%` | `87.5%` | `95.3%` | `11 / 11` | `2` |
| `api_usability` | `158` | `98.1%` | `100.0%` | `92.2%` | `100.0%` | `11 / 11` | `0` |

Across all `632` scorable dimension-repeat comparisons (`158 x 4`), there were **`0` substantive numeric disagreements (`|human - AI| >= 2`)**, `14` one-point boundary differences (`0` vs `1`, `1` vs `2`, `2` vs `3`, or `3` vs `4`, notably whether `ranking:3`'s final-step `ValidationError` rejection without a subsequent step warrants `3` or `4` on `error_recovery`), and `4` `NA`-vs-numeric boundary differences on crashed scenarios (`0` vs `NA` on `workflow_coherence` when `ranking` crashed with `AttributeError` before any observation row, and `1` vs `NA` on `error_recovery` after an uncaught `NotAllowed` / `AttributeError`).

## In-Band Autonomy and SDK Event-Journal Audit

To answer how often agents requested additional human information or halted unable to proceed without intervention, all `5,357 / 5,357` (`100%`) retained SDK transport event journals (`transport/events.jsonl`) were audited in [pilot-estimation-judging/intervention-log-audit-summary.json](pilot-estimation-judging/intervention-log-audit-summary.json):

* Interactive user-input or elicitation RPC events: `0` across `5,357` sessions (`onUserInputRequest` and `onElicitationRequest` were disabled in the transport).
* Tool-call discipline: Out of `42,594` tool invocations, `42,520` (`99.83%`) called `isolated_exec`. Exactly `74` (`0.17%`) attempted built-in `create` (`53`) or `edit` (`21`) file tools (all by `claude-sonnet-5.5`, all immediately rejected with `Tool '<name>' does not exist.`), and `0` attempted any interactive `ask_user` or question tool.
* Sessions ending with a human permission or confirmation question: Exactly **`36 / 5,357` sessions (`0.67%`) across `29 / 315` trajectories (`9.21%`)**, leaving `src/` completely unchanged in `35 / 36` cases:
  * `gpt-6.1-sol`: `18 / 1,805` sessions (`18` `f09-feature` steps across `Arms A, B, C, D, E`; `18 / 18` leaving `src/` unchanged), each halting after implementing `F9` to ask *"May I add `rank_cases` to that test's `READ_METHODS` allowlist?"* rather than violating test immutability.
  * `claude-sonnet-5.5`: `18 / 1,785` sessions (`13` `consolidation`, `4` `review`, `1` `feature`; `17 / 18` leaving `src/` unchanged), asking whether to apply edits via shell commands or run `sh ./tcr` when built-in edit tools or `/usr/bin/env bash` were absent in the minimal Alpine container.
  * `gemini-4-argon`: `0 / 1,767` sessions halted to request human input or permission.

## Ready-to-Adapt Whitepaper Prose Blocks

### Draft Section: Experimental Setup and Five-Arm Design

> We evaluated scheduled post-feature consolidation on a ten-feature sequential Python specification (`s1-retrofit`, a municipal residential retrofit case-management library) followed by a held-out cross-cutting change request (`CR1`, regional access control and manager-approved cross-region handoffs). Three frontier models (`claude-sonnet-5.5`, `gemini-4-argon`, and `gpt-6.1-sol`, all pinned at `medium` reasoning effort via GitHub Copilot SDK `1.0.28` and CLI `1.0.105`) were crossed with five delivery arms at `21` allocated trajectories per cell (`N = 315` trajectories; `5,355` scheduled agent sessions). Every agent session ran without network access, external discovery, or interactive user tools inside a rootless read-only-root container, with earlier accepted test files held immutable.
>
> Arm `A` (baseline) allocated `30` minutes per feature (`270` soft AI credits) with no post-feature step. Arm `B` (consolidation) followed each feature with a `15`-minute consolidation session under test-commit-or-revert (`./tcr`), targeting zero functions above cyclomatic complexity `10`, duplication below `3%`, zero isolated `ruff` warnings, optional behavior-pinning tests in new files, and a refreshed one-page `DESIGN.md`. Arm `C` (review-only) matched `B`'s `15`-minute post-step budget in read-only mode, producing `REVIEW.md` without modifying source or tests. Arm `D` (equal-budget control) gave each feature one uninterrupted `45`-minute, `540`-soft-credit session to separate consolidation structure from raw budget headroom. Arm `E` (visible-spec repair) matched `B`'s `15`-minute post-step budget for repairing defects observable from already-supplied specifications, permitting narrowly audited updates to literal expected values in agent-authored equality assertions. Whereas an earlier three-arm protocol was preregistered on OSF (`https://osf.io/ywsrv/overview`), this expanded five-arm model-stratified design was publicly disclosed in version control prior to collection without an OSF amendment and is reported as an exploratory estimation study.

### Draft Section: Empirical Findings

> Across `313` completed trajectories (`5,341 / 5,355` measured steps; two trajectories quarantined after provider transport interruptions), ten sequential features did not trigger widespread regression cascades on the deterministic `127`-test hidden suite: `claude-sonnet-5.5` and `gemini-4-argon` averaged `99.18%` to `99.74%` pass rates at `P10`, and only one trajectory across the entire study exhibited an open regression on a previously passing unchanged feature contract (`0` witnessed losses across `626` endpoints in our supplementary `12`-workflow replay). Giving single-session feature delivery `50%` more time and credit headroom (`Arm D`) yielded virtually identical execution durations, credit consumption (`53.7` vs `54.5` credits on `claude-sonnet-5.5`; `116.3` vs `112.7` on `gemini-4-argon`; `161.3` vs `155.9` on `gpt-6.1-sol`), and correctness as `Arm A`, whereas separate post-feature sessions (`Arms B, C, E`) approximately doubled total delivery credits (`1.84x` to `2.25x` in `B` vs `A`).
>
> Despite high baseline retention, three model-specific mechanisms differentiated the arms. First, `Arm B` reliably enforced internal structural targets across all three models, reducing functions above cyclomatic complexity `10` to `0.00%` in all `63` `Arm B` trajectories and cutting lint warning density by `92%` on `claude-sonnet-5.5` (`2.26` vs `28.15`/kLOC) and `100%` on `gpt-6.1-sol` (`0.00` vs `16.04`/kLOC). Second, under strict test immutability, `gpt-6.1-sol` frequently over-specified its own `F8` view-method allowlist test, causing `18` `f09-feature` sessions to halt uncommitted asking operator permission to add `rank_cases` to that test (`88.98%` `P10` pass rate). Both `Arm B` consolidation and `Arm E` repair more than doubled full `100%` `P10` suite completion on `gpt-6.1-sol` (`12 / 21` each vs `5 / 21` in `A` and `6 / 21` in `D`), producing positive complete-frame gains in blinded `gpt-6-luna` workflow ratings at `P10` (`B - D: +0.058` functional completeness, `+0.060` API usability on a `0` to `4` scale) and `CR1` (`B - D: +0.035` and `+0.036`). Third, on `gemini-4-argon`, `57` trajectories implemented `F8` read-only views via an explicit blocklist of early write methods that failed to block newly introduced `CR1` mutators (`CR1` success `28.6%` in `A`, `33.3%` in `D`, `38.1%` in `B`). Because `gemini-4-argon`'s static metrics already satisfied `Arm B`'s numeric thresholds (`mean_ccn = 2.68`, `0%` duplication, `0.08` lint/kLOC in `A`), metric-gated consolidation left the proxy design unchanged, whereas dedicated read-only architectural review (`Arm C`) doubled `CR1` success to `76.2%` (`16 / 21`).

### Draft Section: Threats to Validity and Limitations

> Five limitations bound interpretation. First, while operator intervention coverage (`intervention-coverage/v1`) is attested across all `313` completed trajectories (unlocking full `claude-sonnet-5.5` intervals and complete `63 vs 63` `B - D` and `B - A` bootstrap intervals), two trajectories in `Arms C` and `E` (`gpt-6.1-sol-C-20` and `gemini-4-argon-E-15`) were quarantined after provider transport interruptions and are handled via exact worst/best-case Manski identification bounds rather than survivor-only pooling; similarly, `54 / 5,357` study sessions retain unresolved credit holds (`18,900` reserved credits alongside `62,052.61` settled credits). An audit of all `5,357 / 5,357` retained SDK event journals confirmed zero interactive user-input RPCs and identified all `36` sessions (`0.67%`) that ended with a permission or environment question. Second, `s1-retrofit` is a clean, self-contained synthetic Python specification (`~440` to `780` NLOC at `P10`); ten features were insufficient to induce the severe context-window and architectural decay observed in larger legacy codebases, creating a ceiling effect for `claude-sonnet-5.5` and `gemini-4-argon` on `H1` and `H2`. Third, enforcing strict test-file immutability protected against test tampering (`Goodhart` gaming) but penalized `gpt-6.1-sol` when its own `F8` tests over-constrained future `F9` extension methods. Fourth, our post-collection `12`-scenario workflow replay and `gpt-6-luna` judging (`1,252` calls; `418.64` credits) are exploratory, share a provider family with `gpt-6.1-sol`, and exhibited strong ceiling concentration (`69 / 90` calibration rows scored `4` on all dimensions). Fifth, human calibration (`90` rows, `16` distinct scorable contexts; `94.3%` to `98.7%` raw exact agreement, `87.5%` to `96.9%` equal-context exact agreement, `0` disagreements `>= 2` points) was conducted by a single study author using AI-assisted mismatch triage under guidance clarified after AI judging began, and therefore verifies rubric sanity rather than independent inter-rater reliability.

## Artifact Map for Figures, Tables, and Provenance

| Artifact Path | Contents for the Whitepaper |
| --- | --- |
| [pilot-estimation/report.md](pilot-estimation/report.md) | Automated pilot report with owner-attested `claude-sonnet-5.5` CIs, `CR1` identification bounds, and all `315` per-run dispositions |
| [pilot-estimation/runs.csv](pilot-estimation/runs.csv) | `315`-row trajectory table (`arm`, `model`, `replicate`, `end_pass_rate`, `cr_success`, delivery/`CR1` credits) |
| [pilot-estimation/series.csv](pilot-estimation/series.csv) | `3,150`-row cycle-by-cycle trajectory series (`k = 1..10`) for `pass_rate`, `open_regressions`, `nloc_src`, `md_words`, `mean_ccn`, `share_ccn_over_10`, `dup_pct`, `lint_per_kloc` |
| [pilot-estimation/trajectories.svg](pilot-estimation/trajectories.svg) and [pilot-estimation/trajectories.tex](pilot-estimation/trajectories.tex) | Ready-to-embed SVG and TikZ/PGFPlots trajectory figures across `k = 1..10` |
| [pilot-estimation/hypotheses.tex](pilot-estimation/hypotheses.tex) and [pilot-estimation/intervals.csv](pilot-estimation/intervals.csv) | LaTeX endpoint table and interval/bound exports |
| [pilot-estimation/attempts.csv](pilot-estimation/attempts.csv) and [pilot-estimation/provenance.json](pilot-estimation/provenance.json) | All `5,357` session attempts, source-commit lineage, adjudications, and billing/hold provenance |
| [pilot-estimation-judging/README.md](pilot-estimation-judging/README.md) and [pilot-estimation-judging/summary.json](pilot-estimation-judging/summary.json) | Complete `630`-endpoint workflow retention and `1,252`-call v3 blinded AI judge summary + v1/v2/v3 credit lineage |
| [pilot-estimation-judging/extracted-contrasts.json](pilot-estimation-judging/extracted-contrasts.json) | Extracted complete-pair `seed = 2027` bootstrap CIs, exact `[0, 100]%` and `[0, 4]` Manski bounds, and `NA`-abstention counts for all `32` Table 12 cells |
| [pilot-estimation-judging/report.csv](pilot-estimation-judging/report.csv) | `28,980`-row (`run x endpoint x scenario x dimension`) AI rating means, min/max ranges, and retention labels |
| [pilot-estimation-judging/human-calibration/human-vs-ai-comparison.json](pilot-estimation-judging/human-calibration/human-vs-ai-comparison.json) | Paired human-vs-AI calibration comparison (`90`-row and `16`-equal-context metrics + all `18` single-repeat differences) |
| [pilot-estimation-judging/intervention-log-audit-summary.json](pilot-estimation-judging/intervention-log-audit-summary.json) | Complete `5,357`-journal SDK tool, RPC, and permission-halt audit |
