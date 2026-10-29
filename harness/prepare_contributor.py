"""Package a private, relocatable operator checkout, not an OSF attachment."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
import os
import re
import subprocess
import tarfile
from pathlib import Path, PurePosixPath

from study import fingerprint
from study_io import ROOT, StudyError, atomic_json
from study_report import check_credentials

REGISTERED_COMMIT = "763945bce239529b6a3e802e50dc7cf61c2736cf"
REGISTRATION_URL = "https://osf.io/ywsrv/"
REPOSITORY_URL = "https://github.com/jmservera/ama-thought-mve.git"
HANDOFF = """# Contributor source/setup package

This is a trusted-operator package, NOT the original OSF attachment and NOT an
agent workspace. `source/` contains the complete committed source, including
hidden tests/reference solutions, dependency manifests, and a shallow Git
checkout at the exact source commit. No private study outputs, tokens, local
environments or session history are copied. Public historical derived smoke
results and previously published development notes remain part of the tracked
checkout, but are not registered study data. Ignored current-session evidence
is never copied.

Verify the external archive checksum before extraction. `manifest.json` binds
every packaged file. From `source/`, start with `CONTRIBUTOR.md` and the dated
prospective clarification in `protocol/prospective-corrections-2026-10-28.md`.
The original approved registration is https://osf.io/ywsrv/; the corrected
candidate still needs its prospective OSF update and source-bound acceptance.

Offline checks (Python 3.11+, git, make):

    python3 harness/prepare_contributor.py --verify ../PACKAGE.tar.gz
    ./run-study.sh --smoke --dry-run
    ./run-study.sh --smoke --study-id contributor-check

