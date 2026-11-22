"""Automated build & packaging script for MaxHotbox (Autodesk 3ds Max 2026).

Generates inside `dist/`:
  1. MaxHotbox.bundle/                   — Standard Autodesk Application Plugin Package
  2. install.bat / uninstall.bat         — Double-click safe Windows installers
  3. Load_MaxHotbox_Now.ms               — Immediate live loader for already-open Max 2026
  4. MaxHotbox_v<ver>_Max2026.zip        — Standard release archive (bundle + installers + docs)
  5. MaxHotbox_v<ver>_Max2026.mzp        — Drag-and-drop / Run Script 3ds Max 2026 installer
"""

from __future__ import annotations

import ast
import hashlib
import shutil
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_PYTHON = PROJECT_ROOT / "src" / "max_hotbox"
SRC_MAXSCRIPT = PROJECT_ROOT / "src" / "maxscript"
PACKAGING_DIR = PROJECT_ROOT / "packaging"
DIST_DIR = PROJECT_ROOT / "dist"


def _read_plugin_meta() -> tuple[str, str, int]:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from max_hotbox.constants import PLUGIN_NAME, PLUGIN_VERSION, TARGET_MAX_VERSION

    return PLUGIN_NAME, PLUGIN_VERSION, TARGET_MAX_VERSION


def _ignore_junk(_dir: str, names: list[str]) -> set[str]:
    return {
        n
        for n in names
        if n == "__pycache__" or n.endswith(".pyc") or n.endswith(".pyo") or n == ".DS_Store"
    }


def _copy_with_utf8_bom(src: Path, dst: Path) -> None:
    """Copy a MAXScript (.ms / .mcr) or PowerShell (.ps1) file ensuring UTF-8 BOM.

    3ds Max MAXScript reads non-BOM files using system ANSI codepage (GBK on Chinese Windows),
    which breaks UTF-8 Chinese strings unless UTF-8 BOM (EF BB BF) is present.
    """
    text = src.read_text(encoding="utf-8-sig")
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(text, encoding="utf-8-sig", newline="\r\n")


def _ensure_source_boms() -> None:
    """Ensure all MAXScript and PowerShell source files carry UTF-8 BOM."""
    for path in (
        SRC_MAXSCRIPT / "MaxHotbox.mcr",
        SRC_MAXSCRIPT / "post_startup.ms",
        SRC_MAXSCRIPT / "uninstall_helper.ms",
        PACKAGING_DIR / "install_mzp.ms",
        PACKAGING_DIR / "Load_MaxHotbox_Now.ms",
        PACKAGING_DIR / "install.ps1",
        PACKAGING_DIR / "uninstall.ps1",
    ):
        if path.exists():
            text = path.read_text(encoding="utf-8-sig")
            path.write_text(text, encoding="utf-8-sig", newline="\r\n")


