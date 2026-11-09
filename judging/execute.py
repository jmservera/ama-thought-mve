"""Container entry point. Do not run against experiment candidates on the host."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from scenarios import eligible, execute


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, required=True, choices=range(1, 11))
    parser.add_argument("--cr", action="store_true")
    parser.add_argument("--src", type=Path, default=Path("/work/src"))
    parser.add_argument("--out", type=Path, default=Path("/tmp/judging.json"))
    args = parser.parse_args()
    sys.path.insert(0, str(args.src))
    results = [execute(scenario) for scenario in eligible(args.k, args.cr)]
    args.out.write_text(json.dumps({"schema": "s1-workflow-evidence-v1", "results": results}, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
