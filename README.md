---
title: Feature-consolidation MVE kit
description: Experiment tooling, offline integrity checks and pending study validation
ms.date: 2026-10-26
---

Tooling for the experiment in *Everything but the Software*, Section 8: does a consolidation step after every feature keep agent-built software working, understandable and changeable, and at what cost?

## One-command quick start

On Linux with Python 3.11+, git and make:

```bash
./run-study.sh --smoke
```

This runs **only the offline stub**, one feature in each of A/B/C, then produces
CSV/JSON/Markdown, an SVG figure and LaTeX-includable table/figure fragments in
`.study/stub-smoke/results/`. It spends no AI credits. Run the same command again
to resume; completed cells/steps are skipped. Stub results are diagnostic, never
study evidence. Use a new `--study-id my-smoke` after changing execution inputs
or committing a different source revision.

```bash
./run-study.sh --smoke --dry-run      # read-only offline preflight and schedule
./scripts/bootstrap-vm.sh            # checks only; no installs, sudo or agents
./run-study.sh --dry-run --phase first  # reports all live execution blockers
./run-study.sh --smoke --publish     # explicitly push derived stub results + PR
```

Publication needs authenticated `gh`, git author identity and origin push access.
It uses a separate `results/<study-id>` branch, never pushes raw logs or changes
your source branch, and creates/updates a PR against that source branch.
Files are allowlisted, credential-checked and capped at 512 KiB each / 4 MiB total.

**Paid execution is deliberately unavailable.** Copilot CLI 1.0.103's credit
limit is soft, not a hard spending boundary. The runner enforces a <=2,500-credit
aggregate *admission* ledger with explicit prior spending and unknown-usage
stops, but refuses all real sessions until a provider-enforced hard billing
backend exists. A nominal CLI cap, a freeze file or a container cannot bypass
this stop. No protocol has been frozen or registered by this work. Owner freeze,
H4/H7 definitions, independent reviews and other method gates also remain open.
See [RUNBOOK.md](RUNBOOK.md#unattended-controller) for state, recovery and gates.

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

## Lower-level offline commands

Needs Python 3.11+, git and make on Linux, macOS or WSL.

```bash
cd harness
python3 validate_suite.py ../suites/s1-retrofit          # every test passes on the reference solution
python3 runner.py --config config.dry-run.json --suite ../suites/s1-retrofit --arm B --run-id dry-B-01 --features 10 --phase dry
python3 runner.py --config config.dry-run.json --suite ../suites/s1-retrofit --arm A --run-id dry-A-01 --features 10 --phase dry
python3 analyze.py --runs ../runs-dry --phase dry --out ../results-dry --cost-unit seconds
```

The stand-in agent applies the reference solution, so both arms reach 100%; the point is to check the pipeline, not the hypothesis. Real runs use `config.local.json` or `config.docker.json`, as described in the runbook.

Historical diagnostics used the stand-in through ten features and CR1 and a
paid CLI 1.0.95 feature-1 smoke. They are not new study data. The unattended
controller's smoke is strictly a stub; it never calls Copilot.

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
