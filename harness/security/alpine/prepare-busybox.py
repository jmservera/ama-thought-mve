import hashlib
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
recipe = root / "APKBUILD"
original = recipe.read_text()
assert "pkgver=1.37.0\npkgrel=31\n" in original
checksums = re.search(r'sha512sums="\n(.*?)\n"', original, re.DOTALL).group(1)
for expected, name in re.findall(r"^([0-9a-f]{128})  (\S+)$", checksums, re.MULTILINE):
    if name != "busybox-1.37.0.tar.bz2":
        assert hashlib.sha512((root / name).read_bytes()).hexdigest() == expected, name
updated = original.replace("pkgrel=31\n", "pkgrel=100\n", 1)
changes = {}
for name in ("busyboxconfig", "busyboxconfig-extras"):
    path = root / name
    before = path.read_text()
    assert 'CONFIG_EXTRA_LDFLAGS=""' in before
    after = before.replace(
        'CONFIG_EXTRA_LDFLAGS=""', 'CONFIG_EXTRA_LDFLAGS="-Wl,-Map,mve-link.map"'
    )
    for symbol in ("TAR", "CPIO", "UNZIP"):
        enabled = f"CONFIG_{symbol}=y"
        disabled = f"# CONFIG_{symbol} is not set"
        assert enabled in after or disabled in after, (name, symbol)
        after = after.replace(enabled, disabled)
    if name == "busyboxconfig":
        assert "CONFIG_ASH=y" in after
    for symbol in ("AR", "DPKG", "DPKG_DEB", "RPM", "RPM2CPIO"):
        assert f"# CONFIG_{symbol} is not set" in after, (name, symbol)
    path.write_text(after)
    old = hashlib.sha512(before.encode()).hexdigest()
    new = hashlib.sha512(after.encode()).hexdigest()
    assert updated.count(f"{old}  {name}") == 1
    updated = updated.replace(f"{old}  {name}", f"{new}  {name}")
    changes[name] = {"vendor_sha512": old, "local_sha512": new}
package_start = "package() {\n\tlocal file\n"
assert updated.count(package_start) == 1
updated = updated.replace(
    package_start,
    package_start + '\tpython3 /build/tools/verify-busybox.py /evidence/busybox '
    '"$_dyndir" "$_dyndir_extras" "$_staticdir"\n',
)
local_patch = "mve-date-utc.txt"
local_digest = "66180a749d29db662ae5e877bd8af13fb9deb235854fb22ebbd19098ae5758dd5c6e0f0fc4fb5289579030544580b771b292bdd30e7e62586c25e18893bd6b27"
assert hashlib.sha512((root / local_patch).read_bytes()).hexdigest() == local_digest
source_end = '\t$_extras_openrc_files\n"'
assert updated.count(source_end) == 1
updated = updated.replace(source_end, '\t$_extras_openrc_files\n\t' + local_patch + '\n"')
updated = re.sub(
    r'(sha512sums="\n.*?)(\n")',
    lambda match: match[1] + f"\n{local_digest}  {local_patch}" + match[2],
    updated,
    count=1,
    flags=re.DOTALL,
)
prepare_call = "\tdefault_prepare\n"
assert updated.count(prepare_call) == 1
updated = updated.replace(
    prepare_call,
    prepare_call + '\tpatch --batch --forward --fuzz=0 -p1 -d "$builddir" '
    '-i "$srcdir/mve-date-utc.txt"\n',
)
recipe.write_text(updated)
(root / "mve-source-provenance.json").write_text(json.dumps({
    "vendor_commit": "c3ef5d10e6ef6528852c51f0564963e2f8c1be19",
    "vendor_recipe_sha256": hashlib.sha256(original.encode()).hexdigest(),
    "local_recipe_sha256": hashlib.sha256(updated.encode()).hexdigest(),
    "local_package_revision": 100,
    "config_changes": changes,
    "build_change": "Use stable config-owned linker maps and verify actual post-check package inputs; preserve all vendor check commands and its existing SKIP_KNOWN_BUGS policy",
    "test_assertions_modified": False,
    "additional_explicit_skip_flags": False,
    "feature_dependent_vendor_skips_retained": True,
    "local_compatibility_patch": {
        "source_artifact": "busybox-date-utc.patch.gz; losslessly encoded diff payload",
        "sha512": local_digest,
        "reason": "Unmodified date-timezone test exposes stock musl strptime not accepting UTC literal Z; add literal UTC formats without changing numeric offsets or test assertions",
        "stock_failure_reproduced": True,
        "application": "Separate forward-only fuzz0 patch after unchanged vendor patches",
    },
}, indent=2) + "\n")
