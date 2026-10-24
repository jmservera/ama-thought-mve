# The experiment environment pins these tools; TEST_CMD and QUALITY_CMD may be
# overridden by the runner (for example in an offline dry run).
TEST_CMD ?= python3 -m pytest -q -p no:cacheprovider tests
QUALITY_CMD ?= python3 tools/quality.py

.PHONY: test check metrics
test:
	$(TEST_CMD)

metrics:
	$(QUALITY_CMD)

check: test metrics
