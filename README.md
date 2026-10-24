---
title: Feature-consolidation MVE kit
description: Experiment harness, recorded smoke results, and next steps for the full feature-consolidation suite.
---

Kit for the experiment in *Everything but the Software*, Section 8: does a consolidation step after every feature keep agent-built software working, understandable and changeable, and at what cost?

## Current state (2026-10-25)

The offline dry runs and the real-agent smoke test are complete. The recorded
[smoke summary](results/smoke/summary.md) covers `smoke-01`: S1, arm B, F1 and its
consolidation step. Both agent sessions have complete credit accounting:
14.54 AI credits and 204,204 tokens, using `claude-sonnet-5.5`. The end-state
hidden-test pass rate was 100%, with no open regressions, recorded violations or
possible-leak flags. These checks do not establish isolation by themselves.

The next milestone is the full S1 pilot: ten features in arms A and B, followed
by the planned study passes. S1 is not yet ready for that run: only F1-F2 are
marked `ready` in [the suite manifest](suites/s1-retrofit/suite.json); F3-F10 and
CR1 still need tests and reference implementations. Complete, independently
review, validate and freeze the suite, record the owner decisions and protocol
freeze, and verify isolation before launching. Follow [the runbook](RUNBOOK.md).

The smoke run is labelled `pilot` in its metadata, but it is not the full pilot
or a study replicate. Keep it separate from subsequent analysis. Its generated
hypothesis verdicts, including the H3 `invalidated` label, are not study findings:
one arm and one feature cannot establish between-arm effects or quality slopes.

## Repository contents

| Folder | What it holds |
| --- | --- |
| `RUNBOOK.md` | Step-by-step instructions, decisions to freeze, time and cost, troubleshooting. Start here. |
| `protocol/` | The protocol draft in HVE Core's Experiment Designer format (context, hypotheses, vetting, design, plan) plus a divergence log. Approval, freezing and external registration remain prerequisites, not completed milestones. |
| `harness/` | `runner.py` (one run of one arm), `measure.py` (hidden tests and metrics, outside the agent), `analyze.py` (hypothesis table), `schedule.py` (randomised run order), `validate_suite.py` (tests the tests), `fake_agent.py` (offline dry run), prompts, configurations and the agent `Dockerfile`. |
| `skeleton/` | The starting repository for every run: `Makefile`, `tcr`, quality report, empty package. |
| `suites/s1-retrofit/` | Suite S1. Features F1 and F2 are complete examples (specification, visible tests, hidden tests, reference solution); F3-F10 and the change request are specified and must be completed before the pilot. |
| `results/` | Tracked analysis summaries and tables, starting with the smoke results. Review outputs for sensitive data before committing. Raw run repositories, logs and transcripts stay in ignored run directories and a separate backed-up archive. |

## Quick start: offline dry run (no agent, no network)

Needs Python 3.11+, git and make on Linux, macOS or WSL.

```bash
cd harness
python3 runner.py --config config.dry-run.json --suite ../suites/s1-retrofit --arm B --run-id dry-B-01 --features 2 --phase dry --no-cr
python3 runner.py --config config.dry-run.json --suite ../suites/s1-retrofit --arm A --run-id dry-A-01 --features 2 --phase dry --no-cr
python3 analyze.py --runs ../runs-dry --phase dry --out ../results-dry
```

The stand-in agent applies the reference solution, so both arms reach 100%; the point is to check the pipeline, not the hypothesis. Real runs use `config.local.json` or `config.docker.json`, as described in the runbook.

The kit was dry-run end to end with the stand-in agent (feature, consolidation,
review-only, tampered tests and an undelivered feature), then smoke-tested with
a real agent as recorded above. These commands remain available to recheck the
pipeline after changes; they do not run the full suite.
