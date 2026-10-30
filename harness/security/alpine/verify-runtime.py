import _elementtree
import hashlib
import importlib.util
import json
import pyexpat
import shutil
import subprocess
import sys
from pathlib import Path

assert sys.version_info[:3] == (3, 12, 16)
assert importlib.util.find_spec("pip") is None
origins = {
    line[2:] for line in Path("/lib/apk/db/installed").read_text().splitlines()
    if line.startswith("o:")
}
assert "musl" in origins
assert not origins.intersection(("acl", "perl", "tar", "dash", "alpine-sdk"))
assert not Path("/home/builder").exists()
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
    "libexpat": "2.9.0-r100", "mve-python-xml": "3.12.16-r1",
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
modules = {}
for module in (pyexpat, _elementtree):
    link = Path(module.__file__)
    binary = link.resolve()
    assert link.is_symlink() and binary.parent == Path("/usr/lib/mve-python-xml")
    modules[module.__name__] = {
        "import_path": str(link),
        "resolved_path": str(binary),
        "installed_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
    }
libraries = {
    line.split()[-1] for line in Path("/proc/self/maps").read_text().splitlines()
    if "/libexpat.so." in line
}
assert libraries == {"/usr/lib/libexpat.so.1.13.0"}, libraries
library = Path(libraries.pop())
record = {
    "scope": "Actual final-image imports, installed hashes, package versions and command absence",
    "packages": packages,
    "modules": modules,
    "actual_loaded_expat": str(library),
    "actual_loaded_expat_sha256": hashlib.sha256(library.read_bytes()).hexdigest(),
    "busybox_installed_sha256": hashlib.sha256(Path("/bin/busybox").read_bytes()).hexdigest(),
    "removed_archive_consumers": removed,
    "ash_preserved": True,
    "date_utc_literal_preserved": date,
    "build_proof_hash_phase": "Component build proofs precede standard APK stripping; use installed hashes here",
    "unfixed_scoped_exception": "CVE-2025-66382; conditional policy only, not a repair or final owner image acceptance",
}
print(json.dumps(record, indent=2))
