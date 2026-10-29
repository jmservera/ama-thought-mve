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
The 29 October addendum below supersedes the earlier requirement for that
separate provider-enforced study stop; it does not waive information isolation.
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
The live backend remains disabled until accepted billing/accounting controls, runtime and actual
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
calibration trajectories, 468 planned sessions, timing, nominal registered
credit envelope and estimation-only analysis remain unchanged. Operational
credit thresholds are lowered prospectively as follows.

## 29 October addendum: buffered soft limits and accepted financial risk

The owner explicitly accepts the residual financial risk of Copilot CLI soft
limits under the much higher company hard limit. This supersedes the earlier
project requirement for a dedicated provider-enforced 300,000-credit study stop.
The reported **1,000,000-credit hard limit per collaborator** remains an owner
assertion: actual account settings, scope/reset and remaining company allowance
have not been independently verified. It is not a study-specific guarantee.

Use the same **10% buffer** for all models/arms and both stages: **270 AI Credits
per original session**, shared across any infrastructure retry, and **270,000
credits local whole-study admission**, below nominal registered 300/session and
300,000 total. The exact buffer is an implementation assumption implementing the
owner's direction to set limits below previous values. Historical confirmed
usage is **14.54324**; calibration, probes, retries and all other study charges
count. After the excluded SDK setup probe described in
[prior-data-disclosure.md](prior-data-disclosure.md), current total prior usage
is unknown: the initial correction supplied `prior_credits=null` and held
admission until authoritative reconciliation. The later owner-approved historical
budget provision below supersedes that receipt prerequisite, not unknown usage.
The probe's 300 reservation remains held;
the setup fix was not model-retried. Remaining original allowance below
the CLI minimum 30 blocks retry; do not round up or create a fresh allowance.
An initial reservation of 300 provides 30 credits of headroom; any actual
reservation overrun is retained and stops further admission.

GitHub states that an in-progress response completes even if it exceeds the
session limit. The session buffer and 30,000 aggregate buffer reduce overshoot
risk, but **do not guarantee** either nominal registered ceiling or final billed
consumption. Monitoring/complete accounting is still mandatory; new unknown usage
blocks new work. A company billing-cycle reset never resets the lifetime study
ledger. Do not silently shrink sample if affordability fails; halt and amend.
An optional read-only provider audit may add assurance but is no longer a
mandatory budget prerequisite under this explicit risk acceptance.

### Owner-approved historical budget provision, 29 October

The owner explicitly approved carrying forward the full 300-credit reservation
for `gpt-6.1-sol-nonstudy-1` at source `44ec37d`, separately from 14.54324 known
prior usage. Its actual charge remains unknown; the private original ledger is
unchanged. The owner later separately approved the same conservative treatment
for `gpt-6.1-sol-authorized-check-20261029-1` at source `cb19559`, after unexpected
built-in MCP startup stopped the check. Its source-bound ledger SHA-256 is
`2d42df9f95198e97944f23aa67bfff9a41097463ebf0ea877c37928e3f561cf6`.
Its actual charge also remains unknown despite a zero-valued SDK shutdown summary.
Configuration admits only the exact old provision or the exact ordered pair;
it never converts another failure automatically. Current known spending plus
600 held is **614.54324**, leaving **269385.45676** inside the 270000 admission
threshold before new reservations. Both original ledgers remain unchanged.

These are two separately approved prospective financial-policy exceptions for
excluded historical checks, not actual charges, guaranteed billing bounds, a claim of
complete historical accounting, or permission to ignore future missing usage.
Future unknown usage and overruns still stop, and session limits/security
controls remain unchanged. Live verification, exact-source acceptance/freeze
and collection authorization remain separate. Record this change in the OSF
update at the end of preparation, before affected calibration/pilot collection.

This financial decision changes no agent permission/trust/sandbox controls,
evaluator separation, actual model/access checks, independent acceptance or
owner-authorized source-bound freeze. This financial decision itself authorizes
no account changes, paid probes or calibration/pilot launch.
Record this addendum and its exact revised source prospectively in OSF before
affected collection; preserve the original approved attachment unchanged.

## 29 October runtime implementation: isolated SDK candidate

Following the owner's request to implement the backend, the revised candidate
pins repository-local `@github/copilot-sdk` **1.0.28** and explicit CLI **1.0.105 /
protocol 3**. Host interactive authentication remains separate from the model's
sole custom container tool. Built-in/discovered/MCP tools and unrelated
permissions are excluded or denied; no blanket approvals or sandbox bypasses
are introduced. No shared egress gateway or paid Azure provisioning is required
for this candidate design. Candidate tool traffic has no network; only the
trusted host provider/authentication transport has normal connectivity.

