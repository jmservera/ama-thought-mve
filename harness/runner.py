"""Run one arm of the feature-consolidation experiment on one suite.

Usage:
  python3 runner.py --config config.json --suite ../suites/s1-retrofit --arm A|B|C --run-id s1-A-01 \
                    [--features 8] [--phase pilot|first|main] [--no-cr] [--allow-draft]

Every step is a fresh agent session; context travels only through the repository. The runner
enforces the protocol: uncommitted work is discarded, a red head is reset, example tests are
restored if tampered with, and review-only steps may change nothing but REVIEW.md.
"""
import argparse
import datetime as dt
import glob
import json
import os
import shutil
import signal
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)


def sh(args, cwd, check=True, env=None):
    r = subprocess.run(args, cwd=cwd, capture_output=True, text=True, env=env)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(args)} failed: {r.stderr.strip()}")
    return r


def git(repo, *args, check=True):
    return sh(["git", *args], repo, check=check)


def head(repo):
    return git(repo, "rev-parse", "HEAD").stdout.strip()


def fmt_minutes(seconds):
    return f"{round(seconds / 60)} minutes"


def load_prompt(name):
    text = open(os.path.join(HERE, "prompts", name), encoding="utf-8").read()
    lines = [l for l in text.splitlines() if not l.startswith("<!--")]
    if lines and lines[0].startswith("# "):
        lines = lines[1:]
    return "\n".join(lines).strip() + "\n"


def render(template, values):
    out = template
    for k, v in values.items():
        out = out.replace("{" + k + "}", str(v))
    return out


