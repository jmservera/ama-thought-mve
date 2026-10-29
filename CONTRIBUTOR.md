# Collaborator handoff

**Status: offline source/setup package; paid execution is not enabled.**
The original [OSF registration](https://osf.io/ywsrv/overview) is owner-confirmed
approved. This corrected candidate is subsequent to that registration. The
owner must record [the prospective clarification](protocol/prospective-corrections-2026-10-28.md)
before affected collection. No calibration/pilot or paid probe is authorized
by unpacking this bundle.

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
local environments and OSF receipts are excluded. Existing tracked historical
smoke summaries remain excluded historical diagnostics, not registered data.

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

## Billing: what an administrator must establish

The registered whole-study ceiling is 300,000 AI Credits, including prior
14.54324 credits, calibration, every attempt and any logged non-study model
probe. Remaining allowance before any new probe is **299985.45676 credits**.
The company one-million-credit per-collaborator allowance is not that ceiling.
CLI `--max-ai-credits` is soft and cannot supply the provider hard stop.

Use the organization's supported billing administration process to configure
an **individual user-level AI-credit budget**, not only an org/enterprise
metered-spending budget. Current provider documentation expresses its API budget
in whole USD at 100 AI Credits/USD and covers included and metered credits.
For a fresh zero-consumption user budget, 2999 USD = 299900 credits is a
conservative cap below the initial remaining study ceiling; 3000 USD is too
high after prior use. This dated operational mapping is not a retrospective
currency rewrite of the registered ledger.

Have the administrator determine the **actual billing cycle/reset**, effective
budget precedence, creation-time accounting and expiration. Stop before reset,
expiration or any budget/account change. Account for all later prior spend and
reconfigure/re-audit if necessary; never reset local state to recover headroom.
Other concurrent Copilot usage consumes the same operator budget and can only
reduce available study resources; do not silently shrink the sample.

`harness/billing_check.py` makes read-only GitHub identity/budget requests and
writes a private audit, not an enabling token. It needs the operator's supported
Copilot credential supplied privately as `COPILOT_GITHUB_TOKEN` and separate
appropriately authorized `gh` billing access. Prefer approved interactive
operator authentication; do not paste tokens in commands, source, artifacts or
chat, and do not request broader permissions to bypass an access denial.
If the approved login cannot supply the documented identity/audit route,
record that as an unresolved dependency rather than extracting credentials.

```bash
mkdir -m 700 .study/budget-audit
python3 harness/billing_check.py \
  --organization ORGANIZATION --operator OPERATOR --budget-id BUDGET-ID \
  --remaining-credits 299985.45676 \
  --execution-deadline ACTUAL-UTC-DEADLINE \
  --billing-cycle-end ACTUAL-UTC-RESET \
  --out .study/budget-audit/receipt.json
```

Replace uppercase placeholders with verified values. Timestamps need explicit
timezones. This command never modifies a budget, launches a model or authorizes
execution. An unavailable/ambiguous API response fails closed. Its supplied
reset date still needs independent verification.

## Runtime and information boundary: still blocking

The paid dispatch is not implemented. The Docker command builder and legacy
configs are preparation, not a supported launch path or proof of isolation.
Blanket tool approvals have been removed; specific preparation permissions are
not a sandbox. Never add allow-all, YOLO, trust-all or permission-skipping flags
to make a run succeed.

The intended default-deny gateway must permit only the required Copilot/auth
transport while keeping agent tool traffic separate from that trusted transport.
Do not allow `github.com`, `api.github.com` or raw-content hosts wholesale:
the public repository contains held-out evaluator/reference/CR1 material.
A generic CONNECT proxy cannot filter URL paths within TLS. Outbound NAT
alone is not filtering. Network restrictions must be OS-enforced, not just
prompts, URL deny rules or a transcript scan.

A candidate runtime must:

- Expose only current task specifications/visible examples and the disposable
  candidate repository, never evaluator results, future prompts, host home,
  Docker socket, credentials or other run directories.
- Isolate model-controlled shells, test execution, built-in file tools and any
  MCP/LSP/subagent paths; host Copilot authentication must not become an
  agent-readable token. Sandbox shell support alone does not isolate other
  tool types.
- Demonstrate negative filesystem and outbound canaries, including attempted
  retrieval of this public repository's hidden/reference/CR1 files and metadata
  endpoints; demonstrate positive required auth/model routes separately.
- Bind actual response-model identity and final usage to the assigned model,
  retain unknown charges and interrupted processes, and preserve the original
  time/credit allowance across infrastructure-only retries.

Copilot 1.0.105 documents Linux MXC/bubblewrap shell sandboxing, but it requires
host prerequisites and other file tools are not OS-sandboxed. A shell sandbox
with all other tools exposed does not establish the required boundary. No
supported, independently probed runtime boundary has been accepted here.
Do not provision paid Azure infrastructure or alter shared network policy
without separate authorization.

## Collection handoff

Resolve the exact source-bound entries in
[readiness-handoff.md](protocol/readiness-handoff.md), including the corrected
oracle and limitations of the scoped AI reviews. The original source-bound
submission approval does not approve every new candidate.
The owner records the prospective OSF clarification and separately authorizes
the exact freeze/tag. The existing historical tag is not reusable permission.
No freeze file/tag or evidence acceptance is synthesized by this package.

Only after actual auth, provider enforcement and containment are verified may
the conditionally authorized logged non-study per-model probes proceed. Charge
them to the whole-study ledger, never expose study features/CR1 in the probes,
and record model/effort/routing/usage evidence. A subsequent explicitly
authorized calibration/pilot launch requires the actual live backend as well;
the current controller continues refusing it even if nominal gates are filled.
