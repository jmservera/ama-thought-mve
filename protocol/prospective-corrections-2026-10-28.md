# Prospective correction notice: approved implementation, pending OSF recording

**Draft for the owner to record before any affected calibration/pilot session.
Prepared following the 28 October 2026 reviews; not published to OSF by this
repository or its tools.** The owner approved implementing all four corrections
and will record the necessary prospective clarification before affected
collection. No calibration or registered pilot was run during this preparation.

## Original registration and chronology

The owner reported submission and subsequent approval of
[the original registration](https://osf.io/ywsrv/overview), associated with
[the project](https://osf.io/re98c), on 28 October 2026. Approval is
owner-confirmed, not independently verified; its exact approval timestamp is
unavailable. The uploaded files were all the unchanged extracted contents of
`osf-final-763945b`, not the archive itself.

The original source is `763945bce239529b6a3e802e50dc7cf61c2736cf`.
Its retained archive SHA-256 is
`3be0d5ae203301016b68a28e4ca735a50e99ded882e1cd9f1a3bb0fff15ca647`.
The original attachments, prior-data inventory and historical source/tag remain
unchanged. This notice describes a subsequent candidate, not an edit to the
registered snapshot. The contributor manifest and eventual owner-approved freeze
must identify the actual corrected source commit and execution-input hash.

## Outcome attribution and missingness clarification

The previous measurement runners could classify a candidate-caused exception
as an unavailable observation. For example, a retained F4 package lacks the
mandatory F5 `OnHold` export: the F5 hidden module cannot import, although the
51 earlier contracts still pass. Such an established implementation nonpass
must not disappear from the fixed denominator as though measurement were
unavailable.

The corrected policy applies to both pytest and the standard-library runner:

- Record ordinary assertion nonpasses as failed.
- Record a positively established missing **declared** candidate package,
  export, method or field as failed. Bind the declaration to the applicable
  suite API, actual import instruction and/or loaded candidate module/type.
  A misspelled evaluator helper or undeclared external dependency is not
  positive evidence of an implementation failure.
- Record syntax failures bound to an actual candidate source-loader import,
  and established exceptions originating in candidate source, as failed.
  The recognized built-in exceptions are assertion, value, type, attribute,
  name, key, index, zero-division and not-implemented errors; candidate-defined
  exception classes also require actual source/module binding.
- Keep unavailable infrastructure/oracle and unresolved causes unknown.
  Memory, OS and timeout exceptions, unavailable external import dependencies,
  evaluator-code errors, unclassified exceptions and ambiguous/wrapped
  dependency failures are not automatically converted to failed.

Each measurement retains the raw runner outcome, normalized outcome, attribution,
exception/frame provenance and private diagnostic traceback in
`hidden_provenance`. A positively attributed module-import failure maps only
to its affected fixed test identities, not to unrelated previously passing
modules. Other absent/unrun observations remain errors. Neither runner is an
adversarial containment boundary; source attribution does not establish OS
isolation.

This is a prospective clarification of observable nonpass versus genuine
missingness, not a change to the test denominator, allocation or endpoint
definitions. It affects H1 coverage, H2 retention/open-loss histories and H6 CR1
success availability. Genuine unknown outcomes still receive the existing
missingness treatment/bounds, never zero cost, an invented success or automatic
failure. No historical outcomes are silently rewritten or pooled into the study.
Evaluator diagnostics remain external and must never be shown to the agent.

## Three bounded reference/oracle corrections

1. **Read-only views:** `get_case` and `list_cases` return detached dataclass
   values rather than aliases to stored cases. Mutating a returned value cannot
   change the underlying stage/owner or bypass transition/history/audit rules.
   Later reads still reflect legitimate subsequent writes. All current Case
   fields are immutable scalar values; no nested mutable object is shared.
2. **Per-request CR1 approval:** the existing hidden lifecycle test now approves
   the first request before declining it, then verifies a new request requires
   a fresh approval before acceptance. The reference already reset approval.
3. **Held/paused transition precedence:** for an existing case and valid actor,
   hold, then pause, is checked before target-stage validity, including an
   unknown target. This matches the explicit existing every-move rules; hold
   still takes precedence over pause.

Existing hidden identities are strengthened, not added: the panel remains
142 contracts. Changed hidden source hashes/oracle bindings and generated
reference snapshots are versioned; eligibility and acceptance metadata are not
silently changed. Prior scoped static reviews do not automatically accept the
corrected snapshot. Three unchanged-reference repetitions, exact identity/hash
checks and source-bound review are required before collection.

## Execution preparation, not launch permission

The operator uses an organization-sponsored Copilot Enterprise licence. The
owner reports model access and a one-million-credit per-collaborator company
limit; neither demonstrates the registered study-specific 300,000-credit stop.
The owner reconfirmed **14.54324 AI Credits** as all prior paid study usage.
The supplied controller config keeps prior credits explicit rather than
silently assuming zero; the contributor must use that amount plus any later
logged non-study probes before collection.

Official GitHub documentation now distinguishes individual user-level budgets
(hard stop covering included and metered AI credits) from enterprise/org
spending budgets (metered spending only). The read-only budget-audit helper
checks effective individual scope, identity, amount, expiry and supplied
cycle/deadline consistency. It does not configure company budgets or verify
the supplied reset boundary independently. A monthly cap is not a lifetime
study ceiling. A CLI session cap remains soft, minimum 30 credits.

The owner approved designing a default-deny egress gateway/proxy. That is not a
completed deployment or access-probe acceptance. Outbound-only NAT and an
allowlisted GitHub hostname do not prevent retrieval of the public evaluator
source. File separation and URL permission rules alone do not prove containment.
The live backend remains disabled until verified billing, runtime and actual
evaluator/network isolation are integrated without bypassing agent safeguards.
This preparation neither provisions Azure resources nor launches paid probes.

## Review scope and remaining owner actions

The requested Sonnet 5.5 review supported limited static panel/oracle,
analysis and multi-model scheduling/accounting conclusions, but did not approve
actual paid execution. A subsequent focused AI construct review found the four
corrections above. These were AI-assisted technical reviews, not human sign-off,
institutional independent review or blanket scientific/runtime acceptance.
The registered wording requires a qualified independent reviewer, not a
human-only reviewer; the owner must evaluate qualifications, independence and
limitations explicitly for each source-bound conclusion.

Record this notice prospectively in OSF, identify the corrected source and
actual implementation/validation evidence, and resolve the remaining
precollection entries and owner-authorized freeze. Do not mark the candidate
as registered/accepted merely because the original registration is approved.
The three models, A/B/C arms, 18 estimation trajectories, nine excluded
calibration trajectories, 468 planned sessions, timing, credit ceiling and
estimation-only analysis remain unchanged.
