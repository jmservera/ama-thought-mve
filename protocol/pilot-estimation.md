---
title: Prospective v5 five-arm fixed-sample protocol
description: Model-blocked coverage comparison, fair resource matching and pending readiness
ms.date: 2026-11-01
---

**Status: offline candidate, not reviewed/frozen/registered for v5 collection.**
Changed execution inputs invalidate v4 acceptance for this candidate. Preserve
the historical v4 manifest/tag, critiques, acceptance records, prior data and
original OSF attachment unchanged. The [JSON ledger](pilot-estimation.json)
retains actual historical flags and separate pending prospective requirements.
[The v5 amendment](prospective-v5-2026-11-01.md) must be recorded prospectively
before affected collection. No approvals, new observations or dates are inferred
from this implementation.

## Source and scope

The title remains *Feature-Driven Decay in an Agentic Coding Loop*. Historical
cloud/sign-in/usage exports are explicitly owner-deferred; the critique uses
repository evidence only. No new live-export reconciliation is claimed. Prior
credits/holds and prospective complete billing/model/assistance gates remain.

S1 is a synthetic ten-feature retrofit workbench, motivated by AMA, not a
measurement of historical AMA decay or proof that consolidation repairs its
deployment/identity problems. Prior paper alignment is historical provenance;
the parent manuscript's changed source requires its own exact-source review.
This candidate tests treatment packages, not a pure refactoring mechanism.

The experimental unit is one fresh repository trajectory. Features, checkpoints
and tests are repeated/within-run observations, not independent replication.
Models are the three selected candidates: `gpt-6.1-sol`,
`claude-sonnet-5.5`, `gemini-4-argon`; medium effort, SDK1.0.28/CLI1.0.105.
Actual access/model/effort/routing/billing must be verified separately on the
exact frozen runtime. No model session is run by this implementation.

## Arms, released information and permissions

| Arm | Feature allowance | Post allowance | Package |
| --- | --- | --- | --- |
| A | 30min / nominal300 / soft270 credits | None | Feature-only |
| B | 30min / nominal300 / soft270 | 15min / nominal300 / soft270 | Behavior-preserving consolidation, specification-derived tests, DESIGN.md |
| C | 30min / nominal300 / soft270 | 15min / nominal300 / soft270 | Read-only review; REVIEW.md can affect later feature work |
| D | 45min / nominal600 / soft540, one session | None | Matched-resource A+ builder |
| E | 30min / nominal300 / soft270 | 15min / nominal300 / soft270 | Visible regression-repair package, no new capabilities |

All CR1 allowances are 45min / nominal300 / soft270. D matches B's complete
feature-cycle ceilings, but differs in session segmentation, editing instructions
and treatment content. D is not two builder replays. B-C matches ceilings, not
editing permission or realized consumption. B-A includes additional resources.
E-B/E-D contrasts are descriptive packages, not effects of hidden feedback.

Every arm gets only current/previous immutable feature specifications and approved
visible examples. Released originals are retained in `specifications/`, including
example copies outside the green-only test path. No arm, including E, receives
hidden scores, test identities/messages, reference/hidden files, future feature
specifications or CR1 text before its session. Evaluation and its private outputs
remain outside candidate containers. A protected operator may possess those
assets; candidates may not. Candidate tools have no network/credentials; necessary
trusted host SDK provider network is distinct.

B must check behavior-pinning expectations against a numbered immutable visible
specification, not bless an existing defect. New test-file evidence binds actual
before/after file SHA-256, specification SHA-256 and rule/rationale in
TEST_EVIDENCE.json. Existing accepted Python test files are frozen in full,
including imports, fixtures and module/class constants; additions use new files.
Later B feature sessions must keep accepted tests green and
not alter their definitions. A visible contradiction is documented, not repaired
or silently legitimized during B consolidation.

E may repair previously specified behavior, without future specifications or new
capabilities. E may correct an agent-authored test only when it contradicts an
immutable released specification, recording actual code/test diff and old/new
behavior evidence in REPAIR_EVIDENCE.json. Immutable examples/specifications
are never correctable. Evidence locator validation is not semantic approval;
independent fidelity review remains pending.

Every feature session commits only green work; unsuccessful delivery rolls back
under the existing visible-test policy. B/C/E post-steps still run on retained
state after a completed failed feature attempt. No poor-outcome retry or make-up
session. C can retain only REVIEW.md; quality/cache artifacts do not grant editing
permission. B/E retain only green, visible-source-preserving work within scope.
Notes are at most 300 words. Uncommitted work is discarded.

## Prospective sample calculation

Primary comparison: absolute final coverage difference **B-D**, equally weighting
the three model blocks. Two-sided alpha .05, power .80 and minimum useful gain
**10 percentage points** are fixed before outcomes. Within-cell final-score
SD **25pp is a planning ASSUMPTION**, not an observed estimate.

For M=3 equally weighted models and n independent trajectories/arm/model,
Var(B-D)=2*SD^2/(M*n). Normal planning uses:

