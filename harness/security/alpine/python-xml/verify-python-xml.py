import _elementtree
import hashlib
import json
import pyexpat
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve()
assert sys.version_info[:3] == (3, 12, 16)
assert not list((root / "Modules/expat").glob("*.o"))
modules = {}
for module in (pyexpat, _elementtree):
    binary = Path(module.__file__).resolve()
    assert binary.parent == root / "Modules", binary
    needed = subprocess.check_output(["readelf", "-d", str(binary)], text=True)
    if module is pyexpat:
        assert "Shared library: [libexpat.so.1]" in needed
    modules[module.__name__] = {
        "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "dynamic_section": needed,
    }
libraries = {
    line.split()[-1] for line in Path("/proc/self/maps").read_text().splitlines()
    if "/libexpat.so." in line
}
assert len(libraries) == 1, libraries
library = Path(libraries.pop())
record = {
    "python_version": list(sys.version_info[:3]),
    "source_sha256": "b5796915dc45ff745cfb4e990a7e7c93d6f546328a102ce31448d69ebc37575c",
    "scope": "Only pyexpat and _elementtree replaced; original interpreter retained",
    "modules": modules,
    "actual_loaded_expat": str(library),
    "actual_loaded_expat_sha256": hashlib.sha256(library.read_bytes()).hexdigest(),
    "bundled_expat_objects_compiled": False,
    "unfixed_scoped_exception": "CVE-2025-66382; conditional owner policy is not a claim of repair",
}
(root / "mve-python-xml-proof.json").write_text(json.dumps(record, indent=2) + "\n")
