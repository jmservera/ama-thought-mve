---
title: Feature-consolidation MVE kit
description: Experiment tooling, offline integrity checks and pending study validation
ms.date: 2026-10-25
---

Tooling for the experiment in *Everything but the Software*, Section 8: does a consolidation step after every feature keep agent-built software working, understandable and changeable, and at what cost?

## Integrity correction status

The measurement-integrity branch corrects TCR rollback/logging, partial-feature
evaluation, suite validation, metrics and interval-based analysis. It does not
register or approve a study. The existing `protocol-frozen` tag and earlier
runs/results are preserved; these code and method changes need reconciliation
with a new authorised snapshot before registration and fresh confirmatory runs.

Evaluator, metric and test subprocesses use an allowlisted environment and
temporary home/cache directories, but this is not an OS or network sandbox.
Direct CLI callers retain their own process environment. Generated code can still
reach host files and hidden/reference assets subject to host permissions.
No access-probe acceptance or containment is established by these fixes.

The analyzer reports full H4 as not evaluable without comprehension evidence,
and full H7 as not evaluable without its H3 package comparison. HIR telemetry
extraction is not implemented by these changes. Independent suite review,
remaining method decisions, runtime/access checks and registration remain gates.

The later owner-authorised follow-up retains partial and zero-step runs in
reports without treating them as completed trajectories. Planned feature and
post-feature coverage controls endpoint, slope and cost availability; observed
measurements and costs remain descriptive. The original adverse Review is
preserved separately from the follow-up's implementation/test evidence in
[divergence-log.md](divergence-log.md).

| Folder | What it holds |
| --- | --- |
| `RUNBOOK.md` | Step-by-step instructions, decisions to freeze, time and cost, troubleshooting. Start here. |
| `protocol/` | Earlier design drafts, not evidence of completed registration. Reconcile the exact approved snapshot and divergence record before making a new freeze. |
| `harness/` | `runner.py` (one run of one arm), `measure.py` (hidden tests and metrics, outside the agent), `analyze.py` (hypothesis table), `schedule.py` (randomised run order), `validate_suite.py` (tests the tests), `fake_agent.py` (offline dry run), prompts, configurations and the agent `Dockerfile`. |
| `skeleton/` | The starting repository for every run: `Makefile`, `tcr`, quality report, empty package. |
| `suites/s1-retrofit/` | Suite S1: ten features and the change request CR1, each with a specification and API, visible tests, hidden tests (142 in total) and a cumulative reference solution. Validated; needs your review before the freeze. |

## Quick start: offline dry run (no agent, no network)

Needs Python 3.11+, git and make on Linux, macOS or WSL.

```bash
cd harness
python3 validate_suite.py ../suites/s1-retrofit          # every test passes on the reference solution
python3 runner.py --config config.dry-run.json --suite ../suites/s1-retrofit --arm B --run-id dry-B-01 --features 10 --phase dry
python3 runner.py --config config.dry-run.json --suite ../suites/s1-retrofit --arm A --run-id dry-A-01 --features 10 --phase dry
python3 analyze.py --runs ../runs-dry --phase dry --out ../results-dry --cost-unit seconds
```

The stand-in agent applies the reference solution, so both arms reach 100%; the point is to check the pipeline, not the hypothesis. Real runs use `config.local.json` or `config.docker.json`, as described in the runbook.

The kit was dry-run end to end with the stand-in agent in all three arms, through all ten features and the change request (plus tampered tests and an undelivered feature), and smoke-tested with GitHub Copilot CLI 1.0.95 on feature 1.

## Regression checks

Use the project's existing virtual environment; no model access is needed:

```bash
.venv/bin/python -B -m pytest -p no:cacheprovider harness/tests -q
.venv/bin/python -B harness/validate_suite.py suites/s1-retrofit
bash -n skeleton/tcr
shellcheck skeleton/tcr
```

The TCR helper is ported from AMA commit
`e3a104df8f55500a82047b56700e9a161be8c708`, where the original private
`skeleton/tcr` from `20e7f97c5c162cffd0f771ce501e146081912edc` was
corrected. Its tests use fake commands in disposable fixtures. Never run TCR
against this kit checkout or any repository containing work you need to keep.
Its rollback discards uncommitted work; the `reports/` clean exclusion preserves
untracked reports only, not tracked files reset by Git. Separate worktrees are
still required for concurrent real Git operations.

The reference stand-in checks pipeline mechanics, not agent performance or the
hypotheses. Use new run IDs and output directories; never overwrite prior data.
