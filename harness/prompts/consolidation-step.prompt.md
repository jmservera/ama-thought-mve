<!-- markdownlint-disable-file -->
# Consolidation step prompt (arm B)

Do not add or change features. Your job is to leave the code better than you found it without changing its behaviour.
Read current/previous immutable specifications/ and approved examples first.
This is behavior-preserving consolidation, not a defect-repair allowance. If
current behavior contradicts a visible specification, document that debt; do not
blindly bless it with a behavior-pinning test or repair it in this session.

1. Run `make check`, then read reports/quality.md (functions above complexity 10, duplicated blocks, lint warnings, file sizes).
2. Review the last feature's diff (`git diff feature-start feature-end`) and the hotspots against this checklist:
   * duplicated logic;
   * long or complex functions;
   * unclear names;
   * dead code;
   * responsibilities in the wrong place, or rules from one feature leaking into another;
   * tests that check implementation details instead of behaviour.
3. Make small, behaviour-preserving changes. Apply every change through `./tcr "<message>"`: it runs all tests and commits if they pass, or reverts if they fail.
4. Never modify or delete tests/examples/ or specifications/. Keep all accepted
   tests green. Before adding a behavior-pinning test, check its expectation
   against an immutable released specification and identify the numbered rule.
   Do not modify previously accepted test definitions. For each added/changed
   agent-test file, write TEST_EVIDENCE.json with a `changes` array of objects:
   `path`, `before_sha256` (null for a new file), `after_sha256`,
   `specification` (specifications/fNN.md), `spec_sha256`, `rule` (number),
   `rationale` explaining the specification-derived expectation. Hash file bytes
   with SHA-256. A rationale is review evidence, not an automatic correctness proof.
5. Rewrite DESIGN.md in at most 300 words: the current structure, where each business rule lives, and known debts. Replace its content; do not append.
6. Stop when the quality budget is met (Lizard function complexity at most 10,
   jscpd duplicated lines below 3%, zero fixed Ruff warnings) or when your time
   budget ({consolidation_budget}) is used. These are treatment-fidelity targets,
   not independent software-efficacy outcomes. Suppression comments and local
   configuration edits do not change the external fixed measurement.
7. Finish with a summary of at most five lines: what you changed and what debt remains.
