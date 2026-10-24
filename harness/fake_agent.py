"""Offline stand-in for the coding agent, used only to dry-run the pipeline.

It recognises the step from the prompt and applies the suite's reference solution (feature steps),
writes DESIGN.md through ./tcr (consolidation), or writes REVIEW.md and deliberately touches a
source file (review-only, to exercise the runner's enforcement). Environment switches:
FAKE_FAIL_FEATURE=k commits broken code at feature k; FAKE_TAMPER_FEATURE=k edits an example test.
"""
import argparse
import os
import re
import shutil
import subprocess


def sh(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--repo", required=True)
    ap.add_argument("--suite", required=True)
    a = ap.parse_args()
    p, repo = a.prompt, a.repo
    m = re.search(r"implementing feature (\d+) of", p)
    if m:
        k = int(m.group(1))
        ref = os.path.join(a.suite, "reference", f"f{k:02d}", "workbench")
        dst = os.path.join(repo, "src", "workbench")
        if os.path.isdir(ref):
            shutil.rmtree(dst)
            shutil.copytree(ref, dst)
        if os.environ.get("FAKE_FAIL_FEATURE") == str(k):
            with open(os.path.join(dst, "__init__.py"), "a") as f:
                f.write("\nraise RuntimeError('broken on purpose')\n")
            sh("git add -A && git commit -q -m 'feature (broken)'", repo)
            print("committed a broken feature on purpose")
            return
        if os.environ.get("FAKE_TAMPER_FEATURE") == str(k):
            ex = sorted(f for f in os.listdir(os.path.join(repo, "tests", "examples")) if f.startswith(f"test_f{k:02d}"))
            with open(os.path.join(repo, "tests", "examples", ex[0]), "a") as f:
                f.write("\n# weakened on purpose\n")
        r = sh("make -s test", repo)
        if r.returncode == 0:
            sh(f"git add -A && git commit -q -m 'feature {k}'", repo)
            print(f"feature {k} committed")
        else:
            print(f"feature {k}: tests fail, not committing\n{r.stdout[-500:]}")
    elif "Do not add or change features" in p:
        with open(os.path.join(repo, "DESIGN.md"), "w") as f:
            f.write("# Design\n\nAll rules live in src/workbench/__init__.py. Known debt: one module.\n")
        r = sh("./tcr 'design note'", repo)
        print(r.stdout, r.stderr)
    elif "Do not change any code or tests" in p:
        with open(os.path.join(repo, "REVIEW.md"), "w") as f:
            f.write("# Review\n\nOne large module; validation duplicated between add_home and CSV import.\n")
        with open(os.path.join(repo, "src", "workbench", "__init__.py"), "a") as f:
            f.write("\n# a change the review step is not allowed to make\n")
        sh("git add -A && git commit -q -m 'review'", repo)
        print("review written (and an illegal code change, to test enforcement)")
    else:
        print("change request: no canned solution in the dry run")


if __name__ == "__main__":
    main()
