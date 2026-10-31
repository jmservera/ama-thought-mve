import hashlib
import json
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
recipe = root / "APKBUILD"
original = recipe.read_text()
assert hashlib.sha256(original.encode()).hexdigest() == "af43f6de15a7de1402a4ae17ea5fc8cde5383897f1c01dfd890ad24af3b3138e"
assert "pkgver=2.54.0\npkgrel=0\n" in original
checksums = re.search(r'sha512sums="\n(.*?)\n"', original, re.DOTALL).group(1)
for expected, name in re.findall(r"^([0-9a-f]{128})  (\S+)$", checksums, re.MULTILINE):
    if name != "git-2.54.0.tar.xz":
        assert hashlib.sha512((root / name).read_bytes()).hexdigest() == expected, name
updated = original.replace("pkgrel=0\n", "pkgrel=100\n", 1)
assert updated.count("\texpat-dev\n") == 1
updated = updated.replace("\texpat-dev\n", "")
marker = "\t\tNO_GETTEXT=YesPlease\n"
assert updated.count(marker) == 1
updated = updated.replace(marker, marker + "\t\tNO_EXPAT=YesPlease\n")
check = '''check() {
\tmake -C t prefix=/usr DESTDIR="$pkgdir" \\
\t\tperlibdir="$(_perl_config vendorlib)" \\
\t\tall
}'''
assert updated.count(check) == 1
updated = updated.replace(check, check.replace(
    "\tmake -C t", "\tlocal result=0\n\tmkdir -p /evidence/git\n\tmake -C t",
).replace("\t\tall\n}", '''\t\tall > /evidence/git/vendor-check.log 2>&1 || result=$?
\tcat /evidence/git/vendor-check.log
\treturn "$result"
}'''))
marker = "package() {\n"
assert updated.count(marker) == 1
updated = updated.replace(marker, marker + '\tpython3 /build/tools/verify-git.py /evidence/git "$builddir"\n')
recipe.write_text(updated)
(root / "mve-source-provenance.json").write_text(json.dumps({
    "vendor_recipe_sha256": hashlib.sha256(original.encode()).hexdigest(),
    "local_recipe_sha256": hashlib.sha256(updated.encode()).hexdigest(),
    "original_sha512sums": checksums,
    "persistent_option": "NO_EXPAT=YesPlease",
    "upstream_check_command_and_assertions_unchanged": True,
    "check_instrumentation": "Retain complete stdout/stderr and exact exit status before upstream cleanup removes per-script count files",
    "local_revision_not_unrelated_security_fixes": True,
}, indent=2) + "\n")
