<!-- markdownlint-disable-file -->
# MVE Experiment Design: feature-consolidation-harness

Phase 4 output (HVE Core Experiment Designer). Experiment type: LLM / agentic software-engineering process, controlled comparison.

## 1. Approach in one paragraph

Give a coding agent the same sequence of feature requests, one at a time, under two conditions. In arm A it moves straight to the next feature. In arm B it must first stop and consolidate: review what it built, refactor under tests without changing behaviour, and rewrite a one-page design note. After every step, scripts the agent never sees measure whether everything delivered so far still works (hidden acceptance tests), how the internal quality of the code is evolving, how much there is to review, and what it cost. At the end, every code base receives the same unplanned cross-cutting change, to test how changeable it stayed.

## 2. Arms

| Arm | After each feature | Purpose |
| --- | --- | --- |
| A, feature-only (control) | Next feature starts immediately | Baseline of continuous feature accumulation |
| B, feature + consolidation (treatment) | Consolidation step, budget 50% of a feature step | Tests the harness |
| C, feature + review-only (optional placebo) | Read-only review with the same budget as B; writes REVIEW.md only | Separates refactoring from "a second look" (H7) |

Everything except the post-feature step is identical across arms: model and version, agent runtime, feature prompts, starting skeleton, tools, per-feature budget, machine.

## 3. Task suites

Two small, synthetic suites in Python 3.12, tested with pytest, each with ten features whose rules deliberately interact with earlier features (so later features must touch earlier code), plus one held-out change request.

### S1: Retrofit case workbench (from the AMA case domain)

| # | Feature | Interacts with |
| --- | --- | --- |
| F1 | Homes and retrofit cases: create, list, filter; import from CSV | none |
| F2 | Lifecycle (candidate, surveyed, designed, ready, installed, handed over) with valid transitions and history | F1 |
| F3 | Ownership and handoffs that change owner only when accepted | F1, F2 |
| F4 | Return to an earlier stage with a reason; reopen a handed-over case | F2, F3 |
| F5 | Safety hold: blocks forward transitions; only a building-safety role releases it | F2, F4 |
| F6 | Resident consent per planned measure; withdrawal pauses the case; install needs consent | F2, F5 |
| F7 | Appointments: offers versus confirmations; verified no-access counter; escalation after more than five; reopening resets the active counter, keeps history | F2, F4, F6 |
| F8 | Roles and field visibility: contractors never see vulnerability reasons or resident contacts, in any read or export | all reads |
| F9 | Deterministic priority ranking: versioned policy, reason codes, fixed tie-break; held cases surface first | F2, F5, F6, F8 |
| F10 | Append-only audit trail with hash-chain verification; CSV export honouring visibility and filters | all writes, F8 |
| CR1 (held out) | Regions: every home belongs to a region; users are scoped to regions; lists, ranking, exports and handoffs respect scope; cross-region handoff needs manager approval | cross-cutting |

### S2: Library lending (neutral domain)

| # | Feature | Interacts with |
| --- | --- | --- |
| F1 | Catalogue of titles and copies; search | none |
| F2 | Members and membership status | none |
| F3 | Loans with due dates and a per-member limit | F1, F2 |
| F4 | Returns, overdue detection and daily fines | F3 |
| F5 | Renewals with limits, refused when a title is reserved | F3, F6 later |
| F6 | Reservation queues; next member notified (event log) | F3, F5 |
| F7 | Membership tiers that change limits and fines | F2-F6 |
| F8 | Branches and inter-branch transfers | F1, F3, F6 |
| F9 | Closures and holidays that shift due dates and suspend fines | F3, F4, F8 |
| F10 | Reports (overdue, popular titles, fines) with staff-only access | all |
| CR2 (held out) | Digital loans: e-book licences with concurrent-use limits that interact with reservations, tiers, branches and reports | cross-cutting |

**Option for S2 (recommended for external validity):** replace the library suite with a subset of SlopCodeBench (Orlanski et al., 2026; MIT licence; github.com/SprocketLab/slop-code-bench). Its problems are already sequences of checkpoints in which an agent extends its own solution, with tests per checkpoint and published erosion and verbosity measures, which makes it a natural host for the consolidation step between checkpoints. Pick 6-10 problems with at least five checkpoints each. TODO(owner): decide between the library suite and SlopCodeBench.

Related design references: SWE-Maintain (Pan et al., 2026) shows the downstream cost of agent edits comes mainly from inherited test failures, which is why regressions (H2) are a primary measure; SWE-CI (Chen et al., 2026) replays real repository history and could host a later replication.

