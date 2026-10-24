# Results

Runs analysed: 1 (B: 1); phase: pilot; cost unit: credits.
Agent sessions: 2; with a usage file: 2; with complete credit accounting: 2; AI credits: 14.54; tokens: 204,204; models: claude-sonnet-5.5.

| Hypothesis | Estimate | Verdict |
| --- | --- | --- |
| H1 working software | B-A end-state hidden pass rate n/a points, 95% CI [n/a, n/a], permutation p n/a, A12 n/a | not evaluable |
| H2 compounding errors | A slope of open regressions n/a per feature; regression load B/A n/a | not evaluable |
| H3 internal quality | A slopes positive on 0/4; B at most half of A on 0 | invalidated |
| H4 less to review | non-test lines B/A n/a [n/a, n/a] | not evaluable |
| H5 pays for itself | total cost B/A n/a [n/a, n/a]; last third A n/a, B 14.54 | not evaluable |
| H6 changeability | n/a vs n/a change requests succeeded | not evaluable |
| H7 refactoring, not a second look | n/a vs n/a | not evaluable |

## Runs

| Run | Arm | Suite | End pass rate | Open regressions | Mean CC | Dup % | Cost | CR | Violations | Possible leaks |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| smoke-01 | B | s1-retrofit | 100.0 | 0 | 5.00 | 0.00 | 14.5 | None | 0 | 0 |

Small samples: with 3 runs per arm no two-sided rank test can reach p < 0.10; treat intervals, not p-values, as the result.

