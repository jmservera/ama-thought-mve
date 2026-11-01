"""Bounded deterministic hidden-test mutation diagnostic on protected references."""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from study_io import ROOT, StudyError, atomic_json, command
from validate_suite import run_isolated, run_repeated

MAX_MUTANTS_PER_STAGE = 24
OPERATORS = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.GtE, ast.GtE: ast.Lt,
             ast.Gt: ast.LtE, ast.LtE: ast.Gt, ast.In: ast.NotIn, ast.NotIn: ast.In,
             ast.Is: ast.IsNot, ast.IsNot: ast.Is}


@dataclass(frozen=True)
class Mutation:
    """One explicit expression replacement with an immutable source locator."""

    line: int
    column: int
    end_line: int
    end_column: int
    original: str
    replacement: str
    kind: str


def mutations(source: str, limit: int = MAX_MUTANTS_PER_STAGE) -> list[Mutation]:
    """Generate a fixed bounded set; do not seek mutants using outcome feedback."""
    if type(limit) is not int or not 1 <= limit <= MAX_MUTANTS_PER_STAGE:
        raise ValueError("Mutation limit must be an integer from 1 through 24")
    tree = ast.parse(source)
    proposals = []
    for node in ast.walk(tree):
        replacement = None
        kind = ""
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in OPERATORS:
            changed = copy.deepcopy(node)
            changed.ops[0] = OPERATORS[type(node.ops[0])]()
            replacement, kind = ast.unparse(changed), "comparison-flip"
        elif isinstance(node, ast.Constant) and type(node.value) is bool:
            replacement, kind = repr(not node.value), "boolean-flip"
        elif isinstance(node, ast.Constant) and type(node.value) is int and node.value in (0, 1):
            replacement, kind = repr(1 - node.value), "zero-one-boundary"
        if replacement is not None:
            original = ast.get_source_segment(source, node)
            proposals.append(Mutation(node.lineno, node.col_offset, node.end_lineno,
                                      node.end_col_offset, original, replacement, kind))
    proposals.sort(key=lambda item: (item.line, item.column, item.kind))
    return proposals[:limit]


def apply_mutation(source: str, mutation: Mutation) -> str:
    """Replace one UTF-8 AST span in a disposable copy, never the reference itself."""
    lines = source.encode("utf-8").splitlines(keepends=True)
    start = sum(len(line) for line in lines[:mutation.line - 1]) + mutation.column
    end = sum(len(line) for line in lines[:mutation.end_line - 1]) + mutation.end_column
    encoded = source.encode("utf-8")
    if encoded[start:end].decode("utf-8") != mutation.original:
        raise ValueError("Mutation locator does not match the protected source")
    result = (encoded[:start] + mutation.replacement.encode("utf-8") + encoded[end:]).decode("utf-8")
    ast.parse(result)
    return result


def mutation_outcome(outcomes: dict | None, expected: set[str]) -> str:
    """Distinguish killed/surviving observed mutants from missing/error observations."""
    if (not isinstance(outcomes, dict) or set(outcomes) != expected
            or any(value not in ("passed", "failed") for value in outcomes.values())):
        return "unavailable"
    return "killed" if any(value == "failed" for value in outcomes.values()) else "survived"