def _compile_check_python(py_root: Path) -> int:
    count = 0
    for py_file in sorted(py_root.rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        # Validate Python 3.11 syntax (Autodesk 3ds Max 2026 embedded Python)
        tree = ast.parse(source, filename=str(py_file), feature_version=(3, 11))
        compile(tree, str(py_file), "exec")
        count += 1
    return count


def _validate_package_xml(bundle_dir: Path, target_version: int) -> None:
    xml_path = bundle_dir / "PackageContents.xml"
    if not xml_path.exists():
        raise FileNotFoundError(f"Missing {xml_path}")

    tree = ET.parse(xml_path)
    root = tree.getroot()
    if root.tag != "ApplicationPackage":
        raise ValueError(f"Unexpected XML root tag: {root.tag}")

    reqs = root.findall(".//RuntimeRequirements")
    if not reqs:
        raise ValueError("No <RuntimeRequirements> found in PackageContents.xml")
    for req in reqs:
        if req.attrib.get("Platform") != "3ds Max":
            raise ValueError(f"Unexpected Platform: {req.attrib.get('Platform')}")
        if req.attrib.get("SeriesMin") != str(target_version) or req.attrib.get("SeriesMax") != str(target_version):
            raise ValueError(
                f"Expected SeriesMin/SeriesMax={target_version}, got {req.attrib}"
            )

    entries = root.findall(".//ComponentEntry")
    if not entries:
        raise ValueError("No <ComponentEntry> found in PackageContents.xml")
    for entry in entries:
        mod_rel = entry.attrib.get("ModuleName", "")
        if not mod_rel:
            raise ValueError("ComponentEntry missing ModuleName")
        target = (bundle_dir / mod_rel).resolve()
        if not target.exists():
            raise FileNotFoundError(f"PackageContents.xml references missing file: {mod_rel} -> {target}")


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _zip_directory(zf: zipfile.ZipFile, src_dir: Path, arc_prefix: str) -> None:
    for item in sorted(src_dir.rglob("*")):
        if item.is_file():
            rel = item.relative_to(src_dir).as_posix()
            zf.write(item, f"{arc_prefix}/{rel}")


def build() -> dict[str, Path]:
    _ensure_source_boms()
    plugin_name, version, max_ver = _read_plugin_meta()
    release_stem = f"{plugin_name}_v{version}_Max{max_ver}"

    bundle_dir = DIST_DIR / f"{plugin_name}.bundle"
    zip_path = DIST_DIR / f"{release_stem}.zip"
    mzp_path = DIST_DIR / f"{release_stem}.mzp"

    # 1. Clean previous dist artifacts
    DIST_DIR.mkdir(parents=True, exist_ok=True)
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)
    for pattern in (f"{plugin_name}_v*.zip", f"{plugin_name}_v*.mzp", f"{plugin_name}_v*_SHA256.txt"):
        for old_file in DIST_DIR.glob(pattern):
            old_file.unlink()

    # 2. Assemble MaxHotbox.bundle
    contents_dir = bundle_dir / "Contents"
    macro_dir = contents_dir / "macroscripts"
    scripts_dir = contents_dir / "scripts"
    python_dir = contents_dir / "python" / "max_hotbox"

    macro_dir.mkdir(parents=True, exist_ok=True)
    scripts_dir.mkdir(parents=True, exist_ok=True)

    shutil.copy2(PACKAGING_DIR / "PackageContents.xml", bundle_dir / "PackageContents.xml")
    _copy_with_utf8_bom(SRC_MAXSCRIPT / "MaxHotbox.mcr", macro_dir / "MaxHotbox.mcr")
    _copy_with_utf8_bom(SRC_MAXSCRIPT / "post_startup.ms", scripts_dir / "post_startup.ms")
    _copy_with_utf8_bom(SRC_MAXSCRIPT / "uninstall_helper.ms", scripts_dir / "uninstall_helper.ms")
    shutil.copytree(SRC_PYTHON, python_dir, ignore=_ignore_junk)

    # Copy convenient top-level launchers into dist/ (self-contained!)
    shutil.copy2(PROJECT_ROOT / "install.bat", DIST_DIR / "install.bat")
    shutil.copy2(PROJECT_ROOT / "uninstall.bat", DIST_DIR / "uninstall.bat")
    _copy_with_utf8_bom(PACKAGING_DIR / "install.ps1", DIST_DIR / "install.ps1")
    _copy_with_utf8_bom(PACKAGING_DIR / "uninstall.ps1", DIST_DIR / "uninstall.ps1")
    _copy_with_utf8_bom(PACKAGING_DIR / "Load_MaxHotbox_Now.ms", DIST_DIR / "Load_MaxHotbox_Now.ms")

    # 3. Validate bundle
    py_count = _compile_check_python(python_dir)
    _validate_package_xml(bundle_dir, target_version=max_ver)

    # 4. Build standard ZIP release archive
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        _zip_directory(zf, bundle_dir, f"{plugin_name}.bundle")
        zf.write(PROJECT_ROOT / "install.bat", "install.bat")
        zf.write(PROJECT_ROOT / "uninstall.bat", "uninstall.bat")
        zf.write(PACKAGING_DIR / "install.ps1", "install.ps1")
        zf.write(PACKAGING_DIR / "uninstall.ps1", "uninstall.ps1")
        zf.write(DIST_DIR / "Load_MaxHotbox_Now.ms", "Load_MaxHotbox_Now.ms")
        for doc_name in ("README.md", "CHANGELOG.md"):
            doc_path = PROJECT_ROOT / doc_name
            if doc_path.exists():
                zf.write(doc_path, doc_name)

    # 5. Build 3ds Max drag-and-drop / Run Script MZP installer package
    with zipfile.ZipFile(mzp_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.write(PACKAGING_DIR / "mzp.run", "mzp.run")
        zf.write(PACKAGING_DIR / "install_mzp.ms", "install_mzp.ms")
        _zip_directory(zf, bundle_dir, f"{plugin_name}.bundle")

    # 6. Write checksum manifest
    manifest_lines = [
        f"{_sha256(zip_path)}  {zip_path.name}",
        f"{_sha256(mzp_path)}  {mzp_path.name}",
    ]
    checksum_path = DIST_DIR / f"{release_stem}_SHA256.txt"
    checksum_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    print(f"[BUILD OK] Compiled {py_count} Python modules.")
    print(f"  Bundle   : {bundle_dir}")
    print(f"  Install  : {DIST_DIR / 'install.bat'}")
    print(f"  LiveLoad : {DIST_DIR / 'Load_MaxHotbox_Now.ms'}")
    print(f"  ZIP      : {zip_path} ({zip_path.stat().st_size:,} bytes)")
    print(f"  MZP      : {mzp_path} ({mzp_path.stat().st_size:,} bytes)")
    print(f"  SHA256   : {checksum_path}")

    return {
        "bundle": bundle_dir,
        "zip": zip_path,
        "mzp": mzp_path,
        "checksum": checksum_path,
    }


if __name__ == "__main__":
    build()
