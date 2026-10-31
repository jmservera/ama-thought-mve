"""Exact export-shape and local-only publication tests; no paid agent or GitHub calls."""
import csv
import importlib
import json
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile
from itertools import pairwise
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def modules(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "harness"))
    return importlib.import_module("study"), importlib.import_module("study_report")


@pytest.fixture
def reports(modules, tmp_path):
    study, _report = modules
    cfg = json.loads((ROOT / "harness/study-config.json").read_text())
    current = study.Controller(tmp_path / "private", cfg, smoke=True, phase="first", study_id="export-test")
    current.state["deadline"] = 0
    current.save()
    assert not current.go()
    return current.directory / "results"


def test_exact_export_schemas_unavailable_values_and_figure(modules, reports):
    study, report = modules
    assert {path.name for path in reports.iterdir()} == set(report.EXPORTS)
    assert len(report.validated_artifacts(reports)) == len(report.EXPORTS)
    summary = study.read_json(reports / "summary.json")
    assert summary["cost_unit"] == "credits" and len(summary["runs"]) == 3
    assert summary["provenance"]["diagnostic_stub"] is True
    assert summary["provenance"]["session_soft_limit_credits"] == 270
    assert summary["provenance"]["ceiling_nano"] == 270000 * study.NANO
    assert "not guaranteed" in summary["provenance"]["billing_limit_kind"]
    assert summary["endpoints"]["H1"]["B-A"]["difference"] is None
    assert "verdict" not in json.dumps(summary) and "hypotheses" not in summary
    availability = study.read_json(reports / "availability.json")
    assert availability["zero_intervention_inferred"] is False
    assert {"H4", "H7", "HIR", "IDR", "mixed_effects", "decay_amendment"} <= availability["unavailable"].keys()
    with (reports / "runs.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 3 and all(row["status"] == "pending" for row in rows)
    assert all(row["unattempted_cycles"] == "1" and row["HIR"] == "" for row in rows)
    with (reports / "intervals.csv").open() as stream:
        intervals = list(csv.DictReader(stream))
    assert any(row["hypothesis"] == "H1" and row["field"] == "B-A.ci.0" for row in intervals)
    assert ET.parse(reports / "trajectories.svg").getroot().tag.endswith("svg")
    assert "STUB DIAGNOSTIC" in (reports / "trajectories.tex").read_text()
    assert "unavailable" in (reports / "hypotheses.tex").read_text()
    assert "not confirmatory" in (reports / "hypotheses.tex").read_text()


def test_export_is_deterministic_and_has_no_private_paths(modules, reports):
    study, report = modules
    state = study.read_json(reports.parent / "state.json")
    before = {path.name: path.read_bytes() for path in reports.iterdir()}
    report.export(reports.parent, state, "export-test")
    assert before == {path.name: path.read_bytes() for path in reports.iterdir()}
    assert all(str(reports.parent).encode() not in data for data in before.values())


def test_shareable_archive_is_deterministic_and_contains_only_validated_results(modules, reports):
    study, report = modules
    path = report.package_results(reports, "export-test")
    before = path.read_bytes()
    assert path.parent == reports.parent and path.stat().st_mode & 0o777 == 0o600
    with zipfile.ZipFile(path) as archive:
        assert set(archive.namelist()) == {f"export-test/{name}" for name in report.EXPORTS}
        assert archive.read("export-test/report.md") == (reports / "report.md").read_bytes()
    assert report.package_results(reports, "export-test").read_bytes() == before
    with pytest.raises(study.StudyError, match="provenance"):
        report.package_results(reports, "different-study")


@pytest.mark.parametrize("action", ["--status", "--share"])
def test_saved_progress_and_sharing_need_no_authentication_or_paid_preflight(
    modules, reports, tmp_path, monkeypatch, capsys, action,
):
    study, _report = modules
    root = tmp_path / "operator"
    directory = root / ".study/export-test"
    shutil.copytree(reports.parent, directory)
    before = (directory / "state.json").read_bytes()
    monkeypatch.setattr(study, "ROOT", root)
    monkeypatch.setattr(study, "preflight", lambda *args, **kwargs: pytest.fail("Read-only saved action"))
    monkeypatch.setattr(study.sys, "argv", ["study", "--study-id", "export-test", action])
    assert study.main() == 0
    assert "0/5 steps completed; 5 remaining" in capsys.readouterr().out
    assert (directory / "state.json").read_bytes() == before
    assert (directory / "export-test-results.zip").exists() is (action == "--share")


@pytest.mark.parametrize("legacy", [False, True])
def test_exports_distinguish_historical_budget_hold_from_actual_usage(modules, reports, legacy):
    study, report = modules
    state = study.read_json(reports.parent / "state.json")
    cfg = study.read_json(ROOT / "harness/study-config.json")
    state["ledger"]["prior_nano"] = study.credits(cfg["prior_credits"])
    state["ledger"]["historical_credit_provisions"] = study.historical_credit_provisions(cfg)
    exporter = report.legacy_export if legacy else report.export
    exporter(reports.parent, state, "export-test")
    provenance = study.read_json(reports / "provenance.json")
    assert provenance["prior_nano"] == study.credits("21.79019")
    assert provenance["historical_reserved_nano"] == study.credits(1200)
    assert provenance["historical_usage_complete"] is False
    holds = provenance["historical_credit_provisions"]
    assert [hold["attempt_id"] for hold in holds] == [
        item["attempt_id"] for item in cfg["historical_credit_provisions"]]
    assert all(hold["actual_nano"] is None and hold["status"] == "unknown" for hold in holds)


@pytest.mark.parametrize("outcome", ["error", "skipped", "timeout"])
@pytest.mark.parametrize("unknown_k", [9, 10])
def test_unknown_coverage_exports_blank_csv_and_real_figure_gaps(modules, tmp_path, outcome, unknown_k):
    _, report = modules
    first, second, cr = "test_f01::test_x", "test_f02::test_y", "test_cr1::test_cr"
    panel = {"suite": "synthetic", "review": {"accepted": True, "evidence": "synthetic review"},
             "contracts": [{"id": name, "feature": feature, "role": role, "from_cycle": start,
                            "through_cycle": end, "unchanged": True, "oracle_version": "v1"}
                           for name, feature, role, start, end in (
                               (first, "f01", "feature", 1, 10),
                               (second, "f02", "feature", 1, 10),
                               (cr, "cr1", "cr1", 11, 11))]}
    records = []
    for k in range(1, 11):
        for kind in ("feature", "consolidation"):
            hidden = {first: "passed", second: outcome if k == unknown_k else
                      "passed" if k == 10 else "failed"}
            records.append({"kind": kind, "k": k, "measure": {
                "hidden": hidden, "hidden_total": 2,
                "hidden_passed": sum(value == "passed" for value in hidden.values()),
                "metrics": {"mean_ccn": k}}})
    records.append({"kind": "change_request", "k": 10, "measure": {
        "hidden": dict.fromkeys((first, second, cr), "passed"), "hidden_total": 3, "hidden_passed": 3}})
    raw = {"dir": "", "meta": {"arm": "B", "features": 10, "run_id": "synthetic",
                               "suite": "synthetic", "phase": "pilot-estimation", "change_request": True},
           "recs": records}

    result = report.analyze_pilot([raw], panel=panel, n=20)
    report.write_pilot(tmp_path, result)

    with (tmp_path / "series.csv").open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    expected = [None if k == unknown_k else 100 if k == 10 else 50 for k in range(1, 11)]
    assert [None if row["pass_rate"] == "" else float(row["pass_rate"]) for row in rows] == expected
    assert [float(row["mean_ccn"]) for row in rows] == list(range(1, 11))
    summary = json.loads((tmp_path / "summary.json").read_text())["runs"][0]
    assert len(summary["series"]) == 10 and summary["sequence_complete"]
    assert summary["end"]["pass_rate"] == expected[-1]
    assert summary["cr_success"] is (None if unknown_k == 10 else True)

    svg = ET.parse(tmp_path / "trajectories.svg").getroot()
    circles = svg.findall("{http://www.w3.org/2000/svg}circle")
    coverage_points = {(node.attrib["cx"], node.attrib["cy"]) for node in circles
                       if float(node.attrib["cx"]) < 500}
    expected_points = [(f"{60 + 350 * (k - 1) / 9:.2f}", f"{65 + 210 * (1 - value / 100):.2f}")
                       if value is not None else None for k, value in enumerate(expected, 1)]
    assert coverage_points == {point for point in expected_points if point is not None}
    assert len(circles) == len(coverage_points) + 10
    coverage_segments = {node.attrib["d"] for node in svg.findall("{http://www.w3.org/2000/svg}path")
                         if node.attrib.get("stroke") == "#2471a3"
                         and float(node.attrib["d"].split(",")[0][1:]) < 500}
    assert coverage_segments == {f"M{left[0]},{left[1]} L{right[0]},{right[1]}"
                                 for left, right in pairwise(expected_points)
                                 if left is not None and right is not None}
    latex = (tmp_path / "trajectories.tex").read_text()
    assert latex.count(r"\tiny B") == len(circles)


@pytest.mark.parametrize("attack", ["extra", "symlink", "size", "token", "env-secret"])
def test_publication_refuses_non_results_and_secret_payloads(modules, reports, monkeypatch, tmp_path, attack):
    study, report = modules
    if attack == "extra":
        (reports / ".env").write_text("synthetic only")
    elif attack == "symlink":
        (reports / "summary.md").unlink()
        (tmp_path / "private-log").write_text("private")
        (reports / "summary.md").symlink_to(tmp_path / "private-log")
    elif attack == "size":
        (reports / "summary.md").write_text("x" * (512 * 1024 + 1))
    elif attack == "token":
        (reports / "summary.md").write_text("ghp_" + "notarealcredential" * 2)
    else:
        monkeypatch.setenv("COPILOT_GITHUB_TOKEN", "synthetic-credential-canary")
        (reports / "summary.md").write_text("synthetic-credential-canary")
    with pytest.raises(study.StudyError):
        report.validated_artifacts(reports)
    with pytest.raises(study.StudyError):
        report.package_results(reports, "export-test")


def test_tex_escapes_all_special_characters(modules):
    _, report = modules
    result = report.tex(r"A_B&C%$#{x}~^\end")
    assert r"\_" in result and r"\&" in result and r"\%" in result
    assert r"\textbackslash{}end" in result and r"\{" in result


def git(root, *args):
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, check=True)
    return result.stdout.strip()


