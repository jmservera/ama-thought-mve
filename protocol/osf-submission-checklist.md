# OSF preregistration submission checklist

**Original registration: owner-confirmed approved following submission on
28 October 2026, https://osf.io/ywsrv/overview.**
The original 763945b attachment is immutable. The checklist below documents its
submission procedure; do not treat its historical approval as approval of the
subsequent corrected source. Record
[the prospective clarification](prospective-corrections-2026-10-28.md)
and obtain exact candidate acceptance before collection. No collection
permission or independent runtime acceptance is implied.
Use the ordinary **OSF Preregistration** template, not Registered Reports.
Independent scientific review is not an OSF requirement for this submission.
On 30 October the owner superseded independent-review sign-off prerequisites
for this first study with disclosed owner scientific and runtime/access review.
The separate executor provides operational separation, not independent review.
All actual runtime safeguards and final freeze/OSF requirements remain.

## What is ready and what remains

The design, analysis, operational choices, secondary scope and prior-data
disclosure are specified in the attached protocol. The six scientific scopes
and corrected `1120002` runtime/access evidence are owner-accepted, not
independently validated. See the [runtime decision record](runtime-acceptance-2026-10-30.json).
The owner authorized source-bound approval/freeze after merging #4 on 30 October.
See [the freeze manifest](freeze.json). Prospective OSF completion stays unset;
actual amendment recording and separate launch authorization remain. Finite
diagnostics do not guarantee future entitlement.

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
owner-reviewed contract panel, scientific/runtime decision records, source/package hashes and readiness
report. Consult its manifest for the exact snapshot and file inventory.
The decision records identify actual owner acceptance and its limited scope;
package generation itself never approves checks or a later behavioral change.

Do not upload the separate private reviewer bundle, `.study` wholesale, raw
session logs, credentials, hidden test source or reference implementations.
The contract panel reveals evaluator identities: choose access/embargo settings
deliberately and never expose the panel or other held-out material to a study
agent. Final containment provenance must match the source-bound owner freeze.
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

Record the 30 October owner-reviewed scientific policy and six individually
accepted scopes plus corrected runtime/access acceptance, explicitly disclosing
no independent scientific or access/security review. Preserve assistance/usage coverage,
known prior spending and owner-authorised freeze. The 29 October owner-accepted
soft-limit policy uses 270/session and 270,000 local admission buffers, not a
guaranteed provider stop. Record it prospectively; a separate study hard cap
is no longer required. See [CONTRIBUTOR.md](../CONTRIBUTOR.md#billing-soft-limits-and-the-accepted-risk).
The current paid backend remains disabled even with complete registration.
If review requires substantive changes, document them prospectively in OSF and
version the affected source/panel/analysis before collecting affected data.
Preserve the original registration and disclose amendments; do not backdate.

Guidance: [official OSF guide](https://help.osf.io/article/330-welcome-to-registrations),
[COS preregistration](https://www.cos.io/initiatives/prereg), and
[Registered Reports distinction](https://www.cos.io/initiatives/registered-reports)
(consulted 28 October 2026).
