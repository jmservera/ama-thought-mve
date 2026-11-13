---
title: "Pilot estimation, blind S1 judging, and human-calibration evidence"
description: "Sanitized results, accounting lineage, human-vs-AI calibration comparison, and SDK log intervention audit"
ms.date: 2026-11-13
---

## Scope and exploratory posture

This directory records the supplementary post-collection S1 judging outputs, the frozen human-calibration bundle, and the SDK event-journal intervention audit accompanying [../pilot-estimation/report.md](../pilot-estimation/report.md).

* The active five-arm pilot-estimation run (`315` allocated trajectories across three models and five arms, `5,341 / 5,355` measured steps, `313 / 315` completed trajectories) uses an unregistered changed design disclosed after the historical OSF registration.
* Supplementary workflow replay and AI judging were frozen and executed after collection and remain exploratory rather than confirmatory.
* Raw execution packets, private specimen-to-trajectory mappings, and per-call runtime workspaces remain stored off-Git in the checksummed local vault (`.study/evidence-vault-2026-11-13/`).

## Deterministic S1 workflow replay and retention

| Endpoint | Model | Arm | Allocated | Evaluable | All scenarios passed | Witnessed scenario losses |
| --- | --- | --- | --- | --- | --- | --- |
| p10 | claude-sonnet-5.5 | A | 21 | 21 | 20 | 0 |
| p10 | claude-sonnet-5.5 | B | 21 | 21 | 21 | 0 |
| p10 | claude-sonnet-5.5 | C | 21 | 21 | 21 | 0 |
| p10 | claude-sonnet-5.5 | D | 21 | 21 | 20 | 0 |
| p10 | claude-sonnet-5.5 | E | 21 | 21 | 21 | 0 |
| p10 | gemini-4-argon | A | 21 | 21 | 20 | 0 |
| p10 | gemini-4-argon | B | 21 | 21 | 21 | 0 |
| p10 | gemini-4-argon | C | 21 | 21 | 21 | 0 |
| p10 | gemini-4-argon | D | 21 | 21 | 21 | 0 |
| p10 | gemini-4-argon | E | 21 | 20 | 20 | 0 |
| p10 | gpt-6.1-sol | A | 21 | 21 | 5 | 0 |
| p10 | gpt-6.1-sol | B | 21 | 21 | 12 | 0 |
| p10 | gpt-6.1-sol | C | 21 | 20 | 7 | 0 |
| p10 | gpt-6.1-sol | D | 21 | 21 | 6 | 0 |
| p10 | gpt-6.1-sol | E | 21 | 21 | 12 | 0 |
| cr1 | claude-sonnet-5.5 | A | 21 | 21 | 20 | 0 |
| cr1 | claude-sonnet-5.5 | B | 21 | 21 | 21 | 0 |
| cr1 | claude-sonnet-5.5 | C | 21 | 21 | 21 | 0 |
| cr1 | claude-sonnet-5.5 | D | 21 | 21 | 20 | 0 |
| cr1 | claude-sonnet-5.5 | E | 21 | 21 | 20 | 0 |
| cr1 | gemini-4-argon | A | 21 | 21 | 20 | 0 |
| cr1 | gemini-4-argon | B | 21 | 21 | 21 | 0 |
| cr1 | gemini-4-argon | C | 21 | 21 | 21 | 0 |
| cr1 | gemini-4-argon | D | 21 | 21 | 21 | 0 |
| cr1 | gemini-4-argon | E | 21 | 20 | 20 | 0 |
| cr1 | gpt-6.1-sol | A | 21 | 21 | 5 | 0 |
| cr1 | gpt-6.1-sol | B | 21 | 21 | 12 | 0 |
| cr1 | gpt-6.1-sol | C | 21 | 20 | 7 | 0 |
| cr1 | gpt-6.1-sol | D | 21 | 21 | 6 | 0 |
| cr1 | gpt-6.1-sol | E | 21 | 21 | 12 | 0 |

## AI judge contrasts and credit accounting

Assessment v3 (`gpt6-luna-judge-v3`, model `gpt-6-luna` at `medium` reasoning effort, adapter `sdk1.0.28-cli1.0.105-judge3`, two fresh sessions per evaluable specimen) recorded `1252` scheduled calls with `418.635894` settled AI credits and `0.0` unresolved reserved credits.

* Assessment v1 (`3637817e...`): stopped on call 1 before prompt dispatch due to CommonJS/ESM tool-filter normalization (`0` settled credits, `30` reserved credits held).
* Assessment v2 (`e44eaed7...`): completed `15` calls (`5.282763` settled credits) and stopped on call 16 when free-text JSON omitted `evidence_ids` on one scenario (`30` reserved credits held in ledger; `0.3196095` credits reported in runtime diagnostics).
* Assessment v3 (`c10e6d6f...`): enforced strict per-specimen JSON Schema via `responseSchema` within a `2,934`-credit remaining ceiling under the approved `3,000`-credit envelope.

