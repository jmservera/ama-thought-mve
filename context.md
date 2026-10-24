<!-- markdownlint-disable-file -->
# MVE Context: feature-consolidation-harness

Session date: 2026-10-24. Method: HVE Core Experiment Designer (Minimum Viable Experiment), Phase 1 output.
Status: draft for owner review. The owner keeps authority over budget, model, thresholds and scope.

## Problem statement

When coding agents deliver a backlog by adding one feature after another, the code base and its documentation grow faster than anyone can review them, and quality appears to decay faster than in human-only development. In the AMA Case Study 48 repository, a week-long autonomous delivery loop merged 183 pull requests (15-24 Oct 2026) while the owner lost the last usable increment of the product.

The owner's theory:

* Software that only accumulates features, without deliberate consolidation, decays in quality and becomes slower and costlier to change. This is long established for human teams.
* Agentic development runs the same decay faster, for two reasons:
  1. **Compounding errors.** Each step builds on the agent's previous output, including its misreadings of intent and unneeded complexity (Beck's "genie" grants the wish, not the want).
  2. **Unreviewable volume.** Agents produce more code and documentation than people have the time or patience to review and test, so defects and complexity escape.
* A harness that stops after every feature to review, refactor and improve before the next feature (Beck's alternation of "features" and "futures") should slow or reverse that decay.

The experiment tests whether the harness changes the outcome, and at what cost. It is not designed to "prove" the theory: a null or negative result is a valid, publishable outcome.

## Decision this experiment informs

1. Whether to add a mandatory consolidation step to the owner's delivery coordinator (and propose it to HVE Core as a reusable phase or skill).
2. Whether to teach the pattern in partner HVE trainings (for example the 10 Nov 2026 hands-on).
3. What the thought-leadership paper ("Everything but the Software") can claim: the paper's Section on the harness and experiment reports this MVE's results, whatever they are.

## Customer and stakeholder context

* Owner and experimenter: Juan Manuel Servera Bondroit (Sr Partner Solution Architect). Single practitioner; the experiment runs on the owner's existing development VM and agent tooling.
* Audiences for the result: AMA capstone reviewers (Section D), arXiv cs.SE readers, HVE Core maintainers, systems-integrator partners adopting HVE.
* No collaborative partner engagement is assumed. Optional enablement: a partner engineer who is already trialling HVE could replicate one arm independently.

## Constraints

* Time: results are needed before the thought-leadership artefact deadline (two weeks before the capstone panel day). The MVE must fit in about two weeks, with a smaller first pass in about one week.
* Budget: coding-agent consumption (tokens or premium requests) and VM time are finite. TODO(owner): set the budget ceiling.
* Data: synthetic data only. No personal data, no customer data, no production systems.
* Tooling: one agent runtime and one pinned model for all arms. TODO(owner): choose the runtime and model version.

## Assumptions and unknowns

Research preparation status (24 Oct 2026). Evidence IDs refer to the register below.

| ID | Assumption or unknown | Status | Evidence |
| --- | --- | --- | --- |
| A1 | Without consolidation, internal quality of agent-built code degrades as features accumulate. | Supported, with counter-evidence | Human-built software: E1-E6 (Lehman's increasing-complexity and declining-quality laws are conditional and among the least supported, E2). Agents: E7 (+30% static-analysis warnings, +41% cognitive complexity, persistent, after Cursor adoption), E8 (erosion rises in 77% of trajectories; quality instructions do not change the degradation rate), E9 (refactoring share falling, clones rising). Against: E10 (randomised trial, no maintainability penalty at small-task scale). |
| A2 | Agent errors compound: defects introduced at step k persist and new ones accumulate. | Supported | E11 (self-conditioning on own errors), E12 (39% average drop in multi-turn tasks), E13 (regressions grow with iterations for 12 of 20 models), E14 (downstream cost comes mainly from inherited test failures). Synthetic or benchmark settings; not yet measured for sequential feature delivery on one code base. |
| A3 | Agents generate more code and documentation per feature than a human can review in reasonable time. | Supported (observational) | E15 (review at most a few hundred lines per session), E16 (median Google change about 24 lines), E17 (understanding is the main review challenge), E18 (approval up, inline comments down among repeat reviewers of agent PRs). No study found on documentation volume versus review capacity. |
| A4 | A per-feature consolidation step reduces decay. | Inconclusive: no controlled evidence found | Practitioner support (Beck, Martin, Lanzetta). E8 shows instructions alone are insufficient; E19-E21 show agent refactorings are often superficial or wrong without verification (TCR mitigates). This is the gap the MVE fills. |
| A5 | The cost of consolidation is recovered later in the sequence. | Inconclusive | Fowler's design stamina hypothesis is explicitly unproven; E5-E6 are correlational. |
| A6 | Consolidated code bases absorb an unplanned cross-cutting change better. | Inconclusive | No direct evidence found. |
| A7 | The complete consolidation package outperforms review-only. | Inconclusive | No direct evidence found; arm C compares review-only with the package, including refactoring, behaviour-pinning tests and architectural notes. It cannot isolate refactoring. |

## Evidence register (Research preparation)

| ID | Source |
| --- | --- |
| E1 | Lehman (1980), Proc. IEEE 68(9); Lehman et al. (1997), METRICS'97 |
| E2 | Herraiz et al. (2013), ACM Computing Surveys 46(2), review of the laws' empirical support |
| E3 | Parnas (1994), Software Aging, ICSE'94 |
| E4 | Eick et al. (2001), Does Code Decay?, IEEE TSE 27(1) |
| E5 | Tornhill and Borg (2022), Code Red, TechDebt'22 (15x defects, 124% more development time in low-quality code) |
| E6 | Besker, Martini and Bosch (2018), TechDebt'18 (about 23% of developer time lost to technical debt) |
| E7 | He et al. (2026), Speed at the Cost of Quality, MSR'26 (arXiv 2511.04427) |
| E8 | Orlanski et al. (2026), SlopCodeBench, arXiv 2603.24755, MIT licence |
| E9 | GitClear (2025), AI Copilot Code Quality report |
| E10 | Borg et al. (2026), Echoes of AI, Empirical Software Engineering 31(6) |
| E11 | Sinha et al. (2026), The Illusion of Diminishing Returns, ICLR |
| E12 | Laban et al. (2026), LLMs Get Lost In Multi-Turn Conversation, ICLR |
| E13 | Chen et al. (2026), SWE-CI, arXiv 2603.03823 |
| E14 | Pan et al. (2026), SWE-Maintain, arXiv 2610.14768 |
| E15 | Cohen (2006), Best Kept Secrets of Peer Code Review |
| E16 | Sadowski et al. (2018), Modern Code Review at Google, ICSE-SEIP |
| E17 | Bacchelli and Bird (2013), ICSE |
| E18 | Yu et al. (2026), Habituation at the Gate, arXiv 2606.22721 |
| E19 | Gautam et al. (2025), RefactorBench, ICLR |
| E20 | Kim, Zimmermann and Nagappan (2014), IEEE TSE 40(7) |
| E21 | Bavota et al. (2015), JSS 107 |

Research is preparation only: it does not validate any hypothesis or satisfy any success criterion.

## Experiment type

LLM / agentic software-engineering process: a controlled performance and quality comparison between delivery loops. (Recorded explicitly to drive skill loading; the ML-experimentation skill is not required.)

## Prior attempts and related practice

* AMA case evidence: feature-first coordinator loop, 15-24 Oct 2026 (the exploratory case study).
* HVE practice: Mike Lanzetta's "Hypervelocity Orchestra" uses a 13-item done gate and a sprint-boundary retrospective whose findings block the next sprint; this MVE tests a per-feature variant.
* Kent Beck: alternate features with consolidation; Tidy First?; test && commit || revert (TCR).
