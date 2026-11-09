---
title: Blind post-experiment S1 judging
description: Researcher instructions and paper-ready methods for supplementary functional-retention and API-usability evaluation
ms.date: 2026-11-09
---

## Purpose and status

This is a separate, post-experiment evaluation. It does not change experiment
agents, prompts, budgets, frozen protocols, hidden tests or collected results.
Development agents are not rerun and judges cannot repair their output.

The researcher collects executable evidence from archived S1 repositories,
then submits anonymized evidence packets to a separately configured AI judge.
The arm and development-model mapping stays private until reporting.

This new assessment is **supplementary and exploratory**. Designing or freezing
it after collection does not make it preregistered. Do not substitute its results
for the original H1/H2/H6 endpoints, and do not claim a confirmatory verdict.
The active experiment protocol remains [pilot-estimation.md](../protocol/pilot-estimation.md).

## What is measured

| Measure | Definition | Interpretation |
| --- | --- | --- |
| Final workflow fulfilment | Executed scenario outcomes at P10 and, separately, after CR1 | Which exercised requirements work in the inherited product |
| Observed earlier-capability loss | A scenario passed at an earlier eligible end-of-cycle checkpoint but fails at the selected endpoint | A witnessed endpoint regression, not merely an unimplemented feature |
| Retention density | Witnessed endpoint losses divided by scenarios witnessed passing earlier | Undefined when the risk set is empty or contains unavailable endpoint outcomes |
| Functional completeness | AI rating of fulfilment of the supplied requirements within each exercised workflow | Not exhaustive feature conformance |
| Workflow coherence | AI rating of consistency of state, reads and interacting operations | Broader interpretation of execution evidence |
| Error recovery | AI rating of rejection, state preservation and subsequent progress | Null when the evidence cannot establish this dimension |
| API usability | AI rating of whether a caller using the specified API can complete the demonstrated task and interpret its results/errors | Not UI usability, human satisfaction or a user study |

The four AI dimensions are rated separately on an ordinal 0-4 scale:
0 absent/unusable; 1 major blocking failures; 2 material gaps; 3 working with
minor evidenced limitations; 4 coherent fulfilment of the exercised requirements.
There is no composite "software quality" score. Scores need citations to final
execution observations and a rationale. Unobserved dimensions are null, not zero.

### Workflow panel

The fixed panel in [scenarios.py](scenarios.py) contains:

1. F1 registration, combined filtering and atomic import with recovery.
2. F2 lifecycle, invalid transitions, history and stage counts.
3. F3 handoff, decline and acceptance with ownership preservation.
4. F4 rework and reopening without losing ownership or reasons.
5. F5 safety holds, permitted rework and role-controlled release.
6. F6 consent withdrawal, reinstatement and safety precedence.
7. F7 offered/confirmed appointments, verified escalation and reopening reset.
8. F8 live contractor views, protected fields and read-only enforcement.
9. F9 stable priority ranking with interacting hold/consent/vulnerability reasons.
10. F10 audit verification, tamper detection and visibility-preserving export.
11. An F1-F10 delivery/reopening journey with consent, handoff, appointments and audit.
12. CR1 region-scoped reads, rankings, exports and approved cross-region handoff.

Scenarios use synthetic data and the existing public specification. They are
not generated from study results. Each starts with a fresh in-memory Workbench.
The panel is intentionally limited: for example, the ranking workflow does not
exercise every possible ranking combination. The original hidden tests remain
the more extensive deterministic conformance instrument.

Scenario feature labels identify dependencies, **not causal attribution**. A
workflow depending on F1/F2/F6 failing does not prove which implementation broke.
This system measures a fixed panel of capabilities, not a percentage of all
possible functionality or a statistically sampled population of user tasks.

### Snapshots and temporal interpretation

P_k means the end of cycle k: after the feature in A/D, consolidation in B,
review in C, and repair in E. P10 includes the last applicable intervention.
The tool selects each snapshot by its recorded measurement HEAD, not the
current checkout, a movable branch name, or the last successfully observed step.

