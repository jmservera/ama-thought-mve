# Prospective S1 pilot / estimation protocol

**Status: original registration owner-confirmed approved on 28 October 2026;
subsequent corrected candidate awaits prospective OSF recording and exact
source-bound approval. Study not authorised to run.** See
[the prospective clarification](prospective-corrections-2026-10-28.md).
This is the
active protocol for the owner's three-model amendment to the paper. It supersedes the
seven-hypothesis proposals preserved in the other historical protocol notes.
It is not a retrospective amendment to earlier data or `protocol-frozen`.

## Source and scientific scope

Aligned to [main.tex at 196b976](https://github.com/jmservera/ama/blob/196b97644bb9bffa43d41a9921d6a06a93b2699e/docs/capstone/thought-leadership/everything-but-the-software/main.tex),
especially its experiment, prospective-decay and pre-run sections.
[pilot-estimation.json](pilot-estimation.json) records the exact source SHA-256,
baseline/tag provenance, settings, owner choices and outstanding evidence.
[osf-preregistration.md](osf-preregistration.md) is the submission draft.

The AMA case motivates the question; it does not measure a decay rate or show
that consolidation would have fixed missing deployment identity/staff bindings.
This pilot asks whether scheduled consolidation improves the repository
inherited by later feature work. It does not test the five case mechanisms.
The owner amended the paper's single-model/four-per-arm allocation on 27 October:
use GPT 6.1 Sol, Sonnet 5.5 and Gemini 4 Argon with two trajectories per arm/model.
This tests robustness across selected models; it cannot establish that model
choice is irrelevant or generalise to every model.

## Allocation, stages and resources

The unit is one fresh S1 repository trajectory: A feature-only, B feature plus
consolidation, C feature plus read-only review. For each of the three models,
two independent trajectories per arm, ten features F1-F10 and full held-out
CR1: **18 pilot trajectories**. Every model runs every arm.
Interleave arm order within model/replicate blocks using fixed seed 2027 on the same
machine; steps, hidden tests and checkpoints are not independent replicates.
No new run is added or substituted because an effect is favourable, a run is
assisted, a feature fails, or an interval is wide.
Replicate numbers are unique within each arm/model pair and intentionally
repeat across other arms/models; steps are not additional replicates.

| Collection | CLI phase | Runs | Sessions | Maximum agent-hours |
|---|---|---:|---:|---:|
| Excluded budget calibration | `calibration` (legacy `pilot`) | 1 per arm/model: 9 | 150 | 60 |
| Estimation pilot | `pilot-estimation` (legacy `first`) | 2 per arm/model: 18 | 318 | 133.5 |
| Combined resource envelope, never a pooled dataset | separate identities | 27 | 468 | 193.5 |

The estimation pilot has 180 feature, 60 consolidation, 60 review and 18 CR1
sessions. Limits are 30 minutes per feature, 15 per post-step, 45 per CR1.
These are planned sessions, not a maximum call count: an allowed infrastructure
retry can add a call but shares the original step's aggregate time/credit allowance.
B-A adds up to 50% feature-cycle agent time; B-C matches post-step ceilings,
not realised resources or editing permissions. B may add behaviour-pinning
tests and writes DESIGN.md (at most 300 words); C may only write REVIEW.md.
Neither contrast identifies pure refactoring or an equal-total-budget effect.

Model candidates are `gpt-6.1-sol`, `claude-sonnet-5.5` and `gemini-4-argon`.
On 28 October the owner selected a prospective current-toolchain amendment: CLI 1.0.105,
Ruff 0.17.3, Lizard 1.24.3 and jscpd 5.4.1, with medium effort still a candidate.
This replaces the earlier CLI 1.0.103/Ruff 0.17.2 candidates; it does not establish
model entitlement or actual effort behavior. Verify exact availability, compatible
reasoning settings and one frozen runtime before collection. AI credits are primary;
tokens, elapsed seconds and currency are separate. The combined prospective
calibration/pilot ceiling is **300,000 AI Credits**, including prior spending.
The original registered nominal allowance is 300/session, not guaranteed billing
control. On 29 October the owner accepted residual soft-limit overshoot risk.
The supplied operational settings use a uniform **10% buffer: 270 credits per
original session** (including any infrastructure retry) and **270,000 local
study admission**, leaving 30,000 below the unchanged registered envelope.
An in-flight response can finish over the CLI limit; neither buffer guarantees
actual billed consumption. The company hard limit of 1,000,000/collaborator is
owner-reported, not independently verified or a study-specific stop. A separate
provider study hard cap is no longer required. Known prior 17.59833 (historical
smoke 14.54324 plus excluded backend checks 3.05509), calibration,
probes and all attempts count; billing-cycle resets do not reset study spending.
Record [the prospective addendum](prospective-corrections-2026-10-28.md) before
affected collection. Financial-risk acceptance waives no runtime/access,
agent safeguard, runtime/access acceptance or freeze gate.
The owner's approximately $3,000 equivalent is
unverified; it is not a conversion or separate precise monetary ceiling.
After calibration, require a cost-only affordability check of the full unchanged
design; halt and amend if unaffordable rather than silently shrink the sample.
No paid backend is enabled by this protocol or by a completed registration.

The controller implements the model matrix, immutable assigned-model/replicate
identity, 270,000-credit local admission stop and bounded infrastructure retries;
analysis exports primary estimates separately per model. The default finite
study deadline is 14 days, not a change to the original agent-step allowances.
`required_evidence.multi_model_harness_alignment` was explicitly owner-accepted
for `90e393e` on 30 October, together with the other five scientific scopes.
Passing offline tests alone is not that acceptance or submission approval.

## Preregistration versus collection readiness

On 28 October 2026 the owner authorised separating ordinary OSF submission
from permission to collect data. Independent review is **not required by OSF**
for this preregistration. On 30 October the owner prospectively replaced the
project's independent scientific acceptance prerequisite with documented owner
review for this initial exploratory pilot. All six scientific scopes were
individually accepted for `90e393e`; independent review is deferred and must
be disclosed as absent, not completed. A separate experiment operator offers
operational separation, not independent scientific validation. See
[the acceptance record](scientific-acceptance-2026-10-30.json).
Runtime/access acceptance remains pending. Record this policy change in the
existing registration before affected collection; do not alter original assets.

Submission requires a complete consistent plan, recorded owner choices,
secondary scope, prior-data disclosure and actual final source-bound owner
approval. See [the OSF checklist](osf-submission-checklist.md).
The owner has now explicitly approved source content at 235489c plus the
selected metadata/approval updates, reconfirmed the data inventory unchanged
and selected CC BY-NC-ND 4.0 for submission documents with embargo through
2026-12-31. Contributor details will be entered directly in OSF; no additional
preregistration approvals were reported as required. This is not a study launch.
`submission_unresolved` (also exposed as `unresolved`) lists only those blockers;
`collection_unresolved` retains all outstanding methodological/operator evidence
and panel acceptance. Registration alone never authorises execution.

## Procedure and information boundaries

Fresh session per feature/post/CR1 step, with repository context only. Visible
examples are copied by the runner, checksummed and restored on tampering.
Only green committed increments are retained. Undelivered features are reset
and their examples removed (`drop_examples`); hidden tests stay in the cumulative
denominator. Failing retained B heads are reset; C edits outside REVIEW.md are
rejected. Retain rejected/reset-attempt records separately from repository losses.

Record external hidden results immediately after feature F_t and post-step P_t;
in A, P_t = F_t without an extra session. End state is final P_10 before CR1.
CR1 text and tests must be withheld until its dedicated session. Actual local
hidden/reference/CR1 access and subsequent evaluator-score/message visibility
must be independently checked; temporary environments are not OS isolation.

The prospective isolated-backend candidate uses repository-local Copilot SDK
1.0.28 with explicit CLI1.0.105/protocol3 on the trusted host and only a restricted
no-network container tool. Candidate tests and hidden/metric evaluation run in
separate containers, not host subprocesses. See
[the runtime clarification](prospective-corrections-2026-10-28.md#29-october-runtime-implementation-isolated-sdk-candidate)
for canonical committed checkpoints, C's REVIEW exception, resource/process-state
differences and protected-supervisor/oracle limitations. Exact-source offline
evidence does not replace actual model/effort/routing/usage validation,
owner scientific acceptance or owner freeze/launch authorization.

The owner selected continuation: after an unsuccessful feature attempt, B/C
still receive their scheduled post-step on the retained green state without
replaying the discarded feature request. Continue later features and CR1;
incidental recovery within ordinary permissions/budgets is allowed, but no
make-up attempts or replacement trajectories.

Agents see specifications and approved visible examples only; hidden scores,
identifiers, messages and reference solutions are never fed back. Permit at
most one documented infrastructure-only retry per step from its pre-attempt
snapshot within the original aggregate step time/credit allowance. Record all
attempts and costs; poor performance never justifies a retry. Retry an
infrastructure-failed measurement once on the unchanged snapshot; contradictory
valid outcomes halt collection for oracle investigation. Exhausted observations
remain missing. Logged infrastructure administration is permitted, but no code
fixes, hints or design advice. Flag/retain any content-assisted trajectory and
costs; never silently replace it or use a reduced complete-case primary frame.
Only documented terminal agent-caused inability makes an unattempted CR1
unsuccessful; infrastructure/uncertain absence remains missing with bounds.

The owner-approved subsequent correction distinguishes positively established
candidate-caused nonpasses from unavailable measurement. Declared missing
candidate APIs/imports, source-loader-bound syntax failures and established
product exceptions are failed outcomes with raw private provenance retained.
Infrastructure/oracle/unclassified causes remain unknown, not automatic
nonpasses. The exact shared runner policy and its prospective-recording status
are specified in [the correction notice](prospective-corrections-2026-10-28.md).
This preserves the fixed denominator and existing genuine-missingness rules.

## Endpoint hierarchy and estimands

**H1, practical coverage:** final cumulative hidden pass rate, with every scheduled
feature in its denominator. Show all run values/ranges and B-A/B-C differences
of run-level means. Coverage combines acquisition, retention and repair; it is
not itself decay. Missing final checkpoints are unavailable, not last-observed
endpoints. A smaller incomplete implementation is not necessarily better.

**H2, retained-contract loss:** use a reviewed, source-hashed hidden contract
panel, eligibility/oracle versions and feature groups. At cycle t the inherited
risk set is eligible, unchanged contracts passing at any earlier end-of-cycle P.
At both F_t and P_t report eligible/ever-passed/never-passed/currently-passing
counts, risk-set size, open loss count and density. Empty risk sets have
undefined density. Never-passing contracts are acquisition failures, not losses.
A new contract passing F_t but failing P_t is a separate same-cycle post loss.
Retain onset, recovery, recurrence and duration in feature cycles; repairs do
not erase episodes. Missing observations cannot create loss/recovery events;
episodes spanning them are explicitly uncertain/censored. Longitudinal H2
uses inherited open losses at P_t, with accumulated test-cycle losses as a
descriptive companion. The final H2 contrast is the difference in P_10 open-loss
counts, not accumulated test-cycle losses. A zero A loss baseline has no relative-reduction denominator.
Counts, densities and acquisition coverage must be interpreted together.
Test-weighted counts are not independently replicated capabilities.

**H6, CR1:** success requires all CR1 hidden tests and retention of every
feature test passing before CR1. Both allocated trajectories per arm/model belong in
the denominator. Explicitly adjudicated agent-caused terminal inability is a
failure; infrastructure-caused/unclassified unobserved outcomes are missing.
Show success and missing counts and lower/upper outcome bounds. With missing
outcomes, no complete-case risk-difference point estimate is substituted.
For complete outcomes, show B-A/B-C absolute risk differences. Equal-tailed
97.5% Clopper-Pearson component intervals per arm within model, subtracted at opposite
endpoints, give at least 95% coverage **per comparison**, not family-wide.

H1 and CR1 use their own valid final observations. An earlier unobserved
measurement can make the H2 history incomplete without erasing a valid final
coverage/CR1 outcome. Missing final observations themselves remain unavailable.

**Resource counterbalance:** report actual delivery-through-P_10 and CR1
consumption separately, all attempts including failures/stops/assistance.
Unspent allowance is not expenditure. Zero CR1 cost needs affirmative evidence
of no charged session; absent billing is missing, never zero. All-attempt cost
is primary; successful-run CR1 cost is conditional secondary and undefined
when no run succeeds. Cheap failure is not efficiency.

Standalone `analyze.py --study-state PATH` validates the journal's phase and
full selected allocation before counting all attempts. Without this explicit
matching evidence, measured-step cost is descriptive and all-attempt cost
unavailable. An empty attempt sublist is not presumed zero billing.

Primary contrasts require the full allocated unassisted frame. Retain assisted
runs and all costs in disposition tables, report their outcomes separately and
make the affected unassisted contrast unavailable rather than replacing them.
Actual help and requests for help are distinct; missing intervention coverage
is not evidence that a trajectory was unassisted.

## Secondary measures, uncertainty and rival patterns

H3 structural metrics and H5 cost/slope thresholds are not pilot verdicts.
Formal H4 joint size/accuracy/time and H7 dependent half-gap claims are deferred;
no non-inferiority margin or replacement threshold is invented.
The owner deferred comprehension assessment; this pilot makes no
comprehension-effect claim. On 28 October the owner explicitly excluded HIR/IDR
outcomes from this pilot; their report fields remain unavailable, never zero.
This does not waive assistance/intervention logging, CR1-help records,
unassisted-comparison eligibility or primary usage/cost coverage.
See [readiness-handoff.md](readiness-handoff.md) for the recorded scope decision
and remaining reviewer/operator evidence.

Structural metrics use frozen lizard/ruff/jscpd settings and raw trajectories.
Reference gaps require accepted cumulative reference versions under the
disclosed owner-review policy,
matching metric backends/settings and compatible complete feature coverage.
Unavailable/mismatched reference evidence cannot yield a gap or a composite score.
Require three unchanged reference executions at every feature stage and CR1,
with exact outcome agreement and all expected tests passing. Discrepancy blocks
fresh collection until investigated, versioned and revalidated, not rerun until
green. This alone does not substitute for explicit owner suite/panel acceptance.

Offline diagnostics can be reproduced without collecting trajectories:

```bash
.venv/bin/python -B harness/validate_suite.py suites/s1-retrofit --repeats 2 \
  --reference-metrics .study/reference-metrics-diagnostic.json \
  --complexity internal --duplication internal --lint none
```

Create `.study/` first if absent. Two repeats and internal backends here are
**diagnostic settings**, not an author-approved final oracle rule or compatible
production reference baseline. Metrics remain unaccepted; do not calculate
reference gaps against lizard/jscpd/ruff runs from these internal results.

Show all eighteen values/ranges and model-specific B-A/B-C estimates first.
Each arm/model has two independent trajectories. Any overall summary is
exploratory with equal model weights, not a silently pooled primary contrast.
Primary eligibility is assessed within each full allocated unassisted model
frame: an incomplete or assisted model does not disable eligible other models.
Overall allocation/unassisted flags audit the full design; per-model frame flags
identify eligibility, and an overall primary-availability flag means at least
one model is eligible. Individual endpoints still require their own observations.
Coverage/cost intervals use 10,000 whole-run resamples within arm within model,
seed 2027, pointwise 95% percentile
bounds; fewer than two observations/arm or any undefined draw makes the affected
interval unavailable. Never discard undefined draws. These are small-sample
feasibility estimates, not stable precision claims. No formal verdict, mixed-model
significance, power simulation or family-wide interval coverage is claimed.
Stable retention/no reference excess is no observed decay under this workload;
better final coverage alone is improved implementation, not proved decay control.

## Prospective provenance and release gates

Preserve the historical `protocol-frozen` tag at
`20e7f97c5c162cffd0f771ce501e146081912edc`; it does not authorize this amendment.
The baseline containing earlier proposals is
`1fee4535dd65ccedcee9638ef3a77ff3f9ce12a2`.
Earlier [smoke evidence](../results/smoke/summary.md) describes `smoke-01`,
S1/B/F1 plus consolidation and observed 14.54 credits. Its metadata says pilot;
it is neither ten-feature calibration nor a replicate among the eighteen.
Stub runs, historical paid smoke and any earlier calibration/registration
attempts must retain actual dates, labels and data-exposure history. On 28 October
the owner confirmed the disclosed-only inventory; no additional model runs or
calibration/pilot trajectories were reported. The smoke alone does not establish
completeness or absence of earlier exposure. No existing results are relabelled or pooled. The owner confirmed the registered
cohort has not run and will start only after registration. Earlier manual work
was unmeasured; the measured smoke is disclosed as excluded development
diagnostics. Its exact collection/exposure dates remain unverified; the summary's
Git commit date is not a substitute. [The prior-data disclosure](prior-data-disclosure.md)
records exact repository dates in original offset/UTC, observed outcomes and
explicit historical event-time uncertainty. Unrelated
[hve-squad benchmarking](https://github.com/Peter-N91/hve-squad/pull/212)
is not this study's data or validation evidence.

Before submission, confirm recorded owner choices, secondary scope and prior
exposure, approve the final protocol/source/hash snapshot and disclose reviews
and operational checks as pending. Do not fill null evidence fields without
genuine evidence. Upload only the approved submission inputs and complete the
actual OSF contributor-approval/submission workflow. Record its real URL/date
afterward. Independent suite/panel, oracle/reference and multi-model alignment
acceptance remain required before collection, together with runtime/access,
budgets/telemetry, approved freeze and the accepted buffered soft-limit policy
above. A separate study-specific provider hard cap is no longer required.
If review changes substantive methods, document the amendment prospectively in
OSF and version affected inputs before collecting affected data. None of these
approvals or controls is fabricated by offline tools.
Later replication/S2/precision work requires its own prospective plan.
