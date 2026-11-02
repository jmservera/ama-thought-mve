# OSF Preregistration submission draft

**Original 763945b submission: owner-confirmed registered and approved,
28 October 2026. This subsequent corrected candidate is not yet prospectively
recorded; its merged source is owner-approved for freezing, not authorised
for data collection.** The [freeze manifest](freeze.json) keeps prospective
amendment completion unset until the actual OSF update is recorded.
Preserve the original attachment and record
[the prospective clarification](prospective-corrections-2026-10-28.md)
before affected collection.
The current five-arm/replicate-selection release is separately documented in
[the 2 November amendment record](five-arm-amendment-2026-11-02.json).
Historical v2/v3 were not registered; neither v4 nor the new release is
asserted registered here. Use the actual new OSF reference/date once completed,
preserving all historical attachments. The owner requested release preparation,
not paid collection.
Use the general-purpose **OSF Preregistration** form. Field wording may change:
transfer these answers into the live form and attach the approved protocol,
decision ledger, candidate contract panel and checksums. The panel is not
independently accepted. Follow [the submission checklist](osf-submission-checklist.md);
do not upload private session logs or the private reviewer bundle.

## Metadata

**Title:** Scheduled consolidation during agentic feature delivery:
a five-arm, three-model S1 pilot/estimation study.

**Contributors and affiliations:** owner confirmed authorship and permissions
are settled; enter personal details directly in OSF. Do not infer identities
or coauthor endorsement from this repository.

