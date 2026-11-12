---
description: "Runbook for the feature-consolidation MVE with D1-D12 settled on 2026-10-25."
---
# Runbook: running the feature-consolidation MVE

The owner-selected short calibration, parallel scheduler and restart policy
are an **unregistered changed design**, not an amendment to the historical OSF
registration. Follow the current changed-design disclosure and launch gates in
[CONTRIBUTOR.md](CONTRIBUTOR.md) and
[the protocol](protocol/pilot-estimation.md); the historical preregistration
instructions below do not register these changes.

The active scientific authority is [protocol/pilot-estimation.md](protocol/pilot-estimation.md).
Prepare [the OSF draft](protocol/osf-preregistration.md), resolve the decision
ledger and approve the exact submission candidate. On 30 October the owner
accepted scientific and corrected runtime/access evidence under disclosed
owner review, with no independent reviewers for this first study beyond the
separate executor. That executor provides operational separation, not independent
validation. Use [the OSF checklist](protocol/osf-submission-checklist.md) and
[runtime decision record](protocol/runtime-acceptance-2026-10-30.json).
The later [security refresh](protocol/security-remediation-2026-10-30.json)
changes the runtime and remains blocked on residual OS findings. Do not reuse
historical acceptance or the v2 freeze for that new environment. The active
ledger deliberately requires new runtime/final-source acceptance before OSF.
See the [later component-hardening evidence](protocol/security-hardening-2026-10-30.json)
for the exact updated image, backport qualification and still-unresolved findings.
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
accepted soft-limit policy, optional budget audit and retained final freeze requirements.
The owner-amended first pass is an estimation pilot, not confirmatory testing:
GPT 6.1 Sol, Sonnet 5.5 and Gemini 4 Argon, each with 12/21/33 trajectories per
A/B/C/D/E arm, default 12 (180 study, plus 15 excluded calibration).
The default has 3060 study and 240 calibration sessions, at most 1500 combined
agent-hours. D extends uninterrupted feature delivery to 45 minutes/600 nominal
credits (540 soft); E adds 15-minute visible-specification repair. The current total
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

`./run-study.sh --dry-run --phase pilot-estimation` (legacy `first`) prints a 180-cell
default schedule (12 runs per A/B/C/D/E per model, ten features and CR1, 3060 sessions) and all
preflight blockers. `--phase calibration` (legacy `pilot`) proposes one run/arm/model,
ten features and no CR1: 15 trajectories/240 sessions, excluded from the study.
Use `--replicates 21` or `--replicates 33` for the other prespecified allocations;
record the choice before collection and never change it on resume.
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
smoke usage is **14.54324**; three later successful excluded backend checks add
**3.05509**, making known prior usage **17.59833**. Three earlier excluded
runtime checks still have unknown usage. The
owner separately approved each full **300-credit** reservation as a historical
budget provision on 29 October. `prior_credits` records only known usage;
`historical_credit_provisions` binds each hold to its exact approved
attempt/source/ledger digest. Admission counts known usage plus **900 held**,
leaving **269082.40167**
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
uv pip install --python .venv/bin/python -r harness/requirements-measure.txt
uv pip uninstall --python .venv/bin/python pip
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

The signer-key repair changes v6 execution inputs. Treat this source and any
rebuilt image as a new candidate: preserve the v6 tag, manifest and receipt,
and obtain fresh exact-source qualification, owner acceptance and prospective
freeze/registration evidence before collection. Do not copy a candidate receipt
over the v6 receipt merely to clear preflight.
Run the following checks in a separate candidate checkout with no existing
`.study/runtime-canary.json`; the actual-image tests read that exact path.

```bash
docker build --quiet -f harness/Dockerfile.isolated -t mve-isolated:CANDIDATE harness
image="$(docker image inspect --format '{{.Id}}' mve-isolated:CANDIDATE)"
.venv/bin/python -B harness/isolation_canary.py --image "$image" --out .study/runtime-canary.json
MVE_TEST_ISOLATED_IMAGE="$image" .venv/bin/python -B -m pytest -p no:cacheprovider \
  harness/tests/test_isolated_runtime.py -q
```

The image build uses distinct Git and BusyBox signer identities, keeps their
public keys in separate staging directories and refuses missing keys or
conflicting key names. APK signature
verification remains enabled. Do not bypass it or publish intermediate builder
images, which contain private build signing keys. Passing the image build and
offline checks does not itself constitute runtime or scientific acceptance.

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

#### Specific 651-step estimation interruption

The separately authorized recovery below is the sole exception to the
same-source resume rule. It applies only to the disclosed stopped state
`6eb8f45bcb54f8cad20cbd89aba72da7721ebf06ab6188fbf3c0cc460306723f`
and source `99a1ed170d7c71acb428b52e0e24be8856cc3ea3`. It verifies
the exact failed `edit` journal and complete original calibration accounting.
It preserves the original study and creates a separate copy on the new source;
it never edits the original, changes the original deadline, or treats the
unknown charge as zero. The 300-credit reservation stays held, and the failed
step can receive a new independently reserved allowance. Actual billing can
exceed either reservation. Its full original step time allowance also starts
afresh. This is a mid-study, unregistered change after
observing data, not a continuation under a single frozen source.

Before preparing a copy, the owner must review the source change, make the new
commit publicly available, run its source-bound offline canary and create the
normal new unregistered manifest. The owner must also supply a separate private
JSON approval, using the actual new commit, disclosure URL and approval time:

```json
{
  "schema": "estimation-incident-approval/v1",
  "original_state_sha256": "6eb8f45bcb54f8cad20cbd89aba72da7721ebf06ab6188fbf3c0cc460306723f",
  "original_commit": "99a1ed170d7c71acb428b52e0e24be8856cc3ea3",
  "target_commit": "<new public 40-character commit>",
  "attempt_id": "pilot-estimation-claude-sonnet-5.5-E-03-f03-repair-1",
  "unknown_reservation_nano": 300000000000,
  "accept_unknown_hold": true,
  "accept_fresh_retry_reservation": true,
  "accept_fresh_retry_time_allowance": true,
  "accept_mid_study_source_change": true,
  "owner_approved": true,
  "approved_at": "<actual timezone-aware approval timestamp>",
  "disclosure_url": "https://github.com/jmservera/ama-thought-mve/commit/<new commit>"
}
```

