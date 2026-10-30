# Collaborator handoff

**Status: owner-reviewed runtime/access evidence accepted and source freeze authorized after merging #4. Prospective OSF update and collection authorization remain pending.**

[The freeze manifest](protocol/freeze.json) binds the exact source/tag, input
fingerprint, image and canary receipt. Its prospective-registration completion
date is deliberately unset until the actual OSF amendment is recorded; do not
substitute the original registration date or treat the freeze as launch permission.
The original [OSF registration](https://osf.io/ywsrv/overview) is owner-confirmed
approved. This corrected candidate is subsequent to that registration. The
owner must record [the prospective clarification](protocol/prospective-corrections-2026-10-28.md)
before affected collection. No calibration/pilot or paid probe is authorized
by unpacking this bundle.

## Run and share in one command

On the prepared, accepted VM, after the prospective OSF update and owner launch
authorization:

```bash
./run-experiment.sh
```

This runs the frozen **pilot-estimation** schedule, using the **Copilot user
already signed in on this host**. No username, token or account file needs to be
passed to the program or Docker. The SDK checks user authentication before any
credit reservation; sign in to Copilot CLI on this host if that check fails.
Authentication and licence context stay on the trusted host; candidate
containers receive neither. Separate verified model access is still required.

The launcher selects `.venv/bin/python` when available and the local metric-tool
PATH automatically. VM preparation is one-time setup, not silently installed or
changed during collection. All freeze, runtime, budget and registration gates
remain enforced; this candidate is **not yet authorized for collection**.

Progress shows **completed / total steps, remaining steps**, trajectory count,
model, arm and current step. The registered pilot has 318 planned steps;
excluded calibration has 150. A completed step can be a measured nonpass:
progress is not a success rate. Retries do not increase the planned denominator.
Rerunning the same command resumes only where existing durable-recovery and
accounting rules permit; it never resets credit usage or bypasses a stop.

```bash
./run-experiment.sh --dry-run          # read-only readiness and schedule
./run-experiment.sh --status           # saved progress; no sign-in/model call
./run-experiment.sh --share            # recreate the local results ZIP only
./run-experiment.sh --smoke --study-id offline-check  # fake agent, zero model credits
```

Results are generated automatically, including partial-run availability:
`.study/pilot-estimation/results/report.md` is the readable report and
`.study/pilot-estimation/pilot-estimation-results.zip` is the shareable package.
The ZIP contains only validated derived reports, tables, figures and provenance,
never raw attempts, prompts, study repositories or credentials. Nothing is
uploaded automatically; `--publish` remains an explicit separate GitHub action.
For explicitly authorized excluded calibration, use
`./run-experiment.sh --phase calibration --study-id excluded-calibration`.
Do not silently chain calibration into the pilot or reuse a study ID across phases.

## What this package contains

Unlike the original protocol-only OSF attachment, the contributor archive
contains the complete committed runnable source, tests, reference snapshots,
dependency manifest, launchers, documentation and an exact shallow Git checkout.
It is for the **trusted operator only**. Never mount this checkout, its `.git`,
the archive, hidden tests, future CR1 text or reference solutions into a
model-visible candidate workspace.

`manifest.json` binds all archive file hashes and executable modes, the corrected
source commit, controller input hash and original registration source. The
external `.sha256` file binds the archive. Private run data, credentials,
local environments and OSF receipts are excluded. Previously published tracked
development notes and historical smoke summaries are included as part of the
exact source checkout; they remain historical diagnostics, not registered data.
Ignored current-session evidence is never copied.

## Offline setup and checks

Use the dedicated Linux VM. Python 3.11+, git and make are sufficient for the
standard-library diagnostic pipeline. Do not run TCR against the operator
checkout; it discards uncommitted work in its disposable target repository.

```bash
sha256sum -c contributor-CANDIDATE.tar.gz.sha256
tar -xzf contributor-CANDIDATE.tar.gz
cd contributor-CANDIDATE/source
python3 harness/prepare_contributor.py --verify ../../contributor-CANDIDATE.tar.gz
./run-study.sh --smoke --dry-run
./run-study.sh --smoke --study-id collaborator-offline-check
```

Replace `CANDIDATE` with the actual archive name. The package can be relocated;
Git points to the exact source commit and its origin is the public repository,
not the preparation VM. Verify an externally supplied checksum through a
trusted channel; an embedded manifest alone is not an authenticity signature.
Offline smoke runs only the fake agent and consumes zero model credits.

For the full existing offline tests and production metric tools:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r harness/requirements-measure.txt
npm install --prefix .study/runtime-tools --no-audit --no-fund --save-exact jscpd@5.4.1
export PATH="$PWD/.venv/bin:$PWD/.study/runtime-tools/node_modules/.bin:$PATH"
.venv/bin/python -B -m pytest -p no:cacheprovider harness/tests -q
.venv/bin/python -B harness/validate_suite.py suites/s1-retrofit --repeats 3
.venv/bin/python -B harness/contract_panel.py --out protocol/contract-panel.json --check
```

Pin Copilot to 1.0.105, Ruff to 0.17.3, Lizard to 1.24.3 and jscpd to 5.4.1.
The dependency manifest currently leaves some test-only/transitive packages
unpinned; record the actual resolved environment and validate/freeze it before
collection rather than claiming the source bundle is a frozen VM image.
Version/help checks make no model call. No global installation, account
configuration or package build is performed by the check-only bootstrap script.

### Repository-local Copilot SDK

The transport pins **`@github/copilot-sdk` 1.0.28**, compatible with the selected
**Copilot CLI 1.0.105 / protocol 3**. Do not rely on an older machine-wide SDK or
replace its bundled CLI implicitly. Install the lockfile locally:

```bash
npm ci --prefix harness/copilot-sdk --ignore-scripts --no-audit --no-fund
npm --prefix harness/copilot-sdk test
node harness/copilot-sdk/transport.mjs --check-runtime \
  --cli-path "$(command -v copilot)" --base-directory "$PWD/.study/sdk-runtime-check"
```

These commands install dependencies, run fake-transport tests and check runtime/
authentication metadata; they do not create a model session. The last command
uses only private runtime scratch under `.study/`. `node_modules` is neither packaged nor a protocol input;
the exact manifest, npm lockfile and transport source are. Reinstall with
`npm ci`, not an unpinned upgrade, on the collaborator VM. The actual runtime
must separately verify the explicit CLI executable, protocol and signed-in user.
Keep OAuth on the trusted host; never copy authentication material into the
candidate container. Passing these checks is not collection approval.

## Billing: soft limits and the accepted risk

The owner accepted residual soft-limit overshoot risk on **29 October 2026**.
The registered whole-study envelope remains **300,000 AI Credits**, including
known prior **17.59833 credits**, calibration, probes and every attempt. The company
hard limit is **1,000,000 credits per collaborator**, **owner-reported, not
independently verified**. It is an outer company allowance, not a hard stop at
the study budget. No separate study-specific provider hard cap is required.

The supplied controller config applies a uniform **10% operational buffer**:

| Control | Supplied setting | What it means |
| --- | --- | --- |
| `session_soft_limit_credits` | 270 | SDK session soft limit; per original session, including any retry, not a global study cap |
| `session_reserve_credits` | 300 | Nominal reservation ceiling; the initial reservation includes 30 credits of headroom above the soft threshold |
| `ceiling_credits` | 270000 | Local admission stop, leaving 30000 below the registered 300000 envelope |
| `prior_credits` | 17.59833 | Confirmed historical smoke plus three successful excluded backend checks; excludes the three unknown charges |
| `historical_credit_provisions` | 900 held | Three exact, separately owner-approved 300-credit provisions, not actual spending |

Three excluded checks have unknown actual usage and each retains a **300-credit
reservation**. On 29 October the owner separately approved carrying each as a
historical budget provision. Three later excluded backend checks at `eff4d09`
returned complete usage totaling **3.05509**, bringing known prior usage from
14.54324 to **17.59833**; their successful reservations are settled, not held.
Known usage plus historical held budget is **917.59833**,
leaving **269082.40167 credits** within the 270000 admission threshold before
new reservations. This permits accounting admission, not live verification or
collection without their separate approvals.
All three attempts used empty non-study workspaces, 30-credit soft limits and 90-second
deadlines, and returned no tool calls or complete billed-usage evidence.
An SDK directory-setup defect was corrected without another model request;
historical create/send and zero charge are not established by missing events.
The second check at `cb19559` stopped on unintended built-in MCP startup; Sonnet
and Gemini were not called. Its durable shutdown reports zero usage, but this
is not a complete billing receipt. The restrictive startup correction was tested
separately in a new tmux session without sending a model prompt.
Preserve all three private attempt ledgers unchanged. Actual usage remains null;
the config binds each provision to its exact source, attempt, ledger digest
and separate owner approval. Do not book any 300 as actual usage or release
any hold without legitimate reconciliation. If later evidence exceeds a provision,
stop and account for the excess. This is not a guaranteed provider billing bound.
The later authorized check at `5585ed1` also stopped before any candidate tool
call, with incomplete usage. The owner separately approved retaining its full
300-credit reservation as the third exact historical provision. This resolves
its accounting-admission blocker, not runtime acceptance or authority for another
model call. The original ledger remains unchanged and blocked, with actual usage null.
Future incomplete usage still stops; it is never automatically converted to a
historical provision. The source bundle contains no private session/authentication artifacts.
The preparatory CLI configs also use 270. All three models/arms use the same
setting. These are prospective operational changes, not edits to the immutable
original OSF attachment; record the linked clarification before collection.

**Important:** GitHub documents the CLI limit as
[soft](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/set-session-limit):
an in-flight response completes even if it exceeds the threshold. Neither a
30-credit session buffer nor the 30000-credit study buffer guarantees the
registered envelope cannot be exceeded. The owner considers this reasonable
financial risk under the much larger reported company hard limit. No claim is
made that the controller enforces actual billed consumption or the company cap.

Monitor complete final usage after each attempt and reconcile all charges
before admitting more work. Missing/partial usage holds the reservation and
blocks new work; any reservation overrun is retained and stops admission.
Retry only documented infrastructure failures within the **remaining original**
time and 270-credit allowance; never reset the cap. The CLI minimum is 30:
if less remains, stop rather than round up or create a fresh allowance.
Do not silently reduce the planned sample if calibration shows it unaffordable.
Stop and record a prospective amendment instead.

Record any known company billing-cycle/reset, scope or account changes.
A reset does **not** replenish the lifetime study allowance; never clear prior
spend or reset local state to recover headroom. Concurrent non-study Copilot
usage can consume the same company allowance. Resolve ambiguous accounting
before resuming; a soft limit is not permission to ignore missing charges.

### Optional administrator budget audit

An administrator may add a stricter provider user-level budget as extra
protection, but this is **not a prerequisite under the accepted risk policy**.
`harness/billing_check.py` remains a strict, read-only audit of that optional
claim; it is not an enabling token or an audit of soft-limit compliance.
It needs the operator's supported credential supplied privately as
`COPILOT_GITHUB_TOKEN` and separate appropriately authorized `gh` billing access.
Prefer approved interactive authentication; never extract credentials or paste
tokens in commands, source, artifacts or chat. No broader access is requested
to bypass a denial. Missing optional billing-admin API access alone is not a
launch blocker; actual operator authentication/model access still must be proven.

```bash
mkdir -m 700 .study/budget-audit
python3 harness/billing_check.py \
  --organization ORGANIZATION --operator OPERATOR --budget-id BUDGET-ID \
  --remaining-credits 269985.45676 \
  --execution-deadline ACTUAL-UTC-DEADLINE \
  --billing-cycle-end ACTUAL-UTC-RESET \
  --out .study/budget-audit/receipt.json
```

Replace placeholders and remaining allowance with verified current values;
timestamps need explicit timezones. This command never changes budgets, launches
a model or authorizes execution. An unavailable/ambiguous response fails that
optional audit, not the owner-accepted soft policy. Its supplied reset date
still needs independent verification before claiming a provider hard boundary.

## Isolated live backend: owner-reviewed evidence accepted

The owner accepted corrected `1120002` evidence on 30 October and explicitly
selected no independent reviewers for this first study beyond the separate
executor. That is operational separation, not an independent technical audit.
See [the exact decision record](protocol/runtime-acceptance-2026-10-30.json).
Final source-bound freeze, prospective OSF update and collection authorization
remain separate. All technical safeguards described below remain unchanged.

The non-smoke controller now uses `harness/isolated_runtime.py`, not the legacy
local/Docker command templates. The trusted host runs SDK 1.0.28 and the explicit
CLI 1.0.105 executable using approved interactive authentication. No token is
required in the controller environment. The SDK exposes only `isolated_exec`;
built-in tools, discovery, MCP servers and unrelated permission requests are
excluded or denied. Never add blanket approval, permission-skipping, extra host
tools or trusted directories to repair a failed check. The owned CLI explicitly
receives `--disable-builtin-mcps`, but CLI 1.0.105 does not apply that interactive
setting in headless mode. The authoritative restriction is the SDK session's
`disabledMcpServers: ["github-mcp-server"]`. Empty mode/tool exclusion alone
does not stop server startup. The SDK may report that exact disabled builtin as
inert catalog metadata; pending/connected activity, foreign catalog entries and
all MCP tools still fail closed.

The opt-in transport regression exercises actual deferred startup inside an
owned tmux session with `MVE_COPILOT_CLI` set to the pinned executable. A registered
local handler rejects every inference HTTP/WebSocket request without forwarding
to a provider. It verifies startup and the isolated-only tool catalog, not real
model access or complete provider billing. Ordinary `npm test` does not run it.

The bounded transport journal retains SDK events received after a failure,
including shutdown usage diagnostics. Those observations do not clear the
failure or certify a zero bill: incomplete failed-session accounting remains
unknown and its reservation stays held until separately reconciled.

Each tool call uses a fresh, no-network container with read-only root, bounded
tmpfs/CPU/memory/processes/output and a nonroot candidate identity. A separate
fixed supervisor controls state and result publication. No candidate container
receives credentials, a writable host mount, the Docker socket, operator
checkout, hidden suite, future prompts or reference solutions. Host OAuth/model
transport is separate from candidate traffic; this does not depend on globally
allowlisting GitHub domains or changing shared network policy.
Linux resets ordinary child dumpability after exec; the boundary is the distinct
protected supervisor, not persistent child-zero or a zero bounding set. The
prospective notice records the actual UID/capability/NNP/core-limit observations.

Candidate filesystem/Git state is replayed only inside isolation and remains
opaque on the host. Feature/CR checkpoints import only validated committed
regular files. Uncommitted feature/CR changes are discarded; C retains only a
regular `REVIEW.md` working file and reports other changes as violations.
Canonical host Git never consumes candidate Git metadata. It preserves exported
blob bytes and executable modes, including committed ignored files, rather than
running candidate attribute filters. Trusted trajectory history retains
`feature-start`/`feature-end`; arbitrary actor commit metadata is not retained.
Fresh containers preserve files, not background daemons, sockets or process
memory across calls. Resource ceilings and these differences are prospective
runtime details, not claims that the original local environment is unchanged.

Visible tests and hidden/metric evaluation run in separate containers from
read-only canonical snapshots. Only the applicable hidden stage is mounted;
diagnostics and scores remain private and never return to the study agent.
Protected supervisor framing and fixed-denominator validation are not proof
that a fully adversarial Python implementation cannot tamper with in-process
test observations. Keep that limitation explicit in the owner-reviewed study.

Run the image-specific offline canaries, then the coupled Docker/reference tests.
The controller requires `.study/runtime-canary.json` to match the execution
source and owner freeze, including the immutable image ID and receipt hash.
A canary receipt is test evidence, not owner approval. Actual response model,
reasoning effort, routing and complete final billed usage require separate live
evidence. Missing/partial usage retains its reservation and blocks admission.
An ambiguous owned container or containment failure halts collection globally;
never prune containers or edit state to manufacture recovery.

No supported runtime has been accepted for collection merely by installing the
SDK or passing offline checks. Do not provision paid Azure infrastructure or
alter shared network policy without separate authorization.

## Collection handoff

Resolve the exact source-bound entries in
[readiness-handoff.md](protocol/readiness-handoff.md), including the corrected
oracle and limitations of the scoped AI reviews. The original source-bound
submission approval does not approve every new candidate.
The owner records the prospective OSF clarification and separately authorizes
the exact freeze/tag. The existing historical tag is not reusable permission.
No freeze file/tag or evidence acceptance is synthesized by this package.

Only after the current unknown-usage hold is resolved and actual auth,
buffered accounting/telemetry and containment are verified may further
conditionally authorized logged non-study per-model probes proceed. Charge
them to the whole-study ledger, never expose study features/CR1 in the probes,
and record model/effort/routing/usage evidence. A subsequent explicitly
authorized calibration/pilot launch requires the exact accepted runtime,
source-bound canary receipt and owner freeze as well. This package creates no
acceptance record, freeze/tag or launch authorization.