@pytest.fixture
def publication_repo(tmp_path, monkeypatch):
    origin = tmp_path / "origin.git"
    root = tmp_path / "source"
    tools = tmp_path / "tools"
    root.mkdir()
    tools.mkdir()
    subprocess.run(["git", "init", "--bare", "-q", str(origin)], check=True)
    git(root, "init", "-q", "-b", "feat/test")
    git(root, "config", "user.name", "Test")
    git(root, "config", "user.email", "test@example.invalid")
    (root / "source.txt").write_text("Not a result\n")
    git(root, "add", "source.txt")
    git(root, "commit", "-qm", "test source")
    git(root, "remote", "add", "origin", str(origin))
    git(root, "push", "-q", "origin", "HEAD")
    fake = tools / "gh"
    marker = tmp_path / "pr-created"
    log = tmp_path / "gh-calls"
    fake.write_text(
        "#!/bin/sh\n"
        f"printf '%s\\n' \"$*\" >> '{log}'\n"
        'if [ "$1 $2" = "auth status" ]; then exit 0; fi\n'
        'if [ "$1 $2" = "pr list" ]; then\n'
        f"  if [ -f '{marker}' ]; then\n"
        '    printf \'[{"number":3,"url":"https://example.invalid/pr/3"}]\\n\'\n'
        "  else printf '[]\\n'; fi\n"
        "elif [ \"$1 $2\" = \"pr create\" ]; then\n"
        f"  touch '{marker}'\n"
        "  printf 'https://example.invalid/pr/3\\n'\n"
        'elif [ "$1 $2" = "pr edit" ]; then exit 0\n'
        "else exit 7; fi\n"
    )
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", str(tools) + ":" + os.environ["PATH"])
    return root, origin, log


