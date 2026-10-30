"""Contributor archives contain exact runnable source, never private session data."""
import hashlib
import importlib
import io
import json
import subprocess
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def packager(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / "harness"))
    return importlib.import_module("prepare_contributor")


@pytest.fixture
def source(tmp_path):
    repo = tmp_path / "original"
    repo.mkdir()
    (repo / ".gitignore").write_text(".study/\n.copilot-tracking/\n", encoding="utf-8")
    (repo / "source.py").write_text("print('offline source')\n", encoding="utf-8")
    (repo / ".copilot-tracking").mkdir()
    (repo / ".copilot-tracking/historical.md").write_text("Previously published note\n", encoding="utf-8")
    launcher = repo / "run-study.sh"
    launcher.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    launcher.chmod(0o755)
    for command in (
        ["git", "init", "-q"],
        ["git", "config", "user.name", "Fixture"],
        ["git", "config", "user.email", "fixture@example.invalid"],
        ["git", "add", "."],
        ["git", "add", "-f", ".copilot-tracking/historical.md"],
        ["git", "commit", "-qm", "source fixture"],
    ):
        subprocess.run(command, cwd=repo, check=True, capture_output=True)
    private = repo / ".study"
    private.mkdir(mode=0o700)
    (private / "private-session.log").write_text("must not travel", encoding="utf-8")
    (repo / ".copilot-tracking/private-session.md").write_text("must not travel", encoding="utf-8")
    return repo


def test_complete_source_is_private_verified_and_relocatable(packager, source, tmp_path):
    result = packager.prepare(source / ".study/contributor-test", source)
    archive = source / result["archive"]
    manifest = packager.verify(archive)
    assert manifest["private_run_data_included"] is False
    assert manifest["paid_execution_ready"] is False
    assert "source/source.py" in manifest["files"]
    assert "source/.copilot-tracking/historical.md" in manifest["files"]
    assert all("private-session" not in name for name in manifest["files"])
    assert archive.stat().st_mode & 0o077 == 0
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == result["sha256"]
    elsewhere = tmp_path / "relocated"
    elsewhere.mkdir()
    with tarfile.open(archive, "r:gz") as stream:
        stream.extractall(elsewhere, filter="data")
    checkout = elsewhere / "contributor-test/source"
    assert packager.git(checkout, "rev-parse", "HEAD") == result["source_commit"]
    assert packager.git(checkout, "status", "--porcelain") == ""
    assert packager.git(checkout, "remote", "get-url", "origin") == packager.REPOSITORY_URL
    assert (checkout / "run-study.sh").stat().st_mode & 0o100
    assert not list((checkout / ".git").rglob("*logs*"))
    with pytest.raises(packager.StudyError, match="exists"):
        packager.prepare(source / ".study/contributor-test", source)


def test_dirty_or_sensitive_tracked_source_is_refused_before_copying(packager, source):
    (source / "source.py").write_text("changed source\n", encoding="utf-8")
    with pytest.raises(packager.StudyError, match="Commit"):
        packager.prepare(source / ".study/dirty", source)
    subprocess.run(["git", "add", "."], cwd=source, check=True)
    subprocess.run(["git", "commit", "-qm", "source update"], cwd=source, check=True)
    (source / ".env").write_text("synthetic private setting\n", encoding="utf-8")
    subprocess.run(["git", "add", ".env"], cwd=source, check=True)
    subprocess.run(["git", "commit", "-qm", "synthetic bad input"], cwd=source, check=True)
    with pytest.raises(packager.StudyError, match="private"):
        packager.prepare(source / ".study/sensitive", source)
    assert not (source / ".study/dirty").exists()
    assert not (source / ".study/sensitive").exists()


@pytest.mark.parametrize("tamper", ["bytes", "mode", "traversal"])
def test_modified_or_unsafe_archive_is_not_accepted(packager, tmp_path, tamper):
    archive = tmp_path / "bad.tar.gz"
    manifest = {"files": {"source.py": {
        "sha256": hashlib.sha256(b"original").hexdigest(), "executable": False,
    }}}
    with tarfile.open(archive, "w:gz") as stream:
        for name, payload in (
            ("package/manifest.json", json.dumps(manifest).encode()),
            ("package/../source.py" if tamper == "traversal" else "package/source.py",
             b"changed" if tamper == "bytes" else b"original"),
        ):
            info = tarfile.TarInfo(name)
            info.size = len(payload)
            info.mode = 0o644 if tamper == "mode" else 0o600
            stream.addfile(info, io.BytesIO(payload))
    with pytest.raises(packager.StudyError):
        packager.verify(archive)
