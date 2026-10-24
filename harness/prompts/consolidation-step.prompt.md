<!-- markdownlint-disable-file -->
# Consolidation step prompt (arm B)

Do not add or change features. Your job is to leave the code better than you found it without changing its behaviour.

1. Run `make check`, then read reports/quality.md (functions above complexity 10, duplicated blocks, lint warnings, file sizes).
2. Review the last feature's diff (`git diff feature-start feature-end`) and the hotspots against this checklist:
   * duplicated logic;
   * long or complex functions;
   * unclear names;
   * dead code;
   * responsibilities in the wrong place, or rules from one feature leaking into another;
   * tests that check implementation details instead of behaviour.
3. Make small, behaviour-preserving changes. Apply every change through `./tcr "<message>"`: it runs all tests and commits if they pass, or reverts if they fail.
4. Never modify or delete files in tests/examples/. You may add tests that pin current behaviour before you refactor.
5. Rewrite DESIGN.md in at most 300 words: the current structure, where each business rule lives, and known debts. Replace its content; do not append.
6. Stop when the quality budget is met (no function above complexity 10, duplicated lines below 3%, zero warnings in the configured lint rules) or when your time budget ({consolidation_budget}) is used.
7. Finish with a summary of at most five lines: what you changed and what debt remains.
