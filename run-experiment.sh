#!/bin/sh
set -eu
cd "$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
exec ./run-study.sh --study-id pilot-estimation "$@"
