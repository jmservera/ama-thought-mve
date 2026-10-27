<!-- markdownlint-disable-file -->
# Unattended study runner: research and paper/harness comparison

## Research brief

Date: 2026-10-26. Task: unattended-runner. Output: comparison preparing planning.
Audience: study owner. Posture: focused, selected from the explicitly bounded
paper, kit and VM requirements. Research disposition: executed.

Questions: What does Section 8 promise that is absent or unrunnable? Which
existing integrity protections must be reused? Can Copilot's exposed credit
controls actually enforce a hard spending ceiling? What can safely run offline?

## Direction controls and participation

The user explicitly requests the entire research/plan-with-critique/implement/
review loop, commits and a stacked PR. Treat that as authorisation to progress
all four phases, not permission to run the study. No Azure, paid agent runs,
tags, protocol registration, invented thresholds or writes to the paper repo.
Only stub smoke and dry runs. Protocol decisions remain owner gates.
No interaction is available or needed for the bounded implementation.

## Extensions and provenance

RPI phase skills selected for lifecycle evidence. Python foundational skill
applies to implementation. Independent critique will be delegated once.
Research is inline: one coupled paper-to-runtime trace does not warrant workers.
No repository-specific instructions were found in `.github`.
Trusted evidence root: `.copilot-tracking/research/2026-10-26/`.

## Research cycle 1

### Wider

Read the paper's consolidation and experiment sections, repository inventory,
README and CLI help. The paper explicitly has no new results and lists unresolved
registration, method, access and telemetry gates. Existing kit implements
single trajectories and analysis, not study orchestration.

Reflection: build an execution wrapper, not a replacement study or an assertion
that all unresolved scientific claims can now be evaluated.

### Deeper

The single-run implementation creates fresh repositories, enforces example
integrity and C's edit boundary, but refuses existing directories and stops on
exceptions. The analyzer already preserves zero-step/partial metadata runs and
unavailable costs. Reuse those behaviours instead of parallel reimplementation.

Reflection: resumability needs durable per-cell state, per-attempt provenance,
pre-launch reservation, transactional checkpoint rollback and no replacement runs.

### Contrarian

CLI 1.0.103 help exposes final-only usage output and `--max-ai-credits`.
Authoritative installed CLI documentation explicitly identifies the AI credit
limit as a **soft cap**. Killing a process on a timeout cannot bound in-flight
provider billing. An honest hard billing guarantee is unavailable with this
backend. A launch ledger can enforce admission against reconciled usage plus
reservations, but cannot turn a soft provider cap into a hard spending bound.

Reflection: reject an invented overshoot allowance or a boolean "hard cap"
assertion. Paid execution must fail closed while this requirement is unmet.
The runner and stub pipeline can still be implemented and tested end-to-end.

## Findings, evidence, decisions and readiness

## Evidence log and complete gap inventory

