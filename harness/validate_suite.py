"""Test the tests: check a suite against its reference implementation before freezing it.

For each ready feature k it checks that
  1. every visible and hidden test of F1..Fk passes on reference/fk (the tests are achievable), and
  2. the hidden tests of Fk mostly fail on reference/f(k-1) (they really test the new feature).
Usage: python3 validate_suite.py ../suites/s1-retrofit
"""
import glob
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import stdlib_tests  # noqa: E402


def run_isolated(test_files, ref_pkg_dir):
    """Run tests in a subprocess-free but module-isolated way: copy the package to a temp src dir."""
    import subprocess
    tmp = tempfile.mkdtemp(prefix="validate-")
    src = os.path.join(tmp, "src")
    os.makedirs(src)
    if ref_pkg_dir:
        shutil.copytree(ref_pkg_dir, os.path.join(src, "workbench"))
    tdir = os.path.join(tmp, "t")
    os.makedirs(tdir)
    for f in test_files:
        shutil.copy(f, tdir)
    out = os.path.join(tmp, "r.json")
    subprocess.run([sys.executable, os.path.join(HERE, "stdlib_tests.py"), tdir, "--src", src, "--json", out, "-q"],
                   capture_output=True, text=True)
    res = json.load(open(out))["tests"]
    shutil.rmtree(tmp, ignore_errors=True)
    return res


def main():
    suite_dir = os.path.abspath(sys.argv[1])
    suite = json.load(open(os.path.join(suite_dir, "suite.json")))
    ok = True
    for k, f in enumerate(suite["features"], 1):
        if f.get("status") != "ready":
            print(f"{f['id']}: {f.get('status')}")
            continue
        ref = os.path.join(suite_dir, "reference", f["id"], "workbench")
        files = []
        for g in suite["features"][:k]:
            files += glob.glob(os.path.join(suite_dir, "features", g["id"], "examples", "*.py"))
            files += glob.glob(os.path.join(suite_dir, "features", g["id"], "hidden", "*.py"))
        res = run_isolated(files, ref)
        bad = [t for t, o in res.items() if o != "passed"]
        hidden_k = glob.glob(os.path.join(suite_dir, "features", f["id"], "hidden", "*.py"))
        prev = os.path.join(suite_dir, "reference", suite["features"][k - 2]["id"], "workbench") if k > 1 else None
        res_prev = run_isolated(hidden_k, prev)
        passing_without = [t for t, o in res_prev.items() if o == "passed"]
        n_hidden = len(res_prev)
        import_error = all(t.endswith("::<import>") for t in res_prev)
        status = "OK" if not bad else "FAIL"
        ok = ok and not bad
        weak = "all new hidden tests fail without the feature (its API does not exist yet)" if import_error else \
            f"{len(passing_without)}/{n_hidden} new hidden tests already pass without the feature"
        print(f"{f['id']}: {len(res) - len(bad)}/{len(res)} cumulative tests pass on the reference [{status}]; {weak}")
        for t in bad:
            print(f"   failing on reference: {t}")
        for t in passing_without:
            print(f"   weak (passes without the feature): {t}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