The archive path in the first command is illustrative; use its actual location.
Smoke spends zero model credits. The owner accepts soft-credit-limit overshoot
risk: settings are buffered to 270/session and 270000 local admission, not
guaranteed billed limits. The reported company 1M/collaborator hard cap is not
independently verified. See CONTRIBUTOR.md before any authorized paid work.
Paid execution remains disabled: the isolated live backend is not implemented;
no budget receipt, package, licence assertion or freeze file alone enables it.
Never expose this operator checkout, its archive or `.git` to a study model.
"""


def git(root: Path, *args: str) -> str:
    """Run local Git without personal global config, hooks or credential helpers."""
    env = dict(os.environ, GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull)
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
                 "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_CONFIG_COUNT"):
        env.pop(name, None)
    try:
        result = subprocess.run(
            ["git", "-c", "core.hooksPath=" + os.devnull, *args], cwd=root,
            env=env, capture_output=True, text=True, timeout=120, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise StudyError("Local contributor-source Git operation unavailable") from error
    if result.returncode:
        raise StudyError("Local contributor-source Git operation failed; inspect privately")
    return result.stdout.strip()


def source_files(root: Path) -> list[Path]:
    """Reject sensitive or nonregular tracked payloads before copying any objects."""
    paths = []
    for record in git(root, "ls-files", "-s", "-z").split("\0"):
        if not record:
            continue
        metadata, relative = record.split("\t", 1)
        path = PurePosixPath(relative)
        if (metadata.split()[0] not in ("100644", "100755")
                or path.is_absolute() or ".." in path.parts
                or any(part in (".study", ".venv", "__pycache__")
                       or part.startswith(".env") for part in path.parts)
                or path.parts[0].startswith("runs")
                or path.suffix in (".log", ".jsonl", ".gz", ".zip")):
            raise StudyError("Tracked private, linked or raw-session material is not a contributor source input")
        source = root / relative
        if not source.is_file() or source.is_symlink() or source.stat().st_size > 8 * 1024 * 1024:
            raise StudyError("Contributor source must be bounded regular files")
        check_credentials(source.read_bytes().decode("utf-8", errors="replace"))
        paths.append(source)
    if not paths:
        raise StudyError("No tracked contributor source files")
    return paths


def file_inventory(directory: Path) -> dict:
    """Hash bytes and executable bits, including the portable Git object database."""
    inventory = {}
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            raise StudyError("Contributor package must not contain symlinks")
        if path.is_file():
            inventory[path.relative_to(directory).as_posix()] = {
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "executable": bool(path.stat().st_mode & 0o111),
            }
    return inventory


def verify(archive: Path) -> dict:
    """Verify inventory and safe private members without extracting the archive."""
    with tarfile.open(archive, "r:gz") as stream:
        members = stream.getmembers()
        names = [member.name for member in members]
        if len(set(names)) != len(names) or not names:
            raise StudyError("Contributor archive has duplicate or missing members")
        roots = {PurePosixPath(name).parts[0] for name in names}
        if len(roots) != 1:
            raise StudyError("Contributor archive must have exactly one package root")
        root = roots.pop()
        for member in members:
            path = PurePosixPath(member.name)
            if (path.is_absolute() or ".." in path.parts
                    or not (member.isfile() or member.isdir())
                    or member.mode & 0o077):
                raise StudyError("Contributor archive contains unsafe or nonprivate members")
        manifest_name = f"{root}/manifest.json"
        manifest_member = stream.extractfile(manifest_name)
        if manifest_member is None:
            raise StudyError("Contributor manifest missing")
        manifest = json.load(manifest_member)
        expected = manifest.get("files")
        if not isinstance(expected, dict):
            raise StudyError("Contributor manifest inventory missing")
        actual = {}
        for member in members:
            if not member.isfile() or member.name == manifest_name:
                continue
            payload = stream.extractfile(member)
            if payload is None:
                raise StudyError("Contributor archive file unreadable")
            actual[member.name.removeprefix(root + "/")] = {
                "sha256": hashlib.sha256(payload.read()).hexdigest(),
                "executable": bool(member.mode & 0o111),
            }
        if actual != expected:
            raise StudyError("Contributor archive bytes or executable modes differ from manifest")
        return manifest


def prepare(out: Path, root: Path = ROOT) -> dict:
    """Copy one clean committed checkout; never include private .study inputs."""
    root = root.resolve()
    destination = out.absolute()
    base = root / ".study"
    if (destination.resolve() == base or not destination.resolve().is_relative_to(base)
            or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,100}", destination.name)
            or any(path.is_symlink() for path in (destination, *destination.parents)
                   if path.is_relative_to(base))):
        raise StudyError("Choose a new non-symlinked contributor directory under .study")
    archive = destination.with_name(destination.name + ".tar.gz")
    checksum = archive.with_name(archive.name + ".sha256")
    if any(path.exists() for path in (destination, archive, checksum)):
        raise StudyError("Contributor output exists; preserve evidence and choose a new name")
    if git(root, "status", "--porcelain", "--untracked-files=normal"):
        raise StudyError("Commit the complete candidate before packaging contributor source")
    originals = source_files(root)
    commit = git(root, "rev-parse", "HEAD")
    destination.mkdir(parents=True, mode=0o700)
    checkout = destination / "source"
    git(root, "clone", "--quiet", "--depth", "1", "--single-branch",
        "--config", "core.logAllRefUpdates=false", "--config", "init.templateDir=",
        root.as_uri(), str(checkout))
    git(checkout, "remote", "set-url", "origin", REPOSITORY_URL)
    fetch_head = checkout / ".git/FETCH_HEAD"
    if fetch_head.exists():
        fetch_head.unlink()
    if git(checkout, "rev-parse", "HEAD") != commit or git(checkout, "status", "--porcelain"):
        raise StudyError("Copied contributor checkout does not match the clean candidate")
    for original in originals:
        copied = checkout / original.relative_to(root)
        if (copied.read_bytes() != original.read_bytes()
                or bool(copied.stat().st_mode & 0o111) != bool(original.stat().st_mode & 0o111)):
            raise StudyError("Copied contributor source differs from the committed candidate")
    handoff = destination / "README.md"
    handoff.write_text(HANDOFF, encoding="utf-8")
    for path in [destination, *destination.rglob("*")]:
        if path.is_symlink():
            raise StudyError("Contributor checkout unexpectedly contains symlinks")
        path.chmod(0o700 if path.is_dir() or path.stat().st_mode & 0o111 else 0o600)
    manifest = {
        "schema_version": 1, "source_commit": commit, "source_repository": REPOSITORY_URL,
        "source_inputs_sha256": fingerprint(root),
        "registered_source_commit": REGISTERED_COMMIT, "registration_url": REGISTRATION_URL,
        "registration_status": "Owner-confirmed original approval; candidate changes not published by this tool",
        "audience": "trusted operator only; contains hidden evaluator and reference material",
        "git_history": "shallow exact-commit checkout, no personal Git configuration or prior commit history",
        "private_run_data_included": False, "paid_execution_ready": False,
        "files": file_inventory(destination),
    }
    atomic_json(destination / "manifest.json", manifest)
    with archive.open("xb") as output:
        os.chmod(archive, 0o600)
        with (gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed,
              tarfile.open(fileobj=compressed, mode="w") as stream):
            for path in [destination, *sorted(destination.rglob("*"))]:
                info = stream.gettarinfo(str(path), arcname=path.relative_to(destination.parent).as_posix())
                info.uid = info.gid = info.mtime = 0
                info.uname = info.gname = ""
                stream.addfile(info, io.BytesIO(path.read_bytes()) if path.is_file() else None)
    verified = verify(archive)
    if verified != manifest:
        raise StudyError("Contributor archive failed its final manifest check")
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    with checksum.open("x", encoding="utf-8") as output:
        os.chmod(checksum, 0o600)
        output.write(f"{digest}  {archive.name}\n")
    return {"archive": str(archive.relative_to(root)), "sha256": digest,
            "source_commit": commit, "tracked_source_files": len(originals),
            "packaged_files": len(manifest["files"]) + 1, "paid_execution_ready": False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--out", type=Path)
    mode.add_argument("--verify", type=Path)
    args = parser.parse_args()
    result = verify(args.verify) if args.verify else prepare(args.out)
    if args.verify:
        result = {key: result[key] for key in ("source_commit", "paid_execution_ready")}
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (StudyError, OSError, ValueError, KeyError, tarfile.TarError) as error:
        message = str(error) if isinstance(error, StudyError) else type(error).__name__
        print(f"Contributor package stopped: {message}")
        raise SystemExit(2)
