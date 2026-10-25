---
title: Consolidation Harness Protocol Divergence Log
description: Dated changes to the unexecuted experiment protocol
ms.date: 2026-10-25
---

## 2026-10-24: Pre-Run Revision for Draft v3

These changes were made before any run, according to the package's recorded
unexecuted status. No experiment or delivery loop was launched in this revision.
This entry is not owner approval, protocol freezing or public registration.

* Changed the exploratory first pass to S1, A/B, four runs per arm and eight
  features, followed by CR1. The main study remains five runs per arm per suite.
* Defined a first-pass CR1 variant for regions in lists, visibility and
  handoffs. Full CR1's ranking/export checks require F9-F10 and remain in the
  main study. Both variants need pre-pilot specifications and hidden tests.
* Recorded 64 feature, 32 consolidation and eight change-request steps,
  totalling 46 agent-hours or 11.5 idealised hours across four parallel sessions.
  The calculation and exact-rank-test floors are in ../protocol_checks.py.
* Replaced suite random effects with a fixed effect; retained run random
  intercepts. Replaced no-difference invalidation with interval-based decisions.
* Defined H1's post-consolidation end state, change-request regression
  protection and missing-feature resets without shrinking the hidden denominator.
* Disclosed B's extra time allowance, the optional time-matched C comparison,
  the proprietary-model limitation and pending public pre-registration.

Owner approval, the actual registration date/URL, exposed model/runtime
versions, budgets and frozen test assets remain required before execution.

## 2026-10-25: Measurement Integrity Corrections

The owner authorised an isolated worktree and a pushed topic branch to fix
the defects identified while reviewing AMA PR 448. The starting private
snapshot is `20e7f97c5c162cffd0f771ce501e146081912edc`; the branch is
`fix/study-measurement-integrity`. The original checkout, tags, earlier
diagnostic runs and results remain unchanged. This entry does not claim
that no earlier data exists or that registration is complete.

The work corrects implementation against the existing hypotheses. It does
not change thresholds, selected arms, sample sizes, agent budgets or the
owner's local-execution choice. Local process execution is not OS-level
isolation: removing inherited credentials does not make host files or hidden
tests inaccessible. Any new analysis details must be recorded before a new
registration/freeze; the original tag must not be moved or silently replaced.

### Approved RPI Phases

* [x] P01: Port the corrected TCR helper from AMA and adapt its regression
  tests. Verify unique cleaned logs, complete test/stage/commit rollback and
  truthful nonzero failure results in disposable fixtures only.
* [x] P02: Align analyzer verdicts with interval-based H1-H7 rules, including
  H6's alternative cost criterion. Keep incomplete outcomes not evaluable;
  require reviewer data for a full H4 verdict and retain missing usage as
  unknown rather than free work. Test with synthetic inputs, not live results.
* [x] P03: Correct cumulative test collection, empty-suite validation and
  metric failure handling; exclude generated reports from documentation
  counts. Remove inherited credentials from local evaluation/green checks
  and retain an explicit residual host-access-risk limitation. Test CR1 and
  partial-feature behaviour without launching real coding agents.
* [x] P04: Run the focused regressions and applicable offline suite/pipeline
  checks, reconcile documentation and record source-identified results.
* [ ] P05: Obtain independent review, commit with privacy-safe identity and
  push the reviewed topic branch. Do not merge or change original tags.

### Current State

P01-P04 have completed implementation, documentation reconciliation and
focused/offline validation. P05's independent Review is Complete with outcome
Not accepted. The owner selected "Fix all three, test and push". Commit and
push remain withheld until that separate follow-up is implemented and tested.
The next action is to enter Implement for RV-001 through RV-003 while retaining
the original Review outcome. The owner's no-`.copilot-tracking/` constraint is
retained: this file holds the plan/change evidence and the independent
review is retained outside the source checkout.
No protocol approval, registration or scientific result is claimed.

### Independent Review and Routed Work

The original complete report is retained at
`/tmp/ama-thought-mve-integrity-20261025-review.md`, SHA-256
`c04edcb9ecc62c1310b4f282584ffaeddb2693c3264dc23156d384ddce34432d`.
It assessed the 13 changed/new source files before this outcome entry,
manifest digest
`db4287ae300ec46eb710b6e57bce343c1f7712a5706e85aaa55d6e746fc959a9`.
Its 204-test rerun passed in 21.59 seconds, but additional synthetic probes
demonstrated three uncovered defects. Passing regressions did not establish
acceptance. Preserve this Review outcome; do not repeat it or claim closure
inside the completed review task.

