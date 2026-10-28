# OSF preregistration submission checklist

**DRAFT: not submitted, not independently reviewed, not owner-approved.**
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
Final source-bound owner approval remains required; requesting these edits
does not supply it. Even after approval, registration and execution are separate.

## Complete the live OSF form

1. Select the general-purpose OSF Preregistration template.
2. Enter the title/description from [osf-preregistration.md](osf-preregistration.md).
   Complete actual contributors, affiliations, licence and visibility/embargo
   in OSF. Do not infer coauthors or publish private reviewer details.
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

## Owner review and submission

Review the exact source commit, input fingerprint and package inventory.
Confirm the recorded choices and prior-data disclosure; explicitly approve the
submission candidate. Record actual dated approval and evidence in the ledger,
then regenerate a clean exact package if any tracked file changed.
Owner approval covers preregistration, not permission to collect data.

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
