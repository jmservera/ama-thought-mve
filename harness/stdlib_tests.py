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


class _Timeout(Exception):
    pass


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


def _run(fn, timeout):
    def handler(signum, frame):
        raise _Timeout()
    old = signal.signal(signal.SIGALRM, handler)
    signal.alarm(timeout)
    try:
        fn()
        return "passed", ""
    except _Timeout:
        return "timeout", "timed out"
    except AssertionError:
        return "failed", traceback.format_exc(limit=4)
    except Exception:  # noqa: BLE001
        return "error", traceback.format_exc(limit=4)
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old)


def run(paths, src, timeout=10):
    sys.path.insert(0, os.path.abspath(src))
    results = {}
    for i, f in enumerate(discover(paths)):
        mod_name = os.path.splitext(os.path.basename(f))[0]
        try:
            spec = importlib.util.spec_from_file_location(f"_mve_t{i}_{mod_name}", f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception:  # noqa: BLE001
            results[f"{mod_name}::<import>"] = ("error", traceback.format_exc(limit=4))
            continue
        for attr in sorted(vars(mod)):
            obj = getattr(mod, attr)
            if attr.startswith("test") and callable(obj) and not isinstance(obj, type) \
                    and getattr(obj, "__module__", None) == mod.__name__:
                results[f"{mod_name}::{attr}"] = _run(obj, timeout)
            elif isinstance(obj, type) and issubclass(obj, unittest.TestCase) and obj is not unittest.TestCase:
                for m in sorted(x for x in dir(obj) if x.startswith("test")):
                    def call(tc=obj(m)):
                        r = unittest.TestResult()
                        tc.run(r)
                        if r.failures:
                            raise AssertionError(r.failures[0][1])
                        if r.errors:
                            raise RuntimeError(r.errors[0][1])
                    results[f"{mod_name}::{attr}::{m}"] = _run(call, timeout)
    return results


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--src", default="src")
    ap.add_argument("--json")
    ap.add_argument("--timeout", type=int, default=10)
    ap.add_argument("-q", action="store_true")
    a = ap.parse_args()
    res = run(a.paths, a.src, a.timeout)
    failed = {k: v for k, v in res.items() if v[0] != "passed"}
    for k, (outcome, tb) in failed.items():
        print(f"{outcome.upper()}: {k}")
        if not a.q:
            print(tb)
    print(f"{len(res) - len(failed)} passed, {len(failed)} not passed, {len(res)} total")
    if a.json:
        with open(a.json, "w", encoding="utf-8") as fh:
            json.dump({"tests": {k: v[0] for k, v in res.items()}}, fh, indent=1)
    sys.exit(0 if res and not failed else 1)


if __name__ == "__main__":
    main()
