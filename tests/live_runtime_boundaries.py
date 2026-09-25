"""Blender background gate: runtime callbacks and caches survive reload cycles."""

from __future__ import annotations

import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import dan_form as addon  # noqa: E402
from dan_form.ui import overlay  # noqa: E402


def run():
    checks = []

    def check(condition, label):
        if not condition:
            raise AssertionError(label)
        checks.append(label)

    handler_specs = (
        (bpy.app.handlers.depsgraph_update_post, addon._depsgraph_update_post),
        (bpy.app.handlers.undo_post, addon._undo_post),
        (bpy.app.handlers.redo_post, addon._redo_post),
        (bpy.app.handlers.load_post, addon._load_post),
    )
    try:
        for cycle in range(2):
            addon.register()
            check(all(sum(item is callback for item in handlers) == 1
                      for handlers, callback in handler_specs),
                  f"cycle {cycle + 1}: each persistent handler registered once")
            check(overlay.OVERLAY_HANDLE is not None,
                  f"cycle {cycle + 1}: overlay handler registered")
            addon._MAPPING_CACHE[cycle] = "sentinel"
            addon._PATCH_CACHE[cycle] = "sentinel"
            addon._undo_post(None)
            check(not addon._MAPPING_CACHE and not addon._PATCH_CACHE,
                  f"cycle {cycle + 1}: undo invalidates derived caches")
            addon.unregister()
            check(all(callback not in handlers for handlers, callback in handler_specs),
                  f"cycle {cycle + 1}: unregister removes persistent handlers")
            check(overlay.OVERLAY_HANDLE is None,
                  f"cycle {cycle + 1}: unregister removes overlay handler")
        addon.register()
        check(all(sum(item is callback for item in handlers) == 1
                  for handlers, callback in handler_specs),
              "re-register after repeated cycles leaves one handler per event")
        addon._load_post(None)
        check(not addon._MAPPING_CACHE and not addon._PATCH_CACHE,
              "load invalidates derived caches")
        addon.unregister()
        result = {"status": "PASS", "checks": checks,
                  "blender_version": bpy.app.version_string}
    finally:
        if overlay.OVERLAY_HANDLE is not None:
            addon.unregister()
    return result


result = run()
print("DANP_RESULT_JSON=" + __import__("json").dumps(result))
