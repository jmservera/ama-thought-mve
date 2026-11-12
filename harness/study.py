"""Resumable controller with buffered soft-credit settings and explicit launch gates."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import ExitStack, contextmanager
from datetime import datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from types import SimpleNamespace

from analyze import step_usage
from pilot_analysis import collection_role
from runner import POST_KINDS, Run, git, head
from study_io import ROOT, RetryableError, StudyError, atomic_json, command, read_json

NANO = 1_000_000_000
MAX_CREDITS = 300000 * NANO
APPROVED_HISTORICAL_PROVISION = {
    "attempt_id": "gpt-6.1-sol-nonstudy-1",
    "reserved_credits": 300,
    "actual_credits": None,
    "source_commit": "44ec37d9bb470521b2efd396a71ce23deb2f8ebf",
    "evidence_sha256": "82ac0a3c7b6f4c54a2fb65d6cc43a5031ee1c197aa10ece8ba4f492ed7568d22",
    "approval": "owner-approved-carry-forward-2026-10-29",
}
APPROVED_STARTUP_PROVISION = {
    "attempt_id": "gpt-6.1-sol-authorized-check-20261029-1",
    "reserved_credits": 300,
    "actual_credits": None,
    "source_commit": "cb1955957e7950a520b9a75d07bb3486616c5bbf",
    "evidence_sha256": "2d42df9f95198e97944f23aa67bfff9a41097463ebf0ea877c37928e3f561cf6",
    "approval": "owner-approved-startup-carry-forward-2026-10-29",
}
APPROVED_RENEWED_PROVISION = {
    "attempt_id": "gpt-6.1-sol-authorized-check-20261029-5585ed1-1",
    "reserved_credits": 300,
    "actual_credits": None,
    "source_commit": "5585ed1cf8fa27b253c42b40325aa54cc3ab25bd",
    "evidence_sha256": "63804ae9c968423a651b1afe626aa849ce7178c0f06e379a3a5c18a0592ddf25",
    "approval": "owner-approved-renewed-check-carry-forward-2026-10-29",
}
APPROVED_FEATURE_DIAGNOSTIC_PROVISION = {
    "attempt_id": "excluded-paid-p1-sonnet-20261031-f01-feature-1",
    "reserved_credits": 300,
    "actual_credits": None,
    "source_commit": "423253482145ad5e9ba5c1cffd9c730d577d085f",
    "evidence_sha256": "84177c3a4a11e29dc4016ba20b686df8628aab13c0c598d5e77a69c4bf8acba4",
    "approval": "owner-approved-diagnostic-carry-forward-2026-10-31",
}
APPROVED_V4_DIAGNOSTIC_PROVISION = {
    "attempt_id": "excluded-v4-p1-gpt-6.1-sol-20261031-f01-feature-1",
    "reserved_credits": 300,
    "actual_credits": None,
    "source_commit": "03c50856838b539780d57216af2a4cf6744187d7",
    "evidence_sha256": "1919669aa97a2ef092048ee6e217a55875be806235e2c14e9a5e699863c3cf3e",
    "approval": "owner-authorized-test-continuation-2026-10-31",
}
APPROVED_INTERRUPTED_CALIBRATION_PROVISION = {
    "attempt_id": "calibration-gemini-4-argon-D-01-f10-feature-1",
    "reserved_credits": 600,
    "actual_credits": None,
    "source_commit": "65b00307bbab738b966a69ca206b410e6e1c4dc8",
    "evidence_sha256": "f67a58efbd21be1f4f7989158cfb760da9109ee2ff1fd174772db63140e96c09",
    "approval": "owner-approved-interrupted-calibration-hold-2026-11-07",
}
MODEL_DESIGN = "model-stratified-v2-five-arm"
RECOVERY_STATE_SHA256 = "6eb8f45bcb54f8cad20cbd89aba72da7721ebf06ab6188fbf3c0cc460306723f"
RECOVERY_SOURCE = "99a1ed170d7c71acb428b52e0e24be8856cc3ea3"
RECOVERY_ATTEMPT = "pilot-estimation-claude-sonnet-5.5-E-03-f03-repair-1"
RECOVERY_JOURNAL_SHA256 = "ac402234bdca8758bde0eeccdda0594a9509b47b190555000a1f2d0c2588eb47"
BACKEND_RECOVERY_STATE_SHA256 = "b8f9abfb13f45b1261b7bbf82f82f17f934523f662073bc443103b9d84787d9a"
BACKEND_RECOVERY_SOURCE = "3c2ce89b00fe583c1f0715e8ccd3510419d5e734"
BACKEND_RECOVERY_ATTEMPT = "pilot-estimation-gpt-6.1-sol-E-04-f08-feature-1"
BACKEND_RECOVERY_JOURNAL_SHA256 = "eac78300d5e12796fe6174b11a1fb052bdec1220b755cf56f724571ca8235abd"
SANDBOX_RECOVERY_STATE_SHA256 = "18fcc0ece87305cca5205fd8bd24bc7cffaadde38e32e9c77f4bc922b4d7b4ab"
SANDBOX_RECOVERY_SOURCE = "e71037d961cb80fc5c659437796de7736820f6c9"
SANDBOX_RECOVERY_ATTEMPT = "pilot-estimation-gpt-6.1-sol-B-06-f02-consolidation-1"
SANDBOX_RECOVERY_JOURNAL_SHA256 = "de131c24e0d2800d75c5c94e68a12f769a7eff5b5748c99310778d3897e3e635"
SANDBOX_RECOVERY_BROKER_METADATA_SHA256 = "6a98302c57f1dc4673266f8f2f605e3d7c0a7515940d6b99afc1874d20aafc94"
SANDBOX_RECOVERY_BROKER_STATE_SHA256 = "c80f6378326a077e74ad0c674bedba2f14c7a12ce58216180d76728b62476f3e"
SANDBOX_RECOVERY_BROKER_OWNER_SHA256 = "1d6969a512d08cf1a7e80c04648614fffa26ac2d6e7c32f691a5935c6f4a78dd"
SERVICE_RECOVERY_STATE_SHA256 = "ec36955567ffc2424ce4a9a748f43a3e584c3c3d6756488028f4b0b5bd008a7c"
SERVICE_RECOVERY_SOURCE = "fb1a90a0347609b1b1c33f4cd1147433a25cab96"
SERVICE_RECOVERY_ATTEMPT = "pilot-estimation-gpt-6.1-sol-A-09-f02-feature-1"
SERVICE_RECOVERY_JOURNAL_SHA256 = "e4b44c1f0145fe5d54422187dc4c21229a2db405e93aca0aacbc7fbc4c2834db"
TRANSPORT_RECOVERY_STATE_SHA256 = "1c79a8eba989779464cd2757e65887fae727538fb74691e50228c27bde0db60f"
TRANSPORT_RECOVERY_SOURCE = "355d33389441b325da72363a9c3028dbdefa2b4b"
TRANSPORT_RECOVERY_ATTEMPT = "pilot-estimation-gpt-6.1-sol-D-10-f07-feature-1"
TRANSPORT_RECOVERY_JOURNAL_SHA256 = "9057d6c157011ade7dbf9412d791d28c2667acc3a5f7f2182b130c43ebf8d8c4"
CLOSE_RECOVERY_STATE_SHA256 = "7379f557090b61ed94479a9cccf49ac83925d7c45bab606838e007e1377a7732"
CLOSE_RECOVERY_SOURCE = "1d663f08af117332773feb22efc8e182734780a3"
CLOSE_RECOVERY_ATTEMPT = "pilot-estimation-gpt-6.1-sol-E-10-f05-feature-1"
CLOSE_RECOVERY_JOURNAL_SHA256 = "19bffffd77043723c325765c2e11b188acd3a9ce7bc85a4bc7e577e0617bd068"
MIXED_RECOVERY_STATE_SHA256 = "2f331781c5dfb922cc3610a212a823f9a197da57f09c754c83c22f325e6fdca5"
MIXED_RECOVERY_SOURCE = "958d75bc386964edfe6d211117ce53cf5fd53a82"
MIXED_RECOVERY_ATTEMPT = "pilot-estimation-gpt-6.1-sol-E-10-f10-feature-1"
MIXED_RECOVERY_JOURNAL_SHA256 = "a1466ddc9276af0af0f549b523b5264e43ada48ed8e2d09210a7d9c10eb9b59d"
UNACCOUNTED_RECOVERY_STATE_SHA256 = "4660d4b31bdd2bb8a8ac1c62c42dff8021d8cdbc87d24ed50e2c464c592b2d94"
UNACCOUNTED_RECOVERY_SOURCE = "03ac696b382e539cad5f8153b91d144bb4c1990b"
UNACCOUNTED_RECOVERY_ATTEMPT = "pilot-estimation-gpt-6.1-sol-D-11-f06-feature-1"
UNACCOUNTED_RECOVERY_JOURNAL_SHA256 = "8714b88c50b506296309408b09161980b35ba6b8cefeadffbb9d8cc13fb7ec78"
PAIRED_RECOVERY_STATE_SHA256 = "42a75a6285d3fac59112ec7c7e0b684b18de16239d9f33f20961dfdc6aaed282"
PAIRED_RECOVERY_SOURCE = "732c4896da7c0a5b0db0f60c02348743a5b2c54e"
PAIRED_RECOVERY_HOLDS = {
    "pilot-estimation-gpt-6.1-sol-B-11-f05-feature-1":
        "a1a780066151b7d7d85bb720b22ba1ef0ae5d3c9df9bd58da5f485946bfbec6c",
    "pilot-estimation-gpt-6.1-sol-E-11-f01-repair-1":
        "adf74655c4b4ae14678a43e3bc34dcff6173d9472e0f90dc132d04331825cbe2",
}
HTTP_RECOVERY_STATE_SHA256 = "ae55cc6ae2fb758956105e738622a2a2b9ea87c6802c039346b32e254c655397"
HTTP_RECOVERY_SOURCE = "fc8dd5995cde046b4c2de1f2eb25a0df32ff39eb"
HTTP_RECOVERY_HOLDS = {
    "pilot-estimation-gemini-4-argon-B-12-f04-feature-1": {
        "journal_sha256": "28b39857a766019a020b803181cf3778e3a6346680e0c1caec6d0912c7176e89",
        "reserved_nano": 300 * NANO,
    },
    "pilot-estimation-gemini-4-argon-D-12-f06-feature-1": {
        "journal_sha256": "d6d8a3c81e94f1780560fb11f75bbc1103f6962cdfefae75adbe6e067a60b84a",
        "reserved_nano": 600 * NANO,
    },
}
HTTP_TIMEOUT_RECOVERY_STATE_SHA256 = "a1759e095bed45164905610c73efcfa671aa6dcd9dedcbf2ee07250c548d3745"
HTTP_TIMEOUT_RECOVERY_SOURCE = "29e5f0834717b3c8a58a248858782174e775b6b8"
HTTP_TIMEOUT_RECOVERY_ATTEMPT = "pilot-estimation-gemini-4-argon-D-14-f06-feature-1"
HTTP_TIMEOUT_RECOVERY_JOURNAL_SHA256 = "44ef3324c6aa47d8945cd2dcdff87ad4928f8c2043fb449684b3bbe3e528805c"
RESILIENCE_BOOTSTRAP_STATE_SHA256 = "1b50aa55cebf781b6950e4723ac7ac655529f28c7f13bd56ac99adc6a40577cd"
RESILIENCE_BOOTSTRAP_SOURCE = "73712f7834ca520df543b6a58315bb299ffd38a8"
RESILIENCE_BOOTSTRAP_ATTEMPT = "pilot-estimation-gemini-4-argon-E-14-f10-repair-1"
RESILIENCE_BOOTSTRAP_JOURNAL_SHA256 = "8a455755c1eefaee9eabf52d5655dfcf4592b73b6e802b220eb799f738e49c4e"
FALLBACK_RECOVERY_STATE_SHA256 = "e15ef046d01b323b2ae66aa1055572dd0754817b320787763436811308b1b60b"
FALLBACK_RECOVERY_SOURCE = "0c35eff0e345d04c41722a43420d19b892c7fb8c"
FALLBACK_RECOVERY_ATTEMPT = "pilot-estimation-gpt-6.1-sol-C-20-f10-feature-1"
FALLBACK_RECOVERY_JOURNAL_SHA256 = "e6704ca2f50b50dbf79d04f039673076bae1228a9572619d561ebc5fb8e7b26a"
INPUTS = ("protocol", "harness", "skeleton", "suites", "run-study.sh", "run-experiment.sh", "scripts")
GATES = (
    "independent_suite_review", "access_probe", "local_runtime_evidence",
    "missing_feature_policy", "retry_policy", "evaluator_information_policy",
    "analysis_reconciliation", "contract_panel_review", "oracle_stability",
    "cr1_estimands", "secondary_scope", "outage_assistance_policy",
    "telemetry_coverage", "prior_data_disclosure", "budget_calibration",
    "multi_model_harness_alignment",
)


def credits(value: object) -> int:
    """Convert nonnegative credits to exact integer nano-credits."""
    if value is None or isinstance(value, bool):
        raise StudyError("Credit amounts must be explicit nonnegative numbers")
    try:
        amount = Decimal(str(value)) * NANO
    except InvalidOperation as error:
        raise StudyError("Invalid credit amount") from error
    if not amount.is_finite() or amount < 0 or amount != amount.to_integral_value():
        raise StudyError("Credit amounts must be finite, nonnegative nano-credit multiples")
    return int(amount)


def historical_credit_provisions(cfg: dict, *, smoke: bool = False) -> list[dict]:
    """Keep specifically approved historical holds separate from actual usage."""
    provisions = cfg.get("historical_credit_provisions", [])
    if provisions not in ([], [APPROVED_HISTORICAL_PROVISION],
                          [APPROVED_HISTORICAL_PROVISION, APPROVED_STARTUP_PROVISION],
                          [APPROVED_HISTORICAL_PROVISION, APPROVED_STARTUP_PROVISION,
                           APPROVED_RENEWED_PROVISION],
                          [APPROVED_HISTORICAL_PROVISION, APPROVED_STARTUP_PROVISION,
                           APPROVED_RENEWED_PROVISION, APPROVED_FEATURE_DIAGNOSTIC_PROVISION],
                          [APPROVED_HISTORICAL_PROVISION, APPROVED_STARTUP_PROVISION,
                           APPROVED_RENEWED_PROVISION, APPROVED_FEATURE_DIAGNOSTIC_PROVISION,
                           APPROVED_V4_DIAGNOSTIC_PROVISION],
                          [APPROVED_HISTORICAL_PROVISION, APPROVED_STARTUP_PROVISION,
                           APPROVED_RENEWED_PROVISION, APPROVED_FEATURE_DIAGNOSTIC_PROVISION,
                           APPROVED_V4_DIAGNOSTIC_PROVISION, APPROVED_INTERRUPTED_CALIBRATION_PROVISION]):
        raise StudyError("Historical provision must match the exact owner-approved attempt and evidence")
    if smoke:
        return []
    return [{
        "attempt_id": item["attempt_id"],
        "reserved_nano": credits(item["reserved_credits"]),
        "actual_nano": None,
        "status": "unknown",
        "source_commit": item["source_commit"],
        "evidence_sha256": item["evidence_sha256"],
        "approval": item["approval"],
    } for item in provisions]


def validate_config(cfg: dict, *, smoke: bool) -> None:
    """Reject unaffordable, unknown or unbounded controller settings."""
    expected = {"seed", "ceiling_credits", "prior_credits", "session_reserve_credits", "session_soft_limit_credits",
                "max_attempts", "study_timeout_seconds", "min_disk_gib", "freeze_manifest"}
    if set(cfg) - {"historical_credit_provisions"} != expected:
        raise StudyError("Configuration has missing or unknown fields; never put credentials in config")
    if not 0 < credits(cfg["ceiling_credits"]) <= MAX_CREDITS:
        raise StudyError("Aggregate ceiling must be positive and at most 300,000 AI credits")
    prior = 0 if smoke else credits(cfg["prior_credits"])
    if prior > credits(cfg["ceiling_credits"]):
        raise StudyError("Prior pilot spending exceeds aggregate ceiling")
    provisions = historical_credit_provisions(cfg, smoke=smoke)
    minimum_prior = ("146.17332" if len(provisions) >= 6
                     else "21.79019" if len(provisions) >= 4 else "17.59833")
    if provisions and prior < credits(minimum_prior):
        raise StudyError("Historical provision requires the confirmed known prior spending")
    if prior + sum(item["reserved_nano"] for item in provisions) > credits(cfg["ceiling_credits"]):
        raise StudyError("Prior spending and historical provisions exceed aggregate ceiling")
    if credits(cfg["session_reserve_credits"]) != 300 * NANO:
        raise StudyError("Session reservation must match the nominal 300-credit allowance")
    soft = cfg["session_soft_limit_credits"]
    if type(soft) is not int or not 30 <= soft <= 300:
        raise StudyError("Session soft limit must be an integer from 30 through the nominal reservation")
    if credits(cfg["session_reserve_credits"]) > credits(cfg["ceiling_credits"]):
        raise StudyError("Session reservation must fit the aggregate ceiling")
    for name, upper in (("max_attempts", 2), ("study_timeout_seconds", 30 * 86400),
                        ("min_disk_gib", 10000)):
        if type(cfg[name]) is not int or not 1 <= cfg[name] <= upper:
            raise StudyError(f"{name} must be an integer in 1..{upper}")
    if type(cfg["seed"]) is not int:
        raise StudyError("seed must be an integer")
    if not isinstance(cfg["freeze_manifest"], str):
        raise StudyError("freeze_manifest must be a relative path")


def fingerprint(root: Path = ROOT) -> str:
    """Hash all execution inputs, including untracked changes but excluding caches."""
    digest = hashlib.sha256()
    for target in INPUTS:
        source = root / target
        if source.is_symlink():
            raise StudyError("Execution inputs must not contain symlinks")
        for path in [source] if source.is_file() else sorted(source.rglob("*")):
            relative = path.relative_to(root)
            if ("__pycache__" in path.parts or ".pytest_cache" in path.parts
                    or relative.parts[:3] == ("harness", "copilot-sdk", "node_modules")):
                continue
            if path.is_symlink():
                raise StudyError("Execution inputs must not contain symlinks")
            if path.is_file() and path != root / "protocol/freeze.json":
                digest.update(path.relative_to(root).as_posix().encode() + b"\0")
                digest.update(b"x" if path.stat().st_mode & 0o111 else b"-")
                digest.update(path.read_bytes())
    return digest.hexdigest()


REPLICATE_OPTIONS = (12, 21, 33)


def selected_replicates(value=None) -> int:
    """Validate the prespecified per-model/per-arm allocation."""
    design = read_json(ROOT / "protocol/pilot-estimation.json")["study"]
    if design.get("replicate_options") != list(REPLICATE_OPTIONS):
        raise StudyError("Protocol replicate options differ from the supported allocation")
    count = design["runs_per_arm"] if value is None else value
    if type(count) is not int or count not in REPLICATE_OPTIONS:
        raise StudyError("Replicates must be 12, 21 or 33 per model/arm")
    return count


def schedule(smoke: bool, phase: str, seed: int, replicates: int | None = None,
             *, short_calibration: bool = False) -> list[dict]:
    """Randomise arm order in fixed replicate blocks; smoke is never study data."""
    if short_calibration and (smoke or phase != "calibration"):
        raise StudyError("Short calibration is available only in the calibration phase")
    rng = random.Random(seed)
    cells = []
    calibration = phase in ("pilot", "calibration")
    design = read_json(ROOT / "protocol/pilot-estimation.json")["study"]
    if design.get("arms") != list(POST_KINDS) or design.get("analysis_design") != MODEL_DESIGN:
        raise StudyError("Protocol arms differ from the supported five-arm design")
    models = design["model_roster"]
    if (not isinstance(models, list) or len(models) != 3
            or any(not isinstance(model, str) for model in models)
            or set(models) != {"gpt-6.1-sol", "claude-sonnet-5.5", "gemini-4-argon"}):
        raise StudyError("Protocol must declare the three approved model candidates")
    if replicates is not None and (smoke or calibration):
        raise StudyError("Replicate selection applies only to estimation, not calibration or smoke")
    count = design["calibration_runs_per_arm"] if calibration else selected_replicates(replicates)
    if calibration and (type(count) is not int or count != 1):
        raise StudyError("Protocol allocation differs from the approved per-model design")
    for replicate in range(1, 2 if smoke else count + 1):
        block_models = [None] if smoke else list(models)
        rng.shuffle(block_models)
        for model in block_models:
            arms = list("ABC" if smoke else "ABCDE")
            rng.shuffle(arms)
            for arm in arms:
                prefix = "smoke" if smoke else f"{phase}-{model}"
                cell = {"run_id": f"{prefix}-{arm}-{replicate:02d}",
                        "arm": arm, "features": 1 if smoke or short_calibration else 10,
                        "change_request": not smoke and not calibration}
                if not smoke:
                    cell.update(assigned_model=model, analysis_design=MODEL_DESIGN, replicate=replicate)
                    if not calibration:
                        cell["replicates_per_model_arm"] = count
                cells.append(cell)
    return cells


def quarantine_exposure(ledger: dict, policy: dict | None) -> tuple[int, int]:
    """Count full unresolved reservations, never treating provisions as measured spending."""
    entries = [entry for entry in ledger["entries"].values() if entry["status"] == "quarantine_hold"]
    if not entries:
        return 0, 0
    if not policy:
        raise StudyError("Quarantined unknown usage requires the original owner-approved resilience policy")
    resilience_policy({"resilience_policy": policy})
    if any(type(entry.get("reserved_nano")) is not int or entry["reserved_nano"] <= 0
           or entry.get("actual_nano") is not None for entry in entries):
        raise StudyError("Invalid quarantined unknown-charge reservation")
    exposure = sum(entry["reserved_nano"] for entry in entries)
    if len(entries) > policy["max_quarantined_attempts"] or exposure > credits(policy["max_quarantined_credits"]):
        raise StudyError("Quarantined unknown-charge risk envelope exhausted")
    return len(entries), exposure


def reserve(ledger: dict, attempt: str, amount: int, *, quarantine_policy: dict | None = None) -> None:
    """Admit work only when known spending plus all held budget fits."""
    if type(amount) is not int or amount < 0:
        raise StudyError("Reservation must be nonnegative integer nano-credits")
    if attempt in ledger["entries"]:
        raise StudyError("Attempt reservation already exists")
    provisions = ledger.get("historical_credit_provisions", [])
    if any(item["attempt_id"] == attempt for item in provisions):
        raise StudyError("Historical provision attempt cannot be reused")
    entries = ledger["entries"].values()
    if any(entry["status"] == "unknown" for entry in entries):
        raise StudyError("Unknown usage holds its reservation and blocks new work")
    quarantine_exposure(ledger, quarantine_policy)
    if any(entry["status"] == "complete" and entry["actual_nano"] > entry["reserved_nano"] for entry in entries):
        raise StudyError("Actual credits exceeded a reservation; new work stays blocked")
    handoff = ledger.get("calibration_handoff") or {}
    used = (ledger["prior_nano"] + handoff.get("known_nano", 0) + handoff.get("held_nano", 0)
            + sum(item["reserved_nano"] for item in provisions) + sum(
        entry["actual_nano"] if entry["status"] == "complete" else entry["reserved_nano"]
        for entry in ledger["entries"].values()))
    if used + amount > ledger["ceiling_nano"]:
        raise StudyError("Aggregate credit admission ceiling exhausted; no new work launched")
    ledger["entries"][attempt] = {"reserved_nano": amount, "actual_nano": None, "status": "reserved"}


def accounted_nano(usage: dict | None) -> int | None:
    """Use the same explicit completeness precedence as the corrected analyzer."""
    nano = usage.get("totalNanoAiu") if isinstance(usage, dict) else None
    complete = isinstance(usage, dict) and usage.get(
        "credits_complete", usage.get("aiCreditsStatus") == "complete") is True
    if not complete or type(nano) is not int or nano < 0:
        return None
    return nano


RETRY_HOLD = "retry_hold"
MAX_UNACCOUNTED_FAILURES = 3


def retry_hold_policy(manifest: dict | None) -> dict | None:
    """Return the owner-authorized bound for sessions that finish with an unbilled failed request."""
    policy = (manifest or {}).get("unaccounted_retry_hold_policy")
    if policy is None:
        return None
    if (not isinstance(policy, dict) or set(policy) != {"max_holds", "approval", "approved_at"}
            or type(policy["max_holds"]) is not int or not 1 <= policy["max_holds"] <= 200
            or not isinstance(policy["approval"], str) or not policy["approval"].strip()):
        raise StudyError("Invalid unaccounted retry hold policy")
    try:
        approved = datetime.fromisoformat(policy["approved_at"])
    except (TypeError, ValueError) as error:
        raise StudyError("Retry hold approval requires an ISO 8601 timestamp") from error
    if approved.utcoffset() is None:
        raise StudyError("Retry hold approval timestamp must include a timezone")
    return policy


def resilience_policy(manifest: dict | None) -> dict | None:
    """Validate prospective owner authorization without enabling it for existing studies."""
    policy = (manifest or {}).get("resilience_policy")
    if policy is None:
        return None
    fields = {"schema", "approval", "approved_at", "max_quarantined_attempts",
              "max_quarantined_credits", "route_failure_threshold", "route_cooldown_seconds",
              "retry_backoff_seconds", "retry_max_backoff_seconds"}
    if (not isinstance(policy, dict) or set(policy) != fields
            or policy["schema"] != "study-resilience-policy/v1"
            or not isinstance(policy["approval"], str) or not policy["approval"].strip()):
        raise StudyError("Invalid prospective resilience policy")
    for name, lower, upper in (("max_quarantined_attempts", 0, 200),
                               ("route_failure_threshold", 1, 20),
                               ("route_cooldown_seconds", 1, 86400),
                               ("retry_backoff_seconds", 0, 300),
                               ("retry_max_backoff_seconds", 0, 3600)):
        if type(policy[name]) is not int or not lower <= policy[name] <= upper:
            raise StudyError(f"Invalid resilience policy bound: {name}")
    held = credits(policy["max_quarantined_credits"])
    if (held > MAX_CREDITS or (held == 0) != (policy["max_quarantined_attempts"] == 0)
            or policy["retry_backoff_seconds"] > policy["retry_max_backoff_seconds"]):
        raise StudyError("Inconsistent resilience policy bounds")
    try:
        approved = datetime.fromisoformat(policy["approved_at"])
    except (TypeError, ValueError) as error:
        raise StudyError("Resilience approval requires an ISO 8601 timestamp") from error
    if approved.utcoffset() is None:
        raise StudyError("Resilience approval timestamp must include a timezone")
    return policy


def validate_attempt_outcome(outcome: object) -> dict:
    """Reject unknown outcome schemas rather than guessing safety or recovery eligibility."""
    required = {"schema", "work", "safety", "accounting", "quiescent", "failure"}
    if (not isinstance(outcome, dict) or set(outcome) - {"native_calls", "native_failures"} != required
            or outcome["schema"] != "study-attempt-outcome/v1"
            or outcome["work"] not in ("complete", "partial", "unavailable")
            or outcome["safety"] not in ("valid", "violated", "unverified")
            or outcome["accounting"] not in ("final", "provisional", "unknown")
            or type(outcome["quiescent"]) is not bool):
        raise StudyError("Invalid typed attempt outcome; preserve evidence for investigation")
    for name in ("native_calls", "native_failures"):
        if name in outcome and (type(outcome[name]) is not int or not 0 <= outcome[name] <= 1_000_000):
            raise StudyError("Invalid typed attempt counters")
    failure = outcome["failure"]
    if failure is None:
        if outcome["work"] != "complete" or outcome["accounting"] != "final" or outcome["safety"] != "valid":
            raise StudyError("Incomplete typed outcome lacks a failure disposition")
        return outcome
    stages = {"initial_request", "runtime_setup", "runtime_startup", "session_create", "session_tool_catalog",
              "session_send", "session_shutdown", "runtime_cleanup", "output_flush", "accounting"}
    if (not isinstance(failure, dict) or set(failure) != {"kind", "stage", "retry_after_seconds"}
            or failure["kind"] not in ("provider_transient", "transport", "timeout", "contract",
                                        "accounting_incomplete", "authentication")
            or failure["stage"] not in stages):
        raise StudyError("Unknown typed failure contract")
    delay = failure["retry_after_seconds"]
    if delay is not None and (type(delay) not in (int, float) or not math.isfinite(delay) or delay < 0):
        raise StudyError("Invalid typed Retry-After evidence")
    return outcome


def supervised_terminal(directory: Path, attempt: dict, model: str, commit: str,
                        *, expected_sha256: str | None = None) -> dict:
    """Verify source-bound terminal evidence without importing work or replaying a request."""
    relative = attempt.get("directory")
    if (not isinstance(relative, str) or not relative or Path(relative).is_absolute()
            or relative != Path(relative).as_posix() or ".." in Path(relative).parts
            or Path(relative).parts[-2:] != ("attempts", attempt["id"])):
        raise StudyError("Invalid supervised attempt directory")
    parent = directory
    for part in Path(relative).parts:
        parent = parent / part
        if parent.is_symlink() or not parent.is_dir():
            raise StudyError("Supervised evidence contains an unsafe directory")

    def payload(path: Path, limit: int) -> bytes:
        if (path.parent.is_symlink() or path.is_symlink() or not path.is_file()
                or not path.resolve().is_relative_to(directory.resolve()) or path.stat().st_size > limit):
            raise StudyError("Supervised evidence is missing, unsafe or oversized")
        return path.read_bytes()

    terminal_bytes = payload(parent / "terminal.json", 2 * 1024 * 1024)
    expected = expected_sha256 or attempt.get("terminal_sha256")
    if not isinstance(expected, str) or hashlib.sha256(terminal_bytes).hexdigest() != expected:
        raise StudyError("Supervised terminal hash differs from its durable authorization")
    terminal = json.loads(terminal_bytes)
    fields = {"schema", "attempt_id", "source_commit", "request_sha256", "events_sha256", "seconds", "result"}
    if (not isinstance(terminal, dict) or set(terminal) != fields
            or terminal["schema"] != "study-transport-terminal/v1" or terminal["attempt_id"] != attempt["id"]
            or terminal["source_commit"] != commit or attempt.get("source_commit") != commit
            or type(terminal["seconds"]) not in (int, float)
            or not math.isfinite(terminal["seconds"]) or terminal["seconds"] < 0):
        raise StudyError("Supervised terminal source or duration is invalid")
    request_bytes = payload(parent / "request.json", 1024 * 1024)
    request = json.loads(request_bytes)
    if (hashlib.sha256(request_bytes).hexdigest() != terminal["request_sha256"]
            or terminal["request_sha256"] != attempt.get("request_sha256")
            or not isinstance(request, dict) or request.get("model") != model
            or request.get("reasoningEffort") != "medium"
            or request.get("resiliencePolicy") != "study-resilience-policy/v1"
            or credits(request.get("maxAiCredits")) != attempt.get("credit_limit_nano")
            or type(request.get("remainingSeconds")) not in (int, float)
            or not math.isfinite(request["remainingSeconds"])
            or not 0 < request["remainingSeconds"] <= attempt.get("seconds_limit", 0)):
        raise StudyError("Supervised request differs from the original treatment or allowance")
    result = terminal["result"]
    receipt = result.get("receipt") if isinstance(result, dict) else None
    if (not isinstance(result, dict) or set(result) != {"type", "receipt", "exit_code"}
            or result["type"] != "complete" or type(result["exit_code"]) is not int
            or result["exit_code"] not in (0, 1) or not isinstance(receipt, dict)
            or receipt.get("sdk_version") != "1.0.28" or receipt.get("cli_version") != "1.0.105"
            or receipt.get("protocol_version") != 3 or receipt.get("actual_models") != [model]
            or receipt.get("actual_reasoning_efforts") != ["medium"] or receipt.get("routing_changes") != []):
        raise StudyError("Supervised terminal treatment or transport identity differs")
    outcome = validate_attempt_outcome(receipt.get("outcome"))
    if (outcome["safety"] != "valid" or outcome["quiescent"] is not True
            or (outcome["accounting"] == "final") != (accounted_nano(receipt.get("usage")) is not None)):
        raise StudyError("Supervised terminal lacks valid safety, quiescence or accounting")
    if attempt.get("outcome") is not None and attempt["outcome"] != outcome:
        raise StudyError("Supervised outcome differs from the retained receipt")
    if attempt.get("usage") is not None and attempt["usage"] != receipt.get("usage"):
        raise StudyError("Supervised billing differs from the retained receipt")
    journal = payload(parent / "transport/events.jsonl", 64 * 1024 * 1024)
    if not journal.endswith(b"\n") or hashlib.sha256(journal).hexdigest() != terminal["events_sha256"]:
        raise StudyError("Supervised journal hash or final framing differs")
    records = [json.loads(line) for line in journal.splitlines()]
    sessions = {record.get("sessionId") for record in records
                if isinstance(record, dict) and record.get("type") == "event"}
    if (not records or records[-1] != result
            or any(not isinstance(record, dict) or record.get("type") not in ("event", "tool", "complete")
                   for record in records)
            or sum(record["type"] == "complete" for record in records) != 1
            or sessions != {receipt.get("session_id")} or None in sessions or "" in sessions):
        raise StudyError("Supervised journal does not contain one correlated terminal outcome")
    return terminal


def validate_supervisor_state(directory: Path, state: dict, manifest: dict | None) -> None:
    """Revalidate persistent quarantine and route evidence before any resumed admission."""
    policy = resilience_policy(manifest)
    supervisor = state.get("supervisor")
    if supervisor is not None:
        if (not policy or not isinstance(supervisor, dict)
                or set(supervisor) != {"schema", "routes"} or supervisor["schema"] != "study-supervisor/v1"
                or not isinstance(supervisor["routes"], dict)):
            raise StudyError("Persistent supervisor lacks its original approved policy")
        models = {cell.get("assigned_model") for cell in state["cells"]}
        for model, route in supervisor["routes"].items():
            if (model not in models or not isinstance(route, dict)
                    or set(route) != {"consecutive_failures", "blocked_until"}
                    or type(route["consecutive_failures"]) is not int or route["consecutive_failures"] < 0
                    or type(route["blocked_until"]) not in (int, float)
                    or not math.isfinite(route["blocked_until"]) or route["blocked_until"] < 0):
                raise StudyError("Invalid persistent provider route state")
    quarantine_exposure(state["ledger"], policy)
    entries = state["ledger"]["entries"]
    authorized_sources = {state["identity"]["commit"],
                          *(record["original_commit"] for record in recovery_records(state))}
    if supervisor is not None or any(entry["status"] == "quarantine_hold" for entry in entries.values()):
        ids = [attempt["id"] for cell in state["cells"] for attempt in cell["attempts"]]
        if len(set(ids)) != len(ids) or set(ids) != set(entries):
            raise StudyError("Supervised attempt and reservation inventories differ")
    for cell in state["cells"]:
        for attempt in cell["attempts"]:
            if entries[attempt["id"]]["status"] != "quarantine_hold" and not attempt.get("supervision"):
                continue
            source_commit = attempt.get("source_commit")
            if source_commit not in authorized_sources:
                raise StudyError("Supervised attempt source lacks a verified recovery transition")
            terminal = supervised_terminal(directory, attempt, cell["assigned_model"], source_commit)
            outcome = terminal["result"]["receipt"]["outcome"]
            observation = attempt.get("supervision")
            if (not isinstance(observation, dict)
                    or set(observation) != {"action", "observed_at", "source_commit", "route"}
                    or observation["action"] not in ("retain_original_allowance", "quarantine_cell",
                                                       "pause_unknown_risk_exhausted")
                    or observation["source_commit"] != source_commit
                    or observation["route"] != cell["assigned_model"]
                    or type(observation["observed_at"]) not in (int, float)
                    or not math.isfinite(observation["observed_at"]) or observation["observed_at"] < 0):
                raise StudyError("Persistent recovery action differs from its source and route")
            if (not policy or attempt.get("status") != "infra_failed" or attempt.get("measurement")
                    or outcome["work"] == "complete"
                    or outcome["failure"]["kind"] not in ("provider_transient", "transport", "timeout")):
                raise StudyError("Persistent operational recovery is not an unmeasured infrastructure failure")
            if entries[attempt["id"]]["status"] == "quarantine_hold" and (
                    cell.get("status") != "quarantined" or outcome["accounting"] == "final"
                    or attempt.get("cost_included_in_step")
                    or attempt.get("supervision", {}).get("action") != "quarantine_cell"):
                raise StudyError("Quarantined reservation differs from its retained cell outcome")
            if outcome["accounting"] == "final" and (
                    entries[attempt["id"]]["status"] != "complete"
                    or entries[attempt["id"]]["actual_nano"] != accounted_nano(attempt.get("usage"))):
                raise StudyError("Supervised final accounting differs from its retained reservation")
            decision = attempt.get("recovery_action")
            if decision is not None and (
                    not isinstance(decision, dict)
                    or set(decision) != {"action", "decided_at", "not_before", "source_commit"}
                    or decision["action"] != "retry_original_step"
                    or decision["source_commit"] != source_commit
                    or any(type(decision[key]) not in (int, float) or not math.isfinite(decision[key])
                           for key in ("decided_at", "not_before"))
                    or decision["not_before"] < decision["decided_at"]):
                raise StudyError("Persistent retry backoff differs from its original authorization")
    if state.get("operational_recoveries"):
        from prepare_estimation_recovery import validate_operational_recoveries

        validate_operational_recoveries(directory, state, manifest)


def supervise_failure_state(directory: Path, state: dict, manifest: dict | None,
                            cell: dict, attempt: dict) -> None:
    """Apply one evidence-checked supervision transition; the caller owns locking and persistence."""
    policy = resilience_policy(manifest)
    if not policy or attempt.get("supervision"):
        return
    outcome = validate_attempt_outcome(attempt.get("outcome"))
    if (outcome["safety"] != "valid" or outcome["quiescent"] is not True
            or outcome["work"] == "complete" or not outcome["failure"]
            or outcome["failure"]["kind"] not in ("provider_transient", "transport", "timeout")
            or attempt.get("measurement") or attempt.get("cost_included_in_step")
            or cell["run_id"] in state.get("writers", {})
            or attempt.get("source_commit") != state["identity"]["commit"]):
        raise StudyError("Operational recovery lacks valid quiescent unmeasured evidence")
    supervised_terminal(directory, attempt, cell["assigned_model"], state["identity"]["commit"])
    supervisor = state.setdefault("supervisor", {"schema": "study-supervisor/v1", "routes": {}})
    route = supervisor["routes"].setdefault(cell["assigned_model"],
                                           {"consecutive_failures": 0, "blocked_until": 0})
    route["consecutive_failures"] += 1
    now = time.time()
    if route["consecutive_failures"] >= policy["route_failure_threshold"]:
        route["blocked_until"] = max(route["blocked_until"], now + policy["route_cooldown_seconds"])
    retry_after = outcome["failure"]["retry_after_seconds"]
    if retry_after is not None:
        route["blocked_until"] = max(route["blocked_until"], now + retry_after)
    action = "retain_original_allowance"
    entry = state["ledger"]["entries"][attempt["id"]]
    if accounted_nano(attempt.get("usage")) is None:
        if entry["status"] != "unknown":
            raise StudyError("Unfinished provider request lacks an unknown reservation")
        count, exposure = quarantine_exposure(state["ledger"], policy)
        if (count < policy["max_quarantined_attempts"]
                and exposure + entry["reserved_nano"] <= credits(policy["max_quarantined_credits"])):
            entry["status"] = "quarantine_hold"
            action = "quarantine_cell"
        else:
            action = "pause_unknown_risk_exhausted"
        cell["status"] = "quarantined"
    attempt["supervision"] = {"action": action, "observed_at": now,
                              "source_commit": state["identity"]["commit"], "route": cell["assigned_model"]}


def retry_hold_lower_bound(usage: dict | None) -> tuple[int, int] | None:
    """Read only a verified usage floor; it is never a total and never a zero-cost claim."""
    if (not isinstance(usage, dict) or usage.get("credits_complete") is not False
            or usage.get("totalNanoAiu") is not None):
        return None
    nano, count = usage.get("lowerBoundNanoAiu"), usage.get("unaccountedFailedRequests")
    if (type(nano) is not int or nano < 0 or type(count) is not int
            or not 1 <= count <= MAX_UNACCOUNTED_FAILURES):
        return None
    return nano, count


def retry_hold_usage(receipt: dict, exit_code: object, model: str) -> dict | None:
    """Recognize only a session that ended normally with every successful call fully billed."""
    bound = receipt.get("usage_lower_bound")
    usage = receipt.get("usage")
    failures = receipt.get("provider_failures")
    calls = receipt.get("model_calls")
    if (receipt.get("protocol_error") != "provider_retry_usage_incomplete" or exit_code != 1
            or receipt.get("failure_stage") is not None
            or not isinstance(usage, dict) or usage.get("credits_complete") is not False
            or usage.get("totalNanoAiu") is not None
            or not isinstance(bound, dict) or set(bound) != {"totalNanoAiu", "unaccounted_failed_requests"}
            or type(bound["totalNanoAiu"]) is not int or bound["totalNanoAiu"] < 0
            or type(bound["unaccounted_failed_requests"]) is not int
            or not isinstance(failures, list) or not isinstance(calls, list) or not calls
            or len(failures) > MAX_UNACCOUNTED_FAILURES
            or sum(item.get("accounting_complete") is False for item in failures)
            != bound["unaccounted_failed_requests"] > 0
            or receipt.get("actual_models") != [model] or receipt.get("actual_reasoning_efforts") != ["medium"]
            or receipt.get("routing_changes") != []
            or any(item.get("aiCreditsStatus") != "complete" or type(item.get("totalNanoAiu")) is not int
                   for item in calls)
            or sum(item["totalNanoAiu"] for item in calls) != bound["totalNanoAiu"]):
        return None
    return {"credits_complete": False, "totalNanoAiu": None, "aiCreditsStatus": "partial",
            "lowerBoundNanoAiu": bound["totalNanoAiu"],
            "unaccountedFailedRequests": bound["unaccounted_failed_requests"]}


def reconcile(ledger: dict, attempt: str, usage: dict | None) -> None:
    """Keep missing accounting unknown; record and stop on reservation overruns."""
    entry = ledger["entries"][attempt]
    nano = accounted_nano(usage)
    if nano is None:
        bound = retry_hold_lower_bound(usage)
        if bound is None:
            entry["status"] = "unknown"
            return
        # The whole reservation stays charged against the ceiling; only the successful floor is known.
        entry.update(status=RETRY_HOLD, actual_nano=None, lower_bound_nano=bound[0],
                     unaccounted_failed_requests=bound[1])
        if bound[0] > entry["reserved_nano"]:
            raise StudyError("Actual credits exceeded reservation; billing bound is not enforced")
        return
    entry.update(actual_nano=nano, status="complete")
    if nano > entry["reserved_nano"]:
        raise StudyError("Actual credits exceeded reservation; billing bound is not enforced")


def freeze_errors(cfg: dict, root: Path = ROOT, *, unregistered: dict | None = None) -> list[str]:
    """Verify owner-supplied provenance and gates; never create or move a tag."""
    if unregistered is not None:
        errors = []
        commit = unregistered.get("commit")
        if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
            errors.append("Unregistered execution requires a full source commit SHA")
        elif command(["git", "rev-parse", "HEAD"], cwd=root) != commit:
            errors.append("HEAD differs from the disclosed unregistered source commit")
        if unregistered.get("registration_status") != "unregistered":
            errors.append("Changed design must be explicitly identified as unregistered")
        if unregistered.get("public_disclosure_url") != (
                f"https://github.com/jmservera/ama-thought-mve/commit/{commit}"):
            errors.append("Public disclosure must identify the exact source commit")
        if (unregistered.get("owner_confirms_public_disclosure") is not True
                or not isinstance(unregistered.get("disclosed_at"), str)
                or not unregistered["disclosed_at"].strip()):
            errors.append("Owner must attest public disclosure and its timestamp before collection")
        else:
            try:
                disclosed_at = datetime.fromisoformat(unregistered["disclosed_at"])
                if disclosed_at.utcoffset() is None:
                    raise ValueError("Missing timezone")
            except ValueError:
                errors.append("Disclosure timestamp must be ISO 8601 with a timezone")
        if unregistered.get("inputs_sha256") != fingerprint(root):
            errors.append("Unregistered source input hash mismatch")
        for gate in GATES:
            if not isinstance(unregistered.get(gate), str) or not unregistered[gate].strip():
                errors.append(f"Owner evidence missing: {gate}")
        try:
            resilience_policy(unregistered)
        except StudyError as error:
            errors.append(str(error))
        return errors
    manifest_path = (root / cfg["freeze_manifest"]).resolve()
    if not manifest_path.is_relative_to(root / "protocol") or not manifest_path.is_file():
        return ["Missing owner-approved protocol/freeze.json (no protocol is declared frozen)"]
    manifest = read_json(manifest_path)
    errors = []
    commit = manifest.get("commit", "")
    tag = manifest.get("tag", "")
    if not isinstance(commit, str) or not re.fullmatch(r"[0-9a-f]{40}", commit):
        errors.append("Freeze requires a full commit SHA")
    elif command(["git", "rev-parse", "HEAD"], cwd=root) != commit:
        # A subsequent manifest-only commit avoids a self-referential commit SHA.
        differences = command(["git", "diff", "--name-only", commit, "HEAD"], cwd=root).splitlines()
        if differences != [manifest_path.relative_to(root).as_posix()]:
            errors.append("HEAD differs from authorised freeze beyond its provenance manifest")
    if not isinstance(tag, str) or not re.fullmatch(r"protocol-frozen-v[0-9]+", tag):
        errors.append("Freeze requires a new owner-authorised versioned tag, not legacy protocol-frozen")
    elif command(["git", "rev-parse", f"refs/tags/{tag}^{{commit}}"], cwd=root) != commit:
        errors.append("Freeze tag does not resolve to authorised commit")
    if manifest.get("inputs_sha256") != fingerprint(root):
        errors.append("Protocol/suite/prompts/runtime/analysis input hash mismatch")
    if not isinstance(manifest.get("registration_url"), str) or not manifest["registration_url"].startswith("https://"):
        errors.append("Prospective registration URL missing")
    if not manifest.get("registration_date"):
        errors.append("Prospective registration date missing")
    for gate in GATES:
        if not isinstance(manifest.get(gate), str) or not manifest[gate].strip():
            errors.append(f"Owner evidence missing: {gate}")
    return errors


def preflight(cfg: dict, *, smoke: bool, root: Path = ROOT, unregistered: dict | None = None) -> list[str]:
    """Check prerequisites without launching a model, changing git or printing tokens."""
    errors = []
    try:
        validate_config(cfg, smoke=smoke)
    except (StudyError, KeyError) as error:
        errors.append(str(error))
    if sys.version_info < (3, 11):  # noqa: UP036 - check the VM, not just the development interpreter.
        errors.append("Python 3.11+ required")
    for tool in (("git", "make") if smoke else ("git", "node", "copilot", "docker")):
        if not shutil.which(tool):
            errors.append(f"Required tool missing: {tool}")
    minimum = cfg.get("min_disk_gib")
    if type(minimum) is int and shutil.disk_usage(root).free < minimum * 1024**3:
        errors.append(f"Insufficient disk: require {minimum} GiB free")
    if not smoke:
        if shutil.which("git") and command(["git", "status", "--porcelain"], cwd=root):
            errors.append("Live execution requires a clean git worktree")
        for tool, args, version in (
            ("copilot", ["copilot", "--no-auto-update", "--version"], "1.0.105"),
        ):
            if shutil.which(tool):
                output = command(args).strip()
                if tool == "copilot":
                    matched = re.fullmatch(rf"(?:GitHub Copilot CLI )?{re.escape(version)}\.?",
                                           output.splitlines()[0] if output else "")
                else:
                    matched = re.search(rf"(?<![\d.]){re.escape(version)}(?![\d.])", output)
                if not matched:
                    errors.append(f"{tool} must be pinned to {version}")
        if isinstance(cfg.get("freeze_manifest"), str):
            try:
                errors.extend(freeze_errors(cfg, root) if unregistered is None
                              else freeze_errors(cfg, root, unregistered=unregistered))
            except (StudyError, OSError, ValueError, subprocess.TimeoutExpired):
                errors.append("Freeze evidence unreadable or tag verification failed")
        from isolated_runtime import runtime_errors
        errors.extend(runtime_errors(cfg, root) if unregistered is None
                      else runtime_errors(cfg, root, manifest=unregistered))
    return errors


def budget_policy(cfg: dict) -> dict:
    """Expose operational buffers without claiming a provider billing guarantee."""
    return {
        "session_soft_limit_credits": cfg.get("session_soft_limit_credits"),
        "session_reservation_credits": cfg.get("session_reserve_credits"),
        "D_feature_soft_limit_credits": 2 * cfg["session_soft_limit_credits"],
        "D_feature_reservation_credits": 2 * cfg["session_reserve_credits"],
        "local_admission_ceiling_credits": cfg.get("ceiling_credits"),
        "registered_ceiling_credits": MAX_CREDITS // NANO,
        "known_prior_credits": cfg.get("prior_credits"),
        "historical_credit_provisions": cfg.get("historical_credit_provisions", []),
        "historical_usage_complete": not bool(cfg.get("historical_credit_provisions")),
        "company_hard_limit_credits_owner_reported": 1000000,
        "company_hard_limit_independently_verified": False,
        "owner_accepted_soft_limit_overshoot_risk": True,
        "study_specific_provider_hard_cap_required": False,
        "hard_billing_guarantee": False,
        "warning": "CLI session limits are soft: an in-flight response can finish over the limit. "
                   "The local study admission stop includes prior/all-attempt usage and reservations, "
                   "but neither it nor the buffer guarantees final billed consumption.",
    }


@contextmanager
def study_lock(directory: Path):
    """Allow only one writer per durable study, including recovery and publication."""
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    with (directory / "controller.lock").open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise StudyError("Another controller owns this study") from error
        yield


@contextmanager
def paid_study_lock():
    """Keep distinct paid studies from admitting work concurrently on this checkout."""
    directory = ROOT / ".study" / ".paid-study-controller"
    if directory.is_symlink():
        raise StudyError("Paid-study lock directory must not be symlinked")
    with study_lock(directory):
        yield


def calibration_handoff(directory: Path, cfg: dict, unregistered: dict) -> dict:
    """Validate a completed same-source calibration and retain exact all-attempt accounting."""
    path = directory / "state.json"
    if directory.is_symlink() or path.is_symlink() or not path.is_file():
        raise StudyError("Completed calibration state is required for estimation")
    payload = path.read_bytes()
    state = json.loads(payload)
    if not isinstance(state, dict):
        raise StudyError("Invalid calibration state")
    identity = state["identity"]
    expected_provenance = source_provenance(unregistered)
    if (identity.get("smoke") is not False or identity.get("phase") != "calibration"
            or identity.get("study_id") != directory.name
            or identity.get("config") != cfg or identity.get("commit") != unregistered.get("commit")
            or identity.get("inputs_sha256") != unregistered.get("inputs_sha256")
            or identity.get("source_provenance") != expected_provenance
            or identity.get("calibration_plan") != "one-feature-per-model-arm"
            or state.get("status") != "completed"):
        raise StudyError("Calibration must be completed with the same unregistered source and configuration")
    cells = state["cells"]
    expected = schedule(False, "calibration", cfg["seed"], short_calibration=True)
    if (len(cells) != len(expected)
            or any({key: cell.get(key) for key in planned} != planned or cell["status"] != "completed"
                   for cell, planned in zip(cells, expected))):
        raise StudyError("Calibration sampling frame is incomplete or differs from the short plan")
    for cell in cells:
        expected_steps = ["f01-feature"]
        if POST_KINDS[cell["arm"]] is not None:
            expected_steps.append(f"f01-{POST_KINDS[cell['arm']]}")
        journal = directory / "runs" / cell["run_id"] / "steps.jsonl"
        if journal.is_symlink() or not journal.is_file():
            raise StudyError("Calibration durable step journal is missing or unsafe")
        text = journal.read_text(encoding="utf-8")
        if not text.endswith("\n"):
            raise StudyError("Calibration durable step journal is incomplete")
        records = [json.loads(line) for line in text.splitlines()]
        if [record["step"] for record in records] != expected_steps:
            raise StudyError("Calibration durable steps differ from the short plan")
        for record in records:
            attempt_ids = [attempt["id"] for attempt in cell["attempts"] if attempt["step"] == record["step"]]
            if not attempt_ids or record.get("attempts") != attempt_ids:
                raise StudyError("Calibration durable step and attempt accounting differ")
    ledger = state["ledger"]
    if (ledger["prior_nano"] != credits(cfg["prior_credits"])
            or ledger["ceiling_nano"] != credits(cfg["ceiling_credits"])
            or ledger.get("historical_credit_provisions") != historical_credit_provisions(cfg)):
        raise StudyError("Calibration baseline accounting differs from estimation")
    attempts = [attempt for cell in cells for attempt in cell["attempts"]]
    ids = [attempt["id"] for attempt in attempts]
    entries = ledger["entries"]
    if len(ids) != len(set(ids)) or set(ids) != set(entries):
        raise StudyError("Calibration attempts and ledger entries do not match")
    imported = []
    for attempt in attempts:
        entry = entries[attempt["id"]]
        reserved, actual = entry["reserved_nano"], entry["actual_nano"]
        if type(reserved) is not int or reserved < 0:
            raise StudyError("Invalid calibration reservation")
        if entry["status"] == "complete":
            if (type(actual) is not int or actual < 0 or actual > reserved
                    or accounted_nano(attempt.get("usage")) != actual):
                raise StudyError("Calibration completed charge does not match its receipt or reservation")
        elif entry["status"] == "restart_hold":
            restart = next((item for item in state.get("restart_history", [])
                            if attempt["id"] in item.get("interrupted_attempts", [])), None)
            if (actual is not None or attempt["status"] != "restart_interrupted" or restart is None
                    or attempt.get("interrupted_boot_id") != restart.get("previous_boot_id")
                    or attempt.get("recovered_boot_id") != restart.get("boot_id")
                    or restart.get("previous_boot_id") == restart.get("boot_id")):
                raise StudyError("Invalid calibration restart hold")
        else:
            raise StudyError("Unresolved calibration accounting blocks estimation")
        if not attempt.get("cost_included_in_step"):
            raise StudyError("Calibration attempt is not included in its durable step")
        imported.append({"attempt_id": attempt["id"], "status": entry["status"],
                         "reserved_nano": reserved, "actual_nano": actual})
    known = sum(entry["actual_nano"] for entry in imported if entry["status"] == "complete")
    held = sum(entry["reserved_nano"] for entry in imported if entry["status"] == "restart_hold")
    return {"study_id": directory.name, "state_sha256": hashlib.sha256(payload).hexdigest(),
            "known_nano": known, "held_nano": held, "entries": imported}


def source_provenance(unregistered: dict) -> dict:
    return {"registration_status": "unregistered",
            "public_disclosure_url": unregistered["public_disclosure_url"],
            "disclosed_at_owner_reported": unregistered["disclosed_at"],
            "manifest_sha256": hashlib.sha256(
                json.dumps(unregistered, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}


def recovery_incident(state_sha256: str) -> dict:
    """Accept only disclosed estimation interruptions, not arbitrary holds."""
    if state_sha256 == RECOVERY_STATE_SHA256:
        return {"source": RECOVERY_SOURCE, "attempt": RECOVERY_ATTEMPT,
                "journal_sha256": RECOVERY_JOURNAL_SHA256, "steps": 651, "attempts": 652,
                "known_nano": credits("7794.8031"), "kind": "missing_edit", "reserved_nano": 300 * NANO}
    if state_sha256 == BACKEND_RECOVERY_STATE_SHA256:
        return {"source": BACKEND_RECOVERY_SOURCE, "attempt": BACKEND_RECOVERY_ATTEMPT,
                "journal_sha256": BACKEND_RECOVERY_JOURNAL_SHA256, "steps": 878, "attempts": 880,
                "known_nano": credits("10470.87094"), "kind": "backend_500", "reserved_nano": 300 * NANO}
    if state_sha256 == SANDBOX_RECOVERY_STATE_SHA256:
        return {"source": SANDBOX_RECOVERY_SOURCE, "attempt": SANDBOX_RECOVERY_ATTEMPT,
                "journal_sha256": SANDBOX_RECOVERY_JOURNAL_SHA256, "steps": 1482, "attempts": 1485,
                "known_nano": credits("16961.29357"), "kind": "state_links",
                "reserved_nano": 300 * NANO,
                "run_id": "pilot-estimation-gpt-6.1-sol-B-06",
                "broker_metadata_sha256": SANDBOX_RECOVERY_BROKER_METADATA_SHA256,
                "broker_state_sha256": SANDBOX_RECOVERY_BROKER_STATE_SHA256,
                "broker_owner_sha256": SANDBOX_RECOVERY_BROKER_OWNER_SHA256}
    if state_sha256 == SERVICE_RECOVERY_STATE_SHA256:
        return {"source": SERVICE_RECOVERY_SOURCE, "attempt": SERVICE_RECOVERY_ATTEMPT,
                "journal_sha256": SERVICE_RECOVERY_JOURNAL_SHA256, "steps": 2082, "attempts": 2086,
                "known_nano": credits("23969.42938"), "kind": "backend_503_same_turn",
                "reserved_nano": 300 * NANO}
    if state_sha256 == TRANSPORT_RECOVERY_STATE_SHA256:
        return {"source": TRANSPORT_RECOVERY_SOURCE, "attempt": TRANSPORT_RECOVERY_ATTEMPT,
                "journal_sha256": TRANSPORT_RECOVERY_JOURNAL_SHA256, "steps": 2289, "attempts": 2294,
                "known_nano": credits("26552.15674"), "kind": "websocket_reset",
                "reserved_nano": 600 * NANO}
    if state_sha256 == CLOSE_RECOVERY_STATE_SHA256:
        return {"source": CLOSE_RECOVERY_SOURCE, "attempt": CLOSE_RECOVERY_ATTEMPT,
                "journal_sha256": CLOSE_RECOVERY_JOURNAL_SHA256, "steps": 2402, "attempts": 2408,
                "known_nano": credits("27814.55969"), "kind": "websocket_closed_1001",
                "reserved_nano": 300 * NANO}
    if state_sha256 == MIXED_RECOVERY_STATE_SHA256:
        return {"source": MIXED_RECOVERY_SOURCE, "attempt": MIXED_RECOVERY_ATTEMPT,
                "journal_sha256": MIXED_RECOVERY_JOURNAL_SHA256, "steps": 2526, "attempts": 2533,
                "known_nano": credits("29220.13966"), "kind": "backend_mixed_boundaries",
                "reserved_nano": 300 * NANO}
    if state_sha256 == UNACCOUNTED_RECOVERY_STATE_SHA256:
        return {"source": UNACCOUNTED_RECOVERY_SOURCE, "attempt": UNACCOUNTED_RECOVERY_ATTEMPT,
                "journal_sha256": UNACCOUNTED_RECOVERY_JOURNAL_SHA256, "steps": 2691, "attempts": 2699,
                "known_nano": credits("30927.78079"), "kind": "websocket_retry_unaccounted",
                "reserved_nano": 600 * NANO}
    if state_sha256 == PAIRED_RECOVERY_STATE_SHA256:
        holds = {identity: {"journal_sha256": journal, "reserved_nano": 300 * NANO}
                 for identity, journal in PAIRED_RECOVERY_HOLDS.items()}
        return {"source": PAIRED_RECOVERY_SOURCE, "holds": holds,
                "journal_sha256": holds_digest({identity: hold["journal_sha256"]
                                                for identity, hold in holds.items()}),
                "steps": 2722, "attempts": 2732, "known_nano": credits("31374.66179"),
                "kind": "websocket_retry_unaccounted",
                "reserved_nano": sum(hold["reserved_nano"] for hold in holds.values())}
    if state_sha256 == HTTP_RECOVERY_STATE_SHA256:
        holds = {identity: dict(hold) for identity, hold in HTTP_RECOVERY_HOLDS.items()}
        return {"source": HTTP_RECOVERY_SOURCE, "holds": holds,
                "journal_sha256": holds_digest({identity: hold["journal_sha256"]
                                                for identity, hold in holds.items()}),
                "steps": 2865, "attempts": 2877, "known_nano": credits("33565.68218"),
                "kind": "http_service_unavailable",
                "reserved_nano": sum(hold["reserved_nano"] for hold in holds.values())}
    if state_sha256 == HTTP_TIMEOUT_RECOVERY_STATE_SHA256:
        return {"source": HTTP_TIMEOUT_RECOVERY_SOURCE, "attempt": HTTP_TIMEOUT_RECOVERY_ATTEMPT,
                "journal_sha256": HTTP_TIMEOUT_RECOVERY_JOURNAL_SHA256,
                "steps": 3473, "attempts": 3486, "known_nano": credits("40106.89859"),
                "kind": "http_stream_timeout", "reserved_nano": 600 * NANO}
    if state_sha256 == RESILIENCE_BOOTSTRAP_STATE_SHA256:
        return {"source": RESILIENCE_BOOTSTRAP_SOURCE, "attempt": RESILIENCE_BOOTSTRAP_ATTEMPT,
                "journal_sha256": RESILIENCE_BOOTSTRAP_JOURNAL_SHA256,
                "steps": 3527, "attempts": 3541, "known_nano": credits("40976.11943"),
                "kind": "resilience_bootstrap", "reserved_nano": 300 * NANO}
    if state_sha256 == FALLBACK_RECOVERY_STATE_SHA256:
        return {"source": FALLBACK_RECOVERY_SOURCE, "attempt": FALLBACK_RECOVERY_ATTEMPT,
                "journal_sha256": FALLBACK_RECOVERY_JOURNAL_SHA256,
                "steps": 4915, "attempts": 4931, "known_nano": credits("58019.93185"),
                "kind": "fallback_metadata_quarantine", "reserved_nano": 300 * NANO}
    raise StudyError("Recovery state is not one of the disclosed estimation interruptions")


def holds_digest(journals: dict[str, str]) -> str:
    """Bind several preserved journals with one stable digest."""
    return hashlib.sha256(json.dumps(journals, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def incident_holds(incident: dict) -> dict[str, dict]:
    """Every attempt one disclosed interruption leaves held, with its journal and reservation."""
    if "holds" in incident:
        return incident["holds"]
    return {incident["attempt"]: {"journal_sha256": incident["journal_sha256"],
                                  "reserved_nano": incident["reserved_nano"]}}


def incident_attempt_ref(incident: dict) -> str | list[str]:
    """The approval names one attempt, or every held attempt in order."""
    holds = incident_holds(incident)
    return next(iter(holds)) if "holds" not in incident else sorted(holds)


def incident_journal_digest(incident: dict, verified: dict[str, str]) -> str:
    return holds_digest(verified) if "holds" in incident else next(iter(verified.values()))


def recovery_state_hashes() -> tuple[str, ...]:
    return (RECOVERY_STATE_SHA256, BACKEND_RECOVERY_STATE_SHA256, SANDBOX_RECOVERY_STATE_SHA256,
            SERVICE_RECOVERY_STATE_SHA256, TRANSPORT_RECOVERY_STATE_SHA256, CLOSE_RECOVERY_STATE_SHA256,
            MIXED_RECOVERY_STATE_SHA256, UNACCOUNTED_RECOVERY_STATE_SHA256, PAIRED_RECOVERY_STATE_SHA256,
            HTTP_RECOVERY_STATE_SHA256, HTTP_TIMEOUT_RECOVERY_STATE_SHA256, RESILIENCE_BOOTSTRAP_STATE_SHA256,
            FALLBACK_RECOVERY_STATE_SHA256)


def recovery_records(state: dict) -> list[dict]:
    recovery, history = state.get("recovery"), state.get("recovery_history", [])
    sequence = recovery_state_hashes()
    if not isinstance(history, list) or len(history) >= len(sequence) or (history and recovery is None):
        raise StudyError("Invalid recovery history")
    records = [*history, recovery] if recovery is not None else []
    hashes = [record.get("original_state_sha256") if isinstance(record, dict) else None
              for record in records]
    if tuple(hashes) != sequence[:len(hashes)]:
        raise StudyError("Recovery history differs from the disclosed incident sequence")
    return records


def validate_recovery_state(state: dict) -> None:
    """Keep every approved interrupted hold bound to its original source transition."""
    entries = state["ledger"]["entries"]
    holds = [key for key, entry in entries.items() if entry.get("status") == "recovery_hold"]
    interrupted = [attempt for cell in state["cells"] for attempt in cell["attempts"]
                   if attempt.get("status") == "recovery_interrupted"]
    records = recovery_records(state)
    if not records:
        if holds or interrupted:
            raise StudyError("Recovery hold lacks source-bound authorization")
        return
    attempts = [attempt for cell in state["cells"] for attempt in cell["attempts"]]
    ids = [attempt["id"] for attempt in attempts]
    incidents = [recovery_incident(record["original_state_sha256"]) for record in records]
    expected_holds = {identity: hold["reserved_nano"] for incident in incidents
                      for identity, hold in incident_holds(incident).items()}
    quarantine_only = {identity for incident in incidents if incident["kind"] == "fallback_metadata_quarantine"
                       for identity in incident_holds(incident)}
    if (len(set(ids)) != len(ids) or set(ids) != set(entries) or set(holds) != set(expected_holds)
            or len(interrupted) != len(expected_holds)
            or {attempt["id"] for attempt in interrupted} != set(expected_holds)
            or any(attempt.get("usage") is not None and (
                attempt["id"] not in quarantine_only or not isinstance(attempt["usage"], dict)
                or attempt["usage"].get("credits_complete") is not False
                or attempt["usage"].get("totalNanoAiu") is not None) for attempt in interrupted)
            or any(entries[key].get("actual_nano") is not None
                   or entries[key].get("reserved_nano") != reserved for key, reserved in expected_holds.items())):
        raise StudyError("Invalid source transition or recovered unknown-charge hold")
    for cell in state["cells"]:
        selected = [attempt for attempt in cell["attempts"] if attempt["id"] in quarantine_only]
        if selected and (cell.get("status") != "quarantined" or cell["attempts"][-1] is not selected[-1]):
            raise StudyError("Quarantine-only recovery cannot replay the unfinished request")
    previous_ids = set()
    original_sources = {}
    for index, recovery in enumerate(records):
        incident = recovery_incident(recovery["original_state_sha256"])
        before = recovery.get("prior_attempt_ids")
        if (recovery.get("schema") != "estimation-incident-recovery/v1"
                or recovery.get("original_commit") != incident["source"]
                or not re.fullmatch(r"[0-9a-f]{40}", recovery.get("target_commit", ""))
                or recovery["target_commit"] == incident["source"]
                or (index and records[index - 1]["target_commit"] != incident["source"])
                or not re.fullmatch(r"[0-9a-f]{64}", recovery.get("approval_sha256", ""))
                or recovery.get("journal_sha256") != incident["journal_sha256"]
                or not re.fullmatch(r"[0-9a-f]{64}", recovery.get("prior_manifest_sha256", ""))
                or not isinstance(before, list) or len(before) != incident["attempts"]
                or len(set(before)) != len(before) or not set(before).issubset(ids)
                or not previous_ids.issubset(before)):
            raise StudyError("Invalid source transition or recovered unknown-charge hold")
        previous_ids = set(before)
        for identity in before:
            # The first transition that archived an attempt owns its source.
            original_sources.setdefault(identity, incident["source"])
    if records[-1]["target_commit"] != state["identity"]["commit"]:
        raise StudyError("Recovery source differs from the current study identity")
    for attempt in attempts:
        source = original_sources.get(attempt["id"], state["identity"]["commit"])
        if attempt.get("source_commit") != source:
            raise StudyError("Attempt source differs from its preserved recovery history")


def recovery_calibration_manifest(directory: Path, path: Path, unregistered: dict) -> dict:
    """Use the original manifest only for the preserved calibration handoff."""
    if path.is_symlink() or not path.is_file() or not (directory / "state.json").is_file():
        raise StudyError("Recovery calibration manifest or state is missing or unsafe")
    state = read_json(directory / "state.json")
    validate_recovery_state(state)
    validate_recovery_evidence(directory, state, unregistered)
    records = recovery_records(state)
    manifest = read_json(path)
    if (not records or manifest.get("commit") != records[0]["original_commit"]
            or source_provenance(manifest)["manifest_sha256"] != records[0]["prior_manifest_sha256"]):
        raise StudyError("Recovery calibration manifest differs from the original source")
    return manifest


def recovery_source_paths(root: Path, *, expected_state_sha256: str | None = None) -> tuple[Path, Path]:
    """Keep the original checkout and its paid-study lock available during recovery."""
    original = root / ".study/pilot-estimation"
    paid = root / ".study/.paid-study-controller"
    state = original / "state.json"
    if (root.is_symlink() or not root.is_dir() or root.resolve() == ROOT.resolve()
            or (root / ".study").is_symlink() or original.is_symlink() or paid.is_symlink()
            or not original.is_dir() or not paid.is_dir() or state.is_symlink() or not state.is_file()
            or any((path / "controller.lock").is_symlink() or not (path / "controller.lock").is_file()
                   for path in (paid, original))):
        raise StudyError("Original recovery source or stopped state is unavailable or changed")
    state_sha256 = hashlib.sha256(state.read_bytes()).hexdigest()
    if state_sha256 not in recovery_state_hashes():
        raise StudyError("Original recovery source or stopped state is unavailable or changed")
    incident = recovery_incident(state_sha256)
    if (expected_state_sha256 is not None and state_sha256 != expected_state_sha256
            or command(["git", "rev-parse", "HEAD"], cwd=root) != incident["source"]):
        raise StudyError("Original recovery source or stopped state is unavailable or changed")
    return paid, original


def recovery_source_locks(state: dict, roots: list[Path]) -> list[Path]:
    records = recovery_records(state)
    if len(roots) != len(records):
        raise StudyError("Recovered studies require every original checkout in recovery order")
    return [path for record, root in zip(records, roots)
            for path in recovery_source_paths(root, expected_state_sha256=record["original_state_sha256"])]


def validate_recovery_evidence(directory: Path, state: dict, unregistered: dict | None) -> None:
    records = recovery_records(state)
    if not records:
        return
    if unregistered is None:
        raise StudyError("Recovery requires the preserved state and owner approval")
    from prepare_estimation_recovery import (
        digest,
        verify_approval,
        verify_approval_after_attempt,
        verify_journal,
    )
    preserved = []
    for index, recovery in enumerate(records):
        suffix = "" if index == len(records) - 1 else f"-{index + 1:02d}"
        snapshot = directory / f"state.before-recovery{suffix}.json"
        approval_path = directory / f"recovery-approval{suffix}.json"
        manifest_path = directory / f"recovery-manifest{suffix}.json"
        paths = (snapshot, approval_path) if not suffix else (snapshot, approval_path, manifest_path)
        if any(path.is_symlink() or not path.is_file() for path in paths):
            raise StudyError("Recovery requires every preserved state, manifest and owner approval")
        payload = snapshot.read_bytes()
        if hashlib.sha256(payload).hexdigest() != recovery["original_state_sha256"]:
            raise StudyError("Preserved pre-recovery state differs from the original")
        preserved.append((json.loads(payload), read_json(approval_path),
                          read_json(manifest_path) if suffix else unregistered))
    for index, (original, approval, manifest) in enumerate(preserved):
        recovery = records[index]
        incident = recovery_incident(recovery["original_state_sha256"])
        holds = incident_holds(incident)
        current_state = preserved[index + 1][0] if index + 1 < len(records) else state
        verify_approval(approval, manifest)
        if (recovery_records(original) != records[:index]
                or recovery_records(current_state) != records[:index + 1]
                or digest(approval) != recovery["approval_sha256"]
                or approval["approved_at"] != recovery.get("approved_at")
                or approval["disclosure_url"] != recovery.get("disclosure_url")
                or manifest.get("commit") != current_state["identity"]["commit"]
                or manifest.get("inputs_sha256") != current_state["identity"]["inputs_sha256"]
                or source_provenance(manifest) != current_state["identity"].get("source_provenance")):
            raise StudyError("Recovery approval differs from the recorded authorization")
        if (original["identity"].get("source_provenance", {}).get("manifest_sha256")
                != recovery["prior_manifest_sha256"]):
            raise StudyError("Recovery calibration provenance differs from the original")
        old_identity, new_identity = dict(original["identity"]), dict(current_state["identity"])
        for key in ("commit", "inputs_sha256", "source_provenance"):
            old_identity.pop(key, None)
            new_identity.pop(key, None)
        if (old_identity != new_identity or original["started"] != current_state["started"]
                or original["deadline"] != current_state["deadline"]
                or any(original["ledger"].get(key) != current_state["ledger"].get(key)
                       for key in ("ceiling_nano", "prior_nano", "historical_credit_provisions",
                                   "calibration_handoff"))
                or len(original["cells"]) != len(current_state["cells"])):
            raise StudyError("Recovery changed the original allocation, budget or deadline")
        prior_ids = []
        for old_cell, new_cell in zip(original["cells"], current_state["cells"]):
            if (old_cell["run_id"] != new_cell["run_id"]
                    or new_cell.get("completed_steps", 0) < old_cell.get("completed_steps", 0)
                    or (old_cell["status"] == "completed" and new_cell["status"] != "completed")
                    or len(new_cell["attempts"]) < len(old_cell["attempts"])):
                raise StudyError("Recovery lost a completed step or original attempt")
            for old_attempt, current in zip(old_cell["attempts"], new_cell["attempts"]):
                prior_ids.append(old_attempt["id"])
                before, after = dict(old_attempt), dict(current)
                before.pop("source_commit", None)
                after.pop("source_commit", None)
                old_included = before.pop("cost_included_in_step", False)
                new_included = after.pop("cost_included_in_step", False)
                if old_included and not new_included:
                    raise StudyError("Recovery removed a previously included attempt cost")
                if old_attempt["id"] in holds:
                    after["status"] = "interrupted"
                old_entry = dict(original["ledger"]["entries"][old_attempt["id"]])
                new_entry = dict(current_state["ledger"]["entries"][old_attempt["id"]])
                if old_attempt["id"] in holds:
                    new_entry["status"] = "unknown"
                if before != after or old_entry != new_entry:
                    raise StudyError("Recovery changed an original attempt or ledger entry")
        if prior_ids != recovery["prior_attempt_ids"]:
            raise StudyError("Recovery changed the original attempt inventory")
        for identity, hold in holds.items():
            attempt = next((item for cell in original["cells"] for item in cell["attempts"]
                            if item["id"] == identity), None)
            if (attempt is None
                    or verify_journal(directory, attempt, preserved_broker=True) != hold["journal_sha256"]):
                raise StudyError("Preserved interrupted attempt differs from the original journal")
            verify_approval_after_attempt(approval, attempt)


def ensure_no_terminal_receipt(directory: Path, attempt: dict) -> None:
    """Do not replay an agent whose durable terminal evidence survived a reboot."""
    relative = attempt.get("directory")
    if relative is None:
        return
    if (not isinstance(relative, str) or not relative or Path(relative).is_absolute()
            or ".." in Path(relative).parts):
        raise StudyError("Invalid interrupted attempt directory")
    journal = directory / relative / "transport" / "events.jsonl"
    if not journal.resolve().is_relative_to(directory.resolve()) or journal.is_symlink():
        raise StudyError("Unsafe interrupted attempt journal")
    if not journal.exists():
        return
    if not journal.is_file() or journal.stat().st_size > 64 * 1024 * 1024:
        raise StudyError("Invalid interrupted attempt journal")
    with journal.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.endswith("\n"):
                raise StudyError("Interrupted SDK journal is torn; retain it for manual recovery")
            try:
                event = json.loads(line)
            except json.JSONDecodeError as error:
                raise StudyError("Interrupted SDK journal is malformed; retain it for manual recovery") from error
            if not isinstance(event, dict):
                raise StudyError("Interrupted SDK journal is malformed; retain it for manual recovery")
            if event.get("type") == "complete":
                raise StudyError("A terminal SDK receipt survived the reboot; retain outputs for manual recovery")


def group_alive(pid: int) -> bool:
    """Conservatively refuse recovery while a recorded writer group still exists."""
    try:
        os.killpg(pid, 0)
    except ProcessLookupError:
        return False
    return True


def boot_id() -> str:
    """Identify a Linux boot so a restart is not confused with a controller crash."""
    value = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
    if not re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", value):
        raise StudyError("Cannot establish the current VM boot identity")
    return value


def docker_command(repo: Path, session: Path, image: str, prompt: str, cap: int,
                   name: str, model: str = "claude-sonnet-5.5") -> list[str]:
    """Prepare a restricted fresh session; this is not an implemented live backend."""
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", image):
        raise StudyError("Agent image must use an immutable sha256 digest")
    if not re.fullmatch(r"mve-[a-z0-9-]+", name):
        raise StudyError("Invalid owned container name")
    if type(cap) is not int or not 30 <= cap <= 300:
        raise StudyError("Session soft cap must be an integer from 30 through 300 credits")
    if model not in read_json(ROOT / "protocol/pilot-estimation.json")["study"]["model_roster"]:
        raise StudyError("Unapproved assigned model")
    return [
        "docker", "run", "--rm", "--init", "--name", name,
        "--user", f"{os.getuid()}:{os.getgid()}",
        "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
        "--pids-limit=256", "--memory=4g", "--cpus=2",
        "--tmpfs", "/tmp:rw,nosuid,size=128m",
        "--mount", f"type=bind,src={repo.resolve()},dst=/work",
        "--mount", f"type=bind,src={session.resolve()},dst=/session",
        "--workdir", "/work", "-e", "COPILOT_GITHUB_TOKEN",
        "-e", "HOME=/session/home", "-e", "COPILOT_HOME=/session/copilot-home",
        "-e", "COPILOT_AUTO_UPDATE=false", image,
        "copilot", "-C", "/work", "-p", prompt, "--model", model,
        "--reasoning-effort", "medium", "--no-ask-user",
        "--allow-tool", "write(/work)",
        "--allow-tool", "shell(python3)",
        "--allow-tool", "shell(make)",
        "--allow-tool", "shell(git status)",
        "--allow-tool", "shell(git diff)",
        "--no-custom-instructions", "--disable-builtin-mcps", "--no-auto-update",
        "--deny-tool", "shell(git push)", "--deny-tool", "url",
        "--deny-tool", "shell(curl)", "--deny-tool", "shell(wget)",
        "--deny-tool", "shell(pip)", "--deny-tool", "shell(pip3)",
        "--output-format", "json", "--usage-output-file", "/session/usage.json",
        "--max-ai-credits", str(cap), "--log-dir", "/session/logs",
    ]


def terminate(process: subprocess.Popen) -> None:
    """Stop and reap our subprocess group before recovery is allowed."""
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.wait(timeout=5)
    # The group leader can exit while descendants continue writing.
    if group_alive(process.pid):
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def aggregate_usage(attempts: list[dict]) -> dict:
    """All attempts of one step contribute cost exactly once; unknown stays unknown."""
    values = [accounted_nano(attempt.get("usage")) for attempt in attempts]
    complete = bool(values) and all(value is not None for value in values)
    result = {"totalNanoAiu": sum(value for value in values if value is not None) if complete else None,
              "credits_complete": complete}
    token_usages = [step_usage("", {"agent": attempt}) for attempt in attempts]
    if token_usages and all(usage["tokens_complete"] for usage in token_usages):
        result["tokenDetails"] = {
            name: {"tokenCount": sum(usage[f"tokens_{name}"] for usage in token_usages)}
            for name in ("input", "output", "cache_read", "cache_write")}
    return result


class StudyRun(Run):
    """Reuse integrity enforcement while journaling disposable-repository steps."""

    def __init__(self, args: SimpleNamespace, controller: Controller, cell: dict):
        super().__init__(args)
        self.controller = controller
        self.cell = cell
        self.replicates_per_model_arm = cell.get("replicates_per_model_arm")
        self.current_step = ""

    def setup(self) -> None:
        """Initialise only the owned disposable repository, preserving scheduled metadata."""
        metadata = Path(self.dir) / "run.json"
        if Path(self.repo).exists():
            if "config" not in read_json(metadata):
                raise StudyError("Incomplete repository initialisation retained; manual recovery required")
            return
        super().setup(existing_metadata=True)
        meta = read_json(metadata)
        meta.update(diagnostic=self.controller.smoke, study_id=self.controller.study_id)
        if self.controller.state["identity"].get("calibration_plan"):
            meta["calibration_plan"] = self.controller.state["identity"]["calibration_plan"]
        atomic_json(metadata, meta)

    def bounded_process(self, args: list[str], cwd: Path, env: dict, out: Path,
                        err: Path, timeout: float) -> tuple[int, bool, float]:
        """Persist the process identity, bound its lifetime and retain capped logs."""
        start = time.time()
        remaining = self.controller.state["deadline"] - start
        if remaining <= 0:
            raise StudyError("Study deadline reached; no new process launched")
        cell = getattr(self, "cell", {})
        self.controller.writer_pending(cell)
        with out.open("wb") as stdout, err.open("wb") as stderr:
            process = subprocess.Popen(args, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                       stdout=stdout, stderr=stderr, start_new_session=True)
            timed_out = False
            try:
                self.controller.writer_started(cell, process.pid)
                process.wait(timeout=min(timeout, remaining))
            except subprocess.TimeoutExpired:
                timed_out = True
            finally:
                terminate(process)
                self.controller.writer_stopped(cell)
        for path in (out, err):
            if path.stat().st_size > 1024 * 1024:
                with path.open("r+b") as stream:
                    stream.truncate(1024 * 1024)
        return process.returncode, timed_out, time.time() - start

    def run_agent(self, prompt: str, step_dir: str, budget: int) -> dict:
        """Select isolated live execution or the unchanged built-in smoke stub."""
        controller = self.controller
        if not controller.smoke:
            from isolated_runtime import live_runtime
            return live_runtime(self).run_agent(prompt, step_dir, budget)
        remaining_seconds, remaining_credits = self.remaining_allowance(budget)
        reserve_buffer = self.credit_multiplier() * (credits(controller.cfg["session_reserve_credits"])
                                                     - credits(controller.cfg["session_soft_limit_credits"]))
        attempt = controller.new_attempt(self.cell, self.current_step, remaining_credits + reserve_buffer)
        directory = Path(self.dir) / "attempts" / attempt["id"]
        directory.mkdir(parents=True, mode=0o700)
        controller.update(attempt, seconds_limit=remaining_seconds, credit_limit_nano=remaining_credits,
                          directory=str(directory.relative_to(controller.directory)))
        env = {"PATH": str(Path(sys.executable).parent) + os.pathsep + os.environ.get("PATH", ""),
               "HOME": str(directory),
               "TEST_CMD": self.env_extra["TEST_CMD"], "MVE_HARNESS": str(ROOT / "harness"),
               "MVE_COMPLEXITY": "internal", "MVE_DUPLICATION": "internal", "MVE_LINT": "none",
               "PYTHONDONTWRITEBYTECODE": "1"}
        status, timed_out, seconds = self.bounded_process(
            [sys.executable, str(ROOT / "harness/fake_agent.py"), "--prompt", prompt,
             "--repo", self.repo, "--suite", self.suite_dir],
            Path(self.repo), env, directory / "stdout.txt", directory / "stderr.txt", remaining_seconds)
        usage = {"totalNanoAiu": 0, "credits_complete": True,
                 "tokenDetails": {name: {"tokenCount": 0}
                                  for name in ("input", "output", "cache_read", "cache_write")}}
        with controller.lock:
            attempt.update(status="timeout" if timed_out else "agent_returned", exit_code=status,
                           seconds=round(seconds, 4), usage=usage)
            controller.settle_attempt(attempt["id"], usage)
        return {"exit_code": status, "timed_out": timed_out, "seconds": seconds,
                "usage": usage, "possible_leak": False, "diagnostic_stub": True}

    def credit_multiplier(self) -> int:
        return 2 if self.arm == "D" and self.current_step.endswith("-feature") else 1

    def remaining_allowance(self, budget: int) -> tuple[float, int]:
        previous = [attempt for attempt in self.cell["attempts"]
                    if attempt["step"] == self.current_step
                    and attempt["status"] not in ("restart_interrupted", "recovery_interrupted")]
        seconds = 0.0
        spent = 0
        for attempt in previous:
            measurement = attempt.get("measurement", {})
            if measurement:
                raise StudyError("Started measurement requires recovery, not agent replay")
            duration = attempt.get("seconds")
            usage = accounted_nano(attempt.get("usage"))
            if (type(duration) not in (int, float) or not math.isfinite(duration) or duration < 0
                    or usage is None):
                raise StudyError("Unknown prior step duration or usage blocks retry")
            seconds += duration
            spent += usage
        remaining_seconds = budget - seconds
        remaining_credits = self.credit_multiplier() * credits(self.controller.cfg["session_soft_limit_credits"]) - spent
        if remaining_seconds <= 0 or remaining_credits <= 0:
            raise StudyError("Original step time or credit allowance exhausted")
        if not self.controller.smoke and remaining_credits < 30 * NANO:
            raise StudyError("Remaining original soft allowance is below the CLI minimum of 30 credits; "
                             "do not top up or reset the limit")
        return remaining_seconds, remaining_credits

    def is_green(self) -> bool:
        """Bound visible-test writers under the same absolute study deadline."""
        if not self.controller.smoke:
            from isolated_runtime import live_runtime
            return live_runtime(self).visible()
        from evaluation_env import evaluation_environment
        directory = Path(self.dir) / "attempts" / self.cell["attempts"][-1]["id"] / "checks"
        directory.mkdir(parents=True, exist_ok=True)
        with evaluation_environment() as env:
            env["TEST_CMD"] = self.env_extra["TEST_CMD"]
            code, timed_out, _ = self.bounded_process(
                ["make", "-s", "test"], Path(self.repo), env,
                directory / "visible.stdout", directory / "visible.stderr", 600)
        if timed_out:
            raise RetryableError("Visible-test infrastructure timeout; unmeasured cell retained")
        return code == 0

    def measure(self, k: int, step_dir: str, prev_ref: str, cr: bool = False) -> dict:
        """Retry infrastructure evaluation, never the agent, on the retained state."""
        attempt = self.cell["attempts"][-1]
        current = head(self.repo)
        status = git(self.repo, "status", "--porcelain").stdout
        with self.controller.lock:
            measurement = attempt.setdefault("measurement", {"head": current, "calls": 0, "status": "pending"})
        if measurement["head"] != current or measurement["status"] == "snapshot_changed":
            with self.controller.lock:
                measurement["status"] = "snapshot_changed"
                self.controller.state["oracle_halt"] = True
                self.controller.save()
            raise StudyError("Measurement snapshot changed; collection halted")
        if measurement["status"] in ("complete", "exhausted"):
            raise StudyError("Measurement snapshot or durable retry limit forbids replay")
        while measurement["calls"] < 2:
            with self.controller.lock:
                measurement["calls"] += 1
                measurement["status"] = "running"
                self.controller.save()
            try:
                result = self._measure_once(k, step_dir, prev_ref, cr)
            except StudyError:
                with self.controller.lock:
                    measurement["status"] = "invalid_result"
                    self.controller.state["oracle_halt"] = True
                    self.controller.save()
                raise
            except (RetryableError, OSError, subprocess.TimeoutExpired) as error:
                with self.controller.lock:
                    measurement["status"] = "exhausted" if measurement["calls"] == 2 else "infrastructure_failure"
                    measurement["error"] = type(error).__name__
                    self.controller.save()
                if head(self.repo) != current or git(self.repo, "status", "--porcelain").stdout != status:
                    with self.controller.lock:
                        measurement["status"] = "snapshot_changed"
                        self.controller.state["oracle_halt"] = True
                        self.controller.save()
                    raise StudyError("Evaluator changed the retained snapshot; collection halted") from error
                continue
            if (head(self.repo) != current or git(self.repo, "status", "--porcelain").stdout != status
                    or result.get("head") != current):
                with self.controller.lock:
                    measurement["status"] = "snapshot_changed"
                    self.controller.state["oracle_halt"] = True
                    self.controller.save()
                raise StudyError("Evaluator changed or misidentified the retained snapshot; collection halted")
            self.controller.update(measurement, status="complete")
            return result
        raise StudyError("Measurement infrastructure retries exhausted; no agent replay")

    def _measure_once(self, k: int, step_dir: str, prev_ref: str, cr: bool = False) -> dict:
        """Execute one bounded external evaluation."""
        if not self.controller.smoke:
            from isolated_runtime import live_runtime
            return live_runtime(self).measure(k, step_dir, prev_ref, cr)
        from evaluation_env import evaluation_environment
        directory = Path(self.dir) / "attempts" / self.cell["attempts"][-1]["id"] / "evaluation"
        directory.mkdir(parents=True, exist_ok=True)
        output = directory / "measure.json"
        args = [sys.executable, "-B", str(ROOT / "harness/measure.py"), "--repo", self.repo,
                "--suite", self.suite_dir, "--k", str(k), "--out", str(output),
                "--runner", "stdlib", "--complexity", "internal", "--duplication", "internal", "--lint", "none"]
        if prev_ref:
            args += ["--prev-ref", prev_ref]
        if cr:
            args += ["--cr"]
        with evaluation_environment() as env:
            code, timed_out, _ = self.bounded_process(args, Path(self.repo), env,
                                                      directory / "evaluator.stdout",
                                                      directory / "evaluator.stderr", 600)
        if code or timed_out:
            raise RetryableError("Evaluator failed or timed out; partial cell retained")
        return read_json(output)

    def record(self, rec: dict) -> None:
        """Fsync the canonical step before marking it complete in controller state."""
        if not self.controller.smoke and rec.get("kind") in ("consolidation", "repair"):
            from isolated_runtime import live_runtime
            runtime = live_runtime(self)
            count = (runtime.last_export or {}).get("commit_count")
            if type(count) is not int or count < 0:
                raise StudyError("Missing isolated candidate commit-count evidence")
            rec["commits"] = count if rec["commits"] > 0 and head(self.repo) == runtime.last_checkpoint else 0
        attempts = [attempt for attempt in self.cell["attempts"] if attempt["step"] == rec["step"]]
        rec["agent"]["usage"] = aggregate_usage(attempts)
        rec["agent"]["seconds"] = (sum(attempt["seconds"] for attempt in attempts)
                                    if all(attempt.get("seconds") is not None for attempt in attempts) else None)
        rec["attempts"] = [attempt["id"] for attempt in attempts]
        super().record(rec)
        with open(self.steps_path, "a", encoding="utf-8") as stream:
            stream.flush()
            os.fsync(stream.fileno())
        with self.controller.lock:
            for attempt in attempts:
                attempt["cost_included_in_step"] = True
            self.controller.save()

    def post_step(self, k: int) -> None:
        if not self.controller.smoke and self.arm == "C":
            from isolated_runtime import live_runtime
            live_runtime(self).review_step(k)
            return
        super().post_step(k)


class Controller:
    """Own one immutable schedule and exactly one analysis unit per cell."""

    def __init__(self, directory: Path, cfg: dict, *, smoke: bool, phase: str, study_id: str,
                 replicates: int | None = None, short_calibration: bool = False, parallelism: int = 1,
                 unregistered: dict | None = None, handoff: dict | None = None):
        if type(parallelism) is not int or parallelism < 1:
            raise StudyError("Parallelism must be a positive integer")
        self.lock = threading.RLock()
        self.directory = directory
        self.cfg = cfg
        self.smoke = smoke
        self.phase = "dry" if smoke else phase
        self.study_id = study_id
        self.parallelism = parallelism
        self.unregistered = unregistered
        resilience_policy(unregistered)
        self.boot_id = boot_id()
        self.path = directory / "state.json"
        estimation = not smoke and phase not in ("pilot", "calibration")
        if not estimation and replicates is not None:
            raise StudyError("Replicate selection applies only to estimation, not calibration or smoke")
        if estimation and replicates is None and self.path.exists():
            replicates = read_json(self.path)["identity"].get("replicates_per_model_arm")
        count = selected_replicates(replicates) if estimation else None
        identity = {"study_id": study_id, "config": cfg, "smoke": smoke, "phase": self.phase,
                    "inputs_sha256": fingerprint(),
                    "commit": command(["git", "rev-parse", "HEAD"])}
        if unregistered is not None:
            identity["source_provenance"] = source_provenance(unregistered)
        if handoff is not None:
            identity["calibration_handoff"] = handoff
        proposed = schedule(smoke, phase, cfg["seed"], count, short_calibration=short_calibration)
        if not smoke:
            identity.update(analysis_design=MODEL_DESIGN,
                            model_roster=read_json(ROOT / "protocol/pilot-estimation.json")["study"]["model_roster"])
        if estimation:
            identity["replicates_per_model_arm"] = count
        if short_calibration:
            identity["calibration_plan"] = "one-feature-per-model-arm"
        if self.path.exists():
            self.state = read_json(self.path)
            if self.state["identity"] != identity:
                raise StudyError("Resume inputs/config/git commit changed; preserve study and use a new study ID")
        else:
            started = time.time()
            self.state = {"identity": identity, "started": started,
                          "deadline": started + cfg["study_timeout_seconds"],
                          "writer_pid": None, "status": "prepared", "errors": [],
                          "writer_pending": False,
                          "boot_id": self.boot_id, "writers": {}, "restart_history": [],
                          "parallelism_history": [],
                          "ledger": {"ceiling_nano": credits(cfg["ceiling_credits"]),
                                     "prior_nano": 0 if smoke else credits(cfg["prior_credits"]),
                                     "historical_credit_provisions": historical_credit_provisions(cfg, smoke=smoke),
                                     "calibration_handoff": handoff,
                                     "entries": {}},
                          "cells": [dict(cell, status="pending", attempts=[], checkpoint=None)
                                    for cell in proposed]}
            self.save()
        validate_recovery_state(self.state)
        validate_recovery_evidence(directory, self.state, unregistered)
        validate_supervisor_state(directory, self.state, unregistered)
        if (len(self.state["cells"]) != len(proposed)
                or any({key: actual.get(key) for key in expected} != expected
                       for actual, expected in zip(self.state["cells"], proposed))):
            raise StudyError("Stored allocation differs from immutable schedule")
        if (self.state["ledger"]["ceiling_nano"] != credits(cfg["ceiling_credits"])
                or self.state["ledger"]["prior_nano"] != (0 if smoke else credits(cfg["prior_credits"]))
                or self.state["ledger"].get("historical_credit_provisions", [])
                != historical_credit_provisions(cfg, smoke=smoke)
                or self.state["ledger"].get("calibration_handoff") != handoff
                or self.state["deadline"] > self.state["started"] + cfg["study_timeout_seconds"]):
            raise StudyError("Stored budget, prior spending or deadline differs from immutable limits")
        pid = self.state.get("writer_pid")
        if self.state.get("writer_pending"):
            raise StudyError("Ambiguous writer startup; inspect private state before any recovery")
        if pid and group_alive(pid):
            raise StudyError("Recorded writer group may still be alive; stop it before resuming")
        self.state["writer_pid"] = None
        self.recover_writers()
        self.state.setdefault("parallelism_history", []).append(
            {"parallelism": parallelism, "boot_id": self.boot_id, "started": time.time()})
        self.save()
        self.runtime_config = directory / "runtime.json"
        runtime = read_json(ROOT / ("harness/config.dry-run.json" if smoke else "harness/config.json"))
        runtime["runs_dir"] = str(directory / "runs")
        runtime["version_commands"] = {}
        atomic_json(self.runtime_config, runtime)
        for cell in self.state["cells"]:
            run_dir = directory / "runs" / cell["run_id"]
            metadata = run_dir / "run.json"
            expected_metadata = {"run_id": cell["run_id"], "arm": cell["arm"],
                                 "suite": "s1-retrofit", "phase": self.phase,
                                 "collection_role": collection_role({"phase": self.phase}),
                                 "features": cell["features"], "change_request": cell["change_request"],
                                 "diagnostic": smoke, "study_id": study_id}
            if not smoke:
                expected_metadata.update({key: cell[key] for key in ("assigned_model", "analysis_design", "replicate")})
                if estimation:
                    expected_metadata["replicates_per_model_arm"] = count
                if short_calibration:
                    expected_metadata["calibration_plan"] = "one-feature-per-model-arm"
            if not metadata.exists():
                atomic_json(metadata, expected_metadata)
            else:
                stored_metadata = read_json(metadata)
                if any(stored_metadata.get(key) != value for key, value in expected_metadata.items()):
                    raise StudyError("Raw metadata differs from immutable scheduled identity")

    def save(self) -> None:
        """Persist all lifecycle and accounting transitions."""
        with self.lock:
            atomic_json(self.path, self.state)

    def update(self, target: dict, **values) -> None:
        """Mutate and persist shared state as one controller transaction."""
        with self.lock:
            target.update(values)
            self.save()

    def writer_pending(self, cell: dict) -> None:
        with self.lock:
            writers = self.state.setdefault("writers", {})
            key = cell.get("run_id", "legacy")
            if key in writers:
                raise StudyError("A writer is already recorded for this trajectory")
            writers[key] = {"pending": True, "pid": None, "boot_id": self.boot_id}
            self.save()

    def writer_started(self, cell: dict, pid: int) -> None:
        with self.lock:
            writer = self.state["writers"][cell.get("run_id", "legacy")]
            writer.update(pending=False, pid=pid)
            self.save()

    def writer_stopped(self, cell: dict) -> None:
        with self.lock:
            self.state["writers"].pop(cell.get("run_id", "legacy"))
            self.save()

    def recover_writers(self) -> None:
        """Hold interrupted requests only after an independently identifiable VM reboot."""
        previous_boot = self.state.get("boot_id", self.boot_id)
        writers = self.state.setdefault("writers", {})
        if not isinstance(writers, dict):
            raise StudyError("Invalid recorded writer registry")
        for writer in writers.values():
            if (not isinstance(writer, dict) or type(writer.get("pending")) is not bool
                    or writer.get("boot_id") != previous_boot
                    or (writer.get("pid") is not None
                        and (type(writer["pid"]) is not int or writer["pid"] <= 0))):
                raise StudyError("Invalid recorded writer identity")
        if previous_boot == self.boot_id:
            for writer in writers.values():
                if writer.get("pending"):
                    raise StudyError("Ambiguous writer startup; inspect private state before any recovery")
                if writer.get("pid") and group_alive(writer["pid"]):
                    raise StudyError("Recorded writer group may still be alive; stop it before resuming")
            if writers:
                raise StudyError("Writer termination on the same VM boot requires manual recovery")
            if any(attempt["status"] == "running"
                   for cell in self.state["cells"] for attempt in cell["attempts"]):
                raise StudyError("Same-boot interrupted attempt requires manual recovery")
            return
        interrupted = []
        for cell in self.state["cells"]:
            checkpoint = cell.get("checkpoint") or {}
            for attempt in cell["attempts"]:
                if attempt["status"] != "running":
                    continue
                entry = self.state["ledger"]["entries"].get(attempt["id"])
                if (attempt["step"] != checkpoint.get("step") or not entry
                        or entry.get("status") != "reserved"):
                    raise StudyError("Interrupted attempt and reservation do not match the retained checkpoint")
                if not self.smoke:
                    ensure_no_terminal_receipt(self.directory, attempt)
                if self.smoke:
                    reconcile(self.state["ledger"], attempt["id"],
                              {"totalNanoAiu": 0, "credits_complete": True})
                    attempt["usage"] = {"totalNanoAiu": 0, "credits_complete": True}
                else:
                    entry["status"] = "restart_hold"
                    attempt["usage"] = None
                attempt.update(status="restart_interrupted", seconds=None,
                               interrupted_boot_id=previous_boot, recovered_boot_id=self.boot_id)
                interrupted.append(attempt["id"])
        self.state.setdefault("restart_history", []).append(
            {"previous_boot_id": previous_boot, "boot_id": self.boot_id,
             "observed": time.time(), "interrupted_attempts": interrupted})
        self.state["writers"] = {}
        self.state["boot_id"] = self.boot_id
        self.save()

    def retry_holds(self) -> int:
        with self.lock:
            return sum(entry["status"] == RETRY_HOLD for entry in self.state["ledger"]["entries"].values())

    def retry_hold_limit_exceeded(self) -> bool:
        """Holds are allowed only while the owner-approved policy covers every one of them."""
        policy = retry_hold_policy(self.unregistered)
        return self.retry_holds() > (policy["max_holds"] if policy else 0)

    def new_attempt(self, cell: dict, step: str, allowance_nano: int | None = None) -> dict:
        """Reserve before launch, counting every infrastructure retry."""
        with self.lock:
            policy = resilience_policy(self.unregistered)
            if cell.get("status") == "quarantined":
                raise StudyError("Quarantined cell cannot replay an unresolved request")
            if policy and self.route_not_before(cell) > time.time():
                raise RetryableError("Assigned provider route is cooling down; no session dispatched")
            if any(entry["status"] == "unknown" for entry in self.state["ledger"]["entries"].values()):
                raise StudyError("Unknown usage holds its reservation and blocks new work")
            if self.retry_hold_limit_exceeded():
                raise StudyError("Unaccounted retry holds exceed the owner-approved limit")
            if self.state.get("oracle_halt") or self.state.get("stop_requested"):
                raise StudyError("Controller halted; no new session admitted")
            previous = [attempt for attempt in cell["attempts"] if attempt["step"] == step]
            ordinary = [attempt for attempt in previous
                        if attempt["status"] not in ("restart_interrupted", "recovery_interrupted")]
            if len(ordinary) >= self.cfg["max_attempts"]:
                raise StudyError("Bounded attempt limit reached; partial cell retained")
            attempt_id = f"{cell['run_id']}-{step}-{len(previous) + 1}"
            multiplier = 2 if cell["arm"] == "D" and step.endswith("-feature") else 1
            amount = 0 if self.smoke else multiplier * credits(self.cfg["session_reserve_credits"])
            if allowance_nano is not None:
                amount = min(amount, allowance_nano)
            try:
                reserve(self.state["ledger"], attempt_id, amount, quarantine_policy=policy)
            except StudyError:
                self.state["stop_requested"] = True
                self.state["stop_reason"] = "Credit admission failed; no new session admitted"
                self.save()
                raise
            attempt = {"id": attempt_id, "step": step, "status": "running",
                       "started": time.time(), "seconds": None, "usage": None,
                       "parallelism": self.parallelism}
            if self.state.get("recovery") or resilience_policy(self.unregistered):
                attempt["source_commit"] = self.state["identity"]["commit"]
            cell["attempts"].append(attempt)
            self.save()
            return attempt

    def settle_attempt(self, attempt: str, usage: dict | None) -> None:
        """Persist unknown accounting and overruns even when reconciliation stops."""
        with self.lock:
            try:
                reconcile(self.state["ledger"], attempt, usage)
            finally:
                self.save()

    def run_cell(self, cell: dict) -> None:
        """Resume only unmeasured work, never retry a recorded task failure."""
        args = SimpleNamespace(config=str(self.runtime_config), suite=str(ROOT / "suites/s1-retrofit"),
                               arm=cell["arm"], run_id=cell["run_id"], phase=self.phase,
                               features=cell["features"], no_cr=not cell["change_request"], allow_draft=False,
                               assigned_model=cell.get("assigned_model"), analysis_design=cell.get("analysis_design"),
                               replicate=cell.get("replicate"), study_id=self.study_id, diagnostic=self.smoke,
                               replicates_per_model_arm=cell.get("replicates_per_model_arm"))
        run = StudyRun(args, self, cell)
        run.setup()
        records = []
        path = Path(run.steps_path)
        if path.exists():
            text = path.read_text()
            if text and not text.endswith("\n"):
                raise StudyError("Journal lacks final newline: preserve partial run for manual recovery")
            for line in text.splitlines():
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as error:
                    raise StudyError("Torn step record: preserve partial run for manual recovery") from error
        done = [record["step"] for record in records]
        if len(done) != len(set(done)):
            raise StudyError("Duplicate durable steps; refuse ambiguous recovery")
        with self.lock:
            attempts = {attempt["id"]: attempt for attempt in cell["attempts"]}
            for record in records:
                for attempt_id in record.get("attempts", []):
                    if attempt_id not in attempts or attempts[attempt_id]["step"] != record["step"]:
                        raise StudyError("Durable step references an unknown or mismatched attempt")
                    attempts[attempt_id]["cost_included_in_step"] = True
            self.save()
        checkpoint = cell.get("checkpoint")
        if checkpoint and checkpoint["step"] not in done:
            with self.lock:
                if any(attempt["step"] == checkpoint["step"]
                       and (attempt["status"] == "agent_returned" or attempt.get("measurement"))
                       for attempt in cell["attempts"]):
                    raise StudyError("Completed agent or started measurement requires manual recovery; "
                                     "retained outputs will not be discarded")
                for attempt in cell["attempts"]:
                    if attempt["step"] == checkpoint["step"] and attempt["status"] == "running":
                        attempt.update(status="interrupted", usage={"totalNanoAiu": 0, "credits_complete": True}
                                       if self.smoke else None)
                        self.settle_attempt(attempt["id"], attempt["usage"])
                self.save()
            git(run.repo, "reset", "-q", "--hard", checkpoint["head"])
            git(run.repo, "clean", "-qfd")
        if records and head(run.repo) != records[-1]["measure"]["head"]:
            raise StudyError("Retained repository HEAD differs from last durable measurement")
        if git(run.repo, "status", "--porcelain").stdout.strip():
            raise StudyError("Unexpected uncheckpointed work in retained repository")
        steps = []
        for k, feature in enumerate(run.features, 1):
            steps.append((f"f{k:02d}-feature", run.feature_step, (k, feature)))
            if POST_KINDS[run.arm] is not None:
                kind = POST_KINDS[run.arm]
                steps.append((f"f{k:02d}-{kind}", run.post_step, (k,)))
        if run.do_cr:
            steps.append((f"{run.suite['change_request']['id']}-change", run.change_request, ()))
        if done != [step[0] for step in steps[:len(done)]]:
            raise StudyError("Durable step order differs from frozen schedule")
        self.update(cell, completed_steps=len(done), status="running")
        for step, function, params in steps:
            if step in done:
                continue
            with self.lock:
                if self.state.get("oracle_halt") or self.state.get("stop_requested"):
                    raise StudyError("Controller halted; no new step launched")
                if time.time() >= self.state["deadline"]:
                    raise StudyError("Study deadline reached; no new cell/step launched")
                cell["checkpoint"] = {"step": step, "head": head(run.repo)}
                self.save()
            run.current_step = step
            with self.lock:
                show_progress(self.state, f"{cell.get('assigned_model', 'offline stub')} / {cell['arm']} / {step}")
            function(*params)
            with self.lock:
                cell["completed_steps"] += 1
                cell["checkpoint"] = None
                self.save()
        meta = read_json(Path(run.dir) / "run.json")
        meta["finished"] = time.time()
        atomic_json(Path(run.dir) / "run.json", meta)
        with self.lock:
            cell.pop("error", None)
            cell.pop("stop_reason", None)
            cell["status"] = "completed"
            self.save()

    def route_not_before(self, cell: dict) -> float:
        """Keep route cooldown and per-cell backoff outside worker occupancy."""
        with self.lock:
            route = self.state.get("supervisor", {}).get("routes", {}).get(cell.get("assigned_model"), {})
            step = (cell.get("checkpoint") or {}).get("step")
            attempts = [attempt for attempt in cell["attempts"] if attempt["step"] == step]
            decision = attempts[-1].get("recovery_action", {}) if attempts else {}
            return max(route.get("blocked_until", 0), cell.get("retry_not_before", 0), decision.get("not_before", 0))

    def route_succeeded(self, cell: dict) -> None:
        """Reset consecutive failures without releasing a still-active cooldown early."""
        with self.lock:
            route = self.state.get("supervisor", {}).get("routes", {}).get(cell.get("assigned_model"))
            if route is not None:
                route["consecutive_failures"] = 0
                if route["blocked_until"] <= time.time():
                    route["blocked_until"] = 0
                self.save()

    def wait_for_schedule(self, delay: float) -> None:
        """Leave workers free while respecting durable backoff and the absolute deadline."""
        threading.Event().wait(max(0, min(delay, 1)))

    def supervise_failure(self, cell: dict, attempt: dict) -> None:
        """Persist one route observation and quarantine only an approved, quiescent failed request."""
        with self.lock:
            supervise_failure_state(self.directory, self.state, self.unregistered, cell, attempt)
            self.save()

    def retry_live_attempt(self, cell: dict, attempts: list[dict]) -> bool:
        """Authorize only quiescent, finally billed infrastructure failures before measurement."""
        policy = resilience_policy(self.unregistered)
        if not policy or not attempts or self.admission_stopped():
            return False
        if cell["run_id"] in self.state.get("writers", {}) or self.state.get("writer_pid"):
            return False
        latest = attempts[-1]
        outcome = validate_attempt_outcome(latest.get("outcome"))
        failure = outcome.get("failure") or {}
        if (latest.get("status") != "infra_failed"
                or outcome.get("schema") != "study-attempt-outcome/v1"
                or outcome.get("work") not in ("unavailable", "partial")
                or outcome.get("safety") != "valid" or outcome.get("quiescent") is not True
                or outcome.get("accounting") != "final"
                or failure.get("kind") not in ("provider_transient", "transport", "timeout")):
            return False
        for attempt in attempts:
            entry = self.state["ledger"]["entries"].get(attempt["id"], {})
            seconds = attempt.get("seconds")
            nano = accounted_nano(attempt.get("usage"))
            if (attempt.get("measurement") or attempt.get("cost_included_in_step")
                    or type(seconds) not in (int, float) or not math.isfinite(seconds) or seconds < 0
                    or nano is None or entry.get("status") != "complete"
                    or entry.get("actual_nano") != nano or nano > entry["reserved_nano"]):
                return False
            supervised_terminal(self.directory, latest, cell["assigned_model"], self.state["identity"]["commit"])
        retry_after = failure.get("retry_after_seconds")
        if retry_after is not None and (type(retry_after) not in (int, float)
                                        or not math.isfinite(retry_after) or retry_after < 0):
            return False
        decision = latest.get("recovery_action")
        if decision is None:
            delay = min(policy["retry_max_backoff_seconds"],
                        policy["retry_backoff_seconds"] * (2 ** (len(attempts) - 1))
                        + random.uniform(0, policy["retry_backoff_seconds"]))
            delay = max(delay, retry_after or 0)
            decision = {"action": "retry_original_step", "decided_at": time.time(),
                        "not_before": time.time() + delay,
                        "source_commit": self.state["identity"]["commit"]}
            self.update(latest, recovery_action=decision)
        not_before = max(decision["not_before"], self.route_not_before(cell))
        if not_before >= self.state["deadline"]:
            return False
        if not_before > time.time():
            self.update(cell, status="deferred", retry_not_before=not_before)
            return False
        cell.pop("retry_not_before", None)
        return not self.admission_stopped()

    def run_scheduled_cell(self, cell: dict) -> None:
        """Retain a failed cell and preserve the original bounded retry policy."""
        for _ in range(self.cfg["max_attempts"]):
            try:
                self.run_cell(cell)
                return
            except (StudyError, RuntimeError, OSError, subprocess.TimeoutExpired) as error:
                with self.lock:
                    cell.update(status="quarantined" if cell.get("status") == "quarantined" else "partial",
                                error=type(error).__name__,
                                stop_reason=(str(error) if isinstance(error, (StudyError, RetryableError))
                                             else "Infrastructure failure; inspect private attempt logs"))
                    self.save()
                    print(f"Stopped: {cell['run_id']} | {cell['stop_reason']}", file=sys.stderr, flush=True)
                    step = (cell.get("checkpoint") or {}).get("step")
                    attempts = [attempt for attempt in cell["attempts"] if attempt["step"] == step]
                    policy = resilience_policy(self.unregistered)
                    if policy and isinstance(error, RetryableError):
                        if attempts and attempts[-1].get("status") == "infra_failed":
                            self.supervise_failure(cell, attempts[-1])
                        elif self.route_not_before(cell) > time.time():
                            self.update(cell, status="deferred", retry_not_before=self.route_not_before(cell))
                            return
                if (not attempts or len(attempts) >= self.cfg["max_attempts"]
                    or not isinstance(error, RetryableError)
                    or (not self.smoke and not self.retry_live_attempt(cell, attempts))):
                    return

    def admission_stopped(self) -> bool:
        with self.lock:
            if self.state.get("oracle_halt") or self.state.get("stop_requested"):
                return True
            entries = self.state["ledger"]["entries"].values()
            if any(entry["status"] == "unknown" for entry in entries):
                self.state["stop_reason"] = "Unknown usage blocks new paid work"
                self.save()
                return True
            try:
                quarantine_exposure(self.state["ledger"], resilience_policy(self.unregistered))
            except StudyError as error:
                self.state["stop_reason"] = str(error)
                self.save()
                return True
            if any((entry["status"] == "complete" and entry["actual_nano"] > entry["reserved_nano"])
                   or (entry["status"] == RETRY_HOLD and entry["lower_bound_nano"] > entry["reserved_nano"])
                   for entry in entries):
                self.state["stop_reason"] = "A reservation overrun blocks new paid work"
                self.save()
                return True
            if self.retry_hold_limit_exceeded():
                self.state["stop_reason"] = "Unaccounted retry holds exceed the owner-approved limit"
                self.save()
                return True
            if time.time() >= self.state["deadline"]:
                self.state["stop_reason"] = "Absolute study deadline reached"
                self.save()
                return True
            return False

    def go(self) -> bool:
        """Keep failures and unattempted cells, then always produce a complete report."""
        self.update(self.state, status="running", stop_requested=False)
        executor = ThreadPoolExecutor(max_workers=min(self.parallelism, max(1, len(self.state["cells"]))))
        active = {}
        pending = [cell for cell in self.state["cells"] if cell["status"] not in ("completed", "quarantined")]

        def fill() -> None:
            while len(active) < self.parallelism and not self.admission_stopped():
                index = next((index for index, cell in enumerate(pending)
                              if self.route_not_before(cell) <= time.time()), None)
                if index is None:
                    break
                cell = pending.pop(index)
                active[executor.submit(self.run_scheduled_cell, cell)] = cell

        finished = False
        try:
            fill()
            while active or pending:
                if not active and self.admission_stopped():
                    break
                if not active:
                    delay = min(self.route_not_before(cell) for cell in pending) - time.time()
                    self.wait_for_schedule(delay)
                    fill()
                    continue
                completed, _ = wait(active, timeout=1, return_when=FIRST_COMPLETED)
                for future in completed:
                    cell = active.pop(future)
                    future.result()
                    if cell["status"] == "deferred":
                        pending.append(cell)
                fill()
            finished = True
        finally:
            if not finished:
                self.update(self.state, status="interrupted", stop_requested=True)
            executor.shutdown(wait=True, cancel_futures=True)
        success = all(cell["status"] == "completed" for cell in self.state["cells"])
        status = "oracle_halt" if self.state.get("oracle_halt") else "completed" if success else "partial"
        self.update(self.state, status=status)
        from study_report import export
        export(self.directory, self.state, self.study_id)
        show_progress(self.state, self.state["status"])
        return success


def show_progress(state: dict, current: str = "") -> None:
    """Count durable completed steps, not attempts or inferred successes."""
    total = completed = 0
    for cell in state["cells"]:
        planned = cell["features"] * (1 if POST_KINDS[cell["arm"]] is None else 2) + int(cell["change_request"])
        done = cell.get("completed_steps", planned if cell["status"] == "completed" else 0)
        if type(done) is not int or not 0 <= done <= planned:
            raise StudyError("Invalid saved step progress")
        total += planned
        completed += done
    finished = sum(cell["status"] == "completed" for cell in state["cells"])
    print(f"Progress: {completed}/{total} steps completed; {total - completed} remaining | "
          f"{finished}/{len(state['cells'])} trajectories complete"
          + (f" | {current}" if current else ""), flush=True)


def planned_resources(cells: list[dict]) -> dict:
    """Expose the actual selected schedule, not the aggregate spending permission."""
    sessions = seconds = nominal = 0
    for cell in cells:
        post = POST_KINDS[cell["arm"]] is not None
        longer = cell["arm"] == "D"
        features, cr = cell["features"], int(cell["change_request"])
        sessions += features * (1 + post) + cr
        seconds += features * (1800 + 900 * (post or longer)) + 2700 * cr
        nominal += features * (300 + 300 * (post or longer)) + 300 * cr
    return {"trajectories": len(cells), "planned_sessions": sessions,
            "maximum_agent_hours": seconds / 3600,
            "nominal_session_allowance_credits_not_permitted_spending": nominal}


def launch_replicates(args, directory: Path) -> int | None:
    """Select once before collection; read-only commands never prompt."""
    if args.smoke or args.phase in ("pilot", "calibration"):
        if args.replicates is not None:
            raise StudyError("Replicate selection applies only to estimation, not calibration or smoke")
        return None
    saved = directory / "state.json"
    if saved.exists():
        count = read_json(saved)["identity"].get("replicates_per_model_arm")
        if args.replicates is not None and args.replicates != count:
            raise StudyError("Cannot change replicates on resume; preserve the original allocation")
        return selected_replicates(count)
    if args.replicates is not None:
        return selected_replicates(args.replicates)
    default = selected_replicates(21 if getattr(args, "unregistered_manifest", None) else None)
    if not (args.dry_run or args.check_vm) and sys.stdin.isatty():
        print("Choose replicates per model/arm before collection: 12, 21 or 33. "
              "Record this allocation prospectively; it cannot change on resume.", flush=True)
        answer = input(f"Replicates [{default}]: ").strip()
        if answer:
            if answer not in {str(value) for value in REPLICATE_OPTIONS}:
                raise StudyError("Replicates must be 12, 21 or 33 per model/arm")
            return selected_replicates(int(answer))
    return default


def main() -> int:
    """Check, preview, run the stub pipeline, or explicitly publish derived results."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "harness/study-config.json")
    parser.add_argument("--study-id", default="stub-smoke")
    parser.add_argument("--smoke", action="store_true", help="one feature per A/B/C, built-in fake agent only")
    parser.add_argument("--dry-run", action="store_true", help="read-only preflight and schedule")
    parser.add_argument("--check-vm", action="store_true", help="check prerequisites; never install or run agents")
    parser.add_argument("--phase", choices=["pilot", "first", "calibration", "pilot-estimation"],
                        default="pilot-estimation")
    parser.add_argument("--replicates", type=int, choices=REPLICATE_OPTIONS,
                        help="replicates per model/arm; default 12 registered or 21 unregistered, immutable on resume")
    parser.add_argument("--short-calibration", action="store_true",
                        help="one feature per model/arm in excluded calibration")
    parser.add_argument("--parallel", type=int, default=4,
                        help="maximum concurrent independent trajectories (default: 4; adjustable on resume)")
    parser.add_argument("--unregistered-manifest", type=Path,
                        help="explicit owner evidence for the publicly disclosed, unregistered changed design")
    parser.add_argument("--calibration-study-id",
                        help="completed short-calibration study whose accounting is carried into estimation")
    parser.add_argument("--recovery-calibration-manifest", type=Path,
                        help="original manifest for a separately authorized incident-recovery calibration")
    parser.add_argument("--recovery-source-root", type=Path, action="append",
                        help="original checkout; repeat in recovery order to preserve every source lock")
    parser.add_argument("--publish", action="store_true", help="push only derived results and create/update a PR")
    saved = parser.add_mutually_exclusive_group()
    saved.add_argument("--status", action="store_true", help="show saved progress without authentication or model calls")
    saved.add_argument("--share", action="store_true", help="package existing derived results locally; never run models")
    args = parser.parse_args()
    if args.parallel < 1:
        raise StudyError("Parallelism must be a positive integer")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", args.study_id):
        raise StudyError("study-id must be lowercase letters/digits/hyphens, at most 64 characters")
    directory = ROOT / ".study" / args.study_id
    if (ROOT / ".study").is_symlink() or directory.is_symlink():
        raise StudyError("Study state must not be symlinked")
    if (directory / "state.json").is_symlink():
        raise StudyError("Study state must not be symlinked")
    if args.status or args.share:
        if not (directory / "state.json").is_file():
            raise StudyError(f"No saved experiment: {args.study_id}")
        state = read_json(directory / "state.json")
        show_progress(state, state["status"])
        if args.share:
            from study_report import package_results
            with study_lock(directory):
                print(f"Shareable results: {package_results(directory / 'results', args.study_id)}")
        return 0
    saved_state = read_json(directory / "state.json") if (directory / "state.json").is_file() else None
    recovered = bool(saved_state and saved_state.get("recovery"))
    if recovered != bool(args.recovery_source_root):
        raise StudyError("Recovered studies require their original checkout; other studies must not supply one")
    if recovered != bool(args.recovery_calibration_manifest):
        raise StudyError("Recovered studies require their original calibration manifest")
    source_locks = recovery_source_locks(saved_state, args.recovery_source_root) if recovered else None
    cfg = read_json(args.config)
    if args.smoke and args.unregistered_manifest:
        raise StudyError("Unregistered launch evidence does not apply to offline smoke runs")
    if args.unregistered_manifest and args.unregistered_manifest.is_symlink():
        raise StudyError("Unregistered launch evidence must not be a symlink")
    unregistered = read_json(args.unregistered_manifest) if args.unregistered_manifest else None
    estimation = not args.smoke and args.phase not in ("pilot", "calibration")
    if args.calibration_study_id and not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", args.calibration_study_id):
        raise StudyError("Invalid calibration study ID")
    if args.calibration_study_id == args.study_id:
        raise StudyError("Calibration and estimation must use different study IDs")
    if args.calibration_study_id and (not estimation or unregistered is None):
        raise StudyError("Calibration handoff is only available for unregistered estimation")
    replicates = launch_replicates(args, directory)
    errors = (preflight(cfg, smoke=args.smoke) if unregistered is None
              else preflight(cfg, smoke=args.smoke, unregistered=unregistered))
    if unregistered is not None and (args.phase == "pilot"
                                      or (args.phase == "calibration" and not args.short_calibration)):
        errors.append("Unregistered calibration requires the explicitly authorized short calibration plan")
    handoff = None
    calibration_directory = ROOT / ".study" / args.calibration_study_id if args.calibration_study_id else None
    calibration_manifest = unregistered
    if args.recovery_calibration_manifest:
        if not estimation or unregistered is None or calibration_directory is None:
            raise StudyError("Recovery calibration manifest requires unregistered estimation and calibration")
        calibration_manifest = recovery_calibration_manifest(directory, args.recovery_calibration_manifest,
                                                            unregistered)
    if unregistered is not None and estimation:
        if calibration_directory is None:
            errors.append("Completed short-calibration accounting handoff is required for estimation")
        else:
            try:
                handoff = calibration_handoff(calibration_directory, cfg, calibration_manifest)
            except (StudyError, OSError, ValueError, KeyError, TypeError) as error:
                errors.append(str(error) if isinstance(error, StudyError)
                              else "Calibration accounting evidence is unreadable or malformed")
    cells = (schedule(args.smoke, args.phase, cfg["seed"], replicates,
                      short_calibration=args.short_calibration) if type(cfg.get("seed")) is int else [])
    preview = {"mode": "stub-smoke" if args.smoke else args.phase,
               "replicates_per_model_arm": replicates,
               "calibration_plan": "one-feature-per-model-arm" if args.short_calibration else None,
               "parallelism": args.parallel,
               "maximum_active_trajectories": min(args.parallel, len(cells)),
               "registration_status": ("diagnostic" if args.smoke
                                       else "unregistered" if unregistered is not None else "registration-required"),
               "public_disclosure_url": unregistered.get("public_disclosure_url") if unregistered else None,
               "calibration_handoff": handoff,
               "inputs_sha256": fingerprint(),
               "schedule": cells,
               "planned_resources": planned_resources(cells) if not args.smoke else None,
               "token_present": bool(os.environ.get("COPILOT_GITHUB_TOKEN")),
               "hard_billing_supported": False, "budget_policy": budget_policy(cfg), "errors": errors}
    if args.dry_run or args.check_vm:
        print(json.dumps(preview, indent=2))
        return 2 if errors else 0
    if errors:
        raise StudyError("; ".join(errors))
    if not args.smoke:
        from isolated_runtime import check_host_auth
        check_host_auth(ROOT)
        print("Authentication: signed-in host Copilot user; no credentials enter candidate containers.", flush=True)
    with ExitStack() as locks:
        if not args.smoke:
            locks.enter_context(paid_study_lock())
        if source_locks:
            for path in source_locks:
                locks.enter_context(study_lock(path))
            recovery_source_locks(saved_state, args.recovery_source_root)
        locks.enter_context(study_lock(directory))
        if calibration_directory is not None:
            with study_lock(calibration_directory):
                handoff = calibration_handoff(calibration_directory, cfg, calibration_manifest)
        controller = Controller(directory, cfg, smoke=args.smoke, phase=args.phase, study_id=args.study_id,
                                replicates=replicates, short_calibration=args.short_calibration,
                                parallelism=args.parallel, unregistered=unregistered, handoff=handoff)
        success = controller.go()
        from study_report import package_results
        print(f"Shareable results: {package_results(directory / 'results', args.study_id)}")
        if args.publish:
            from study_report import publish
            publish(directory / "results", args.study_id)
    label = "offline diagnostic" if args.smoke else "experiment"
    print(f"{'Completed' if success else 'Partial'} {label}: "
          f".study/{args.study_id}/results/report.md")
    return 0 if success else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (StudyError, OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        # Do not echo raw tool output, prompts or arbitrary config contents.
        message = str(error) if isinstance(error, StudyError) else type(error).__name__
        print(f"Study stopped: {message}", file=sys.stderr)
        raise SystemExit(2)