In the clean new checkout, prepare the copy without starting any models:

```bash
.venv/bin/python harness/prepare_estimation_recovery.py \
  --source-root /path/to/original-checkout \
  --old-manifest /path/to/original-owner-evidence.json \
  --new-manifest /path/to/new-owner-evidence.json \
  --approval /path/to/private-recovery-approval.json
```

The original checkout and its study must remain available and unchanged.
After separate launch review, use the normal estimation command with the new
manifest and the original calibration ID, adding both
`--recovery-source-root /path/to/original-checkout` and
`--recovery-calibration-manifest /path/to/original-owner-evidence.json`.
The controller locks both checkouts during paid work, verifies the saved
pre-recovery state and approval, and keeps each attempt's source commit in the
results. The original source, new source, state hash, retained hold and
chronology must be disclosed in the paper. Do not interpret mixed-source
trajectories as if they were all run under one frozen implementation.

#### Transient provider failures and accounting

The pinned transport accepts at most three correlated WebSocket provider
failures per session with status 500, 502, 503 or 504, `internal_error`,
`websocket_error`, unchanged model/medium effort and no automatic or BYOK
routing. Both pinned event representations must agree with the active model
turn. This lets the CLI's existing retry activity finish; the transport does
not resend the prompt or create a new session. The original session deadline,
soft credit limit, isolated-only tool catalog and all discovery/permission
guards remain enforced.

Continuation is not guaranteed. Successful retry work still requires the
normal final correlated aggregate and an explicit complete charge for every
failed API/service request. An omitted failed-request charge is unknown, not
zero; an earlier turn's receipt cannot be reused even if request identifiers
repeat. Exhausted retries, missing accounting, authentication/client errors or
changed treatment still stop collection and retain reservations. Never clear a
halt or mark a failed request free to force a restart.

#### Specific 878-step backend interruption

The second supported exception is the stopped state
`b8f9abfb13f45b1261b7bbf82f82f17f934523f662073bc443103b9d84787d9a`
at source `3c2ce89b00fe583c1f0715e8ccd3510419d5e734`. GPT arm E,
replicate 04, F8 received a WebSocket HTTP 500. Its exact attempt
`pilot-estimation-gpt-6.1-sol-E-04-f08-feature-1` has unknown usage and a
300-credit reservation. The first incident's 300-credit hold remains too.
Neither hold is a measured charge or a provider billing guarantee.

The earlier approval does not approve this second incident. After reviewing,
publishing and qualifying the new source, supply a new private approval using
the same JSON schema above, replacing `original_state_sha256`,
`original_commit` and `attempt_id` with this incident's values. Use the actual
new target commit, its disclosure URL and an approval time after disclosure and
the interrupted attempt. All five approval booleans must be explicitly true:
the new unknown hold, a separately reserved fresh retry, a full fresh F8
step-time allowance and the additional unregistered source change are
material decisions. The original allocation, configuration and absolute
deadline do not change.

In a clean, separately qualified new checkout, prepare without inference:

```bash
.venv/bin/python harness/prepare_estimation_recovery.py \
  --source-root /path/to/stopped-878-checkout \
  --old-manifest /path/to/stopped-878-owner-evidence.json \
  --prior-source-root /path/to/original-651-checkout \
  --calibration-manifest /path/to/original-651-owner-evidence.json \
  --new-manifest /path/to/new-owner-evidence.json \
  --approval /path/to/new-private-recovery-approval.json
```

The new copy preserves all 878 completed steps, all 880 retained attempts and
both unknown holds. It archives the first snapshot, approval and intermediate
manifest and verifies both transitions. Results preserve every attempt's
actual source commit and expose the earlier transition in
`source_transition_history`, alongside the latest `source_transition`.
Both stopped source checkouts remain intact and available.

After preparation, use the normal estimation command with both original
checkouts in chronological order. Run its read-only preflight first:

```bash
./run-experiment.sh --phase pilot-estimation --replicates 21 --parallel 8 \
  --config /path/to/unchanged-budget-config.json \
  --unregistered-manifest /path/to/new-owner-evidence.json \
  --calibration-study-id excluded-short-calibration-toolfix \
  --recovery-source-root /path/to/original-651-checkout \
  --recovery-source-root /path/to/stopped-878-checkout \
  --recovery-calibration-manifest /path/to/original-651-owner-evidence.json \
  --dry-run
```

Removing `--dry-run` is a separate paid-launch decision. The controller locks
the new checkout and both original paid-study roots and revalidates their
exact stopped states. This is not a general unknown-usage waiver: undisclosed
interruptions remain blocked. Preserve both approvals and disclose the entire
source/accounting chronology in the paper.

#### Candidate filesystem rejections

A candidate command that produces a link, hard link or special file is
rejected; those artifacts are never accepted into the retained workspace.
For this specific `execute`-operation rejection, the fixed supervisor now
returns a bounded explicit failed tool result with unchanged prior state.
The broker verifies the frame metadata and supervisor/child identity proofs
before returning it to the same SDK session. The model can continue with
another normal tool call within the original time/credit allowance. No prompt
replay or new paid session is added.

Ownership, cleanup, malformed framing, unknown state tokens, integrity failures,
output floods, deadlines and other unclassified helper errors remain fatal.
Do not catch every isolation failure and turn it into a recoverable result.
Changing the fixed helper requires a new immutable image and source-bound
canary; do not reuse the earlier image/receipt binding.

#### Specific 1482-step sandbox interruption

The third supported incident is the exact stopped state
`18fcc0ece87305cca5205fd8bd24bc7cffaadde38e32e9c77f4bc922b4d7b4ab`
at source `e71037d961cb80fc5c659437796de7736820f6c9`.
`pilot-estimation-gpt-6.1-sol-B-06-f02-consolidation-1` requested a
symlink-creating isolated command. The old helper rejected the state and the
SDK session ended without a terminal usage receipt. Its journal SHA-256 is
`de131c24e0d2800d75c5c94e68a12f769a7eff5b5748c99310778d3897e3e635`.
The prior opaque broker state and its metadata/owner identity remain intact,
and no owned container remained after cleanup.

