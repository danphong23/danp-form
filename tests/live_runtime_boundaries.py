"""Blender background gate: runtime callbacks and caches survive reload cycles."""

from __future__ import annotations

import sys
import logging
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
            from dan_form.ui import panel
            for module in (addon._operators, addon._lifecycle, overlay, panel):
                check(sys.modules.get(module.__name__) is module
                      and module.__spec__.name == module.__name__,
                      f"cycle {cycle + 1}: binding preserves {module.__spec__.name} module identity")
            check(addon._selected_source_elements(None) == (set(), set()),
                  f"cycle {cycle + 1}: unsupported selection context returns an empty pair")
            check(all(sum(item is callback for item in handlers) == 1
                      for handlers, callback in handler_specs),
                  f"cycle {cycle + 1}: each persistent handler registered once")
            check(addon.DANFORM_PT_sidebar.__module__ == "dan_form.ui.panel",
                  f"cycle {cycle + 1}: sidebar class belongs to the UI module")
            check(overlay.OVERLAY_HANDLE is not None,
                  f"cycle {cycle + 1}: overlay handler registered")
            transform_timer = lambda: 60.0
            undo_timer = lambda: 60.0
            bpy.app.timers.register(transform_timer, first_interval=60.0)
            bpy.app.timers.register(undo_timer, first_interval=60.0)
            addon._runtime.NATIVE_TRANSFORM_TIMERS[cycle + 1] = transform_timer
            addon._runtime.NATIVE_UNDO_TIMER_CALLBACK = undo_timer
            addon._MAPPING_CACHE[cycle] = "sentinel"
            addon._PATCH_CACHE[cycle] = "sentinel"
            addon._undo_post(None)
            check(not addon._MAPPING_CACHE and not addon._PATCH_CACHE,
                  f"cycle {cycle + 1}: undo invalidates derived caches")
            check(not bpy.app.timers.is_registered(transform_timer)
                  and not addon._runtime.NATIVE_TRANSFORM_TIMERS
                  and bpy.app.timers.is_registered(undo_timer),
                  f"cycle {cycle + 1}: undo cancels stale transform timers only")
            transform_timer = lambda: 60.0
            bpy.app.timers.register(transform_timer, first_interval=60.0)
            addon._runtime.NATIVE_TRANSFORM_TIMERS[cycle + 101] = transform_timer
            addon.unregister()
            check(all(callback not in handlers for handlers, callback in handler_specs),
                  f"cycle {cycle + 1}: unregister removes persistent handlers")
            check(overlay.OVERLAY_HANDLE is None,
                  f"cycle {cycle + 1}: unregister removes overlay handler")
            check(not bpy.app.timers.is_registered(transform_timer)
                  and not bpy.app.timers.is_registered(undo_timer)
                  and not addon._runtime.NATIVE_TRANSFORM_TIMERS
                  and addon._runtime.NATIVE_UNDO_TIMER_CALLBACK is None,
                  f"cycle {cycle + 1}: unregister cancels owned timers and clears handles")
        addon.register()
        check(all(sum(item is callback for item in handlers) == 1
                  for handlers, callback in handler_specs),
              "re-register after repeated cycles leaves one handler per event")
        original_overlay_mode = overlay._overlay_mode
        original_context_source = overlay._context_source
        original_overlay_batches = overlay._overlay_batches
        previous_error_reported = overlay._DRAW_ERROR_REPORTED
        overlay._DRAW_ERROR_REPORTED = False
        overlay._overlay_mode = lambda _context: "source"
        overlay._context_source = lambda _context: (type("Source", (), {
            "get": lambda _self, _key: "fixture-source"
        })(), object())

        def injected_overlay_failure(*_args, **_kwargs):
            raise RuntimeError("INJECTED_GPU_DRAW_FAILURE")

        overlay._overlay_batches = injected_overlay_failure
        captured_logs = []

        class CaptureOverlayLog(logging.Handler):
            def emit(self, record):
                captured_logs.append(record)

        overlay_logger = logging.getLogger(overlay.__name__)
        original_log_level = overlay_logger.level
        original_log_propagate = overlay_logger.propagate
        capture_handler = CaptureOverlayLog()
        overlay_logger.setLevel(logging.ERROR)
        overlay_logger.propagate = False
        overlay_logger.addHandler(capture_handler)
        overlay._OVERLAY_CACHE["stale-fixture"] = object()
        try:
            overlay._draw_control_overlay()
            overlay._draw_control_overlay()
            diagnostic_reported = overlay._DRAW_ERROR_REPORTED
            stale_cache_cleared = not overlay._OVERLAY_CACHE
        finally:
            overlay._OVERLAY_CACHE.pop("stale-fixture", None)
            overlay_logger.removeHandler(capture_handler)
            overlay_logger.setLevel(original_log_level)
            overlay_logger.propagate = original_log_propagate
            overlay._overlay_mode = original_overlay_mode
            overlay._context_source = original_context_source
            overlay._overlay_batches = original_overlay_batches
            overlay._DRAW_ERROR_REPORTED = previous_error_reported
        check(stale_cache_cleared and diagnostic_reported,
              "overlay draw failure clears stale buffers and activates its diagnostic guard")
        check(len(captured_logs) == 1 and captured_logs[0].exc_info
              and captured_logs[0].exc_info[0] is RuntimeError
              and "INJECTED_GPU_DRAW_FAILURE" in logging.Formatter().formatException(
                  captured_logs[0].exc_info),
              "overlay GPU failure logs one contextual traceback per failure streak; "
              f"captured={len(captured_logs)} record(s)")
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
