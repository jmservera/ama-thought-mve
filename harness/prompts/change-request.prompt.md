<!-- markdownlint-disable-file -->
# Change request prompt (all arms)

You are implementing a change request in this repository. All earlier features are in place.

Read README.md first. If DESIGN.md (arm B) or REVIEW.md (arm C) exists, read it next.

## Change request: {title}

{user story}

Rules:
{rules}

## How to work

* Make every test in tests/ pass, including tests/examples/test_{cr_id}_*.py. Do not modify or delete anything in tests/examples/. You may add tests.
* Do not delete or weaken existing tests.
* Run `make test` before committing. Commit only when all tests pass. Uncommitted work is discarded when your time is up.
* Time budget: {cr_budget}.
* When the change is committed, stop and summarise what you changed in at most five lines.
