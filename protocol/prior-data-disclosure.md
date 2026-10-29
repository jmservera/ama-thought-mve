# Existing data and repository chronology

**Prospective disclosure, recorded 28 October 2026; not final protocol approval
or completed registration.** Repository dates below are Git metadata, not
reconstructed execution or first-inspection timestamps.

## Owner-confirmed inventory

On 28 October the owner confirmed that the disclosed inventory is complete:
the historical measured development smoke, earlier unmeasured manual work,
and offline/fake/reference diagnostics. No additional model runs or
calibration/pilot trajectories were reported. This is an owner attestation,
not independent proof of absence. The owner previously confirmed the intended
registered cohort has not run and will start only after registration.

The measured `smoke-01` used Sonnet 5.5, arm B, F1 plus consolidation: two
sessions, 14.54324 AI Credits and 204,204 tokens. Its recorded final hidden pass
rate is 100%, with zero recorded open regressions, violations and possible-leak
flags. These outcomes were available during subsequent tooling/protocol
development. Zero flags do not prove isolation; generated historical hypothesis
verdicts are not scientific evidence of an effect.

The smoke's historical `pilot` label is retained but does not make it a
ten-feature calibration trajectory or one of the eighteen pilot units.
Unmeasured manual work, smoke and all offline/fake/reference diagnostics remain
excluded from registered estimation trajectories. No results are relabelled
or pooled. Unrelated hve-squad benchmarking is not this MVE's evidence.

## Recorded repository chronology

Author and committer timestamps agree for the three records below. They are
shown in their original offset and UTC to avoid assigning the wrong calendar day.

| Repository record | Git date, original offset | UTC |
|---|---|---|
| [c5184c5](https://github.com/jmservera/ama-thought-mve/commit/c5184c5dcfc7a7e23ae08972e8a733ea998d9f27): first tracked smoke summaries/series, including performance and usage | 2026-10-25 00:53:50 +02:00 | 2026-10-24 22:53:50Z |
| [ee27fa2](https://github.com/jmservera/ama-thought-mve/commit/ee27fa23f87fba98201b9893eb385699cbc61c67): README interpretation, exclusion and readiness limitations | 2026-10-25 00:58:08 +02:00 | 2026-10-24 22:58:08Z |
| [fb7e884](https://github.com/jmservera/ama-thought-mve/commit/fb7e88433d83527f9ad5bc72b9ccf31ec869a3d4): RUNBOOK records completed smoke, excluded status and uncompleted full pilot/study | 2026-10-25 01:05:46 +02:00 | 2026-10-24 23:05:46Z |

These are records of artifacts and their interpretation in Git. They do not
authenticate the machine clock, establish exact smoke start/end times or prove
when any person first inspected results. The tracked summaries contain no such
event timestamps; the historical `runs-smoke/` raw directory was not available
in the inspected checkout. Exact historical collection and first-inspection
times therefore remain unverified, rather than being inferred from commits.
Dates of unmeasured manual work are likewise not established by these records.

Offline diagnostics and their observed outcomes were used in implementation
and preregistration preparation. This includes the three-repeat reference
validation of F1-F10 and CR1 on 28 October 2026, whose private operator receipt
records command start/end times. It involved no model/provider call and is not
a registered trajectory. Model-independent tooling/reference exposure is
disclosed, not presented as an outcome-blind design process.

## 29 October excluded isolated-runtime setup probe

After source `44ec37d9bb470521b2efd396a71ce23deb2f8ebf` passed offline
validation, an owner-conditionally authorized empty-workspace GPT6.1Sol runtime
probe was attempted. It was not a feature/CR1 session, calibration trajectory
or pilot unit. It used a 30-credit soft limit, 90-second allowance and a 300-credit
reservation; fresh no-model checks reported SDK 1.0.28/CLI 1.0.105/protocol 3 and
authenticated user transport. No experiment tasks, hidden tests or reference
solutions were supplied.

The private attempt records 1.8024 seconds, zero observed tool calls and no
complete usage receipt. Evidence contains an SDK setup failure, not attested
session-create/model-send stages. A missing base-directory defect was corrected
offline without a retry. **Unknown charge is not zero charge.** The reservation
remains held and total current prior usage is unknown; historical 14.54324 is
only the earlier confirmed amount. `prior_credits=null` blocks new live
admissions until authoritative attempt-correlated usage/no-charge reconciliation.
No other model probe, calibration or registered pilot followed this failure.

Private logs/ledger are retained outside the source bundle. No exact wall-clock
execution/inspection times are inferred from Git or file timestamps. The
recorded monotonic duration does not establish those times.

## Scope of this record

This resolves `required_evidence.prior_data_disclosure` as an explicit inventory,
recorded repository chronology and uncertainty disclosure. It does not resolve
independent scientific acceptance, actual runtime/access evidence, final owner
approval or registration. Preserve original artifacts and any later recovered
raw chronology; disclose corrections prospectively rather than backdating.
