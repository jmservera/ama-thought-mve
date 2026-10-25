"""TCR regressions using disposable fixtures and fake make/git commands."""

from contextlib import ExitStack
import os
from pathlib import Path
import select
import shutil
import subprocess

import pytest


TCR_HELPER = Path(__file__).resolve().parents[2] / "skeleton" / "tcr"


@pytest.fixture
def tcr_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    command_directory = tmp_path / "bin"
    command_directory.mkdir()
    (tmp_path / "logs").mkdir()
    for command in ("bash", "mktemp", "rm", "tail"):
        executable = shutil.which(command, path=os.defpath)
        assert executable is not None, command
        (command_directory / command).symlink_to(executable)

    for command, script in {
        "make": r'''#!/bin/bash
set -euo pipefail
if [[ -v TCR_PARENT_ONLY ]]; then exit 90; fi
printf 'make %s\n' "$*" >> "$CALLS"
printf '%s\n' "$TOKEN"
if [[ -n "${READY:-}" ]]; then
    printf '%s\n' "$TOKEN" > "$READY"
    IFS= read -r permission < "$RELEASE"
fi
if [[ "$FAIL_STAGE" == tests ]]; then exit 7; fi
exit 0
''',
        "git": r'''#!/bin/bash
set -euo pipefail
printf 'git %s\n' "$*" >> "$CALLS"
case "$1" in
  add) if [[ "$FAIL_STAGE" == staging ]]; then printf '%s staging\n' "$TOKEN" >&2; exit 8; fi ;;
  commit) if [[ "$FAIL_STAGE" == commit ]]; then printf '%s commit\n' "$TOKEN" >&2; exit 9; fi ;;
  reset) if [[ "$ROLLBACK_FAILURE" == reset ]]; then exit 10; fi ;;
  clean)
    [[ "$*" == 'clean -qfd -e reports/' ]] || exit 12
    if [[ "$ROLLBACK_FAILURE" == clean ]]; then exit 11; fi
    ;;
  *) exit 13 ;;
esac
exit 0
''',
    }.items():
        command_path = command_directory / command
        command_path.write_text(script, encoding="ascii")
        command_path.chmod(0o700)

    (tmp_path / "tcr").write_bytes(TCR_HELPER.read_bytes())
    monkeypatch.setenv("TCR_PARENT_ONLY", "not-for-child")
    return tmp_path


def _child_environment(workspace: Path, **overrides: str) -> dict[str, str]:
    return {
        "PATH": str(workspace / "bin"),
        "HOME": str(workspace),
        "LC_ALL": "C",
        "TMPDIR": str(workspace / "logs"),
        "CALLS": str(workspace / "calls"),
        "FAIL_STAGE": "",
        "ROLLBACK_FAILURE": "",
        "TOKEN": "isolated-diagnostic",
        **overrides,
    }


