#!/bin/sh
# Check only: never install packages, invoke sudo, or change Docker permissions.
set -eu
cd "$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)"
exec "${PYTHON:-python3}" -B harness/study.py --check-vm "$@"
