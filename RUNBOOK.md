# Runbook: running the feature-consolidation MVE

This runbook turns the pre-registered protocol in `protocol/` into results you can put in Section 8 of the paper. Follow the steps in order. Do not start any run you intend to analyse until steps 1 to 4 are complete. If you change anything after that, record it in `protocol/divergence-log.md`.

Tool facts were checked on 24 October 2026 against GitHub Copilot CLI 1.0.95 help and the official documentation. The latest CLI release at that date was 1.0.103. Re-check the flags on the version you pin.

## 0. What you need

- **Machine.** A dedicated Linux machine: a VM, a dev container or WSL2. It needs Python 3.11 or later, git, make, Node.js 22 or later (for the CLI) and, ideally, Docker. Do not use the machine for anything else during runs.
- **Copilot access.**
  - GitHub Copilot with the Copilot CLI policy enabled for your account or organisation.
  - A fine-grained personal access token with the **Copilot Requests** permission. Only user-owned tokens offer that permission. Put it in the environment variable `COPILOT_GITHUB_TOKEN`. Classic `ghp_` tokens are not supported.
- **Budget.**
  - Agent time: see section 11.
  - AI credits: measure them in the pilot. For a rough order of magnitude, SlopCodeBench reports USD 0.20 to 3.17 per checkpoint across models. Those are API prices, not Copilot credits.
- **Calendar.**
  - Building and freezing the suite: about three days.
  - Pilot: one day.
  - First pass: one to two days with four sessions in parallel.

## 1. Freeze the design with HVE Core's Experiment Designer

1. Create a new repository, for example `consolidation-mve`. Keep it private until the protocol is registered, then make it public. Copy this kit into it.
2. Install HVE Core. Record the version or commit you use.
   - **VS Code:** extension `ise-hve-essentials.hve-core`.
   - **Copilot CLI plugin:**
     ```bash
     copilot plugin marketplace add microsoft/hve-core
     copilot plugin install hve-core@hve-core
     ```
     The plugin tracks `main`, so note the commit.
3. Copy `protocol/` to `.copilot-tracking/mve/2026-10-24/feature-consolidation-harness/` and add `.copilot-tracking/` to `.gitignore`. It is the agent's working copy, not the record.
4. In Copilot Chat, select **Experiment Designer** in the agent picker and point it at that folder. Ask it to:
   - revisit vetting with the decisions in section 2;
   - update `hypotheses.md`, `experiment-design.md` and `mve-plan.md`.
   The agent is interactive and asks questions, so run it in chat, not with `-p`.
5. Promote the result back to `protocol/`, the tracked record.
6. Compute and register the plan:
   ```bash
   sha256sum protocol/mve-plan.md > protocol/mve-plan.sha256
   git add protocol && git commit -m "Freeze protocol" && git tag protocol-frozen
   ```
7. Register the frozen protocol before any confirmatory run. Use OSF Registries, or publish the paper's protocol version on arXiv. Its timestamp is your proof that thresholds came first.

## 2. Decisions to freeze