This incident retains a third 300-credit unknown reservation, alongside the
two earlier study holds. The total 900-credit study provision is not measured
spending or a guaranteed billing bound. A separately approved retry of this
post-step reserves another 300 credits and receives a fresh full
**900-second consolidation allowance**, not the 1800-second F8 feature allowance
from the preceding incident. The original budget, allocation and absolute
deadline remain unchanged.

Review and disclose the new exact source and image before collection. Supply a
new genuine approval with the same schema as the first incident, replacing
the original state/source/attempt fields above and using the actual public
target, disclosure URL and approval time. Prior approvals and synthetic
qualification fixtures do not authorize this incident.

Prepare the separate copy in the clean new qualified checkout:

```bash
.venv/bin/python harness/prepare_estimation_recovery.py \
  --source-root /path/to/stopped-1482-checkout \
  --old-manifest /path/to/stopped-1482-owner-evidence.json \
  --prior-source-root /path/to/original-651-checkout \
  --prior-source-root /path/to/stopped-878-checkout \
  --calibration-manifest /path/to/original-651-owner-evidence.json \
  --new-manifest /path/to/new-owner-evidence.json \
  --approval /path/to/new-private-recovery-approval.json
```

The copy retains all 1482 durable steps and 1485 prior attempts, archives all
earlier snapshots/approvals/manifests, and binds immutable broker evidence
under the interrupted attempt's `recovery-broker/`. The live broker may later
advance; it must not replace that archival evidence.

Use the normal estimation command with the original calibration manifest and
three `--recovery-source-root` options, ordered original 651, stopped 878,
stopped 1482. Run `--dry-run` first. Paid work locks all four checkout roots,
and every original state must remain available and byte-identical. The source
of every older attempt is preserved, not relabelled as the new implementation.

#### Specific 2082-step service interruption

The fourth supported incident is stopped state
`ec36955567ffc2424ce4a9a748f43a3e584c3c3d6756488028f4b0b5bd008a7c`
at source `fb1a90a0347609b1b1c33f4cd1147433a25cab96`.
`pilot-estimation-gpt-6.1-sol-A-09-f02-feature-1` received a WebSocket HTTP
503 with `service_unavailable` / `websocket_error`. Its journal SHA-256 is
`e4b44c1f0145fe5d54422187dc4c21229a2db405e93aca0aacbc7fbc4c2834db`.
The terminal receipt is an incomplete `unexpected_runtime_activity` failure,
not a certified zero charge.

The transport amendment adds only this exact 503 code/transport combination.
It also accepts a next attempt in the same logical turn only after that
turn's correlated modern failure and legacy mirror. Arbitrary duplicate or
overlapping starts, changed turns without a terminal error, model/effort or
routing changes, authentication/client/rate-limit errors and mismatched IDs
remain fatal. The maximum three provider failures, original prompt, shared
time/credit limits, complete failed-request charges and terminal aggregate
stay mandatory. Each attempt captures its own accounting watermark.

The harness does not schedule new retries/backoff or send a new prompt;
it permits only verified pinned CLI retry activity. Internal CLI backoff is
not promised. Missing failed-request charges still halt collection.

This copy retains all 2082 steps, 2086 prior attempts and four 300-credit
study holds (1200 nominal credits, not measured spending or a billing bound).
A separately approved fresh F2 feature retry reserves another 300 credits and
receives the full **1800-second feature allowance**. The allocation, budget,
calibration and original absolute deadline remain unchanged.

Use a genuine new post-disclosure approval for this exact state/source/attempt
and the new qualified target. Preserve the earlier approvals, rather than
extending or replacing them. In the clean qualified target checkout:

```bash
.venv/bin/python harness/prepare_estimation_recovery.py \
  --source-root /path/to/stopped-2082-checkout \
  --old-manifest /path/to/stopped-2082-owner-evidence.json \
  --prior-source-root /path/to/original-651-checkout \
  --prior-source-root /path/to/stopped-878-checkout \
  --prior-source-root /path/to/stopped-1482-checkout \
  --calibration-manifest /path/to/original-651-owner-evidence.json \
  --new-manifest /path/to/new-owner-evidence.json \
  --approval /path/to/new-private-recovery-approval.json
```

For launch, supply four `--recovery-source-root` values: original 651,
stopped 878, stopped 1482, then stopped 2082, in that order. All five paid-study
roots are locked. Verify `--dry-run` first and leave paid launch separate.
Existing historical attribution manifests/audits stay byte-identical and bound
to their original qualified source/image/helper. Reporting locates only their
exact validated archival snapshot/approval/manifest, never a silent fallback
to an unrelated or tampered object. No historical outcome is rerun to improve it.

#### Specific 2289-step WebSocket-reset interruption

The stopped state
`1c79a8eba989779464cd2757e65887fae727538fb74691e50228c27bde0db60f`
is source `355d33389441b325da72363a9c3028dbdefa2b4b`, with 2289 completed
measurements, 2294 attempts and 130 completed trajectories out of 315.
The interrupted attempt is
`pilot-estimation-gpt-6.1-sol-D-10-f07-feature-1`.
Its retained journal SHA-256 is
`9057d6c157011ade7dbf9412d791d28c2667acc3a5f7f2182b130c43ebf8d8c4`.

This was a top-level WebSocket transport reset, not a feature-test failure or
an HTTP 500/503 response. The modern failure has `failureKind=transport`,
`transport=websocket`, `rte=true`, `source=top_level`, endpoint `ws:/responses`,
the exact closing-handshake ECONNRESET message, pinned model/effort and
explicitly non-auto/non-BYOK routing. It has no HTTP status, error code or error
type. The legacy mirror must agree on request IDs, endpoint,
transport kind and exact error, without inventing an HTTP status.
An error-message substring alone is not sufficient evidence.

