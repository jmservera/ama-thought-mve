"""Tests for preserving both APK build-stage signer keys."""

import importlib.util
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "security/alpine/install-signing-keys.py"
SPEC = importlib.util.spec_from_file_location("install_signing_keys", SCRIPT)
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


@pytest.fixture
def key_dirs(tmp_path):
    destination, git, busybox = (tmp_path / name for name in ("trusted", "git", "busybox"))
    for directory in (destination, git, busybox):
        directory.mkdir()
    return destination, git, busybox


def test_installs_both_keys_and_preserves_existing_keys(key_dirs):
    destination, git, busybox = key_dirs
    (destination / "alpine.rsa.pub").write_bytes(b"existing")
    (git / "-git.rsa.pub").write_bytes(b"git")
    (busybox / "-busybox.rsa.pub").write_bytes(b"busybox")

    installer.install_signing_keys(destination, [git, busybox])
    installer.install_signing_keys(destination, [git, busybox])

    assert (destination / "alpine.rsa.pub").read_bytes() == b"existing"
    assert (destination / "-git.rsa.pub").read_bytes() == b"git"
    assert (destination / "-busybox.rsa.pub").read_bytes() == b"busybox"
    assert (destination / "-git.rsa.pub").stat().st_mode & 0o777 == 0o644


def test_conflicting_signers_fail_before_installation(key_dirs):
    destination, git, busybox = key_dirs
    (git / "same.rsa.pub").write_bytes(b"git")
    (busybox / "same.rsa.pub").write_bytes(b"busybox")

    with pytest.raises(ValueError, match="Conflicting public signing key"):
        installer.install_signing_keys(destination, [git, busybox])
    assert not list(destination.iterdir())


def test_identical_key_names_and_contents_are_accepted(key_dirs):
    destination, git, busybox = key_dirs
    (git / "same.rsa.pub").write_bytes(b"shared")
    (busybox / "same.rsa.pub").write_bytes(b"shared")

    installer.install_signing_keys(destination, [git, busybox])

    assert (destination / "same.rsa.pub").read_bytes() == b"shared"


def test_conflicting_existing_trust_is_not_overwritten(key_dirs):
    destination, git, busybox = key_dirs
    (destination / "same.rsa.pub").write_bytes(b"trusted")
    (git / "same.rsa.pub").write_bytes(b"different")
    (busybox / "other.rsa.pub").write_bytes(b"busybox")

    with pytest.raises(ValueError, match="Conflicting trusted signing key"):
        installer.install_signing_keys(destination, [git, busybox])
    assert (destination / "same.rsa.pub").read_bytes() == b"trusted"
    assert not (destination / "other.rsa.pub").exists()


@pytest.mark.parametrize("invalid", ["missing", "empty", "symlink"])
def test_missing_or_invalid_stage_key_fails(key_dirs, tmp_path, invalid):
    destination, git, busybox = key_dirs
    (git / "git.rsa.pub").write_bytes(b"git")
    if invalid == "empty":
        (busybox / "busybox.rsa.pub").write_bytes(b"")
    elif invalid == "symlink":
        (busybox / "busybox.rsa.pub").symlink_to(tmp_path / "nonexistent")

    with pytest.raises(ValueError):
        installer.install_signing_keys(destination, [git, busybox])
    assert not list(destination.iterdir())
