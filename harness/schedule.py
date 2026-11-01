"""Read-only preview of the same immutable five-arm schedule used by the controller."""
import argparse
import json

from study import schedule


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pass", dest="phase", default="pilot-estimation",
                    choices=["pilot", "first", "calibration", "pilot-estimation"])
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--seed", type=int, required=True)
    a = ap.parse_args()
    print(json.dumps(schedule(a.smoke, a.phase, a.seed), indent=2))


if __name__ == "__main__":
    main()
