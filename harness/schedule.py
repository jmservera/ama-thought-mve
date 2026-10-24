"""Print a randomised, interleaved run order for one pass of the experiment.

Usage: python3 schedule.py --pass first --suites s1-retrofit --arms A B --runs 4 --features 8 --seed 2026 [--config config.json]
Prints one runner command per line, in the order to execute them, and saves the order to schedule-<pass>.txt.
"""
import argparse
import random


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pass", dest="phase", required=True, choices=["pilot", "first", "main"])
    ap.add_argument("--suites", nargs="+", default=["s1-retrofit"])
    ap.add_argument("--arms", nargs="+", default=["A", "B"])
    ap.add_argument("--runs", type=int, default=4)
    ap.add_argument("--features", type=int, default=10)
    ap.add_argument("--seed", type=int, required=True)
    ap.add_argument("--config", default="config.json")
    a = ap.parse_args()
    rng = random.Random(a.seed)
    blocks = []
    for r in range(1, a.runs + 1):
        block = [(s, arm, r) for s in a.suites for arm in a.arms]
        rng.shuffle(block)          # every arm appears once per block: drift hits all arms alike
        blocks.append(block)
    lines = []
    for block in blocks:
        for s, arm, r in block:
            rid = f"{a.phase}-{s.split('-')[0]}-{arm}-{r:02d}"
            lines.append(f"python3 runner.py --config {a.config} --suite ../suites/{s} --arm {arm} "
                         f"--run-id {rid} --features {a.features} --phase {a.phase}")
    with open(f"schedule-{a.phase}.txt", "w") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