| # | Decision | Recommendation | Why |
| --- | --- | --- | --- |
| D1 | Model, reasoning effort, CLI version | One model, pinned by ID; `--reasoning-effort medium`; CLI pinned with `--no-auto-update` | A `model:` line in a custom agent file overrides `--model`. The runner disables custom instructions and passes no agent. |
| D2 | Budgets | Feature 30 min; consolidation or review 15 min; change request 45 min; plus `--max-ai-credits`, set after the pilot | The credit cap is a soft cap with a minimum of 30. Wall-clock time is enforced by the runner. |
| D3 | Replicates | **At least 4 runs per arm per suite**, not 3 | With 3 vs 3, no two-sided rank test can go below p = 0.10. With 4 vs 4 the floor is 0.029; with 5 vs 5 it is 0.008. |
| D4 | Feature step that delivers nothing | `drop_examples`: remove that feature's examples so later steps start green; hidden tests still count it as missing | `keep_examples` lets one failure block every later commit and every consolidation (TCR always reverts). |
| D5 | End state for H1 | After the last feature's post-feature step | Arm B's final consolidation is part of the treatment. |
| D6 | Verdict when the interval includes zero | `inconclusive`, not `invalidated`; `invalidated` only when the whole interval lies below the minimum effect (5 points) | Absence of evidence is not evidence of absence. `analyze.py` implements this rule. |
| D7 | Suite S2 | The library suite (no extra tooling), or a SlopCodeBench subset ported to the kit's format | SlopCodeBench has no Copilot CLI adapter; you would write an agent class or convert problems. Check the licence of the problems repository first. |
| D8 | Change-request success | All change-request hidden tests pass and no feature test that passed at the end state fails | This is what `analyze.py` computes. |
| D9 | Metric settings | Lint rules E, F, W, C90, B, SIM through `ruff --isolated`; jscpd with 50 tokens and 5 lines; complexity from lizard | `--isolated` and running jscpd from an empty folder mean the agent cannot change the metrics by editing configuration. |
| D10 | Cost unit | AI credits from `--usage-output-file`; otherwise tokens from the OpenTelemetry file; otherwise seconds | The usage JSON schema is undocumented. Confirm it in the smoke test. |
| D11 | Isolation | Agent in a container that sees only the run's repository (`config.docker.json`) | Hidden tests and reference solutions must be unreachable, not just unmentioned. |
| D12 | Placebo arm C | Include it if the budget allows (about +60% agent time) | It separates refactoring from a second look (H7). |

What the kit adds to the protocol (accept or change these before freezing):
- **Runner enforcement.**
  - A head with failing tests is reset.
  - Edited example tests are restored and logged.
  - Review-only steps may change only `REVIEW.md`.
  - Uncommitted work is discarded.
- **Fixed denominators.** A hidden test module that fails to import counts all of its tests as failed.
- **Measurements the agent cannot influence.** `ruff --isolated` and jscpd v5 run from an empty folder.
- **Small fixes.** `tcr` exits with status 1 when it reverts. Each feature's API is listed under its rules. A change-request prompt is added.
- **Analysis.** Treat suite as a fixed effect in any mixed model, because there are only two suites. Run is the random effect.

## 3. Finish and freeze suite S1

F1 and F2 are complete examples. Each has a specification in `suite.json`, 4 visible tests, 12 hidden tests and a reference solution. Complete F3 to F10 and the change request CR1 the same way:

1. **Specification:** in `suite.json`, give a user story, rules in plain language and an explicit API. Hidden tests may use only the API that the specification and the visible tests define.
2. **Visible tests:** 3 to 5, in `features/fNN/examples/test_fNN_*.py`. Write plain test functions so the stand-in runner can execute them.
3. **Hidden tests:** 10 to 20, in `features/fNN/hidden/test_fNN_hidden.py`, including interactions with earlier features.
4. **Reference solution:** a cumulative snapshot in `reference/fNN/workbench/`.
5. **CR1:** put it in `suites/s1-retrofit/cr1/examples` and `cr1/hidden`, with its reference in `reference/cr1/`.

You can draft these with HVE Core's RPI agents:
- Run `rpi-plan` with `mve-plan.md` and its SHA-256.
- Then run `rpi-implement`.
- Then run `rpi-review`, which judges conformance to the plan only, not hypotheses.

A second person, or at least a separate review session that you check, must read every hidden test against its rules.

Test the tests until every feature reports OK and no hidden test is reported as weak:

```bash
python3 harness/validate_suite.py suites/s1-retrofit
```

Freeze the suite:

```bash
find suites -type f -print0 | sort -z | xargs -0 sha256sum > protocol/suite.sha256
git add -A && git commit -m "Freeze suite S1" && git tag suite-frozen
```

## 4. Prepare the environment and run a smoke test

**Option A, container per step (recommended).**

