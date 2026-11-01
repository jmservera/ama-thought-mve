---
title: Private trusted researcher and operator handoff
description: Offline v5 setup, information separation and prospective launch requirements
ms.date: 2026-11-01
---

**Offline candidate only. Collection is blocked.** Historical v4 approvals and
[freeze.json](protocol/freeze.json) do not approve this changed source.
The original OSF registration is owner-confirmed; the new prospective
amendment, independent review, new freeze and launch authorization are pending.

## Private sharing and information separation

The owner selected `public-pr-now` on 2026-11-01 after acknowledging both original
repositories remain public. The parent may publish development-source PRs now;
this does not release researcher archives/results, mutate visibility/OSF or
authorize collection. Interim development-source exposure is a contamination
limitation, including possible oracle/reference knowledge. Future privacy cannot
undo it. The title remains *Feature-Driven Decay in an Agentic Coding Loop*.

Before any experiment, the owner must make both original repositories private
and attest the exact repository IDs, readback time, visibility and access policy.
The trusted independent operator must have no access to those repositories or
the paper. These owner attestations and operator access readbacks are pending,
not facts inferred from private archive delivery. Previously public/model
exposure cannot be undone by changing visibility.

The operator may possess the complete protected harness, hidden tests and
reference assets for independent execution/review. **Candidates may not.**
Never mount the kit checkout, its `.git`, archive, paper, hidden outcomes/
identifiers/messages, reference code, future specifications or unreleased
change requests into candidate execution.

Candidate tools remain credential-free, no-network, resource-bounded containers.
The trusted host SDK's necessary provider network/authentication is distinct;
neither grants candidate shell/network access. Do not copy credentials into Docker.
Agents receive only current/previous immutable visible specifications and approved
examples. E is a visible-repair package, not a hidden-feedback intervention.

The private contributor archive includes complete committed source and a shallow
exact-source Git checkout, verifies bytes/modes and supplies an external SHA-256.
Exchange that checksum through a trusted channel. An embedded hash is not a
signature or independent approval. The origin URL names the owner repository;
it is not a claim about its actual visibility. Nothing uploads automatically.
New contributor packaging requires a clean committed exact source; this offline
uncommitted candidate cannot be packaged as if frozen.

## Offline setup and checks

Use Python 3.11+, git and make. Install validation dependencies only after a
missing-dependency failure or manifest change, with **pip**, in a dedicated
external per-task virtualenv. Example from this checkout:

```bash
python3 -m venv ../mve-v5-validation-venv
../mve-v5-validation-venv/bin/python -m pip install -r harness/requirements-measure.txt
npm install --prefix .study/runtime-tools --no-audit --no-fund --save-exact jscpd@5.4.1
mkdir -p .study/scratch
export TMPDIR="$PWD/.study/scratch"
export PATH="$PWD/../mve-v5-validation-venv/bin:$PWD/.study/runtime-tools/node_modules/.bin:$PATH"
export PYTHON="$PWD/../mve-v5-validation-venv/bin/python"
$PYTHON -B -m pytest -p no:cacheprovider harness/tests -q
$PYTHON -B harness/validate_suite.py suites/s1-retrofit --repeats 3
$PYTHON -B harness/contract_panel.py --out protocol/contract-panel.json --check
$PYTHON -B harness/mutation_adequacy.py --out .study/v5-mutations-NEW.json
./run-study.sh --smoke --study-id v5-offline-check
```

Choose new output/environment names; do not overwrite another task's files.
Pin Ruff 0.17.3, Lizard 1.24.3 and jscpd 5.4.1. Resolve/record the complete
dependency environment before collection; package installation is not VM
qualification. Do not modify the paid backend or globally install/configure it.
The check-only bootstrap script does not install tools or invoke models.

### Repository-local Copilot SDK

The existing transport pins SDK 1.0.28, CLI 1.0.105 and protocol 3. Its manifest
requires Node >=24. Missing/older prerequisites must be disclosed, not silently
qualified. Restore its lockfile locally when missing:

```bash
npm ci --prefix harness/copilot-sdk --ignore-scripts --no-audit --no-fund
npm --prefix harness/copilot-sdk test
```

