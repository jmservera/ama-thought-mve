"""Measure one experiment step from outside the agent: hidden tests, code metrics, integrity, diff size.

Usage (normally called by runner.py):
  python3 measure.py --repo R --suite S --k K [--cr] --prev-ref REF --out out.json
                     [--runner pytest|stdlib] [--complexity lizard|internal] [--duplication jscpd|internal] [--lint ruff|none]
"""
import argparse
import ast
import glob
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

from evaluation_env import evaluation_environment
from failure_attribution import api_policy

HERE = os.path.dirname(os.path.abspath(__file__))


class HiddenResults(dict):
    """Keep the established identity/outcome mapping API and private evidence."""

    def __init__(self, outcomes, provenance):
        super().__init__(outcomes)
        self.provenance = provenance


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def suite_items(suite_dir, k, cr):
    suite = json.load(open(os.path.join(suite_dir, "suite.json"), encoding="utf-8"))
    ids = [f["id"] for f in suite["features"][:k]]
    if cr:
        ids.append(suite["change_request"]["id"])
    return ids


def _class_tests(node, classes, module, ancestors=()):
    if node.name in ancestors:
        raise ValueError(f"Cyclic test class inheritance: {module}::{node.name}")
    methods = {method.name for method in node.body
               if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
               and method.name.startswith("test")}
    is_test_case = False
    for base in node.bases:
        base_name = getattr(base, "id", getattr(base, "attr", None))
        is_test_case = is_test_case or base_name == "TestCase"
        if isinstance(base, ast.Name) and base_name in classes:
            inherited, inherited_case = _class_tests(classes[base_name], classes, module, ancestors + (node.name,))
            methods.update(inherited)
            is_test_case = is_test_case or inherited_case
    return methods, is_test_case


def expected_tests(files):
    """Discover fixed test identities without importing candidate-dependent modules."""
    ids = []
    for path in files:
        mod = os.path.splitext(os.path.basename(path))[0]
        if not mod.startswith("test"):
            continue
        with open(path, encoding="utf-8") as source:
            tree = ast.parse(source.read(), filename=path)
        classes = {node.name: node for node in tree.body if isinstance(node, ast.ClassDef)}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                ids.append(f"{mod}::{node.name}")
            elif isinstance(node, ast.ClassDef):
                methods, is_test_case = _class_tests(node, classes, mod)
                if node.name.startswith("Test") or is_test_case:
                    ids.extend(f"{mod}::{node.name}::{method}" for method in sorted(methods))
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate discovered test identities")
    return ids


def validated_results(results, expected):
    """Map exact identities to the fixed denominator; collection errors leave tests unrun."""
    if not expected or not isinstance(results, dict) or not results:
        raise RuntimeError("Test runner produced no test results")
    modules = {test.split("::", 1)[0] for test in expected}
    collection_errors = {f"{module}::<import>" for module in modules}
    for test, outcome in results.items():
        if not isinstance(test, str) or outcome not in ("passed", "failed", "error", "skipped", "timeout"):
            raise RuntimeError("Test runner produced malformed test results")
        if test not in expected and not (test in collection_errors and outcome == "error"):
            raise RuntimeError(f"Test runner reported an unexpected test identity: {test}")
    return {test: results.get(test, "error") for test in expected}


def attributed_results(raw, expected, provenance):
    result = validated_results(raw, expected)
    if not isinstance(provenance, dict) or set(provenance) - set(raw):
        raise RuntimeError("Test runner produced malformed provenance")
    evidence = {}
    for key, record in provenance.items():
        if (key not in raw or not isinstance(record, dict) or record.get("raw_outcome") != raw[key]
                or record.get("outcome") not in ("passed", "failed", "error", "skipped", "timeout")
                or not isinstance(record.get("attribution"), str)
                or not isinstance(record.get("diagnostic"), str)):
            raise RuntimeError("Test runner produced malformed provenance")
    for identity in expected:
        collection = identity.split("::", 1)[0] + "::<import>"
        source = identity if identity in raw else collection
        record = provenance.get(source)
        if record:
            result[identity] = record["outcome"]
            evidence[identity] = {**record, "reported_identity": source}
        else:
            evidence[identity] = {"raw_outcome": raw.get(source, "error"), "outcome": result[identity],
                                  "attribution": "runner_status", "diagnostic": ""}
    return HiddenResults(result, evidence)


def load_stdlib_results(path, expected):
    try:
        with open(path, encoding="utf-8") as report:
            payload = json.load(report)
    except (OSError, ValueError) as error:
        raise RuntimeError("Test runner did not produce a readable JSON report") from error
    if not isinstance(payload, dict):
        raise RuntimeError("Test runner produced a malformed JSON report")
    raw = payload.get("tests")
    validated_results(raw, expected)
    return attributed_results(raw, expected, payload.get("provenance", {}))


