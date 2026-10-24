<!-- markdownlint-disable-file -->
# MVE Hypotheses: feature-consolidation-harness

Phase 2 output (HVE Core Experiment Designer). Hypotheses and thresholds are provisional; the owner accepts, revises or rejects them and records approval and the dated frozen protocol version before the pilot. No approval or freeze is recorded yet. Criteria changed after execution starts are recorded as divergence, never silently replaced.

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
* **Cumulative hidden pass rate** after step k: share of hidden acceptance tests for scheduled features 1..k that pass, including missing features in the denominator.
* **Regression**: a hidden test that passed after an earlier step and fails now.
* **End state**: after the last feature's post-feature step (a no-op in A), before the held-out change request. H1 uses this state, not the state before consolidation.
* **Missing feature**: a feature step that commits no green increment is reset by the runner; its example tests are removed, but its hidden tests still count.
* **Change-request success**: all its hidden tests pass and no feature test that passed at the end state fails afterwards.

The exploratory first pass uses S1, A and B, four runs per arm and eight features (F1-F8), plus a pre-frozen CR1 variant for available behaviour. Ranking and export checks need F9-F10 and are reserved for main-study CR1. The main study uses five runs per arm per suite and ten features; pilot and first-pass data are not pooled into it.

For all hypotheses, validation requires the stated estimate threshold and a 95% interval excluding zero in the beneficial direction. Invalidation requires whole intervals to rule out the stated minimum useful effect; other evaluable results, including intervals spanning zero without ruling out useful effects, are inconclusive. Compound criteria use the stated conjunction or alternative, not non-significance as proof of failure. H1's minimum is 5 points; H4's invalidation margin remains 10%. H5 uses headroom below its 150% ceiling and late-feature savings, retaining its 125% validation threshold.

## Objective 1: Working software as features accumulate (owner's factor 1, compounding errors)

**H1 (priority 1, primary).** I propose that a consolidation step after every feature preserves functional correctness as features accumulate. I will compare A and B using the cumulative hidden suite after every feature and post-feature step. H1 is validated when, at the end state, B's mean hidden pass rate is at least 10 percentage points higher and the 95% interval's lower bound is above zero. H1 is invalidated only when the whole interval is below 5 points. Other evaluable outcomes are inconclusive, including estimates between 5 and 10 points and intervals spanning zero without ruling out a useful gain. A 12-point gain with an interval of [-2, 26] is inconclusive, not invalidated, and routes to adjust, not no-go.

**H2 (priority 1).** I propose that regressions accumulate and persist in feature-only delivery. I will count open regressions and their survival after every step. Validation requires a positive trend in A (slope interval above zero), at least 50% fewer open regressions in B at the end state, and a reduction interval above zero. Invalidation requires the whole slope interval to rule out an upward trend in A, or the whole reduction interval to fall below 50%. Other evaluable outcomes are inconclusive.

Dependency: H1 can only show an effect if decay exists in arm A. H2 and H3 are checked in the pilot; if arm A shows no decay within the planned sequence, lengthen the sequence before the main runs (see the iteration plan).

## Objective 2: Internal quality and review load (owner's factor 2, unreviewable volume)

**H3 (priority 2).** I propose that internal quality degrades without consolidation. I will measure mean cyclomatic complexity, the share of functions above 10, duplicated lines and lint warnings per thousand lines. Validation requires positive slopes in A on at least three of four measures and B's slopes at most half of A's, with beneficial interaction intervals excluding zero. Invalidation requires intervals that rule out the required positive-slope and half-slope pattern, not merely non-significant slopes. Other evaluable outcomes are inconclusive.

**H4 (priority 2).** I propose that consolidation leaves less to review and understand. I will compare non-test lines, diff lines, documentation words and a timed, blinded comprehension task with two or three reviewers and five fixed questions. Validation requires at least 20% fewer non-test lines and at least 20% less comprehension time at no lower accuracy, with reduction intervals above zero. Invalidation requires whole reduction intervals below 10% for both size and time. Other evaluable outcomes are inconclusive.

## Objective 3: Cost and changeability (is it worth it?)

**H5 (priority 2).** I propose that consolidation pays for itself within the sequence. I will record tokens or premium requests and time for all steps. Validation requires B's total cost at most 125% of A's and lower implementation cost per feature in the last third, with intervals above zero for headroom below the 150% ceiling and late-feature savings. Invalidation requires B's whole cost interval above 150% of A's and its late-saving interval at or below zero. B has up to 50% extra agent time per feature; H5 compares costs directly. Other evaluable outcomes are inconclusive.

**H6 (priority 1).** I propose that consolidated code absorbs an unplanned change better. Each end state receives the same held-out request and budget. Success uses the definition above. Validation requires a success-rate gain of at least 20 points, or a cost saving of at least 25% at no lower success, with the relevant benefit interval above zero. Invalidation requires whole intervals to rule out both a 20-point gain and a 25% saving at no lower success. Other evaluable outcomes are inconclusive.

## Optional package comparison

**H7 (priority 3, optional).** I propose that the complete consolidation package beats review-only. C holds B's extra time constant without refactoring: it cannot change code or tests and writes REVIEW.md, while B may add behaviour-pinning tests and writes DESIGN.md. Validation requires B to beat C on H1 and H3 by at least half of the B-A difference, with benefit intervals above zero; invalidation requires intervals to rule out that half-gap benefit. If the B-A gap is not established, H7 is inconclusive or not evaluable. Later sessions read different notes, so this compares packages, not refactoring alone.

## Priority ranking and rationale

| Rank | Hypothesis | Why |
| --- | --- | --- |
| 1 | H1 | Directly answers the adoption decision: does the harness keep software working? |
| 2 | H6 | Tests changeability (Beck's "futures"), the property most at risk in feature-only delivery. |
| 3 | H2 | Tests the compounding-error mechanism behind the owner's factor 1. |
| 4 | H3 | Tests internal decay, which the harness targets directly. |
| 5 | H5 | Tells adopters whether the harness is affordable. |
| 6 | H4 | Tests the owner's factor 2; needs human reviewers, so it is costlier. |
| 7 | H7 | Compares the consolidation package with review-only; optional. |

## Owner decisions on proposed thresholds

| Item | Proposed | Owner decision |
| --- | --- | --- |
| H1 thresholds (10 / 5 points) | Proposed | TODO(owner): accept, revise or reject |
| H2 threshold (50% fewer open regressions) | Proposed | TODO(owner) |
| H3 threshold (slope at most half) | Proposed | TODO(owner) |
| H4 thresholds (20% fewer lines, 20% less time) | Proposed | TODO(owner) |
| H5 thresholds (125% / 150% cost) | Proposed | TODO(owner) |
| H6 thresholds (20 points / 25% cost) | Proposed | TODO(owner) |
| H7 review-only arm | Optional | TODO(owner): include or defer |
