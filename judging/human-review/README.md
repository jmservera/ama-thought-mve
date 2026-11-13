---
title: Offline human assessment workflow
description: Reproducible reviewer interface and reporting procedure for the blinded S1 calibration sample
ms.date: 2026-11-13
---

## Status and scope

This is the source of the offline reviewer pack delivered on 13 November 2026,
including human guidance `human-calibration-guidance/v3`. It documents the
assessment instrument and intended procedure, **not completed human reviews**.
Only actual human responses and their recorded disclosures can establish that
the procedure was followed. AI dry runs are excluded from human calibration.

The tool is specific to the fixed eight-specimen, 90-row S1 sample: six P10
specimens with eleven scenarios and two CR1 specimens with twelve scenarios.
It does not select specimens, run candidate code, contact a model, inspect AI
ratings, or change the experiment. Keep the assessment supplementary and
exploratory; this interface does not establish preregistration or judge accuracy.

The public source contains no study packets, completed reviewer responses,
private development mappings, credentials or paid-call records. Generate packs
and retain responses under ignored private storage such as `.study/`.

## Build a reviewer pack

The [builder](build.py), [page template](reviewer-app.html),
[workflow explanations](reviewer-context.json), [icon provenance](icons/README.md)
and [regression tests](../tests/test_human_review.py) are repository-owned source.

Python 3.11+ in the repository virtual environment is sufficient. The builder
uses the standard library, local HTML/JSON and bundled icons; no npm install,
server or network connection is needed to build or use the exported pack.

From an existing verified, unscored reviewer ZIP:

```bash
.venv/bin/python -B judging/human-review/build.py \
  --source-zip .study/review-input/reviewer-pack.zip \
  --output .study/human-review/reviewer-pack.zip
```

Alternatively, build from the original frozen selection and judging manifest:

```bash
.venv/bin/python -B judging/human-review/build.py \
  --data-root /private/judging-data \
  --output .study/human-review/reviewer-pack.zip
```

The data root must contain `human-calibration/manifest.json`, the eight selected
packet JSON files beside it, and `judging-batch/public/manifest.json` containing
the frozen packet hashes and rubric. The builder verifies those packet bindings.
It never reads the private study mapping or judge-response ledger.

Choose a new output path: existing ZIPs are never overwritten. The output has
a SHA-256 sidecar and an internal file-hash manifest. Original packet bytes,
selection and rubric are preserved; scores and reviewer declarations start blank.
Archive the exact source revision, input/output ZIP hashes and guidance version
with the coordinator's private provenance record. Do not copy private inputs into Git.

## Reviewer procedure

1. Give each independent reviewer a separate copy of the same ZIP. Keep AI
   ratings, the AI dry-run outputs and development labels away from reviewers.
2. Extract the ZIP and open `START_HERE.html`. Read the task, planned setup and
   final evidence. The expected-result explanations identify the public rules;
   planned checks are not evidence that an unrecorded operation actually ran.
3. Enter a reviewer ID or pseudonym, reviewer kind and exposure disclosures.
   Disclose general knowledge of the study aim and any previous AI-score exposure.
4. Score functional completeness, workflow coherence, error recovery and API
   usability separately. Select final evidence IDs and give a rationale for each
   dimension. Matching expected/actual values establish a passed comparison, not
   automatic 4s for unobserved dimensions. Missing evidence is NA, never zero.
5. Use mismatch-first ordering to prioritize differences without dropping the
   matching or unavailable rows. Explicitly reuse only your own completed
   assessment for exact-context matches; edited target rows are protected and
   copied ratings retain source/time/edit provenance. An unavailable-evidence
   bulk abstention requires your own reason and confirmation.
6. Save a private portable draft when needed. Browser local storage is a
   convenience, not an archive; use separate browser profiles for reviewers.
7. Export both CSVs. Partial exports retain all 90 rows with unfinished fields
   blank and an `in_progress` status. Only a declared human who has completed all
   rows and disclosures can explicitly attest completed human review.
8. Return the scores and reviewer-details CSVs to the coordinator. Freeze each
   independent response and receipt time before revealing AI ratings or discussing
   disagreements. Preserve independent originals alongside any later adjudication.

The complete guide, exact rubric, versioned human clarifications, shared feature
requirements and evidence-group index are included in each generated ZIP.

## Reporting the assessment

Report who actually reviewed the material, using consented identities or
pseudonyms, review/receipt dates, completeness, exposure disclosures, guidance
version, any copied assessments and the adjudication procedure. Never turn a
blank template, an AI test run or a generated package into a human attestation.
Publish participant responses only after separate consent and sanitization.

The original sample has 79 available rows but only 16 distinct full scoring
contexts, plus 11 unavailable rows. These counts describe the original handoff,
not an independent sample size; a rebuilt pack reports its own counts. Retain all
allocated rows and report availability and paired-rating coverage separately.

Show per-dimension exact and within-one-category agreement, with NA agreement
separate from numeric agreement. Alongside row-weighted summaries, show an
explicitly labelled equal-context sensitivity summary: average paired-row
agreement indicators within each exact group, then average the group values.
Do not silently select one representative judgment, average ordinal scores to
invent a consensus, or count copied ratings as independent observations.

The small, repeated, mostly passing panel cannot validate mid-scale judge
accuracy or support broad reliability claims. A broader stress panel would need
a separately declared selection and assessment; this builder does not create one.

Human guidance v3 and the explanations were added after original AI scoring
began and after an AI usability dry run. The AI rubric remains unchanged.
Disclose the guidance difference in human/AI comparisons; do not describe the
new instructions as prospectively applied to the original AI judge or silently
rejudge its responses.

## Validation and third-party assets

```bash
.venv/bin/python -B judging/human-review/build.py --self-test
.venv/bin/python -B -m pytest -p no:cacheprovider judging/tests/test_human_review.py -q
```

Offline browser checks exercised scoring, NA safeguards, explicit own-rating
reuse, draft import/version refusal, human-completion gates, actual CSV quoting
and export, plus desktop/mobile layout. Those synthetic interactions are software
validation, not human calibration evidence.

The ten local SVG icons are from `lucide-static` 1.72.0
(<https://github.com/lucide-icons/lucide>, <https://lucide.dev>).
The original ISC license and the included Feather-derived MIT notice are
preserved alongside the icons and included in generated reviewer ZIPs. Icon
source bytes are unmodified; the builder adds accessibility attributes to the
rendered copies. No icon download or CDN is used at runtime.