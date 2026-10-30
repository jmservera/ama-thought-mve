#!/bin/sh
set -eu
cd "$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
if [ -z "${PYTHON:-}" ]; then
    if [ -x .venv/bin/python ]; then
        PYTHON="$PWD/.venv/bin/python"
    else
        PYTHON=python3
    fi
fi
export PATH="$PWD/.venv/bin:$PWD/.study/runtime-tools/node_modules/.bin:$PATH"
exec "$PYTHON" -B harness/study.py "$@"