### Specification format (per feature)

* A short user story, the rules in plain language, and 3-5 **visible** example tests (`tests/examples/test_fNN_*.py`, read-only for the agent).
* 10-20 **hidden** acceptance tests per feature, kept outside the agent workspace, including interaction tests with earlier features. The cumulative hidden suite after step k contains the hidden tests of F1..Fk.
* Specifications and hidden tests are written and frozen before the pilot; a second person (or a second agent session reviewed by the owner) checks each hidden test against its specification.

### Starting skeleton (identical per suite)

`src/` package with an empty domain module; `tests/` with pytest configured; `Makefile` with `test`, `check` and `metrics` targets; ruff configuration; a README of at most 150 words; the `tcr` script (section 5). No design note in arm A; arm B creates and maintains `DESIGN.md`; arm C maintains `REVIEW.md`.

## 4. Procedure per run

1. Create a fresh git repository from the skeleton. Record model, runtime and tool versions.
2. For k = 1..N (N = 10; 8 in the first pass):
   1. Copy feature k's visible example tests into the workspace.
   2. **Feature step** (all arms): the runner tags the head `feature-start` (`git tag -f`), then starts a fresh agent session with the feature prompt (`harness/feature-step.prompt.md`). Budget: 30 minutes wall-clock (TODO(owner): confirm, plus a turn or token cap). The agent may commit only when all visible tests pass; uncommitted work at the end of the budget is discarded, so the step either delivers a green increment or nothing.
   3. **Measure** (scripts, outside the agent): tag the committed head `feature-end`, then run the cumulative hidden suite and the metrics in section 6 on the committed head.
   4. **Post-feature step**: arm A none; arm B consolidation session (`harness/consolidation-step.prompt.md`, 15 minutes); arm C review-only session (`harness/review-only-step.prompt.md`, 15 minutes).
   5. **Measure again** (arms B and C) on the new head.
3. **Change request**: fresh session with the held-out request, 45-minute budget, same commit rule; run its hidden tests plus the full cumulative suite.
4. Archive the repository, session logs, metrics and cost records with the run identifier.

Fresh sessions per step mirror the case's coordinator: context travels only through the repository.

## 5. The harness (consolidation step, arm B)

Consolidation is a bounded, behaviour-preserving step:

1. Run `make check`; read `reports/quality.md` (generated by the metrics script: functions above complexity 10, duplicated blocks, lint warnings, file sizes).
2. Review the last feature's diff and the hotspots against a fixed checklist: duplication; long or complex functions; unclear names; dead code; misplaced responsibilities; rules from one feature leaking into another; tests that check implementation rather than behaviour.
3. Change code only through `./tcr "<message>"`, which runs all tests and commits if they pass or reverts if they fail. Behaviour must not change.
4. Never modify or delete files in `tests/examples/`. New tests may be added to pin current behaviour before a refactoring.
5. Rewrite `DESIGN.md` in at most 300 words: the structure, where each rule lives, known debts. Replace, do not append.
6. Stop when the quality budget is met (no function above complexity 10, duplicated lines below 3%, zero warnings in the configured lint set) or the time budget is used.

`tcr` (test && commit || revert):

```bash
#!/usr/bin/env bash
# Usage: ./tcr "message"
if make test > /tmp/tcr.log 2>&1; then
  git add -A && git commit -q -m "tcr: ${1:-refactor}" && echo "TCR: committed"
else
  git reset -q --hard && git clean -qfd -e reports/ && echo "TCR: reverted, tests failed" && tail -n 20 /tmp/tcr.log
fi
```

## 6. Measures and instrumentation

| Measure | Hypotheses | How (indicative commands) |
| --- | --- | --- |
| Cumulative hidden pass rate; open regressions; regression survival | H1, H2 | `pytest <hidden-suite> --junitxml=...` against the committed head |
| Mean cyclomatic complexity per function; share of functions with complexity above 10 | H3 | `lizard src --csv` |
| Duplicated lines (%) | H3 | `jscpd src --min-tokens 50 --reporters json` |
| Lint warnings per 1,000 lines | H3 | `ruff check src --select E,F,W,C90,B,SIM --output-format json` (rule set frozen) |
| Maintainability index (secondary) | H3 | `radon mi -j src` |
| Non-test lines of code; test lines | H4 | `radon raw -j src` or `cloc` |
| Diff lines per step | H4 | `git diff --shortstat <prev> <head>` |
| Documentation words generated | H4 | word count of Markdown files written by the agent |
| Blinded comprehension: accuracy and time on five fixed questions | H4 | 2-3 reviewers, randomised, arm labels and agent files removed (S1 only) |
| Tokens or premium requests; wall-clock; agent turns | H5 | agent runtime usage logs (TODO(owner): confirm what the runtime reports) |
| Change-request success and cost | H6 | CR hidden tests plus cumulative suite; cost as above |
| Test integrity: visible test checksums; test and assertion counts | all | checked after every step; any tampering is recorded and the step marked |
| Coverage of visible tests (secondary) | context | `pytest --cov=src --cov-report=json` |

