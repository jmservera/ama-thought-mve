"""External treatment-fidelity checks, never independent efficacy claims."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from evaluation_env import evaluation_environment

SUPPRESSION = re.compile(r"#.*(?:\bnoqa\b|\bnosec\b|type:\s*ignore|pragma:\s*no\s*cover|jscpd:ignore)", re.IGNORECASE)
CONFIG_NAMES = {
    "pyproject.toml", "ruff.toml", ".ruff.toml", ".flake8", "setup.cfg", "tox.ini",
    ".jscpd.json", ".jscpd.yaml", ".jscpd.yml", ".gitignore",
    "Makefile", "conftest.py", "quality.py", "metrics_core.py", "pytest.ini", ".coveragerc",
}


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    with evaluation_environment() as env:
        return subprocess.run(
            ["git", "-c", f"safe.directory={repo.absolute()}", "-c", "core.hooksPath=/dev/null",
             "-c", "core.fsmonitor=false", *args],
            cwd=repo, env=env, capture_output=True, text=True, timeout=60, check=False)


def measure_fidelity(repo: Path, previous: str | None, *, policy: Path) -> dict:
    """Count added suppressions/config edits from a real diff with fixed external policy."""
    configuration = json.loads(policy.read_text(encoding="utf-8"))
    source = {"policy_sha256": hashlib.sha256(policy.read_bytes()).hexdigest(),
              "ruff_isolated": True, "ruff_ignore_noqa": True, "lint_rules": configuration["ruff_select"],
              "complexity": "Lizard cyclomatic complexity", "duplication": "jscpd token/line duplication",
              "classification": "treatment-fidelity, not independent efficacy"}
    current = _git(repo, "rev-parse", "HEAD")
    if current.returncode:
        raise RuntimeError("Fidelity measurement requires a real candidate HEAD")
    source["head"] = current.stdout.strip()
    suppressions = sum(bool(SUPPRESSION.search(line))
                       for folder in ("src", "tests") for path in (repo / folder).rglob("*.py")
                       for line in path.read_text(encoding="utf-8").splitlines())
    if previous is None:
        return {**source, "suppression_lines_total": suppressions, "new_suppression_lines": None,
                "changed_configuration_paths": None, "diff_coverage": "unknown: previous checkpoint absent"}
    diff = _git(repo, "diff", "--no-ext-diff", "--no-textconv", "--unified=0", previous, "HEAD")
    names = _git(repo, "diff", "--name-only", previous, "HEAD")
    if diff.returncode or names.returncode:
        raise RuntimeError("Fidelity diff unavailable; do not infer zero suppressions/config edits")
    added = []
    python_file = False
    for line in diff.stdout.splitlines():
        if line.startswith("+++ "):
            path = line.removeprefix("+++ b/")
            python_file = path.startswith(("src/", "tests/")) and path.endswith(".py")
        elif python_file and line.startswith("+"):
            added.append(line[1:])
    config_paths = sorted(path for path in names.stdout.splitlines() if Path(path).name in CONFIG_NAMES)
    return {**source, "diff_before": previous, "suppression_lines_total": suppressions,
            "new_suppression_lines": sum(bool(SUPPRESSION.search(line)) for line in added),
            "changed_configuration_paths": config_paths, "configuration_changes": len(config_paths),
            "diff_coverage": "observed"}


def review_follow_through(run: dict) -> dict:
    """Verify external review/diff locators; overlap alone never establishes repairs."""
    if run["meta"]["arm"] != "C":
        return {"status": "not-applicable", "observed_reviews": 0, "unknown_reviews": None,
                "annotations": [], "repair_effect_proven": False}
    expected = run["meta"].get("features")
    opportunities = max(0, expected - 1) if type(expected) is int else None
    entries = run["meta"].get("review_follow_through_annotations")
    base = {"status": "unknown: external annotations unavailable", "observed_reviews": 0,
            "unknown_reviews": opportunities, "coverage_complete": opportunities == 0, "annotations": [],
            "scheduled_reviews": expected, "later_feature_opportunities": opportunities,
            "last_review_scope": "No later feature after the final review; not an unobserved repair",
            "repair_effect_proven": False,
            "scope": "External semantic annotations with genuine review/diff locators; file overlap is not a repair"}
    if entries is None:
        if opportunities == 0:
            base["status"] = "not-applicable: no later-feature review opportunity"
        return base
    if not isinstance(entries, list):
        raise ValueError("External C follow-through annotations must be a list")
    fields = {"cycle", "review_head", "review_path", "review_lines", "later_feature_head",
              "diff_path", "diff_hunk", "assessment", "reviewer", "evidence"}
    repo = Path(run["dir"]) / "repo"
    observed = set()
    annotations = []
    for entry in entries:
        if (not isinstance(entry, dict) or set(entry) != fields
                or type(entry["cycle"]) is not int or not 1 <= entry["cycle"] < expected
                or entry["review_path"] != "REVIEW.md"
                or not isinstance(entry["review_lines"], list) or len(entry["review_lines"]) != 2
                or any(type(line) is not int or line < 1 for line in entry["review_lines"])
                or entry["review_lines"][0] > entry["review_lines"][1]
                or any(not isinstance(entry[key], str) or not entry[key].strip()
                       for key in ("diff_path", "diff_hunk", "reviewer", "evidence"))
                or entry["assessment"] not in ("implemented", "not-implemented", "inapplicable", "unknown")
                or any(not isinstance(entry[key], str) or not re.fullmatch(r"[a-f0-9]{40}", entry[key])
                       for key in ("review_head", "later_feature_head"))):
            raise ValueError("Malformed external C annotation; require actual review/diff/rater locators")
        if not repo.is_dir():
            annotations.append({**entry, "locator_status": "unknown: retained repository unavailable"})
            continue
        reviews = [record for record in run["recs"] if isinstance(record, dict)
                   and record.get("kind") == "review" and record.get("k") == entry["cycle"]]
        features = [record for record in run["recs"] if isinstance(record, dict)
                    and record.get("kind") == "feature" and record.get("k", 0) > entry["cycle"]]
        review = _git(repo, "show", f"{entry['review_head']}:REVIEW.md")
        diff = _git(repo, "diff", "--no-ext-diff", "--no-textconv", "--unified=3",
                    entry["review_head"], entry["later_feature_head"], "--", entry["diff_path"])
        located = (len(reviews) == 1 and (reviews[0].get("measure") or {}).get("head") == entry["review_head"]
                   and any((record.get("measure") or {}).get("head") == entry["later_feature_head"]
                           for record in features)
                   and re.match(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@", entry["diff_hunk"])
                   and review.returncode == 0 and diff.returncode == 0
                   and len(review.stdout.splitlines()) >= entry["review_lines"][1]
                   and entry["diff_hunk"] in diff.stdout and bool(diff.stdout.strip()))
        annotations.append({**entry, "locator_status": "observed" if located else "unknown: locator unavailable"})
        if located and entry["assessment"] != "unknown":
            observed.add(entry["cycle"])
    return {**base, "status": "external annotation evidence; not automatic repair proof",
            "observed_reviews": len(observed),
            "coverage_complete": len(observed) == opportunities, "annotations": annotations,
            "unknown_reviews": opportunities - len(observed)}
