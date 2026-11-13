"""Offline reviewer-package regressions using synthetic data, not human responses."""
from __future__ import annotations

import copy
import csv
import hashlib
import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def builder():
    spec = importlib.util.spec_from_file_location("human_review_build", ROOT / "judging/human-review/build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def package_files(builder):
    selection, packets, rubric = builder.diagnostic_inputs()
    files, _ = builder.build_files(selection, packets, rubric)
    return files


@pytest.fixture
def source_zip(builder, package_files, tmp_path):
    source = tmp_path / "source.zip"
    with zipfile.ZipFile(source, "x") as archive:
        for name, raw in package_files.items():
            archive.writestr(f"{builder.ROOT_NAME}/{name}", raw)
    return source


def test_given_repository_assets_when_running_self_test_then_no_private_dependencies_are_needed(builder):
    builder.self_test()


def test_given_diagnostic_packets_when_building_then_all_rows_and_human_blanks_are_preserved(builder, package_files):
    builder.validate_files(package_files)
    rows = list(csv.DictReader(io.StringIO(package_files["SCORING_TEMPLATE.csv"].decode("utf-8-sig"))))
    details = list(csv.DictReader(io.StringIO(package_files["REVIEWER_DETAILS.csv"].decode("utf-8-sig"))))

    assert len(package_files) == 30
    assert len(rows) == len({(row["specimen_id"], row["scenario_id"]) for row in rows}) == 90
    assert all(not row[f"{dimension}_score"] for row in rows for dimension in builder.DIMENSIONS)
    assert all(not value for row in details for value in row.values())


def test_given_untrusted_evidence_when_rendering_then_scripts_remain_data(builder, package_files):
    assert b"&lt;script&gt;not executable&lt;/script&gt;" in package_files["evidence/S01.html"]
    assert b"\\u003cscript>not executable\\u003c/script>" in package_files["START_HERE.html"]
    assert b"connect-src 'none'" in package_files["START_HERE.html"]
    assert b"script-src 'sha256-" in package_files["START_HERE.html"]
    builder.validate_files(package_files)


@pytest.mark.parametrize("field", ["requirements", "final"])
def test_given_same_outputs_with_different_context_when_grouping_then_they_are_not_merged(builder, field):
    selection, packets, _ = builder.diagnostic_inputs()
    original = builder.evidence_groups(selection, packets)
    identity = selection["specimens"][0]
    changed = copy.deepcopy(packets[identity][0])
    if field == "requirements":
        changed["scenarios"][0]["requirements"][0]["story"] = "A different public requirement"
    else:
        changed["scenarios"][0]["final"]["error_type"] = "DiagnosticFailure"
    packets[identity] = changed, builder.canonical(changed)

    assert len(builder.evidence_groups(selection, packets)) == len(original) + 1


def test_given_changed_workflow_action_when_building_then_explanation_mismatch_is_rejected(builder):
    selection, packets, rubric = builder.diagnostic_inputs()
    identity = selection["specimens"][0]
    packet = copy.deepcopy(packets[identity][0])
    packet["scenarios"][0]["id"] = "registration"
    packets[identity] = packet, builder.canonical(packet)

    with pytest.raises(ValueError, match="differs from the frozen observation"):
        builder.build_files(selection, packets, rubric)


@pytest.mark.parametrize("private_value", [b'"assigned_model"', b"pilot-estimation-private-run"])
def test_given_private_identity_when_validating_then_export_is_refused(builder, package_files, private_value):
    package_files["rubric.json"] = private_value

    with pytest.raises(ValueError, match="Private identity"):
        builder.validate_files(package_files)


def test_given_prefilled_human_score_when_validating_then_no_review_can_be_fabricated(builder, package_files):
    rows = list(csv.DictReader(io.StringIO(package_files["SCORING_TEMPLATE.csv"].decode("utf-8-sig"))))
    rows[0]["functional_completeness_score"] = "4"
    package_files["SCORING_TEMPLATE.csv"] = builder.csv_bytes(list(rows[0]), rows)

    with pytest.raises(ValueError, match="must never be prefilled"):
        builder.validate_files(package_files)


def test_given_verified_source_when_exporting_then_packets_hashes_and_source_bytes_are_preserved(
        builder, source_zip, package_files, tmp_path, monkeypatch):
    output = tmp_path / "reviewer.zip"
    original = source_zip.read_bytes()
    monkeypatch.setattr(sys, "argv", ["build.py", "--source-zip", str(source_zip), "--output", str(output)])

    assert builder.main() == 0

    with zipfile.ZipFile(output) as archive:
        assert archive.testzip() is None
        exported = {name.removeprefix(builder.ROOT_NAME + "/"): archive.read(name) for name in archive.namelist()}
    builder.validate_files(exported)
    for name in (name for name in package_files if name.startswith("packets/") or name in ("selection.json", "rubric.json")):
        assert exported[name] == package_files[name]
    assert source_zip.read_bytes() == original
    assert output.with_suffix(".zip.sha256").read_text() == f"{hashlib.sha256(output.read_bytes()).hexdigest()}  reviewer.zip\n"


def test_given_existing_output_when_exporting_then_original_file_is_not_overwritten(
        builder, source_zip, tmp_path, monkeypatch):
    output = tmp_path / "existing.zip"
    output.write_bytes(b"Keep existing evidence unchanged")
    monkeypatch.setattr(sys, "argv", ["build.py", "--source-zip", str(source_zip), "--output", str(output)])

    with pytest.raises(ValueError, match="new ZIP path"):
        builder.main()

    assert output.read_bytes() == b"Keep existing evidence unchanged"


@pytest.mark.parametrize("tamper", [False, True])
def test_given_frozen_data_root_when_exporting_then_only_hash_bound_packets_are_accepted(
        builder, package_files, tmp_path, monkeypatch, tamper):
    data = tmp_path / "data"
    sample = data / "human-calibration"
    public = data / "judging-batch/public"
    sample.mkdir(parents=True)
    public.mkdir(parents=True)
    (sample / "manifest.json").write_bytes(package_files["selection.json"])
    selection = json.loads(package_files["selection.json"])
    bindings = []
    for identity in selection["specimens"]:
        raw = package_files[f"packets/{identity}.json"]
        packet = json.loads(raw)
        bindings.append({"id": identity, "sha256": hashlib.sha256(builder.canonical(packet)).hexdigest()})
        if tamper and identity == selection["specimens"][0]:
            packet["scenarios"][0]["title"] = "Changed after the instrument freeze"
            raw = builder.canonical(packet)
        (sample / f"{identity}.json").write_bytes(raw)
    (public / "manifest.json").write_text(json.dumps({
        "packets": bindings, "rubric": json.loads(package_files["rubric.json"])}), encoding="utf-8")
    output = tmp_path / "reviewer.zip"
    monkeypatch.setattr(sys, "argv", ["build.py", "--data-root", str(data), "--output", str(output)])

    if tamper:
        with pytest.raises(ValueError, match="differs from the frozen judging evidence"):
            builder.main()
        assert not output.exists()
    else:
        assert builder.main() == 0
        with zipfile.ZipFile(output) as archive:
            assert archive.read(f"{builder.ROOT_NAME}/selection.json") == package_files["selection.json"]


def test_given_traversal_member_when_reading_source_then_zip_is_rejected(builder, tmp_path, monkeypatch):
    source = tmp_path / "unsafe.zip"
    output = tmp_path / "unused.zip"
    with zipfile.ZipFile(source, "x") as archive:
        archive.writestr(f"{builder.ROOT_NAME}/../private.json", "{}")
    monkeypatch.setattr(sys, "argv", ["build.py", "--source-zip", str(source), "--output", str(output)])

    with pytest.raises(ValueError, match="missing or unexpected|non-allowlisted|Unsafe"):
        builder.main()

    assert not output.exists()