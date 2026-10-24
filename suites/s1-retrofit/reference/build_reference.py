"""Build the cumulative reference snapshots of suite S1 from source.py.

Lines between '# >>> TAG' and '# <<< TAG' are kept only when the snapshot satisfies TAG: 'f05' keeps them from
feature 5 on, 'f05-' only before feature 5, 'cr1' only for the change request. Markers may be nested.
Usage: python3 build_reference.py   (writes <id>/workbench/__init__.py next to this file for f01..f10 and cr1)
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
MARK = re.compile(r"^\s*# (>>>|<<<) (f\d\d|cr1)(-?)\s*$")


def level(tag):
    return 11 if tag == "cr1" else int(tag[1:])


def build(target):
    out, stack = [], []
    with open(os.path.join(HERE, "source.py"), encoding="utf-8") as fh:
        for line in fh:
            m = MARK.match(line)
            if m:
                kind, tag, neg = m.groups()
                if kind == ">>>":
                    stack.append((tag, neg))
                elif stack.pop() != (tag, neg):
                    raise SystemExit(f"unbalanced marker {tag}{neg}")
                continue
            if all((target >= level(t)) != bool(n) for t, n in stack):
                out.append(line)
    if stack:
        raise SystemExit("unclosed marker")
    return "".join(out)


def main():
    ids = [f"f{k:02d}" for k in range(1, 11)] + ["cr1"]
    for i, sid in enumerate(ids, 1):
        code = build(i).replace("at snapshot LEVEL", f"at snapshot {sid}")
        compile(code, sid, "exec")
        d = os.path.join(HERE, sid, "workbench")
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "__init__.py"), "w", encoding="utf-8") as fh:
            fh.write(code)
        print(f"{sid}: {len(code.splitlines())} lines")


if __name__ == "__main__":
    main()