* RV-001, High, `harness/analyze.py`: scheduled ten-feature runs interrupted
  after feature 1 can validate H1 and H5. Retain partial runs descriptively,
  but require complete planned endpoints and cost windows for those verdicts.
  Route to a later `rpi-implement` task.
* RV-002, High, `harness/analyze.py`: discovery omits metadata-bearing runs
  without a first `steps.jsonl` record. Discover runs from metadata and retain
  missing outcomes/accounting explicitly. Route to a later `rpi-implement`
  task together with RV-001; this prevents survivor bias.
* RV-003, Medium, `harness/runner.py` and `skeleton/tools/metrics_core.py`:
  evaluator entry and metric subprocesses still inherit credentials outside
  the sanitized hidden-test context. Extend the minimal environment to that
  boundary without altering agent authentication or claiming OS isolation.
  Route to the same later `rpi-implement` task.

The recommended next action is a separately authorised correction of all
three findings, with focused regression coverage, before the requested topic
push. No repair, source acceptance, commit or push is implied by this entry.

### Implementation and Validation Evidence

* P01 ports the corrected AMA helper at
  `e3a104df8f55500a82047b56700e9a161be8c708`. The helpers are byte-identical,
  with SHA-256 `78a81a8a36d0c0b4c3274be997d88c78f892b5b82ddfdc7ee74ad26dc7540be6`.
  All seven synthetic rollback/logging tests, `bash -n` and ShellCheck passed.
  No destructive TCR was run against either original checkout.
* P02 adds 83 synthetic analyzer tests. Missing usage stays unknown; H2 uses
  the stated endpoint, compound verdicts use intervals, and H6 retains its
  alternative cost criterion. Full H4 and H7 are explicitly not evaluable
  without their missing components.
* P03 adds 114 synthetic evaluation/validation/metric tests. Valid tests
  survive an unrelated collection error; denominators remain fixed; empty
  contributions and metric subprocess failure no longer become success.
  Evaluation uses a credential-minimal environment, not an OS sandbox.
* The combined regression command
  `python -B -m pytest -p no:cacheprovider harness/tests -q` passed all 204
  tests in 18.54 seconds with the existing Python 3.12 virtual environment.
* S1 reference validation passed every stage: 164/164 cumulative tests at
  F10 and 182/182 including CR1. This does not replace independent human
  oracle review. No suite specification, oracle or reference was changed.
* Offline A/B/C runs with `config.dry-run.json`, ten features and CR1, and an
  explicit seconds-only analyzer run completed in this disposable worktree.
  Only `fake_agent.py` and reference fixtures were used, not real coding
  agents or private results. Outputs are diagnostic, uncommitted and not
  hypothesis evidence.

### Analysis Reconciliation Before a New Freeze

The corrected analyzer implements 10,000 stratified whole-run bootstrap
draws, equal-suite weighting and marginal 95% percentile intervals. Shared
draws retain covariance in compound effects. Any undefined resampled
estimate makes its interval unavailable instead of dropping that draw.
Trajectory analysis bootstraps per-run OLS slopes; the proposed mixed model
is not implemented. H3 reports both the benefit and half-slope-margin
intervals, using the point half-slope threshold and beneficial interval for
its component validation rule.

H6 success differences use conservative simultaneous Clopper-Pearson bounds
with Bonferroni allocation across arms and suites. Successful-attempt cost
contrasts retain failures in run resampling and report failed costs
separately. Observed no-lower success is not a non-inferiority result. H5's
late implementation-cost window is the last `floor(N/3)` features, at least
one. Missing primary-credit records do not trigger a secondary-unit fallback.

These choices need explicit reconciliation with the approved analysis before
fresh registration; they are not retroactive evidence of a frozen method.
Comprehension integration, H7's package contrast, HIR extraction, independent
oracle review and accepted runtime/access checks remain separate gates.

## 2026-10-25: Owner-Selected Review-Findings Follow-Up

Task ID: `2026-10-25-study-measurement-integrity-review-findings`.
Task slug: `study-measurement-integrity-review-findings`.
Parent workstream: `study-measurement-integrity`; its original Review remains
Complete / Not accepted. Mode: manual. Active phase: Implement. Status: active.
No automatic session was started. The owner explicitly selected
"Fix all three, test and push" after seeing RV-001 through RV-003.

This is a later `rpi-implement` invocation, not a repeated Review or a rewrite
of the original outcome. The existing topic branch is retained for coherent
delivery; no existing work is moved to another branch. The approved evidence
is the original independent report and this plan/change record. No separate
tracking plan/details/critique is created under the owner's write constraint.