The panel is replayed at P1-P10, with each scenario becoming eligible only when
its dependencies have been scheduled. The CR1 panel is also run after CR1.
No candidate code runs on the host. Replaying a snapshot is evaluation, not
repeating or repairing a development trajectory.

For each endpoint/scenario, classification is one of:

* `retained`: an earlier eligible checkpoint passed and the endpoint passes.
* `observed_loss`: an earlier eligible checkpoint passed and the endpoint fails.
* `passing_without_prior_witness`: the endpoint passes but no earlier pass was observed.
* `never_observed_pass`: all earlier eligible observations are available, but none passed.
* `no_prior_pass_observed_incomplete_history`: no pass was witnessed and some earlier evidence is unavailable.
* `unavailable`: the scheduled endpoint itself is unavailable.

An F10-only scenario has no prior eligible P checkpoint before P10, so its
P10 failure is not classified as degradation. At CR1, its P10 result can supply
a baseline. A witnessed pass followed by a failure supports endpoint loss even
if some intervening observations are missing; it does not identify onset time.
This tool does not estimate recurrence, episode duration or the original H2
hidden-contract loss estimand. A final pass may conceal an earlier recovered
regression; no claim of uninterrupted retention is made.

## Researcher procedure

### Prerequisites and separation

Use a separate checkout of the judging revision and a **stopped, local archive**
of the study directory, containing `state.json` and `runs/<run_id>/` with
repositories and `steps.jsonl`. Work from a copy made after collection, not the
live VM's study directory. Do not pull this branch into the running experiment.
Copying the archive is an operator task; this tool never connects to a VM.

Python 3.11+ and Git are required. Scenario execution reuses the existing
[SandboxBroker](../harness/isolation.py) with an already qualified, compatible
isolated evaluator image. Supply its inspected immutable `sha256:...` content
ID. The tool does not build, pull, upgrade or delete images. It creates and
cleans up only its own local evaluation containers. It does not alter study
repositories, tags, working files or state.

The Copilot adapter uses the existing pinned SDK 1.0.28 / CLI 1.0.105 transport,
Node 24+, and the researcher's signed-in host identity. It does not copy
credentials into candidate containers. If dependencies are missing, install
them in the separate checkout using the existing setup instructions; the tool
never installs or updates the experiment runtime automatically.

### Freeze and prepare

Before inspecting candidate results, record the judging source commit, scenario
and rubric versions, selected judge model(s), adapter revision(s), repetitions,
credit budget, missingness policy, and human calibration procedure. Disclose
whether the researcher or paper authors had already seen experiment outcomes.
The bundle records preparation time and source-file hashes, but these are
local provenance, not independently verified timestamps or preregistration.
Hashes cover the judging code and the shared isolation/transport helpers.
Changing those files invalidates resume rather than silently changing the instrument.

```bash
python3 judging/judge.py prepare \
  --study-dir /archive/completed-study \
  --output /private/judging-batch \
  --image sha256:REPLACE_WITH_INSPECTED_LOCAL_IMAGE_ID
```

Only ten-feature S1 allocations are supported. The complete allocated cell list
is retained, including failures and unavailable endpoints. A running study is
refused. A stopped incomplete archive requires `--allow-incomplete`; it does
not permit replacing missing P10/CR1 with an earlier checkpoint. Stub/reference
validation uses `--diagnostic`, and its reports are marked not study evidence.
Declared development-model rosters and model/arm replicate frames are checked.
An archive missing an allocated model or cell is not accepted as a smaller study.

Preparation can take time: it evaluates up to eleven snapshots per trajectory.
No AI credits are spent by `prepare`. Collection/infrastructure exceptions
produce explicit unavailable checkpoints and private warnings, not invented
zero scores. Inspect these warnings before authorizing judging.
Committed regular runtime files, including non-source assets, are replayed in
the local sandbox without Git metadata or checkout filters. Removing such assets
could create artificial failures. No files or treatment notes from that sandbox
are directly included in judge packets.

### Run the blinded judge

