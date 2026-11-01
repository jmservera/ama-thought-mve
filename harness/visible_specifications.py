"""Immutable candidate-visible specifications/examples and intervention evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def specification_bytes(item: dict) -> bytes:
    """Render only an already released story, rules and API from the visible suite."""
    lines = [f"# {item['id']}: {item['title']}", "", item["story"], "", "## Rules"]
    lines += [f"{index}. {rule}" for index, rule in enumerate(item["rules"], 1)]
    lines += ["", "## API"] + [f"* {api}" for api in item.get("api", [])]
    return ("\n".join(lines) + "\n").encode("utf-8")


def visible_files(suite_dir: Path, features: list[dict], cr: dict | None = None) -> dict[str, bytes]:
    """Build the allowlist without reading hidden/reference or future feature files."""
    result = {}
    for item in [*features, *([cr] if cr else [])]:
        result[f"specifications/{item['id']}.md"] = specification_bytes(item)
        base = suite_dir / ("features" if item in features else "") / item["id"] / "examples"
        for source in sorted(base.glob("*.py")):
            if source.is_symlink() or not source.is_file():
                raise ValueError("Approved visible examples must be regular immutable source files")
            result[f"specifications/examples/{item['id']}/{source.name}"] = source.read_bytes()
    return result


def stage(repo: Path, files: dict[str, bytes]) -> None:
    """Stage the same released source-bound material for every arm."""
    for relative, content in files.items():
        destination = repo / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)


def restore(repo: Path, files: dict[str, bytes]) -> list[str]:
    """Restore released immutable content and reject candidate-authored specifications."""
    changed = []
    directory = repo / "specifications"
    if directory.exists():
        for path in sorted(directory.rglob("*"), reverse=True):
            relative = path.relative_to(repo).as_posix()
            if path.is_symlink():
                path.unlink()
                changed.append(relative)
            elif path.is_file() and relative not in files:
                path.unlink()
                changed.append(relative)
    for relative, content in files.items():
        path = repo / relative
        if not path.is_file() or path.read_bytes() != content:
            changed.append(relative)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
    return sorted(set(changed))


def note_violations(repo: Path, name: str) -> list[str]:
    """Reject missing/non-UTF-8/over-budget notes without silent truncation."""
    path = repo / name
    if not path.is_file() or path.is_symlink():
        return [f"required treatment note missing or nonregular: {name}"]
    try:
        words = len(path.read_text(encoding="utf-8").split())
    except UnicodeError:
        return [f"treatment note is not UTF-8: {name}"]
    return [f"treatment note exceeds 300 words: {name}"] if words > 300 else []


def test_changes(repo: Path, before: str, git) -> tuple[list[str], list[str]]:
    """Freeze accepted Python test files, including fixture/module/class context."""
    changed = git(repo, "diff", "--name-only", before, "HEAD").stdout.splitlines()
    paths = [path for path in changed if path.startswith("tests/")
             and not path.startswith("tests/examples/") and path.endswith(".py")]
    modified = []
    for path in paths:
        old = git(repo, "rev-parse", f"{before}:{path}", check=False)
        new = repo / path
        current = git(repo, "rev-parse", f"HEAD:{path}", check=False)
        if old.returncode == 0 and (
            not new.is_file() or new.is_symlink() or current.returncode != 0
            or current.stdout.strip() != old.stdout.strip()
        ):
            modified.append(path)
    return paths, modified


def intervention_evidence(repo: Path, before: str, kind: str, files: dict[str, bytes],
                          features: list[dict], git) -> tuple[list[str], dict]:
    """Check real diff/spec hash locators; semantic contradiction review stays external."""
    paths, modified = test_changes(repo, before, git)
    changed = git(repo, "diff", "--name-only", before, "HEAD").stdout.splitlines()
    required = set(paths)
    if kind == "repair":
        required.update(path for path in changed if path.startswith("src/") and path.endswith(".py"))
    violations = []
    if modified and kind != "repair":
        violations.append("accepted agent-authored tests changed: " + ", ".join(modified))
    evidence_name = "REPAIR_EVIDENCE.json" if kind == "repair" else "TEST_EVIDENCE.json"
    summary = {"evidence_file": evidence_name, "diff_before": before,
               "diff_after": git(repo, "rev-parse", "HEAD").stdout.strip(),
               "required_paths": sorted(required), "observed_paths": [], "unknown_paths": sorted(required),
               "semantic_review": "unreviewed: candidate rationale is not proof of specification consistency"}
    if not required:
        return violations, summary
    evidence_path = repo / evidence_name
    if not evidence_path.is_file() or evidence_path.is_symlink():
        violations.append(f"missing {evidence_name} for changed code/tests")
        return violations, summary
    try:
        document = json.loads(evidence_path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as error:
        violations.append(f"invalid {evidence_name}: {type(error).__name__}")
        return violations, summary
    if (not isinstance(document, dict) or set(document) != {"changes"}
            or not isinstance(document["changes"], list)):
        violations.append(f"invalid {evidence_name} schema")
        return violations, summary
    field_names = {"path", "before_sha256", "after_sha256", "specification", "spec_sha256",
                   "rule", "rationale"}
    rules = {f"specifications/{feature['id']}.md": len(feature["rules"]) for feature in features}
    observed = set()
    for entry in document["changes"]:
        if not isinstance(entry, dict) or set(entry) != field_names:
            violations.append(f"invalid change locator in {evidence_name}")
            continue
        path, spec = entry["path"], entry["specification"]
        if not isinstance(path, str) or not isinstance(spec, str):
            violations.append("change evidence paths must be strings")
            continue
        if path not in required or path in observed or spec not in rules or spec not in files:
            violations.append("change evidence does not identify one changed path and a released specification")
            continue
        old = git(repo, "show", f"{before}:{path}", check=False)
        previous_hash = hashlib.sha256(old.stdout.encode()).hexdigest() if old.returncode == 0 else None
        new = repo / path
        current_hash = hashlib.sha256(new.read_bytes()).hexdigest() if new.is_file() else None
        if (entry["before_sha256"] != previous_hash or entry["after_sha256"] != current_hash
                or entry["spec_sha256"] != hashlib.sha256(files[spec]).hexdigest()
                or type(entry["rule"]) is not int or not 1 <= entry["rule"] <= rules[spec]
                or not isinstance(entry["rationale"], str) or not entry["rationale"].strip()):
            violations.append("change evidence hash/rule/rationale mismatch")
            continue
        observed.add(path)
    summary.update(observed_paths=sorted(observed), unknown_paths=sorted(required - observed))
    if required - observed:
        violations.append(f"unbound changed paths in {evidence_name}: " + ", ".join(sorted(required - observed)))
    return violations, summary
