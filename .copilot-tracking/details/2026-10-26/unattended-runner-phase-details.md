# Unattended runner phase details

Task ID: unattended-runner-2026-10-26. Date: 2026-10-26.

## P01

Critique refinements PC-001/002/003: use an immutable <=2500-credit budget and
explicit prior-spend amount; no missing-prior-spend default for live execution.
Persist absolute study expiry across restarts. Every subprocess must have a
bounded wait and process-group termination/escalation/reap policy. Retain PID
identity for crash recovery; refuse recovery while an owned child may still
write. A run cell is the sole replicate; interrupted attempts never create
replicates. Sum known attempt usage once into each durable step's usage and
seconds, holding unknown usage. Include failed/unmeasured attempts separately
in disposition exports even if a step ultimately completes.

P01-T01 uses existing `Run` step methods through a narrow subclass. Persist
metadata for the complete schedule before any attempt; store checkpoints before
steps and durable records afterwards. Recover a recorded step without rerunning;
otherwise reset only its disposable repository to the recorded checkpoint.
Retain attempt status and stderr/stdout privately; do not publish raw exception
strings or transcripts. Retry infrastructure interruptions with a fixed attempt
limit; normal non-delivery remains a retained measured outcome, not a retry.
Bind resume to complete inputs/config and git HEAD. Single controller flock.

P01-T02 uses integer nano-credit reservations, global within one study workspace;
include prior pilot spending explicitly. A missing/partial usage record holds its
reservation and blocks admission. Fail before oversubscription; retain overruns.
No provider-enforced hard bound is exposed by CLI 1.0.103, so live mode remains
blocked rather than relying on a nominal cap. Freeze manifest is owner-supplied:
full commit/tag plus input tree digest, registration and resolved gate evidence,
immutable image digest and limits. Never generate a freeze or permit a legacy
tag alone to pass. Docker command sees only disposable repo/session output,
no hidden/reference assets or host Docker socket. Switching D11 needs approval.

## P02

P02-T01 invokes existing analyzer, then exports flat hypotheses/intervals,
run dispositions and machine-readable availability; no invented statistical
methods. Standalone SVG and LaTeX picture avoid optional plotting dependencies.
Secondary units remain separate and missing credit usage never becomes zero.
Stub outputs are visibly diagnostic and excluded from study data.

P02-T02 supports `--publish` only after outputs validate. Fixed filename
allowlist, strict identifier, no links/raw logs/free-form agent content, secret
scan and per-file/aggregate caps. Results branch starts at source commit; use
an isolated temporary git worktree, leave caller branch intact. Fetch/resume
existing results branch, push without force, gh create or edit against source
branch. Test through local git/fake gh without network mutation.

## P03

P03-T01 documents one-command smoke/dry-run and currently blocked live execution;
bootstrap checks only, no sudo/install or implicit network. Amend divergence for
Docker, scheduling/retry/information policy proposals, not approved protocol.
P03-T02 uses existing available Python then installs only if a missing dependency
failure occurs. Run all regression tests, reference suite, shell syntax and smoke
twice; assert same schedule/records and exact exports. No real model subprocess.

## P04

P04-T01 directly reviews the coherent diff after validation. Record execution
separately from acceptance; any open material gap is not called conformant.
P04-T02 explicitly stages owned source/docs/tests and force-adds only dated RPI
artifacts (tracking is ignored). Conventional commit plus requested trailer;
push topic branch, gh create stacked PR with #1 dependency and credit limitation.
