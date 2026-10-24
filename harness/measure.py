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

HERE = os.path.dirname(os.path.abspath(__file__))


def sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def suite_items(suite_dir, k, cr):
    suite = json.load(open(os.path.join(suite_dir, "suite.json"), encoding="utf-8"))
    ids = [f["id"] for f in suite["features"][:k]]
    if cr:
        ids.append(suite["change_request"]["id"])
    return ids


def expected_tests(files):
    """Every hidden test id (module::function), so that a module that fails to import counts all its tests."""
    ids = []
    for p in files:
        mod = os.path.splitext(os.path.basename(p))[0]
        tree = ast.parse(open(p, encoding="utf-8").read())
        ids += [f"{mod}::{n.name}" for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test")]
    return ids


def run_hidden(repo, suite_dir, ids, runner, timeout=600):
    tmp = tempfile.mkdtemp(prefix="hidden-")
    files = []
    for fid in ids:
        for p in glob.glob(os.path.join(suite_dir, "features" if not fid.startswith("cr") else "", fid, "hidden", "*.py")):
            shutil.copy(p, tmp)
            files.append(p)
    expected = expected_tests(files)
    src = os.path.join(repo, "src")
    env = dict(os.environ, PYTHONPATH=src, PYTHONDONTWRITEBYTECODE="1")
    out = {}
    try:
        if runner == "pytest":
            xml = os.path.join(tmp, "junit.xml")
            cmd = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", f"--junit-xml={xml}", tmp]
            if importlib.util.find_spec("pytest_timeout"):
                cmd.insert(-1, "--timeout=10")  # signal method: a hung test fails, the run and the XML survive
            subprocess.run(cmd, cwd=tmp, env=env, capture_output=True, text=True, timeout=timeout)
            for tc in ET.parse(xml).getroot().iter("testcase"):
                mod = [c for c in tc.get("classname", "").split(".") if c.startswith("test")]
                key = f"{mod[-1] if mod else tc.get('classname')}::{tc.get('name')}"
                if tc.find("failure") is not None:
                    out[key] = "failed"
                elif tc.find("error") is not None:
                    out[key] = "error"
                elif tc.find("skipped") is not None:
                    out[key] = "skipped"
                else:
                    out[key] = "passed"
        else:
            js = os.path.join(tmp, "res.json")
            subprocess.run([sys.executable, os.path.join(HERE, "stdlib_tests.py"), tmp, "--src", src, "--json", js, "-q"],
                           cwd=tmp, env=env, capture_output=True, text=True, timeout=timeout)
            out = json.load(open(js, encoding="utf-8"))["tests"]
    except subprocess.TimeoutExpired:
        out = {}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    # Fixed denominator: tests that never ran (import or collection error, timeout) count as errors.
    return {t: out.get(t, "error") for t in expected}


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
        except SyntaxError:
            continue
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
    r = subprocess.run(["git", "diff", "--numstat", prev_ref, "HEAD"], cwd=repo, capture_output=True, text=True)
    stats = {"src": [0, 0], "tests": [0, 0], "docs": [0, 0], "other": [0, 0]}
    for line in r.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or parts[0] == "-":
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
    ap.add_argument("--runner", default="pytest", choices=["pytest", "stdlib"])
    ap.add_argument("--complexity", default="lizard")
    ap.add_argument("--duplication", default="jscpd")
    ap.add_argument("--lint", default="ruff")
    a = ap.parse_args()
    sys.path.insert(0, os.path.join(os.path.dirname(HERE), "skeleton", "tools"))
    from metrics_core import measure as code_metrics  # noqa: E402

    ids = suite_items(a.suite, a.k, a.cr)
    hidden = run_hidden(a.repo, a.suite, ids, a.runner)
    m = code_metrics(a.repo, a.complexity, a.duplication, a.lint)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=a.repo, capture_output=True, text=True).stdout.strip()
    result = {
        "head": head,
        "k": a.k,
        "cr": a.cr,
        "hidden": hidden,
        "hidden_passed": sum(1 for v in hidden.values() if v == "passed"),
        "hidden_total": len(hidden),
        "metrics": {k: v for k, v in m.items() if not k.startswith("_")},
        "integrity": integrity(a.repo, a.suite, ids),
        "test_counts": test_counts(a.repo),
        "diff": diff_stats(a.repo, a.prev_ref),
        "test_runner": a.runner,
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=1)
    print(f"hidden {result['hidden_passed']}/{result['hidden_total']}, mean CC {result['metrics']['mean_ccn']}, "
          f"dup {result['metrics']['dup_pct']}%, lint {result['metrics']['lint_warnings']}")


if __name__ == "__main__":
    main()
