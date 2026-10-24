# Feature-consolidation MVE kit

Everything needed to run the experiment in *Everything but the Software*, Section 8: does a consolidation step after every feature keep agent-built software working, understandable and changeable, and at what cost?

| Folder | What it holds |
| --- | --- |
| `RUNBOOK.md` | Step-by-step instructions, decisions to freeze, time and cost, troubleshooting. Start here. |
| `protocol/` | The pre-registered design in HVE Core's Experiment Designer format (context, hypotheses, vetting, design, plan) plus a divergence log. |
| `harness/` | `runner.py` (one run of one arm), `measure.py` (hidden tests and metrics, outside the agent), `analyze.py` (hypothesis table), `schedule.py` (randomised run order), `validate_suite.py` (tests the tests), `fake_agent.py` (offline dry run), prompts, configurations and the agent `Dockerfile`. |
| `skeleton/` | The starting repository for every run: `Makefile`, `tcr`, quality report, empty package. |
| `suites/s1-retrofit/` | Suite S1. Features F1 and F2 are complete examples (specification, visible tests, hidden tests, reference solution); F3-F10 and the change request are specified and must be completed before the pilot. |

## Quick start: offline dry run (no agent, no network)

Needs Python 3.11+, git and make on Linux, macOS or WSL.

```bash
cd harness
python3 runner.py --config config.dry-run.json --suite ../suites/s1-retrofit --arm B --run-id dry-B-01 --features 2 --phase dry --no-cr
python3 runner.py --config config.dry-run.json --suite ../suites/s1-retrofit --arm A --run-id dry-A-01 --features 2 --phase dry --no-cr
python3 analyze.py --runs ../runs-dry --phase dry --out ../results-dry
```

The stand-in agent applies the reference solution, so both arms reach 100%; the point is to check the pipeline, not the hypothesis. Real runs use `config.local.json` or `config.docker.json`, as described in the runbook.

The kit was dry-run end to end with the stand-in agent (feature, consolidation, review-only, tampered tests and an undelivered feature). It has not yet been run with a real agent: the runbook's smoke test is the first real check.