Copy [config.example.json](config.example.json) to a private configuration,
choose an entitled model ID, and set a separately approved budget. Three fresh
sessions per specimen are the example, not a scientific reliability guarantee.
You may configure multiple independent judge models with unique IDs.
Prefer judges independent of the development models where practical; disclose
any overlap and possible model-family preference. No independence is assumed.

```bash
python3 judging/judge.py run \
  --output /private/judging-batch \
  --config /private/judge-config.json \
  --authorize-paid-judging
```

This explicit flag authorizes the selected adapters and their model calls,
including transmission of the blinded evidence to the approved provider.
The flag does not authorize running development agents or changing the VM.
Keep API keys out of config/command arguments; use private environment or the
approved authentication mechanism.

For N complete trajectories with CR1, J judge configurations and R repetitions,
the maximum scheduled judge sessions are **2 x N x J x R**. Entirely unavailable
specimens do not trigger calls. Each call reserves `per_call_credits` before
startup; new admission stops when it would exceed `ceiling_credits`.
These are separate judging costs, not experimental treatment costs. Copilot's
session limit is soft and may overshoot: this is not a hard provider spending cap.

Run the same command to resume completed judgments. Configurations, packets and
requests are hash-bound. Pending, failed, invalid, interrupted or overspent calls
block further admission; the tool does not automatically retry or silently
replace a rating. Preserve the ledger, reconcile charges privately and document
an approved recovery/new assessment rather than manually clearing reservations.
Do not change model/rubric after seeing scores and call it the same assessment.

### Report and handoff

```bash
python3 judging/judge.py report --output /private/judging-batch
```

The outputs are `report.json`, `report.csv` and `report.md` in the new judging
directory. They do **not** overwrite the experiment reports. CSV includes
per-scenario, per-dimension means/ranges, available rating counts, final outcomes
and retention labels, linked back to development arm/model only at reporting.
JSON includes every allocated specimen, unavailable-checkpoint warnings and
descriptive contrasts, plus known judging costs and unknown-charge reservations.
Keep raw evidence, mappings and paid-call records private.
Review and sanitize any report before publication; publication is not automatic.

Each scenario's mean requires all scheduled repeat/judge ratings for that
dimension. A run-level mean is descriptive over its available scenario means;
its available/scheduled counts and completeness flag are retained. Ordinal
averaging is a pragmatic descriptive summary, not a calibrated interval scale.
The tool reports rating ranges rather than claiming inter-rater reliability.

Arm differences require complete run-level scores across the full allocated
frame for both arms in every development model, otherwise they are unavailable.
They equally weight within-model differences, so a model with more observed data
does not dominate. B-D is the equal-budget package comparison; B-A, B-C and E-B
are secondary descriptive comparisons. B-A is not time/budget matched. Ratings,
features and snapshots are not independent experimental replicates.
No bootstrap intervals, hypothesis tests or formal verdicts are produced here.

## Blinding and evidence controls

Judges receive only the specimen packet, requirements, rubric and response
shape through stdin. Packet IDs are random; submission order is shuffled.
No development arm/model, original run ID, commit SHA, source tree, DESIGN/REVIEW
notes, transcript, usage log or private mapping is sent to the judge.
Only the command adapter gets its own judge model/version configuration.

The Copilot adapter disables configuration discovery, custom tools, built-in
and MCP tools, infinite sessions and experimental mode. It verifies an empty
tool catalog and fails closed on tool execution, unexpected discovery/routing,
incomplete accounting or mismatched runtime identity. It reuses the existing
guarded host transport. Returned evidence strings are data, not instructions.

Blinding is not perfect: performance patterns or returned product values may
suggest a model/treatment. Private warnings and inference risks must be reported.
The researcher preparing/unblinding data is not automatically a blinded reviewer.
In-process scenario instrumentation is not proof against deliberately malicious
Python tampering. The existing supervisor/container protects the host, but this
is an ordinary software-behaviour assessment, not an adversarial proof of oracle
integrity. Human spot checks remain important.

## Generic command adapter contract

