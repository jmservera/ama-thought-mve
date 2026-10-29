"""Private exception provenance shared by the two trusted evaluation runners.

Only declared missing APIs and established candidate-source exceptions are
nonpasses. An import dependency or evaluator fault is not evidence of failure.
This is diagnostic attribution, not an isolation boundary against hostile code.
"""
import dis
import importlib.machinery
import importlib.util
import json
import os
import re
import sys
import traceback
from contextlib import contextmanager

VIEW_READERS = {"get_home", "get_case", "list_cases", "case_details", "history",
                "notes", "stage_counts", "rank_cases", "export_cases_csv"}


@contextmanager
def view_contracts(src, policy, objects):
    """Observe actual declared view returns without modifying candidate methods."""
    factories = set(policy.get("methods", [])) & {"view_as", "view_for"}
    if not factories:
        yield
        return
    previous = sys.getprofile()

    def observe(frame, event, result):
        if callable(previous):
            previous(frame, event, result)
        if event != "return" or result is None or not frame.f_code.co_argcount:
            return
        package = sys.modules.get(policy.get("package"))
        workbench = vars(package).get("Workbench") if package is not None else None
        owner = type(frame.f_locals.get(frame.f_code.co_varnames[0]))
        if not isinstance(workbench, type) or workbench not in owner.__mro__:
            return
        for name in factories:
            method = next((vars(base)[name] for base in owner.__mro__ if name in vars(base)), None)
            if getattr(method, "__code__", None) is frame.f_code and _module_origin(frame.f_globals, src):
                objects[id(result)] = result
                break

    sys.setprofile(observe)
    try:
        yield
    finally:
        sys.setprofile(previous)


def api_policy(suite_dir, ids):
    path = os.path.join(suite_dir, "suite.json")
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as source:
        suite = json.load(source)
    package = suite.get("package")
    if not isinstance(package, str) or not package.isidentifier():
        return {}
    exports, methods, attributes = set(), set(), {}
    items = suite.get("features", []) + [suite.get("change_request", {})]
    for item in items:
        if item.get("id") not in ids:
            continue
        for declaration in item.get("api", []):
            if f"importable from {package}" in declaration:
                exports.update(re.findall(r"\b[A-Z][A-Za-z0-9_]*\b", declaration.split("importable")[0]))
            signature = re.match(r"([A-Za-z_]\w*)\(", declaration)
            if signature:
                name = signature[1]
                (exports if name[0].isupper() else methods).add(name)
            fields = re.search(r"\b([A-Z]\w*) (?:with (?:the )?|gains the )attributes? ([^.]+)", declaration)
            if fields:
                attributes.setdefault(fields[1], set()).update(
                    part.strip().split()[0] for part in re.split(r",|\band\b", fields[2]) if part.strip()
                )
    return {"package": package, "exports": sorted(exports), "methods": sorted(methods),
            "attributes": {name: sorted(fields) for name, fields in attributes.items()}}


def _source(path, src):
    return isinstance(path, str) and os.path.isfile(path) and \
        os.path.commonpath((os.path.realpath(path), os.path.realpath(src))) == os.path.realpath(src)


def _module_origin(namespace, src):
    spec = namespace.get("__spec__")
    loader = getattr(spec, "loader", None)
    if not isinstance(loader, importlib.machinery.SourceFileLoader):
        return None
    origin = getattr(spec, "origin", None)
    if (spec.name != namespace.get("__name__") or not _source(origin, src)
            or os.path.realpath(loader.get_filename(spec.name)) != os.path.realpath(origin)
            or os.path.realpath(namespace.get("__file__", "")) != os.path.realpath(origin)):
        return None
    return {"module": spec.name, "source": os.path.realpath(origin)}


def _instruction(tb):
    return next((op for op in dis.get_instructions(tb.tb_frame.f_code)
                 if op.offset == tb.tb_lasti), None)


def _mandatory_import(error, frames, src, policy):
    if not frames or not isinstance(error, ImportError):
        return None
    tb = frames[-1]
    op = _instruction(tb)
    package = policy.get("package")
    if not package or error.name != package or op is None:
        return None
    if isinstance(error, ModuleNotFoundError):
        # A missing external dependency has a different name or a deeper frame.
        if op.opname != "IMPORT_NAME" or op.argval != package:
            return None
        return {"module": package, "missing": package}
    if op.opname != "IMPORT_FROM" or op.argval not in policy.get("exports", []):
        return None
    module = sys.modules.get(package)
    origin = _module_origin(vars(module), src) if module is not None else None
    if origin and error.path and os.path.realpath(error.path) == origin["source"] \
            and op.argval not in vars(module):
        return {**origin, "missing": op.argval}
    return None


def _mandatory_attribute(error, src, policy, view_objects):
    if not isinstance(error, AttributeError):
        return None
    package = sys.modules.get(policy.get("package"))
    if package is not None and error.obj is package and error.name in policy.get("exports", []) \
            and error.name not in vars(package):
        origin = _module_origin(vars(package), src)
        if origin:
            return {**origin, "missing": error.name}
    cls = type(error.obj)
    module = sys.modules.get(cls.__module__)
    origin = _module_origin(vars(module), src) if module is not None else None
    mandatory = set()
    if package is not None:
        contracts = {**policy.get("attributes", {}), "Workbench": policy.get("methods", [])}
        for export, names in contracts.items():
            public = vars(package).get(export)
            if isinstance(public, type) and public in cls.__mro__:
                mandatory.update(names)
    if view_objects.get(id(error.obj)) is error.obj:
        mandatory.update(VIEW_READERS & set(policy.get("methods", [])))
    if origin and error.name in mandatory \
            and not any(error.name in vars(base) for base in cls.__mro__):
        return {**origin, "missing": error.name}
    return None