Correction: `rte` is the Copilot API's `X-GitHub-Copilot-Request-TE`
treatment/eligibility header signal, **not retryability**. The pinned SDK
defines it in its generated `session-events` event types. The earlier
description of this field as retryability was incorrect. Its historical value
is retained for the exact archived incident; generic reset handling no longer
uses the treatment signal to decide whether an otherwise correlated reset is
accepted. Complete failed-request charges and the existing retry ceiling are
still required.

The transport recognizes only this structured signature in addition to the
existing reviewed API failures. It permits the pinned CLI's already bounded
retry activity, not a new harness prompt or unlimited connection retries.
The shared three-failure ceiling, original session limits, complete correlated
failed-request charges, model/effort/routing and tool isolation remain mandatory.
This cannot repair an upstream connection or guarantee a successful retry.

The real stopped session has no successful retry or complete terminal charge.
Accepting its event signature does not make its usage complete or its charge
zero. The five study reservations remain held: four previous 300-credit holds
and this **600-credit D feature hold**, totalling 1800 nominal credits.
Known study consumption is 26552.15674 credits; calibration, prior spend and
historical reservations remain separate and unchanged.

An approved separate copy can give the same D/F7 step a fresh **2700-second**
feature allowance and separately reserve **600 credits**, with its unchanged
540-credit operational soft limit. The old 600-credit hold is not released.
Nominal reservations and soft limits do not bound actual billing.
All allocation, configuration, absolute deadline and original evidence remain
unchanged. This is another explicitly disclosed, unregistered mid-study source
transition after observations, not continuation under one original freeze.

After publishing and qualifying the exact corrected source, obtain a new
genuine owner approval for this state/source/attempt. Use the existing
`estimation-incident-approval/v1` fields, but set
`unknown_reservation_nano` to **600000000000** and explicitly accept the
unknown hold, fresh reservation, full fresh D feature time and source change.
Earlier approvals do not authorize this incident.

In the clean qualified target checkout, prepare the copy without model calls:

```bash
.venv/bin/python harness/prepare_estimation_recovery.py \
  --source-root /path/to/stopped-2289-checkout \
  --old-manifest /path/to/stopped-2289-owner-evidence.json \
  --prior-source-root /path/to/original-651-checkout \
  --prior-source-root /path/to/stopped-878-checkout \
  --prior-source-root /path/to/stopped-1482-checkout \
  --prior-source-root /path/to/stopped-2082-checkout \
  --calibration-manifest /path/to/original-651-owner-evidence.json \
  --new-manifest /path/to/new-owner-evidence.json \
  --approval /path/to/new-private-recovery-approval.json
```

The new copy retains all five transitions and every original observation,
attempt, calibration record, approval, audit and unknown-charge reservation.
Earlier audit authorities keep their exact original scope/source/image/helper;
they are not relabelled or rerun. Per-incident reservation validation preserves
the 300-credit historical holds and this 600-credit D hold without shrinking
either to a common default.

For launch, supply five `--recovery-source-root` values: original 651, stopped
878, stopped 1482, stopped 2082, then stopped 2289, in that order, and retain the
original calibration manifest. All six paid-study roots are locked.
Check `--dry-run` before a separately authorized researcher launch.
Do not update/reset the stopped original checkout or manually clear
`oracle_halt`, reservations or checkpoints.

#### Specific 2402-step WebSocket-close interruption

The stopped state
`7379f557090b61ed94479a9cccf49ac83925d7c45bab606838e007e1377a7732`
is source `1d663f08af117332773feb22efc8e182734780a3`: 2402 completed
measurements, 2408 attempts and 138 completed trajectories of 315.
The interrupted attempt is
`pilot-estimation-gpt-6.1-sol-E-10-f05-feature-1`; its journal SHA-256 is
`19bffffd77043723c325765c2e11b188acd3a9ce7bc85a4bc7e577e0617bd068`.

The provider closed its WebSocket with `1001 please reconnect`. This is a
different signature from the earlier ECONNRESET: there are no modern API-call
or service-request correlation IDs and no complete terminal usage. The
`rte=false` observation is a treatment-header value, not evidence that a
retry is forbidden or free. The request reference embedded in the error text
must not be promoted into missing accounting identifiers.

Normal resume remains blocked. The new diagnostic
`websocket_closed_usage_unknown` explicitly aborts this terminal closure; it
does not authorize an automatic retry, waive billing, switch to HTTP or mark a
feature failed. An unknown charge is not zero. This correction cannot guarantee
provider connectivity.

The separately approved sixth copy preserves every observation and all six
unknown study holds, totalling **2100 nominal credits**: five 300-credit holds
and the earlier 600-credit D hold. Known study consumption is 27814.55969
credits. A fresh attempt of this same E/F5 step needs a separately reserved
**300 credits** and the full **1800-second feature allowance**, under the
unchanged 270-credit operational soft limit. Preserve calibration, prior
spending, allocation, ceiling and absolute deadline.

Publish and qualify the exact new source before a genuine state/source-specific
owner approval. Use the existing approval schema with this state, source and
attempt, `unknown_reservation_nano=300000000000`, and explicit acceptance of the
retained hold, fresh reservation/time and unregistered mid-study source change.
No prior approval authorizes this sixth transition.

In the new qualified checkout, use the standard copy-only preparer with the
stopped 2402 checkout as `--source-root`, its manifest as `--old-manifest`,
and five `--prior-source-root` values in order: original 651, stopped 878,
stopped 1482, stopped 2082, stopped 2289. Keep the original calibration manifest.
For launch, supply all six original roots as `--recovery-source-root`, adding
the stopped 2402 root last. All seven paid-study roots remain locked.
Verify `--dry-run`; leave paid collection to the researcher.
Do not edit/reset an original study, clear its halt/hold, or rerun a historical
outcome to obtain a better result.

#### Specific 2526-step mixed-retry and export interruption

