"""Test the tests: check a suite against its reference implementation before freezing it.

For every feature k in a complete, ready suite it checks that
  1. every visible and hidden test of F1..Fk passes on reference/fk (the tests are achievable), and
    2. prior-reference passes are reported for coverage review, not rejected automatically.
Usage: python3 validate_suite.py ../suites/s1-retrofit
"""
import argparse
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from evaluation_env import evaluation_environment  # noqa: E402
from measure import expected_tests, load_stdlib_results  # noqa: E402


def run_isolated(test_files, ref_pkg_dir):
    """Copy a reference into a local child process; host and network access are not isolated."""
    expected = expected_tests(test_files)
    if not expected:
        raise ValueError("No discovered tests to validate")
    if ref_pkg_dir is not None and not os.path.isdir(ref_pkg_dir):
        raise ValueError(f"Reference package is missing: {ref_pkg_dir}")
    with tempfile.TemporaryDirectory(prefix="validate-") as tmp, evaluation_environment() as env:
        src = os.path.join(tmp, "src")
        os.makedirs(src)
        if ref_pkg_dir is not None:
            shutil.copytree(ref_pkg_dir, os.path.join(src, "workbench"))
        tdir = os.path.join(tmp, "t")
        os.makedirs(tdir)
        names = set()
        for path in test_files:
            name = os.path.basename(path)
            if name in names:
                raise ValueError(f"Duplicate test filename: {name}")
            names.add(name)
            shutil.copy(path, tdir)
        out = os.path.join(tmp, "r.json")
        command = [sys.executable, "-I", "-B", os.path.join(HERE, "stdlib_tests.py"), tdir,
                   "--src", src, "--json", out, "-q"]
        try:
            process = subprocess.run(command, cwd=tmp, env=env, capture_output=True, text=True, timeout=600)
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RuntimeError("Reference test subprocess failed") from error
        if process.returncode not in (0, 1):
            raise RuntimeError(f"Reference test subprocess exited with code {process.returncode}")
        result = load_stdlib_results(out, expected)
        not_passed = any(outcome in ("failed", "error", "timeout") for outcome in result.values())
        if (process.returncode == 0 and not_passed) or (process.returncode == 1 and not not_passed):
            raise RuntimeError("Reference test subprocess exit status disagrees with its test report")
        return result


def item_tests(suite_dir, item, kind="features"):
    if item.get("status") != "ready":
        raise ValueError(f"{item.get('id', 'change request')}: not ready ({item.get('status')})")
    groups = []
    for folder, audience in (("examples", "visible"), ("hidden", "hidden")):
        files = sorted(glob.glob(os.path.join(suite_dir, kind, item["id"], folder, "*.py")))
        if not expected_tests(files):
            raise ValueError(f"{item['id']}: no discovered {audience} tests")
        groups.append(files)
    return groups


def reference_package(suite_dir, item_id):
    path = os.path.join(suite_dir, "reference", item_id, "workbench")
    if not os.path.isdir(path):
        raise ValueError(f"{item_id}: reference package is missing: {path}")
    return path


def run_repeated(files, reference, repeats):
    baseline = run_isolated(files, reference)
    for _ in range(repeats - 1):
        if run_isolated(files, reference) != baseline:
            raise RuntimeError("Oracle instability: repeated unchanged-reference outcomes differ")
    return baseline


