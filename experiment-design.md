<!-- markdownlint-disable-file -->
# MVE Experiment Design: feature-consolidation-harness

Phase 4 output (HVE Core Experiment Designer). Experiment type: LLM / agentic software-engineering process, controlled comparison.

Status: proposed, awaiting recorded owner approval and freezing of the dated protocol version before the pilot. Sample sizes, study scope and optional arm C are frozen before any non-pilot run.

## 1. Approach in one paragraph

Give a coding agent the same sequence of feature requests, one at a time, under two conditions. In arm A it moves straight to the next feature. In arm B it must first stop and consolidate: review what it built, refactor under tests without changing behaviour, and rewrite a one-page design note. After every step, scripts the agent never sees measure whether everything delivered so far still works (hidden acceptance tests), how the internal quality of the code is evolving, how much there is to review, and what it cost. At the end, every code base receives the same unplanned cross-cutting change, to test how changeable it stayed.

## 2. Arms

| Arm | After each feature | Purpose |
| --- | --- | --- |
| A, feature-only (control) | Next feature starts immediately | Baseline of continuous feature accumulation |
| B, feature + consolidation (treatment) | Consolidation step, budget 50% of a feature step | Tests the harness |
| C, feature + review-only (optional comparison) | Read-only review with the same budget as B; writes REVIEW.md only | Compares the complete consolidation package with review-only (H7) |

Everything except the post-feature step is identical across arms: model and version, agent runtime, feature prompts, starting skeleton, tools, per-feature budget, machine.

Arm B has up to 50% more agent time per feature than A. Arm C holds that extra time constant without refactoring; H5 compares A and B's costs directly. A-B is not a time-matched comparison.

The B-C contrast does not isolate refactoring. B may add behaviour-pinning tests and writes architectural DESIGN.md; C cannot change code or tests and writes issue-oriented REVIEW.md. Later feature sessions read those different notes, so any H7 benefit belongs to the complete package, including tests and documentation.

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
* 10-20 **hidden** acceptance tests per feature, kept outside the agent workspace, including interaction tests with earlier features. The cumulative hidden suite after step k contains the hidden tests of F1..Fk, including any missing feature.
* Specifications and hidden tests are written and frozen before the pilot; a second person (or a second agent session reviewed by the owner) checks each hidden test against its specification.

### Starting skeleton (identical per suite)

`src/` package with an empty domain module; `tests/` with pytest configured; `Makefile` with `test`, `check` and `metrics` targets; ruff configuration; a README of at most 150 words; the `tcr` script (section 5). No design note in arm A; arm B creates and maintains `DESIGN.md`; arm C maintains `REVIEW.md`.

## 4. Procedure per run

1. Create a fresh git repository from the skeleton. Record model, runtime and tool versions.
2. For k = 1..N (N = 8 in the first pass; N = 10 in the pilot and main study):
   1. Copy feature k's visible example tests into the workspace.
  2. **Feature step** (all arms): the runner tags the head `feature-start` (`git tag -f`), then starts a fresh agent session with the feature prompt (`harness/feature-step.prompt.md`). Budget: 30 minutes wall-clock (TODO(owner): confirm, plus a turn or token cap). The agent may commit only when all visible tests pass. If it commits no green increment, the runner resets to the pre-step head, removes that feature's example tests and counts the feature as missing. Its hidden tests remain in the cumulative denominator; runner-owned removal is recorded separately from agent tampering.
   3. **Measure** (scripts, outside the agent): tag the committed head `feature-end`, then run the cumulative hidden suite and the metrics in section 6 on the committed head.
   4. **Post-feature step**: arm A none; arm B consolidation session (`harness/consolidation-step.prompt.md`, 15 minutes); arm C review-only session (`harness/review-only-step.prompt.md`, 15 minutes).
   5. **Measure again** (arms B and C) on the new head.
3. **End state**: after the last feature's post-feature step (a no-op in A), freeze the H1 measurement and the set of feature hidden tests that pass.
4. **Change request**: fresh session with the held-out request, 45-minute budget, same green-commit rule; run its hidden tests plus the full scheduled cumulative suite. Success requires all change-request hidden tests to pass and no feature test that passed at the end state to fail. The first pass uses F1-F8 and a pre-frozen CR1 variant covering regions in lists, field visibility and handoffs. Ranking and export checks require F9-F10 and belong only to full CR1 in the main study. The variant and its hidden tests must be frozen before the pilot; no post-result selection is allowed.
5. Archive the repository, session logs, metrics and cost records with the run identifier.

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
* Pilot and exploratory first-pass results are excluded from the main study's confirmatory analysis; each stage is reported separately.
* Blinded human review; analysis script written and dry-run on pilot data before the main runs.
* Sample sizes, first-pass-only versus first-pass-plus-main scope, and inclusion of C are recorded before any non-pilot run. No outcome-dependent additions to the confirmatory sample are permitted.
* Every run is reported, including incomplete ones; deviations go to a divergence log.

## 8. Scope, sample and timeline

| Pass | Scope | Steps | When |
| --- | --- | --- | --- |
| Build | Suites S1 (and S2), hidden tests, skeleton, prompts, runner, metrics, analysis script | n/a | Days 1-3 |
| Pilot | S1, arms A and B, one run each, N = 10 | 20 feature + 10 consolidation steps | Day 4 |
| First pass (minimum viable, exploratory) | S1, arms A and B, 4 runs each, N = 8, plus scoped CR1 | 64 feature + 32 consolidation + 8 CR steps | Days 5-6 |
| Main (if budget allows) | S1 and S2, arms A and B (C optional), 5 runs each, N = 10, plus CRs | 200 feature + 100 consolidation + 20 CR steps | Week 2 |