```text
n = ceil(2 * SD_pp^2 * (z_(1-alpha/2) + z_power)^2 / (M * delta_pp^2))
  = ceil(2 * 25^2 * (1.95996398454 + 0.84162123357)^2 / (3 * 10^2))
  = ceil(32.7036655598) = 33
```

Thus **33/cell, 495 trajectories** across all five arms and three models.
`harness/feasibility.py` computes/verifies the calculation rather than relying
on a bare hardcoded sample.

| Planning SD, pp | Trajectories/arm/model | Total five-arm trajectories |
| --- | ---: | ---: |
| 15 | 12 | 180 |
| 20 | 21 | 315 |
| 25 | 33 | 495 |
| 50, worst-case population SD for bounded0-100 score | 131 | 1965 |

This is normal planning, not completed empirical power simulation or protection
against arbitrary non-normality. CR1 binary success is secondary and **not
powered by this coverage calculation**. No claim that its interval is necessarily
informative. Report observed pooled within-cell variance/SD and residual df:
complete five-arm df480, B/D-only df192. Partial observed variance retains
observed/planned df and missingness; it never authorizes resizing.

Fix all allocations before outcomes. No outcome-driven additions, replacements,
cherry-picking, assisted-run substitution or silent sample reduction. Schedule
seed2027 interleaves arms within model/replicate blocks and rotates model order
on the same machine. Assigned model/arm/replicate and source/config persist on resume.

Excluded calibration is **one trajectory/arm/model (15)**, no CR1, cost-only.
Do not examine calibration outcomes to select n, models, arms, prompts or requests.
All calibration/prior/attempt charges count; calibration is never pooled with
the fixed study.

## Resources and proposed feasibility go/no-go

| Phase | Runs | Feature/post/CR1 sessions | Total sessions | Maximum hours | Nominal caps | Soft-cap sum |
| --- | ---: | --- | ---: | ---: | ---: | ---: |
| Fixed study | 495 | 4950 / 2970 / 495 | 8415 | 3836.25 | 2821500 | 2539350 |
| Excluded calibration | 15 | 150 / 90 / 0 | 240 | 105 | 81000 | 72900 |
| Combined, separate datasets | 510 | 5100 / 3060 / 495 | 8655 | 3941.25 | 2902500 | 2612250 |

**Worst-case caps exceed** the unchanged nominal **300000** envelope and
**270000** local admission ceiling. Known prior21.79019 and historical holds1200
leave **268778.20981** before calibration. Holds are unknown provisions, not
certified spending. Every attempt counts. New unknown usage and reservation
overshoot block new work; neither soft buffer guarantees actual billing.
There is no verified credit/currency conversion. The owner-reported company
1000000/collaborator cap is not independently verified study enforcement.

Original infrastructure retry is at most once, from the original checkpoint,
sharing remaining original time/soft credits. D retains its original single
2700-second/540-credit feature allowance across all retries. Measurement retry
uses the same immutable snapshot, never another agent replay. Stop below the
SDK's30-credit minimum rather than top up. The whole-study deadline is14 days;
maximum CR1 hours alone371.25 exceed its336 hours. No feasible deadline or
complete allocation affordability is asserted.

These are **prospective proposed thresholds, not completed approvals**:

* Failed infrastructure original steps at most5%.
* Missing primary measurements0.
* Oracle contradictions0 across all required triplicate references (33 executions).
* No information-boundary failure.
* Complete actual billing, assigned/actual model/effort and assistance evidence.
* Cost-only calibration supports all **495 unchanged trajectories** within
  remaining270000 admission, including calibration, known prior, holds and
  largest original reservation, and the approved remaining deadline.

The proposed deterministic projection uses every calibration cell, multiplier1.25
on feature/post cost/time, full CR1 soft/nominal cost and maximum time forecasts,
and600-credit largest-reservation headroom. Its conservatism is an assumption,
not an observed statistical/financial upper confidence bound. Verify the actual
calibration attempt/accounting journal and source hash, not just a supplied total.
The main ledger adds actual calibration spending exactly once; historical holds
and ongoing attempts remain separate.

If any threshold is unmet or unaffordable, **halt and prospectively amend before
affected collection**, never shrink n or replace trajectories. A calibration-only
freeze cannot authorize main collection. Budget risk acceptance waives no scientific,
boundary, billing, source-freeze, privacy or registration gate.

## Endpoint and missingness analysis

Final coverage is the fixed unchanged feature-contract panel at P10 before CR1.
Current panel:127 feature contracts and15 CR1 contracts. Coverage is test-weighted,
not equal-feature importance or proof of complete behavior. Use the exact panel
hashes and accepted mappings; its earlier owner review is historical, not new
independent v5 acceptance.

New `model-blocked-v2` primary estimation uses final run-level whole-trajectory
resampling within each model/arm cell,10000 draws/seed2027, equal model weights1/3.
Report pointwise95% percentile intervals and disclose their assumptions. The sole
primary contrast is B-D; per-model coverage, B-A, B-C and E-B/E-D are descriptive
secondary. Do not treat495*10 features as independent subjects. Retain every
allocation, outcome/missingness and assistance disposition. Content assistance
or unknown assistance compromises primary interpretation; do not replace/exclude
such trajectories silently. Missing final outcomes are unavailable, not earlier
values or failed outcomes absent explicit agent-cause evidence.

