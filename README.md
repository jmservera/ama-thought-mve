---
title: Feature-consolidation MVE kit
description: Experiment tooling, offline integrity checks and pending study validation
ms.date: 2026-10-26
---

Tooling for the experiment in *Everything but the Software*, Section 8: does a consolidation step after every feature keep agent-built software working, understandable and changeable, and at what cost?

**Current scope:** an eighteen-trajectory S1 **pilot/estimation study**, not seven
confirmatory hypothesis tests. Start with [the canonical protocol](protocol/pilot-estimation.md)
and [OSF submission draft](protocol/osf-preregistration.md). Source paper is pinned
to `196b97644bb9bffa43d41a9921d6a06a93b2699e`, with the owner's explicit
three-model amendment: GPT 6.1 Sol, Sonnet 5.5 and Gemini 4 Argon, two
trajectories per arm/model; nine excluded calibration trajectories.
The total ceiling is **300,000 AI Credits**, including prior spend/calibration,
with fixed 300-credit/session soft caps. Owner approval for preregistration
submission is recorded on 28 October 2026: document licence CC BY-NC-ND 4.0
and embargo through 2026-12-31. The original registration is now
[owner-confirmed approved](https://osf.io/ywsrv/overview).
Subsequent approved corrections await
[prospective OSF recording](protocol/prospective-corrections-2026-10-28.md);
independent exact-source acceptance and execution readiness remain open.

[CONTRIBUTOR.md](CONTRIBUTOR.md) documents the separate complete source/setup
bundle, offline checks, read-only user-budget audit and actual launch blockers.

The controller schedules the model-aware allocation, preserves model/replicate
identity on resume and exports separate primary estimates per model, never a
pooled primary result. Infrastructure retries share the original step allowances;
measurement retries do not replay agent work. Independent
`multi_model_harness_alignment` acceptance is still required before collection;
implemented engineering is not study approval.

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
./run-study.sh --dry-run --phase pilot-estimation  # 18 model-aware trajectories; no agent calls
./run-study.sh --smoke --publish     # explicitly push derived stub results + PR
```

Publication needs authenticated `gh`, git author identity and origin push access.
It uses a separate `results/<study-id>` branch, never pushes raw logs or changes
your source branch, and creates/updates a PR against that source branch.
Files are allowlisted, credential-checked and capped at 512 KiB each / 4 MiB total.

### Run the accepted experiment

After one-time VM preparation, source/runtime acceptance, the prospective OSF
update and owner launch authorization, run:

```bash
./run-experiment.sh
```

It uses the **Copilot user already signed in on the host**; no identity or
credentials are copied into Docker. The local Python environment is selected
automatically. Progress shows completed/total steps, remaining steps and the
current model/arm. The default pilot has 318 planned steps.
Rerun the same command for permitted durable recovery; `--status` shows saved
progress without model calls.

A shareable, credential-checked ZIP is generated automatically at
`.study/pilot-estimation/pilot-estimation-results.zip`, alongside the readable
`results/report.md`. `./run-experiment.sh --share` recreates that ZIP without
running models or uploading anything. See the
[operator instructions](CONTRIBUTOR.md#run-and-share-in-one-command).
**The convenience launcher does not bypass the currently pending readiness gates.**

**Credit limits are soft; the owner accepts the residual financial risk.**
The supplied settings use a 10% buffer: **270 AI Credits per original session**
(shared across any infrastructure retry), below the registered 300, and a
**270,000-credit local study admission stop**, below the unchanged registered
300,000-credit envelope. Prior **14.54324 credits**, calibration, probes and
every attempt count. [CLI session limits](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/set-session-limit)
allow an in-flight response to finish **over** the limit; the buffer reduces risk
but guarantees neither per-session nor total billed consumption. The company
hard limit is **1,000,000 credits per collaborator**, as reported by the owner,
not independently verified or a study-specific stop. A separate provider-enforced
study hard cap is no longer required; the read-only budget audit is optional.
See [CONTRIBUTOR.md](CONTRIBUTOR.md#billing-soft-limits-and-the-accepted-risk)
for monitoring, reset and overrun instructions.

**Historical budget provisions:** three excluded empty-workspace runtime checks
failed, first during SDK setup and then twice on unexpected built-in MCP startup.
None produced tool calls or complete usage evidence. On 29 October the owner
separately approved retaining each 300-credit reservation as an exact
source/evidence-bound unknown provision. Known usage remains **14.54324**;
**900 credits** are held separately, not booked as spending or certified zero.
Known usage plus held budget is **914.54324**, leaving **269085.45676** within
the 270000 local admission threshold. Total actual prior usage remains unknown.
These provisions are not guaranteed billing bounds. Future
unknown usage still stops new work; live verification and collection gates remain.

**The isolated live backend is a candidate implementation, not collection
approval.** It uses repository-local Copilot SDK **1.0.28** with CLI **1.0.105**:
authentication stays on the trusted host; the model receives only a restricted
container tool. Scientific/source acceptance, actual live usage/model evidence,
source-bound runtime canaries, owner freeze and the prospective OSF update remain
separate gates. No protocol has been frozen or registered by this tool.
See [CONTRIBUTOR.md](CONTRIBUTOR.md#isolated-live-backend-acceptance-pending).
See [RUNBOOK.md](RUNBOOK.md#unattended-controller) for state, recovery and gates.

## Integrity correction status

The measurement-integrity branch corrects TCR rollback/logging, partial-feature
evaluation, suite validation, metrics and interval-based analysis. It does not
register or approve a study. The existing `protocol-frozen` tag and earlier
runs/results are preserved; these code and method changes need reconciliation
with a new authorised snapshot before registration and fresh pilot collection.

Lower-level offline evaluator commands use an allowlisted environment and
temporary home/cache directories, not an OS or network sandbox. They are not
the new non-smoke controller path: that path runs candidate tools, visible tests,
hidden imports and metrics in separate disposable containers. Do not use legacy
direct-runner configurations to execute generated code on the operator host.
Offline test success does not establish live model/access or scientific acceptance.

Default analysis estimates H1 coverage, H2 retained-contract losses and H6 CR1
with missingness and all-attempt costs; it issues no hypothesis verdicts.
Formal H4/H7 claims are deferred, not undefined thresholds to supply.
HIR/IDR remain unavailable without verified coverage/adjudication. Independent suite review,
remaining method decisions, runtime/access checks and registration remain gates.
Those are collection gates, not requirements for ordinary OSF preregistration.

The later owner-authorised follow-up retains partial and zero-step runs in
reports without treating them as completed trajectories. Planned feature and
post-feature coverage controls endpoint, slope and cost availability; observed
measurements and costs remain descriptive. The original adverse Review is
preserved separately from the follow-up's implementation/test evidence in
[divergence-log.md](divergence-log.md).

| Folder | What it holds |
| --- | --- |
| `RUNBOOK.md` | Step-by-step instructions, decisions to freeze, time and cost, troubleshooting. Start here. |
| `protocol/` | Current pilot protocol, OSF draft, decision ledger and candidate contract panel; older proposals explicitly labelled historical. |
| `harness/` | Runner, external measurement, estimation-only analysis/exports, offline registration packager and suite validation; historical verdict analysis requires `--legacy-proposal`. |
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

The stand-in agent applies the reference solution; it checks pipeline mechanics,
not agent performance. Historical local/Docker configurations are not launch
authorisation. The unattended live backend remains gated on exact-source evidence
and owner acceptance.

## Prepare an offline OSF draft

```bash
.venv/bin/python -B harness/contract_panel.py --out protocol/contract-panel.json --check
.venv/bin/python -B harness/prepare_registration.py --out .study/osf-draft
```

The package refuses overwrites and contains only explicit submission inputs,
source hashes and readiness checks, not raw logs. It neither contacts OSF nor
registers or authorises a run. Owner choices are recorded in
`protocol/pilot-estimation.json`. Model-aware harness acceptance
and independent reviews remain pending **before collection**, not prerequisites
to submit the plan. Follow [the OSF checklist](protocol/osf-submission-checklist.md):
confirm owner choices, secondary scope and prior-data disclosure, disclose the
unreviewed/unverified status, and approve the exact snapshot before submitting
through OSF. Readiness reports separate `submission_unresolved` from
`collection_unresolved`; `unresolved` aliases submission blockers. No
registration URL is required to prepare a draft. Use a new directory when
regenerating it. Preparing or registering the plan never authorises execution.

The controller's `calibration` (legacy `pilot`) proposes nine excluded
ten-feature runs without CR1; `pilot-estimation` (legacy `first`) proposes
eighteen with CR1. Never pool stages or turn
historical development smoke into registered pilot data.

After committing a corrected delivery candidate, prepare the separate private
operator source package (not another OSF submission attachment):

```bash
.venv/bin/python -B harness/prepare_contributor.py --out .study/contributor-CANDIDATE
.venv/bin/python -B harness/prepare_contributor.py --verify .study/contributor-CANDIDATE.tar.gz
```

It includes runnable source and a shallow exact-commit Git checkout, excludes
private study data, refuses overwrites and verifies file hashes/private modes.
It contains held-out evaluator/reference material: trusted operator only,
never a model-visible workspace. Paid execution remains disabled.

For standalone analysis of controller runs, supply its explicit journal:

```bash
.venv/bin/python -B harness/analyze.py --runs .study/STUDY-ID/runs \
  --study-state .study/STUDY-ID/state.json --out .study/STUDY-ID/reanalysis
```

Without a matching journal, measured-step costs remain descriptive and
**all-attempt** consumption is unavailable. Empty attempt lists are not assumed
free without no-billing evidence. Final H2 contrasts use P10 open losses;
accumulated test-cycle losses are separately labelled descriptive companions.

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
