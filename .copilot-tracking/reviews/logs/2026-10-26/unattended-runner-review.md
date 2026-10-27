# Unattended runner Review

Task: unattended-runner-2026-10-26. Date: 2026-10-26.
Execution: **Complete** (one post-implementation assessment).
Outcome: **Not accepted for the full live-study requirement**. The bounded
offline-safe tooling is implemented and validated; required paid-backend and
scientific capabilities are not falsely represented as completed.

## Compared artifact set

- Research: `.copilot-tracking/research/2026-10-26/unattended-runner-research.md`.
- Plan: `.copilot-tracking/plans/2026-10-26/unattended-runner-plan.md`.
- Details: `.copilot-tracking/details/2026-10-26/unattended-runner-phase-details.md`.
- Single critique: `.copilot-tracking/reviews/2026-10-26/unattended-runner-critique.md`.
- Changes: `.copilot-tracking/changes/2026-10-26/unattended-runner-changes.md`.

Boundary: all user-requested runtime/report/publication requirements, not merely
the revised offline implementation scope. Read-only assessment; no source fixes
or repeated critique/Review. Pending delivery is assessed separately from code.

## Coverage and implementation evidence

| Boundary | Assessment |
| --- | --- |
| Paper comparison | Research C1-C16 cover the paper's consolidation package, hypotheses, prospective first pass, no-results status, correction, measures and deferred extensions. Paper was read-only. |
| Preflight | Tools, version pins, Docker daemon, token presence only, disk, exact <=2500-credit limit, explicit prior spend, clean git, immutable source/input provenance and owner gate evidence are checked. Confirmatory dry-run exited 2 with 12 proposed cells, missing freeze and hard-billing refusal. |
| Unattended mechanics | Stub entrypoint is one command; no prompts, credential/network dependency or model access. Schedule/source/config are immutable on resume; lock/atomic state, attempt limits, timeouts and checkpoint rollback have semantic coverage. |
| Integrity | All scheduled metadata exists before execution and survives setup interruption. Durable steps are deduplicated. Measured non-delivery is not retried; interrupted/unmeasured attempts remain linked to one cell and all-attempt costs remain visible. |
| Credit safety | Integer nano-credit admission, exact boundary, explicit prior spending, unknown-accounting stop and durable overrun recording are tested. No real cap enforcement is claimed: RV-001. |
| Isolation | Separate disposable git repositories for stub runs; no kit tags created. Hardened immutable-image Docker command builder exists, but is not a wired paid backend: RV-002. Existing local evaluator isolation limitations remain disclosed. |
| Exports | Exactly 13 allowlisted files, 49,448 bytes in the final stub run. Corrected analyzer is reused, including incomplete runs. CSV/JSON/Markdown estimates, intervals and dispositions; native LaTeX/SVG figure outputs. Unavailable scientific outputs are explicit: RV-003. |
| Publication | Local bare-origin/fake-gh tests prove result-only changed paths, normal push, source branch preservation, idempotent commit/PR update, auth/push failure and secret/link/size refusals. Actual results publication was not run. |
| Documentation | README one-command smoke, check-only bootstrap, controller runbook and divergence record accurately state that paid sessions are unavailable, Docker policy is unapproved and a freeze is not created. |
| Critique | PC-001 exact immutable 2500 ceiling/prior spend; PC-002 persistent deadline and stopped writers; PC-003 cell/attempt projection and all-attempt costs all have implementation and tests. No second critique. |
| Scope changes | Shared IO boundary and optional existing-metadata setup are justified implementation refinements. Safe-tooling acceptance is narrower than the user's desired runnable paid study, so full task conformance is not claimed. |
| Delivery | Commit/push/stacked PR remain parent-owned authorised delivery, not study execution or approval. |

## Validation assessed

- Complete regression suite: **337 passed in 40.54s** (289 existing, 48 new).
- Every S1 reference stage passes: **164/164 F10**, **182/182 including CR1**.
- Isolated Ruff; entrypoint sh syntax/ShellCheck; TCR bash syntax/ShellCheck;
  diff whitespace checks: passed.
- Documented final smoke: five fake sessions, three cells, 12/12 hidden F1 tests
  each; deliberate forbidden C change detected and reverted. Second invocation
  skipped all work. Ledger actual usage is zero for every stub attempt.
- Offline dry-run and bootstrap: passed. Confirmatory dry-run: expected exit 2.
- Publication artifacts independently passed the allowlist/credential/size
  validator; SVG parsed; no raw logs selected for commit.
- No live study, Copilot prompt, billing test, image build or cloud provisioning.
  No independent oracle/owner/human approval inferred. LaTeX was not compiled;
  export structure and escaping are covered, not visual TeX rendering.
- Kit tag remains `protocol-frozen` at
  `2d43d63cdbebe337c29ed3b2d69c74a67c484212`. No tag operations were run.

## Complete finding set and routing

### RV-001 [High]: Hard actual billing and paid execution are unavailable

Evidence: `harness/study.py` preflight unconditionally refuses paid execution;
`StudyRun.run_agent` supports only the built-in stub. Installed CLI documentation
describes AI-credit limits as soft, and final-only usage cannot bound in-flight
billing. Admission accounting alone does not fulfil a hard consumption ceiling.

Impact: The owner cannot yet launch the actual first pass with one command,
even after providing all nominal freeze data. This is the central unmet user
requirement, not a defect to fix by weakening the ceiling or running a paid probe.

Route: distinct `rpi-research` follow-up to identify an enforceable provider/
billing boundary, then a separately authorised implementation. Keep paid
execution disabled until that evidence exists. No invented overshoot allowance.

### RV-002 [Medium]: Docker/live session path is preparatory, not operational

Evidence: `docker_command` prepares pinned headless Copilot arguments and
restricted mounts/resources, but the current controller deliberately loads the
stub runtime. No production container lifecycle, real-session usage adapter or
access-probe acceptance is implemented or tested.

Impact: Container builder tests are not evidence that a real study can run
unattended or that hidden/reference/network boundaries are established.

Route: later `rpi-implement` after RV-001 and owner Docker amendment. Wire
container lifecycle, cleanup/reconciliation and real measurement configuration
without changing arms or thresholds; validate under a separately authorised
zero-credit backend before any paid study.

### RV-003 [Medium]: Full paper measurements and method evidence remain unavailable

Evidence: Research C7-C12 and `availability.json` retain H4 comprehension, H7
definitions/full contrast, HIR/IDR telemetry coverage, the proposed decay
amendment and mixed-effects diagnostics as unavailable. Existing OLS/bootstrap
exports are not all promised paper methods. Independent review, registration
and verified runtime/access evidence are still owner gates.

Impact: Generated tables have accurate availability labels and implemented
estimates, but cannot supply every actual Section 8 result. Stub findings cannot
be used to fill the paper's results branch.

Route: owner decision/evidence `rpi-plan` follow-up, then bounded implementation
for approved statistical/telemetry surfaces. Do not invent thresholds, approvals,
reviewer results or a replacement estimator. Optional S2/repeated-change probes
remain outside the authorised study, not newly required work.

## Outcome and handoff

No additional high-confidence correctness defect was established in the
validated offline scope. The above three material capability/evidence gaps are
the complete routed set. Full-study acceptance remains **Not accepted** despite
passing tests. Preserve this outcome and do not rerun Review inside this task.
The parent may commit and publish the clearly labelled tooling PR as requested;
that is not approval to run the study.
