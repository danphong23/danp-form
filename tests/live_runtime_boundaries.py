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
            for module in (addon._operators, addon._lifecycle, overlay):
                check(sys.modules.get(module.__name__) is module
                      and module.__spec__.name == module.__name__,
                      f"cycle {cycle + 1}: binding preserves {module.__spec__.name} module identity")
            check(addon._selected_source_elements(None) == (set(), set()),
                  f"cycle {cycle + 1}: unsupported selection context returns an empty pair")
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
        original_register_class = bpy.utils.register_class
        register_attempts = 0

        def injected_register_failure(cls):
            nonlocal register_attempts
            register_attempts += 1
            if register_attempts == 3:
                raise RuntimeError("INJECTED_REGISTER_FAILURE")
            return original_register_class(cls)

        bpy.utils.register_class = injected_register_failure
        registration_failed = False
        try:
            addon.register()
        except RuntimeError as exc:
            registration_failed = str(exc) == "INJECTED_REGISTER_FAILURE"
        finally:
            bpy.utils.register_class = original_register_class
        registered_classes = [cls.__name__ for cls in addon.CLASSES
                              if hasattr(bpy.types, cls.__name__)]
        scene_props = (
            "dan_form_source", "dan_form_controller", "dan_form_status",
            "dan_form_selected_control", "dan_form_control_items",
            "dan_form_control_index", "dan_form_ui_source_uuid",
            "dan_form_overlay_enabled", "dan_form_patches_enabled",
            "dan_form_overlay_hidden", "dan_form_overlay_xray",
            "dan_form_overlay_width", "dan_form_proportional_profile",
            "dan_form_proportional_radius",
        )
        check(registration_failed and not registered_classes
              and not any(hasattr(bpy.types.Scene, name) for name in scene_props)
              and overlay.OVERLAY_HANDLE is None
              and not addon._runtime.DANP_TRANSACTIONS,
              "failed mid-registration rolls back classes, properties and overlay")
        original_register_controls = addon._register_control_keymaps

        def injected_late_registration_failure():
            original_register_controls()
            raise RuntimeError("INJECTED_LATE_REGISTER_FAILURE")

        addon._register_control_keymaps = injected_late_registration_failure
        late_failure_seen = False
        try:
            addon.register()
        except RuntimeError as exc:
            late_failure_seen = str(exc) == "INJECTED_LATE_REGISTER_FAILURE"
        finally:
            addon._register_control_keymaps = original_register_controls
        remaining_handlers = any(
            callback in handler_list
            for handler_list, callback in handler_specs
        )
        check(late_failure_seen
              and not any(hasattr(bpy.types, cls.__name__) for cls in addon.CLASSES)
              and not any(hasattr(bpy.types.Scene, name) for name in scene_props)
              and not remaining_handlers
              and not addon._runtime.TOPOLOGY_KEYMAPS
              and not addon._runtime.CONTROL_KEYMAPS
              and overlay.OVERLAY_HANDLE is None,
              "late registration failure removes handlers, keymaps and overlay")
        result = {"status": "PASS", "checks": checks,
                  "blender_version": bpy.app.version_string}
    finally:
        if overlay.OVERLAY_HANDLE is not None:
            addon.unregister()
    return result


result = run()
print("DANP_RESULT_JSON=" + __import__("json").dumps(result))