The stopped state
`2f331781c5dfb922cc3610a212a823f9a197da57f09c754c83c22f325e6fdca5`
is source `958d75bc386964edfe6d211117ce53cf5fd53a82`: 2526 completed
measurements, 2533 attempts and 144 completed trajectories of 315.
The interrupted attempt is
`pilot-estimation-gpt-6.1-sol-E-10-f10-feature-1`; its journal SHA-256 is
`a1466ddc9276af0af0f549b523b5264e43ada48ed8e2d09210a7d9c10eb9b59d`.

Two separate problems occurred. The provider returned two correlated HTTP 500
`internal_error` failures in logical turn 6. The CLI emitted an error
`model.call_finished` after the first physical attempt, then reused the same
logical turn with `retryAttempt=1`; the next retry began without another finish
marker. The guard incorrectly discarded the first failure history at the
optional finish boundary. The correction carries failed logical-call history
across both boundary forms, while resetting the accounting watermark at every
new physical attempt. Success clears pending history; a different logical turn
does not inherit its retry index. Overlap, unmatched mirrors, wrong identities,
the shared three-failure ceiling and complete failed-request charges remain
mandatory. No new harness prompt, backoff or budget extension is added.

The subsequent result-export failure was independent. The generated regular
`provenance.json` was 622058 bytes, above its former 512 KiB classification.
It is now explicitly a bounded large structured export, capped at **16 MiB**,
like the existing tabular/trajectory outputs. `attempts.csv` already had that
larger cap and was not the cause. Small outputs retain 512 KiB limits,
`summary.json` retains 128 MiB, and the aggregate remains 192 MiB. Fixed
filename allowlisting, symlink/nonregular-file rejection and credential scans
are unchanged. Errors name the offending allowed artifact.

The exact stopped journal still lacks successful terminal usage and complete
failed-request charges. Recognizing its retry sequence does not certify zero
cost or authorize normal replay. The seventh approved copy retains all **2400
nominal unknown study credits**, including the previous 600-credit D hold and
latest 300-credit E/F10 hold. Known study consumption is 29220.13966 credits.
The same E/F10 step needs a separately reserved **300-credit** retry and full
**1800-second feature allowance**, under the unchanged 270-credit soft limit.
Do not change allocation, configuration, calibration, original start, absolute
deadline or budget ceiling.

After publishing and qualifying the exact corrected source, obtain a genuine
state/source/attempt-specific approval with
`unknown_reservation_nano=300000000000`. Use the stopped 2526 checkout as
`--source-root`, its manifest as `--old-manifest`, and six earlier
`--prior-source-root` values: original 651, stopped 878, stopped 1482,
stopped 2082, stopped 2289, stopped 2402. Preserve the original calibration
manifest. For researcher launch, provide all seven original roots in order
with `--recovery-source-root`; all eight paid-study roots stay locked.
Historical raw data and audit authorities must remain unchanged.

Source validation now records the earliest archival source for each attempt
in a map instead of repeatedly scanning prior-ID lists. This preserves the
same source-ownership rule while avoiding quadratic work as recovery history
grows. Verify status, dry-run, raw-byte preservation and bounded result
packaging before handing the new pinned launcher to the researcher.
No automatic launch or historical outcome rerun is authorized.

#### Specific 2691-step unaccounted-retry interruption

The stopped state
`4660d4b31bdd2bb8a8ac1c62c42dff8021d8cdbc87d24ed50e2c464c592b2d94`
is source `03ac696b382e539cad5f8153b91d144bb4c1990b`: 2691 completed
measurements, 2699 attempts and 155 completed trajectories of 315.
The interrupted attempt is
`pilot-estimation-gpt-6.1-sol-D-11-f06-feature-1`; its journal SHA-256 is
`8714b88c50b506296309408b09161980b35ba6b8cefeadffbb9d8cc13fb7ec78`.

The provider reset its WebSocket with ECONNRESET during logical turn 5.
The native same-turn retry succeeded, and the session shut down routinely
after nine successful calls. Their complete receipts total **14.87887 credits**,
but none correlates with the failed physical request. Routine shutdown and a
successful retry do not prove that the failed request was free. The transport
correctly reported `provider_retry_usage_incomplete`, with unknown total usage.
This is not another retry-history bug, and the accounting guard is unchanged.
Stopped cells now print their retained safe reason, so the operator sees more
than the final `oracle_halt` progress label.

Normal resume remains blocked. The separately approved eighth copy must retain
all **3000 nominal unknown study credits**, including the new **600-credit**
D/F6 hold and all seven earlier holds. Known study consumption is 30927.78079
credits. A fresh attempt at this same D/F6 step requires a separately reserved
**600 credits** and the full **2700-second feature allowance**, under the
unchanged **540-credit operational soft limit**. Preserve configuration,
calibration, original start, absolute deadline, allocation and ceiling.

Publish and qualify the exact new source before obtaining a genuine
state/source/attempt-specific approval with
`unknown_reservation_nano=600000000000`. The existing approval schema must
explicitly accept the retained hold, fresh reservation and time allowance, and
unregistered mid-study source change. No previous approval authorizes this
transition. The verifier pins the exact journal, its mirrored reset, ordered
error finish and successful same-turn retry, routine shutdown, missing
failed-request charge and incomplete-accounting terminal receipt.

Use the standard copy-only preparer in the new qualified checkout. Supply the
stopped 2691 mixed-retry checkout as `--source-root`, its manifest as
`--old-manifest`, and seven earlier `--prior-source-root` values in order:
original 651, stopped 878, stopped 1482, stopped 2082, stopped 2289, stopped
2402 and stopped 2526. Keep the original calibration manifest.
For researcher launch, provide all eight original roots in order using
`--recovery-source-root`; all nine paid-study roots remain locked.
Verify raw journals and audit authorities byte-for-byte, exact accounting,
status, dry-run and result packaging before handing off the pinned launcher.
No automatic paid launch, original-state edit or historical-outcome rerun is
authorized. Provider omissions may recur; this recovery cannot guarantee
connectivity or complete future billing.

#### Owner-authorized retry holds (keeps a study running through provider resets)

