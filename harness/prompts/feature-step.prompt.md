<!-- markdownlint-disable-file -->
# Feature step prompt (all arms)

You are implementing feature {k} of {N} in this repository.
Your treatment is {arm}: {arm_description}.

Read README.md first. If DESIGN.md (arm B) or REVIEW.md (arm C) exists, read it next.
Read the released specifications/ files and their immutable approved examples.
Those current/previous specifications, not accidental code behavior or agent-authored
tests, define correctness. Do not access or invent future specifications.

## Feature {k}: {title}

{user story}

Rules:
{rules}

## How to work

* Implement only this feature. Do not start later features.
* Make every test in tests/ pass, including tests/examples/test_f{k:02d}_*.py. Do not modify or delete anything in tests/examples/. You may add tests.
* Do not delete or weaken existing tests.
* Keep previously accepted agent-authored tests green, especially tests accepted
  during earlier B consolidation. Do not modify their definitions. A specification
  contradiction can be documented for the separate visible-repair session only;
  it is not permission to weaken tests during feature work.
* Run `make test` before committing. Commit only when all tests pass. Uncommitted work is discarded when your time is up.
* Time budget: {feature_budget}.
* When the feature is committed, stop and summarise what you changed in at most five lines.