| ID | Source | Finding / missing or unrunnable surface |
| --- | --- | --- |
| C1 | `README.md:45`, `harness/runner.py:328`, `harness/schedule.py:11` | Multi-command manual scheduling; no one-command orchestrator, persistent schedule, lock, resume, bounded retry or aggregate timeout. Existing directories abort rather than resume. |
| C2 | `RUNBOOK.md:25`, `RUNBOOK.md:239`, `harness/runner.py:153` | Budget reconciliation is manual. No aggregate ledger, active reservation or unknown-usage stop. Final-only usage can be absent after interruption. |
| C3 | `harness/config.local.json:15`, `harness/config.docker.json:15`, `harness/Dockerfile:8`, `harness/requirements-measure.txt:2` | Placeholder model, mutable image/tool installs, no integrated version/preflight checks, no bootstrap checker. |
| C4 | `harness/runner.py:101`, `harness/runner.py:143`, `harness/config.docker.json:26` | Fresh local git repo isolates histories only; Docker mounts all step output (including subsequent hidden scores if reused), permits network, and has no immutable image gate, resource limits or credential-minimal host evaluation sandbox. |
| C5 | `harness/analyze.py:27`, `harness/analyze.py:157`, `divergence-log.md:97` | Existing corrected analysis retains failed/zero-step/partial runs; preserve this. No schedule-wide disposition table, retry ledger or durable interruption recovery. |
| C6 | `harness/analyze.py:688`, `harness/analyze.py:775` | Markdown/JSON/series and optional PNG exist; no deterministic dependency-free figure, LaTeX fragments, flat hypothesis/interval tables, disposition/coverage/cost/availability reports or publication workflow. Optional missing matplotlib is silently ignored. |
| C7 | `harness/analyze.py:734`, `RUNBOOK.md:307` | Per-run OLS is not the paper's proposed mixed-effects model. Bootstrap diagnostics, model/precision and interval decisions require prospective reconciliation; do not silently fit a different method. |
| C8 | `harness/analyze.py:603`, `harness/analyze.py:677`, `RUNBOOK.md:331` | H4 comprehension ingestion, scoring, non-inferiority and blinded human review absent. H7's endpoint/scale/dependent contrast/zero-gap policy unresolved; existing component is not a full H7 endpoint. |
| C9 | `harness/runner.py:214`, `harness/analyze.py:180`, `protocol/experiment-design.md:103` | Paper's proposed frozen contract eligibility map, P-only inherited cohorts, F/P loss episodes, recurrence/duration, same-cycle losses, repeated oracle checks, reference-gap sensitivities and propagation annotation are not implemented. Existing regression series is not the full amendment. Optional repeated-change probe and S2 are not authorised. |
| C10 | `README.md:24`, `RUNBOOK.md:342` | HIR/IDR extraction, traceable events/outside-CLI coverage and author adjudication absent; no independent annotation reliability. Missing telemetry must remain unavailable, not zero intervention. |
| C11 | `RUNBOOK.md:131`, `protocol/mve-plan.md:1` | Independent oracle review, verified freeze hashes/registration/prior-data chronology, actual access probes and all owner method gates remain incomplete. Existing `protocol-frozen` tag is historical, not authorisation for this code. |
| C12 | `harness/runner.py:236`, `harness/runner.py:328` | Existing implementation continues after failed features and runs B/C regardless; evaluator outputs are external but local filesystem-accessible. These policies need explicit prospective owner acknowledgement, not unrecorded runner defaults. |
| C13 | `RUNBOOK.md:348`, `results/smoke/summary.json:1` | No bounded, sanitised result-only commit/push/PR automation; prior smoke results must never be pooled into new data. |
| C14 | `../ama/docs/capstone/thought-leadership/everything-but-the-software/main.tex:1262` | Paper consolidation package is tests/metrics, checklist, TCR, behaviour-pinning tests and <=300-word replacement note. Existing prompts enforce by instruction, not complete machine verification of treatment fidelity or quality-budget stop. |
| C15 | `../ama/docs/capstone/thought-leadership/everything-but-the-software/main.tex:1323`, `:1503`, `:1900`, `:1925` | Section 8 says no results, 4 runs/arm, 10 features+CR1, 212 sessions, exploratory framing; D11 selected local execution. Requested Docker runner is a proposed isolation amendment, not authority to revise the paper or freeze. Results must include estimates/intervals, trajectories, missingness and null/negative findings without confirmatory claims. |
| C16 | `RUNBOOK.md:31`, installed Copilot CLI 1.0.103 help and authoritative CLI documentation retrieved 2026-10-26 | Soft caps/final-only accounting cannot establish hard actual AI-credit bounds. No provider-enforced hard limit interface is available in the inspected CLI. |

## Decisions, alternatives and readiness

Accepted: reuse `Run` enforcement and the corrected analyzer; add an offline-safe
orchestrator and deterministic exports; gate every live mode on complete freeze,
registration/method decisions and a genuinely enforceable credit boundary.
Rejected: silently choose H4/H7 definitions, equate Docker or deny rules with
proven containment, manufacture mixed-model results, or call a soft cap hard.
Deferred: independent human approvals, actual provider billing integration,
telemetry adjudication, optional scientific extensions and real runs.

Planning Readiness: **Ready for implementation of safe tooling**, not for study
execution. One wider/deeper/contrarian cycle covers all named surfaces; another
cycle cannot resolve owner decisions or manufacture a provider hard-limit API.
No external search or delegated research was necessary. All paper access was
read-only. Prior source assertions were verified directly rather than accepted
as study evidence. Main residual blocker: no supported hard billing backend.