A single provider reset that the CLI retries successfully used to stop the whole
study: the successful calls were fully billed, but the reset request never
reported a charge, so every such session ended `provider_retry_usage_incomplete`
and the controller froze all cells. This happened three times in two days. The
transport guard is unchanged and still fail-closed: a missing charge is never
zero. A study may instead opt in to a bounded, conservative accounting mode.

The owner evidence manifest may carry an optional field. Without it, behavior
is exactly the earlier, strict one.

```json
"unaccounted_retry_hold_policy": {
  "max_holds": 40,
  "approval": "owner decision reference",
  "approved_at": "2026-11-11T00:00:00+00:00"
}
```

When present, a session is kept only if all of the following hold: it ended
normally with a routine shutdown; every successful call has a complete charge
and their sum equals the shutdown total; at most three failed requests remain
unbilled; the model, effort and routing are exactly as assigned; and fewer than
`max_holds` holds exist. The transport reports the certified successful sum as
`usage_lower_bound`, a floor and never a total. Then:

* The delivered work and its measurement are kept; nothing is replayed.
* The ledger entry becomes `retry_hold`. Its **entire reservation** (300 credits,
  600 for a D-arm feature) stays charged against the ceiling, and the verified
  floor is stored as `lower_bound_nano`. `actual_nano` stays empty.
* The step cost is recorded as **incomplete** in analysis, never as the floor.
  `attempts.csv` and `summary.json` show `credits_status=retry_hold` with
  `lower_bound_nano`.
* New work is not blocked. Reaching `max_holds`, removing the policy, or a floor
  above its reservation stops new paid work with an explicit reason.

The exact Gemini HTTP 503 shape at `/chat/completions` is also recognized when
its top-level `providerCallId` matches the legacy `request_id`, with assigned
Gemini/medium identity, HTTP/API status 503, `rte=false` and no auto/BYOK routing.
The existing three-failure ceiling and original session limits remain in force;
the transport never resends the prompt. HTTP provider IDs are not API/service
billing IDs, so a failed HTTP request is never certified by matching absent
identifiers. The policy can keep work only after a successful native retry,
normal shutdown and fully certified successful-call charges. A failed or
unfinished session still needs separately approved recovery.

An unidentified Gemini HTTP stream timeout is not a correlated 503. The exact
top-level `/chat/completions` transport timeout after 600000 milliseconds,
without a provider/API/service request ID, stops with
`http_stream_timeout_usage_unknown`. No request identity, failed charge or safe
retry is inferred from its message. The full reservation stays held, and the
normal-ended retry-hold policy cannot accept the interrupted session. This
diagnostic does not prevent the upstream provider timeout or resend the prompt.

Any other missing-charge condition, such as a 1001 close, a fault during the
session, or a mismatched receipt, still ends as unknown usage and needs the
separately approved copy-only recovery. Provider omissions can still recur and
no provider-side billing guarantee exists.

#### Prospective operational resilience

Newly qualified source can opt in to typed failure supervision through the
owner evidence manifest. This is a prospective protocol change, not permission
to modify a running study, clear an existing `oracle_halt`, or insert a policy
into a historical manifest. Publish, qualify, disclose and authorize the exact
new source and policy before collection. Existing studies retain their original
rules. The following example is not owner approval:

```json
{
  "resilience_policy": {
    "schema": "study-resilience-policy/v1",
    "approval": "REPLACE_WITH_OWNER_DECISION_REFERENCE",
    "approved_at": "2026-11-11T00:00:00+00:00",
    "max_quarantined_attempts": 10,
    "max_quarantined_credits": 6000,
    "route_failure_threshold": 3,
    "route_cooldown_seconds": 60,
    "retry_backoff_seconds": 2,
    "retry_max_backoff_seconds": 30
  }
}
```

Omitting the policy preserves earlier behavior. Setting both quarantine bounds
to zero permits only finally billed infrastructure retries and keeps strict
unknown-cost admission stops. Nonzero bounds explicitly accept residual unknown
provider charges so other eligible cells can continue. Reservations remain
provisions, not provider-enforced billing caps or measured spending. Each hold
consumes its full original reservation against the existing aggregate ceiling.
The count and credit bounds apply together; exhaustion pauses new admission.
This policy does not replace the separate successful-session retry-hold policy.

The transport emits `study-attempt-outcome/v1` with independent work, safety,
accounting and quiescence fields. Structured top-level provider or transport
failures need not match exact error messages or supply optional billing IDs.
Missing IDs and charges are never fabricated. Unsupported schemas, model or
effort changes, active discovery, malformed control records, isolation failures
and accounting contradictions remain fail-closed. A later safety violation
cannot be hidden by an earlier provider error.

* An incomplete request with final accounting may retry only before measurement,
  after owned cleanup, within the original time, credit, deadline and attempt
  limits. Persistent bounded backoff prevents immediate repeated dispatch.
* An incomplete request with unknown accounting is never replayed. Its cell is
  quarantined, its ledger entry becomes `quarantine_hold`, and `actual_nano`
  remains empty. Other cells continue only within both approved risk bounds.
* Repeated failures pause the assigned model route. Deferred cells do not occupy
  worker slots; ready routes can continue. The controller never substitutes a
  model, effort, arm or replicate. Cooldowns survive resume.
* Completed work with missing billing remains retained and cannot be replayed.
  Without the separately approved successful-session retry hold, it causes a
  financial pause rather than claiming oracle corruption.
* Functional nonpasses are measurements, not infrastructure errors. Measurement
  retries remain bounded to the same retained snapshot and never rerun the agent.

Raw events stay private. Each supervised outcome binds the exact source,
request, terminal receipt and raw-journal hashes. Resume verifies the evidence,
reservations and policy before admission. Derived `attempts.csv` adds work,
safety, accounting, failure-kind/stage, route, native-call counters and recovery
action fields; provenance reports observed counters and quarantine exposure.
Missing counter coverage is explicit. No prompt, provider diagnostic message
or raw journal is added to the shareable package.