### Approved Follow-Up Phases

* [x] F01: Correct analyzer completeness and run discovery for RV-001/RV-002.
  Preserve partial and zero-step runs for reporting; require complete scheduled
  feature/post-feature endpoints and costs for affected comparisons. Add
  synthetic interruption, missing-record and complete-run regressions.
  Ownership: `harness/analyze.py` and `harness/tests/test_analysis.py` only.
* [x] F02: Correct evaluator/metric environment coverage for RV-003. Keep
  allowlisted temporary environments through evaluator entry and metric
  subprocesses without changing agent authentication or local execution.
  Ownership: `harness/runner.py`, `harness/measure.py`,
  `harness/evaluation_env.py`, `skeleton/tools/metrics_core.py` and
  `harness/tests/test_measurement_integrity.py` only.
* [ ] F03: Reconcile both phase returns and documentation, run focused and
  offline integration checks, commit with privacy-safe identity, push the
  topic branch and verify the remote SHA. Retain the original Review and
  its findings; report later implementation evidence separately.

F01 and F02 are dependency-ready, independent and write-disjoint. Only their
whole phases may be delegated. The parent owns F03 and this evidence file.
No new thresholds, sample/arm/budget choices, real experiments, original-data
reads, tag changes, merges or additional Review are authorised by this plan.
F01 and F02 have completed implementation and focused validation. F03's
combined validation and documentation reconciliation have also completed;
commit and topic push remain pending at this source snapshot. The external
publication state will record the actual commit/push results without claiming
those future actions here. No second Review or acceptance outcome was created.

### Follow-Up Implementation Evidence

* F01's three original interruption/discovery probes failed before the fix,
  then passed. All 83 original analyzer cases remain; 74 added cases bring
  the file to 157 passing tests. Metadata-bearing runs survive missing/empty
  step files; scheduled coverage controls final endpoints, slopes and costs.
  Missing/malformed records remain explicit and partial observed data remain
  descriptive, not substitute final measurements.
* F02's three evaluator/metric environment probes failed before the fix,
  then passed. All 114 original measurement cases remain; 11 added cases
  bring the file to 125 passing tests. A shared allowlist builder in trusted
  standalone metrics supports the harness via a fixed kit-relative file path.
  Evaluator, metric and measurement-Git launches use explicit minimal
  environments; agent authentication is unchanged. Metadata is qualified as
  `allowlisted_subprocesses`, not caller-process or OS isolation.
* The parent's direct combined command
  `python -B -m pytest -p no:cacheprovider harness/tests -q` passed all 289
  tests in 15.31 seconds: seven TCR, 157 analyzer and 125 measurement cases.
  An earlier execution-wrapper attempt reported exit 1 without pytest detail;
  the direct rerun did not reproduce that failure.
* Narrow Ruff syntax/import checks (`E9,F63,F7,F82,F401`), Bash syntax,
  ShellCheck and `git diff --check` passed. These are not a full style,
  security or scientific-method acceptance claim.
* The parent reran full S1 reference validation: F10 164/164 cumulative
  tests and CR1 182/182, unchanged suite/oracle/reference files.
* New offline A/B/C runs under
  `/tmp/ama-thought-mve-followup-validation-20261025-02/` used only the
  reference stand-in, ten features and CR1. All reached complete scheduled
  endpoints with 127/127 feature hidden tests and 142/142 including CR1.
  The seconds-only analyzer completed; all three summaries report
  `sequence_complete`, `outcomes_complete` and `cr_success` true.
  C's deliberate illegal source edits were detected/restored by the existing
  review-only enforcement. These outputs are not scientific study results.
* Before commit, the original checkout was clean at
  `20e7f97c5c162cffd0f771ce501e146081912edc`; `protocol-frozen` still
  dereferenced to that same original commit. No earlier run/result data was
  opened or changed. The authenticated account was rechecked as `jmservera`
  (ID 8036360) for its privacy-safe noreply commit identity.

### Remaining Publication Action

F03 remains unchecked until the actual commit and push succeed. Retain the
external original Review, commit only the 13 intended source/doc/test files,
exclude generated outputs, then push `fix/study-measurement-integrity` with
an explicit upstream. Verify the remote SHA and original checkout/tag again.
The publication state at
`/tmp/ama-thought-mve-integrity-20261025-publication-state.json` will be the
post-snapshot delivery record. No merge or protocol-tag replacement is allowed.
