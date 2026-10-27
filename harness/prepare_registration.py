"""Prepare a private offline OSF draft; never submit, freeze or run a study."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

from contract_panel import accepted, checked_panel
from study import fingerprint
from study_io import ROOT, StudyError, atomic_json, command, read_json
from study_report import check_credentials

SUBMISSION_FILES = (
    "protocol/README.md", "protocol/pilot-estimation.md",
    "protocol/osf-preregistration.md", "protocol/pilot-estimation.json",
    "protocol/contract-panel.json",
    "harness/prompts/feature-step.prompt.md", "harness/prompts/consolidation-step.prompt.md",
    "harness/prompts/review-only-step.prompt.md", "harness/prompts/change-request.prompt.md",
)
DECISIONS = {
    "post_after_failed_feature", "prerequisite_continuation_and_later_recovery",
    "evaluator_information_boundary", "outage_retry_and_missing_measurement_rules",
    "agent_failure_classification", "assisted_run_disposition_and_telemetry",
    "comprehension_include_or_defer", "oracle_repeat_count_and_failure_rules",
    "post_calibration_credit_cap_and_affordability", "actual_prior_data_seen_and_chronology",
}
EVIDENCE = {
    "independent_suite_review", "contract_panel_review", "oracle_stability",
    "local_runtime_evidence", "access_probe_including_cr1_text",
    "analysis_and_reference_metrics_acceptance",
    "telemetry_coverage_or_explicit_secondary_unavailability", "prior_data_disclosure",
    "multi_model_harness_alignment",
}


def resolved(value) -> bool:
    return (isinstance(value, str) and bool(value.strip())
            and not re.match(r"(?i)^(todo|tbd|pending|unavailable|unknown|not reviewed)\b", value.strip()))


def readiness(config: dict, panel: dict) -> dict:
    if set(config["owner_decisions"]) != DECISIONS or set(config["required_evidence"]) != EVIDENCE:
        raise StudyError("Decision/evidence ledger fields changed or missing; reconcile the protocol schema")
    study = config["study"]
    resources = config["resources"]
    models = study.get("model_roster")
    design = (study["purpose"] == "pilot-estimation" and study["suite"] == "s1-retrofit"
              and study["arms"] == ["A", "B", "C"] and study["runs_per_arm"] == 2
              and isinstance(models, list) and len(models) == 3
              and all(isinstance(model, str) for model in models)
              and set(models) == {"gpt-6.1-sol", "claude-sonnet-5.5", "gemini-4-argon"}
              and config["runtime"]["model"] is None
              and study["features"] == 10 and study["change_request"] is True
              and study["calibration_runs_per_arm"] == 1 and study["calibration_change_request"] is False
              and study["formal_hypotheses"] == []
              and resources["credit_ceiling"] == 300000
              and resources.get("pilot_session_credit_cap") == 300
              and resources["calibration_session_credit_cap"] == 300
              and resources["separate_monetary_budget_usd"] is None
              and [resources[name] for name in ("feature_seconds", "post_seconds", "change_request_seconds")]
              == [1800, 900, 2700])
    unresolved = [f"owner_decisions.{key}" for key, value in config["owner_decisions"].items() if not resolved(value)]
    unresolved += [f"required_evidence.{key}" for key, value in config["required_evidence"].items() if not resolved(value)]
    approval = config["owner_approval"]
    if not (approval["approved"] is True and resolved(approval["date"]) and resolved(approval["evidence"])):
        unresolved.append("owner_approval")
    if not accepted(panel):
        unresolved.append("contract_panel_independent_acceptance")
    registration = config["registration"]
    registered = (registration["submitted"] is True and isinstance(registration["url"], str)
                  and re.fullmatch(r"https://osf\.io/[A-Za-z0-9/]+", registration["url"]) is not None
                  and resolved(registration["date"]))
    return {"draft_complete": design, "author_submission_ready": design and not unresolved,
            "unresolved": unresolved, "registration_recorded": registered,
            "registration_independently_verified": False, "execution_ready": False,
            "execution_blockers": ["Provider-enforced hard billing backend absent; paid execution disabled",
                                   "Model-aware scheduler/analysis and operational-rule alignment need acceptance",
                                   "Actual approved freeze/runtime/access/budget evidence must be verified"],
            "no_registration_required_to_prepare_draft": True,
            "registered_or_approved_by_tool": False}


def prepare(out: Path, root: Path = ROOT) -> dict:
    root = root.resolve()
    destination = out.absolute()
    base = root / ".study"
    if (not destination.resolve().is_relative_to(base) or destination.resolve() == base
            or any(path.is_symlink() for path in [destination, *destination.parents] if path.is_relative_to(base))):
        raise StudyError("Draft output must be a new non-symlinked directory within .study/")
    if destination.exists():
        raise StudyError("Draft output already exists; preserve it and choose a new directory")
    files = []
    for relative in SUBMISSION_FILES:
        path = root / relative
        if (not path.is_file() or any(parent.is_symlink() for parent in (path, *path.parents))
                or path.stat().st_size > 512 * 1024):
            raise StudyError(f"Missing, linked or oversized submission input: {relative}")
        check_credentials(path.read_text(encoding="utf-8"))
        files.append(path)
    panel = checked_panel(root / "protocol/contract-panel.json", root / "suites/s1-retrofit")
    config = read_json(root / "protocol/pilot-estimation.json")
    report = readiness(config, panel)
    source_hashes = {}
    for folder in ("protocol", "harness", "skeleton", "suites", "scripts"):
        for path in sorted((root / folder).rglob("*")):
            if "__pycache__" in path.parts or ".pytest_cache" in path.parts:
                continue
            if path.is_symlink():
                raise StudyError("Source evidence must not contain symlinks")
            if path.is_file():
                source_hashes[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    launcher = root / "run-study.sh"
    source_hashes["run-study.sh"] = hashlib.sha256(launcher.read_bytes()).hexdigest()
    manifest = {"status": "offline-draft-not-submitted", "source_commit": command(["git", "rev-parse", "HEAD"], cwd=root),
                "working_tree_dirty": bool(command(["git", "status", "--porcelain"], cwd=root)),
                "inputs_sha256": fingerprint(root), "paper": config["paper"],
                "source_sha256": source_hashes, "submission_files": list(SUBMISSION_FILES),
                "approval_inferred": False, "readiness": report}
    # All checks precede creation. An interrupted package is retained, never overwritten.
    destination.mkdir(parents=True, mode=0o700)
    for path in files:
        target = destination / path.relative_to(root)
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copyfile(path, target)
        target.chmod(0o600)
    manifest["package_sha256"] = {relative: hashlib.sha256((destination / relative).read_bytes()).hexdigest()
                                for relative in SUBMISSION_FILES}
    atomic_json(destination / "manifest.json", manifest)
    atomic_json(destination / "readiness.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=ROOT / ".study/osf-draft")
    args = parser.parse_args()
    try:
        report = prepare(args.out)
    except (StudyError, OSError, ValueError, KeyError, TypeError) as error:
        parser.exit(2, f"Draft preparation refused: {error if isinstance(error, StudyError) else type(error).__name__}\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