For a stopped study already collected under this exact source and policy, a
generic same-source recovery can reconcile a durable failed terminal receipt
that survived an interrupted bookkeeping transition. It does not copy the
study or calibration and makes no model call. An owner authorization must bind
`schema=study-operational-approval/v1`, the exact stopped `state_sha256`, unchanged
`source_commit`, canonical `manifest_sha256`, an `attempts` mapping from each
selected attempt ID to its `terminal.json` SHA-256, `owner_approved=true`, an
approval reference and a nonfuture timezone-aware `approved_at` after the
attempt. Unknown-charge requests can only be quarantined, never given a fresh
allowance. Completed or measured work, live or ambiguous writers, source
changes, safety halts and expired deadlines are refused.

Validate first; without `--apply` this command writes no recovery state:

```bash
.venv/bin/python -B harness/prepare_estimation_recovery.py \
  --operational-study .study/STUDY_ID \
  --manifest /private/owner-manifest.json \
  --approval /private/operational-approval.json
```

After reviewing the preview, append `--apply` to commit the exact authorized
transition under the paid-study and controller locks. Original state and
approval are retained in the study's `operational-recovery` audit directory.
Source, schedule, calibration, original allowances, ledger history and absolute
deadline are unchanged. Repeating an applied authorization is rejected.
Changing source still requires the separate disclosed source-change procedure;
this command cannot recover legacy incidents that lack typed terminal evidence.

For the reported 3527-step interruption, the console's
`unexpected_runtime_activity` label alone is not a diagnosis. The retained
Gemini E-14 `f10-repair` journal confirms a top-level HTTP transport failure
after 61.5 seconds, not the earlier ten-minute timeout. Its event stream replays
as a supported transport failure under the prospective supervisor, with unknown
accounting. Historical replay does not establish provider cancellation or owned
cleanup. Do not clear its halt or assume the omitted charge was zero. This
candidate still needs source-bound migration and owner authorization before
the stopped legacy study can resume; offline tests do not supply that authority.

#### Specific 2722-step paired unaccounted-retry interruption

The stopped state
`42a75a6285d3fac59112ec7c7e0b684b18de16239d9f33f20961dfdc6aaed282`
is source `732c4896da7c0a5b0db0f60c02348743a5b2c54e`: 2722 completed
measurements, 2732 attempts and 157 completed trajectories of 315.
Two attempts halted together, each with the same signature as the 2691-step
incident (one correlated ECONNRESET, a successful same-turn retry, a routine
shutdown, and no charge for the reset request):

* `pilot-estimation-gpt-6.1-sol-B-11-f05-feature-1`, journal
  `a1a780066151b7d7d85bb720b22ba1ef0ae5d3c9df9bd58da5f485946bfbec6c`,
  with an error finish between the reset and the retry.
* `pilot-estimation-gpt-6.1-sol-E-11-f01-repair-1`, journal
  `adf74655c4b4ae14678a43e3bc34dcff6173d9472e0f90dc132d04331825cbe2`,
  retried without an intervening error finish.

Their nine successful calls total 14.23347 and 10.18283 credits and equal each
shutdown total, but those are floors. Known study consumption is 31374.66179
credits; the unknown holds are all eight earlier recoveries plus these two,
3600 nominal credits. A fresh attempt at each of these steps needs its own
separately reserved 300 credits and the full original allowance.

One recovery transition can now hold several attempts. The approval names
every held attempt as a sorted `attempt_id` list and states the combined
`unknown_reservation_nano=600000000000`. Use the stopped 2722 checkout as
`--source-root`, its manifest as `--old-manifest`, and eight earlier
`--prior-source-root` values in order: original 651, stopped 878, 1482, 2082,
2289, 2402, 2526 and 2691. Keep the original calibration manifest. For launch,
supply all nine original roots in order. No original state, journal, audit or
calibration byte may change, and no paid launch is authorized by the copy.

#### Specific 2865-step Gemini HTTP 503 interruption

The stopped state
`ae55cc6ae2fb758956105e738622a2a2b9ea87c6802c039346b32e254c655397`
is source `fc8dd5995cde046b4c2de1f2eb25a0df32ff39eb`: 2865 completed
measurements, 2877 attempts and 165 completed trajectories of 315. Two Gemini
attempts halted on HTTP 503 from `/chat/completions`:

* `pilot-estimation-gemini-4-argon-B-12-f04-feature-1`, journal
  `28b39857a766019a020b803181cf3778e3a6346680e0c1caec6d0912c7176e89`,
  retains its 300-credit reservation.
* `pilot-estimation-gemini-4-argon-D-12-f06-feature-1`, journal
  `d6d8a3c81e94f1780560fb11f75bbc1103f6962cdfefae75adbe6e067a60b84a`,
  retains its 600-credit reservation.

The old WebSocket-only classifier rejected the correlated HTTP provider
failure as `unexpected_runtime_activity`. Both journals retain an ordered
matching `providerCallId`/`request_id`, model/medium effort, top-level HTTP/API
503, `rte=false` and terminal error finish, but no successful retry, idle or
routine shutdown. Their failed-request charges remain unknown. Recognizing the
HTTP signature does not make these interrupted sessions qualify for the
completed-session hold policy, and it does not guarantee a future native retry.

Keep the earlier 3600 nominal recovery-held credits and the existing GPT
E11/F9-repair 300-credit `retry_hold` as well. After recovery, the two new holds
bring `recovery_hold` provisions to 4500 credits; the separate retry hold makes
4800 nominal held study credits in total. Fully accounted ledger usage is
33543.74832 credits. The existing retry-held step adds a certified 21.93386-credit
floor, not a complete charge; the registry's complete-plus-floor inventory is
33565.68218 credits. Never report that inventory as complete study billing.

Publish and qualify the exact new source before obtaining a genuine approval
bound to this state, both sorted attempt IDs and combined
`unknown_reservation_nano=900000000000`. Fresh B/F4 work separately reserves
300 credits and the full 1800-second allowance under the unchanged 270-credit
soft limit. Fresh D/F6 work separately reserves 600 credits and the full
2700-second allowance under the unchanged 540-credit soft limit. Preserve
configuration, allocation, original calibration, ceiling, absolute deadline,
all raw results and every earlier source/approval/audit authority.

