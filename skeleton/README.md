# Retrofit case workbench

A small Python 3.12 library for managing home-retrofit cases. You add one feature at a time.

- Code lives in `src/workbench/`. Use only the Python standard library.
- Tests live in `tests/`. The files in `tests/examples/` define each feature's behaviour: never modify or delete them. You may add your own tests elsewhere in `tests/`.
- `make test` runs all tests. `make check` runs the tests and writes `reports/quality.md` (complexity hotspots, duplicated blocks, lint warnings, file sizes).
- `./tcr "message"` runs the tests and commits if they pass, or reverts every uncommitted change if they fail.
- Commit only when `make test` passes.