```bash
docker build -t mve-agent:frozen harness/
docker image inspect --format '{{.Id}}' mve-agent:frozen   # record this digest; never rebuild during the study
python3 -m pip install -r harness/requirements-measure.txt  # host tools for the runner's checks and measurements
npm install -g jscpd                                        # same version as in the image
cp harness/config.docker.json harness/config.json
```

**Option B, dedicated VM.** Install the CLI and the tools on the VM, then use the local configuration:

```bash
npm install -g @github/copilot jscpd
python3 -m pip install -r harness/requirements-measure.txt
cp harness/config.local.json harness/config.json
```

**In both cases:**
- Replace `PIN-A-MODEL-ID` in `config.json` with the model ID. To see valid IDs, use `/model` in an interactive session.
- Set `effort` and `max_credits`.
- Export your token: `export COPILOT_GITHUB_TOKEN=...`.

Each step runs the agent with these flags, all present in CLI 1.0.95:

```text
copilot -C <repo> -p <prompt> --model <id> --reasoning-effort <level>
  --allow-all-tools --deny-tool "shell(git push)" --no-ask-user --no-custom-instructions
  --disable-builtin-mcps --no-auto-update --output-format json --log-dir <step>/logs
  --share <step>/transcript.md --usage-output-file <step>/usage.json --max-ai-credits <n>
```

The environment adds:
- `COPILOT_HOME`: fresh for every step, so no memory or session carries over.
- `COPILOT_OTEL_FILE_EXPORTER_PATH`: writes token counts per step.

Memory is off by default in prompt mode.

**Smoke test.**

1. Dry run without an agent:
   ```bash
   cd harness
   python3 runner.py --config config.dry-run.json --suite ../suites/s1-retrofit --arm B --run-id dry-B-01 --features 2 --phase dry --no-cr
   ```
2. One real feature and one consolidation step:
   ```bash
   python3 runner.py --config config.json --suite ../suites/s1-retrofit --arm B --run-id smoke-01 --features 1 --phase pilot --no-cr
   ```
3. Check, in `runs/smoke-01/steps/*/`:
   - `transcript.md`, `usage.json`, `otel.jsonl` and `logs/` exist;
   - the feature step committed after `make test`;
   - the consolidation step used `./tcr`;
   - no `possible_leak` appears in `steps.jsonl`.
4. Probe the isolation. Run one extra session that asks the agent to open a web page and to read a file outside the repository. Both must fail. If either succeeds, switch to container mode or enable the CLI's command sandbox (`copilot help sandbox`).
5. Open `usage.json`. If its credit field is not matched by the default `--cost-unit "credit|premium"` of `analyze.py`, note the field name and pass a matching expression.

## 5. Pilot (data excluded from the analysis)

```bash
python3 schedule.py --pass pilot --arms A B --runs 1 --features 10 --seed 101 --config config.json > pilot.txt
bash pilot.txt
python3 analyze.py --runs ../runs --phase pilot --out ../results/pilot
```

Use the pilot only to calibrate, and log every change in the divergence log:
- **Budgets:** if most feature steps hit the time limit, the features are too big for the budget. Adjust either one before the first pass.
- **Credit cap:** set `max_credits` to about twice the 90th percentile of credits per step.
- **No decay in arm A:** follow the iteration plan in `experiment-design.md`. Lengthen the sequence or strengthen the interplay between features.

## 6. First pass (S1, arms A and B, at least 4 runs each, 8 features plus CR1)

```bash
python3 schedule.py --pass first --arms A B --runs 4 --features 8 --seed 2027 --config config.json > first.txt
cat first.txt | xargs -P 4 -I{} sh -c "{}"
```

`xargs -P 4` runs four sessions at a time. Order is randomised in blocks, so every arm appears once per block and drift affects all arms alike.

- Watch progress with `tail -f ../runs/*/steps.jsonl`.
- Change nothing during a pass.
- If a run fails for infrastructure reasons, start a new run ID and log it. Never drop or replace a run silently.
- Add arm C with `--arms A B C` if you decided to include it.

## 7. Analyse and decide

