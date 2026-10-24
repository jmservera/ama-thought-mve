<!-- markdownlint-disable-file -->
# Feature step prompt (all arms)

You are implementing feature {k} of {N} in this repository.

Read README.md first. If DESIGN.md (arm B) or REVIEW.md (arm C) exists, read it next.

## Feature {k}: {title}

{user story}

Rules:
{rules}

## How to work

* Implement only this feature. Do not start later features.
* Make every test in tests/ pass, including tests/examples/test_f{k:02d}_*.py. Do not modify or delete anything in tests/examples/. You may add tests.
* Do not delete or weaken existing tests.
* Run `make test` before committing. Commit only when all tests pass. Uncommitted work is discarded when your time is up.
* Time budget: {feature_budget}.
* When the feature is committed, stop and summarise what you changed in at most five lines.
