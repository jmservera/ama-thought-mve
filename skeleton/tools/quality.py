"""Write reports/quality.md for the current repository (run by `make check`)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from metrics_core import measure  # noqa: E402


def main():
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    m = measure(repo)
    os.makedirs(os.path.join(repo, "reports"), exist_ok=True)
    rel = lambda p: os.path.relpath(p, repo)  # noqa: E731
    lines = ["# Quality report", "",
             f"Functions: {m['functions']}; mean complexity {m['mean_ccn']}; max {m['max_ccn']}; "
             f"share above 10: {100 * m['share_ccn_over_10']:.1f}%",
             f"Duplicated lines: {m['dup_pct']}%; lint warnings: {m['lint_warnings']}; "
             f"source lines: {m['nloc_src']}; test lines: {m['nloc_tests']}", "",
             "## Complexity hotspots (complexity above 10 first)", "", "| Function | File:line | Complexity |", "| --- | --- | --- |"]
    lines += [f"| {f['name']} | {rel(f['file'])}:{f['line']} | {f['ccn']} |" for f in m["_hotspots"]]
    lines += ["", "## Duplicated blocks", ""]
    if m["_dup_blocks"]:
        for b in m["_dup_blocks"]:
            occ = ", ".join(f"{rel(p) if p and os.path.isabs(p) else p}:{ln}" for p, ln in b["occurrences"])
            lines.append(f"- {b['lines']} lines at {occ}")
    else:
        lines.append("- none")
    lines += ["", "## Lint warnings by rule", ""]
    lines += [f"- {k}: {v}" for k, v in m["_lint_by_code"].items()] or ["- none"]
    lines += ["", "## Largest files (code lines)", ""]
    lines += [f"- {p}: {n}" for p, n in m["_file_sizes"]]
    with open(os.path.join(repo, "reports", "quality.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"quality: mean complexity {m['mean_ccn']}, duplication {m['dup_pct']}%, lint {m['lint_warnings']}"
          f" -> reports/quality.md")


if __name__ == "__main__":
    main()
