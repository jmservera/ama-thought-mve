# OSF preregistration submission checklist

**OWNER-APPROVED FOR SUBMISSION, 28 October 2026. Not submitted or registered;
not independently reviewed or authorised for collection.**
Use the ordinary **OSF Preregistration** template, not Registered Reports.
Independent scientific review is not an OSF requirement for this submission.
The project retains it as a prerequisite before collecting calibration/pilot data.

## What is ready and what remains

The design, analysis, operational choices, secondary scope and prior-data
disclosure are specified in the attached protocol. Independent suite/panel,
analysis/reference and multi-model alignment acceptance are pending. Runtime
entitlement/effort/accounting and actual information-boundary checks remain
unverified. Do not describe the candidate as independently validated.

`readiness.json` reports `submission_unresolved` separately from
`collection_unresolved`. `unresolved` is an alias for submission blockers.
Actual source-bound owner approval is now recorded; it was supplied explicitly,
not inferred from an edit request. Registration and execution remain separate.

## Recorded final owner decisions

The owner approved content at `235489cc8b63307d35d624b1b7bb02124c1bfec1`
plus only the selected metadata/approval updates, on 28 October 2026.
The agreed protocol and prior-data inventory were reconfirmed unchanged, with
no additional work/data exposure or calibration/registered pilot collected.
The owner chose to submit with independent review/runtime checks pending,
confirmed contributors/permissions settled and no additional preregistration
approvals required.

**Document licence:** [CC BY-NC-ND 4.0 International](https://creativecommons.org/licenses/by-nc-nd/4.0/).
This applies only to owner-controlled preregistration documents/attachments,
not repository code or third-party materials.
**Visibility:** embargo through **2026-12-31**, selected but not configured here.
Personal contributor/affiliation details must be entered directly in OSF.

## Complete the live OSF form

1. Select the general-purpose OSF Preregistration template.
2. Enter the title/description from [osf-preregistration.md](osf-preregistration.md).
   Enter the settled contributors/affiliations directly in OSF, select
   **CC BY-NC-ND 4.0 International**, and choose embargo ending **2026-12-31**.
   Do not infer coauthors or publish private reviewer details.
3. Transfer the existing-data disclosure, including excluded historical smoke,
   manual work and offline/reference diagnostics. Git dates are source-history
   dates, not verified historical collection/first-inspection dates.
4. Transfer questions, design/randomisation, inclusion/exclusion, outcomes,
   missingness/analysis and resource rules from the corresponding sections.
   This is an eighteen-trajectory pilot/estimation plan with nine excluded
   calibration trajectories, not seven confirmatory hypothesis tests.
5. Include the pending-review/runtime statement above. No completed independent
   review or model access is claimed; any necessary substantive method change
   will be documented prospectively before collecting affected data.

## Attach only the submission package

Generate a fresh private package after committing the final candidate:

```bash
.venv/bin/python -B harness/prepare_registration.py --out .study/osf-preregistration-NEW-CANDIDATE
```

The package contains the explicit protocol/checklist/ledger/prompt files,
candidate **unreviewed** contract panel, source/package hashes and readiness
report. Consult its manifest for the exact snapshot and file inventory.
These are appropriate review inputs, not evidence that checks were accepted.
References to earlier raw engineering diagnostics do not imply their approval.

Do not upload the separate private reviewer bundle, `.study` wholesale, raw
session logs, credentials, hidden test source or reference implementations.
The contract panel reveals evaluator identities: choose access/embargo settings
deliberately and never expose the panel or other held-out material to a study
agent. Actual containment remains an unresolved precollection requirement.
Retain an owner-controlled backup of the exact submitted package and checksums.

## Verify the approved package and submit

Review the exact source commit, input fingerprint and package inventory.
The owner has explicitly approved the recorded choices, prior-data disclosure
and limited metadata updates; dated evidence is in the ledger. Verify that the
package matches that approved scope. Further substantive changes require
renewed approval; regenerate a clean exact package if any tracked file changes.
The recorded approval covers preregistration, not permission to collect data.

Submit through OSF and complete its actual contributor-approval/archive process.
A local package or saved live draft is not completed registration. Record the
real registration URL/date only once completion is confirmed; do not invent them.

## Before any collection

Complete the retained independent reviews, oracle/reference acceptance,
model-aware alignment, runtime/access checks, assistance/usage coverage,
known prior spending, owner-authorised freeze and provider-enforced hard billing.
The current paid backend remains disabled even with complete registration.
If review requires substantive changes, document them prospectively in OSF and
version the affected source/panel/analysis before collecting affected data.
Preserve the original registration and disclose amendments; do not backdate.

Guidance: [official OSF guide](https://help.osf.io/article/330-welcome-to-registrations),
[COS preregistration](https://www.cos.io/initiatives/prereg), and
[Registered Reports distinction](https://www.cos.io/initiatives/registered-reports)
(consulted 28 October 2026).
