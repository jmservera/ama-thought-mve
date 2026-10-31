import ctypes
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

for name in ("pyexpat", "_elementtree"):
    assert importlib.util.find_spec(name) is None, f"Expat parser module still present: {name}"
for name in ("libexpat.so", "libexpat.so.1", "/usr/lib/libexpat.so.1.13.0"):
    try:
        ctypes.CDLL(name)
    except OSError:
        pass
    else:
        raise AssertionError(f"Expat shared parser still loadable: {name}")

assert sys.version_info[:3] == (3, 12, 16)
assert importlib.util.find_spec("pip") is None
origins = {
    line[2:] for line in Path("/lib/apk/db/installed").read_text().splitlines()
    if line.startswith("o:")
}
assert "musl" in origins
assert not origins.intersection(("acl", "perl", "tar", "dash", "alpine-sdk", "expat", "mve-python-xml"))
assert not Path("/home/builder").exists()
assert not Path("/usr/lib/mve-python-xml").exists()
applets = subprocess.check_output(["/bin/busybox", "--list"], text=True).splitlines()
removed = ("ar", "cpio", "dpkg", "dpkg-deb", "rpm", "rpm2cpio", "tar", "unzip")
for name in removed:
    assert name not in applets and shutil.which(name) is None, name
    result = subprocess.run(
        ["/bin/busybox", name], capture_output=True, text=True, check=False,
    )
    assert result.returncode != 0 and "applet not found" in result.stderr, name
subprocess.run(
    ["/bin/busybox", "ash", "-c", "test mve = mve"], check=True,
)
date = subprocess.check_output(
    ["/bin/busybox", "date", "-u", "-d", "1999-1-2 3:4:5Z", "+%Y-%m-%d %H:%M:%S"],
    text=True,
).strip()
assert date == "1999-01-02 03:04:05", date
packages = {
    "git": "2.54.0-r100", "git-init-template": "2.54.0-r100",
    "busybox": "1.37.0-r100", "busybox-binsh": "1.37.0-r100",
    "ssl_client": "1.37.0-r100",
}
installed = {}
for entry in Path("/lib/apk/db/installed").read_text().split("\n\n"):
    fields = dict(line.split(":", 1) for line in entry.splitlines() if line[:2] in ("P:", "V:"))
    if "P" in fields:
        installed[fields["P"]] = fields["V"]
for name, version in packages.items():
    assert installed.get(name) == version, (name, installed.get(name), version)
assert not set(installed).intersection(("expat", "libexpat", "expat-dev", "mve-python-xml"))
assert "so:libexpat" not in Path("/lib/apk/db/installed").read_text()


def loader_image(data):
    header = struct.unpack_from("<16sHHIQQQIHHHHHH", data)
    assert header[0][:6] == b"\x7fELF\x02\x01" and header[9] == 56
    normalized = bytearray(data)
    normalized[40:48] = bytes(8)
    normalized[58:64] = bytes(6)
    programs = data[header[5]:header[5] + header[9] * header[10]]
    segments = []
    for index in range(header[10]):
        program = struct.unpack_from("<IIQQQQQQ", programs, index * header[9])
        if program[0] == 1:
            offset, length = program[2], program[5]
            assert offset + length <= len(data)
            segments.append(hashlib.sha256(normalized[offset:offset + length]).hexdigest())
    assert segments
    return {"header": hashlib.sha256(normalized[:64]).hexdigest(),
            "programs": hashlib.sha256(programs).hexdigest(), "segments": segments}


git_proof = json.loads(Path("/usr/share/mve-security/git-no-expat-proof.json").read_text())
assert git_proof["no_expat_option"] and git_proof["upstream_test_totals"]["failed"] == 0
git_executables = {}
for name, expected in git_proof["executables"].items():
    path = Path("/usr/bin/git") if name == "git" else Path("/usr/libexec/git-core") / name
    data = path.read_bytes()
    assert loader_image(data) == expected["loader_image"], f"Checked/installed Git load image differs: {name}"
    git_executables[name] = {"path": str(path), "installed_sha256": hashlib.sha256(data).hexdigest(),
                             "checked_loader_image_identical": True}
assert not Path("/usr/libexec/git-core/git-http-push").exists()

