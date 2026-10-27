"""Exact export-shape and local-only publication tests; no paid agent or GitHub calls."""
import csv
import importlib
import json
import os
import subprocess
import xml.etree.ElementTree as ET
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
    assert summary["hypotheses"]["H1"]["diff_points"] is None
    availability = study.read_json(reports / "availability.json")
    assert availability["zero_intervention_inferred"] is False
    assert {"H4", "H7", "HIR", "IDR", "mixed_effects", "decay_amendment"} <= availability["unavailable"].keys()
    with (reports / "runs.csv").open() as stream:
        rows = list(csv.DictReader(stream))
    assert len(rows) == 3 and all(row["status"] == "pending" for row in rows)
    assert all(row["unattempted_cycles"] == "1" and row["HIR"] == "" for row in rows)
    with (reports / "intervals.csv").open() as stream:
        intervals = list(csv.DictReader(stream))
    assert any(row["hypothesis"] == "H1" and row["field"] == "ci.0" for row in intervals)
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


def test_h7_intervals_are_exported(modules, reports, monkeypatch):
    study, report = modules
    state = study.read_json(reports.parent / "state.json")
    summary = study.read_json(reports / "summary.json")
    summary["hypotheses"]["H7"]["intervals"] = {"B_minus_A": [None, 1.0], "B_minus_C": [-2.0, None]}
    monkeypatch.setattr(report, "analyze_hypotheses", lambda *args, **kwargs: summary["hypotheses"])

    report.export(reports.parent, state, "export-test")

    with (reports / "intervals.csv").open() as stream:
        rows = [row for row in csv.DictReader(stream) if row["hypothesis"] == "H7"]
    assert {row["field"]: (row["value"], row["available"]) for row in rows} == {
        "intervals.B_minus_A.0": ("", "False"),
        "intervals.B_minus_A.1": ("1.0", "True"),
        "intervals.B_minus_C.0": ("-2.0", "True"),
        "intervals.B_minus_C.1": ("", "False"),
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
