<!-- markdownlint-disable-file -->
# MVE Plan: feature-consolidation-harness

Phase 5 output (HVE Core Experiment Designer). Status: **draft, awaiting owner confirmation**. Details live in context.md, hypotheses.md, vetting.md and experiment-design.md in this folder.

## Problem and context

Coding agents that add one feature after another appear to degrade software faster than human teams do, through compounding errors and more output than people can review. In the AMA case, a ten-day autonomous loop merged 183 pull requests while the owner lost the last usable increment. This MVE tests whether a harness that stops after every feature to review, refactor under tests and rewrite a one-page design note changes that outcome, and at what cost.

Decision informed: adopt the consolidation step in the delivery coordinator, propose it to HVE Core and teach it to partners (go); report the null result and test alternatives (no-go); or refine and rerun (adjust).

## Hypotheses (priority order)

| Rank | ID | Claim | Right when | Wrong when |
| --- | --- | --- | --- | --- |
| 1 | H1 | Consolidation preserves working software | Final cumulative hidden pass rate at least 10 points higher in B, interval excludes 0 | Difference below 5 points or interval includes 0 |
| 2 | H6 | Consolidated code absorbs an unplanned change better | Change-request success at least 20 points higher, or cost at least 25% lower | No difference |
| 3 | H2 | Errors compound without consolidation | Open regressions trend upward in A; at least 50% fewer in B at the end | No upward trend in A |
| 4 | H3 | Internal quality decays without consolidation | Positive slopes in A on 3 of 4 measures; B's slope at most half | No positive slope in A |
| 5 | H5 | Consolidation pays for itself | B total cost at most 125% of A; B cheaper per feature in the last third | B above 150% with no late advantage |
| 6 | H4 | Less to review and understand | B has at least 20% fewer non-test lines; reviewers at least as accurate in 20% less time | Differences below 10% |
| 7 | H7 (optional) | The gain comes from refactoring, not a second look | B beats placebo C by at least half the B-A gap | B and C alike |

All thresholds are proposals until the owner accepts them (hypotheses.md).

## Vetting summary

Viable MVE. Mitigated concerns: confirmation bias (precommitted thresholds, hidden tests, blinded review, all runs reported), metric gaming (behavioural and changeability measures alongside metrics), test tampering (hidden suite outside the workspace, checksummed examples), small samples (report intervals, add runs if inconclusive). Partly a "solved problem" for human teams; the open question is the agentic acceleration and the per-feature agent remedy.

## Design summary

* Arms: A feature-only; B feature plus consolidation; C review-only placebo (optional).
* Suites: S1 retrofit case workbench (AMA domain) and S2 library lending, ten interacting features each plus one held-out cross-cutting change request; visible example tests per feature, 10-20 hidden tests per feature.
* Procedure: fresh agent session per step; commit only when visible tests pass; cumulative hidden suite and metrics after every step; change request at the end.
* Budgets (proposed): feature step 30 minutes; consolidation 15 minutes; change request 45 minutes.
* Scale: pilot (1 run per arm), first pass (S1, 3 runs per arm, 8 features), main (S1 and S2, 5 runs per arm, 10 features) if budget allows.
* Timeline: about one week to the first-pass result; a second week for the main runs.

## Resources

* The owner's development VM and agent runtime with one pinned model.
* Coding-agent budget (tokens or premium requests): TODO(owner).
* Open-source measurement tools: pytest, lizard, jscpd, ruff, radon, coverage.
* Two or three human reviewers for the blinded comprehension task (about 30 minutes each).

## Next steps by outcome

* **Go** (H1 and H6 validated, H5 not invalidated): add the consolidation step to the coordinator; share prompts and results with HVE Core maintainers as a candidate "consolidate" phase or skill; teach it at partner sessions; report in the paper.
* **No-go** (H1 invalidated): report the null result in the paper; next MVE tests human demo checkpoints and work-in-progress limits instead.
* **Adjust** (mixed or inconclusive): apply the iteration plan (longer sequences, more runs, smaller consolidation budget), then rerun.

## Evaluation approach

Scripts compute all measures; the analysis script is frozen and dry-run on pilot data before the main runs; outcome.md records each hypothesis as validated, invalidated, mixed, inconclusive or not evaluable, with sample sizes, intervals, anomalies and the go, no-go or adjust decision. Execution conformance (RPI review) is judged separately from hypothesis outcomes.

## Owner decisions needed before execution

1. Accept, revise or reject each threshold (hypotheses.md).
2. Model, version and agent runtime to pin for all arms.
3. Budget ceiling for coding-agent consumption.
4. First pass only, or first pass plus main runs; include the placebo arm or not.
5. Reviewers for the blinded comprehension task.
6. Whether to replace S2 with a public benchmark if Research finds a suitable one.
