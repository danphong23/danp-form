"""Install/uninstall smoke test for a flattened Blender extension ZIP."""

from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

import bpy


def run():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(args) != 1:
        raise RuntimeError("Pass the release ZIP path after --")
    archive = Path(args[0]).resolve()
    checks = []
    temp_root = Path(tempfile.mkdtemp(prefix="danp-install-smoke-"))
    package_root = temp_root / "dan_form"
    package_root.mkdir()
    registered = False
    try:
        with zipfile.ZipFile(archive) as package:
            for member in package.namelist():
                resolved = (package_root / member).resolve()
                if package_root not in resolved.parents and resolved != package_root:
                    raise AssertionError(f"Unsafe archive member: {member}")
                package.extract(member, package_root)
        checks.append("archive extracts without path traversal")
        init_path = package_root / "__init__.py"
        if not init_path.is_file():
            raise AssertionError("extension root has no __init__.py")
        spec = importlib.util.spec_from_file_location(
            "dan_form", init_path,
            submodule_search_locations=[str(package_root)],
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules["dan_form"] = module
        spec.loader.exec_module(module)
        checks.append("installed package imports from extracted archive")
        module.register()
        registered = True
        checks.append("add-on register succeeds")
        module.unregister()
        registered = False
        checks.append("add-on unregister succeeds")
        return {"status": "PASS", "checks": checks,
                "blender_version": bpy.app.version_string,
                "archive": str(archive)}
    finally:
        if registered and "dan_form" in sys.modules:
            try:
                sys.modules["dan_form"].unregister()
            except (AttributeError, RuntimeError):
                pass
            del sys.modules["dan_form"]
        shutil.rmtree(temp_root, ignore_errors=True)


result = run()
print("DANP_RESULT_JSON=" + json.dumps(result))
