# Unattended runner implementation plan

Task ID: unattended-runner-2026-10-26. Date: 2026-10-26.

## Executive Summary

Add one offline-safe entrypoint, durable study/attempt state, conservative credit
admission, safe result publication and paper-ready exports. Reuse corrected
single-run enforcement and analysis. Paid execution remains fail-closed:
the available CLI cannot guarantee a hard billing cap, and no freeze is approved.
This is an explicit unmet execution prerequisite, not a claimed complete study.

## User Decisions and Requirements

- Full ordered RPI loop including one critique, implementation and one Review.
- Read-only paper comparison; retain every failed/partial run; no real credits.
- One-command Linux runner, preflight/bootstrap, resumability/isolation, bounded
  retries/timeouts, exact reporting surfaces, result-only commits and PRs.
- Preserve tags and owner H4/H7/method/freeze/registration gates.
- Validate existing/new tests, dry run and tiny stub smoke.
- Commit work and dated evidence; push feat/unattended-runner and open a PR
  against fix/study-measurement-integrity declaring dependency on #1.

## Goals

Make pipeline mechanics easy and unattended without hiding missing scientific
evidence or overstating credit safety.

## Scope and Non-Goals

Runtime wrapper, result exporter, installation checker, tests and concise docs.
No new scientific endpoints/thresholds, paper changes, tags, real agents, actual
registration, independent human review or unauthorised extensions.

## Functional Requirements

FR1: immutable schedule and input fingerprint; lock/atomic state; skip completed
steps; restore interrupted disposable repositories; bounded attempts; explicit
run dispositions including unattempted cells.
FR2: preflight tools/versions/Docker/token presence/disk/git/freeze/budget; never
print credentials. Ledger reserves before launching, reconciles complete usage,
holds unknown usage and blocks further work; CLI soft caps are not a hard bound.
FR3: smoke uses only built-in fake agent, no network/Docker/token requirements.
Dry-run is read-only, emits schedule/gates and returns actionable failures.
FR4: export corrected estimates/intervals to CSV/JSON/Markdown, LaTeX table and
dependency-free SVG/LaTeX trajectory figure; mark stub results and unresolved
H4/H7/HIR/IDR/decay/mixed-model fields unavailable.
FR5: explicitly selected publication copies only fixed derived artifacts through
a detached results worktree, size/secret/symlink checks, no raw logs, no force
push, idempotent commit and gh PR create/update.

## Non-Functional Requirements

Stdlib runtime; deterministic exports; strict paths/config types; durable
reservation-before-execution; private local state; bounded publication sizes;
no destructive operations outside explicitly owned disposable run repositories.

## Acceptance Criteria

AC1: tests demonstrate no paid command in smoke/dry-run and live refusal without
freeze and hard billing support, including otherwise complete freeze fixtures.
AC2: repeat smoke skips complete cells, resumes interrupted state, preserves
failed attempts and zero-step cells, rejects changed inputs and concurrent runs.
AC3: exact admission boundary/unknown usage/overrun and restart tests; no unit
fallback or survivor-only inference.
AC4: exact output files/shapes, deterministic figure and available intervals;
stub provenance, unavailable human/method outputs and all dispositions visible.
AC5: publication tested with local repositories/fake gh, result-only changed paths,
idempotence, missing auth and push failures visible; actual study never launched.
AC6: existing regressions and new tests run; stacked implementation PR created.

## Phase Checklist

<!-- P01 -->
### P01: Runtime and safety
- [x] P01-T01: Add entrypoint, configuration, VM checks and durable runner.
- [x] P01-T02: Add credit reservations, freeze gates and isolation command builder.
<!-- P02 -->
### P02: Reporting and publication
- [x] P02-T01: Add deterministic paper exports and availability/dispositions.
- [x] P02-T02: Add bounded result-only publication with resumable git/gh flow.
<!-- P03 -->
### P03: Documentation and validation
- [x] P03-T01: Quick-start/runbook/divergence update and focused new regressions.
- [x] P03-T02: Existing tests, suite validation, dry-run and repeated stub smoke.
<!-- P04 -->
### P04: Review and delivery
- [x] P04-T01: One post-implementation Review with candid requirement assessment.
- [ ] P04-T02: Commit, push and open stacked PR.

## Critique Contract

One fresh critique, read-only except its artifact. Test ownership: parent;
existing tests removed: none; additions: at most two test modules, bounded by
behaviour rather than test count. Canonical targets: study runtime/exporter,
one config, two shell entrypoints, existing docs and divergence; generated targets:
local ignored state and bounded results only. Semantic tests cover accounting,
recovery and publication; existing regressions protect measurement behaviour.
Validation: pytest, reference validation, shell syntax, dry-run and stub smoke.

## Critique Disposition

Execution complete, verdict Revise; all three compatible findings applied
directly without a second critique or user decision:

- PC-001: admission ceiling is <=2,500 credits, including explicit prior pilot
  spending and all attempts. Budget/prior spending are immutable on resume;
  unknown prior spending blocks live execution, never defaults to zero.
- PC-002: persist an absolute study deadline; bound agent/evaluator processes
  with termination, escalation and reaping; record timeout before any retry.
  Do not resume while an owned writer may be alive. Restart never extends time.
- PC-003: exactly one analyzer run per scheduled cell, stable step identity,
  durable step deduplication. All failed attempt costs attach to that same
  step once; unknown costs remain unavailable. A measured failure is never
  retried. Only interrupted/unmeasured work retries from its recorded checkpoint;
  unsafe/ambiguous recovery retains the cell as partial rather than replacement.

Planning Readiness: Ready for safe tooling implementation. Full paid execution
acceptance remains blocked by a provider capability, not a planner choice.

## Implementation Handoff State

P01-P03 complete; final regressions: 337 passed in 40.54s, reference CR1 182/182,
Ruff/ShellCheck/shell syntax/diff checks passed. Five stub sessions completed;
second invocation skipped every durable step. Input fingerprint:
`8c5b26f9bdb574b7bd1bfbc9ee5f42f2316d546bd59515d3ccf413c854644af0`.
No real sessions, freezes, tags or paper changes. P04 Review is Complete with
outcome Not accepted for full live-study capability; only delivery remains.
The full user request cannot be accepted as complete live-study capability:
provider hard billing and a wired paid backend remain unavailable.

## Follow-Up Items

1. Provider-enforced hard credit boundary: prerequisite for any paid execution.
2. Owner freeze/method/registration/independent review gates: no manufactured
   approval; H4/H7, telemetry and proposed decay extensions remain unavailable.

## Handoff

Research: `.copilot-tracking/research/2026-10-26/unattended-runner-research.md`.
Details: `.copilot-tracking/details/2026-10-26/unattended-runner-phase-details.md`.
Critique: `.copilot-tracking/reviews/2026-10-26/unattended-runner-critique.md`.
Changes: `.copilot-tracking/changes/2026-10-26/unattended-runner-changes.md`.
Review: `.copilot-tracking/reviews/logs/2026-10-26/unattended-runner-review.md`.
