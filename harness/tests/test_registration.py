"""Offline submission/readiness and oracle-repeatability boundary tests."""
import importlib
import json
import shutil
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def registration(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "harness"))
    return importlib.import_module("prepare_registration")


@pytest.fixture
def config():
    config = json.loads((ROOT / "protocol/pilot-estimation.json").read_text())
    config.pop("scientific_review_policy", None)
    config.pop("runtime_access_review_policy", None)
    for key in ("independent_suite_review", "contract_panel_review", "oracle_stability",
                "analysis_and_reference_metrics_acceptance", "multi_model_harness_alignment",
                "local_runtime_evidence", "access_probe_including_cr1_text"):
        config["required_evidence"][key] = None
    config["owner_approval"] = {"approved": False, "date": None, "evidence": None}
    config["registration"] = {"submitted": False, "url": None, "date": None}
    return config


@pytest.fixture
def draft_root(tmp_path, registration, monkeypatch):
    for relative in registration.SUBMISSION_FILES:
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / relative, target)
    shutil.copytree(ROOT / "suites", tmp_path / "suites")
    shutil.copyfile(ROOT / "run-study.sh", tmp_path / "run-study.sh")
    monkeypatch.setattr(registration, "command", lambda args, **kwargs: "a" * 40 if "rev-parse" in args else "")
    return tmp_path


def test_candidate_panel_matches_exact_source_and_never_approves_itself(registration):
    module = importlib.import_module("contract_panel")
    suite = ROOT / "suites/s1-retrofit"
    actual = module.checked_panel(ROOT / "protocol/contract-panel.json", suite)
    candidate = module.build_panel(suite)
    assert {key: value for key, value in actual.items() if key not in ("review", "status")} == {
        key: value for key, value in candidate.items() if key not in ("review", "status")}
    assert len(actual["contracts"]) == 142 and not module.accepted(candidate)
    assert module.accepted(actual) and actual["review"]["independent"] is False
    assert len({item["id"] for item in actual["contracts"]}) == 142


def test_changed_oracle_source_invalidates_panel(registration, draft_root):
    path = draft_root / "suites/s1-retrofit/features/f01/hidden/test_f01_hidden.py"
    path.write_text(path.read_text() + "\n# synthetic source change\n")
    with pytest.raises(ValueError, match="differs"):
        registration.prepare(draft_root / ".study/draft", draft_root)
    assert not (draft_root / ".study").exists()


def test_draft_complete_is_separate_from_submission_registration_and_execution(registration, config):
    report = registration.readiness(config, {"review": {"accepted": False}})
    assert report["draft_complete"] and report["no_registration_required_to_prepare_draft"]
    assert not report["author_submission_ready"] and not report["registration_recorded"]
    assert report["unresolved"] == report["submission_unresolved"] == ["owner_approval"]
    assert len(report["collection_unresolved"]) == 9
    assert not report["execution_ready"]


def test_explicit_secondary_exclusion_resolves_only_its_alternative_gate(registration, config):
    config["required_evidence"] = dict.fromkeys(registration.EVIDENCE)
    pending = registration.readiness(config, {"review": {"accepted": False}})
    config["required_evidence"]["telemetry_coverage_or_explicit_secondary_unavailability"] = (
        "Owner explicitly excludes HIR/IDR outcomes; assistance and primary accounting remain required.")
    report = registration.readiness(config, {"review": {"accepted": False}})
    assert set(pending["unresolved"]) - set(report["unresolved"]) == {
        "required_evidence.telemetry_coverage_or_explicit_secondary_unavailability"}
    assert len(report["unresolved"]) == 2
    assert len(report["collection_unresolved"]) == 10
    assert not report["author_submission_ready"] and not report["execution_ready"]
    assert not report["registration_recorded"]


def test_explicit_decisions_and_approval_do_not_invent_registration_or_live_backend(registration, config):
    config["owner_decisions"] = dict.fromkeys(registration.DECISIONS, "Synthetic owner resolution")
    config["required_evidence"] = dict.fromkeys(registration.EVIDENCE, "Synthetic independent evidence")
    config["owner_approval"] = {"approved": True, "date": "2026-10-27", "evidence": "Synthetic approval"}
    report = registration.readiness(config, {"review": {"accepted": True, "evidence": "Synthetic review"}})
    assert report["author_submission_ready"]
    assert not report["registration_recorded"] and not report["execution_ready"]
    config["owner_decisions"]["post_after_failed_feature"] = "TODO choose policy"
    assert not registration.readiness(config, {"review": {"accepted": True, "evidence": "review"}})["author_submission_ready"]
    config["owner_decisions"] = {}
    with pytest.raises(registration.StudyError, match="ledger fields"):
        registration.readiness(config, {"review": {}})


def test_draft_rejects_incomplete_duplicate_or_unapproved_model_roster(registration, config):
    models = config["study"]["model_roster"]
    for roster in (models[:2], [models[0], models[0], models[2]],
                   [*models[:2], "unapproved-model"], [*models[:2], {}]):
        config["study"]["model_roster"] = roster
        assert not registration.readiness(config, {"review": {}})["draft_complete"]