Tools use fresh read-only-root, no-network containers with bounded resources
and tmpfs. Opaque candidate filesystem/Git state is replayed only in containers;
it is never extracted into the trusted operator checkout. Feature/CR delivery
uses committed regular content only, retaining the original changed-HEAD
condition even for an empty commit. Uncommitted feature/CR work is discarded.
C preserves its regular REVIEW working file and reports other committed/
nonignored working edits as violations. Trusted canonical checkpoints preserve
exported bytes/modes and trajectory refs, not arbitrary actor Git configuration
or commit metadata. Attribute filters are not run on the trusted host.
Files persist across tool calls; process/socket/daemon memory does not.

A fixed supervisor and candidate have distinct identities. Actual offline
checks observe supervisor UID0/dumpability0, no-new-privileges and only
DAC_OVERRIDE/KILL/SETGID/SETUID capabilities. Candidate UID1001 has zero
effective/permitted/inheritable/ambient capabilities and no-new-privileges;
its finite bounding set is not claimed to be zero. Linux resets ordinary child
dumpability from pre-exec0 to post-exec1. Persistent child-zero is not provided:
the control boundary is the distinct protected supervisor, whose proc/control/
memory/signal interference checks are tested, not a false post-exec assertion.
Core-file limits are zero. No additional privileges are granted to hide this
kernel behavior.

Visible tests, hidden imports and metrics execute separately on read-only
canonical snapshots with only the applicable hidden stage. No evaluator
writeback, scores or diagnostics return to the study agent. Protected framing
and fixed-result-schema checks do not prove a fully adversarial Python oracle
tamper-proof. Filesystem/resource/export/output bounds and this limitation
must remain explicit in independent source/runtime review.

The immutable image content ID, canary source/helper hashes and whole execution
input hash are bound to a private offline receipt and owner freeze. Base/primary
tools are pinned; transitive registry/apt inputs are not a fully locked rebuild.
A rebuilt/different image needs fresh validation and acceptance.
SDK startup/status checks and offline Docker canaries spend no model credits.
Actual response identity, medium effort, routing and complete final billed
usage remain a separate constrained live-evidence gate; never infer them from
requested parameters. Unknown usage retains its reservation and blocks;
ambiguous owned containers or containment failures halt admissions globally.

This is a prospective runtime clarification, not a change to the model matrix,
18 pilot/nine calibration trajectories, fixed142 hidden identities (including
CR1), timing, endpoints, estimation-only analysis or nominal credit envelope.
The owner will assess a fresh independent AI technical report on the exact
source; scientific acceptance, panel acceptance, runtime/freeze and collection
permission are not synthesized. Record this revision through the existing
OSF registration update process before affected collection; do not replace the
original immutable attachments.

## 29 October F10 audit oracle and canonical encoding

The independent source review demonstrated two nonconforming audit
implementations that passed every current test: omitting `action` from the hash
payload and substituting a truncated SHA-512 digest. The reference itself
already used SHA-256 over all required fields; the gap was oracle coverage.

The owner explicitly selected a prospective public canonical encoding:

```python
payload = json.dumps(
    [seq, action, target, by, prev_hash],
    ensure_ascii=True,
    separators=(", ", ": "),
).encode("utf-8")
digest = hashlib.sha256(payload).hexdigest()
```

There is no trailing newline. This matches the existing reference's output,
including escaped non-ASCII actors, but **narrows previously unspecified
serialization freedom**. It is a newly explicit public requirement, not a
retroactive claim that an undocumented encoding was always mandatory.

Existing F10 visible and hidden tests now independently check the digest and
reject changed actions, rather than relying only on the candidate's own
verifier. The 142 hidden identities and eligibility mapping are retained;
affected suite/module/oracle hashes are regenerated as an unaccepted candidate.
Reference sources/snapshots remain unchanged. No calibration/pilot observations
are relabelled, recollected or pooled by this correction.

Record this clarification and its exact revised source in the existing OSF
update before affected collection, preserving original attachments. Earlier
review recommendations do not automatically accept the revised fingerprint;
affected-source assessment and explicit owner acceptance remain required.
The excluded setup probe's unknown usage/reservation, live runtime evidence,
owner freeze and collection gates are unchanged.