def run_hidden(repo, suite_dir, ids, runner, timeout=600, scratch_dir=None):
    if not ids or runner not in ("pytest", "stdlib"):
        raise ValueError("Hidden evaluation requires suite items and a supported test runner")
    repo = os.path.abspath(repo)
    src = os.path.join(repo, "src")
    with tempfile.TemporaryDirectory(prefix=".hidden-", dir=scratch_dir or os.path.dirname(repo)) as tmp, \
            evaluation_environment() as env:
        files = []
        names = set()
        for fid in ids:
            feature_files = sorted(glob.glob(os.path.join(
                suite_dir, "features" if not fid.startswith("cr") else "", fid, "hidden", "*.py")))
            if not expected_tests(feature_files):
                raise ValueError(f"{fid}: no discovered hidden tests")
            for path in feature_files:
                name = os.path.basename(path)
                if name in names:
                    raise ValueError(f"Duplicate hidden test filename: {name}")
                names.add(name)
                shutil.copy(path, tmp)
                files.append(path)
        expected = expected_tests(files)
        policy_path = os.path.join(tmp, "policy.json")
        with open(policy_path, "w", encoding="utf-8") as policy_file:
            json.dump(api_policy(suite_dir, ids), policy_file)
        if runner == "pytest":
            xml = os.path.join(tmp, "junit.xml")
            provenance_path = os.path.join(tmp, "provenance.json")
            bootstrap = (
                "import importlib.util, json, sys, pytest; "
                "helper, src, policy, output = sys.argv[1:5]; "
                "spec = importlib.util.spec_from_file_location('_mve_failure_attribution', helper); "
                "module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); "
                "plugin = module.pytest_plugin(src, json.load(open(policy)), output); "
                "sys.path.insert(0, src); raise SystemExit(pytest.main(sys.argv[5:], plugins=[plugin]))"
            )
            cmd = [sys.executable, "-I", "-B", "-c", bootstrap,
                   os.path.join(HERE, "failure_attribution.py"), src, policy_path, provenance_path,
                   "-q", "-p", "no:cacheprovider",
                   "--continue-on-collection-errors", f"--junit-xml={xml}", tmp]
            if importlib.util.find_spec("pytest_timeout"):
                cmd[-1:-1] = ["-p", "pytest_timeout", "--timeout=10"]
        else:
            js = os.path.join(tmp, "res.json")
            cmd = [sys.executable, "-I", "-B", os.path.join(HERE, "stdlib_tests.py"), tmp,
                   "--src", src, "--json", js, "--policy", policy_path, "-q"]
        try:
            process = subprocess.run(cmd, cwd=tmp, env=env, capture_output=True, text=True, timeout=timeout)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RuntimeError(f"Hidden {runner} subprocess failed") from error
        if process.returncode not in (0, 1):
            raise RuntimeError(f"Hidden {runner} exited with code {process.returncode}")
        if runner == "pytest":
            try:
                root = ET.parse(xml).getroot()
            except (OSError, ET.ParseError) as error:
                raise RuntimeError("Hidden pytest did not produce a readable JUnit report") from error
            if root.tag not in ("testsuite", "testsuites"):
                raise RuntimeError("Hidden pytest produced a malformed JUnit report")
            out = {}
            for case in root.iter("testcase"):
                classname = case.get("classname", "")
                name = case.get("name", "")
                key = f"{classname.replace('.', '::')}::{name}"
                outcome = "error" if case.find("error") is not None else \
                    "failed" if case.find("failure") is not None else \
                    "skipped" if case.find("skipped") is not None else "passed"
                if not classname and outcome == "error":
                    key = f"{name.removesuffix('.py')}::<import>"
                if key in out:
                    raise RuntimeError(f"Hidden pytest reported a duplicate test identity: {key}")
                out[key] = outcome
            result = validated_results(out, expected)
            # Validate the raw report/exit agreement before any scientific reclassification.
            raw_not_passed = any(value in ("failed", "error", "timeout") for value in result.values())
            if (process.returncode == 0 and raw_not_passed) or (process.returncode == 1 and not raw_not_passed):
                raise RuntimeError(f"Hidden {runner} exit status disagrees with its test report")
            provenance = {}
            for case in root.iter("testcase"):
                problem = case.find("error")
                if problem is None:
                    problem = case.find("failure")
                if problem is not None:
                    classname, name = case.get("classname", ""), case.get("name", "")
                    key = f"{classname.replace('.', '::')}::{name}" if classname else \
                        f"{name.removesuffix('.py')}::<import>"
                    provenance[key] = {
                        "raw_outcome": out[key], "outcome": "error", "attribution": "unknown",
                        "diagnostic": problem.text or problem.get("message", ""),
                    }
            if os.path.isfile(provenance_path):
                try:
                    with open(provenance_path, encoding="utf-8") as report:
                        captured = json.load(report)["provenance"]
                    if not isinstance(captured, dict):
                        raise TypeError("Malformed provenance records")
                    provenance.update(captured)
                except (OSError, ValueError, KeyError, TypeError) as error:
                    raise RuntimeError("Hidden pytest produced malformed provenance") from error
            result = attributed_results(out, expected, provenance)
        else:
            result = load_stdlib_results(js, expected)
        not_passed = any(outcome in ("failed", "error", "timeout") for outcome in result.values())
        if (process.returncode == 0 and not_passed) or (process.returncode == 1 and not not_passed):
            raise RuntimeError(f"Hidden {runner} exit status disagrees with its test report")
        return result


