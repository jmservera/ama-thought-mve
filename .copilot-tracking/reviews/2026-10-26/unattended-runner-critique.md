# RPI Plan Critique: Unattended study runner

## Metadata

* Task ID: unattended-runner-2026-10-26
* Critique date: 2026-10-26
* Plan: .copilot-tracking/plans/2026-10-26/unattended-runner-plan.md
* Phase details: .copilot-tracking/details/2026-10-26/unattended-runner-phase-details.md
* Critique execution status: Complete
* Execution count: One independent final-candidate assessment; no nested agents.

## Inputs and Criterion Boundary

* Caller requirements: one-command unattended study tooling with preflight,
  resume, bounded retry/timeouts, isolation, trustworthy exports, result-only
  publication and a hard aggregate ceiling of 2500 AI credits. No paid runs,
  tags or paper edits. Preserve owner-controlled scientific gates.
* Research considered:
  .copilot-tracking/research/2026-10-26/unattended-runner-research.md,
  including C1–C16 and its accepted/rejected/deferred decisions.
* Decisions and acceptance criteria considered: FR1–FR5, non-functional
  requirements, AC1–AC6, P01-T01 through P04-T02, follow-up prerequisites,
  and the locked critique contract. Test ownership remains with the parent;
  no existing tests are removed; at most two additional test modules; target
  ownership and prescribed validation remain unchanged.
* Boundary: assess planning credibility from the three supplied artifacts and
  caller requirements, not implementation correctness or execution readiness.
  No source inspection, external research, tests, paid commands, repository
  publication or paper access was performed during this critique.

## Coverage Assessment

| Requirement, research, phase, or task ID | Coverage | Evidence or concern |
| --- | --- | --- |
| FR1; C1, C5; P01-T01; AC2 | Partial | Durable schedule, fingerprint, lock, checkpoint rollback and retained failures are specified. Timeout lifecycle and retry-to-analysis mapping need resolution in PC-002 and PC-003. |
| FR2; C2, C16; P01-T02; AC1, AC3 | Partial | Reservation, unknown-usage blocking, overrun retention and unconditional current-backend live refusal are sound. The requested numeric aggregate ceiling is not bound into the configuration/ledger contract: PC-001. |
| FR2; C3, C11; P01-T01/T02 | Covered | Version/tool/Docker/token/disk/git checks, owner freeze, immutable image and registration gates are explicit; bootstrap is check-only. |
| FR3; P03-T01/T02; AC1, AC2 | Covered | Built-in fake agent, offline smoke, read-only dry-run, no real model subprocess and repeated smoke are explicitly required. |
| FR4; C5–C10, C15; P02-T01; AC3, AC4 | Partial | Reuse of corrected analysis, unavailable methods/human fields, separate units, missing-not-zero cost, intervals and diagnostic stub provenance are credible. Retry selection/denominator semantics remain open: PC-003. |
| FR5; C13; P02-T02; AC5 | Covered | Explicit publication, fixed derived-file allowlist, link/secret/size checks, detached worktree, no force push, local/fake-gh tests and idempotent PR handling are specified. |
| C4, C12; P01-T02; P03-T01 | Covered | Restricted Docker mounts, no hidden/reference assets or host socket, immutable image/limits and prospective policy amendments are stated, without claiming approved containment or protocol authorization. |
| C7–C12, C14, C15; scope; follow-up items | Covered | No invented scientific endpoints, thresholds, approvals, telemetry, mixed models or decay extensions. Existing Run enforcement is reused; full treatment-fidelity verification is not falsely promised. |
| P03-T01/T02; AC6; critique contract | Partial | Existing regressions, reference suite, shell syntax, dry-run and repeat smoke are required. Add the resolving behavioral assertions below within the locked ownership/module limit. |
| P04-T01/T02; AC6 | Covered | One candid implementation Review, explicit staging, dated evidence, topic push and stacked PR against fix/study-measurement-integrity with #1 dependency are specified. No tags or paper edits. |

## Verdict

* Verdict: Revise
* Rationale: The safe-tooling scope and fail-closed billing decision are
  credible. Three planner-owned contract gaps remain: numeric budget scope,
  timeout/cancellation behavior, and scientific accounting across retries.
  These do not require permission to run paid work or choose scientific
  methods. Complete this single critique's corrections directly; do not
  commission another critique.

## Findings

<!-- rpi:critique id=PC-001 -->
### PC-001 [Medium]: Bind the requested 2500-credit ceiling to the ledger contract

