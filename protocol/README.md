# Current protocol and registration draft

Start with [pilot-estimation.md](pilot-estimation.md) and
[osf-preregistration.md](osf-preregistration.md).
[pilot-estimation.json](pilot-estimation.json) is the machine-readable design
and owner-decision ledger. Choices now specify three models, two trajectories
per arm/model (18 pilot plus nine excluded calibration), and 300,000 total
AI Credits as the nominal registered envelope. The 29 October owner-accepted
soft-limit policy uses 270/session and 270,000 local admission (10% buffers);
in-flight responses can exceed soft limits, so billed consumption is not
guaranteed. The much larger company hard limit is owner-reported, not verified
study enforcement. See [collaborator instructions](../CONTRIBUTOR.md#billing-soft-limits-and-the-accepted-risk).
The original registration is owner-confirmed approved following
submission on 28 October 2026: https://osf.io/ywsrv/overview.
The subsequent corrected candidate needs
[prospective OSF recording](prospective-corrections-2026-10-28.md) and
actual prospective amendment completion; no permission to collect data is recorded.
The owner separately approved all six scientific scopes for `90e393e` on
30 October and selected owner review rather than independent scientific
acceptance for this exploratory pilot. The lack of independent review is a
disclosed limitation, not a completed review. See
[the scientific decision record](scientific-acceptance-2026-10-30.json).
Corrected `1120002` runtime/access evidence was also explicitly owner-accepted.
The owner selected no independent reviewers for this first study; the separate
executor supplies operational separation, not scientific or security auditing.
See [the runtime decision record](runtime-acceptance-2026-10-30.json).
This changes review sign-off policy, not actual runtime safeguards.

The controller/analysis implement model-aware scheduling and separate primary
estimates per model, with immutable assigned-model/replicate identity. Required
`multi_model_harness_alignment` is owner-accepted on the reviewed source;
runtime/access acceptance is separately recorded. After merging #4 the owner
authorized the source-bound [freeze manifest](freeze.json); its prospective
OSF completion date stays unset until the actual amendment is recorded.
Final OSF recording and separate launch authorization remain.
An updated draft does not authorise the expanded study.
These are precollection safeguards, **not ordinary OSF submission requirements**.
The owner authorised submitting an honestly unreviewed plan on 28 October 2026,
with actual approval of 235489c content plus selected metadata now recorded.
The selected document licence is CC BY-NC-ND 4.0, with embargo through
2026-12-31; contributors/affiliations are entered directly in OSF. Follow
[osf-submission-checklist.md](osf-submission-checklist.md) for the live form and
safe attachments. Readiness reports separate submission and collection blockers;
no pending evidence is marked accepted to prepare a registration.

The other context/hypotheses/design/plan/vetting documents below are retained
**historical proposals**, not active seven-test criteria. The immutable
[pre-amendment snapshot](https://github.com/jmservera/ama-thought-mve/tree/1fee4535dd65ccedcee9638ef3a77ff3f9ce12a2)
and old `protocol-frozen` tag remain unchanged. Current analysis is estimation-only;
historical analysis requires explicit `--legacy-proposal`.
