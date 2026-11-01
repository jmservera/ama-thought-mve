# Retrofit case workbench

A small Python 3.12 library for managing home-retrofit cases. You add one feature at a time.

- Code lives in `src/workbench/`. Use only the Python standard library.
- Tests live in `tests/`. The files in `tests/examples/` define each feature's behaviour: never modify or delete them. You may add your own tests elsewhere in `tests/`.
- `make test` runs all tests. `make check` runs the tests and writes `reports/quality.md` (complexity hotspots, duplicated blocks, lint warnings, file sizes).
- `./tcr "message"` runs the tests and commits if they pass, or reverts every uncommitted change if they fail.
- Commit only when `make test` passes.

Current and previous released specifications are in `specifications/`. Their
approved example copies are immutable and visible even when an unsuccessful
feature's tests were removed from the green-only test path. Specifications,
not an accidental implementation or an agent-authored test, define correct
behavior. Never edit these specifications/examples or invent future requests.
Keep all previously accepted tests green. B may add specification-derived
behavior-pinning tests with TEST_EVIDENCE.json; E is a separately visible repair
package and may correct a contradictory agent-authored test only with explicit
specification/diff/hash evidence. Immutable examples are never correctable.