def test_publish_is_result_only_idempotent_and_preserves_source_branch(modules, reports, publication_repo):
    _, report = modules
    root, _origin, log = publication_repo
    source_head = git(root, "rev-parse", "HEAD")
    assert report.publish(reports, "export-test", root) == "https://example.invalid/pr/3"
    remote = git(root, "ls-remote", "origin", "refs/heads/results/export-test").split()[0]
    git(root, "fetch", "-q", "origin", "results/export-test")
    names = git(root, "diff", "--name-only", source_head, "FETCH_HEAD").splitlines()
    assert set(names) == {f"results/export-test/{name}" for name in report.EXPORTS}
    assert "Co-authored-by: Copilot" in git(root, "log", "-1", "--format=%B", "FETCH_HEAD")
    assert report.publish(reports, "export-test", root) == "https://example.invalid/pr/3"
    assert git(root, "ls-remote", "origin", "refs/heads/results/export-test").split()[0] == remote
    assert git(root, "rev-parse", "HEAD") == source_head
    assert git(root, "branch", "--show-current") == "feat/test"
    assert not git(root, "status", "--porcelain")
    calls = log.read_text()
    assert calls.count("pr create") == 1 and calls.count("pr edit") == 1
    assert "--base feat/test" in calls and "--force" not in calls
    assert git(root, "worktree", "list", "--porcelain").count("worktree ") == 1


