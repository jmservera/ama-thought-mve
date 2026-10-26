# Unattended runner implementation evidence

Task: unattended-runner-2026-10-26. Date: 2026-10-26. Scope: P01-P04.
Plan and details: same dated unattended-runner artifacts under plans/details.
One critique completed; PC-001/002/003 incorporated before implementation.

## P01/P02 implementation

P01/P02 implemented. `run-study.sh` and check-only `scripts/bootstrap-vm.sh`
dispatch the stdlib controller. Immutable schedules, input/config/source
fingerprints, per-study lock, fsynced state, explicit attempt IDs, process
startup ambiguity detection, persistent deadlines and bounded group termination
protect recovery. Zero-step metadata survives even interrupted repository setup.
Only unmeasured infrastructure interruptions retry; measured failure never does.
Canonical steps include every retry's cost exactly once; unrecorded attempt costs
also remain in the all-attempt accounting export. Unknown stays unavailable.

The integer nano-credit admission ledger includes explicit prior spend and
reserves before execution; unknown usage blocks admission, overruns persist
before stopping. Maximum ceiling is 2,500 credits and immutable on restart.
No paid backend is enabled. Docker command preparation is tested, not a live
or access-probed execution backend.

The reporting layer reuses the corrected statistics and exports 13 fixed files:
CSV/JSON/Markdown plus deterministic SVG and native LaTeX fragments. H4/H7,
human telemetry, currency conversion, proposed decay measures and mixed models
are explicitly unavailable. Result-only publication is exercised against local
bare git and fake gh: separate worktree, allowlist, symlink/secret/size checks,
normal push, idempotent commits and PR create/update. Source checkout preserved.

`study_io.py` is a justified shared boundary to avoid controller/export circular
imports and duplicate exception classes when executing the CLI as `__main__`.
No external runtime dependency or new package manifest was needed.

## P03 documentation

README one-command quick-start, detailed controller runbook and divergence
record distinguish safe diagnostic capability from unmet real-study requirements.
Legacy manual commands are explicitly not a bypass for the new safety gates.
The low-level runner now uses disposable branch checkpoint refs instead of
creating tags and bounds its trusted git helper calls. No kit tags changed.

## Amendments and divergences

Hard actual spending enforcement cannot be supplied by CLI 1.0.103. No
unverified "hard cap" workaround is accepted. Paid execution must refuse even
when a nominal per-session limit fits the launch ledger. This unmet requirement
will be reported explicitly in Review and delivery, not called conformant.

## Validation

Baseline first failed 6/289 tests because isolated pytest/ruff and make were
missing. Restored declared measurement dependencies into ignored `.venv`;
restored make into a session-local extracted package without sudo or changing
host packages. No cloud resource or service was used.

An interim full run passed 334 tests in 39.77s. Reference validation passed every
F1-F10 stage (164/164 at F10) and 182/182 including CR1. Shell syntax/ShellCheck,
isolated Ruff and diff hygiene checks passed after minor formatting corrections.
Documented stub command completed all five A/B/C sessions; repeating skipped
all durable work. Offline dry-run/bootstrap passed without a token or Docker.
Final post-refinement validation:

- `PATH="$PWD/.venv/bin:$PATH" .venv/bin/python -B -m pytest -p no:cacheprovider harness/tests -q`:
  **337 passed in 40.54s** (289 existing plus 48 new cases).
- Same environment, `harness/validate_suite.py suites/s1-retrofit`: every
  cumulative stage passes, **164/164 F10**, **182/182 including CR1**.
- Isolated Ruff over new Python modules/tests; sh syntax/ShellCheck for both
  entrypoints; bash syntax/ShellCheck for existing TCR; `git diff --check`: pass.
- `./run-study.sh --smoke --study-id final-validation-20261026`: five stub
  sessions, all 12/12 F1 hidden tests; expected deliberately forbidden C edit
  recorded and reverted. Second identical command launches no new session.
- Offline `--smoke --dry-run` and bootstrap `--smoke`: exit 0, no token present.
- Tests use local bare git plus fake gh for publication, including normal
  push rejection, auth failure, secret/link/size refusal and PR idempotence.
  No actual diagnostic-results PR was opened; only implementation publication
  is authorised for this delivery.

No real agent was invoked. Local ignored run artifacts are not study data and
are not staged. LaTeX fragments have structured export tests; a TeX compiler was
not installed or used. Source/result export shapes and SVG parsing are tested.

## Review readiness

P01-P03 complete, source and docs reconciled, no pending implementation
validation. One Review completed; authorised commit/push/stacked PR remains.
Full live execution remains an explicitly unmet requirement; no passing test
is represented as provider-billing enforcement or scientific approval.

## P04 Review handoff

Review execution Complete; outcome Not accepted for full live capability.
RV-001 hard billing, RV-002 wired Docker/backend and RV-003 full scientific
measure/method evidence are routed to later work. Offline tooling has no
additional established correctness defect. No fix/re-review loop was run.
Actual confirmatory dry-run exited 2 as expected; final derived exports passed
the publication validator: 13 files, 49,448 bytes, five stub attempts, zero usage.