def _syntax_origin(error, frames, src):
    if not frames or not isinstance(error, SyntaxError) or not _source(error.filename, src):
        return None
    # CPython removes importlib frames from syntax errors. Bind the real import
    # instruction to its standard source-loader target, not just the filename.
    tb = frames[-1]
    instructions = list(dis.get_instructions(tb.tb_frame.f_code))
    index = next((i for i, op in enumerate(instructions) if op.offset == tb.tb_lasti), -1)
    if index < 2 or instructions[index].opname != "IMPORT_NAME":
        return None
    level, fromlist = instructions[index - 2].argval, instructions[index - 1].argval
    name = instructions[index].argval
    if not isinstance(level, int):
        return None
    if level:
        package = tb.tb_frame.f_globals.get("__package__")
        if not package:
            return None
        name = importlib.util.resolve_name("." * level + name, package)
    names = [name] + [f"{name}.{alias}" for alias in (fromlist or ()) if alias != "*"]
    for imported in names:
        search, spec = [src], None
        for end in range(1, len(imported.split(".")) + 1):
            qualified = ".".join(imported.split(".")[:end])
            spec = importlib.machinery.PathFinder.find_spec(qualified, search)
            if spec is None:
                break
            search = spec.submodule_search_locations
            if end < len(imported.split(".")) and search is None:
                spec = None
                break
        if (spec is not None and isinstance(spec.loader, importlib.machinery.SourceFileLoader)
                and os.path.realpath(spec.origin) == os.path.realpath(error.filename)):
            return {"module": spec.name, "source": os.path.realpath(spec.origin)}
    return None


def exception_evidence(error, src, policy, raw_outcome="error", view_objects=None):
    """Classify using live exception/frame/module objects, never message matching."""
    while type(error).__module__.startswith("_pytest.") and error.__cause__ is not None:
        error = error.__cause__
    frames = []
    tb = error.__traceback__
    while tb:
        frames.append(tb)
        tb = tb.tb_next
    record = {
        "raw_outcome": raw_outcome,
        "outcome": "failed" if isinstance(error, AssertionError) and raw_outcome == "failed" else "error",
        "attribution": "assertion" if isinstance(error, AssertionError) and raw_outcome == "failed" else "unknown",
        "exception_type": f"{type(error).__module__}.{type(error).__qualname__}",
        "diagnostic": "".join(traceback.format_exception(type(error), error, error.__traceback__)),
        "frames": [{"file": tb.tb_frame.f_code.co_filename, "line": tb.tb_lineno,
                    "function": tb.tb_frame.f_code.co_name} for tb in frames],
    }
    chain, seen = [], set()
    current = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        chain.append(current)
        current = current.__cause__ or current.__context__
    if any(isinstance(item, (MemoryError, OSError, TimeoutError)) for item in chain):
        record.update(outcome="error", attribution="unknown")
        return record
    origin = _mandatory_import(error, frames, src, policy)
    reason = "mandatory_import"
    if origin is None and not any(isinstance(item, ImportError) for item in chain):
        origin = _mandatory_attribute(error, src, policy, view_objects or {})
        reason = "mandatory_api"
        if origin is None:
            origin = _syntax_origin(error, frames, src)
            reason = "candidate_syntax"
        if origin is None and frames:
            leaf = frames[-1].tb_frame
            candidate = _module_origin(leaf.f_globals, src)
            known = type(error) in (AssertionError, ValueError, TypeError, AttributeError, NameError, KeyError,
                                    IndexError, ZeroDivisionError, NotImplementedError)
            cls_module = sys.modules.get(type(error).__module__)
            custom = candidate is not None and type(error).__module__ == leaf.f_globals.get("__name__") \
                and leaf.f_globals.get(type(error).__name__) is type(error)
            custom |= cls_module is not None and \
                _module_origin(vars(cls_module), src) is not None and \
                vars(cls_module).get(type(error).__name__) is type(error)
            if leaf.f_code.co_name in ("__getattr__", "__getattribute__"):
                known = custom = False
            if candidate and os.path.realpath(leaf.f_code.co_filename) == candidate["source"] and (known or custom):
                origin, reason = candidate, "candidate_exception"
    if origin:
        record.update(outcome="failed", attribution=reason, candidate=origin)
    return record


def pytest_plugin(src, policy, output):
    """Create the tiny plugin only inside the pytest child, before candidate imports."""
    import pytest

    class Provenance:
        def __init__(self):
            self.records = {}
            self.views = {}

        def pytest_sessionstart(self, session):
            self.tracker = view_contracts(src, policy, self.views)
            self.tracker.__enter__()

        def pytest_exception_interact(self, node, call, report):
            if getattr(report, "when", "collect") == "collect":
                key = os.path.splitext(os.path.basename(report.nodeid))[0] + "::<import>"
                self.records[key] = exception_evidence(call.excinfo.value, src, policy, view_objects=self.views)

        @pytest.hookimpl(wrapper=True)
        def pytest_runtest_makereport(self, item, call):
            report = yield
            if call.excinfo is not None and report.failed:
                key = os.path.basename(item.nodeid).replace(".py::", "::", 1)
                raw = "failed" if report.when == "call" else "error"
                self.records[key] = exception_evidence(call.excinfo.value, src, policy, raw, self.views)
            return report

        def pytest_sessionfinish(self, session, exitstatus):
            self.tracker.__exit__(None, None, None)
            with open(output, "w", encoding="utf-8") as report:
                json.dump({"provenance": self.records}, report)

    return Provenance()
