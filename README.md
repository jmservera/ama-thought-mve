---
title: Feature-Driven Decay in an Agentic Coding Loop
description: Offline v5 candidate, fixed replication and source-bound collection blockers
ms.date: 2026-11-01
---

Experiment kit for *Feature-Driven Decay in an Agentic Coding Loop*.
On 2026-11-01 the owner explicitly selected `public-pr-now` after acknowledging
that `jmservera/ama` and `jmservera/ama-thought-mve` remain public. The parent
coordinator may publish development-source PRs now. This is not public
researcher-archive release, OSF action, visibility mutation or collection permission.
Interim public development-source exposure, including protocol/oracle/reference
material, is a contamination limitation, not proof that future models are unexposed.

Researcher/operator archives are still intended for private trusted handoff.
Before collection the owner must make both original repositories private and
supply visibility/access attestations, with no operator access to the original
repositories/paper. Those actions and readbacks remain pending. Private visibility
cannot undo past or interim public/model exposure.

**Status: offline v5 candidate only. No collection, paid calls, new acceptance,
freeze, prospective OSF amendment, visibility change or researcher-archive/
study-result release is authorized or completed by this work.** Development PR
permission is separate. Start with [the canonical protocol](protocol/pilot-estimation.md),
[machine-readable ledger](protocol/pilot-estimation.json),
[prospective v5 amendment](protocol/prospective-v5-2026-11-01.md) and
[OSF draft/checklist](protocol/osf-submission-checklist.md).

## The fixed prospective design

The unit is a fresh ten-feature S1 repository trajectory, not a feature or test.
All five arms run on GPT 6.1 Sol, Sonnet 5.5 and Gemini 4 Argon.

| Arm | Feature | Scheduled post | Nominal feature/post credits | Operational soft credits |
| --- | --- | --- | --- | --- |
| A | 30 min | None | 300 / 0 | 270 / 0 |
| B | 30 min | 15 min behavior-preserving consolidation, tests, DESIGN.md | 300 / 300 | 270 / 270 |
| C | 30 min | 15 min read-only review, REVIEW.md | 300 / 300 | 270 / 270 |
| D | 45 min, one A+ builder session | None | 600 / 0 | 540 / 0 |
| E | 30 min | 15 min visible-specification regression repair | 300 / 300 | 270 / 270 |

Every original CR1 session has 45 minutes, nominal 300 and operational 270
credits. D is a **single 45-minute feature session**, not a replay proxy. Its
infrastructure retries share the original 45-minute/540-soft-credit allowance.
There is no generic larger-cap bypass.

Primary: equal-model-weight blocked final-coverage **B-D**, with two-sided
alpha .05, 80% normal-planning power, useful absolute gain **10 percentage
points** and within-cell SD **25pp (ASSUMPTION, not observed variance)**.
The calculation yields 32.70366556, rounded up to **33 trajectories/arm/model:
495 total**. Sensitivity SD15/20/25/50pp requires 12/21/33/131 per cell.
The bounded-score worst case SD50pp would need 1,965 trajectories. This sample
is fixed before outcomes; no favorable additions, replacements, cherry-picking
or silent sample reduction.

| Phase | Trajectories | Original sessions | Maximum agent-hours | Nominal cap sum |
| --- | ---: | ---: | ---: | ---: |
| Fixed study | 495 | 8415 | 3836.25 | 2821500 |
| Excluded cost-only calibration, no CR1 | 15 | 240 | 105 | 81000 |
| Combined, never pooled | 510 | 8655 | 3941.25 | 2902500 |

These worst-case caps **do not fit** the unchanged 300,000 registered envelope
or 270,000 local admission stop. Known prior usage remains **21.79019 credits**;
four exact historical holds remain **1200 credits**, not certified spending.
Remaining local admission before new calibration is **268778.20981**.
The 14-day sequential deadline also cannot cover the stated maximum hours.
Cost-only full-sample feasibility and deadline evidence are pending. If
unfeasible, halt and prospectively amend before collection, **never shrink n**.
Soft limits allow in-flight overshoot; no guaranteed billed cap or currency
conversion is claimed.

## Offline commands, zero model calls

```bash
./run-study.sh --smoke --dry-run
./run-study.sh --smoke --study-id v5-offline-check
python3 harness/schedule.py --pass pilot-estimation --seed 2027
python3 harness/feasibility.py --out .study/v5-planning-NEW.json
./run-experiment.sh --dry-run
```

Smoke runs one feature in each A/B/C/D/E, eight original fake-agent sessions,
without CR1. It exercises progress, rollback, visible source protection,
measurements, deterministic reports and durable resume. Stub/reference data
are diagnostics, not observations of model performance.
Use a new diagnostic ID after execution inputs change; never overwrite prior
evidence. A live dry-run returns nonzero while readiness is blocked.

[CONTRIBUTOR.md](CONTRIBUTOR.md) specifies pip-based external validation setup,
the repository-local SDK, offline tests and private hash-verified handoff.
[RUNBOOK.md](RUNBOOK.md) defines phase/deadline/accounting recovery.

## Measurement and interpretation

* New `model-blocked-v2` inference resamples whole trajectories within each
  arm/model and uses equal model weights. Per-model outcomes, B-A/B-C and E-B/E-D
  are descriptive secondary. All allocations, missingness and assistance remain.
* Binary CR1 is secondary, not powered by coverage planning. Exact Clopper-Pearson
  intervals are per arm/model, not family-wide. Reports include tests passed/15,
  pre-CR1-passed contracts lost, observed/missing risk denominators and F9/F10
  prerequisite strata with post-treatment selection limitations.
* Ruff uses fixed external `--isolated --ignore-noqa` measurement. Lizard
  complexity and jscpd duplication are distinct fidelity targets, not independent
  efficacy endpoints. Added suppressions/config edits are recorded.
* C's notes can affect later feature sessions. External follow-through annotations
  need real review/diff locators; file overlap is not proof of repair.
* SDK request/dispatch latency and host/tool timing are recorded when observable.
  Provider-active compute and rate-limit waits remain unknown, never invented zeros.

## Preserved history and pending source requirements

The owner deferred historical cloud, sign-in and usage exports; the critique
uses repository evidence only. This is not live-export verification or new
billing reconciliation. Known prior/holds and all prospective billing/model/
assistance requirements remain unchanged.

[protocol/freeze.json](protocol/freeze.json) and `protocol-frozen-v4` are
unchanged historical evidence. Changed v5 inputs invalidate their applicability.
The active controller points to **absent/pending `protocol/freeze-v5.json`**;
this work does not create a freeze or tag.
The original [OSF registration](https://osf.io/ywsrv/) remains owner-confirmed,
not independently verified; its actual old submitted flag/date are retained.
The new prospective amendment remains false/unset.

Historical scientific/runtime acceptance, critiques, prior-data disclosure,
results and protocol snapshots are retained unchanged. Historical
`model-stratified-v1` means A/B/C, n=2/cell (18 trajectories), not v2.
Its four cross-arm pairwise differences and pooled within-cell SD/df9 remain
diagnostics; a two-observation percentile bootstrap has no nominal 95% claim.

Independent exact-source scientific/runtime review, new containment/oracle
evidence, mutation review, billing/model/assistance evidence, numerical feasibility,
owner privacy/access readback, prospective OSF amendment and owner freeze/launch
authorization are all pending. The [prewritten randomized change-request pool](protocol/change-request-pool.json)
is for a subsequent main study only; current fixed CR1 is unchanged.