class Run:
    def __init__(self, a):
        self.cfg = json.load(open(a.config, encoding="utf-8"))
        self.suite_dir = os.path.abspath(a.suite)
        self.suite = json.load(open(os.path.join(self.suite_dir, "suite.json"), encoding="utf-8"))
        self.arm = a.arm
        self.run_id = a.run_id
        self.phase = a.phase
        self.n = a.features or self.cfg.get("features", 10)
        runs_dir = self.cfg.get("runs_dir", "../runs")
        runs_dir = runs_dir if os.path.isabs(runs_dir) else os.path.join(HERE, runs_dir)
        self.dir = os.path.abspath(os.path.join(runs_dir, a.run_id))
        self.repo = os.path.join(self.dir, "repo")
        self.do_cr = not a.no_cr
        feats = self.suite["features"][: self.n]
        items = feats + ([self.suite["change_request"]] if self.do_cr else [])
        not_ready = [f["id"] for f in items if f.get("status") != "ready"]
        if not_ready and not a.allow_draft:
            sys.exit(f"Suite items not ready: {', '.join(not_ready)}. Finish and freeze them first (or use --no-cr / --features).")
        if len(feats) < self.n:
            sys.exit(f"Suite has only {len(feats)} features")
        self.features = feats
        self.budgets = self.cfg["budgets_seconds"]
        os.environ.setdefault("MVE_HARNESS", HERE)
        self.env_extra = {k: os.path.expandvars(v) for k, v in self.cfg.get("env", {}).items()}
        self.steps_path = os.path.join(self.dir, "steps.jsonl")

    # ------------------------------------------------------------------ setup
    def setup(self):
        if os.path.exists(self.dir):
            sys.exit(f"Run directory exists: {self.dir}")
        os.makedirs(self.dir)
        shutil.copytree(os.path.join(KIT, "skeleton"), self.repo)
        tcr = os.path.join(self.repo, "tcr")
        os.chmod(tcr, 0o755)  # zip files and synced folders often drop the executable bit
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.name", "mve-agent")
        git(self.repo, "config", "user.email", "mve-agent@example.invalid")
        git(self.repo, "add", "-A")
        git(self.repo, "update-index", "--chmod=+x", "tcr")
        git(self.repo, "commit", "-q", "-m", "skeleton")
        versions = {}
        for name, cmd in self.cfg.get("version_commands", {}).items():
            try:
                r = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=60)
                versions[name] = (r.stdout or r.stderr).strip()[:500]
            except Exception as e:  # noqa: BLE001
                versions[name] = f"unavailable: {e}"
        meta = {"run_id": self.run_id, "arm": self.arm, "phase": self.phase, "suite": self.suite["name"],
                "features": self.n, "change_request": self.do_cr, "started": dt.datetime.now(dt.timezone.utc).isoformat(),
                "config": self.cfg, "versions": versions}
        json.dump(meta, open(os.path.join(self.dir, "run.json"), "w", encoding="utf-8"), indent=1)

    # ------------------------------------------------------------------ helpers
    def env(self):
        e = dict(os.environ)
        e.update(self.env_extra)
        return e

    def is_green(self):
        r = subprocess.run(["make", "-s", "test"], cwd=self.repo, capture_output=True, text=True, env=self.env(),
                           timeout=600)
        return r.returncode == 0

    def discard_uncommitted(self):
        git(self.repo, "reset", "-q", "--hard")
        git(self.repo, "clean", "-qfd")

    def copy_examples(self, item, kind="features"):
        src = os.path.join(self.suite_dir, kind, item["id"], "examples") if kind else ""
        files = sorted(glob.glob(os.path.join(src, "*.py")))
        for p in files:
            shutil.copy(p, os.path.join(self.repo, "tests", "examples"))
        return [os.path.basename(p) for p in files]

    def restore_examples(self, upto_ids):
        changed = []
        for fid in upto_ids:
            kind = "features" if not fid.startswith("cr") else ""
            for p in glob.glob(os.path.join(self.suite_dir, kind, fid, "examples", "*.py")):
                target = os.path.join(self.repo, "tests", "examples", os.path.basename(p))
                if not os.path.exists(target) or open(target, "rb").read() != open(p, "rb").read():
                    shutil.copy(p, target)
                    changed.append(os.path.basename(p))
        return changed

    def run_agent(self, prompt, step_dir, budget):
        os.makedirs(step_dir, exist_ok=True)
        for sub in ("home", "copilot-home", "logs"):
            os.makedirs(os.path.join(step_dir, sub), exist_ok=True)
        open(os.path.join(step_dir, "prompt.md"), "w", encoding="utf-8").write(prompt)
        values = {"prompt": prompt, "repo": self.repo, "stepdir": step_dir, "logdir": os.path.join(step_dir, "logs"),
                  "transcript": os.path.join(step_dir, "transcript.md"), "usage": os.path.join(step_dir, "usage.json"),
                  "copilot_home": os.path.join(step_dir, "copilot-home"), "suite": self.suite_dir, "harness": HERE,
                  "uid": str(os.getuid()), "gid": str(os.getgid()),
                  **{k: str(v) for k, v in self.cfg.get("agent_values", {}).items()}}
        cmd = [render(x, values) for x in self.cfg["agent_command"]]
        env = self.env()
        env.update({k: render(v, values) for k, v in self.cfg.get("agent_env", {}).items()})
        t0 = time.time()
        with open(os.path.join(step_dir, "agent.stdout"), "w") as out, open(os.path.join(step_dir, "agent.stderr"), "w") as err:
            p = subprocess.Popen(cmd, cwd=self.repo, env=env, stdout=out, stderr=err, start_new_session=True)
            timed_out = False
            try:
                p.wait(timeout=budget)
            except subprocess.TimeoutExpired:
                timed_out = True
                os.killpg(p.pid, signal.SIGTERM)
                try:
                    p.wait(timeout=20)
                except subprocess.TimeoutExpired:
                    os.killpg(p.pid, signal.SIGKILL)
                    p.wait()
        usage = None
        if os.path.exists(values["usage"]):
            try:
                usage = json.load(open(values["usage"], encoding="utf-8"))
            except ValueError:
                usage = {"unparsed": open(values["usage"], encoding="utf-8").read()[:2000]}
        leak = self.leak_check(step_dir)
        return {"exit_code": p.returncode, "timed_out": timed_out, "seconds": round(time.time() - t0, 1),
                "usage": usage, "possible_leak": leak}

    def leak_check(self, step_dir):
        needles = [self.suite_dir, os.path.basename(self.suite_dir) + "/features", "/hidden/test_"]
        for name in ("transcript.md", "agent.stdout"):
            p = os.path.join(step_dir, name)
            if os.path.exists(p):
                text = open(p, encoding="utf-8", errors="replace").read()
                if any(n in text for n in needles):
                    return True
        return False

    def measure(self, k, step_dir, prev_ref, cr=False):
        m = self.cfg["measure"]
        out = os.path.join(step_dir, "measure.json")
        cmd = [sys.executable, os.path.join(HERE, "measure.py"), "--repo", self.repo, "--suite", self.suite_dir,
               "--k", str(k), "--out", out, "--runner", m["test_runner"], "--complexity", m["complexity"],
               "--duplication", m["duplication"], "--lint", m["lint"]]
        if prev_ref:
            cmd += ["--prev-ref", prev_ref]
        if cr:
            cmd.append("--cr")
        r = subprocess.run(cmd, capture_output=True, text=True, env=self.env())
        if r.returncode != 0:
            raise RuntimeError(f"measure failed: {r.stderr}")
        return json.load(open(out, encoding="utf-8"))

    def record(self, rec):
        rec.update({"run_id": self.run_id, "arm": self.arm, "phase": self.phase, "suite": self.suite["name"],
                    "time": dt.datetime.now(dt.timezone.utc).isoformat()})
        with open(self.steps_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        hm = rec.get("measure", {})
        print(f"[{self.run_id}] {rec['step']}: delivered={rec.get('delivered')} hidden={hm.get('hidden_passed')}/"
              f"{hm.get('hidden_total')} violations={rec.get('violations')}", flush=True)

    # ------------------------------------------------------------------ steps
    def feature_step(self, k, feat):
        step = f"f{k:02d}-feature"
        sd = os.path.join(self.dir, "steps", step)
        names = self.copy_examples(feat)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", f"runner: examples for {feat['id']}")
        git(self.repo, "tag", "-f", "feature-start")
        start = head(self.repo)
        rules = "\n".join(f"- {r}" for r in feat["rules"] + [f"API: {x}" for x in feat.get("api", [])])
        prompt = render(load_prompt("feature-step.prompt.md"), {
            "k": k, "N": self.n, "title": feat["title"], "user story": feat["story"], "rules": rules,
            "k:02d": f"{k:02d}", "feature_budget": fmt_minutes(self.budgets["feature"])})
        res = self.run_agent(prompt, sd, self.budgets["feature"])
        self.discard_uncommitted()
        violations = []
        restored = self.restore_examples([f["id"] for f in self.features[:k]])
        if restored:
            violations.append(f"examples modified: {', '.join(restored)}")
            git(self.repo, "add", "-A")
            git(self.repo, "commit", "-q", "-m", "runner: restore example tests")
        delivered = head(self.repo) != start and self.is_green()
        if not delivered:
            if head(self.repo) != start:
                violations.append("committed while tests failed; reset")
            git(self.repo, "reset", "-q", "--hard", start)
            if self.cfg.get("on_undelivered", "drop_examples") == "drop_examples":
                for n in names:
                    git(self.repo, "rm", "-q", os.path.join("tests", "examples", n))
                git(self.repo, "commit", "-q", "-m", f"runner: {feat['id']} not delivered; examples removed")
        git(self.repo, "tag", "-f", "feature-end")
        m = self.measure(k, sd, "feature-start")
        self.record({"step": step, "k": k, "kind": "feature", "delivered": delivered, "agent": res,
                     "violations": violations, "measure": m})

    def post_step(self, k):
        if self.arm == "A":
            return
        kind = "consolidation" if self.arm == "B" else "review"
        step = f"f{k:02d}-{kind}"
        sd = os.path.join(self.dir, "steps", step)
        before = head(self.repo)
        tmpl = "consolidation-step.prompt.md" if self.arm == "B" else "review-only-step.prompt.md"
        prompt = render(load_prompt(tmpl), {"consolidation_budget": fmt_minutes(self.budgets["post"])})
        res = self.run_agent(prompt, sd, self.budgets["post"])
        violations = []
        if self.arm == "C":
            review = None
            p = os.path.join(self.repo, "REVIEW.md")
            if os.path.exists(p):
                review = open(p, encoding="utf-8").read()
            changed = set(git(self.repo, "diff", "--name-only", before, "HEAD").stdout.split())
            changed |= {line[3:].strip() for line in git(self.repo, "status", "--porcelain").stdout.splitlines() if line.strip()}
            changed.discard("REVIEW.md")
            if changed:
                violations.append(f"review step changed other files: {', '.join(sorted(changed))[:300]}")
            git(self.repo, "reset", "-q", "--hard", before)
            git(self.repo, "clean", "-qfd")
            if review is not None:
                open(p, "w", encoding="utf-8").write(review)
                git(self.repo, "add", "REVIEW.md")
                git(self.repo, "commit", "-q", "-m", "runner: review notes", check=False)
        else:
            self.discard_uncommitted()
            restored = self.restore_examples([f["id"] for f in self.features[:k]])
            if restored:
                violations.append(f"examples modified: {', '.join(restored)}; consolidation reset")
                git(self.repo, "reset", "-q", "--hard", before)
            elif not self.is_green():
                violations.append("consolidation left the head red; reset")
                git(self.repo, "reset", "-q", "--hard", before)
        m = self.measure(k, sd, before)
        self.record({"step": step, "k": k, "kind": kind, "agent": res, "violations": violations, "measure": m,
                     "commits": int(git(self.repo, "rev-list", "--count", f"{before}..HEAD").stdout.strip() or 0)})

    def change_request(self):
        cr = self.suite["change_request"]
        step = f"{cr['id']}-change"
        sd = os.path.join(self.dir, "steps", step)
        names = self.copy_examples(cr, kind="")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "runner: examples for change request")
        start = head(self.repo)
        rules = "\n".join(f"- {r}" for r in cr["rules"] + [f"API: {x}" for x in cr.get("api", [])])
        prompt = render(load_prompt("change-request.prompt.md"), {
            "title": cr["title"], "user story": cr["story"], "rules": rules, "cr_id": cr["id"],
            "cr_budget": fmt_minutes(self.budgets["change_request"])})
        res = self.run_agent(prompt, sd, self.budgets["change_request"])
        self.discard_uncommitted()
        violations = []
        restored = self.restore_examples([f["id"] for f in self.features] + [cr["id"]])
        if restored:
            violations.append(f"examples modified: {', '.join(restored)}")
            git(self.repo, "add", "-A")
            git(self.repo, "commit", "-q", "-m", "runner: restore example tests")
        delivered = head(self.repo) != start and self.is_green()
        if not delivered:
            git(self.repo, "reset", "-q", "--hard", start)
        m = self.measure(self.n, sd, start, cr=True)
        self.record({"step": step, "k": self.n, "kind": "change_request", "delivered": delivered, "agent": res,
                     "violations": violations, "measure": m, "examples": names})

    def go(self):
        self.setup()
        for k, feat in enumerate(self.features, 1):
            self.feature_step(k, feat)
            self.post_step(k)
        if self.do_cr:
            self.change_request()
        meta_p = os.path.join(self.dir, "run.json")
        meta = json.load(open(meta_p, encoding="utf-8"))
        meta["finished"] = dt.datetime.now(dt.timezone.utc).isoformat()
        json.dump(meta, open(meta_p, "w", encoding="utf-8"), indent=1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--suite", required=True)
    ap.add_argument("--arm", required=True, choices=["A", "B", "C"])
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--features", type=int)
    ap.add_argument("--phase", default="main", choices=["pilot", "first", "main", "dry"])
    ap.add_argument("--no-cr", action="store_true")
    ap.add_argument("--allow-draft", action="store_true")
    Run(ap.parse_args()).go()


if __name__ == "__main__":
    main()
