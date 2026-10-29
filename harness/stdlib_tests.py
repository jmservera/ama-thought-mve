"""Minimal runner for plain pytest-style test functions (no fixtures) and unittest classes.

Used for offline dry runs and as a fallback when pytest is unavailable. Prints a short
summary, optionally writes JSON {"tests": {id: outcome}}, and exits 0 only if all tests pass.
"""
import argparse
import importlib.util
import json
import os
import signal
import sys
import traceback
import unittest

_helper_spec = importlib.util.spec_from_file_location(
    "_mve_failure_attribution", os.path.join(os.path.dirname(os.path.abspath(__file__)), "failure_attribution.py")
)
_helper = importlib.util.module_from_spec(_helper_spec)
_helper_spec.loader.exec_module(_helper)


class _Timeout(Exception):
    pass


class Results(dict):
    def __init__(self):
        super().__init__()
        self.provenance = {}


class _TestResult(unittest.TestResult):
    def addError(self, test, err):
        self.exception = err
        super().addError(test, err)


def discover(paths):
    files = []
    for p in paths:
        if os.path.isfile(p):
            files.append(p)
            continue
        for d, dirs, fs in os.walk(p):
            dirs[:] = sorted(x for x in dirs if not x.startswith((".", "__")))
            files += [os.path.join(d, f) for f in sorted(fs) if f.startswith("test") and f.endswith(".py")]
    return sorted(files)


def _run(fn, timeout, src, policy, evidence):
    def handler(signum, frame):
        raise _Timeout()
    old = signal.signal(signal.SIGALRM, handler)
    signal.alarm(timeout)
    try:
        outcome = fn()
        valid = (isinstance(outcome, tuple) and len(outcome) == 2
                 and outcome[0] in ("skipped", "failed", "error", "timeout")
                 and isinstance(outcome[1], str))
        return outcome if valid else ("passed", "")
    except _Timeout:
        evidence.update(raw_outcome="timeout", outcome="timeout", attribution="unknown", diagnostic="timed out")
        return "timeout", "timed out"
    except Exception as error:  # noqa: BLE001
        raw = "failed" if isinstance(error, AssertionError) else "error"
        evidence.update(_helper.exception_evidence(error, src, policy, raw))
        return raw, traceback.format_exc()
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def run(paths, src, timeout=10, policy=None):
    sys.path.insert(0, os.path.abspath(src))
    policy = policy or {}
    results = Results()
    for i, f in enumerate(discover(paths)):
        mod_name = os.path.splitext(os.path.basename(f))[0]
        try:
            spec = importlib.util.spec_from_file_location(f"_mve_t{i}_{mod_name}", f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception as error:  # noqa: BLE001
            key = f"{mod_name}::<import>"
            results[key] = ("error", traceback.format_exc())
            results.provenance[key] = _helper.exception_evidence(error, src, policy)
            continue
        for attr in sorted(vars(mod)):
            obj = getattr(mod, attr)
            if attr.startswith("test") and callable(obj) and not isinstance(obj, type) \
                    and getattr(obj, "__module__", None) == mod.__name__:
                key = f"{mod_name}::{attr}"
                evidence = {}
                results[key] = _run(obj, timeout, src, policy, evidence)
                if evidence:
                    results.provenance[key] = evidence
            elif isinstance(obj, type) and issubclass(obj, unittest.TestCase) and obj is not unittest.TestCase:
                for m in sorted(x for x in dir(obj) if x.startswith("test")):
                    def call(tc=obj(m)):
                        r = _TestResult()
                        tc.run(r)
                        if r.failures:
                            raise AssertionError(r.failures[0][1])
                        if r.errors:
                            _, error, tb = r.exception
                            raise error.with_traceback(tb)
                        if r.unexpectedSuccesses:
                            raise AssertionError("unexpected success")
                        if r.skipped or r.expectedFailures or not r.testsRun:
                            return "skipped", (r.skipped or r.expectedFailures or [(None, "not executed")])[0][1]
                    key = f"{mod_name}::{attr}::{m}"
                    evidence = {}
                    results[key] = _run(call, timeout, src, policy, evidence)
                    if evidence:
                        results.provenance[key] = evidence
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--src", default="src")
    ap.add_argument("--json")
    ap.add_argument("--timeout", type=int, default=10)
    ap.add_argument("--policy", help="Trusted declared-API attribution policy JSON")
    ap.add_argument("-q", action="store_true")
    a = ap.parse_args()
    policy = {}
    if a.policy:
        with open(a.policy, encoding="utf-8") as policy_file:
            policy = json.load(policy_file)
    res = run(a.paths, a.src, a.timeout, policy)
    failed = {k: v for k, v in res.items() if v[0] != "passed"}
    for k, (outcome, tb) in failed.items():
        print(f"{outcome.upper()}: {k}")
        if not a.q:
            print(tb)
    print(f"{len(res) - len(failed)} passed, {len(failed)} not passed, {len(res)} total")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"tests": {k: v[0] for k, v in res.items()}, "provenance": res.provenance}, fh, indent=1)
    sys.exit(0 if res and not any(v[0] in ("failed", "error", "timeout") for v in res.values()) else 1)


if __name__ == "__main__":
    main()
