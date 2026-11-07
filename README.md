---
title: Feature-consolidation MVE kit
description: Experiment tooling, offline integrity checks and pending study validation
ms.date: 2026-10-26
---

Tooling for the experiment in *Everything but the Software*, Section 8: does a consolidation step after every feature keep agent-built software working, understandable and changeable, and at what cost?

**Prospective five-arm release:** D/E and researcher-selectable 12/21/33
replicates (default 12) supersede the historical v4 allocation. See the
[current amendment and remaining collection gates](protocol/five-arm-amendment-2026-11-02.json).
Releasing the verified source for OSF does not register it or authorize collection.

**Current scope:** a five-arm S1 **pilot/estimation study**, not seven
confirmatory hypothesis tests. Start with [the canonical protocol](protocol/pilot-estimation.md)
and [OSF submission draft](protocol/osf-preregistration.md). Source paper is pinned
to `196b97644bb9bffa43d41a9921d6a06a93b2699e`, with the owner's explicit
three-model amendment: GPT 6.1 Sol, Sonnet 5.5 and Gemini 4 Argon.
The prospective five-arm amendment implements the paper's D (longer delivery)
and E (visible behavioural repair), with 12/21/33 trajectories per arm/model,
default 12 (180 study trajectories); 15 excluded calibration trajectories.
The total ceiling is **300,000 AI Credits**, including prior spend/calibration,
with 300-credit nominal session allowances, except D's 600-credit feature step.
Operational soft thresholds are 270 and 540 respectively. Historical owner approval for preregistration
submission is recorded on 28 October 2026: document licence CC BY-NC-ND 4.0
and embargo through 2026-12-31. The original registration is now
[owner-confirmed approved](https://osf.io/ywsrv/overview).
Subsequent approved corrections await
[prospective OSF recording](protocol/prospective-corrections-2026-10-28.md);
prospective amendment completion and execution authorization remain open.
On 30 October the owner individually accepted the six scientific scopes for
`90e393e` and selected an explicitly **owner-reviewed exploratory pilot**, without
independent scientific acceptance. This limitation and policy change must be
recorded prospectively in OSF; no independent review is claimed. See
[the decision record](protocol/scientific-acceptance-2026-10-30.json).
The owner also accepted corrected `1120002` runtime/access evidence under
explicit owner review, without independent reviewers for this first study.
The separate executor provides operational separation, not independent review.
See [the runtime decision record](protocol/runtime-acceptance-2026-10-30.json).
All permission, isolation, accounting and final freeze safeguards remain.
The [security refresh](protocol/security-remediation-2026-10-30.json) and
[Debian component hardening](protocol/security-hardening-2026-10-30.json)
remain historical evidence, as does
[the earlier Alpine adoption](protocol/security-alpine-adoption.json).
On 31 October the owner authorized
[the qualified Expat-free runtime](protocol/security-expat-removal-2026-10-31.json),
verified publication, final acceptance and a replacement freeze.
Pytest and attribution rules remain; internal reporting now uses strict JSON.
Signed no-Expat Git replaces the Expat/Python-XML build families; archive-free
BusyBox remains. The private candidate passed 25 canaries, 794 harness tests,
16 SDK tests and 33 exact scientific comparisons to both baselines, with no skips.
Final production-source validation and receipt binding are required before freeze.
Container XML parsing and Git WebDAV push are deliberately unavailable.
The historical Expat exception is not needed for the parser-free image; this is
component removal, not an upstream fix or an all-clear. General candidate
resource exhaustion/missingness remains possible under unchanged safeguards.

[CONTRIBUTOR.md](CONTRIBUTOR.md) documents the separate complete source/setup
bundle, offline checks, read-only user-budget audit and actual launch blockers.

The controller schedules the model-aware allocation, preserves model/replicate
identity on resume. The five-arm primary B-D contrast equally weights the three
within-model coverage differences, with whole-trajectory stratified resampling;
per-model and other contrasts are secondary, not substitutes for a missing primary.
Historical ABC analysis remains separate. Infrastructure retries share the original step allowances;
measurement retries do not replay agent work. Owner scientific alignment
and runtime/access acceptance are recorded for their named sources; the final
replacement source freeze was authorized on 31 October; its exact inputs
are recorded in [the freeze manifest](protocol/freeze.json).
The prospective OSF amendment date remains unset, so the launcher still blocks
collection. OSF recording is last; no new model calls are authorized.

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
./run-study.sh --dry-run --phase pilot-estimation  # default 180 trajectories; no agent calls
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
current model/arm.
Before a new interactive estimation launch, the researcher chooses **12, 21 or
33 independent trajectories per model/arm**; Enter selects **12**. The default
five-arm allocation is 180 trajectories and 3060 planned sessions. Calibration
remains one trajectory per model/arm (15 trajectories, 240 sessions).
An optional one-feature calibration contains 15 trajectories and 24 sessions
(15 feature sessions and nine post-steps). It is a proposed change, not the
registered 240-session calibration. It requires a prospective amendment, a new
source/runtime freeze and separate launch authorization:

```bash
./run-study.sh --phase calibration --study-id excluded-short-calibration --short-calibration --dry-run
```

The short sample does not observe later-feature or change-request costs. Its
cost-only extrapolation is uncertain and cannot establish affordability by itself.
Never reuse the interrupted calibration's study ID or discard its ledger.

For unattended execution or a read-only preview:

```bash
./run-experiment.sh --replicates 12
./run-experiment.sh --replicates 21 --dry-run
./run-experiment.sh --replicates 33 --dry-run
```

The chosen count is saved in immutable study identity and all trajectory
metadata; resume reuses it and rejects a different count. Choose and record
the allocation prospectively, never based on observed study results.
This selection does not establish80%power:12,21and33correspond to different
assumed variabilities, not measured guarantees. D has one uninterrupted
45-minute feature session (600 nominal / 540 soft credits) and no post-step.
E has an ordinary feature session followed by 15-minute visible-specification
repair, never hidden-test feedback. Accepted Python test files are immutable;
E's explicit correction exception requires blob-bound visible-specification
quotes and retained explanations in `REPAIR.json` and the private step journal.
This provenance validation is not independent semantic adjudication.
Changing this source requires new source/runtime qualification and prospective
freeze/registration evidence; the historical published v4does not authorize it.
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
(**540 for D feature sessions**, below the corresponding 600 nominal allowance)
(shared across any infrastructure retry), below the registered 300, and a
**270,000-credit local study admission stop**, below the unchanged registered
300,000-credit envelope. Known prior **146.17332 credits**, calibration, probes and
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
source/evidence-bound unknown provision. A later excluded Sonnet P1 diagnostic
also lacked complete billing and retains a fourth 300-credit hold. Prior known usage was
**49.74337**,
including **3.05509** from three subsequent successful excluded backend checks
at `eff4d09` and **4.19186** from the separately authorized audited Sonnet P1
session (see [prior-data disclosure](protocol/prior-data-disclosure.md));
the corrected excluded three-model P1 check adds **27.95318** with complete billing.
The first v4 three-model P1 batch then stopped on overlapping GPT tool requests,
before verified results. Its uncertified receipt retains a fifth 300-credit hold.
The owner directed implementation and completion of the excluded check; the
local correction serializes already-authorized tool calls and makes cleanup
robust to broken stdin, without widening permissions or isolation.
The interrupted v7 calibration added **96.42995** settled credits. Its tenth
attempt has unknown usage and an owner-approved **600-credit** hold, not a
confirmed charge or guaranteed upper bound. The original ledger remains private
and unchanged. Known usage is **146.17332** and **2100 credits** are held
separately, not booked as spending or certified zero.
Known usage plus held budget is **2246.17332**, leaving **267753.82668** within
the 270000 local admission threshold. Total actual prior usage remains unknown.
These provisions are not guaranteed billing bounds. Future
unknown usage still stops new work; live verification and collection gates remain.
Calibration and estimation use separate ledgers: before estimation, reconcile
all short-calibration charges into its configuration and review affordability.
The published v4 freeze/release does not include this local transport correction.
Corrected paid checks use a separate source-qualified diagnostic manifest, not
registered collection or a replacement public freeze.
One corrected P1 cycle each for GPT6.1Sol, Sonnet5.5 and Gemini4Argon produced
verified native measurements/journals and complete model/effort/usage receipts.
These checks remain private excluded diagnostics, not study observations.

Evaluator staging uses explicit readable input modes under private parent
directories, including when the host uses `umask077`. Read-only mounts and
candidate isolation are unchanged. The audited paid output was verified through
an offline continuation, not an uninterrupted registered launcher run.
The owner confirms neither v2 nor v3 was registered on OSF; their code freezes
remain historical. Prepare the corrected v4 materials prospectively before collection.

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
`protocol/pilot-estimation.json`. The six scientific scopes are owner-accepted
under the prospectively disclosed owner-review policy; independent scientific
review is deferred. Runtime/access and freeze/OSF requirements remain
**before collection**. Follow [the OSF checklist](protocol/osf-submission-checklist.md):
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