def test_publish_auth_and_push_failures_are_explicit(modules, reports, publication_repo, monkeypatch):
    study, report = modules
    root, _, _ = publication_repo
    original = report.command

    def fail_auth(args, **kwargs):
        if args[:3] == ["gh", "auth", "status"]:
            raise study.StudyError("gh authentication unavailable")
        return original(args, **kwargs)

    monkeypatch.setattr(report, "command", fail_auth)
    with pytest.raises(study.StudyError, match="authentication"):
        report.publish(reports, "export-test", root)
    monkeypatch.setattr(report, "command", original)
    # A local rejecting hook exercises a real non-force push failure.
    hook = publication_repo[1] / "hooks/pre-receive"
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    with pytest.raises(study.StudyError, match="git failed"):
        report.publish(reports, "export-test", root)
    assert git(root, "worktree", "list", "--porcelain").count("worktree ") == 1


def test_pilot_intervals_are_exported_without_h7_claims(modules, reports, monkeypatch):
    study, report = modules
    state = study.read_json(reports.parent / "state.json")
    summary = study.read_json(reports / "summary.json")
    summary["endpoints"] = {"H1": {"B-A": {"ci": [None, 1.0]}, "B-C": {"ci": [-2.0, None]}}}
    monkeypatch.setattr(report, "analyze_pilot", lambda *args, **kwargs: summary)

    report.export(reports.parent, state, "export-test")

    with (reports / "intervals.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert {row["field"]: (row["value"], row["available"]) for row in rows} == {
        "B-A.ci.0": ("", "False"),
        "B-A.ci.1": ("1.0", "True"),
        "B-C.ci.0": ("-2.0", "True"),
        "B-C.ci.1": ("", "False"),
    }


def test_publish_refuses_remote_results_branch_with_source_commits(modules, reports, publication_repo):
    _, report = modules
    root, _origin, _log = publication_repo
    git(root, "checkout", "-q", "-b", "results/export-test")
    (root / "extra.txt").write_text("source change\n")
    git(root, "add", "extra.txt")
    git(root, "commit", "-qm", "inherited source commit")
    git(root, "push", "-q", "origin", "results/export-test")
    git(root, "checkout", "-q", "feat/test")
    with pytest.raises(modules[0].StudyError, match="outside result-only boundary"):
        report.publish(reports, "export-test", root)


