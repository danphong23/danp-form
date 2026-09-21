"""Native Controller Edit transform bridge.

Blender owns the actual G/R/S interaction (axis locks, numeric input,
snapping, mouse preview and cancel).  This module only bridges the live
controller coordinates into the existing pure deformation transaction.
"""

from __future__ import annotations

import bmesh
import bpy
from mathutils import Vector

from .. import runtime
from ..constants import *


def _controller_targets(controller: bpy.types.Object) -> dict[int, Vector]:
    bm = bmesh.from_edit_mesh(controller.data)
    bm.verts.ensure_lookup_table()
    layer = bm.verts.layers.int.get(PROXY_VID_ATTR)
    if layer is None:
        raise ValueError("PROXY_MAPPING_MISSING")
    return {int(vertex[layer]): vertex.co.copy() for vertex in bm.verts if vertex.select and not vertex.hide}


def _controller_positions(controller: bpy.types.Object) -> dict[int, Vector]:
    if controller.mode == "EDIT":
        bm = bmesh.from_edit_mesh(controller.data)
        bm.verts.ensure_lookup_table()
        layer = bm.verts.layers.int.get(PROXY_VID_ATTR)
        return {int(vertex[layer]): vertex.co.copy() for vertex in bm.verts} if layer else {}
    layer = controller.data.attributes.get(PROXY_VID_ATTR)
    if layer is None:
        return {}
    return {int(item.value): controller.data.vertices[index].co.copy()
            for index, item in enumerate(layer.data) if index < len(controller.data.vertices)}


def controller_targets(controller: bpy.types.Object) -> dict[int, Vector]:
    """Read the currently selected native Controller Edit target positions."""
    return _controller_targets(controller)


def controller_positions(controller: bpy.types.Object) -> dict[int, Vector]:
    """Read all proxy coordinates for undo/redo matching."""
    return _controller_positions(controller)


def _has_native_transform(context: bpy.types.Context) -> bool:
    return any(str(operator.bl_idname).startswith("TRANSFORM_OT_")
               for operator in context.window_manager.operators)


def begin(source, controller, deps, operation: str, controller_rest=None) -> dict:
    key = source.as_pointer()
    tx = deps.transactions.get(key)
    if tx is None:
        tx = _deform_begin(source, controller)
    session = {
        "source": source.as_pointer(),
        "controller": controller.as_pointer(),
        "operation": operation,
        "source_uuid": source.get(SOURCE_UUID_KEY),
        "transaction": tx,
        "last_targets": _controller_targets(controller),
        # The observer normally starts on the first geometry update, after
        # Blender has already applied the first mouse sample.  Callers may
        # therefore provide the immutable pre-transform snapshot captured by
        # the lifecycle cache; falling back to the live pose is retained for
        # explicit API/EXEC_DEFAULT calls.
        "controller_rest": controller_rest or _controller_positions(controller),
        # A macro-backed native transform owns its own finish/cancel path.
        # The legacy observer path may still be used by direct API/MCP calls,
        # but must never be confused with the user-facing modal operation.
        "managed_by_macro": str(operation).startswith("MACRO_"),
        "had_delta": False,
    }
    runtime.NATIVE_TRANSFORM_SESSIONS[key] = session
    return session


def update(source, controller, deps, session, profile="LINEAR", radius=0.0,
           targets=None) -> dict | None:
    if targets is None:
        targets = _controller_targets(controller)
    if not targets:
        return None
    # Controller and Source share local coordinates by construction
    # (controller is parented with an identity basis).  Keep this conversion
    # explicit so a future non-identity controller can add one in one place.
    result = _deform_update(source, controller, (0.0, 0.0, 0.0), profile,
                            radius, targets=targets, sync_controller=False)
    session["last_targets"] = targets
    rest = session.get("controller_rest", {})
    session["had_delta"] = session.get("had_delta", False) or not _positions_close(targets, rest)
    return result


def commit(source, deps) -> None:
    key = source.as_pointer()
    tx = deps.transactions.get(key)
    session = runtime.NATIVE_TRANSFORM_SESSIONS.get(key)
    if tx is not None:
        if session is not None and str(session.get("operation", "")).startswith(("NATIVE", "MACRO")):
            runtime.NATIVE_UNDO_RECORDS[key] = {
                "source": key,
                "controller": session["controller"],
                "source_pre": {int(vid): position.copy() for vid, position in tx["p0"].items()},
                "source_post": {int(vid): position.copy() for vid, position in _source_positions(source).items()},
                "controller_post": _controller_positions(
                    next((obj for obj in bpy.data.objects if obj.as_pointer() == session["controller"]), source)
                ),
                "state": "committed",
            }
        _deform_commit(source)
    runtime.NATIVE_TRANSFORM_SESSIONS.pop(key, None)


def cancel(source, controller, deps) -> None:
    key = source.as_pointer()
    if key in deps.transactions:
        _deform_cancel(source, controller)
    runtime.NATIVE_TRANSFORM_SESSIONS.pop(key, None)


def finalize_active(source, controller, deps) -> bool:
    """Close an active native session before another command changes context.

    Blender can end a native transform implicitly when focus moves to the
    sidebar or when another transform starts.  In that case the proxy may
    already be back at its modal rest pose even though the Source preview is
    still valid.  Treat a session with a real delta as committed; only an
    untouched session is a cancellation.
    """
    key = source.as_pointer()
    session = runtime.NATIVE_TRANSFORM_SESSIONS.get(key)
    if session is None:
        return False
    try:
        if session.get("had_delta"):
            # Selection may already have moved to the next control.  The
            # previous session must be committed from its own last sample,
            # never from the new selection.
            update(source, controller, deps,
                   targets=session.get("last_targets", {}))
            commit(source, deps)
        else:
            cancel(source, controller, deps)
    except (ValueError, RuntimeError, KeyError):
        # Do not leave a half-open transaction blocking the next command.
        runtime.NATIVE_TRANSFORM_SESSIONS.pop(key, None)
        deps.transactions.pop(key, None)
        raise
    return True


def native_transform_active(context: bpy.types.Context) -> bool:
    return _has_native_transform(context)


def _positions_close(left, right, tolerance=1e-6) -> bool:
    if set(left) != set(right):
        return False
    return all((left[key] - right[key]).length <= tolerance for key in left)


def bind(api) -> None:
    global _deform_begin, _deform_update, _deform_commit, _deform_cancel, _source_positions
    _deform_begin = api._deform_begin
    _deform_update = api._deform_update
    _deform_commit = api._deform_commit
    _deform_cancel = api._deform_cancel
    _source_positions = api._source_positions


__all__ = ["bind", "begin", "update", "commit", "cancel", "finalize_active", "native_transform_active", "controller_targets", "controller_positions"]