def test_draft_rejects_old_allocation_budget_or_singular_runtime(registration, config):
    for section, key, wrong in (("study", "runs_per_arm", 4),
                                ("resources", "credit_ceiling", 2500),
                                ("resources", "separate_monetary_budget_usd", 500),
                                ("runtime", "model", "claude-sonnet-5.5")):
        original = config[section][key]
        config[section][key] = wrong
        assert not registration.readiness(config, {"review": {}})["draft_complete"]
        config[section][key] = original


def test_both_stage_session_caps_are_required_by_approved_draft(registration, config):
    for key in ("pilot_session_credit_cap", "calibration_session_credit_cap"):
        config["resources"][key] = 301
        assert not registration.readiness(config, {"review": {}})["draft_complete"]
        config["resources"][key] = 300


def test_alignment_evidence_blocks_collection_not_approved_submission(registration, config):
    config["required_evidence"] = dict.fromkeys(registration.EVIDENCE, "Synthetic independent evidence")
    config["required_evidence"]["multi_model_harness_alignment"] = None
    config["owner_approval"] = {"approved": True, "date": "2026-10-27", "evidence": "Synthetic approval"}
    report = registration.readiness(config, {"review": {"accepted": True, "evidence": "Synthetic review"}})
    assert report["draft_complete"] and report["author_submission_ready"]
    assert report["submission_unresolved"] == report["unresolved"] == []
    assert report["collection_unresolved"] == ["required_evidence.multi_model_harness_alignment"]
    assert not report["execution_ready"]
    del config["required_evidence"]["multi_model_harness_alignment"]
    with pytest.raises(registration.StudyError, match="ledger fields"):
        registration.readiness(config, {"review": {}})


def test_unreviewed_plan_can_be_approved_for_submission_without_collection(registration, config):
    for key in registration.EVIDENCE - registration.SUBMISSION_EVIDENCE:
        config["required_evidence"][key] = None
    config["owner_approval"] = {"approved": True, "date": "2026-10-28", "evidence": "Synthetic submission approval"}
    report = registration.readiness(config, {"review": {"accepted": False}})
    assert report["author_submission_ready"] and report["submission_unresolved"] == []
    assert set(report["collection_unresolved"]) == {
        *(f"required_evidence.{key}" for key in registration.EVIDENCE - registration.SUBMISSION_EVIDENCE),
        "contract_panel_independent_acceptance",
    }
    assert not report["independent_review_required_for_submission"]
    assert report["independent_review_required_before_collection"]
    assert not report["registration_recorded"] and not report["execution_ready"]
    assert any("Isolated live backend" in blocker for blocker in report["execution_blockers"])


def test_owner_scientific_review_is_explicit_and_does_not_clear_runtime_or_freeze(registration):
    current = json.loads((ROOT / "protocol/pilot-estimation.json").read_text())
    current.pop("runtime_access_review_policy")
    for key in ("local_runtime_evidence", "access_probe_including_cr1_text"):
        current["required_evidence"][key] = None
    panel = json.loads((ROOT / "protocol/contract-panel.json").read_text())
    report = registration.readiness(current, panel)
    assert report["scientific_review_mode"] == "owner-reviewed-exploratory-pilot"
    assert report["independent_review_required_before_collection"] is False
    assert set(report["collection_unresolved"]) == {
        "required_evidence.local_runtime_evidence",
        "required_evidence.access_probe_including_cr1_text", "owner_approval"}
    assert report["execution_ready"] is False
    assert report["independent_runtime_access_review_required_before_collection"] is True
    panel["review"]["accepted"] = False
    assert "contract_panel_acceptance" in registration.readiness(current, panel)["collection_unresolved"]
    panel["review"]["accepted"] = True
    current.pop("scientific_review_policy")
    assert "contract_panel_independent_acceptance" in registration.readiness(
        current, panel)["collection_unresolved"]


@pytest.mark.parametrize("field,value", [
    ("mode", "skip-review"), ("decision_date", None), ("evidence", "pending review"),
    ("independent_review_required_before_collection", True), ("independent_review_completed", True),
])
def test_owner_review_policy_cannot_omit_provenance_or_claim_independence(registration, field, value):
    current = json.loads((ROOT / "protocol/pilot-estimation.json").read_text())
    current["scientific_review_policy"][field] = value
    with pytest.raises(registration.StudyError, match="scientific review|Scientific review"):
        registration.readiness(current, {"review": {}})


def test_owner_runtime_access_acceptance_does_not_authorize_execution_or_claim_independence(registration):
    current = json.loads((ROOT / "protocol/pilot-estimation.json").read_text())
    panel = json.loads((ROOT / "protocol/contract-panel.json").read_text())
    report = registration.readiness(current, panel)
    assert report["runtime_access_review_mode"] == "owner-reviewed-runtime-access"
    assert report["independent_runtime_access_review_required_before_collection"] is False
    assert report["independent_runtime_access_review_completed"] is False
    assert report["collection_unresolved"] == ["owner_approval"]
    assert report["execution_ready"] is False
    assert any("freeze" in blocker for blocker in report["execution_blockers"])
    assert not any("require separate acceptance" in blocker for blocker in report["execution_blockers"])
    current["required_evidence"]["access_probe_including_cr1_text"] = None
    pending = registration.readiness(current, panel)
    assert "required_evidence.access_probe_including_cr1_text" in pending["collection_unresolved"]
    assert any("require separate acceptance" in blocker for blocker in pending["execution_blockers"])


