<!-- markdownlint-disable-file -->
# MVE Vetting: feature-consolidation-harness

Phase 3 output (HVE Core Experiment Designer). Verdict: **viable as an MVE**, with two concerns to mitigate (confirmation bias and scope creep).

## Vetting criteria

| Criterion | Assessment | Notes |
| --- | --- | --- |
| Does the MVE make business sense? | Pass | A real decision depends on it: whether to add a consolidation gate to the delivery coordinator, teach it in partner HVE trainings and propose it to HVE Core. The owner sponsors the work and needs the result for the capstone paper. |
| Is there a crisp problem statement? | Pass | Does a per-feature consolidation step change quality, regressions, changeability and cost when agents add features one after another? See context.md. |
| Has Responsible AI been considered? | Pass, with notes | Synthetic data only; no personal data. Reliability: results come from small samples and one model, so the paper must not over-generalise. Transparency: publish protocol, prompts, suites, metrics and raw results. Accountability: the owner acts on results. Cost and energy: bounded by a budget ceiling. |
| Are next steps clear? | Pass | Validated: add the consolidation step to the coordinator, propose a "consolidate" phase or skill to HVE Core maintainers, teach it, report in the paper. Invalidated: report the null result, then test the alternatives the experience report suggests (human demo checkpoints, smaller batches, work-in-progress limits). Mixed: adjust per the iteration plan. |

## Red flag check

| Red flag | Present? | Assessment and mitigation |
| --- | --- | --- |
| Demos and prototypes | No | The output is a measured comparison, not a showcase. |
| Skipping ahead | No | The harness is tested before it becomes a coordinator rule. |
| Solved problems | No | Feature-driven decay is well established for human teams, and several 2025-2026 studies suggest agents accelerate it (context.md, A1-A2). Research found no study that tests a consolidation step interleaved between agent feature steps; SlopCodeBench shows quality instructions alone do not change the degradation rate. Keep the hypotheses focused on that gap. |
| Mini-MVP | Risk | Building a polished harness product would turn this into an MVP. Mitigation: the harness is a prompt, a TCR wrapper and a metrics script; experiment code is disposable. |
| Low commitment or impact | No | Paper deadline and coordinator decision depend on it. |
| Customer lacks follow-through capacity | No | The owner controls the coordinator and the paper. |
| No next steps | No | See above. |
| No end users | Low risk | The "users" are engineers reviewing agent output. H4 uses two or three human reviewers; recruit them before the main runs. |
| Production code expectations | No | Suites and harness are disposable experiment assets. |
| Show without teach | Not applicable | Not a partner engagement. Optional: a partner engineer replicates one arm. |

## Concerns raised

1. **Confirmation bias.** The motivation is to "prove" a theory the owner already holds. Mitigations: thresholds fixed before the pilot; hidden tests and metrics computed by scripts; blinded human review (arm labels removed, tracking files stripped); all runs reported, including failed and null ones; deviations logged.
2. **Metric gaming (Goodhart).** A consolidation step judged by complexity metrics may split functions without improving design. Mitigations: several metrics, hidden behavioural tests, the held-out change request (H6) and blinded comprehension (H4), none of which can be satisfied by cosmetic refactoring.
3. **Test tampering.** Agents may delete or weaken tests to make them pass. Mitigations: hidden tests live outside the agent workspace; visible example tests are checksummed and read-only; test and assertion counts are tracked per step.
4. **Scale.** LLM runs vary widely. Five runs per arm per suite is an MVE-sized sample: report effect sizes with intervals and treat the result as preliminary unless intervals are clear.

Disposition: proceed to Phase 4 with these mitigations built into the design.
