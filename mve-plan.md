<!-- markdownlint-disable-file -->
# MVE Plan: feature-consolidation-harness

Phase 5 output (HVE Core Experiment Designer). Status: **draft, awaiting owner confirmation**. Details live in context.md, hypotheses.md, vetting.md and experiment-design.md in this folder.

## Problem and context

Coding agents that add one feature after another appear to degrade software faster than human teams do, through compounding errors and more output than people can review. In the AMA case, a ten-day autonomous loop merged 183 pull requests while the owner lost the last usable increment. This MVE tests whether a harness that stops after every feature to review, refactor under tests and rewrite a one-page design note changes that outcome, and at what cost.

Decision informed: adopt the consolidation step in the delivery coordinator, propose it to HVE Core and teach it to partners (go); report the null result and test alternatives (no-go); or refine and rerun (adjust).

## Hypotheses (priority order)

| Rank | ID | Claim | Right when | Wrong when |
| --- | --- | --- | --- | --- |
| 1 | H1 | Consolidation preserves working software | End-state hidden pass rate at least 10 points higher in B, 95% interval lower bound above 0 | Whole interval below 5 points |
| 2 | H6 | Consolidated code absorbs an unplanned change better | Change-request success at least 20 points higher, or cost at least 25% lower at no lower success | Whole intervals rule out both gains |
| 3 | H2 | Errors compound without consolidation | Open regressions trend upward in A; at least 50% fewer in B at the end | Whole intervals rule out A's upward trend or 50% reduction |
| 4 | H3 | Internal quality decays without consolidation | Positive slopes in A on 3 of 4 measures; B's slope at most half | Intervals rule out the required slope pattern |
| 5 | H5 | Consolidation pays for itself | B total cost at most 125% of A; B cheaper per feature in the last third | Whole cost interval above 150%; late-saving interval at or below zero |
| 6 | H4 | Less to review and understand | B has at least 20% fewer non-test lines; reviewers at least as accurate in 20% less time | Whole size and time reduction intervals below 10% |
| 7 | H7 (optional) | The consolidation package beats review-only | B beats C by at least half the B-A gap | Intervals rule out the half-gap benefit |

All hypotheses and thresholds are provisional until the owner records approval and the dated frozen protocol version before the pilot (hypotheses.md). No approval or freeze is recorded yet. H1 is inconclusive for all other evaluable outcomes; for example, a 12-point gain with a 95% interval of [-2, 26] does not invalidate H1.

For each hypothesis, validation also requires the relevant 95% benefit interval to exclude zero in the beneficial direction. Invalidation requires whole intervals to rule out its minimum useful effect, with the joint and alternative criteria in hypotheses.md. An interval spanning zero without ruling out useful effects is inconclusive, not no-go. For H5 the effects are headroom below the 150% ceiling and late-feature savings, retaining 125% as the validation threshold. Pre-registration is pending: record the actual date and public URL before any run; this local plan is not a registration.

## Vetting summary

Viable MVE. Planned mitigations: confirmation bias (owner-approved thresholds to be frozen, hidden tests, blinded review, all runs reported), metric gaming (behavioural and changeability measures alongside metrics), test tampering (hidden suite outside the workspace, checksummed examples), small samples (report intervals for the fixed sample; any extension is separately exploratory). Partly a "solved problem" for human teams; the open question is the agentic acceleration and the per-feature agent remedy.

## Design summary

* Arms: A feature-only; B feature plus consolidation; C review-only comparison (optional). H7 compares complete packages, not refactoring alone: B also adds behaviour-pinning tests and architectural DESIGN.md, while C cannot change tests and writes issue-oriented REVIEW.md; later sessions read those different notes.
* Suites: S1 retrofit case workbench (AMA domain) and S2 library lending, ten interacting features each plus one held-out cross-cutting change request; visible example tests per feature, 10-20 hidden tests per feature.
* Procedure: fresh agent session per step; commit only when visible tests pass. A step with no green commit is reset and its example tests removed; the feature counts as missing in the hidden denominator. H1's end state is after the final post-feature step. CR success requires all CR hidden tests and no regression of a feature test that passed at that state.
* Budgets (proposed): feature step 30 minutes; consolidation 15 minutes; change request 45 minutes.
* Scale: pilot (1 run per arm), exploratory first pass (S1, A/B, 4 runs per arm, 8 features F1-F8, then scoped CR1), main (S1 and S2, 5 runs per arm, 10 features) if selected before any non-pilot run. First-pass CR1 covers regions in lists, visibility and handoffs; full CR1's ranking and export checks require F9-F10 and are reserved for the main study. Freeze both variants before the pilot. Pilot and first-pass data are excluded from main-study confirmatory inference; sample sizes and optional C are not extended based on results.
* First-pass budget: 64 feature, 32 consolidation and 8 change-request steps; 46 hours of agent time, or an idealised 11.5 hours with four parallel sessions, excluding measurement and scheduling overhead. `anc/protocol_checks.py` reproduces this and the exact two-sided rank-test floors: 0.100, 0.029 and 0.008 for three, four and five runs per arm. These floors are not a power analysis.
* Fairness: B has up to 50% more agent time per feature; C holds that extra time constant without refactoring. H5 compares costs directly.
* Analysis: suite as a fixed effect and run as a random intercept; bootstrap whole runs within suite and arm. One proprietary model and no open-weights baseline limit generalisation and replication.
* Timeline: about one week to the first-pass result; a second week for the main runs.

## Resources

* The owner's development VM and agent runtime with one pinned model.
* Coding-agent budget (tokens or premium requests): TODO(owner).
* Open-source measurement tools: pytest, lizard, jscpd, ruff, radon, coverage.
* Two or three human reviewers for the blinded comprehension task (about 30 minutes each).

## Next steps by outcome

* **Go** (H1 and H6 validated, H5 not invalidated): add the consolidation step to the coordinator; share prompts and results with HVE Core maintainers as a candidate "consolidate" phase or skill; teach it at partner sessions; report in the paper.
* **No-go** (H1 invalidated): report that the interval rules out the minimum useful H1 gain; next MVE tests human demo checkpoints and work-in-progress limits instead. Do not use no-go for an inconclusive result.
* **Adjust** (mixed or inconclusive, including H1): report the uncertainty without changing the original confirmatory sample or verdict. Any additional runs or changed sequence or budget require a separately recorded exploratory extension or a new predeclared study.

## Evaluation approach

Scripts compute all measures; the analysis script is frozen and dry-run on pilot data before the main runs; outcome.md records each hypothesis as validated, invalidated, mixed, inconclusive or not evaluable, with sample sizes, intervals, anomalies and the go, no-go or adjust decision. Execution conformance (RPI review) is judged separately from hypothesis outcomes.

## Owner decisions needed before execution

1. Accept, revise or reject each hypothesis and threshold (hypotheses.md); record approval and the dated frozen protocol version before the pilot.
2. Model, version and agent runtime to pin for all arms.
3. Budget ceiling for coding-agent consumption.
4. First pass only, or first pass plus main runs; include the review-only arm or not. Record scope and fixed sample sizes before any non-pilot run.
5. Reviewers for the blinded comprehension task.
6. Whether to replace S2 with a public benchmark if Research finds a suitable one.