| Endpoint | Contrast | Dimension | Complete-frame difference |
| --- | --- | --- | --- |
| cr1 | B-D | functional_completeness | 0.0351 |
| cr1 | B-D | workflow_coherence | unavailable |
| cr1 | B-D | error_recovery | unavailable |
| cr1 | B-D | api_usability | 0.0357 |
| cr1 | B-A | functional_completeness | 0.0357 |
| cr1 | B-A | workflow_coherence | unavailable |
| cr1 | B-A | error_recovery | unavailable |
| cr1 | B-A | api_usability | 0.0370 |
| cr1 | B-C | functional_completeness | unavailable |
| cr1 | B-C | workflow_coherence | unavailable |
| cr1 | B-C | error_recovery | unavailable |
| cr1 | B-C | api_usability | unavailable |
| cr1 | E-B | functional_completeness | unavailable |
| cr1 | E-B | workflow_coherence | unavailable |
| cr1 | E-B | error_recovery | unavailable |
| cr1 | E-B | api_usability | unavailable |
| p10 | B-D | functional_completeness | 0.0577 |
| p10 | B-D | workflow_coherence | unavailable |
| p10 | B-D | error_recovery | unavailable |
| p10 | B-D | api_usability | 0.0599 |
| p10 | B-A | functional_completeness | 0.0729 |
| p10 | B-A | workflow_coherence | unavailable |
| p10 | B-A | error_recovery | unavailable |
| p10 | B-A | api_usability | 0.0722 |
| p10 | B-C | functional_completeness | unavailable |
| p10 | B-C | workflow_coherence | unavailable |
| p10 | B-C | error_recovery | unavailable |
| p10 | B-C | api_usability | unavailable |
| p10 | E-B | functional_completeness | unavailable |
| p10 | E-B | workflow_coherence | unavailable |
| p10 | E-B | error_recovery | unavailable |
| p10 | E-B | api_usability | unavailable |

## Frozen human calibration and agreement with AI judge

Reviewer `jmservera` submitted [human-calibration/SCORING_jmservera.csv](human-calibration/SCORING_jmservera.csv) and [human-calibration/REVIEWER_DETAILS_jmservera.csv](human-calibration/REVIEWER_DETAILS_jmservera.csv) under `human-calibration-guidance/v3` with status `in_progress` (`review_completed_yes_no = no`).

> [!IMPORTANT]
> Reviewer disclosure: "I used AI for identifying the cases with failures or mismatches instead of reviewing all the successful ones." Guidance v3 was authored after original AI scoring started, and the `79` scorable rows represent `16` distinct full scoring contexts (`11` rows in `S01` are unavailable). Agreement figures below are descriptive calibration diagnostics, not independent inter-rater reliability estimates.

| Dimension | Scorable paired comparisons | Raw 79-row exact | Raw 79-row within 1 | Equal-context (16) exact | Equal-context (16) within 1 | Unavailable NA match | NA vs numeric |
| --- | --- | --- | --- | --- | --- | --- | --- |
| functional_completeness | 158 | 98.7% | 100.0% | 96.9% | 100.0% | 11/11 | 0 |
| workflow_coherence | 158 | 97.5% | 98.7% | 93.8% | 96.9% | 11/11 | 2 |
| error_recovery | 158 | 94.3% | 98.7% | 87.5% | 95.3% | 11/11 | 2 |
| api_usability | 158 | 98.1% | 100.0% | 92.2% | 100.0% | 11/11 | 0 |

## Intervention attestation design and SDK journal audit

In [../../harness/intervention_coverage.py](../../harness/intervention_coverage.py), operator intervention coverage is never written automatically by the runner because automated logs cannot prove the absence of out-of-band human repository edits or hints. Without an explicit `intervention-coverage/v1` sidecar file, every trajectory remains `unknown` rather than `unassisted`, keeping `primary_estimates_available` set to `false`.

To check in-band agent behavior across the full study, all retained SDK transport event journals on the VM were audited in [intervention-log-audit-summary.json](intervention-log-audit-summary.json):

* Retained SDK event journals inspected: `5357 / 5357` attempts across `315` trajectories (`313` completed, `2` quarantined due to provider transport/fallback interruptions).
* Interactive user-input or elicitation RPC events: `0` (`onUserInputRequest` and `onElicitationRequest` were disabled, and `builtin:*` / `mcp:*` tools were excluded).
* Attempts to invoke any tool other than `isolated_exec`: `74` (`53` `create` and `21` `edit` calls, all rejected as nonexistent tools; `0` interactive question-tool calls out of `42594` total tool invocations).
* Sessions ending with a human permission or clarification question: `36` out of `5357` sessions across `29` distinct trajectories (`18` `claude-sonnet-5.5` sessions asking to confirm shell/TCR edits without built-in edit tools or `bash`, and `18` `gpt-6.1-sol` `f09-feature` sessions halting uncommitted to ask permission to add `rank_cases` to their own `f08` view allowlist test; `0` `gemini-4-argon` sessions).
* Non-review measured steps leaving `HEAD` unchanged: `509`.
