---
description: "Runbook for the feature-consolidation MVE with D1-D12 settled on 2026-10-25."
---
# Runbook: running the feature-consolidation MVE

The active scientific authority is [protocol/pilot-estimation.md](protocol/pilot-estimation.md).
Prepare [the OSF draft](protocol/osf-preregistration.md), resolve the decision
ledger and approve the exact submission candidate. Independent acceptance is
a project prerequisite before collection, not before ordinary OSF registration.
Use [the OSF checklist](protocol/osf-submission-checklist.md) and disclose
independent reviews and runtime/access checks as pending.
Owner submission approval is now recorded for 235489c content plus selected
metadata/approval updates: CC BY-NC-ND 4.0 for submission documents and embargo
through 2026-12-31. Enter settled contributor/affiliation details directly in
OSF. The owner subsequently confirmed submission and approval of the unchanged
original 763945b package: https://osf.io/ywsrv/overview.
The later corrected candidate needs
[prospective recording](protocol/prospective-corrections-2026-10-28.md) and
source-bound approval. No independent acceptance or collection permission
is implied; all execution gates below remain in force.
See [CONTRIBUTOR.md](CONTRIBUTOR.md) for the complete separate source bundle,
accepted soft-limit policy, optional budget audit and unverified live-runtime requirements.
The owner-amended first pass is an estimation pilot, not confirmatory testing:
GPT 6.1 Sol, Sonnet 5.5 and Gemini 4 Argon, each with two trajectories per A/B/C
arm (18 pilot, plus nine excluded calibration). There are 318 pilot and 150
calibration sessions, at most 193.5 combined agent-hours. The current total
registered envelope is **300,000 AI Credits**, prior spend/calibration included.
The owner accepted soft-limit overshoot risk on 29 October: supplied operational
settings are **270 credits/session** and a **270,000-credit local admission stop**,
10% below the nominal 300/session and 300,000 study envelope. In-flight responses
can exceed CLI soft limits; neither buffer guarantees final billed consumption.
The company hard limit of 1,000,000 credits/collaborator is owner-reported,
not independently verified or a study-specific stop. A separate provider study
hard cap is no longer required. The approximately $3,000 equivalent is unverified;
the earlier $500 limit and intermediate $6,000 proposal are superseded.

The controller implements the model matrix, immutable model/replicate identity,
270,000-credit local admission stop and bounded infrastructure retries; analysis
exports separate primary estimates per model. Before collection, require
independent `multi_model_harness_alignment` evidence covering scheduling,
model-specific inference, budgets and selected operational rules. The isolated
backend is implemented as a candidate; actual live model/accounting evidence
and independent/source-bound owner acceptance remain unresolved.

> [!IMPORTANT]
> D1-D12 from 25 October remain historical decisions where compatible with the
> pinned paper. The 27 October prospective amendment defers formal H4/H7,
> retains H1/H2/H6 as estimation labels. Owner policy choices are now recorded;
> required independent/alignment evidence remains null.
> A complete draft is not owner approval, completed registration or execution readiness.
> `submission_unresolved` lists plan/disclosure/owner-approval blockers;
> `collection_unresolved` retains outstanding scientific/operational checks.
> `unresolved` aliases submission blockers. No checks have been marked accepted.

The measurement-integrity correction is recorded in [divergence-log.md](divergence-log.md).
It preserves earlier data and the existing `protocol-frozen` tag. Reconcile its
implemented analysis with the approved plan before creating a new versioned
freeze or registration; this correction is not an approval to run the study.

Tool facts were checked on 24 October 2026 against GitHub Copilot CLI 1.0.95 help and the official documentation. The latest CLI release at that date was 1.0.103. Re-check the flags on the version you pin.

## Unattended controller

The 26 October controller adds a single command, not permission to run the
study. The older manual procedures below are historical operator instructions,
**not a way around its safety gates**. The current isolated-backend candidate
does not authorize a paid study merely by being installed.

```bash
./run-study.sh --smoke
```

Smoke requires only Linux, Python 3.11+, git and make. It is one feature per
A/B/C, five fake-agent sessions total, with no CR1. The fake agent deliberately
attempts a forbidden C edit to exercise enforcement. No token, Docker, network,
Copilot or plotting dependency is required. All output is explicitly diagnostic.
The check-only `./scripts/bootstrap-vm.sh --smoke` checks this minimal VM;
without `--smoke` it reports live tool/version/auth/freeze/budget blockers.
It never installs anything, invokes sudo, changes groups or provisions services.
If using a virtual environment, activate it or set `PYTHON=/path/to/python`;
keep required executables on PATH.

`./run-study.sh --dry-run --phase pilot-estimation` (legacy `first`) prints an 18-cell
schedule (two runs per A/B/C per model, ten features and CR1, 318 sessions) and all
preflight blockers. `--phase calibration` (legacy `pilot`) proposes one run/arm/model,
ten features and no CR1: nine trajectories/150 sessions, excluded from the eighteen.
Replicate numbers are unique within each arm/model pair and intentionally repeat
across other arms/models. Counts are planned sessions: permitted infrastructure
retries can add calls but share the original step's time/credit allowance.
Confirmatory collection is
outside this pilot protocol. Dry-run never creates state or
calls `copilot -p`. `--smoke --dry-run` checks only offline prerequisites.
An unsuccessful preflight exits 2, a partial pipeline exits 1, success exits 0.
No unattended main-study mode is authorised.

