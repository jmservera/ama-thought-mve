<!-- markdownlint-disable-file -->
# Visible behavioural repair (arm E)

Repair previously specified behaviour using ONLY the visible specifications
below and the visible examples. Run `make test`, inspect the implementation
against these specifications and fix behavioural defects. Do not request
hidden tests, scores, reference solutions or future requirements. Do not add
features or run a structural-quality consolidation pass. You may add new
behavioural tests in new files.

All accepted Python files under tests/ are immutable in full, including
imports, fixtures and constants. Never modify or delete tests/examples/.
Only in this repair session may you correct an agent-authored test expectation
that specifically contradicts a visible specification. Never delete a test
file. The supported exception changes only a literal expected value on the
right side of an `assert actual == expected` comparison. All surrounding bytes,
imports, fixtures, constants and test logic must remain unchanged. Other
claimed corrections are rejected, not automatically adjudicated.
For every modified accepted file, replace REPAIR.json with:

{"corrections": [{"path": "tests/test_existing.py",
"before_blob": "git rev-parse HEAD:tests/test_existing.py before editing",
"after_blob": "git hash-object tests/test_existing.py after editing",
"specification": "f01", "quote": "exact contradictory visible specification text",
"explanation": "which expectation was wrong and why the quoted specification contradicts it"}]}

Use the actual blob hashes, not the command strings. Each changed file needs
its own entry and retained explanation. The harness verifies provenance and
quote binding; this is not independent semantic adjudication of your claim.
Commit repairs and evidence through `./tcr "<message>"`. Uncommitted work and
red or policy-violating changes are discarded. Do not replace DESIGN.md or
REVIEW.md as a handover task. Stop within {consolidation_budget}.

Visible specifications through the current feature:
{visible_specifications}