* Related IDs: caller hard aggregate 2500-credit requirement; FR2; AC3;
  P01-T02; C2, C16.
* Evidence: The plan's FR2 and AC3 specify reservations and boundary tests,
  and phase details P01-T02 specify integer nano-credits and prior pilot
  spending. Neither artifact states 2500, defines whether configuration can
  raise that ceiling, or defines how the ceiling and prior spending are
  preserved when resuming.
* Concern: A generic configurable budget can satisfy the written acceptance
  criteria while omitting the user's exact limit. This is distinct from the
  already acknowledged inability to enforce actual provider billing.
* Impact: Tooling could report a budget-compliant admission decision using a
  different aggregate threshold or a changed resume budget.
* Smallest useful change: State the aggregate ceiling explicitly as 2500 AI
  credits, including prior pilot spending and all attempts, with lower limits
  allowed but no override above 2500. Bind ceiling/prior-spend provenance to
  immutable study state and reject incompatible resume inputs. Unknown prior
  spend must not silently become zero. Keep live execution blocked with the
  current CLI regardless of this ledger.
* Action owner: Planning parent; implementation/test execution remains owned
  by the parent under the existing target contract.
* Exact resolving evidence: Updated FR2/P01-T02/AC3 define the numeric maximum,
  units, prior-spend treatment and resume rule. Planned offline tests cover
  admission exactly at the remaining boundary, rejection above it, attempts
  and pilot spend consuming one aggregate, configuration above 2500, and
  changed/unknown prior spending. AC1 still rejects current-backend live mode
  even with a complete freeze and nominal CLI cap.
* Decision route: Direct planner correction. No user response required; the
  user already selected the ceiling. No recommendation to equate soft caps
  with a hard billing guarantee.

<!-- rpi:critique id=PC-002 -->
### PC-002 [Medium]: Specify bounded timeout and cancellation recovery

* Related IDs: unattended timeout requirement; FR1, FR2; P01-T01/T02;
  AC2, AC3; C1, C2.
* Evidence: The plan's user requirements name bounded retries/timeouts;
  research C1 identifies the missing aggregate timeout. Phase details P01-T01
  give a fixed attempt limit and checkpoint recovery but no timeout boundary,
  process termination policy or timeout-specific state/accounting transition.
* Concern: An attempt limit does not bound a hung attempt. The plan does not
  establish how per-attempt and aggregate deadlines survive restart, when a
  child process is confirmed stopped, or when rollback/retry becomes safe.
* Impact: The one-command controller can hang or resume against a still-live
  writer. Treating timeout as an ordinary retry could also launch another
  attempt while final-only usage remains unknown.
* Smallest useful change: Define validated per-attempt and aggregate deadlines,
  including restart treatment; bounded termination/escalation and reaping of
  owned subprocesses; durable timeout/interruption dispositions; and no
  rollback or relaunch until owned writers are stopped. Preserve the existing
  rule that unknown usage holds its reservation and blocks admission.
* Action owner: Planning parent; parent owns the corresponding validation.
* Exact resolving evidence: P01-T01/T02 and AC2/AC3 specify the timeout state
  transitions and deadline persistence. Offline fake-child tests demonstrate
  a hung attempt terminates within a bounded grace period, aggregate timeout
  prevents later cells from launching, restart does not reset the aggregate
  allowance, retained attempts remain visible, and missing usage prevents
  retry rather than releasing the reservation.
* Decision route: Direct planner correction. No scientific policy or paid
  execution authorization is needed; no user response required.

<!-- rpi:critique id=PC-003 -->
### PC-003 [High]: Define the analysis unit and cost accounting across retries

* Related IDs: FR1, FR4; AC2–AC4; P01-T01; P02-T01; C5, C6, C15.
* Evidence: Phase details P01-T01 retain every attempt and retry infrastructure
  interruptions, while normal non-delivery is not retried. P02-T01 invokes the
  existing analyzer and exports run dispositions. Neither document specifies
  how multiple attempt directories become one scheduled experimental unit,
  how an interrupted partial trajectory is continued without duplicate
  observations, or how retry costs enter exported cost/efficiency quantities.
* Concern: Retaining attempts and retaining scheduled cells are not the same
  analysis contract. Blindly analyzing attempts can inflate sample size;
  choosing the successful retry can erase failed/partial observations or
  omit the cost of failed attempts.
