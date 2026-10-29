"""Shared private state and trusted-tool boundaries for controller and reporting."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class StudyError(RuntimeError):
    """An explicit safety or execution stop, safe to display without raw logs."""


class RetryableError(RuntimeError):
    """An unmeasured infrastructure failure, never a measured task failure."""


def read_json(path: Path) -> dict:
    """Read an object rather than silently accepting malformed state."""
    with path.open(encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise StudyError(f"Expected JSON object: {path.name}")
    return value


def atomic_json(path: Path, value: dict) -> None:
    """Replace and fsync private state before allowing dependent work."""
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as stream:
        os.chmod(temp, 0o600)
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temp, path)
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def command(args: list[str], *, cwd: Path = ROOT, timeout: float = 60) -> str:
    """Bound trusted tooling without echoing raw stderr or credentials."""
    try:
        result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False)
    except subprocess.TimeoutExpired as error:
        raise StudyError(f"{Path(args[0]).name} check timed out") from error
    if result.returncode:
        raise StudyError(f"{Path(args[0]).name} failed (exit {result.returncode}); inspect privately")
    return result.stdout.strip()
