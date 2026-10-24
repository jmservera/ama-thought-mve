<!-- markdownlint-disable-file -->
# Review-only step prompt (optional placebo arm C)

Do not change any code or tests. Your job is to review what was just built.

1. Run `make check`, then read reports/quality.md.
2. Review the last feature's diff (`git diff feature-start feature-end`) and the hotspots against this checklist: duplicated logic; long or complex functions; unclear names; dead code; responsibilities in the wrong place; tests that check implementation details instead of behaviour.
3. Rewrite REVIEW.md in at most 300 words: the main issues you see and where they are. Replace its content; do not append. Do not modify any other file.
4. Time budget: {consolidation_budget}. Commit REVIEW.md and stop.
