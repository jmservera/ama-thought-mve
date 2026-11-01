---
title: Prospective v5 offline and durable-execution runbook
description: Source-bound phases, accounting and blocked collection
ms.date: 2026-11-01
---

[The canonical protocol](protocol/pilot-estimation.md) is authoritative.
[CONTRIBUTOR.md](CONTRIBUTOR.md) covers the private operator boundary and
pip-based external validation environment. This is an offline candidate,
not permission to collect data or run paid probes.

The owner selected `public-pr-now` on 2026-11-01 after acknowledging both original
repositories remain public. Parent development-source PRs are permitted now,
separately from researcher-archive/results release, visibility/OSF changes and
collection. Interim public source exposure is a contamination limitation; future
privacy cannot undo it. Before collection the private repository/operator boundaries
below still apply. Historical cloud/sign-in/usage exports are owner-deferred;
repository evidence is used without inventing new reconciliation.

## Preview and smoke

```bash
./run-study.sh --smoke --dry-run
./run-study.sh --smoke --study-id v5-offline-check
./run-study.sh --smoke --study-id v5-offline-check --status
python3 harness/schedule.py --pass pilot-estimation --seed 2027
python3 harness/feasibility.py --out .study/v5-planning-NEW.json
./run-experiment.sh --dry-run
```

Smoke uses eight original fake-agent sessions: A/D feature only; B/C/E feature
plus consolidation/review/visible repair. It has no CR1 or model calls.
C's attempted forbidden edit is discarded. Repeating unchanged smoke resumes,
not reruns, completed steps. Changed source/config/input hashes require a new
diagnostic ID; preserve old data.

Live preview is read-only and returns nonzero while gates are missing.
The default v5 main schedule is 33/cell, three models, five arms: 495 runs,
8415 sessions, 3836.25 maximum hours. Calibration is one/cell, 15 runs,
240 sessions/105h, cost-only and without CR1. Phase aliases `first`/`pilot`
remain interface aliases; they do not change historical v1 metadata.

## Prospective sequence, not completed actions

1. Owner privacy attestations and independent operator access readback:
   both original repositories private, no operator access to them/the paper.
   Preserve and disclose earlier public/model exposure.
2. Exact-source independent scientific/runtime/boundary review, unchanged
   triplicate references and bounded mutation diagnostic review. Candidate
   tools have no network/credentials; trusted host provider transport is distinct.
3. Prospective OSF amendment/embargo and new owner freeze/phase authorization.
   Preserve the original registration and historical v4 manifest/tag.
4. Separately authorized, excluded cost-only calibration, no CR1. No outcome
   selection or replacement; failed/unrecoverable calibration halts and requires
   prospective amendment, not a quiet rerun under another ID.
5. Verify actual calibration accounting/model/assistance and all-495 numerical
   feasibility. Main ledger adds calibration actual spending once, retaining
   prior usage and historical holds. The proposed 1.25 projection margin is not
   a financial uncertainty guarantee.
6. Only a genuine main-phase freeze/launch authorization plus exact-source
   numerical go permits the unchanged fixed study. Publication follows collection
   and paper release, not private archive preparation.

Current maximum caps exceed budget and deadline. The 300000 nominal envelope,
270000 admission, 21.79019 known prior and 1200 historical holds are unchanged.
The sequential deadline is 14 days; total maximum hours are 3941.25. Even the
495 maximum CR1 sessions alone exceed 14 days. No completed affordability/deadline
evidence is claimed. Halt and amend before collection if infeasible; never shrink n.

## Durable recovery

Use the same study ID, exact source, config, model roster and allocation.
Completed measured tasks are not replayed after poor outcomes. Infrastructure
retry is at most once from its original pre-step checkpoint and shares remaining
original time/soft credits; D retains its single 45-minute/540-credit allowance.
Measurement retry uses the same retained immutable snapshot, not another model call.

Unknown accounting holds reservations and blocks new work. Overshoot, torn
journals, live/ambiguous owned writers, changing calibration evidence and oracle
contradictions block recovery. Never erase state, reset usage, restart the deadline,
replace trajectories or kill processes by name. Investigate exact owned resources
and preserve raw evidence. TCR is only for disposable candidate/test repositories,
never this kit checkout or work that must be kept.

## Reports and private handoff

```bash
./run-experiment.sh --status
./run-experiment.sh --share
python3 harness/analyze.py --runs .study/STUDY/runs \
  --study-state .study/STUDY/state.json --out .study/STUDY/reanalysis
```

The explicit journal supplies all-attempt credits. No journal/usage means
unavailable, not zero. Reports retain full allocation and assistance dispositions,
loss-risk missingness, CR1 graded counts/prerequisite strata, fidelity and timing.
No raw logs or repositories enter the derived ZIP. Share is local-only.
Private contributor source packaging requires a clean committed candidate and
external checksum verification; this work performs no commit or upload.
