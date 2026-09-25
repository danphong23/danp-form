"""Build and validate a clean Blender extension archive from this checkout."""

from __future__ import annotations

import argparse
import hashlib
import re
import tomllib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGE_ROOT_FILES = (
    "README.md", "README_VI.md", "CHANGELOG.md", "LICENSE.md",
    "blender_manifest.toml",
)
FORBIDDEN_PARTS = {".git", "__pycache__", "tests", "test", ".pytest_cache"}
EXCLUDED_DOCS = {"docs/testing/2026-09-25-h10-package-candidate.md"}


def package_entries() -> dict[str, Path]:
    entries = {name: ROOT / name for name in PACKAGE_ROOT_FILES}
    for path in (ROOT / "dan_form").rglob("*"):
        if not path.is_file() or "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        entries[path.relative_to(ROOT / "dan_form").as_posix()] = path
    for folder in ("docs", "tasks"):
        for path in (ROOT / folder).rglob("*.md"):
            relative = path.relative_to(ROOT).as_posix()
            if relative not in EXCLUDED_DOCS:
                entries[relative] = path
    return entries


def validate(archive: Path) -> tuple[list[str], str]:
    with zipfile.ZipFile(archive) as package:
        names = package.namelist()
        bad = package.testzip()
        if bad:
            raise ValueError(f"Corrupt ZIP member: {bad}")
        if len(names) != len(set(names)):
            raise ValueError("Duplicate ZIP paths")
        if any(any(part in FORBIDDEN_PARTS for part in Path(name).parts)
               or name.endswith((".pyc", ".pyo")) for name in names):
            raise ValueError("Package contains a test/cache/build artifact")
        required = {"__init__.py", "blender_manifest.toml", "LICENSE.md", "README.md", "README_VI.md"}
        missing = sorted(required - set(names))
        if missing:
            raise ValueError("Missing package files: " + ", ".join(missing))
        manifest = tomllib.loads(package.read("blender_manifest.toml").decode("utf-8"))
        source_init = package.read("__init__.py").decode("utf-8")
        version = ".".join(map(str, manifest["version"].split(".")))
        version_tuple = tuple(int(part) for part in version.split("."))
        match = re.search(r'"version"\s*:\s*\(([^)]*)\)', source_init)
        if not match or tuple(int(part.strip()) for part in match.group(1).split(",") if part.strip()) != version_tuple:
            raise ValueError("Manifest and add-on bl_info versions differ")
        if manifest.get("id") != "dan_form":
            raise ValueError("Unexpected extension ID")
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        return names, digest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="ZIP output path; defaults to dist/DANP_Form_<version>.zip")
    parser.add_argument("--validate", type=Path, help="Validate an existing ZIP without rebuilding it")
    args = parser.parse_args()
    if args.validate:
        archive = args.validate.resolve()
    else:
        manifest = tomllib.loads((ROOT / "blender_manifest.toml").read_text(encoding="utf-8"))
        archive = (args.output or ROOT / "dist" / f"DANP_Form_{manifest['version']}.zip").resolve()
        archive.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
            for name, path in sorted(package_entries().items()):
                package.write(path, name)
    names, digest = validate(archive)
    print(f"PASS: {len(names)} files; SHA256={digest}; archive={archive}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