## 7. Controls against bias

Reporting follows the guidelines for empirical studies involving LLMs (Baltes et al., arXiv 2508.15503): record the exact model version, prompts, tool versions and full session logs; because code generation is non-deterministic even at temperature zero (Ouyang et al., TOSEM 2025), use repeated runs and report intervals.

* One pinned model and runtime for all arms; arms interleaved in a randomised run order on the same machine, so model drift and load affect all arms alike.
* Hidden tests and the metrics pipeline frozen before the pilot; the agent cannot read them.
* Pilot results are excluded from the confirmatory analysis.
* Blinded human review; analysis script written and dry-run on pilot data before the main runs.
* Every run is reported, including incomplete ones; deviations go to a divergence log.

## 8. Scope, sample and timeline

| Pass | Scope | Steps | When |
| --- | --- | --- | --- |
| Build | Suites S1 (and S2), hidden tests, skeleton, prompts, runner, metrics, analysis script | n/a | Days 1-3 |
| Pilot | S1, arms A and B, one run each, N = 10 | 20 feature + 10 consolidation steps | Day 4 |
| First pass (minimum viable) | S1, arms A and B, 3 runs each, N = 8, plus CR1 | 48 feature + 24 consolidation + 6 CR steps | Days 5-6 |
| Main (if budget allows) | S1 and S2, arms A and B (C optional), 5 runs each, N = 10, plus CRs | 200 feature + 100 consolidation + 20 CR steps | Week 2 |

Upper bound of agent time for the first pass, at the proposed budgets: about 35 hours, or roughly 9 hours with four parallel sessions. TODO(owner): set the token or premium-request ceiling after the pilot measures real consumption.

Out of scope: human checkpoints inside the loop, multiple models, browser user interfaces, cloud deployment, and running the full RPI workflow per feature (a possible replication once the primary result exists).

## 9. Analysis plan (fixed before the main runs)

* **H1**: difference in mean cumulative hidden pass rate after the final feature (B minus A) with a 95% bootstrap interval, resampling runs within suite. Supporting model: mixed-effects logistic regression of per-test pass on arm, feature index and their interaction, with random intercepts for suite and run.
* **H2, H3**: linear mixed models of each measure on arm, feature index and arm-by-index, random intercepts for suite and run; report slopes and interaction with intervals.
* **H5**: per-step cost on arm and feature index; cumulative cost curves; ratio of total cost B to A with a bootstrap interval.
* **H6**: success-rate difference with an exact or Bayesian beta-binomial interval (small n); cost ratio for successful attempts.
* **H4**: non-test lines (as H3); comprehension time and accuracy compared with rank-based tests and effect sizes.
* Outcome vocabulary per hypothesis (HVE): validated, invalidated, mixed, inconclusive or not evaluable. Decision: go (adopt the harness), no-go (report null and test alternatives) or adjust.

## 10. Iteration plan

* Arm A shows no decay in the pilot: lengthen the sequence to 15 features or increase feature interplay before the main runs.
* Results within thresholds but intervals overlap zero: add runs (up to 10 per arm) before deciding.
* Consolidation games metrics (for example trivial function splitting) without behavioural gains: report it as a Goodhart finding; add a human checkpoint arm in a follow-up.
* Consolidation cost exceeds 150% of a feature step on average: reduce its budget and rerun the pilot.

## 11. Threats to validity

Small samples and LLM variance; one model and runtime; synthetic suites written by the experimenter; complexity metrics as proxies for quality; possible test tampering; the experimenter's stake in the outcome. Mitigations are in sections 3, 6 and 7 and in vetting.md.

## 12. Execution with HVE RPI (after the owner confirms mve-plan.md)

* Plan: sequence suite authoring, hidden-test review, skeleton, harness prompts, runner, metrics and analysis script, without changing hypotheses or thresholds.
* Implement: build the disposable experiment assets.
* Review: check execution conformance only; hypothesis verdicts are decided afterwards in outcome.md against the precommitted criteria.
