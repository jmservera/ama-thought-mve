# OSF Preregistration submission draft

**DRAFT - not submitted, not registered, not author-approved.**
Use the general-purpose **OSF Preregistration** form. Field wording may change:
transfer these answers into the live form and attach the approved protocol,
decision ledger, candidate contract panel and checksums. The panel is not
independently accepted. Follow [the submission checklist](osf-submission-checklist.md);
do not upload private session logs or the private reviewer bundle.

## Metadata

**Title:** Scheduled consolidation during agentic feature delivery:
an eighteen-trajectory, three-model S1 pilot/estimation study.

**Contributors, affiliations, licence, registration visibility/embargo:**
owner to complete in OSF. Do not infer coauthor participation or endorsement.

**Description:** We compare feature-only delivery (A), consolidation after each
feature (B), and read-only review (C), fully crossed with GPT 6.1 Sol, Sonnet 5.5
and Gemini 4 Argon: two independent trajectories per arm/model, eighteen
ten-feature S1 trajectories in total. The pilot estimates final behavioural coverage,
retained-contract losses, final CR1 success and consumption; it checks feasibility,
variation and failure modes for a later separately planned study. Consolidation
includes extra resources, permission to edit/add tests and a different note.

## Registration type and existing data

Prospective **pilot/estimation** preregistration, not a confirmatory seven-test
study or a registered report with journal acceptance. The intended eighteen-run
cohort has not been run by this work.