elf_files, links = {}, {}
for directory, directories, files in os.walk("/"):
    if directory == "/":
        directories[:] = [name for name in directories if name not in ("proc", "sys", "dev")]
    for name in directories + files:
        path = Path(directory) / name
        assert not (name.startswith("libexpat") or
                    (name.startswith(("pyexpat", "_elementtree")) and name.endswith(".so"))), path
        if path.is_symlink():
            links[str(path)] = str(path.resolve())
    for name in files:
        path = Path(directory) / name
        if path.is_symlink() or not path.is_file():
            continue
        with path.open("rb") as stream:
            prefix = stream.read(8)
            if not (prefix.startswith(b"\x7fELF") or prefix == b"!<arch>\n"):
                continue
            data = prefix + stream.read()
        assert all(marker not in data for marker in
                   (b"XML_ParserCreate", b"pyexpat.expat_CAPI", b"libexpat.so")), path
        elf_files[str(path)] = hashlib.sha256(data).hexdigest()
assert elf_files
assert not any("libexpat" in line for line in Path("/proc/self/maps").read_text().splitlines())

for name, version in (("pytest", "9.1.1"), ("pytest-timeout", "2.4.0"), ("lizard", "1.24.3")):
    assert importlib.metadata.version(name) == version
assert subprocess.check_output(["ruff", "--version"], text=True).strip() == "ruff 0.17.3"
assert subprocess.check_output(["node", "--version"], text=True).strip() == "v24.22.2"
assert subprocess.check_output(
    ["node", "/usr/local/lib/node_modules/jscpd/run-jscpd.js", "--version"], text=True,
).strip() == "jscpd 5.4.1"
with tempfile.TemporaryDirectory(prefix="mve-git-proof-") as temporary:
    repo = Path(temporary) / "repo"
    repo.mkdir()
    env = {"PATH": "/usr/local/bin:/usr/bin:/bin", "HOME": temporary, "LC_ALL": "C"}

    def git(*arguments):
        return subprocess.check_output(["git", "-C", str(repo), *arguments], env=env, text=True)

    git("init", "-q")
    git("config", "user.name", "Offline runtime proof")
    git("config", "user.email", "proof@example.invalid")
    (repo / "src.py").write_text("VALUE = 1\n")
    git("add", "src.py")
    git("commit", "-qm", "offline proof")
    head = git("rev-parse", "HEAD").strip()
    (repo / "src.py").write_text("VALUE = 2\n")
    assert git("diff", "--numstat", "HEAD").strip() == "1\t1\tsrc.py"
    (repo / "src.py").write_text("VALUE = 1\n")
    assert git("status", "--porcelain") == ""
    bundle = Path(temporary) / "proof.bundle"
    git("bundle", "create", str(bundle), "HEAD")
    git("bundle", "verify", str(bundle))
    subprocess.run(["git", "clone", "-q", str(bundle), str(Path(temporary) / "clone")],
                   env=env, check=True)
    assert subprocess.check_output(
        ["git", "-C", str(Path(temporary) / "clone"), "rev-parse", "HEAD"], env=env, text=True,
    ).strip() == head
    archive = subprocess.check_output(["git", "-C", str(repo), "archive", "HEAD"], env=env)
    assert len(archive) > 0

record = {
    "scope": "Supplied active merged runtime, package/ELF closure and installed checked-code binding; not historical layers, host binaries or arbitrary candidate-supplied code",
    "packages": packages,
    "expat_module_imports_unavailable": True,
    "direct_expat_library_loading_unavailable": True,
    "expat_packages_and_providers_absent": True,
    "git_installed_executables": git_executables,
    "git_webdav_helper_absent": True,
    "required_local_git_operations_passed": True,
    "pinned_metric_tool_versions_preserved": True,
    "active_elf_and_archive_sha256": elf_files,
    "active_symlink_targets": links,
    "busybox_installed_sha256": hashlib.sha256(Path("/bin/busybox").read_bytes()).hexdigest(),
    "removed_archive_consumers": removed,
    "ash_preserved": True,
    "date_utc_literal_preserved": date,
    "build_proof_hash_phase": "Component build proofs precede standard APK stripping; use installed hashes here",
    "compatibility_loss": "Container Expat-backed XML APIs and Git dumb HTTP/WebDAV push",
    "general_candidate_resource_exhaustion_not_eliminated": True,
}
print(json.dumps(record, indent=2))
