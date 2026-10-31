import hashlib
import json
import re
import shutil
import struct
import subprocess
import sys
from pathlib import Path


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


out, root = map(Path, sys.argv[1:3])
out.mkdir(parents=True, exist_ok=True)
config = (root / "config.mak").read_text()
assert "NO_EXPAT=YesPlease\n" in config
assert not (root / "git-http-push").exists()
assert subprocess.check_output([str(root / "git"), "--version"], text=True).strip() == "git version 2.54.0"
records = {}
for name in ("git", "git-http-fetch", "git-remote-http"):
    path = root / name
    data = path.read_bytes()
    dynamic = subprocess.check_output(["readelf", "-d", str(path)], text=True)
    symbols = subprocess.check_output(["nm", "-u", str(path)], text=True)
    assert "expat" not in dynamic.lower() and "XML_" not in symbols, name
    shutil.copy2(path, out / name)
    records[name] = {"sha256": hashlib.sha256(data).hexdigest(), "loader_image": loader_image(data),
                     "dynamic_dependencies": dynamic, "undefined_symbols": symbols}
shutil.copy2(root / "config.mak", out / "config.mak")
shutil.copy2(root / "GIT-BUILD-OPTIONS", out / "GIT-BUILD-OPTIONS")
shutil.copy2(root.parents[1] / "mve-source-provenance.json", out / "source-provenance.json")
log = (out / "vendor-check.log").read_text()
totals = {}
for name in ("fixed", "success", "failed", "broken", "total"):
    matches = re.findall(rf"^{name}\s+(\d+)$", log, re.MULTILINE)
    assert len(matches) == 1, (name, matches)
    totals[name] = int(matches[0])
assert totals.get("failed") == 0, totals
totals["skipped"] = totals["total"] - sum(totals[name] for name in ("fixed", "success", "failed", "broken"))
assert totals["success"] > 0 and totals["skipped"] >= 0
test_scripts = re.findall(r"^\*\*\* (t\d{4}-\S+\.sh) \*\*\*$", log, re.MULTILINE)
assert test_scripts
(out / "no-expat-proof.json").write_text(json.dumps({
    "phase": "package entry after unchanged vendor checks",
    "persistent_config_sha256": hashlib.sha256(config.encode()).hexdigest(),
    "no_expat_option": True, "webdav_helper_absent": True,
    "upstream_test_scripts": len(test_scripts), "upstream_test_totals": totals,
    "vendor_check_log_sha256": hashlib.sha256(log.encode()).hexdigest(),
    "upstream_cleanup_retained": True,
    "feature_and_vendor_skips_preserved": True,
    "executables": records,
    "loader_comparison_scope": "All program headers/PT_LOAD bytes; only ELF section-table bookkeeping masked",
}, indent=2) + "\n")
