<!-- markdownlint-disable-file -->
# Review-only step prompt (arm C)

Do not change any code or tests. Your job is to review what was just built.
Read current/previous immutable specifications/ and approved examples. REVIEW.md
can influence later feature sessions, so this is an information-bearing review
package, not an inert placebo and not a repair session.

1. Run `make check`, then read reports/quality.md.
2. Review the last feature's diff (`git diff feature-start feature-end`) and the hotspots against this checklist: duplicated logic; long or complex functions; unclear names; dead code; responsibilities in the wrong place; tests that check implementation details instead of behaviour.
3. Rewrite REVIEW.md in at most 300 words: the main issues you see and where they
   are, with genuine path/line or diff-hunk locators and the relevant released
   specification/rule. Replace its content; do not append. Do not modify any other
   file. A file being touched later does not itself establish that an issue was repaired.
4. Time budget: {consolidation_budget}. Commit REVIEW.md and stop.
