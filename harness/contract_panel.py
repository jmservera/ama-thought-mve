"""Derive a reviewable hidden-contract candidate without executing the suite."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from measure import expected_tests

ROOT = Path(__file__).resolve().parents[1]


def build_panel(suite_dir: Path) -> dict:
    suite = json.loads((suite_dir / "suite.json").read_text(encoding="utf-8"))
    sources = {"suite.json": hashlib.sha256((suite_dir / "suite.json").read_bytes()).hexdigest()}
    contracts = []
    for cycle, item in enumerate(suite["features"] + [suite["change_request"]], 1):
        cr = cycle > len(suite["features"])
        folder = suite_dir / ("" if cr else "features") / item["id"] / "hidden"
        files = sorted(folder.glob("*.py"))
        if not files or item.get("status") != "ready":
            raise ValueError(f"Contract source not ready: {item['id']}")
        for path in files:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            sources[path.relative_to(suite_dir).as_posix()] = digest
            for identity in expected_tests([str(path)]):
                contracts.append({"id": identity, "feature": item["id"],
                                  "role": "cr1" if cr else "feature",
                                  "from_cycle": cycle,
                                  "through_cycle": cycle if cr else len(suite["features"]),
                                  "oracle_version": digest, "unchanged": True})
    if len({item["id"] for item in contracts}) != len(contracts):
        raise ValueError("Hidden contract identities must be unique")
    return {"schema_version": 1, "suite": suite["name"], "sources_sha256": sources,
            "contracts": contracts,
            "review": {"accepted": False, "evidence": None},
            "status": "candidate-unreviewed"}


def checked_panel(path: Path, suite_dir: Path) -> dict:
    panel = json.loads(path.read_text(encoding="utf-8"))
    candidate = build_panel(suite_dir)
    if any(panel.get(key) != candidate[key]
           for key in ("schema_version", "suite", "sources_sha256", "contracts")):
        raise ValueError("Contract panel differs from current source identities/eligibility/oracle versions")
    return panel


def accepted(panel: dict) -> bool:
    review = panel.get("review") or {}
    return review.get("accepted") is True and isinstance(review.get("evidence"), str) and bool(review["evidence"].strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=ROOT / "suites/s1-retrofit")
    parser.add_argument("--out", type=Path, default=ROOT / "protocol/contract-panel.json")
    parser.add_argument("--check", action="store_true", help="Verify existing panel without changing approval")
    args = parser.parse_args()
    if args.check:
        panel = checked_panel(args.out, args.suite)
    else:
        panel = build_panel(args.suite)
        with args.out.open("x", encoding="utf-8") as output:
            json.dump(panel, output, indent=2)
            output.write("\n")
    print(f"{len(panel['contracts'])} contracts; accepted={accepted(panel)}; no review performed")


if __name__ == "__main__":
    main()