def test_export_includes_model_column_without_inferring_historical_identity(modules, reports):
    """Smoke/diagnostic runs carry no assigned identity; model/replicate columns stay blank, never inferred."""
    for name in ("runs.csv", "series.csv", "retention.csv", "episodes.csv"):
        with (reports / name).open() as stream:
            reader = csv.DictReader(stream)
            assert "model" in reader.fieldnames and "replicate" in reader.fieldnames
            rows = list(reader)
        assert all(row["model"] == "" and row["replicate"] == "" for row in rows)


def _model_stratified_record(kind, k, cr=None):
    hidden = {"t1": "passed"}
    if cr is not None:
        hidden["cr1"] = cr
    return {"kind": kind, "k": k, "measure": {"hidden": hidden, "hidden_total": len(hidden),
            "hidden_passed": sum(value == "passed" for value in hidden.values())},
            "agent": {"seconds": 1, "usage": {"credits_complete": True, "totalNanoAiu": 1000000000}}}


def _model_stratified_raw(arm, model="claude-sonnet-5.5", replicate=1):
    records = [_model_stratified_record("feature", 1)]
    if arm != "A":
        records.append(_model_stratified_record("consolidation" if arm == "B" else "review", 1))
    records.append(_model_stratified_record("change_request", 1, cr="passed"))
    return {"dir": "", "meta": {"arm": arm, "features": 1, "run_id": f"{model}-{arm}-{replicate}",
            "suite": "synthetic", "phase": "pilot-estimation", "change_request": True,
            "assigned_model": model, "analysis_design": "model-stratified-v1", "replicate": replicate,
            "intervention": {"coverage_complete": True, "assisted": False, "evidence": "fixture"}},
            "recs": records}


def test_write_pilot_flattens_model_stratified_endpoints_into_csv(modules, tmp_path):
    _, report = modules
    pilot = importlib.import_module("pilot_analysis")
    panel = {"suite": "synthetic", "review": {"accepted": True, "evidence": "synthetic review"},
             "contracts": [{"id": "t1", "feature": "f1", "role": "feature", "from_cycle": 1,
                           "through_cycle": 1, "unchanged": True, "oracle_version": "v1"},
                          {"id": "cr1", "feature": "f1", "role": "cr1", "from_cycle": 2,
                           "through_cycle": 2, "unchanged": True, "oracle_version": "v1"}]}
    runs = [_model_stratified_raw(arm) for arm in "ABC"]
    result = pilot.analyze_pilot(runs, panel=panel, n=50)
    report.write_pilot(tmp_path, result)
    with (tmp_path / "hypotheses.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert any(row["hypothesis"] == "claude-sonnet-5.5" and row["field"].startswith("H1.") for row in rows)
    assert "## All run values and dispositions" in (tmp_path / "report.md").read_text()
    assert "claude-sonnet-5.5" in (tmp_path / "report.md").read_text()


def test_historical_and_diagnostic_designs_are_explicit_in_rendered_outputs(modules, tmp_path):
    _, report = modules
    pilot = importlib.import_module("pilot_analysis")
    for phase, label in (("pilot-estimation", "Historical"), ("dry", "Unassigned diagnostic")):
        runs = [_model_stratified_raw(arm) for arm in "ABC"]
        for run in runs:
            for key in ("assigned_model", "analysis_design", "replicate"):
                del run["meta"][key]
            run["meta"]["phase"] = phase
        result = pilot.analyze_pilot(runs, n=50)
        assert "frame" not in result and result["design_description"].startswith(label)
        assert all(run["assigned_model"] is None for run in result["runs"])
        directory = tmp_path / phase
        report.write_pilot(directory, result)
        for name in ("summary.json", "summary.md", "report.md", "hypotheses.tex"):
            assert label in (directory / name).read_text()
        assert ("STUB DIAGNOSTIC" in (directory / "report.md").read_text()) == (phase == "dry")
        del result["design_description"]
        result["methods"].pop("design", None)
        report.write_pilot(directory, result)
        for name in ("summary.json", "summary.md", "report.md", "hypotheses.tex"):
            assert label in (directory / name).read_text()
