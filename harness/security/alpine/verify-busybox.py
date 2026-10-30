import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
proofs = []
for argument in sys.argv[2:]:
    directory = Path(argument)
    config = (directory / ".config").read_text()
    for symbol in ("AR", "CPIO", "DPKG", "DPKG_DEB", "RPM", "RPM2CPIO", "TAR", "UNZIP"):
        assert f"# CONFIG_{symbol} is not set" in config, (directory, symbol)
    if directory.name != "build-dynamic-extras":
        assert "CONFIG_ASH=y" in config
    binary = directory / ("busybox.static" if directory.name == "build-static" else "busybox")
    unstripped = directory / "busybox_unstripped"
    link_map = directory / "mve-link.map"
    map_text = link_map.read_text()
    assert "Linker script and memory map" in map_text
    retained = map_text.split("Linker script and memory map", 1)[1]
    symbols = subprocess.check_output(["nm", "-a", str(unstripped)], text=True)
    for name in ("data_extract_all", "create_or_remember_link", "create_links_from_list"):
        assert name not in retained, (directory, "retained map", name)
        assert not any(line.split()[-1] == name for line in symbols.splitlines() if line.split())
    applets = subprocess.check_output([str(binary), "--list"], text=True).splitlines()
    for name in ("ar", "cpio", "dpkg", "dpkg-deb", "rpm", "rpm2cpio", "tar", "unzip"):
        assert name not in applets, (directory, name)
        result = subprocess.run([str(binary), name], check=False, capture_output=True, text=True)
        assert result.returncode != 0 and "applet not found" in result.stderr, (directory, name)
    target = out / directory.name
    target.mkdir(exist_ok=True)
    for source in (directory / ".config", binary, unstripped, link_map):
        shutil.copy2(source, target / source.name)
    proofs.append({
        "variant": directory.name,
        "config_sha256": hashlib.sha256(config.encode()).hexdigest(),
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "unstripped_sha256": hashlib.sha256(unstripped.read_bytes()).hexdigest(),
        "map_sha256": hashlib.sha256(link_map.read_bytes()).hexdigest(),
        "disabled_consumers": ["AR", "CPIO", "DPKG", "DPKG_DEB", "RPM", "RPM2CPIO", "TAR", "UNZIP"],
        "retained_map_and_unstripped_symbols_clear": True,
        "direct_applets_rejected": True,
    })
(out / "removal-proof.json").write_text(json.dumps({
    "scope": "Source-backed complete extraction-consumer closure, normalized configs, retained linker-map region, unstripped ELF symbols and actual applet dispatch",
    "variants": proofs,
    "not_merely_deleted_symlinks": True,
}, indent=2) + "\n")