def check(suite: Path, scratch: Path, limit: int = MAX_MUTANTS_PER_STAGE) -> dict:
    """Run f10/CR1 hidden panels with triplicate baseline and bounded fixed mutations."""
    metadata = json.loads((suite / "suite.json").read_text(encoding="utf-8"))
    scratch.mkdir(parents=True, exist_ok=True)
    from study import fingerprint
    from measure import expected_tests

    rows = []
    files = [path for feature in metadata["features"]
             for path in sorted((suite / "features" / feature["id"] / "hidden").glob("*.py"))]
    stages = (metadata["features"][-1]["id"], metadata["change_request"]["id"])
    for stage in stages:
        hidden = files + (sorted((suite / stage / "hidden").glob("*.py"))
                          if stage == metadata["change_request"]["id"] else [])
        reference = suite / "reference" / stage / "workbench"
        source_path = reference / "__init__.py"
        source = source_path.read_text(encoding="utf-8")
        baseline = run_repeated([str(path) for path in hidden], str(reference), 3)
        if any(value != "passed" for value in baseline.values()):
            raise StudyError("Mutation baseline is not triplicate all-pass; gate remains pending")
        expected = set(expected_tests([str(path) for path in hidden]))
        mutant_rows = []
        selected = mutations(source, limit)
        for index, mutation in enumerate(selected, 1):
            candidate_source = apply_mutation(source, mutation)
            with tempfile.TemporaryDirectory(prefix="protected-mutation-", dir=scratch) as directory:
                package = Path(directory) / "workbench"
                shutil.copytree(reference, package)
                (package / "__init__.py").write_text(candidate_source, encoding="utf-8")
                try:
                    outcomes = run_isolated([str(path) for path in hidden], str(package))
                except (RuntimeError, OSError) as error:
                    outcomes = None
                    error_name = type(error).__name__
                else:
                    error_name = None
            disposition = mutation_outcome(outcomes, expected)
            mutant_rows.append({
                "id": f"{stage}-{index:02d}", "source_path": "__init__.py",
                "line": mutation.line, "column": mutation.column, "kind": mutation.kind,
                "original": mutation.original, "replacement": mutation.replacement,
                "mutant_sha256": hashlib.sha256(candidate_source.encode()).hexdigest(),
                "disposition": disposition, "unavailable_reason": error_name
                    if error_name else "non-binary/error test outcome" if disposition == "unavailable" else None,
                "failed_contracts": sorted(test for test, value in (outcomes or {}).items() if value == "failed"),
                "equivalence": "unadjudicated, including survivors",
            })
        killed = sum(row["disposition"] == "killed" for row in mutant_rows)
        survived = sum(row["disposition"] == "survived" for row in mutant_rows)
        unavailable = len(mutant_rows) - killed - survived
        observed = killed + survived
        rows.append({
            "stage": stage, "hidden_contracts": len(expected),
            "baseline_repeats": 3, "baseline_all_pass": True,
            "reference_sha256": hashlib.sha256(source.encode()).hexdigest(),
            "hidden_source_sha256": {path.relative_to(suite).as_posix():
                                     hashlib.sha256(path.read_bytes()).hexdigest() for path in hidden},
            "mutants_generated": len(selected), "mutants_observed": observed,
            "mutants_killed": killed, "mutants_survived": survived,
            "mutants_unavailable": unavailable, "equivalent_confirmed": None,
            "equivalence_assessment": "not performed; survivors may be equivalent or reveal gaps",
            "observed_kill_fraction": killed / observed if observed else None,
            "all_generated_denominator_kill_fraction": killed / len(selected) if selected else None,
            "mutants": mutant_rows,
        })
    return {
        "schema_version": 1, "status": "bounded-offline-diagnostic-not-adequacy-approval",
        "source_commit": command(["git", "rev-parse", "HEAD"], cwd=ROOT),
        "inputs_sha256": fingerprint(ROOT),
        "working_tree_dirty": bool(command(["git", "status", "--porcelain"], cwd=ROOT)),
        "algorithm_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "maximum_mutants_per_stage": limit, "stages": rows,
        "mutants_generated": sum(row["mutants_generated"] for row in rows),
        "mutants_unavailable": sum(row["mutants_unavailable"] for row in rows),
        "acceptance_gate_complete": False, "universal_adequacy_claim": False,
        "evaluation_environment": "Trusted reference local child with allowlisted environment; not candidate OS/network containment evidence",
        "scope": "Deterministic first bounded comparison/bool/0-1 mutations on protected f10/CR1; no claim about all possible faults or equivalent-mutant exclusion",
    }


def main() -> int:
    """Write a new private receipt; do not overwrite past evidence or upload it."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, default=ROOT / "suites/s1-retrofit")
    parser.add_argument("--limit", type=int, default=MAX_MUTANTS_PER_STAGE)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    destination = args.out.absolute()
    if not destination.resolve().is_relative_to(ROOT / ".study") or destination.exists():
        raise StudyError("Mutation output must be a new private .study/ file")
    result = check(args.suite, ROOT / ".study/scratch", args.limit)
    atomic_json(destination, result)
    print(json.dumps({key: result[key] for key in ("status", "mutants_generated", "mutants_unavailable",
                                                  "acceptance_gate_complete")}, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (StudyError, ValueError, OSError, RuntimeError) as error:
        raise SystemExit(f"Mutation check unavailable/refused; gate pending: {error}") from error