Upper bound of agent time for the first pass, at the proposed budgets: 46 hours (64 x 30 + 32 x 15 + 8 x 45 = 2,760 minutes), or an idealised 11.5 hours with four parallel sessions, excluding measurement and scheduling overhead. With three runs per arm the exact two-sided Mann-Whitney floor is 2/C(6,3) = 0.10, so p < 0.10 is unattainable; four runs reach 0.029 and five reach 0.008. These are attainability bounds, not a power analysis. Reproduce both calculations with `anc/protocol_checks.py` from the paper package. TODO(owner): set the token or premium-request ceiling after the pilot measures real consumption, and record the selected scope, sample sizes and inclusion of C before any non-pilot run. First-pass runs are not counted toward the five main-study runs per arm per suite.

Pre-registration is pending. Before any run, record the actual registration date and public URL, the approved thresholds, the scoped CR1 specification and the frozen protocol version. Do not infer registration from this local package or backdate it.

Out of scope: human checkpoints inside the loop, multiple models, browser user interfaces, cloud deployment, and running the full RPI workflow per feature (a possible replication once the primary result exists).

## 9. Proposed analysis plan (freeze before the main runs)

* **H1**: difference in mean cumulative hidden pass rate at the end state, after the last feature's post-feature step (B minus A), with a 95% bootstrap interval, resampling whole runs within suite and arm. Validated when the estimated gain is at least 10 percentage points and the interval's lower bound is above zero; invalidated only when the whole interval is below 5 points; otherwise inconclusive for evaluable data. A 12-point gain with an interval of [-2, 26] is inconclusive. Supporting model: mixed-effects logistic regression of per-test pass on arm, feature index and their interaction, suite as a fixed effect and run as a random intercept. Only two suites are planned, so suite is not a random effect.
* **H2, H3**: linear mixed models of each measure on arm, feature index and arm-by-index, suite as a fixed effect and run as a random intercept; report slopes and interaction with intervals.
* **H5**: per-step cost on arm and feature index; cumulative cost curves; ratio of total cost B to A with a bootstrap interval.
* **H6**: success-rate difference with a 95% exact or Bayesian beta-binomial interval (small n); cost ratio for successful attempts, reporting all failed attempts separately. Freeze the interval method before the pilot. Success means all CR tests pass with no loss of a feature test that passed at the end state.
* **H4**: non-test lines (as H3); comprehension time and accuracy compared with rank-based tests and effect sizes.
* Across hypotheses, validate only when the estimate meets its threshold and its 95% benefit interval excludes zero in the beneficial direction. Invalidate only when whole intervals rule out the minimum useful effect in hypotheses.md, respecting joint and alternative criteria. For H5 the beneficial effects are headroom below the 150% ceiling and late-feature savings, with the 125% validation threshold retained. Non-significance or an interval spanning zero without ruling out a useful effect is inconclusive, not invalidated. Small samples can leave the result inconclusive; the rank-test floor is not a power guarantee.
* Outcome vocabulary per hypothesis (HVE): validated, invalidated, mixed (component findings differ), inconclusive or not evaluable. Mixed component findings do not override the interval rule. Decision: go (adopt the harness), no-go (useful H1 gain ruled out) or adjust.
* H1 invalidation routes to no-go; inconclusive H1 routes to adjust, without enlarging the confirmatory sample. Go requires H1 and H6 validated and H5 not invalidated, as specified in mve-plan.md.
* Main-study inference uses only its predeclared fixed sample (five runs per arm per suite), not pilot, first-pass or later extension runs. Report any exploratory extension separately, without pooling it into the original confirmatory estimates or changing their verdict.

## 10. Iteration plan

* Arm A shows no decay in the pilot: lengthen the sequence to 15 features or increase feature interplay, record a revised protocol and rerun the pilot before freezing the non-pilot design.
* Intervals overlap zero without meeting the invalidation criterion: report the outcome as inconclusive. Any additional runs form a separately labelled exploratory extension with its own recorded design, not an enlargement of the original confirmatory sample.
* Consolidation games metrics (for example trivial function splitting) without behavioural gains: report it as a Goodhart finding; add a human checkpoint arm in a follow-up.
* Consolidation cost exceeds 150% of a feature step on average: reduce its budget and rerun the pilot.

## 11. Threats to validity

Small samples and LLM variance; one proprietary model and runtime, with no open-weights baseline; synthetic suites written by the experimenter; complexity metrics as proxies for quality; possible test tampering; the experimenter's stake in the outcome. Provider-side changes can limit replication even with an exposed version pinned (Baltes et al., arXiv 2508.15503). Mitigations are in sections 3, 6 and 7 and in vetting.md.

## 12. Execution with HVE RPI (after the owner confirms mve-plan.md)

* Plan: sequence suite authoring, hidden-test review, skeleton, harness prompts, runner, metrics and analysis script, without changing hypotheses or thresholds.
* Implement: build the disposable experiment assets.
* Review: check execution conformance only; hypothesis verdicts are decided afterwards in outcome.md against the precommitted criteria.