Each configured command is an argv array, never a shell string. `{root}` expands
to this checkout. The adapter is trusted researcher infrastructure and must not
inspect private mappings, repair software or run arbitrary candidate commands.
Its own model access, credential handling and accounting are its responsibility.

Read one request JSON object from stdin. Return one object on stdout:

```json
{
  "judge_id": "configured-id",
  "judge_version": "configured-version",
  "model": "configured-model",
  "usage": {"credits_complete": true, "totalNanoAiu": 100000000},
  "verdict": {
    "scenarios": [
      {
        "scenario_id": "registration",
        "scores": {
          "functional_completeness": 3,
          "workflow_coherence": 3,
          "error_recovery": 3,
          "api_usability": 3
        },
        "evidence_ids": ["registration:1"],
        "rationale": "Explain the rating using the cited final evidence."
      }
    ]
  }
}
```

The example row is illustrative; return **every requested scenario exactly once
in request order**. Ratings must be integers 0-4 or null; booleans/floats are
rejected. Cite only supplied final observations or `<scenario>:error` for a
recorded uncaught candidate error. Unavailable scenarios need all-null scores
and no citations. A perfect functional-completeness score is rejected when the
executed workflow demonstrates a failure. Metadata/accounting must come from the trusted adapter, not
from the model's self-report. One credit is 1,000,000,000 nano-AIU.
Non-Copilot adapters must supply verified equivalent credit accounting; there
is no silent conversion from tokens, seconds or currency.

## Validation and human calibration

Offline tests do not call a model or spend credits:

```bash
python3 -m pytest -q judging/tests
node --test judging/copilot-judge.test.mjs
```

To additionally exercise reference snapshots through the local isolated
evaluator, set `JUDGING_TEST_IMAGE` to a compatible local image's immutable ID:

```bash
JUDGING_TEST_IMAGE=sha256:YOUR_LOCAL_IMAGE_ID \
  python3 -m pytest -q judging/tests
```

This starts only local test-owned containers, never a VM/experiment session.
The integration uses trusted reference fixtures and labels its output diagnostic.
Passing these tests validates the pipeline, **not the judge model's accuracy**.

Before interpreting real ratings, arrange a blinded human-reviewed calibration
sample, including successful, incomplete and regressed workflows. Record sample
selection before scoring, compare humans with each judge, inspect disagreements,
and record who reviewed what and when. This software does not certify that
calibration happened. Do not tune on study outcomes and present that tuning
as prospective measurement. Human review and any paid judge smoke require
separate operator action; no human attestations are generated.

## Paper-ready methods text

> We added a supplementary exploratory post-collection assessment of the
> software produced by each allocated S1 trajectory. A fixed specification-led
> panel of API workflows was replayed against archived, recorded end-of-cycle
> snapshots in a read-only isolated evaluator, without rerunning development
> agents or modifying their repositories. Scenarios became eligible when all
> their dependencies were scheduled. The primary end-of-development snapshot
> was P10, after the applicable treatment post-step; post-CR1 was assessed
> separately. Endpoint failures were classified as witnessed capability loss
> only when the same scenario had passed at an earlier eligible checkpoint.
> Never-observed passes and unavailable measurements were reported separately.
> Anonymized evidence packets excluded development-arm/model labels, source
> files, treatment notes and logs. Separately configured AI judges rated
> functional completeness, workflow coherence, error recovery and API usability
> on distinct 0-4 ordinal scales, with execution citations and explicit
> abstention for unsupported dimensions. Fresh repeated sessions supplied
> descriptive rating means and ranges. Complete-frame arm differences equally
> weighted within-development-model differences; incomplete comparisons were
> unavailable rather than estimated from complete survivors. These measures
> describe the exercised capabilities and AI-rated API usability, not exhaustive
> conformance, real-user usability or confirmatory causal decay control.

The writing agent must fill in the actual source/rubric/scenario hashes,
judge runtime/model versions, repetitions, evaluated/missing counts, costs,
data-exposure history and human-calibration record from the completed assessment.
Do not say the assessment was run, calibrated, independently reviewed or
preregistered merely because this tool and methods text exist.
