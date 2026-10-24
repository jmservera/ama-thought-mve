"""Code-quality measures shared by `make check` (agent-visible) and the experiment runner.

Backends (environment variables or function arguments):
  MVE_COMPLEXITY = lizard | internal | auto   (default auto: lizard if importable)
  MVE_DUPLICATION = jscpd | internal | auto   (default auto: jscpd if on PATH)
  MVE_LINT = ruff | none | auto               (default auto: ruff if on PATH)
Every result records the backend used, so runs measured differently are never mixed.
"""
import ast
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from collections import defaultdict

DUP_WINDOW = 6
LINT_RULES = "E,F,W,C90,B,SIM"  # frozen rule set; C90 uses the default complexity limit of 10


def py_files(root):
    out = []
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if not x.startswith(".") and x != "__pycache__"]
        out += [os.path.join(d, f) for f in sorted(files) if f.endswith(".py")]
    return sorted(out)


def _read(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read()


def code_lines(text):
    n = 0
    for line in text.splitlines():
        s = line.strip()
        if s and not s.startswith("#"):
            n += 1
    return n


# ---------------------------------------------------------------- complexity
class _CC(ast.NodeVisitor):
    """McCabe-style count of decision points; nested functions are measured separately."""

    def __init__(self):
        self.n = 1

    def generic_visit(self, node):
        if isinstance(node, (ast.If, ast.For, ast.AsyncFor, ast.While, ast.IfExp, ast.ExceptHandler)):
            self.n += 1
        elif isinstance(node, ast.BoolOp):
            self.n += len(node.values) - 1
        elif isinstance(node, ast.comprehension):
            self.n += 1 + len(node.ifs)
        elif hasattr(ast, "match_case") and isinstance(node, ast.match_case):
            self.n += 1
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
                continue
            self.visit(child)


def _internal_functions(path):
    try:
        tree = ast.parse(_read(path))
    except SyntaxError:
        return []
    out = []

    def walk(node, prefix):
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                v = _CC()
                for stmt in child.body:
                    v.visit(stmt)
                name = prefix + child.name
                end = getattr(child, "end_lineno", child.lineno)
                out.append({"file": path, "name": name, "line": child.lineno,
                            "ccn": v.n, "nloc": end - child.lineno + 1})
                walk(child, name + ".")
            elif isinstance(child, ast.ClassDef):
                walk(child, prefix + child.name + ".")
    walk(tree, "")
    return out


def complexity(files, backend=None):
    backend = backend or os.environ.get("MVE_COMPLEXITY", "auto")
    if backend in ("auto", "lizard"):
        try:
            import lizard  # type: ignore
            funcs = []
            for p in files:
                info = lizard.analyze_file(p)
                for fn in info.function_list:
                    funcs.append({"file": p, "name": fn.name, "line": fn.start_line,
                                  "ccn": fn.cyclomatic_complexity, "nloc": fn.nloc})
            return {"backend": "lizard", "functions": funcs}
        except ImportError:
            if backend == "lizard":
                raise
    funcs = []
    for p in files:
        funcs += _internal_functions(p)
    return {"backend": "internal", "functions": funcs}


# --------------------------------------------------------------- duplication
def _norm(line):
    s = line.split("#", 1)[0].strip()
    return s


def _internal_duplication(files):
    windows = defaultdict(list)
    total = 0
    norm_lines = {}
    for p in files:
        lines = [(i + 1, _norm(l)) for i, l in enumerate(_read(p).splitlines())]
        lines = [(i, s) for i, s in lines if s and not s.startswith(("import ", "from "))]
        norm_lines[p] = lines
        total += len(lines)
        for j in range(len(lines) - DUP_WINDOW + 1):
            chunk = "\n".join(s for _, s in lines[j:j + DUP_WINDOW])
            windows[hashlib.sha1(chunk.encode()).hexdigest()].append((p, j))
    dup = set()
    blocks = []
    for occ in windows.values():
        if len(occ) < 2:
            continue
        for p, j in occ:
            for k in range(j, j + DUP_WINDOW):
                dup.add((p, k))
        p0, j0 = occ[0]
        blocks.append({"occurrences": [(p, norm_lines[p][j][0]) for p, j in occ], "lines": DUP_WINDOW, "first": (p0, j0)})
    pct = 100.0 * len(dup) / total if total else 0.0
    return {"backend": "internal", "duplicated_lines": len(dup), "lines": total,
            "percentage": round(pct, 2), "blocks": blocks[:20]}


def _jscpd_duplication(src):
    exe = shutil.which("jscpd")
    if not exe:
        return None
    out = tempfile.mkdtemp(prefix="jscpd-")
    # jscpd v5 flags (format, thresholds, JSON reporter). Run from an empty folder so that no
    # .jscpd.json written by the agent can change the measure.
    subprocess.run([exe, "-f", "python", "--min-tokens", "50", "--min-lines", "5", "-r", "json",
                    "--output", out, os.path.abspath(src)], capture_output=True, text=True, timeout=300, cwd=out)
    report = os.path.join(out, "jscpd-report.json")
    if not os.path.exists(report):
        return None
    data = json.load(open(report, encoding="utf-8"))
    tot = data.get("statistics", {}).get("total", {})
    blocks = [{"occurrences": [(d.get("firstFile", {}).get("name"), d.get("firstFile", {}).get("start")),
                               (d.get("secondFile", {}).get("name"), d.get("secondFile", {}).get("start"))],
               "lines": d.get("lines")} for d in data.get("duplicates", [])[:20]]
    return {"backend": "jscpd", "duplicated_lines": tot.get("duplicatedLines"), "lines": tot.get("lines"),
            "percentage": tot.get("percentage"), "blocks": blocks}


def duplication(src, files, backend=None):
    backend = backend or os.environ.get("MVE_DUPLICATION", "auto")
    if backend in ("auto", "jscpd"):
        r = _jscpd_duplication(src)
        if r is not None:
            return r
        if backend == "jscpd":
            raise RuntimeError("jscpd requested but not available or produced no report")
    return _internal_duplication(files)


# ----------------------------------------------------------------------- lint
def lint(src, backend=None, config_root=None):
    backend = backend or os.environ.get("MVE_LINT", "auto")
    exe = shutil.which("ruff")
    if backend == "none" or (backend == "auto" and not exe):
        return {"backend": "none", "warnings": None, "by_code": {}}
    if not exe:
        raise RuntimeError("ruff requested but not on PATH")
    # --isolated ignores every configuration file, so editing pyproject.toml cannot change the measure.
    r = subprocess.run([exe, "check", "--isolated", "--select", LINT_RULES, "--output-format", "json",
                        "--exit-zero", "--no-cache", os.path.abspath(src)],
                       capture_output=True, text=True, timeout=300, cwd=config_root or None)
    items = json.loads(r.stdout or "[]")
    by_code = defaultdict(int)
    for it in items:
        by_code[it.get("code") or "?"] += 1
    return {"backend": "ruff", "warnings": len(items), "by_code": dict(sorted(by_code.items()))}


# -------------------------------------------------------------------- summary
def measure(repo, complexity_backend=None, duplication_backend=None, lint_backend=None):
    src = os.path.join(repo, "src")
    tests = os.path.join(repo, "tests")
    sfiles = py_files(src)
    tfiles = py_files(tests) if os.path.isdir(tests) else []
    cc = complexity(sfiles, complexity_backend)
    funcs = cc["functions"]
    nloc_src = sum(code_lines(_read(p)) for p in sfiles)
    nloc_tests = sum(code_lines(_read(p)) for p in tfiles)
    dup = duplication(src, sfiles, duplication_backend)
    li = lint(src, lint_backend, config_root=repo)
    md_words = 0
    for d, dirs, files in os.walk(repo):
        dirs[:] = [x for x in dirs if not x.startswith(".")]
        for f in files:
            if f.endswith(".md"):
                md_words += len(_read(os.path.join(d, f)).split())
    ccs = [f["ccn"] for f in funcs]
    return {
        "backends": {"complexity": cc["backend"], "duplication": dup["backend"], "lint": li["backend"]},
        "functions": len(funcs),
        "mean_ccn": round(sum(ccs) / len(ccs), 3) if ccs else 0.0,
        "max_ccn": max(ccs) if ccs else 0,
        "share_ccn_over_10": round(sum(1 for c in ccs if c > 10) / len(ccs), 4) if ccs else 0.0,
        "dup_pct": dup["percentage"],
        "lint_warnings": li["warnings"],
        "lint_per_kloc": (round(1000.0 * li["warnings"] / nloc_src, 3) if (li["warnings"] is not None and nloc_src) else None),
        "nloc_src": nloc_src,
        "nloc_tests": nloc_tests,
        "md_words": md_words,
        "files_src": len(sfiles),
        "_hotspots": sorted(funcs, key=lambda f: -f["ccn"])[:10],
        "_dup_blocks": dup.get("blocks", [])[:5],
        "_lint_by_code": li["by_code"],
        "_file_sizes": sorted(((os.path.relpath(p, repo), code_lines(_read(p))) for p in sfiles), key=lambda x: -x[1])[:10],
    }