**Licence:** [Creative Commons Attribution-NonCommercial-NoDerivatives 4.0
International (CC BY-NC-ND 4.0)](https://creativecommons.org/licenses/by-nc-nd/4.0/),
selected by the owner for owner-controlled preregistration documents and
submission attachments. Repository code and third-party materials are not
relicensed by this selection.

**Visibility:** owner selected embargo until **31 December 2026**
(`2026-12-31`). These settings must still be entered in OSF; no active embargo
or completed registration is claimed.

**Description:** We compare feature-only delivery (A), consolidation after each
feature (B), read-only review (C), longer uninterrupted delivery (D) and
visible-specification behavioural repair (E), fully crossed with GPT 6.1 Sol, Sonnet 5.5
and Gemini 4 Argon:12,21or33 independent trajectories per arm/model,
default 12, yielding 180, 315 or 495 ten-feature S1 trajectories. The researcher
selects and records the allocation prospectively before collection. The launcher
persists it in immutable study identity and all run metadata; resume cannot
change it and observed results cannot determine it. Calibration remains1per
arm/model. B-D is the primary equal-model-weighted practical coverage comparison.
This is not a guaranteed 80% power claim: 12/21/33 correspond to assumed
15/20/25-point within-cell SDs for a ten-point effect, not measured variability.
The pilot estimates final behavioural coverage,
retained-contract losses, final CR1 success and consumption; it checks feasibility,
variation and failure modes for a later separately planned study. Consolidation
includes extra resources, permission to edit/add tests and a different note.

## Registration type and existing data

Prospective **pilot/estimation** preregistration, not a confirmatory seven-test
study or a registered report with journal acceptance. The intended selected
cohort has not been run by this work.

**Data already exist:** yes, separate development diagnostics exist. Tracked
`results/smoke` covers historical paid `smoke-01` (B, F1 plus consolidation,
14.54 credits) and discloses observed performance/usage; its stored phase label
does not make it an estimation replicate. Offline reference/stub diagnostics
also exist and their outcomes have been used to check tooling. Neither is pooled
into the selected study trajectories. The owner confirmed on 27 October that the
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
actual artifacts before signing the live existing-data answers. During final
approval on 28 October the owner reconfirmed this inventory is accurate and
complete, with no additional work/data exposure or calibration/registered
pilot collected.

No timestamp, lack of prior exposure, complete calibration or registration is
asserted from a local draft, manuscript statement or historical Git tag.

## Review status and preregistration policy

This plan has **not received independent scientific acceptance**. On
30 October the owner individually accepted the six scientific scopes for
`90e393e`: suite adequacy, panel mapping and explicit panel acceptance,
analysis/reference metrics, multi-model alignment and oracle stability.
The owner selected documented owner review for this first exploratory pilot
and deferred independent scientific review. This is a limitation to disclose,
not a completed independent review. A separate operator does not independently
validate the scientific design. See
[the decision record](scientific-acceptance-2026-10-30.json).
The owner subsequently accepted corrected `1120002` runtime/access evidence
and confirmed no independent reviewers for this first study beyond the separate
executor. This also prospectively supersedes the independent-access-review
sign-off prerequisite; no independent scientific or access/security review is
claimed. The executor supplies operational separation only. See
[the runtime decision record](runtime-acceptance-2026-10-30.json).
Historical paid model checks retain their actual source and limited scope;
current offline evidence is finite, not an exhaustive security proof or future
entitlement guarantee. All permission, isolation, accounting, final freeze and
prospective OSF requirements remain. Ordinary OSF preregistration records the plan;
it does not require independent scientific peer review or certify validity.

On 28 October the owner explicitly approved the content at source commit
`235489cc8b63307d35d624b1b7bb02124c1bfec1`, plus the selected metadata and
approval-record updates, for submission with this disclosure. The owner
confirmed no additional approvals are required before preregistration.
The project retains all outstanding
runtime/access and operational checks as prerequisites before calibration/pilot
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
The primary resource measure is certified AI credits. Complete
input/output/cache token telemetry is not currently supplied by the isolated
bridge, so token comparisons are explicitly unavailable, not zero.

## Study design, sampling and randomisation

Controlled repeated-trajectory software experiment; synthetic data, one S1
suite, three deliberately selected model candidates: `gpt-6.1-sol`,
`claude-sonnet-5.5`, `gemini-4-argon`. Select 12, 21 or 33 fresh repositories per A/B/C/D/E arm
within each model, default 12, ten sequential features and full CR1: 180, 315 or 495 independent
units. Arm order is randomised within model/replicate blocks, seed 2027. Same machine,
skeleton, specifications and tools. B adds consolidation, C read-only review,
D extends each feature session to 45 minutes/600 nominal credits without a
post-step, and E adds 15-minute visible-specification repair. B and D share
total cycle time/nominal credits, not session count or realised consumption.
B-C is not pure refactoring or equal realised compute.

Separate budget calibration: one trajectory per arm/model (15 total), ten
features, no CR1, excluded from the study. CLI `calibration`/legacy `pilot` refers to this
excluded stage; `pilot-estimation`/legacy `first` refers to the selected study.
The older three-model/two-per-cell ABC design remains historical, not approved
collection under this new allocation. Replication tests robustness
to these models, not independence from model choice or all-model generality.
No optional stopping, outcome-based replacements or sample enlargement.
All incomplete, assisted, failed and unattempted allocated trajectories remain.
Owner choices are recorded in the attached ledger: continue scheduled work,
including B/C/E post-steps on retained green state after unsuccessful feature
delivery, with no replay/make-up; incidental recovery within existing step
permissions is allowed. At most one documented infrastructure-only retry per
step from its pre-attempt snapshot may use the remaining original aggregate
step budget; all attempts/charges count. Poor outcomes never justify retry.
Retry an infrastructure-failed measurement once on the same immutable snapshot;
contradictory valid outcomes halt collection for oracle investigation.
Final source approval is still required before submission.
Accepted Python test files are immutable, with additions in new files only.
E's explicit exception supports only literal expected-value corrections in
equality assertions of agent-authored tests, retaining all other bytes.
Require old/new blob hashes, exact visible-specification quote/identifier and
explanation in `REPAIR.json` and the private journal. Immutable examples and
skeleton tests have no exception. Provenance checks are not independent
semantic adjudication; review the alleged contradiction before interpreting it.

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

All run-level outcomes/ranges accompany the primary B-D difference, equally
weighted across three within-model means, and secondary model-specific
B-D/B-A/B-C/E-B differences. Each arm/model has the same selected 12, 21 or 33
trajectories. The primary requires the complete allocated unassisted five-arm
frame and observed final coverage; no observed-model pooling or complete-case
substitution. Report pooled within-cell SD and its degrees of freedom.
No feature or
test is an independent inference unit. H1 and resource comparisons use mean
differences and pointwise whole-run bootstrap intervals within arm within model
(10,000 draws, seed 2027).
Insufficient strata or any undefined draw makes the affected interval unavailable;
do not discard undefined draws or impute last-observed final outcomes.
Historical two-run ABC cohorts remain separate under their historical analysis;
they are not relabelled as the new primary design.

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
Clopper-Pearson component intervals and opposite-endpoint B-D/B-A/B-C/E-B bounds,
at least 95% coverage per comparison, not across the whole endpoint family.
Successful-only CR1 cost is secondary/conditional, undefined with zero successes;
all-attempt consumption is interpreted jointly with success, not as success cost.

No significance-based seven-hypothesis decisions, mixed-effects primary analysis,
non-inferiority margin or H7 half-gap test. No outlier removal/winsorisation.
Null/negative/non-estimable patterns are reported. Eligibility/oracle amendments,
policy deviations and unplanned analyses are versioned and labelled exploratory.

## Resources, provenance and approval checklist

30-minute ordinary feature, 45-minute D feature, 15-minute post and 45-minute CR1
limits; default 12 has 3060 estimation sessions/1395 maximum agent-hours;
21 has 5355 sessions/2441.25 hours; 33 has 8415 sessions/3836.25 hours.
240 excluded calibration sessions/105 hours; default combined 3300 sessions/1500 hours
excluding non-agent overhead. Counts are planned sessions; allowed infrastructure retries can add
calls but share the original step's aggregate time and credit allowance.
Nominal 300-AI-Credit/session allowance (600 for D feature sessions) for both
stages; **300,000 AI Credits total**, including prior spend and calibration.
The owner's 29 October prospective policy accepts soft-limit overshoot risk:
supplied operational settings use a 10% buffer, **270/session (540 for D features)** and **270,000
local admission**, without changing allocation or the nominal registered envelope.
An in-flight response can exceed the CLI threshold; neither buffer guarantees
actual billed consumption. The company hard limit of 1,000,000/collaborator is
owner-reported, not independently verified or a study-specific stop. A separate
provider study hard cap is no longer a project prerequisite. Record this
addendum prospectively before affected collection; the original OSF attachment
is unchanged.
Combined nominal allowances including calibration are 85500*n + 81000:
1,107,000 / 1,876,500 / 2,902,500 credits for n=12/21/33. These summed
allowances are not permitted spending. The fixed selected allocation must pass
cost-only affordability/deadline checks; otherwise halt and prospectively amend,
never silently reduce sample size. The published v4 does not contain this
five-arm amendment; new exact-source qualification, approval, freeze and
prospective OSF recording remain required before collection.
The owner's approximately $3,000 equivalent is unverified, not a conversion or
separate precise monetary limit. A cost-only full-design affordability check
after calibration must pass; otherwise halt and amend rather than reduce sample
silently. Actual usage completeness and the isolated live backend remain required.
Require three exact agreeing reference executions at every feature stage and
CR1, all expected tests passing; discrepancies block collection until
investigated/versioned/revalidated, not rerun until green.

The scheduler and analysis implement model-aware allocation and separate
per-model primary estimates. Owner-accepted
`multi_model_harness_alignment` evidence covers the
eighteen-trajectory model-aware schedule, model-specific analysis, revised
budget and chosen operational rules. Requested model/runtime availability and
compatible reasoning settings also require verification; no live probe or
paid collection is authorized by the scientific decisions. Earlier excluded
backend checks are separately disclosed; their runtime acceptance remains
pending. The owner selected the prospective
CLI 1.0.105/Ruff 0.17.3/Lizard 1.24.3/jscpd 5.4.1 amendment on 28 October;
these candidates do not by themselves establish runtime acceptance.

Attach `pilot-estimation.md`, `pilot-estimation.json`, owner-accepted
`contract-panel.json`, protocol/harness/suite source hashes, fixed prompts,
analysis version, `scientific-acceptance-2026-10-30.json`, pending-evidence
disclosures and data chronology. Existing90e393e oracle/reference diagnostics
were accepted by the owner within their recorded limits, not independently
approved or newly executed on a later source.
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