These fake-transport tests create no model session. Runtime/user-authentication
and actual provider model/effort/billing evidence remain separately gated.
Do not invoke a paid probe to resolve an offline prerequisite.

## Run and share in one command

```bash
./run-experiment.sh --smoke --study-id v5-offline-check
./run-experiment.sh --dry-run
./run-experiment.sh --status
./run-experiment.sh --share
```

The smoke command is zero-credit diagnostic work. Status/share read existing
local data only. Share recreates a private derived-results ZIP, not an upload.
It never includes raw logs, candidate repositories or credentials.
Publication is planned only after collection and paper release with explicit
source-bound owner authorization; no release or OSF embargo configuration is
performed here.

After future genuine exact-source gates, separately authorize excluded
`--phase calibration --study-id excluded-calibration`, 15 trajectories/240
sessions without CR1. Main `pilot-estimation` (legacy `first`) means the new
fixed 495/8415 design, not the old 18/318. Old metadata remains v1.
Do not chain phases or reuse IDs to restart poor outcomes.

## Billing soft limits and the accepted risk

Historical cloud/sign-in/usage exports are explicitly owner-deferred. The critique
uses repository evidence only, not new live-export reconciliation. This deferral
does not remove historical holds or prospective complete billing/model/assistance
requirements and grants no model-session permission.

The unchanged nominal aggregate is **300000**, local admission **270000**.
Known prior **21.79019** plus four exact **300-credit holds** count. Holds are
unknown provisions, not certified spending; new unknown usage stops new work.
The owner-reported company 1000000/collaborator cap is not independently
verified or a study-specific stop. No financial conversion is made.

| Original step | Nominal reservation | Operational soft allowance | Time |
| --- | ---: | ---: | ---: |
| A/B/C/E feature | 300 | 270 | 30 min |
| D feature only | 600 | 540 | 45 min |
| B/C/E post | 300 | 270 | 15 min |
| Every CR1 | 300 | 270 | 45 min |

Retries share the original aggregate allowance and snapshot, never top it up.
SDK minimum remaining allowance is 30 credits; stop below that.
Missing timing/accounting, conflicting snapshots and overshoot remain stops.
In-flight responses can exceed soft caps; buffers are not billing guarantees.

After complete cost-only calibration, the deterministic helper must verify all
15 actual attempt/accounting/model/assistance records, project all unchanged
495 trajectories with the proposed 1.25 margin, reserve full CR1 forecasts and
600-credit largest-reservation headroom, and fit remaining admission/deadline.
The main ledger carries actual calibration spending forward exactly once.
An affordable assertion or old budget receipt is not enough.

```bash
$PYTHON -B harness/feasibility.py --calibration .study/calibration-cost-evidence.json \
  --calibration-state .study/excluded-calibration/state.json \
  --out .study/feasibility-v5.json
```

The evidence is outcome-free, explicitly source-bound and subject to independent
review. No such calibration or numerical go has been obtained here.
Worst-case combined caps are **2902500 credits / 3941.25 agent-hours**, outside
the aggregate and the current 14-day sequential deadline. If unfeasible, halt
and amend before collection; do not reduce or replace n.

## Required exact-source review and freeze

Use the [v5 amendment checklist](protocol/prospective-v5-2026-11-01.md).
Do not edit earlier acceptance records, critiques, prior data or v4 tag/manifest.
Every new source/config/prompt/oracle/analysis change invalidates earlier
receipts. A new `protocol/freeze-v5.json` must name the exact source/tag,
input hash, accepted image/canary, authorized phase, dated genuine independent
review and owner approvals, privacy/access evidence and actual prospective OSF
amendment. A calibration-only freeze does not authorize the fixed main sample.
Main collection additionally requires exact-source full-sample feasibility.

### Result interpretation

Reports retain all runs/dispositions and observed/missing denominators.
Ruff/Lizard/jscpd, suppression/config counts and external C review annotations
are treatment fidelity, not independently demonstrated efficacy.
SDK API/dispatch durations and host/tool wall timing are latency observations;
provider-active/rate-limit waits remain unknown. CR1 binary power is not supplied
by the coverage calculation. F9/F10 conditional strata are selected after
treatment and cannot identify a causal repair effect.
