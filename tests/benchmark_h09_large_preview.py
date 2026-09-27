"""Measure a full Source preview on a disposable Windows Blender project copy.

Run only in background Blender against a project copy placed directly in the
system temporary directory with a ``danp_h09_`` filename. The benchmark clears
per-control visibility masks in memory so every stored control participates;
it never saves the fixture.
"""

from __future__ import annotations

import ctypes
import json
import math
import statistics
import sys
import time
import tempfile
from pathlib import Path

import bpy

BACKGROUND_P95_LIMIT_MS = 40.0


def _preflight() -> Path:
    if not bpy.app.background:
        raise RuntimeError("Run this destructive fixture benchmark only in background Blender")
    blend_path = Path(bpy.data.filepath).resolve()
    temp_root = Path(tempfile.gettempdir()).resolve()
    if blend_path.parent != temp_root or not blend_path.name.startswith("danp_h09_"):
        raise RuntimeError("Open a disposable .blend copy named danp_h09_*.blend from the system temp directory")
    return blend_path


def _process_memory() -> dict | None:
    if sys.platform != "win32":
        return None

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong),
            ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    psapi = ctypes.WinDLL("psapi", use_last_error=True)
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p
    psapi.GetProcessMemoryInfo.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ProcessMemoryCounters),
        ctypes.c_ulong,
    ]
    psapi.GetProcessMemoryInfo.restype = ctypes.c_int
    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(ProcessMemoryCounters)
    if not psapi.GetProcessMemoryInfo(
        kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
    ):
        return None
    mib = 1024.0 * 1024.0
    return {
        "working_set_mb": counters.WorkingSetSize / mib,
        "process_peak_working_set_mb": counters.PeakWorkingSetSize / mib,
    }


def run() -> dict:
    fixture_path = _preflight()
    addon_root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(addon_root))
    import dan_form as addon  # noqa: PLC0415
    from mathutils import Vector  # noqa: PLC0415

    addon.register()
    try:
        source = next((obj for obj in bpy.data.objects
                       if obj.get(addon.SOURCE_UUID_KEY)), None)
        controller = addon._find_controller(source) if source is not None else None
        if (source is None or controller is None or source.type != "MESH"
                or source.mode != "OBJECT" or controller.mode != "OBJECT"):
            raise RuntimeError("Fixture must contain an initialized Source/Controller pair in Object Mode")
        source_scene = next((scene for scene in source.users_scene
                             if scene.objects.get(controller.name) == controller), None)
        window = bpy.context.window
        if source_scene is None or window is None:
            raise RuntimeError("Fixture Source and Controller must share an accessible scene")
        # Representative projects may keep the character in a non-active scene.
        # Resolve the pair first, then switch the disposable benchmark window to
        # its owning scene before hide/selection operators use the active layer.
        if window.scene != source_scene:
            window.scene = source_scene
        if source_scene.view_layers.get(window.view_layer.name) is None:
            window.view_layer = source_scene.view_layers[0]
        if len(source.data.vertices) < 1000 or len(addon._controls(source)) < 30:
            raise RuntimeError("Fixture must have at least 1,000 Source vertices and 30 control definitions")

        definitions = addon._controls(source)
        for definition in definitions:
            definition["enabled"] = True
            definition["hidden_vertex_ids"] = []
            definition["hidden_edge_ids"] = []
        addon._json_set(source, addon.CONTROLS_KEY, definitions)
        addon._json_set(source, addon.HIDDEN_VIDS_KEY, [])
        addon._json_set(source, addon.HIDDEN_EIDS_KEY, [])
        source[addon.NETWORK_REVISION_KEY] = int(source.get(addon.NETWORK_REVISION_KEY, 0)) + 1
        addon._invalidate_patch_cache(source)
        addon._NETWORK_CACHE.pop(source.as_pointer(), None)
        source.hide_set(False)
        controller.hide_set(False)
        addon._rebuild_proxy(source, controller)

        visible_vertices, visible_edges = addon._effective_proxy_elements(source)
        if not visible_vertices or not visible_edges:
            raise RuntimeError("Visibility reset did not produce an effective control proxy")
        for obj in bpy.context.selected_objects:
            obj.select_set(False)
        controller.select_set(True)
        bpy.context.view_layer.objects.active = controller
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        selected = addon._controller_selected_source_ids(controller)
        if selected != set(visible_vertices):
            raise RuntimeError("Controller selection does not cover all effective control vertices")

        memory_before = _process_memory()

        def begin_targets():
            transaction = addon._deform_begin(source, controller)
            targets = {
                vertex_id: transaction["p0"][vertex_id] + Vector((0.002, 0.0, 0.0))
                for vertex_id in transaction["selected"]
            }
            return transaction, targets

        transaction, targets = begin_targets()
        for _ in range(4):
            addon._deform_update(
                source, controller, targets=targets, sync_controller=False,
                selection_intent=set(transaction["selected"]),
            )

        samples_ms = []
        preview_result = None
        for _ in range(30):
            started = time.perf_counter()
            preview_result = addon._deform_update(
                source, controller, targets=targets, sync_controller=False,
                selection_intent=set(transaction["selected"]),
            )
            samples_ms.append((time.perf_counter() - started) * 1000.0)
        addon._deform_cancel(source, controller)

        transaction, targets = begin_targets()
        addon._deform_update(
            source, controller, targets=targets, sync_controller=False,
            selection_intent=set(transaction["selected"]),
        )
        started = time.perf_counter()
        addon._deform_commit(source)
        confirm_commit_ms = (time.perf_counter() - started) * 1000.0
        memory_after = _process_memory()

        ordered = sorted(samples_ms)
        p95_index = max(0, math.ceil(0.95 * len(ordered)) - 1)
        shape_key = addon._active_shape_key(source)
        p95_ms = ordered[p95_index]
        return {
            "status": "PASS" if p95_ms <= BACKGROUND_P95_LIMIT_MS else "FAIL",
            "fixture": {
                "path": str(fixture_path),
                "source_vertices": len(source.data.vertices),
                "source_edges": len(source.data.edges),
                "source_faces": len(source.data.polygons),
                "control_definitions": len(definitions),
                "visible_controller_vertices": len(visible_vertices),
                "visible_controller_edges": len(visible_edges),
                "selected_source_vertices": len(selected),
                "shape_key_count": len(source.data.shape_keys.key_blocks)
                if source.data.shape_keys else 0,
                "active_target": shape_key.name if shape_key else "Base Mesh",
            },
            "preview": {
                "warmup_samples": 4,
                "measured_samples": len(samples_ms),
                "median_ms": statistics.median(samples_ms),
                "p95_ms": p95_ms,
                "scope_vertices": preview_result["scope_vertices"],
                "changed_vertices": preview_result["changed_vertices"],
            },
            "confirm_commit_ms": confirm_commit_ms,
            "thresholds": {
                "background_preview_p95_max_ms": BACKGROUND_P95_LIMIT_MS,
            },
            "process_memory_before": memory_before,
            "process_memory_after": memory_after,
            "limitations": [
                "Background workflow timing excludes native mouse dispatch, viewport redraw, and GPU overlay drawing.",
                "Process peak working set is a process-lifetime high-water mark and includes file loading/setup.",
                "Control visibility is reset only in this unsaved disposable copy.",
            ],
        }
    finally:
        addon.unregister()


result = run()
print("DANP_RESULT_JSON=" + json.dumps(result, sort_keys=True))