def reference_metrics(suite_dir, suite, backends):
    """Unapproved raw reference metrics, with explicit diagnostic backend provenance."""
    sys.path.insert(0, str(Path(HERE).parent / "skeleton/tools"))
    from metrics_core import measure as code_metrics

    template = Path(HERE).parent / "skeleton/pyproject.toml"
    versions = {"python": sys.version.split()[0]}
    with evaluation_environment() as env:
        for backend in backends:
            if backend in ("lizard", "jscpd", "ruff"):
                version = subprocess.run([backend, "--version"], env=env, capture_output=True,
                                         text=True, timeout=60, check=False)
                versions[backend] = (version.stdout or version.stderr).strip() if version.returncode == 0 else None
    rows = []
    for item in suite["features"] + [suite["change_request"]]:
        reference = Path(reference_package(suite_dir, item["id"]))
        with tempfile.TemporaryDirectory(prefix="reference-metrics-") as directory:
            repo = Path(directory)
            shutil.copytree(reference, repo / "src/workbench")
            shutil.copyfile(template, repo / "pyproject.toml")
            metrics = code_metrics(str(repo), *backends)
        rows.append({"stage": item["id"], "metrics": metrics,
                     "reference_sha256": {path.relative_to(reference).as_posix():
                         hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in sorted(reference.rglob("*.py"))}})
    return {"status": "candidate-unreviewed", "accepted_for_gaps": False,
            "backends_requested": dict(zip(("complexity", "duplication", "lint"), backends)),
            "tool_versions": versions,
            "lint_config_sha256": hashlib.sha256(template.read_bytes()).hexdigest(),
            "metrics_code_sha256": hashlib.sha256(
                (Path(HERE).parent / "skeleton/tools/metrics_core.py").read_bytes()).hexdigest(),
            "rows": rows,
            "interpretation": "Raw original units only; matching versions/settings, coverage and independent acceptance required"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite")
    parser.add_argument("--repeats", type=int, default=1,
                        help="Diagnostic repeats; author must freeze the final count and failure policy")
    parser.add_argument("--reference-metrics", type=Path)
    parser.add_argument("--complexity", choices=["internal", "lizard"], default="lizard")
    parser.add_argument("--duplication", choices=["internal", "jscpd"], default="jscpd")
    parser.add_argument("--lint", choices=["none", "ruff"], default="ruff")
    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be positive")
    suite_dir = os.path.abspath(args.suite)
    try:
        with open(os.path.join(suite_dir, "suite.json"), encoding="utf-8") as source:
            suite = json.load(source)
        if not suite.get("features"):
            raise ValueError("Full-suite validation requires features")
        prepared = []
        for feature in suite["features"]:
            visible, hidden = item_tests(suite_dir, feature)
            prepared.append((feature, visible, hidden, reference_package(suite_dir, feature["id"])))
        cr = suite.get("change_request") or {}
        item_tests(suite_dir, cr, kind="")
        reference_package(suite_dir, cr["id"])
        ok = True
        files = []
        for index, (feature, visible, hidden, ref) in enumerate(prepared):
            files += visible + hidden
            res = run_repeated(files, ref, args.repeats)
            bad = [test for test, outcome in res.items() if outcome != "passed"]
            prev = prepared[index - 1][3] if index else None
            res_prev = run_repeated(hidden, prev, args.repeats)
            passing_without = [test for test, outcome in res_prev.items() if outcome == "passed"]
            status = "OK" if not bad else "FAIL"
            ok = ok and not bad
            print(f"{feature['id']}: {len(res) - len(bad)}/{len(res)} cumulative tests pass on the reference "
                  f"[{status}]; {len(passing_without)}/{len(res_prev)} new hidden tests already pass without "
                  "the feature (coverage diagnostic only)")
            for test in bad:
                print(f"   failing on reference: {test}")
            for test in passing_without:
                print(f"   prior-reference pass (review coverage): {test}")
        ok = check_change_request(suite_dir, suite, repeats=args.repeats) and ok
        if args.reference_metrics:
            if not ok:
                raise RuntimeError("Reference failures prevent metric evidence export")
            payload = reference_metrics(suite_dir, suite, (args.complexity, args.duplication, args.lint))
            payload["oracle_repeats"] = args.repeats
            payload["oracle_stability_accepted"] = False
            with args.reference_metrics.open("x", encoding="utf-8") as output:
                json.dump(payload, output, indent=2, allow_nan=False)
                output.write("\n")
    except (OSError, ValueError, SyntaxError, RuntimeError) as error:
        print(f"FAIL: {error}")
        sys.exit(1)
    sys.exit(0 if ok else 1)


def check_change_request(suite_dir, suite, repeats=1):
    """Check CR1 cumulatively and report prior-reference passes without rejecting valid edge cases."""
    cr = suite.get("change_request") or {}
    cr_visible, cr_hidden = item_tests(suite_dir, cr, kind="")
    if not suite.get("features"):
        raise ValueError("Change-request validation requires features")
    files = []
    for feature in suite["features"]:
        visible, hidden = item_tests(suite_dir, feature)
        files += visible + hidden
    res = run_repeated(files + cr_visible + cr_hidden, reference_package(suite_dir, cr["id"]), repeats)
    bad = [t for t, o in res.items() if o != "passed"]
    last = reference_package(suite_dir, suite["features"][-1]["id"])
    res_prev = run_repeated(cr_hidden, last, repeats)
    weak = [t for t, o in res_prev.items() if o == "passed"]
    print(f"{cr['id']}: {len(res) - len(bad)}/{len(res)} tests (all features plus the change request) pass on the "
          f"reference [{'OK' if not bad else 'FAIL'}]; {len(weak)}/{len(res_prev)} change-request hidden tests already "
          f"pass without it (coverage diagnostic only)")
    for t in bad:
        print(f"   failing on reference: {t}")
    for t in weak:
        print(f"   prior-reference pass (review coverage): {t}")
    return not bad


if __name__ == "__main__":
    main()
