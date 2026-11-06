"""Install separate build-stage public keys without replacing trusted keys."""

import sys
from pathlib import Path


def install_signing_keys(destination: Path, sources: list[Path]) -> None:
    if not destination.is_dir() or destination.is_symlink():
        raise ValueError(f"Trusted key directory unavailable: {destination}")
    pending = {}
    for source in sources:
        keys = sorted(source.glob("*.rsa.pub"))
        if not keys:
            raise ValueError(f"No public signing keys in {source}")
        for key in keys:
            if key.is_symlink() or not key.is_file():
                raise ValueError(f"Invalid public signing key: {key}")
            content = key.read_bytes()
            if not content:
                raise ValueError(f"Empty public signing key: {key}")
            if key.name in pending and pending[key.name] != content:
                raise ValueError(f"Conflicting public signing key: {key.name}")
            pending[key.name] = content

    for name, content in pending.items():
        target = destination / name
        if target.is_symlink():
            raise ValueError(f"Trusted key is a symlink: {target}")
        if target.exists() and (not target.is_file() or target.read_bytes() != content):
            raise ValueError(f"Conflicting trusted signing key: {target}")
    for name, content in pending.items():
        target = destination / name
        if not target.exists():
            target.write_bytes(content)
            target.chmod(0o644)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("Usage: install-signing-keys.py DESTINATION GIT_KEYS BUSYBOX_KEYS")
    install_signing_keys(Path(sys.argv[1]), [Path(path) for path in sys.argv[2:]])