def integrity(repo, suite_dir, ids):
    modified, missing = [], []
    for fid in ids:
        base = os.path.join(suite_dir, "features" if not fid.startswith("cr") else "", fid, "examples")
        for p in glob.glob(os.path.join(base, "*.py")):
            target = os.path.join(repo, "tests", "examples", os.path.basename(p))
            if not os.path.exists(target):
                missing.append(os.path.basename(p))
            elif sha256(target) != sha256(p):
                modified.append(os.path.basename(p))
    return {"modified": sorted(modified), "missing": sorted(missing)}


def test_counts(repo):
    tests = asserts = 0
    for p in glob.glob(os.path.join(repo, "tests", "**", "*.py"), recursive=True):
        try:
            tree = ast.parse(open(p, encoding="utf-8").read())
        except SyntaxError as error:
            raise ValueError(f"Cannot count invalid Python tests: {p}") from error
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
                tests += 1
            elif isinstance(node, ast.Assert):
                asserts += 1
            elif isinstance(node, ast.Call) and getattr(node.func, "attr", "").startswith("assert"):
                asserts += 1
    return {"tests": tests, "asserts": asserts}


def diff_stats(repo, prev_ref):
    if not prev_ref:
        return None
    with evaluation_environment() as env:
        r = subprocess.run(["git", "-c", f"safe.directory={os.path.abspath(repo)}",
                            "diff", "--numstat", prev_ref, "HEAD"], cwd=repo, capture_output=True, text=True,
                           env=env, check=False)
    if r.returncode != 0:
        raise RuntimeError(f"git diff exited with code {r.returncode}")
    stats = {"src": [0, 0], "tests": [0, 0], "docs": [0, 0], "other": [0, 0]}
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 3:
            raise RuntimeError("git diff produced malformed numstat output")
        if parts[0] == "-":
            continue
        add, rem, path = int(parts[0]), int(parts[1]), parts[2]
        kind = "src" if path.startswith("src/") else "tests" if path.startswith("tests/") else \
            "docs" if path.endswith(".md") else "other"
        stats[kind][0] += add
        stats[kind][1] += rem
    return {k: {"added": v[0], "removed": v[1]} for k, v in stats.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--suite", required=True)
    ap.add_argument("--k", type=int, required=True)
    ap.add_argument("--cr", action="store_true")
    ap.add_argument("--prev-ref")
    ap.add_argument("--out", required=True)
    ap.add_argument("--scratch-dir", help="Trusted writable evaluator scratch directory")
    ap.add_argument("--runner", default="pytest", choices=["pytest", "stdlib"])
    ap.add_argument("--complexity", default="lizard")
    ap.add_argument("--duplication", default="jscpd")
    ap.add_argument("--lint", default="ruff")
    a = ap.parse_args()
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "skeleton", "tools"))
    from metrics_core import measure as code_metrics  # noqa: E402

    ids = suite_items(a.suite, a.k, a.cr)
    hidden = run_hidden(a.repo, a.suite, ids, a.runner,
                        **({"scratch_dir": a.scratch_dir} if a.scratch_dir else {}))
    m = code_metrics(a.repo, a.complexity, a.duplication, a.lint)
    with evaluation_environment() as env:
        head_result = subprocess.run(["git", "-c", f"safe.directory={os.path.abspath(a.repo)}",
                                      "rev-parse", "--verify", "HEAD"], cwd=a.repo, capture_output=True,
                                     text=True, env=env, check=False)
    if head_result.returncode != 0 or not head_result.stdout.strip():
        raise RuntimeError("git rev-parse did not produce a valid HEAD")
    head = head_result.stdout.strip()
    result = {
        "head": head,
        "k": a.k,
        "cr": a.cr,
        "hidden": hidden,
        "hidden_provenance": getattr(hidden, "provenance", {}),
        "hidden_passed": sum(1 for v in hidden.values() if v == "passed"),
        "hidden_total": len(hidden),
        "metrics": {k: v for k, v in m.items() if not k.startswith("_")},
        "integrity": integrity(a.repo, a.suite, ids),
        "test_counts": test_counts(a.repo),
        "diff": diff_stats(a.repo, a.prev_ref),
        "test_runner": a.runner,
        "evaluation": {"execution": "local_subprocess", "environment": "allowlisted_subprocesses",
                       "os_isolated": False, "network_isolated": False},
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    print(f"hidden {result['hidden_passed']}/{result['hidden_total']}, mean CC {result['metrics']['mean_ccn']}, "
          f"dup {result['metrics']['dup_pct']}%, lint {result['metrics']['lint_warnings']}")


if __name__ == "__main__":
    main()