* Impact: Estimates, intervals, coverage and cost efficiency could be biased
  despite preserving every raw record. This directly threatens the corrected
  measurement behavior the plan promises to reuse.
* Smallest useful change: Define stable scheduled-cell, attempt and step
  identities, and an explicit analyzer input projection. A retry must not
  become an additional experimental replicate or replace a measured failure.
  Specify how durable steps are deduplicated, ambiguous partial work is
  represented, and all attempt costs are aggregated once per scheduled cell,
  with unknown cost remaining unavailable. If safe continuation cannot be
  established, preserve the cell as partial/unavailable rather than select a
  favorable replacement trajectory.
* Action owner: Planning parent; parent owns measurement regression tests.
* Exact resolving evidence: P01-T01/P02-T01 and AC2–AC4 define the projection,
  denominator, deduplication and retry-cost rules. Offline fixtures with an
  interrupted attempt plus recovery, a measured non-delivery, a zero-step
  cell and unknown usage prove unchanged scheduled-cell count, no duplicated
  committed step, no success-only selection, all-attempt cost reconciliation
  and complete disposition export. Assertions fit the existing at-most-two
  new-module contract and retain all existing tests.
* Decision route: Direct planner correction constrained to preserving the
  existing experiment and analyzer semantics. No new scientific estimator or
  replacement-run policy is authorized or needed; no user response required.

## Strengths and Residual Risk

* Correctly distinguishes conservative admission accounting from a genuinely
  enforced billing boundary. Provider-enforced hard billing support remains
  an unmet prerequisite, not a capability to simulate with CLI flags.
* Current live execution is explicitly blocked even with otherwise complete
  freeze fixtures. This is an honest incomplete execution requirement, not
  a reason to weaken the hard ceiling or run a paid probe.
* Durable schedule/attempt provenance, checkpoint rollback restricted to owned
  disposable repositories, private raw output and immutable resume inputs
  provide a sound recovery foundation.
* Diagnostic smoke is excluded from study data. Missing usage and unavailable
  H4/H7/HIR/IDR/decay/mixed-model outputs are not fabricated.
* Publication has a credible result-only trust boundary and local-only test
  strategy. No source branch switch, force push, raw transcript publication,
  paper edit or tag mutation is proposed.
* Owner freeze, registration, independent review, method and Docker-policy
  approvals remain genuine gates. Their absence is not a planner defect to
  solve by inventing approval.

## Questions or Blocking Evidence Gaps

* No unanswered user decision blocks the bounded tooling implementation.
* No supported provider hard-limit interface is supplied. That prevents paid
  execution and full-study acceptance, but does not block this assessment or
  implementation of offline-safe tooling.
* PC-001 through PC-003 are the complete actionable finding set for the
  supplied boundary; no additional findings are withheld for another pass.

## Limitations

* Research source assertions were assessed as supplied evidence, not
  independently reverified against code, CLI help or the external paper.
* This critique does not certify implemented recovery, statistical exports,
  containment, credential handling or publication. Those require the planned
  offline validation and single implementation Review.

## Recommended Next Action

* Highest-impact finding: PC-003, retry-to-analysis and cost-accounting contract.
* Action owner: Planning parent.
* Smallest next action: Define the scheduled-cell projection and regression
  assertions, resolve PC-001/PC-002 in the same direct plan/detail revision,
  then continue the authorized implementation lifecycle without another
  critique.
* User response required: No.

| Artifact | Description |
| --- | --- |
| [.copilot-tracking/plans/2026-10-26/unattended-runner-plan.md](.copilot-tracking/plans/2026-10-26/unattended-runner-plan.md) | Assessed implementation plan |
| [.copilot-tracking/details/2026-10-26/unattended-runner-phase-details.md](.copilot-tracking/details/2026-10-26/unattended-runner-phase-details.md) | Assessed phase details |
| [.copilot-tracking/research/2026-10-26/unattended-runner-research.md](.copilot-tracking/research/2026-10-26/unattended-runner-research.md) | Supplied research and decision evidence |
| [.copilot-tracking/reviews/2026-10-26/unattended-runner-critique.md](.copilot-tracking/reviews/2026-10-26/unattended-runner-critique.md) | Complete single-pass critique |

## Next Steps

The active planning parent should resolve the three planner-direct findings,
record their disposition and proceed with offline implementation and validation.
No user action, paid command or second critique is required. Paid execution
remains blocked pending genuine hard-billing support and owner gates.
