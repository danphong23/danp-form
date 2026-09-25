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


def moved_controller_targets(controller: bpy.types.Object, rest: dict[int, Vector],
                             tolerance: float = 1e-7) -> dict[int, Vector]:
    """Return every Controller vertex whose coordinate changed from rest."""
    current = _controller_positions(controller)
    return {
        vertex_id: position.copy()
        for vertex_id, position in current.items()
        if vertex_id not in rest or (position - rest[vertex_id]).length > tolerance
    }


def _has_native_transform(context: bpy.types.Context) -> bool:
    """Return whether Blender still owns an interactive transform.

    ``WindowManager.operators`` is an execution/history collection and is not
    a reliable modal-state signal.  Blender exposes the actual live modal
    operators on each Window instead.  Reading every window also matters when
    the depsgraph callback is running without the 3D View as its active area.
    An empty modal-operator collection is the exact end boundary.  We do not
    fall back to ``active_operator`` because that context field can describe
    the operator being dispatched rather than a still-running modal transform.
    """
    windows = getattr(getattr(context, "window_manager", None), "windows", ())
    for window in windows:
        for operator in getattr(window, "modal_operators", ()):
            if str(getattr(operator, "bl_idname", "")).startswith("TRANSFORM_OT_"):
                return True
    return False


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
        "last_targets": {},
        # The observer normally starts on the first geometry update, after
        # Blender has already applied the first mouse sample.  Callers may
        # therefore provide the immutable pre-transform snapshot captured by
        # the lifecycle cache; falling back to the live pose is retained for
        # explicit API/EXEC_DEFAULT calls.
        "controller_rest": controller_rest or _controller_positions(controller),
        "had_delta": False,
    }
    if controller_rest:
        tx["controller_pre"] = {
            int(vertex_id): position.copy()
            for vertex_id, position in controller_rest.items()
        }
    runtime.NATIVE_TRANSFORM_SESSIONS[key] = session
    return session


def update(source, controller, deps, session, profile="LINEAR", radius=0.0,
           targets=None) -> dict | None:
    if targets is None:
        targets = moved_controller_targets(controller, session.get("controller_rest", {}))
    selection_intent = set(
        (session.get("transaction") or {}).get("selection", ())
    )
    # Controller and Source share local coordinates by construction
    # (controller is parented with an identity basis).  Keep this conversion
    # explicit so a future non-identity controller can add one in one place.
    result = _deform_update(source, controller, (0.0, 0.0, 0.0), profile,
                            radius, targets=targets, sync_controller=False,
                            selection_intent=selection_intent)
    session["last_targets"] = {vertex_id: position.copy() for vertex_id, position in targets.items()}
    rest = session.get("controller_rest", {})
    # ``targets`` contains only vertices Blender actually moved, including
    # unselected Proportional vertices.  Selection intent is passed separately
    # so points unchanged by an axis Scale can still belong to its moving side.
    rest_targets = {vertex_id: rest[vertex_id] for vertex_id in targets if vertex_id in rest}
    session["had_delta"] = session.get("had_delta", False) or (
        bool(targets) and not _positions_close(targets, rest_targets)
    )
    return result


def commit(source, deps) -> None:
    key = source.as_pointer()
    tx = deps.transactions.get(key)
    if tx is not None:
        _deform_commit(source)
    runtime.NATIVE_TRANSFORM_SESSIONS.pop(key, None)


def cancel(source, controller, deps) -> None:
    key = source.as_pointer()
    if key in deps.transactions:
        # Cancellation restores both Source and Controller.  Updating the
        # Controller can synchronously invoke the depsgraph observer while
        # this session is still registered; without the guard, that observer
        # interprets the restoration itself as another live transform sample
        # and writes a fresh preview back onto Source.
        previous_guard = runtime.SYNC_GUARD
        runtime.SYNC_GUARD = True
        try:
            _deform_cancel(source, controller)
        finally:
            runtime.SYNC_GUARD = previous_guard
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
            update(source, controller, deps, session,
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


__all__ = ["bind", "begin", "update", "commit", "cancel", "finalize_active", "native_transform_active", "controller_targets", "controller_positions", "moved_controller_targets"]
