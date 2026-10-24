<!-- markdownlint-disable-file -->
# MVE Hypotheses: feature-consolidation-harness

Phase 2 output (HVE Core Experiment Designer). Thresholds are proposals set before any run; the owner accepts, revises or rejects each one before execution. Criteria changed after execution starts are recorded as divergence, never silently replaced.

## Project goal

Find out whether interleaving every agent-delivered feature with a consolidation step (stop, review, refactor under tests, refresh a one-page design note) keeps agent-built software working, understandable and changeable, compared with adding features continuously, and what it costs.

## Initiative-level assumptions

* Both arms use the same model, agent runtime, instructions, starting skeleton, feature specifications and per-feature budget. The only manipulated variable is the consolidation step.
* Hidden acceptance tests are never visible to the agent.
* Synthetic domains and data only.

## Terms

* **Run**: one fresh, independent delivery of a whole feature sequence by one arm.
* **Feature step**: the agent implements one feature from its specification until its visible examples pass or the step budget is exhausted.
* **Consolidation step** (treatment only): review, behaviour-preserving refactoring under test && commit || revert (TCR), and a rewritten one-page design note, within a fixed budget.
* **Cumulative hidden pass rate** after step k: share of hidden acceptance tests for features 1..k that pass.
* **Regression**: a hidden test that passed after an earlier step and fails now.

## Objective 1: Working software as features accumulate (owner's factor 1, compounding errors)

**H1 (priority 1, primary).** We believe that a consolidation step after every feature preserves functional correctness as features accumulate. We will test this by delivering the same feature sequence in a feature-only arm (A) and a feature-plus-consolidation arm (B), five independent runs per arm per suite, and running the cumulative hidden acceptance suite after every feature step. We will know we are right when, after the final feature, arm B's mean cumulative hidden pass rate is at least 10 percentage points higher than arm A's and the 95% confidence interval of the difference excludes zero; we are wrong when the difference is below 5 points or its interval includes zero.

**H2 (priority 1).** We believe that in feature-only delivery, errors compound: regressions accumulate and persist. We will test this by counting open regressions and the number of steps each one survives, after every feature step, in both arms. We will know we are right when arm A's open regressions show a positive trend over the feature index (slope interval above zero) and arm B has at least 50% fewer open regressions after the final feature; we are wrong when arm A shows no positive trend.

Dependency: H1 can only show an effect if decay exists in arm A. H2 and H3 are checked in the pilot; if arm A shows no decay within the planned sequence, lengthen the sequence before the main runs (see the iteration plan).

## Objective 2: Internal quality and review load (owner's factor 2, unreviewable volume)

**H3 (priority 2).** We believe that feature-only delivery degrades internal quality faster than the code grows. We will test this by measuring, after every step, mean cyclomatic complexity per function, the share of functions above complexity 10, the share of duplicated lines and linter warnings per thousand lines. We will know we are right when arm A's slope over the feature index is positive for at least three of the four measures and arm B's slope is at most half of arm A's (arm-by-index interaction interval excludes zero); we are wrong when arm A shows no positive slope.

**H4 (priority 2).** We believe the consolidation arm leaves less for a human to review and understand. We will test this by comparing non-test lines of code, diff lines per feature, documentation words generated, and a blinded comprehension task in which two or three reviewers answer five fixed questions about each final code base, timed. We will know we are right when arm B has at least 20% fewer non-test lines after the final feature and reviewers answer at least as accurately in at least 20% less time; we are wrong when neither size nor comprehension time differs by more than 10%.

## Objective 3: Cost and changeability (is it worth it?)

**H5 (priority 2).** We believe consolidation pays for itself within the sequence. We will test this by recording tokens or premium requests and wall-clock time for every feature step and every consolidation step. We will know we are right when arm B's total cost to reach the final feature is at most 125% of arm A's and arm B's implementation cost per feature over the last third of the sequence is lower than arm A's; we are wrong when arm B's total cost exceeds 150% of arm A's with no late-sequence advantage.

**H6 (priority 1).** We believe consolidated code bases absorb an unplanned cross-cutting change better. We will test this by giving every final code base the same held-out change request with the same budget and running its hidden tests. We will know we are right when arm B's success rate is at least 20 percentage points higher, or its cost at least 25% lower at no lower success; we are wrong when neither difference appears.

## Optional attribution check

**H7 (priority 3, runs only if budget allows).** We believe the benefit comes from refactoring rather than from a second look. We will test this with a placebo arm (C) whose post-feature step has the same budget but is read-only: the agent reviews and writes notes but cannot change code. We will know we are right when arm B outperforms arm C on H1 and H3 by at least half of the B-A difference; we are wrong when arms B and C perform alike.

## Priority ranking and rationale

| Rank | Hypothesis | Why |
| --- | --- | --- |
| 1 | H1 | Directly answers the adoption decision: does the harness keep software working? |
| 2 | H6 | Tests changeability (Beck's "futures"), the property most at risk in feature-only delivery. |
| 3 | H2 | Tests the compounding-error mechanism behind the owner's factor 1. |
| 4 | H3 | Tests internal decay, which the harness targets directly. |
| 5 | H5 | Tells adopters whether the harness is affordable. |
| 6 | H4 | Tests the owner's factor 2; needs human reviewers, so it is costlier. |
| 7 | H7 | Strengthens attribution; optional. |

## Owner decisions on proposed thresholds

| Item | Proposed | Owner decision |
| --- | --- | --- |
| H1 thresholds (10 / 5 points) | Proposed | TODO(owner): accept, revise or reject |
| H2 threshold (50% fewer open regressions) | Proposed | TODO(owner) |
| H3 threshold (slope at most half) | Proposed | TODO(owner) |
| H4 thresholds (20% fewer lines, 20% less time) | Proposed | TODO(owner) |
| H5 thresholds (125% / 150% cost) | Proposed | TODO(owner) |
| H6 thresholds (20 points / 25% cost) | Proposed | TODO(owner) |
| H7 placebo arm | Optional | TODO(owner): include or defer |