```bash
python3 analyze.py --runs ../runs --phase first --out ../results/first
```

**Outputs:**
- `summary.md`: one row per hypothesis with its estimate, interval and verdict, then one row per run.
- `summary.json`
- `series.csv`: one row per run and feature.
- `trajectories.png`

**How the outputs are computed:**
- **Intervals:** 95% bootstrap intervals that resample whole runs within arm and suite.
- **p-values:** exact permutation p-values are reported, but read the intervals first.

**Before you accept a verdict:**
- read the violations and possible-leak columns;
- read two or three transcripts per arm.

**Optional mixed model.** Needs pandas and statsmodels:

```python
import pandas as pd, statsmodels.formula.api as smf
d = pd.read_csv("../results/first/series.csv")
print(smf.mixedlm("mean_ccn ~ C(arm) * k + C(suite)", d, groups=d["run_id"]).fit().summary())
```

**Close the loop:**
- Go back to the Experiment Designer and write `outcome.md`. Record each hypothesis as validated, invalidated, mixed, inconclusive or not evaluable, and the decision as go, no-go or adjust.
- In the paper, set `\resultstrue` and replace the placeholder with the figure and the hypothesis table. Report every run, including failed ones.

## 8. Main study (if budget allows)

- **Scope:** both suites, arms A and B (C optional), 5 runs each, 10 features plus change requests.
- **Order:** generate it with `schedule.py --pass main --suites s1-retrofit s2-library ...`.
- **Second suite:** write S2 the same way as S1 (section 3).

## 9. Comprehension task (H4, manual)

1. Export each final code base without arm labels: delete `DESIGN.md` and `REVIEW.md`, and give each a random code.
2. Two or three reviewers answer the same five questions per code base. Example: "Where is the rule that blocks installation without consent?"
3. Record accuracy and minutes per code base in a CSV, then compare arms with rank tests and Â12.

## 10. Archive and publish

- **Archive:** `runs/` (repositories, prompts, transcripts, usage, logs, measures), `results/`, the image digest, `protocol/` and the divergence log.
- **Clean:** strip tokens and personal data before publishing. The CLI redacts `COPILOT_GITHUB_TOKEN` and `GITHUB_TOKEN` from output by default. Check anyway.
- **Publish:** with the paper, for example on Zenodo or OSF.

## 11. Time and agent sessions (upper bounds at the proposed budgets)

| Pass | Agent sessions | Maximum agent hours | With 4 in parallel |
| --- | --- | --- | --- |
| Pilot: S1, A and B once, 10 features, no change request | 30 | 12.5 | 7.5 (only two runs, so two in parallel) |
| First pass: S1, A and B x4, 8 features, CR1 | 104 | 46.0 | 11.5 |
| First pass with placebo arm C x4 | 172 | 73.0 | 18.2 |
| Main: S1 and S2, A and B x5, 10 features, change requests | 320 | 140.0 | 35.0 |

These are upper bounds. Steps usually finish early. Measured credits per session from the pilot, times the session counts, give the credit budget.

## 12. Troubleshooting

| Symptom | Fix |
| --- | --- |
| `make: not found` | Install make, for example `apt-get install make`. |
| `./tcr: Permission denied` | The runner sets the executable bit, because zip files and synced folders drop it. In other copies, run `chmod +x tcr`. |
| The agent ends at once or asks for approval | Keep `--allow-all-tools` for prompt mode. Check that the CLI policy is enabled and the token has Copilot Requests. |
| `usage.json` missing or without credits | Use the tokens from `otel.jsonl` (`--cost-unit "input|output"`) or `--cost-unit seconds`, and say so in the paper. |
| Many `examples modified` violations | The agent is weakening tests. The runner already restores them; report the counts per arm. |
| Hidden pass rate near zero in both arms | The features are too large or the API is unclear. Revise and re-freeze before the first pass, never after. |
| `possible_leak` true | Read the transcript. If the agent saw hidden tests, discard the run, log it and fix isolation. |