def _run_tcr(workspace: Path, **overrides: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(workspace / "bin" / "bash"), str(workspace / "tcr"), "fixture"],
        cwd=workspace,
        env=_child_environment(workspace, **overrides),
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def _reap(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.kill()
    process.communicate(timeout=10)


def test_given_success_when_run_then_commits_without_rollback(tcr_workspace: Path) -> None:
    result = _run_tcr(tcr_workspace)

    assert result.returncode == 0, result.stderr
    assert result.stdout == "TCR: committed\n"
    assert result.stderr == ""
    assert (tcr_workspace / "calls").read_text(encoding="ascii").splitlines() == [
        "make -s test",
        "git add -A",
        "git commit -q -m tcr: fixture",
    ]
    assert list((tcr_workspace / "logs").iterdir()) == []


@pytest.mark.parametrize(
    ("failure_stage", "expected_status", "expected_attempts"),
    [
        ("tests", 7, ["make -s test"]),
        ("staging", 8, ["make -s test", "git add -A"]),
        (
            "commit",
            9,
            ["make -s test", "git add -A", "git commit -q -m tcr: fixture"],
        ),
    ],
)
def test_given_stage_failure_when_run_then_rolls_back_and_cleans_log(
    tcr_workspace: Path,
    failure_stage: str,
    expected_status: int,
    expected_attempts: list[str],
) -> None:
    result = _run_tcr(tcr_workspace, FAIL_STAGE=failure_stage)

    assert result.returncode == expected_status, result.stderr
    assert result.stdout == ""
    assert f"TCR: {failure_stage} failed (exit {expected_status})" in result.stderr
    assert "isolated-diagnostic" in result.stderr
    assert "TCR: reverted" in result.stderr
    assert (tcr_workspace / "calls").read_text(encoding="ascii").splitlines() == (
        expected_attempts + ["git reset -q --hard", "git clean -qfd -e reports/"]
    )
    assert list((tcr_workspace / "logs").iterdir()) == []


@pytest.mark.parametrize("rollback_stage", ["reset", "clean"])
def test_given_rollback_failure_when_run_then_preserves_original_failure(
    tcr_workspace: Path, rollback_stage: str,
) -> None:
    result = _run_tcr(tcr_workspace, FAIL_STAGE="tests", ROLLBACK_FAILURE=rollback_stage)

    assert result.returncode == 7, result.stderr
    assert result.stdout == ""
    assert "TCR: tests failed (exit 7)" in result.stderr
    assert "TCR: rollback failed; inspect the worktree" in result.stderr
    assert "TCR: reverted" not in result.stderr
    expected_attempts = ["make -s test", "git reset -q --hard"]
    if rollback_stage == "clean":
        expected_attempts.append("git clean -qfd -e reports/")
    assert (tcr_workspace / "calls").read_text(encoding="ascii").splitlines() == expected_attempts
    assert list((tcr_workspace / "logs").iterdir()) == []


def test_given_parallel_fake_repositories_when_tests_fail_then_logs_are_unique_and_removed(
    tcr_workspace: Path,
) -> None:
    diagnostics = ("diagnostic-one", "diagnostic-two")
    processes = []
    release_descriptors = []
    with ExitStack() as cleanup:
        for diagnostic in diagnostics:
            repository = tcr_workspace / diagnostic
            repository.mkdir()
            ready = repository / "ready"
            release = repository / "release"
            os.mkfifo(ready)
            os.mkfifo(release)
            ready_descriptor = os.open(ready, os.O_RDWR | os.O_NONBLOCK)
            cleanup.callback(os.close, ready_descriptor)
            release_descriptor = os.open(release, os.O_RDWR | os.O_NONBLOCK)
            cleanup.callback(os.close, release_descriptor)
            process = subprocess.Popen(
                [str(tcr_workspace / "bin" / "bash"), str(tcr_workspace / "tcr")],
                cwd=repository,
                env=_child_environment(
                    tcr_workspace,
                    HOME=str(repository),
                    CALLS=str(repository / "calls"),
                    FAIL_STAGE="tests",
                    TOKEN=diagnostic,
                    READY=str(ready),
                    RELEASE=str(release),
                ),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            cleanup.callback(_reap, process)
            processes.append(process)
            release_descriptors.append(release_descriptor)
            assert select.select([ready_descriptor], [], [], 10)[0] == [ready_descriptor]
            assert os.read(ready_descriptor, 100).decode("ascii").strip() == diagnostic

        log_files = list((tcr_workspace / "logs").iterdir())
        assert len(log_files) == 2
        assert all(log_file.name.startswith("tcr.") for log_file in log_files)
        assert {log_file.read_text(encoding="ascii").strip() for log_file in log_files} == set(diagnostics)
        for release_descriptor in release_descriptors:
            os.write(release_descriptor, b"continue\n")

        for index, process in enumerate(processes):
            stdout, stderr = process.communicate(timeout=10)
            assert process.returncode == 7, stderr
            assert stdout == ""
            assert diagnostics[index] in stderr
            assert diagnostics[1 - index] not in stderr

    assert list((tcr_workspace / "logs").iterdir()) == []
