---
title: Consolidation Harness Protocol Divergence Log
description: Dated changes to the unexecuted experiment protocol
ms.date: 2026-10-24
---

## 2026-10-24: Pre-Run Revision for Draft v3

These changes were made before any run, according to the package's recorded
unexecuted status. No experiment or delivery loop was launched in this revision.
This entry is not owner approval, protocol freezing or public registration.

* Changed the exploratory first pass to S1, A/B, four runs per arm and eight
  features, followed by CR1. The main study remains five runs per arm per suite.
* Defined a first-pass CR1 variant for regions in lists, visibility and
  handoffs. Full CR1's ranking/export checks require F9-F10 and remain in the
  main study. Both variants need pre-pilot specifications and hidden tests.
* Recorded 64 feature, 32 consolidation and eight change-request steps,
  totalling 46 agent-hours or 11.5 idealised hours across four parallel sessions.
  The calculation and exact-rank-test floors are in ../protocol_checks.py.
* Replaced suite random effects with a fixed effect; retained run random
  intercepts. Replaced no-difference invalidation with interval-based decisions.
* Defined H1's post-consolidation end state, change-request regression
  protection and missing-feature resets without shrinking the hidden denominator.
* Disclosed B's extra time allowance, the optional time-matched C comparison,
  the proprietary-model limitation and pending public pre-registration.

Owner approval, the actual registration date/URL, exposed model/runtime
versions, budgets and frozen test assets remain required before execution.
