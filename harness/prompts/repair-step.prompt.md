<!-- markdownlint-disable-file -->
# Visible regression-repair step prompt (arm E)

This is a visible regression-repair session, not consolidation or hidden feedback.
Read the current/previous immutable specifications/ and approved examples. No
external evaluator scores, test identities/messages, reference code or future
requests are available to you. Repair only previously specified behavior using
visible specifications, approved examples, the repository and your own visible
tests. Do not add new capabilities or start another feature.

1. Run the visible tests and inspect the last feature diff. Find a regression or
   defect against a numbered rule in a released specification, not against an
   assumed reference implementation.
2. Make bounded repairs through `./tcr "<message>"`. All accepted tests must stay
   green. Never edit or delete tests/examples/ or specifications/.
3. You may correct an agent-authored test only when its expectation contradicts
   an immutable released specification. A failing implementation is not itself
   evidence that a test is wrong. Never correct an immutable approved example.
4. For every changed src/*.py or agent-authored tests/*.py file, record
   REPAIR_EVIDENCE.json with a `changes` array of objects containing `path`,
   `before_sha256` (null for a new file), `after_sha256`, `specification`
   (specifications/fNN.md), `spec_sha256`, `rule` (number), and `rationale`.
   Use SHA-256 of file bytes. Explain the contradiction and the old/new expected
   behavior explicitly for a corrected test. This evidence remains subject to
   external semantic review; it is not an approval.
5. Write REPAIR.md in at most 300 words with the actual diff/specification
   locators, repairs attempted and remaining visible uncertainty. If there is
   no visible defect, record that and do not manufacture one.
6. Time budget: {consolidation_budget}. Commit green work and stop. New capability
   work, test weakening without specification-bound evidence and immutable
   material changes are protocol violations.