**Data already exist:** yes, separate development diagnostics exist. Tracked
`results/smoke` covers historical paid `smoke-01` (B, F1 plus consolidation,
14.54 credits) and discloses observed performance/usage; its stored phase label
does not make it an estimation replicate. Offline reference/stub diagnostics
also exist and their outcomes have been used to check tooling. Neither is pooled
into the eighteen trajectories. The owner confirmed on 27 October that the
registered study has not run and will start only after registration; earlier
manual work was unmeasured, and the measured smoke is disclosed as excluded
development diagnostics. On 28 October the owner confirmed this disclosed inventory is complete, with no
additional model runs or calibration/pilot trajectories reported. The first
smoke artifacts are recorded in Git at `c5184c5`, 25 October 2026
00:53:50 +02:00 (24 October 22:53:50 UTC). Subsequent README/RUNBOOK
commits record interpretation and exclusion. These are repository dates, not
actual collection or first-inspection timestamps; those historical event times
remain unverified. [The full disclosure](prior-data-disclosure.md) records
the evidence and uncertainty, including offline reference outcomes used to
revise tooling. No outcome-blind development process is claimed.
Unrelated [hve-squad benchmarking](https://github.com/Peter-N91/hve-squad/pull/212)
is not this MVE's data or validation evidence. Reconcile this disclosure with
actual artifacts before signing the live existing-data answers.

No timestamp, lack of prior exposure, complete calibration or registration is
asserted from a local draft, manuscript statement or historical Git tag.

## Review status and preregistration policy

This plan has **not received independent scientific acceptance**. Suite/panel,
oracle/reference metrics and multi-model alignment reviews remain pending.
Model/runtime entitlement, effort/routing/accounting and actual information
boundaries remain unverified. Ordinary OSF preregistration records the plan;
it does not require independent scientific peer review or certify validity.

On 28 October the owner authorised submitting the plan with this disclosure
after final source-bound owner approval. The project retains all outstanding
review and operational checks as prerequisites before calibration/pilot
collection. No checks are marked accepted merely to prepare or submit this
registration. Any substantive method changes arising from review will be
documented prospectively in OSF and versioned before collecting affected data.

## Questions, hypotheses and endpoint hierarchy

There are **no formal pass/fail hypotheses for this pilot**. H1/H2/H6 retain
traceability labels: what behaviour remains; whether previously passing
unchanged contracts are lost/recovered; whether the final repository absorbs CR1.
Resource use is the practical counterbalance. Formal H4/H7 claims are deferred;
structural metrics are descriptive secondary scope subject to their evidence
gates. The owner explicitly excluded HIR/IDR outcomes on 28 October;
unavailable fields are not zero intervention. Comprehension assessment is deferred; no comprehension-effect
claim will be made.
Earlier numeric thresholds do not decide adoption or seven hypothesis verdicts.

## Study design, sampling and randomisation

Controlled repeated-trajectory software experiment; synthetic data, one S1
suite, three deliberately selected model candidates: `gpt-6.1-sol`,
`claude-sonnet-5.5`, `gemini-4-argon`. Two fresh repositories per A/B/C arm
within each model, ten sequential features and full CR1: eighteen independent
units. Arm order is randomised within model/replicate blocks, seed 2027. Same machine,
skeleton, specifications, tools and feature budgets. B adds consolidation and
C adds read-only review; B-C is not pure refactoring or equal realised compute.

Separate budget calibration: one trajectory per arm/model (nine total), ten
features, no CR1, excluded from the eighteen. CLI `calibration`/legacy `pilot` refers to this
excluded stage; `pilot-estimation`/legacy `first` refers to the eighteen.
The three-model/two-per-cell design is an explicit owner amendment to the
paper's original single-model/four-per-arm pilot. Replication tests robustness
to these models, not independence from model choice or all-model generality.
No optional stopping, outcome-based replacements or sample enlargement.
All incomplete, assisted, failed and unattempted allocated trajectories remain.
Owner choices are recorded in the attached ledger: continue scheduled work,
including B/C post-steps on retained green state after unsuccessful feature
delivery, with no replay/make-up; incidental recovery within existing step
permissions is allowed. At most one documented infrastructure-only retry per
step from its pre-attempt snapshot may use the remaining original aggregate
step budget; all attempts/charges count. Poor outcomes never justify retry.
Retry an infrastructure-failed measurement once on the same immutable snapshot;
contradictory valid outcomes halt collection for oracle investigation.
Final source approval is still required before submission.

## Blinding and inclusion/exclusion

Agents cannot be blinded to their assigned post-step prompt. Evaluator outputs
are external and never fed back: no hidden scores, identifiers, messages or
reference solutions. Only specifications and approved visible examples are
available; CR1 is withheld until its dedicated session. Verify actual access;
do not claim OS isolation for local execution. The owner deferred comprehension
assessment; no comprehension-effect claim will be made.
Only logged infrastructure administration is permitted, with no human code
fixes, hints or design advice. Flag any content-assisted trajectory and retain
all data/costs. HIR/IDR outcomes are excluded; assistance/intervention logging,
unassisted eligibility, CR1-help records and primary cost coverage remain required.

No trajectory is excluded for poor outcomes. Assisted trajectories are retained
and labelled; their data/costs are shown separately from the unassisted comparison,
which can become unavailable at its allocated size. Missing feature tests remain
in H1's scheduled cumulative denominator. Infrastructure absence is not a failure
unless a prospectively agreed rule and event evidence establish that classification.

## Manipulations and measured variables

Fixed prompts, limits and enforcement: see `pilot-estimation.md`.
H1: final P_10 hidden coverage. H2: F/P unchanged-contract risk sets, losses,
densities and episodes from the reviewed eligibility map. H6: CR1 success
preserving pre-CR1 passing tests, and all-attempt cost.
Show eligible/ever-passed/never-passed/currently-passing counts and feature groups;
separate new acquisition failures and same-cycle post losses.
Credits primary; tokens/seconds/currency separate. Failed, stopped, assisted and
unmeasured attempts remain in resource accounting; unknown is not free.
Secondary metrics use frozen settings, reference-compatible raw gaps and
descriptive ranges; no unvalidated composite decay score.

## Analysis, transformations, missing data and inference

All run-level outcomes/ranges precede model-specific B-A and B-C differences.
Each arm/model has two trajectories. Any equal-model-weighted overall summary
is explicitly exploratory, not a silently pooled primary contrast. No feature or
test is an independent inference unit. H1 and resource comparisons use mean
differences and pointwise whole-run bootstrap intervals within arm within model
(10,000 draws, seed 2027).
Insufficient strata or any undefined draw makes the affected interval unavailable;
do not discard undefined draws or impute last-observed final outcomes.
Two runs/arm/model permits only very limited feasibility/variation estimates,
not stable precision or a completed power simulation.

H2 reports paired F/P histories; inherited risk requires a pass at an earlier P.
Its final contrast uses P_10 open-loss counts; accumulated test-cycle losses
are separately labelled descriptive. Earlier missing measurements do not erase
otherwise valid final H1/CR1 observations; their own required missing checkpoints
still make the endpoint unavailable.
Empty risk-set density is undefined; missing outcomes never become passes,
losses or recoveries. Preserve episodes and uncertainty over outages.
No relative reduction when A's loss denominator is zero.

CR1 denominator: all allocated runs. Adjudicated agent-caused terminal inability
is unsuccessful; unobserved infrastructure/unknown cases remain missing.
With missing outcomes, show lower/upper success and contrast bounds instead of
complete-case point estimates. With complete outcomes, use 97.5% equal-tailed
Clopper-Pearson component intervals and opposite-endpoint B-A/B-C bounds,
at least 95% coverage per comparison, not across the whole endpoint family.
Successful-only CR1 cost is secondary/conditional, undefined with zero successes;
all-attempt consumption is interpreted jointly with success, not as success cost.

No significance-based seven-hypothesis decisions, mixed-effects primary analysis,
non-inferiority margin or H7 half-gap test. No outlier removal/winsorisation.
Null/negative/non-estimable patterns are reported. Eligibility/oracle amendments,
policy deviations and unplanned analyses are versioned and labelled exploratory.

## Resources, provenance and approval checklist

30/15/45-minute limits; 318 pilot sessions/133.5 maximum agent-hours,
150 excluded calibration sessions/60 hours; combined 468 sessions/193.5 hours
excluding non-agent overhead. Counts are planned sessions; allowed infrastructure retries can add
calls but share the original step's aggregate time and credit allowance.
Fixed 300-AI-Credit/session soft cap for both
stages; **300,000 AI Credits total**, including prior spend and calibration.
The owner's approximately $3,000 equivalent is unverified, not a conversion or
separate precise monetary limit. A cost-only full-design affordability check
after calibration must pass; otherwise halt and amend rather than reduce sample
silently. A provider-enforced hard billing boundary is still absent.
Require three exact agreeing reference executions at every feature stage and
CR1, all expected tests passing; discrepancies block collection until
investigated/versioned/revalidated, not rerun until green.

The scheduler and analysis implement model-aware allocation and separate
per-model primary estimates. Before collection obtain independent
`multi_model_harness_alignment` evidence covering the
eighteen-trajectory model-aware schedule, model-specific analysis, revised
budget and chosen operational rules. Requested model/runtime availability and
compatible reasoning settings also require verification; no live probe or
paid collection was performed by this work. The owner selected the prospective
CLI 1.0.105/Ruff 0.17.3/Lizard 1.24.3/jscpd 5.4.1 amendment on 28 October;
these candidates do not by themselves establish runtime acceptance.

Attach `pilot-estimation.md`, `pilot-estimation.json`, candidate unreviewed
`contract-panel.json`, protocol/harness/suite source hashes, fixed prompts,
analysis version, pending-evidence disclosures and data chronology.
Existing oracle/reference diagnostics are unaccepted development evidence,
not independent approval or a prerequisite to submit the plan.
Source paper: jmservera/ama `196b97644bb9bffa43d41a9921d6a06a93b2699e`.
Historical proposal/tag provenance is in the protocol; never replace the old tag.

Before submission: confirm recorded owner choices, planned runtime/caps,
secondary scope and prior exposure; disclose pending review/runtime evidence
and approve exact files/source SHA. Do not fabricate acceptance of pending checks.
Owner completes OSF contributor/privacy settings and real approval workflow.
Only after registration completes record the actual URL and date; a saved draft
or uploaded archive is not completed registration. Freeze execution inputs before
fresh collection only after all retained review and operational prerequisites
are genuinely met; no exercise runs or launch authorisation are performed here.

## Guidance consulted

- [Official OSF registration/preregistration guide](https://help.osf.io/article/330-welcome-to-registrations)
- [COS template and pilot guidance](https://www.cos.io/blog/choosing-preregistration-template-guide-for-researchers)

Retrieved 27 October 2026. A general-purpose draft is provided, not an assurance
that OSF, an institution or a journal has approved this design.
The preregistration/peer-review distinction was checked on 28 October against
[COS preregistration guidance](https://www.cos.io/initiatives/prereg) and
[Registered Reports](https://www.cos.io/initiatives/registered-reports).