@pytest.mark.parametrize("field,value", [
    ("mode", "skip-review"), ("decision_date", None), ("evidence", "pending review"),
    ("independent_review_required_before_collection", True), ("independent_review_completed", True),
])
def test_owner_runtime_review_policy_requires_provenance_and_no_independence_claim(registration, field, value):
    current = json.loads((ROOT / "protocol/pilot-estimation.json").read_text())
    current["runtime_access_review_policy"][field] = value
    with pytest.raises(registration.StudyError, match="runtime/access|Runtime/access"):
        registration.readiness(current, {"review": {}})


@pytest.mark.parametrize("key", ["prior_data_disclosure", "telemetry_coverage_or_explicit_secondary_unavailability"])
@pytest.mark.parametrize("missing", [None, "TODO owner decision"])
def test_submission_still_requires_real_disclosures_and_scope(registration, config, key, missing):
    config["owner_approval"] = {"approved": True, "date": "2026-10-28", "evidence": "Synthetic submission approval"}
    config["required_evidence"][key] = missing
    report = registration.readiness(config, {"review": {"accepted": False}})
    assert not report["author_submission_ready"]
    assert report["submission_unresolved"] == [f"required_evidence.{key}"]
    assert f"required_evidence.{key}" in report["collection_unresolved"]


def test_package_is_allowlisted_hashed_private_and_refuses_overwrite(registration, draft_root):
    (draft_root / ".env").write_text("synthetic private data")
    out = draft_root / ".study/draft"
    report = registration.prepare(out, draft_root)
    manifest = json.loads((out / "manifest.json").read_text())
    assert manifest["readiness"] == report and manifest["approval_inferred"] is False
    copied = {path.relative_to(out).as_posix() for path in out.rglob("*") if path.is_file()}
    assert copied == set(registration.SUBMISSION_FILES) | {"manifest.json", "readiness.json"}
    assert set(manifest["package_sha256"]) == set(registration.SUBMISSION_FILES)
    assert not out.stat().st_mode & 0o077
    assert all(not path.stat().st_mode & 0o077 for path in out.rglob("*"))
    before = (out / "manifest.json").read_bytes()
    with pytest.raises(registration.StudyError, match="already exists"):
        registration.prepare(out, draft_root)
    assert (out / "manifest.json").read_bytes() == before


@pytest.mark.parametrize("attack", ["outside", "symlink", "secret"])
def test_package_rejects_unsafe_boundary_and_credentials(registration, draft_root, monkeypatch, attack):
    out = draft_root / ".study/draft"
    if attack == "outside":
        out = draft_root / "public"
    elif attack == "symlink":
        (draft_root / "elsewhere").mkdir()
        (draft_root / ".study").symlink_to(draft_root / "elsewhere", target_is_directory=True)
    else:
        monkeypatch.setenv("SYNTHETIC_API_KEY", "synthetic-only-credential-canary")
        (draft_root / "protocol/osf-preregistration.md").write_text("synthetic-only-credential-canary")
    with pytest.raises(registration.StudyError):
        registration.prepare(out, draft_root)
    assert not out.exists()


def test_unchanged_oracle_repeats_reject_instability(registration, monkeypatch):
    validator = importlib.import_module("validate_suite")
    calls = iter([{"test": "passed"}, {"test": "failed"}])
    monkeypatch.setattr(validator, "run_isolated", lambda *_: next(calls))
    with pytest.raises(RuntimeError, match="instability"):
        validator.run_repeated([], None, 2)


def test_stable_repeats_compare_exact_outcomes_and_do_not_approve(registration, monkeypatch):
    validator = importlib.import_module("validate_suite")
    seen = []
    def fixed(files, reference):
        seen.append((files, reference))
        return {"test": "passed"}
    monkeypatch.setattr(validator, "run_isolated", fixed)
    assert validator.run_repeated(["synthetic"], "reference", 3) == {"test": "passed"}
    assert len(seen) == 3


def test_reference_metrics_are_raw_backend_labelled_unapproved_evidence(registration):
    validator = importlib.import_module("validate_suite")
    suite_path = ROOT / "suites/s1-retrofit"
    suite = json.loads((suite_path / "suite.json").read_text())
    suite["features"] = suite["features"][:1]
    metrics = validator.reference_metrics(str(suite_path), suite, ("internal", "internal", "none"))
    assert metrics["accepted_for_gaps"] is False
    assert metrics["rows"][0]["metrics"]["backends"]["complexity"] == "internal"
    assert metrics["rows"][0]["reference_sha256"] and metrics["lint_config_sha256"]