Historical `model-stratified-v1` is separately analyzed as A/B/C n2/cell,
18 trajectories. Retain its four pairwise cross-arm differences and pooled
within-cell SD/df9 diagnostics. A two-observation percentile bootstrap does not
establish nominal95% coverage. Do not relabel or reinterpret old data with33
replicates or five arms. Legacy unmarked data remain explicitly historical or
diagnostic, not inferred v2.

### Retained loss and CR1

Inherited risk contains unchanged contracts passed at an earlier P checkpoint.
Report full known risk, uncertain acquisition/history, observed risk and missing
risk separately. Loss density uses **observed inherited-risk outcomes only**;
missing outcomes never count as not lost in its denominator. Full-risk counts
and strict complete-history endpoints remain unavailable when incomplete.
Episodes preserve uncertain onset/recovery/duration and censoring.

CR1 binary success requires all fixed CR1 contracts plus every pre-CR1-passed
feature contract still passing. Documented terminal agent-caused inability can
be unsuccessful; infrastructure/oracle/unclassified absence remains missing.
Exact95% Clopper-Pearson intervals are per arm/model binary proportions when
every allocated binary outcome is known, not simultaneous/family-wide coverage.
Retain all-allocation identification bounds with missing outcomes.

Export graded CR1 tests passed/15 with observed/missing denominators, plus count
of pre-CR1-passed contracts lost, full/observed/missing risk and uncertainty.
Stratify CR1 by both/not-both/unknown F9/F10 prerequisite acquisition, defined
as each fixed F9/F10 group passing in full at an observed pre-CR1 F/P checkpoint
after its specification release. A missing acquisition opportunity remains unknown,
not never-acquired. Also report current P10 availability separately: previously
acquired prerequisites may have been lost. This is post-treatment selection;
conditional success cannot establish a causal repair effect or generalize to
unacquired prerequisites.

### Fidelity and telemetry

Structural quality budgets targeted by B are **treatment-fidelity checks**, not
independent efficacy outcomes. Ruff runs against fixed external policy with
`--isolated --ignore-noqa`; count newly added suppression lines/config changes.
Lizard complexity is not jscpd duplication. Candidate configuration/suppressions
cannot redefine the external score.

External C follow-through annotations need actual REVIEW.md head/line and
later-feature diff-hunk locators, rater/evidence and observed/unknown coverage.
File overlap alone proves no repair. Annotation locator checks are not semantic
or independent approval.

Record actually observable SDK API duration in milliseconds, logical-dispatch
latency, host wall/send wait and isolated tool roundtrips, with coverage.
Provider-active compute and rate-limit waits remain unknown where unavailable.
SDK/host latency must not be described as active compute or invented zeros.
HIR/IDR and comprehension efficacy remain deferred. All-attempt cost completeness
and assistance evidence remain mandatory.

## Protected adequacy and follow-up

Require exact triplicate unchanged all-pass reference vectors at all ten feature
stages and CR1; contradictions halt collection, not rerun-until-green.
The bounded reproducible mutation helper preselects up to24 expression mutants
at each protected f10/CR1 reference, runs hidden tests only on disposable copies
and reports generated/observed/killed/surviving/unavailable denominators and
unadjudicated equivalence. Survivors may be equivalent or gaps; no universal
adequacy claim. If unavailable, disclose it and leave acceptance pending.

[The prewritten randomized request pool](change-request-pool.json) is for the
**subsequent main study only**. Current fixed CR1, its examples/hidden tests and
references remain unchanged. Follow-up requests are randomized in matched
model/replicate blocks, released only at their assigned session, and require
separate prospective sample/difficulty/oracle review, OSF amendment and freeze.

## Privacy, registration and launch

On 2026-11-01 the owner selected `public-pr-now` after acknowledging both original
repositories remain public. The parent may publish development-source PRs now.
This does not authorize researcher-archive/results release, OSF or visibility
changes, or collection. Interim public source exposure, including protocol/oracle/
reference material, is a contamination limitation; future privacy cannot restore
an unexposed model or operator.

Researcher/operator archives remain intended for private trusted handoff.
The owner must make both original repositories private before experiment;
owner attestations/readback and no-operator-access-to-originals/paper checks are
pending. Private visibility cannot undo earlier public/model exposure. Protected
operator harness assets are permitted; candidate access is forbidden.

Proper prospective OSF registration/amendment and embargo are planned, not
completed by this candidate. Publication is planned only after collection and
paper release. Actual old OSF submitted/date flags and historical licence/embargo
choices are preserved; no new metadata or configuration is fabricated.
Final exact-source independent scientific/runtime review, current oracle/canary
and mutation review, model/billing/assistance, affordability/deadline, privacy/access,
new owner freeze and prospective OSF/launch evidence remain pending.
See [the OSF checklist](osf-submission-checklist.md) and
[private contributor instructions](../CONTRIBUTOR.md).