Use the stopped 2865 paired-recovery checkout as `--source-root`, its manifest
as `--old-manifest`, and nine earlier `--prior-source-root` values in order:
original 651, stopped 878, 1482, 2082, 2289, 2402, 2526, 2691 and 2722.
Keep the first original calibration manifest. For researcher launch, supply all
ten original roots in order. Neither the old 2722 approval nor the existing
200-hold policy authorizes this new copy or a paid launch. Keep the stopped
checkout unchanged and validate the new copy's accounting, raw bytes, status,
dry-run and private result packaging before a separately authorized restart.

#### Specific 3473-step Gemini HTTP stream timeout

The stopped state
`a1759e095bed45164905610c73efcfa671aa6dcd9dedcbf2ee07250c548d3745`
is source `29e5f0834717b3c8a58a248858782174e775b6b8`: 3473 completed
measurements, 3486 attempts and 201 completed trajectories of 315. The exact
attempt is `pilot-estimation-gemini-4-argon-D-14-f06-feature-1`, journal
`44ef3324c6aa47d8945cd2dcdff87ad4928f8c2043fb449684b3bbe3e528805c`.

The provider's native HTTP stream timed out after 600000 milliseconds. The
structured top-level failure and mirror retain Gemini/medium, HTTP transport,
`/chat/completions`, `failureKind=transport`, `rte=false`, no auto/BYOK routing
and an ordered terminal error finish. The modern event has no provider/API/
service request ID, and the mirror has an empty `request_id`. There is no
successful retry, idle or routine shutdown. The old source reports
`unexpected_runtime_activity`; the new explicit timeout reason is still a
usage-unknown hard stop, not permission to retry this uncorrelated request.

Keep the current D/F6 **600-credit** unknown reservation, all **4500** earlier
recovery-held credits and all ten existing `retry_hold` entries totaling
**3600** reserved credits. Recovery brings `recovery_hold` provisions to 5100
credits; together with the retry holds, all **8700 nominal held study credits**
remain counted. Fully accounted ledger usage is 39889.35262 credits. Existing
retry-held steps contribute a 217.54597-credit certified floor, not complete
charges. The registry's complete-plus-floor inventory is 40106.89859 credits;
never report that as complete study billing or turn any held cost into zero.

After publishing and freshly qualifying the exact new source, obtain genuine
state/source/attempt-specific approval with
`unknown_reservation_nano=600000000000`. A fresh D/F6 attempt separately reserves
600 credits and the full original 2700-second allowance under the unchanged
540-credit operational soft limit. Preserve every raw result, existing
`max_holds=200`, source/approval/audit history, calibration, allocation, ceiling
and original absolute deadline. An earlier source or recovery approval does
not authorize this transition or a paid launch.

Use the stopped 3473 HTTP-recovery checkout as `--source-root`, its manifest
as `--old-manifest`, and ten earlier `--prior-source-root` values in order:
original 651, stopped 878, 1482, 2082, 2289, 2402, 2526, 2691, 2722 and 2865.
Keep the first original calibration manifest. For researcher launch, supply all
eleven original roots in order. Never edit or overwrite the stopped checkout;
validate exact accounting, every preserved raw/calibration byte, status,
dry-run and private packaging in the new approved copy before a separately
authorized restart. Provider connectivity and final billing are not guaranteed.

#### Exception attribution and intervention coverage

A declared product exception raised by a candidate source-loaded view getter
can be a failed software outcome. Its classification must bind the live
exception class to a declared package export and the actual candidate source
frame. Arbitrary attribute traps, foreign classes, builtin aliases and
exceptions caused by memory, timeout, OS or import failures remain unknown.
Do not classify an exception from its message or reported name alone.

Historical raw measurements are retained. Attribution corrections require
separate read-only reevaluation of the same recorded candidate snapshots and
an explicit analysis-adjudication audit. No model is called to improve a poor
outcome, and no passed/failed result may be promoted by the audit. The original
metrics and raw step journals remain unchanged; derived reports must identify
the attribution overlay and its source/image.

Retain a separate `analysis-adjudications.json` manifest using
`analysis-adjudications/v1`, bound to the exact pre-recovery state SHA-256,
execution source commit, immutable image and attribution-helper SHA-256.
Each entry names one original `run_id` / `step`, canonical whole-record
SHA-256, candidate snapshot head, and a bounded regular audit file with its
SHA-256. Each audit's `evaluation` also binds that same source/image/helper
and the isolated, credential-minimal execution. Its metrics/diff are the
preserved originals, not measurements from a new run.

Known passed/failed outcomes and the original raw failure must be unchanged.
Only positively proven candidate-exception `error` to `failed` changes are
eligible. Any present invalid entry stops the entire overlay; it is not
silently skipped or partially applied. The source-pinned reporting path
accepts the exact approved interrupted attempt's recovery bookkeeping only
with validated retained approval, never arbitrary changes to its timing,
source or unknown charge. Do not overwrite an audit or rerun a contradictory
result until it is green.

The harness cannot infer the absence of out-of-band human edits or task hints.
An absent intervention record remains unknown, not unassisted. The operator
can supply `intervention-coverage/v1` evidence with `study_id`, exact
`state_sha256`, `owner_attested: true`, a nonfuture timezone-aware `attested_at`,
nonempty `evidence_reference`, and disjoint `unassisted_run_ids` /
`assisted_run_ids` covering every completed trajectory in that scope.
Partial or future trajectories are not covered prospectively.

```bash
.venv/bin/python harness/intervention_coverage.py \
  --study-directory .study/pilot-estimation \
  --attestation /private/path/operator-intervention-attestation.json
```

This records immutable sidecar evidence without rewriting original
observations. Reporting applies it in memory only to unchanged completed
trajectories in the scope. Logged content assistance cannot be erased. Existing
attestations are never overwritten; preserve them when preparing any later
analysis copy. Until real operator coverage is supplied, the affected primary
unassisted comparison stays unavailable.

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
Files must be regular and not linked. Large table, JSON and trajectory exports
are capped at 16 MiB each except `summary.json`, which is capped at 128 MiB;
other exports are capped at 512 KiB each, and the total at 192 MiB; token
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