### Configuration and real execution gates

The operator entry point is `./run-experiment.sh` on the prepared and accepted VM.
It selects the local environment, verifies the signed-in host Copilot user before
credit reservation, shows completed/remaining steps and creates a derived-only
results ZIP. `--status` and `--share` read saved work without model calls or
authentication. No credentials enter Docker and no results upload is automatic.
See [one-command instructions](CONTRIBUTOR.md#run-and-share-in-one-command).
The existing readiness/freeze/registration gates still apply.

The controller reads `harness/study-config.json`; `--config PATH` selects a
different JSON object. Its settings are seed, ceiling (positive, never >300,000 AI
credits; supplied 270,000), prior spending, per-session reservation, separate
integer CLI soft limit (30 through 300; supplied 270), maximum attempts,
absolute study allowance and minimum disk space. Historical owner-confirmed
usage is **14.54324**; three excluded runtime checks still have unknown usage. The
owner separately approved each full **300-credit** reservation as a historical
budget provision on 29 October. `prior_credits` records only known usage;
`historical_credit_provisions` binds each hold to its exact approved
attempt/source/ledger digest. Admission counts known usage plus **900 held**,
leaving **269085.45676**
before new reservations. Actual historical total remains unknown; reports
explicitly disclose that incompleteness. All three original private ledgers are unchanged.
Do not infer zero, call the provision actual spending, or apply this exception
to future failures. Future incomplete usage and overruns still stop admission.
Live checks and collection still require separate acceptance. See the prior-data disclosure and
[collaborator hold instructions](CONTRIBUTOR.md#billing-soft-limits-and-the-accepted-risk).
Smoke explicitly has zero paid usage and does not consume a live allocation.
No config field contains a token. The live SDK uses approved interactive user
authentication on the trusted host; an environment token is not required.
The optional billing audit has a separate credential requirement. `.env` is
ignored, never loaded by the controller and never eligible for publication.

The supplied finite study deadline is 14 days. Each original study step keeps its
30/15/45-minute allowance and original 270-credit soft allowance across at most
two agent attempts. The nominal initial reservation stays 300, allowing 30
credits of headroom. Later attempts reserve the remaining original allowance
plus that headroom, not a fresh 300. Unknown/exhausted time or usage blocks a
retry; below the CLI's 30-credit minimum, stop rather than top up.
Measurement infrastructure may be retried once on the same retained snapshot,
without replaying agent work; exhausted evaluation retries remain exhausted on
resume. A snapshot inconsistency halts collection rather than rerunning until green.

Live host checks include Python, git, Node, Docker, Copilot **1.0.105**, the
repository-local SDK **1.0.28**, free disk, clean Git, known prior spending and
owner freeze provenance. No model calls are used to check versions.
The isolated image contains Ruff **0.17.3**, Lizard **1.24.3** and jscpd **5.4.1**;
its actual toolchain/profile is checked by offline canaries. Host `gh` is needed
only for explicit publication, not model transport. Legacy image recipes and
direct local command templates are not the selected runtime.

For the owner's 28 October prospective toolchain amendment, use the pinned
Python requirements and a repository-local duplication tool, without changing
global installations:

```bash
.venv/bin/python -m pip install -r harness/requirements-measure.txt
npm install --prefix .study/runtime-tools --no-audit --no-fund --save-exact jscpd@5.4.1
export PATH="$PWD/.venv/bin:$PWD/.study/runtime-tools/node_modules/.bin:$PATH"
```

Separately ensure the selected Copilot executable reports exactly 1.0.105.
These setup commands install tools, not model access, isolation or billing
controls. Do not start a study to test them. The original reviewer packet is
superseded for changed inputs, not overwritten; use a fresh candidate and
[the consolidated reviewer assignment](protocol/readiness-handoff.md).
The owner excluded HIR/IDR outcomes; assistance/usage coverage remains mandatory.

Install and check the local SDK as described in
[CONTRIBUTOR.md](CONTRIBUTOR.md#repository-local-copilot-sdk). Build a separately
named image from the **harness** build context, then verify actual offline
containment and frozen-reference evaluation without a model session:

```bash
docker build --quiet -f harness/Dockerfile.isolated -t mve-isolated:CANDIDATE harness
image="$(docker image inspect --format '{{.Id}}' mve-isolated:CANDIDATE)"
.venv/bin/python -B harness/isolation_canary.py --image "$image" --out .study/runtime-canary.json
MVE_TEST_ISOLATED_IMAGE="$image" .venv/bin/python -B -m pytest -p no:cacheprovider \
  harness/tests/test_isolated_runtime.py -q
```

Replace `CANDIDATE` with a fresh operator-owned tag; do not overwrite unrelated
images. Record the immutable content ID, not merely the tag. Base and primary
tools are pinned, but transitive registry/apt inputs are not a fully locked
reproducible build: a different rebuilt image requires fresh canaries and
source-bound acceptance. Do not rebuild or switch images during collection.
Regenerate canary evidence after execution inputs change. The receipt is
private offline evidence, not scientific acceptance or a freeze authorization.

The owner must separately supply `protocol/freeze.json`, containing:
`commit` (full frozen source SHA), a new authorised versioned `tag`, `inputs_sha256`
(the controller's complete protocol/harness/skeleton/suite digest),
`registration_url`, `registration_date`, and nonempty
evidence references for each gate: `independent_suite_review`, `access_probe`,
`local_runtime_evidence`, `missing_feature_policy`, `retry_policy`,
`evaluator_information_policy`, `analysis_reconciliation`, `contract_panel_review`,
`oracle_stability`, `cr1_estimands`, `secondary_scope`,
`outage_assistance_policy`, `telemetry_coverage`, `prior_data_disclosure`,
`budget_calibration`, `multi_model_harness_alignment`. A file is a machine-checkable provenance record, not
independent proof that its claims are true. No such file or tag is created here.
The historical `protocol-frozen` tag alone is rejected. Formal H4/H7 definitions
remain deferred. The selected isolated backend additionally requires
`runtime_image` (immutable `sha256:...` image ID) and `runtime_canary_sha256`
(SHA-256 of `.study/runtime-canary.json`) in the owner freeze. The legacy gate
name `local_runtime_evidence` now covers the exact host SDK/container runtime,
not acceptance of the old local-shell mode.
The manifest itself is excluded from the input digest. HEAD must match the
frozen source or differ only by a subsequent manifest-only commit, avoiding
an impossible self-referential commit hash.
Dry-run prints `inputs_sha256`; the digest includes the launcher/bootstrap
scripts and executable bits as well as protocol, harness, skeleton and suites.

Freeze evidence is necessary but is not independent proof of its claims.
The SDK adapter must additionally validate actual model/effort/routing and
complete explicit final usage; requested model names or a terminal summary
alone are not billing evidence. The owner accepts residual soft-limit financial
risk, not missing isolation or unknown accounting.
`harness/billing_check.py` optionally audits a stronger provider budget read-only;
it never modifies billing or enables dispatch. The ledger atomically reserves
before launch; reconciled spending plus every outstanding reservation and
earlier pilot spending must fit the immutable ceiling. Missing/partial usage
holds its reservation and blocks new work; an overrun is retained and stops
admission. This is a **hard launch-admission check**, not hard actual billing.
No timeout or overshoot buffer guarantees the latter. Monitor/reconcile actual
usage, preserve prior spend across billing-cycle resets, and never describe the
reported company hard limit as verified study enforcement.
The old Docker command builder remains historical; the non-smoke controller
uses the restricted SDK bridge and isolated state broker instead.

### State and recovery

All private material lives in ignored `.study/<study-id>/`: `state.json`,
`runtime.json`, per-cell disposable git repositories, canonical `steps.jsonl`,
attempt logs and `results/`. A single-writer lock covers execution and
publication. Atomic state writes are fsynced before dependent actions. Input
hash, source HEAD, schedule, budget and prior spending cannot change on resume.
Do not edit state to extend a budget or deadline; retain it and use an explicitly
authorised new study identity instead. Do not delete partial cells.

Repeat the same command to resume. A durable measured step is never retried,
including a measured failed feature. An unmeasured evaluator interruption can
retry at most `max_attempts` from the previous committed checkpoint, in the
**same** scheduled cell; all attempts/costs remain linked to that step, never new
replicates. Unknown attempt credit costs remain unavailable. If a step record
is torn/ambiguous, or a recorded process group may still be alive, recovery
refuses rather than guessing or replacing the run. Stop that specific recorded
writer safely before resuming; the controller does not kill unrelated processes.

Agent/evaluator subprocess groups have timeouts and TERM/KILL/reap handling.
The absolute study deadline persists across restarts. Work after expiry is
unattempted, not silently excluded. Each cell's metadata is created before any
session, so even zero-step cells enter reporting. Normal smoke runs use separate
disposable repositories and credential-minimal fake-agent environments, **not
OS isolation**. The new live tool containers have no network or writable host
mounts; evaluators receive only selected read-only snapshots/kit/suites.
Opaque worktree state is restored only in containers. Fresh tool calls preserve
files, not running daemons or sockets. Trusted host checkpoints retain regular
committed content and safe trajectory refs, not arbitrary candidate Git metadata.
C alone retains an uncommitted regular REVIEW file. These prospective runtime
differences supersede D11's old local implementation, not scientific or launch
acceptance. A container identity/containment failure globally halts admissions:
inspect only exact recorded IDs/names and verified ownership/image; never prune
or kill unrelated resources. Do not remove pending intents to force a restart.

### Paper outputs and result-only publication

`results/` contains `report.md`, `summary.md`, `summary.json`, `series.csv`,
`hypotheses.csv`, `intervals.csv`, `runs.csv`, `attempts.csv`, `retention.csv`,
`episodes.csv`,
`availability.json`, `provenance.json`, `trajectories.svg`, `hypotheses.tex`,
`trajectories.tex`. Use `\input{hypotheses.tex}` and
`\input{trajectories.tex}`; the figure requires no optional plotting package.
JSON/flat CSV retain all implemented estimates and interval endpoints.
Tables explicitly include failed, partial and unattempted cells and attempts.
They do not replace missing endpoints with last observed outcomes.

Whole-run bootstrap and conservative exact-binomial helpers are reused, not
the historical seven-verdict engine. Reports estimate H1/H2/H6 and resources,
preserve paired F/P losses/episodes, all allocations and missing CR1 bounds.
Unreviewed panels provide diagnostics only. Reference gaps and HIR/IDR remain
unavailable without compatible evidence; formal H4/H7 and mixed-model claims
are deferred. No numerical threshold or hypothesis verdict is invented.
Stub zero credits are real **zero model usage**,
not an estimate for later sessions. Existing `results/smoke` is never pooled in.

Add `--publish` to the same smoke command to publish derived diagnostics:

```bash
./run-study.sh --smoke --study-id vm-check --publish
```

This explicitly authorises a normal push to `results/vm-check` and gh PR
create/update against the current source branch. Authenticated gh, push
permission and git author identity are required. The source branch is never
checked out or changed by publication. An isolated temporary results worktree
stages only the fixed generated allowlist under `results/<study-id>/`.
No `.env`, raw transcript, repository, arbitrary archive or prompt is eligible.
Files must be regular, not linked, <=512 KiB each and <=4 MiB combined; token
patterns and known environment secret values block publishing. Oversized
results cause an explicit stop, never silent truncation of measurements.
Private attempt stdout/stderr are capped at 1 MiB each after execution.
Remote results are fetched, updated without force, and existing PRs edited.
Publication errors leave durable results available to retry.

## Historical manual procedures (not current launch instructions)

The numbered sections below preserve the earlier proposal/operator record.
Their confirmatory wording, H4/H7 thresholds, Docker guidance and phase labels
do not supersede the current protocol or safety gates above. Use immutable
history for earlier snapshots; do not execute historical launch examples to
bypass the disabled paid backend.

## 0. What you need

- **Machine.** A dedicated Linux machine: a VM, a dev container or WSL2. It needs Python 3.11 or later, git, make, Node.js 22 or later (for the CLI) and, ideally, Docker. Do not use the machine for anything else during runs.
- **Copilot access.**
  - GitHub Copilot with the Copilot CLI policy enabled for your account or organisation.
  - A fine-grained personal access token with the **Copilot Requests** permission. Only user-owned tokens offer that permission. Put it in the environment variable `COPILOT_GITHUB_TOKEN`. Classic `ghp_` tokens are not supported.
- **Budget.**
  - Agent time: see section 11.
  - Total prospective pilot plus first-pass ceiling: **2,500 AI credits**. No main-study allocation is authorised. Reconcile actual usage and reserve for active sessions before launching more work; per-session credit caps are soft and do not enforce this aggregate ceiling.
  - AI credits: measure them in the pilot. In the first smoke test (24 Oct 2026) a session cost about 7 to 9 AI credits even for a trivial step, mostly fixed context; later features cost more as the code grows. For comparison, SlopCodeBench reports USD 0.20 to 3.17 per checkpoint at API prices.
- **Calendar.**
  - Building and freezing the suite: about three days.
  - Pilot: one day.
  - First pass: one to two days with four sessions in parallel.

## 1. Freeze the design with HVE Core's Experiment Designer

1. Create a new repository, for example `consolidation-mve`. Keep it private until the protocol is registered, then make it public. Copy this kit into it.
2. Install HVE Core. Record the version or commit you use.
   - **VS Code:** extension `ise-hve-essentials.hve-core`.
   - **Copilot CLI plugin:**

     ```bash
     copilot plugin marketplace add microsoft/hve-core
     copilot plugin install hve-core@hve-core
     ```

     The plugin tracks `main`, so note the commit.
3. For a new session, copy `protocol/` to `.copilot-tracking/mve/2026-10-24/feature-consolidation-harness/` and add `.copilot-tracking/` to `.gitignore`. It is the agent's working copy, not the record. The current working copy already contains the settled decisions: do not overwrite it with the older protocol draft.
4. In Copilot Chat, select **Experiment Designer** in the agent picker and point it at that folder. Ask it to:
   - revisit vetting with the decisions in section 2;
   - update `hypotheses.md`, `experiment-design.md` and `mve-plan.md`.
   The agent is interactive and asks questions, so run it in chat, not with `-p`.
5. After pilot calibration, remaining threshold approval and preflight checks, promote the result and divergence log back to `protocol/`, the tracked record.
6. Compute the plan hash and commit the approved record. Choose a new unused versioned tag; never force, move or replace the existing `protocol-frozen` tag. The following name is an example, not an assertion that it is available:

   ```bash
   sha256sum protocol/mve-plan.md > protocol/mve-plan.sha256
    git add protocol && git commit -m "Freeze protocol" && git tag protocol-frozen-v2
   ```

7. Register the frozen protocol before any confirmatory run. Use OSF Registries, or publish the paper's protocol version on arXiv. Its timestamp is your proof that thresholds came first.

## 2. Settled decisions D1-D12

Approved on 25 October 2026. These choices supersede the earlier recommendations; any further change requires an explicit owner decision and a log entry. Confirmation of D1-D12 does not itself freeze or register the protocol.

| # | Decision | Owner settlement | Why or condition |
| --- | --- | --- | --- |
| D1 | Model, reasoning effort, CLI version | `claude-sonnet-5.5`; `--reasoning-effort medium`; GitHub Copilot CLI **1.0.103**, with automatic updates and custom instructions disabled and no custom agent override | Verify and record the installed CLI version and model metadata. A model ID does not guarantee immutable server-side weights. |
| D2 | Budgets | Feature 30 min; consolidation or review 15 min; CR1 45 min. Pilot soft cap **300 credits per session**. Total prospective pilot plus first-pass ceiling **2,500 credits** | Before freeze, calibrate the session cap to twice the pilot's 90th-percentile session consumption, rounded up to whole credits and at least 30. Reassess affordability; pause for a new decision rather than silently reduce scope. |
| D3 | Replicates | First pass: **4 independent runs per A/B/C arm**, S1. Optional main study: at least 5 per included arm per suite | Four runs is a minimum replication choice, not a power guarantee. With 4 vs 4, the minimum exact two-sided rank-test p-value is about 0.029. |
| D4 | Feature step that delivers nothing | `drop_examples`: remove that feature's examples so later steps start green; hidden tests still count it as missing | `keep_examples` lets one failure block every later commit and every consolidation (TCR always reverts). |
| D5 | End state for H1 | After the final consolidation in B and final review in C; after the final feature in A, all before CR1 | Post-feature steps are part of their respective treatments. |
| D6 | H1 interval and verdict | `validated` if B-A's estimate is at least 10 percentage points and the 95% interval lower bound is above 0; `invalidated` only if its upper bound is below 5 points; otherwise `inconclusive`, or `not evaluable` if evidence is missing | An interval spanning zero alone does not imply invalidation. This matches the existing H1 verdict function. |
| D7 | Suite S2 | Library lending, deferred to a separately authorised main study; no SlopCodeBench adaptation in this MVE | S1 alone is selected for the pilot and first pass. S2 is outside the current funding allocation. |
| D8 | Change-request success | Every CR1 hidden test passes and no feature hidden test passing at the pre-CR1 endpoint is lost | Use **all 10 features** in the first pass: CR1 depends on F9-F10 APIs, so the earlier eight-feature proposal is superseded. |
| D9 | Metric settings | ruff **0.17.2**, rules E,F,W,C90,B,SIM with `--isolated`; jscpd **5.4.1**, minima 50 tokens and 5 lines, launched from an empty directory; complexity from lizard **1.24.3** | Verify these versions and settings before freeze. Isolated settings prevent repository configuration from changing the metrics. |
| D10 | Cost unit | AI credits = `totalNanoAiu` / 10^9 from each session's `usage.json`, primary; tokens and wall-clock time secondary | Report incomplete credit accounting; never silently mix units in one cost comparison. Premium-request counts are not the primary cost measure. |
| D11 | Isolation | **Local execution on the existing VM**, not container mode; keep hidden/reference assets outside run repositories, deny web/package-fetch tools, probe access and audit transcripts | Owner accepted the weaker boundary. Local deny rules are not an OS sandbox; a passing probe does not prove containment. Disclose residual access risk; a failed probe blocks execution pending mitigation or a revised decision. |
| D12 | Placebo arm C | **Include C in both pilot and first pass**, with the same post-feature budget as B; only `REVIEW.md` may change during review | Supports H7 attribution. Quantitative H7 criteria and analysis conformance still require approval before freeze. |

What the kit adds to the protocol (accept or change these before freezing):

- **Runner enforcement.**
  - A head with failing tests is reset.
  - Edited example tests are restored and logged.
  - Review-only steps may change only `REVIEW.md`.
  - Uncommitted work is discarded.
- **Fixed denominators.** A hidden test module that fails to import counts all of its tests as failed.
- Measurement configuration: `ruff --isolated` and jscpd v5 run from an empty
  folder. This reduces configuration influence, not all influence from generated
  code. Backend failure is not a zero-warning result; generated root `reports/`
  content is excluded from authored Markdown counts, but `DESIGN.md` and
  `REVIEW.md` remain included.
- Small fixes: `tcr` returns the failed test/stage/commit status after attempting
  rollback and uses a unique temporary log. Its `reports/` clean exclusion does
  not protect tracked report files from reset. Each feature's API is listed
  under its rules. A change-request prompt is added.
- Analysis: the implemented analyzer resamples per-run OLS slopes. It does not
  fit the proposed mixed model. If that model is adopted separately, treat
  suite as a fixed effect and run as a random effect, and settle that analysis
  choice before a new freeze.

## 3. Review and freeze suite S1

Suite S1 is complete: ten features and the change request CR1, each with a specification and explicit API in `suite.json`, 3-4 visible tests (`features/fNN/examples/`, `cr1/examples/`), 12-15 hidden tests (`features/fNN/hidden/`, `cr1/hidden/`) and a cumulative reference solution (`reference/source.py`; rebuild the snapshots with `python3 suites/s1-retrofit/reference/build_reference.py`).

What you still have to do:

1. **Review the hidden tests against the rules.** The protocol needs someone other than their author to check them. For each hidden test, ask: is the behaviour stated in that feature's rules or an earlier feature's rules, using only the stated API? Fix or delete any test that is not. Watch especially for error-precedence cases (which error wins when two rules apply): the rules state them where tests rely on them.
2. **Check the difficulty.** The features should be small enough for one 30-minute step but interact enough to create pressure on earlier code. The pilot (step 5) is the real check.
3. **Change nothing after the freeze.**

Require every cumulative reference stage and CR1 to pass. Validation rejects
draft items, missing reference packages, empty per-item visible/hidden tests
and failed collection processes. Prior-reference diagnostics are advisory:
some edge cases can legitimately pass before a feature exists, so review
their intent rather than equating every earlier pass with an invalid test.

```bash
python3 harness/validate_suite.py suites/s1-retrofit
```

Freeze the suite:

```bash
find suites -type f -print0 | sort -z | xargs -0 sha256sum > protocol/suite.sha256
git add -A && git commit -m "Freeze suite S1" && git tag suite-frozen
```

## 4. Prepare the environment and run a smoke test

**Option A, container per step (alternative, not selected under D11).** Switching to this option requires an updated isolation decision and log entry.

```bash
docker build -t mve-agent:frozen harness/
docker image inspect --format '{{.Id}}' mve-agent:frozen   # record this digest; never rebuild during the study
python3 -m pip install -r harness/requirements-measure.txt  # host tools for the runner's checks and measurements
npm install -g jscpd                                        # same version as in the image
cp harness/config.docker.json harness/config.json
```

**Option B, local VM execution (selected under D11).** For a fresh setup, install the pinned CLI and duplication tool and use the local configuration. Skip the copy if `harness/config.json` is already configured; it would replace the current values.

Evaluator, metric and green-check subprocesses receive an allowlisted environment
with temporary home/cache directories instead of inherited model credentials.
Agent authentication is unchanged. This is credential-exposure reduction,
not OS isolation: local processes can still access files and network subject
to host permissions. Metadata says `evaluation.environment` is
`allowlisted_subprocesses`; a direct CLI caller's own process is not scrubbed.
D11's probe and residual-risk gates still apply.

```bash
npm install -g @github/copilot@1.0.103 jscpd@5.4.1
python3 -m pip install -r harness/requirements-measure.txt
cp harness/config.local.json harness/config.json
```

**In both cases:**

- Set `agent_values.model` to `claude-sonnet-5.5`, `effort` to `medium` and pilot `max_credits` to `300` in `config.json`.
- Verify CLI 1.0.103, ruff 0.17.2, jscpd 5.4.1 and lizard 1.24.3 before runs; do not assume installation selected the frozen versions.
- Export your token: `export COPILOT_GITHUB_TOKEN=...`.

Each step runs the agent with these flags, all present in CLI 1.0.95:

```text
copilot -C <repo> -p <prompt> --model <id> --reasoning-effort <level>
  --allow-all-tools --deny-tool "shell(git push)" --deny-tool url --deny-tool "shell(curl)"
  --deny-tool "shell(wget)" --deny-tool "shell(pip)" --deny-tool "shell(pip3)" --no-ask-user --no-custom-instructions
  --disable-builtin-mcps --no-auto-update --output-format json --log-dir <step>/logs
  --share <step>/transcript.md --usage-output-file <step>/usage.json --max-ai-credits <n>
```

The environment adds:

- `COPILOT_HOME`: fresh for every step, so no memory or session carries over.
- `COPILOT_OTEL_FILE_EXPORTER_PATH`: writes token counts per step.

Memory is off by default in prompt mode.

**Smoke test.**

1. Dry run without an agent:

   ```bash
   cd harness
   python3 runner.py --config config.dry-run.json --suite ../suites/s1-retrofit --arm B --run-id dry-B-01 --features 2 --phase dry --no-cr
   ```

2. One real feature and one consolidation step:

   ```bash
   python3 runner.py --config config.json --suite ../suites/s1-retrofit --arm B --run-id smoke-01 --features 1 --phase pilot --no-cr
   ```

3. Check, in `runs/smoke-01/steps/*/`:
   - `transcript.md`, `usage.json`, `otel.jsonl` and `logs/` exist;
   - the feature step committed after `make test`;
   - the consolidation step used `./tcr`;
   - no `possible_leak` appears in `steps.jsonl`.
4. Probe the isolation with one extra session that uses the same flags as the runner, from the kit folder:

   ```bash
   MODEL=$(python3 -c "import json; print(json.load(open('harness/config.json'))['agent_values']['model'])")
   SECRET="$PWD/suites/s1-retrofit/features/f01/hidden/test_f01_hidden.py"
   COPILOT_HOME=$(mktemp -d) COPILOT_AUTO_UPDATE=false \
   copilot -C runs/smoke-01/repo --model "$MODEL" \
     --allow-all-tools --deny-tool "shell(git push)" --deny-tool url --deny-tool "shell(curl)" \
     --deny-tool "shell(wget)" --deny-tool "shell(pip)" --deny-tool "shell(pip3)" --no-ask-user \
     --no-custom-instructions --disable-builtin-mcps --no-auto-update \
     --share "$PWD/probe-transcript.md" \
     -p "This is a permissions test. Do not change any files. Try each of these and report exactly what happened, including any error: 1) fetch https://example.com and tell me its page title; 2) print the first 5 lines of $SECRET; 3) run: curl -sI https://example.com | head -1"
   ```

  All three must fail. Without the `url`, `curl`, `wget` and `pip` deny rules, the first smoke test (24 Oct 2026) showed that reading outside the repository was already denied, but web access succeeded through both the web-fetch tool and curl. Under the selected local mode, even a passing probe does not establish OS-level containment. Disclose that residual risk and audit transcripts. If any probe succeeds, stop: verify a mitigation or obtain a revised isolation decision before execution. Container mode or the CLI command sandbox are alternatives, not silently selected fallbacks.
5. Check the cost data: `python3 harness/analyze.py --runs runs --phase pilot --out results/smoke | head -4` must report AI credits greater than zero and every session with complete credit accounting. Then move the smoke run out of `runs/` (`mkdir -p runs-smoke && mv runs/smoke-01 runs-smoke/`) so it is not analysed with the pilot.

## 5. Pilot (data excluded from the analysis)

S1, one run each of A, B and C, ten features, **no CR1**: 50 sessions. Commands below run from `harness/`. The scheduler does not add `--no-cr` for pilot runs, so append it explicitly to every generated command; execute `pilot.txt`, not the scheduler's unmodified `schedule-pilot.txt` copy.

```bash
python3 schedule.py --pass pilot --arms A B C --runs 1 --features 10 --seed 101 --config config.json | sed 's/$/ --no-cr/' > pilot.txt
bash pilot.txt
python3 analyze.py --runs ../runs --phase pilot --out ../results/pilot
```

Use the pilot only to calibrate, and log every change in the divergence log:

- **Budgets:** if most feature steps hit the time limit, the features are too big for the budget. Adjust either one before the first pass.
- **Credit cap:** start at 300 credits per session; before freeze set `max_credits` to twice the pilot's 90th-percentile session consumption, rounded up to whole credits and at least 30.
- **Aggregate budget:** reconcile pilot spending and reserve for active sessions. Authorise the complete 212-session first pass only if the pilot-based estimate fits the remainder of the 2,500-credit allocation; otherwise pause for a new budget or scope decision. Session caps do not enforce the total ceiling.
- **No decay in arm A:** follow the iteration plan in `experiment-design.md`. Lengthen the sequence or strengthen the interplay between features.

Complete the remaining threshold approvals and analysis checks, independent test review and environment/access checks. Promote the working artifacts, freeze and register the final protocol before section 6. Do not add or omit runs based on observed treatment effects.

## 6. First pass (S1, A/B/C, 4 runs each, 10 features plus CR1)

This is the settled first-pass scope: 212 sessions. Ten features supply CR1's F9-F10 prerequisites. Run only after the budget and confirmatory-execution gates above are satisfied.

```bash
python3 schedule.py --pass first --arms A B C --runs 4 --features 10 --seed 2027 --config config.json > first.txt
cat first.txt | xargs -P 4 -I{} sh -c "{}"
```

`xargs -P 4` runs four sessions at a time. Order is randomised in blocks, so every arm appears once per block and drift affects all arms alike.

- Watch progress with `tail -f ../runs/*/steps.jsonl`.
- Change nothing during a pass.
- If a run fails for infrastructure reasons, start a new run ID and log it. Never drop or replace a run silently.
- Arm C is included, not optional for this pass. During its review-only steps, only `REVIEW.md` may change.
- Reconcile credit usage and reserve for active runs before launching more work. If the remaining allocation is insufficient, pause and log it; do not silently reduce replication or discard runs.

## 7. Analyse and decide

```bash
python3 analyze.py --runs ../runs --phase first --out ../results/first
```

**Outputs:**

- `summary.md`: one row per hypothesis with its estimate, interval and verdict, then one row per run.
- `summary.json`
- `series.csv`: one row per run and feature.
- `trajectories.png`

**How the outputs are computed:**

- Bootstrap intervals: 10,000 whole-run resamples within arm and suite, with
  equal-suite weighting and shared draws for compound contrasts. Reported
  95% percentile intervals are marginal, not simultaneous across hypotheses.
  Missing contributing metrics or any undefined resampled estimate makes the
  affected interval unavailable; undefined draws are not silently dropped.
- H2 uses end-state open-regression reduction and A's trajectory, not AUC as
  a substitute. H3 uses per-run OLS quality slopes; its component rule requires
  a positive A-slope interval, the point-estimate half-slope threshold and a
  beneficial A-minus-B interval. The half-slope-margin interval is also reported.
- H5 separates late feature-implementation cost from consolidation/review cost.
  Late means the last `floor(N/3)` feature sessions, with at least one session.
- H6 success bounds use Clopper-Pearson binomial intervals with Bonferroni
  allocation across both arms and all suites, followed by subtraction of
  opposite endpoints. These are conservative at-least-95% simultaneous bounds,
  not a narrow exact interval for the difference; four runs can be inconclusive.
  The alternative successful-attempt cost comparison retains failed attempts
  in run resampling and reports their counts and costs separately. Its
  no-lower-success condition is observed, not established non-inferiority.
- H4 volume and H7 correctness components are descriptive. Full H4 needs blinded
  comprehension evidence; full H7 needs the H3 package comparison as well.
  Neither full verdict is implemented, so both remain not evaluable.
- Requested AI-credit costs need complete accounting for every contributing
  session. Missing costs are unknown, not zero. There is no automatic fallback
  to tokens or seconds; an explicit secondary-unit analysis must be labelled.
- Metadata-bearing runs remain in reporting even without a first step record.
  Interrupted or malformed trajectories do not substitute their last observed
  feature for the scheduled endpoint. Check `sequence_complete`,
  `outcomes_complete`, missing-step fields and recorded errors. Partial observed
  outcomes/costs remain descriptive; unavailable scheduled values are not
  replaced by complete survivors.
- Permutation p-values are exact when feasible and otherwise Monte Carlo.
  Read the intervals first.

These implementation details require reconciliation with the proposed analysis
before a new freeze; unchanged numeric thresholds do not establish method
approval or registration conformance.

**Before you accept a verdict:**

- read the violations and possible-leak columns;
- read two or three transcripts per arm.

**Proposed separate mixed model.** Not fitted by `analyze.py`; it needs pandas
and statsmodels and pre-freeze method reconciliation:

```python
import pandas as pd, statsmodels.formula.api as smf
d = pd.read_csv("../results/first/series.csv")
print(smf.mixedlm("mean_ccn ~ C(arm) * k + C(suite)", d, groups=d["run_id"]).fit().summary())
```

**Close the loop:**

- Go back to the Experiment Designer and write `outcome.md`. Record each hypothesis as validated, invalidated, mixed, inconclusive or not evaluable, and the decision as go, no-go or adjust.
- In the paper, set `\resultstrue` and replace the placeholder with the figure and the hypothesis table. Report every run, including failed ones.

## 8. Main study (deferred, not authorised)

- **Funding:** outside the current 2,500-credit pilot plus first-pass allocation; requires a separate owner decision.
- **Scope:** S1 and library-lending S2, at least 5 runs per included arm per suite, 10 features plus change requests. Decide arm inclusion separately; C is already selected for the current pilot and first pass.
- **Order:** generate it with `schedule.py --pass main --suites s1-retrofit s2-library ...`.
- **Second suite:** write S2 the same way as S1 (section 3).

## 9. Comprehension task (H4, manual)

1. Export each final code base without arm labels: delete `DESIGN.md` and `REVIEW.md`, and give each a random code.
2. Two or three reviewers answer the same five questions per code base. Example: "Where is the rule that blocks installation without consent?"
3. Record accuracy and minutes per code base in a CSV, then compare arms with rank tests and A12.

The current analyzer does not ingest these reviewer data or calculate a full
H4 verdict. Preserve the blinded-review record and complete the approved
analysis separately before reporting H4 as evaluated. HIR extraction and
author verification also remain separate, unimplemented work in this kit.

## 10. Archive and publish

- **Archive:** `runs/` (repositories, prompts, transcripts, usage, logs, measures), `results/`, the image digest, `protocol/` and the divergence log.
- **Clean:** strip tokens and personal data before publishing. The CLI redacts `COPILOT_GITHUB_TOKEN` and `GITHUB_TOKEN` from output by default. Check anyway.
- **Publish:** with the paper, for example on Zenodo or OSF.

## 11. Time and agent sessions (upper bounds at the settled budgets)

| Pass | Agent sessions | Maximum agent hours | With 4 in parallel |
| --- | --- | --- | --- |
| Pilot: S1, A/B/C once, 10 features, no CR1 | 50 | 20.0 | 7.5 (only three runs, so at most three in parallel) |
| First pass: S1, A/B/C x4, 10 features, CR1 | 212 | 89.0 | 22.25 (ideal utilisation) |
| Pilot plus first pass | 262 | 109.0 | Passes run separately; include calibration and preflight time |
| Main study | Not authorised | Recalculate after scope approval | Separately funded |

These are agent-time upper bounds, excluding checks and scheduling overhead; parallel time depends on run-level scheduling. The pilot command in section 5 is sequential, so its agent-time upper bound is 20 hours as written. Steps usually finish early.

The excluded smoke run used 14.54324 credits across two sessions, averaging 7.27162. Extrapolating that mean to 262 sessions gives about **1,905 credits**, leaving about **595** within the **2,500-credit ceiling**. This is not a reliable forecast for later, harder features and excludes extra preflight or retry sessions. Re-estimate after the pilot, reconcile actual spending throughout, and pause for a new owner decision if the remaining allocation cannot cover the full planned pass. No main-study allocation is included.

## 12. Troubleshooting

| Symptom | Fix |
| --- | --- |
| `make: not found` | Install make, for example `apt-get install make`. |
| `./tcr: Permission denied` | The runner sets the executable bit, because zip files and synced folders drop it. In other copies, run `chmod +x tcr`. |
| The agent ends at once or asks for approval | Keep `--allow-all-tools` for prompt mode. Check that the CLI policy is enabled and the token has Copilot Requests. |
| `usage.json` missing or without credits | Report incomplete accounting. Recover the records or mark that cost comparison not evaluable. The analyzer does not automatically substitute tokens or seconds for the requested AI-credit comparison. |
| Many `examples modified` violations | The agent is weakening tests. The runner already restores them; report the counts per arm. |
| Hidden pass rate near zero in both arms | The features are too large or the API is unclear. Revise and re-freeze before the first pass, never after. |
| `possible_leak` true | Preserve and flag the run and transcript, stop affected execution and investigate. Do not silently delete or replace a run; apply the approved exposure policy or obtain an owner decision before restarting. |
