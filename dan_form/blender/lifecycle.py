"""Blender lifecycle callbacks and runtime invalidation.

The callbacks are deliberately kept outside the package facade.  ``bind``
injects the small set of Source/controller adapters and shared runtime caches
after import, so registration and reload always point at one callback object.
"""

from __future__ import annotations

import bpy
from bpy.app.handlers import persistent
from mathutils import Vector
import uuid

from .. import runtime
from ..constants import *
from . import transform_session as _transform_session
from .context import orphaned_owned_objects
from .workflows import update_revision

NATIVE_POLL_INTERVAL = 0.01


def bind(api) -> None:
    for name in dir(api):
        if name.startswith("_"):
            globals()[name] = getattr(api, name)


@persistent
def _depsgraph_update_post(scene: bpy.types.Scene, depsgraph: bpy.types.Depsgraph) -> None:
    if runtime.SYNC_GUARD:
        return
    runtime.SYNC_GUARD = True
    try:
        updated_ids = {update.id.original.as_pointer() for update in depsgraph.updates}
        _validate_init_target_provenance(updated_ids)
        _reconcile_duplicate_bindings()
        _cleanup_orphaned_owned_objects()
        changed_geometry = {update.id.original.as_pointer() for update in depsgraph.updates if update.is_updated_geometry}
        for source, controller in _source_controller_pairs():
            source_ptr = source.as_pointer()
            if controller.mode == "EDIT":
                runtime.CONTROLLER_EDIT_ACTIVE.add(source_ptr)
            elif source_ptr in runtime.CONTROLLER_EDIT_ACTIVE:
                runtime.CONTROLLER_EDIT_ACTIVE.discard(source_ptr)
                previous_preview = runtime.SHAPE_PREVIEW_STATES.pop(source.as_pointer(), None)
                if previous_preview is not None:
                    source.show_only_shape_key = bool(previous_preview)
            source_changed = source.as_pointer() in changed_geometry or source.data.as_pointer() in changed_geometry
            controller_changed = controller.as_pointer() in changed_geometry or controller.data.as_pointer() in changed_geometry
            current_shape_eval = _shape_key_evaluation_signature(source)
            previous_shape_eval = runtime.SHAPE_EVAL_SIGNATURES.get(source_ptr)
            shape_eval_changed = previous_shape_eval != current_shape_eval
            runtime.SHAPE_EVAL_SIGNATURES[source_ptr] = current_shape_eval
            if not source_changed and not controller_changed and not shape_eval_changed:
                continue
            previous_proxy_snapshot = _PROXY_SNAPSHOTS.get(controller.as_pointer())
            modifier_key = source.as_pointer()
            previous_modifiers = runtime.MODIFIER_SIGNATURES.get(modifier_key)
            current_modifiers = _modifier_signature(source)
            modifier_changed = previous_modifiers is not None and previous_modifiers != current_modifiers
            runtime.MODIFIER_SIGNATURES[modifier_key] = current_modifiers
            _OVERLAY_CACHE.clear()
            _PATCH_OVERLAY_CACHE.pop(source.as_pointer(), None)
            try:
                if source_changed:
                    _MAPPING_CACHE.pop(source.as_pointer(), None)
                    _FACE_CACHE.pop(source.as_pointer(), None)
                    _validate_source_topology(source)
                    if modifier_changed:
                        bpy.context.scene.dan_form_status = (
                            "An unapplied modifier is active. DANP still maps to the Source mesh; "
                            "the overlay follows the evaluated shape."
                        )
                _guard_proxy_topology(source, controller)
                if (controller_changed and controller.mode == "EDIT"
                        and _controller_pose_changed(source, controller, previous_proxy_snapshot)):
                    # Blender restores the proxy to C0 on RMB/Esc. Detect it before calling
                    # update(); otherwise the timer can commit a cancelled
                    # preview or start the next mouse sample from a deformed
                    # Source pose (the cumulative-shrink bug).
                    session = runtime.NATIVE_TRANSFORM_SESSIONS.get(source.as_pointer())
                    if (session is not None
                            and session.get("had_delta")
                            and _transform_session._positions_close(
                                _transform_session.controller_positions(controller),
                                session.get("controller_rest", {}))):
                        _transform_session.cancel(source, controller, _workflow_dependencies())
                        bpy.context.scene.dan_form_status = "Native Controller transform cancelled"
                        continue
                    _observe_native_controller_transform(
                        source, controller, previous_proxy_snapshot
                    )
                # A native G/R/S session owns the live Controller Edit pose.
                # Pushing Source back into that proxy during the same
                # dependency-graph tick would visibly snap the transform and
                # lose numeric/axis-lock input.  The transform bridge performs
                # the final sync on commit or cancel.
                if ((source_changed or shape_eval_changed)
                        and source.as_pointer() not in runtime.NATIVE_TRANSFORM_SESSIONS):
                    _sync_proxy(source, controller)
            except (KeyError, ValueError) as exc:
                if str(exc).startswith("TOPOLOGY_CHANGED"):
                    _set_topology_paused_status(source)
                elif str(exc).startswith("CONTROL_DATA_INVALID"):
                    bpy.context.scene.dan_form_status = f"Error: {exc}"
        active_source, _ = _context_source(bpy.context)
        _sync_ui_list(bpy.context.scene, active_source)
    except (AttributeError, RuntimeError, ValueError) as exc:
        if str(exc).startswith("TOPOLOGY_CHANGED"):
            active_source, _ = _context_source(bpy.context)
            if active_source is not None:
                _set_topology_paused_status(active_source)
        elif str(exc).startswith("CONTROL_DATA_INVALID") and bpy.context.scene is not None:
            bpy.context.scene.dan_form_status = f"Error: {exc}"
    finally:
        runtime.SYNC_GUARD = False


def _validate_init_target_provenance(updated_ids=None) -> None:
    """Invalidate Reset evidence when a captured key stack is structurally replaced."""
    objects = {obj.as_pointer(): obj for obj in bpy.data.objects}
    for source_ptr, evidence in list(runtime.INIT_TARGET_PROVENANCE.items()):
        source = objects.get(source_ptr)
        if (updated_ids and source is not None
                and source_ptr not in updated_ids
                and evidence.get("mesh") not in updated_ids
                and (source.data.shape_keys is None
                     or source.data.shape_keys.as_pointer() not in updated_ids)):
            continue
        if source is None or source.type != "MESH" or source.data.as_pointer() != evidence.get("mesh"):
            evidence["valid"] = False
            continue
        shape_keys = source.data.shape_keys.key_blocks if source.data.shape_keys else ()
        current = tuple((key.as_pointer(), str(key.name)) for key in shape_keys)
        if current != evidence.get("stack"):
            evidence["valid"] = False


def _remember_binding(source, controller) -> None:
    source_uuid = str(source.get(SOURCE_UUID_KEY, "")) if source is not None else ""
    if source_uuid and controller is not None and controller.parent == source:
        runtime.BINDING_OWNERS[source_uuid] = (source.as_pointer(), controller.as_pointer())


def _forget_binding(source) -> None:
    if source is None:
        return
    pointer = source.as_pointer()
    for source_uuid, record in list(runtime.BINDING_OWNERS.items()):
        if record[0] == pointer:
            runtime.BINDING_OWNERS.pop(source_uuid, None)


def _find_object_by_pointer(pointer):
    if not pointer:
        return None
    return next((obj for obj in bpy.data.objects if obj.as_pointer() == pointer), None)


def _source_has_matching_child(source, source_uuid):
    children = _controller_children(source)
    return len(children) == 1 and children[0].get(CONTROLLER_KEY) == source_uuid


def _reconcile_duplicate_bindings() -> int:
    """Rekey new complete pairs by observed ownership, independent of copy gesture."""
    changed = 0
    seen_uuids = {
        str(obj.get(SOURCE_UUID_KEY))
        for obj in bpy.data.objects
        if obj.type == "MESH" and obj.get(CONTROLLER_KEY) is None and obj.get(SOURCE_UUID_KEY)
    }
    # A single direct parent/child pair plus one or more childless meshes is
    # unambiguous: the childless objects are mesh-only copies. Strip only their
    # object-local DANP state and unique mesh ID attributes, then leave them
    # explicitly unbound. This also repairs such files on load without needing
    # operator history.
    for source_uuid in seen_uuids:
        sources = _source_objects_by_uuid(source_uuid)
        if len(sources) < 2:
            continue
        owners = [source for source in sources if _source_has_matching_child(source, source_uuid)]
        if len(owners) != 1:
            continue
        owner = owners[0]
        for duplicate_source in sources:
            if duplicate_source == owner or _controller_children(duplicate_source):
                continue
            _clear_duplicate_source_state(duplicate_source)
            duplicate_source[UNBOUND_COPY_KEY] = True
            changed += 1

    for source_uuid, owner_record in list(runtime.BINDING_OWNERS.items()):
        owner = _find_object_by_pointer(owner_record[0])
        owner_controller = _find_object_by_pointer(owner_record[1])
        if (owner is None or owner.get(SOURCE_UUID_KEY) != source_uuid
                or owner_controller is None or owner_controller.parent != owner
                or owner_controller.get(CONTROLLER_KEY) != source_uuid):
            runtime.BINDING_OWNERS.pop(source_uuid, None)
            continue

        # A Controller-only copy creates an extra marked child. The already
        # registered child remains authoritative for this running session.
        # Demote only the newly observed child; do not touch its geometry.
        for child in _controller_children(owner):
            if child != owner_controller and child.get(CONTROLLER_KEY) == source_uuid:
                world = child.matrix_world.copy()
                child.parent = None
                child.matrix_world = world
                child[UNBOUND_COPY_KEY] = True
                changed += 1

        for duplicate_source in _source_objects_by_uuid(source_uuid):
            if duplicate_source == owner:
                continue
            children = _controller_children(duplicate_source)
            if not children:
                # Mesh-only copies remain unbound and inert. Their copied UUID
                # is handled by the Source resolver and Initialize action.
                duplicate_source[UNBOUND_COPY_KEY] = True
                changed += 1
                continue
            if not _source_has_matching_child(duplicate_source, source_uuid):
                continue
            duplicate_controller = children[0]
            if (getattr(duplicate_source.data, "users", 1) > 1
                    or getattr(duplicate_controller.data, "users", 1) > 1):
                continue
            fresh_uuid = uuid.uuid4().hex
            while _source_objects_by_uuid(fresh_uuid):
                fresh_uuid = uuid.uuid4().hex
            duplicate_source[SOURCE_UUID_KEY] = fresh_uuid
            duplicate_source.pop(UNBOUND_COPY_KEY, None)
            duplicate_controller[CONTROLLER_KEY] = fresh_uuid
            duplicate_source["dan_form_controller_name"] = duplicate_controller.name
            duplicate_controller["dan_form_source_name"] = duplicate_source.name
            runtime.BINDING_OWNERS[fresh_uuid] = (
                duplicate_source.as_pointer(), duplicate_controller.as_pointer()
            )
            changed += 1

    # Register newly initialized pairs while retaining known owners through
    # ordinary depsgraph updates. Conflicted loaded files are deliberately not
    # assigned an arbitrary winner.
    for source, controller in _source_controller_pairs():
        current = runtime.BINDING_OWNERS.get(str(source.get(SOURCE_UUID_KEY, "")))
        if current is None or current == (source.as_pointer(), controller.as_pointer()):
            _remember_binding(source, controller)
    return changed


def _refresh_binding_registry(clear: bool = False) -> None:
    if clear:
        runtime.BINDING_OWNERS.clear()
    _reconcile_duplicate_bindings()
    for source, controller in _source_controller_pairs():
        _remember_binding(source, controller)


def _set_topology_paused_status(source) -> None:
    scene = getattr(bpy.context, "scene", None)
    if scene is not None:
        scene.dan_form_status = (
            f"DANP Form is paused: the topology of '{source.name}' changed. "
            "Use Undo to restore the mapping or Reset DANP to create new controls."
        )


def _cleanup_orphaned_owned_objects() -> int:
    """Mark stale ownership for explicit repair; never delete scene data here."""
    stale = {obj.as_pointer() for obj in orphaned_owned_objects()}
    changed = 0
    for obj in bpy.data.objects:
        pointer = obj.as_pointer()
        marked = bool(obj.get(ORPHANED_OWNED_KEY))
        if getattr(obj, "library", None) is not None or getattr(obj, "override_library", None) is not None:
            continue
        if pointer in stale and not marked:
            try:
                obj[ORPHANED_OWNED_KEY] = True
                changed += 1
            except (ReferenceError, RuntimeError, TypeError):
                continue
        elif pointer not in stale and marked:
            try:
                obj.pop(ORPHANED_OWNED_KEY, None)
                changed += 1
            except (ReferenceError, RuntimeError, TypeError):
                continue
    return changed


def _controller_pose_changed(source, controller, previous_snapshot) -> bool:
    """Distinguish coordinate transforms from selection-only Edit updates."""
    current_positions = _transform_session.controller_positions(controller)
    if previous_snapshot is None or len(previous_snapshot) < 4:
        try:
            return not _positions_close(current_positions, _source_positions(source))
        except (AttributeError, KeyError, RuntimeError, ValueError):
            return False
    previous_positions = {
        int(vertex_id): Vector(coordinates)
        for vertex_id, coordinates, _selected, _hidden in previous_snapshot[3][0]
    }
    return not _positions_close(current_positions, previous_positions)


def _controller_selection_changed(controller, transaction) -> bool:
    """Selection changes delimit transforms; proportional motion does not."""
    try:
        current = _controller_selected_source_ids(controller)
    except (AttributeError, KeyError, RuntimeError, ValueError):
        return False
    expected = transaction.get("selection", transaction.get("selected", ()))
    return set(current) != set(expected)


def _rest_from_proxy_snapshot(snapshot):
    if not snapshot or len(snapshot) < 4:
        return None
    try:
        return {int(vertex_id): Vector(coordinates)
                for vertex_id, coordinates, _selected, _hidden in snapshot[3][0]}
    except (IndexError, TypeError, ValueError):
        return None


def _observe_native_controller_transform(source, controller, previous_snapshot=None) -> None:
    """Bridge native Blender G/R/S edits without nesting a modal operator.

    Controller Edit remains entirely owned by Blender.  On the first native
    coordinate update we capture the DANP transaction rest, then update the
    Source from the live selected proxy coordinates.  A lightweight timer
    waits for Blender's transform operator to finish before committing the
    single transaction; canceling the native operation restores the proxy and
    therefore restores Source through the same path.
    """
    key = source.as_pointer()
    deps = _workflow_dependencies()
    session = runtime.NATIVE_TRANSFORM_SESSIONS.get(key)
    try:
        if session is None:
            session = _transform_session.begin(
                source, controller, deps, "NATIVE",
                controller_rest=_rest_from_proxy_snapshot(previous_snapshot),
            )
            session["timer_registered"] = False
        else:
            # A user can confirm a native transform and immediately select a
            # different vertex before the quiet timer closes the observer
            # session.  The transaction's selected ID set belongs to the
            # previous transform; feeding the new set into it produces
            # TARGET_INVALID and cancellation restores the old Source pose.
            # Commit the old preview from its immutable last targets first.
            transaction = session.get("transaction") or {}
            if _controller_selection_changed(controller, transaction):
                _transform_session.finalize_active(source, controller, deps)
                session = _transform_session.begin(
                    source, controller, deps, "NATIVE",
                    controller_rest=_rest_from_proxy_snapshot(previous_snapshot),
                )
                session["timer_registered"] = False
        scene = bpy.context.scene
        _transform_session.update(
            source,
            controller,
            deps,
            session,
            profile=getattr(scene, "dan_form_proportional_profile", "LINEAR"),
            radius=float(getattr(scene, "dan_form_proportional_radius", 0.0)),
        )
        if not session.get("timer_registered"):
            session["timer_registered"] = True
            bpy.app.timers.register(
                lambda source_ptr=key: _native_transform_timer(source_ptr),
                first_interval=0.0,
            )
    except (ValueError, RuntimeError, KeyError):
        runtime.NATIVE_TRANSFORM_SESSIONS.pop(key, None)
        if key in deps.transactions:
            try:
                _transform_session.cancel(source, controller, deps)
            except (ValueError, RuntimeError):
                deps.transactions.pop(key, None)


def _native_transform_timer(source_ptr):
    session = runtime.NATIVE_TRANSFORM_SESSIONS.get(source_ptr)
    if session is None:
        return None
    source = next((obj for obj in bpy.data.objects if obj.as_pointer() == source_ptr), None)
    controller = next((obj for obj in bpy.data.objects if obj.as_pointer() == session["controller"]), None)
    if source is None or controller is None or controller.mode != "EDIT":
        if source is not None and controller is not None and source_ptr in _DANP_TRANSACTIONS:
            try:
                # Leaving Controller Edit Mode through "Back to Model" is a
                # normal completion path.  The old code treated every mode
                # change as cancellation and restored Source to p0, which
                # erased a valid edit immediately after the user left the
                # controller.  Preserve completed edits; only restore when
                # no transform delta was produced.
                if session.get("had_delta"):
                    _transform_session.commit(source, _workflow_dependencies())
                else:
                    _transform_session.cancel(source, controller, _workflow_dependencies())
            except (ValueError, RuntimeError):
                _DANP_TRANSACTIONS.pop(source_ptr, None)
        runtime.NATIVE_TRANSFORM_SESSIONS.pop(source_ptr, None)
        return None
    try:
        current = _transform_session.controller_positions(controller)
        # Selection can change without a geometry depsgraph update.  If it did
        # change before the timer's quiet window elapsed, close the previous
        # operation now; the next transform will create a fresh transaction.
        transaction = session.get("transaction") or {}
        if _controller_selection_changed(controller, transaction):
            _transform_session.finalize_active(source, controller, _workflow_dependencies())
            bpy.context.scene.dan_form_status = "Native Controller transform committed"
            return None
        # A cancelled modal transform restores the proxy to its immutable
        # rest pose.  Handle this before the native-operator probe so a
        # context with an empty WindowManager.operators list cannot turn the
        # restored pose into a committed zero/partial operation.
        if (session.get("had_delta")
                and _transform_session._positions_close(
                    current, session.get("controller_rest", {}))):
            _transform_session.cancel(source, controller, _workflow_dependencies())
            bpy.context.scene.dan_form_status = "Native Controller transform cancelled"
            return None
        if _transform_session.native_transform_active(bpy.context):
            # The timer only samples Blender's explicit modal state.  It does
            # not infer confirmation from elapsed time or from a quiet mouse.
            return NATIVE_POLL_INTERVAL
        # Blender has ended the modal operator.  This is the Confirm boundary;
        # cancellation is handled above by the exact C0 restoration check.
        # Update once from the final absolute Controller pose before closing.
        scene = bpy.context.scene
        _transform_session.update(
            source,
            controller,
            _workflow_dependencies(),
            session,
            profile=getattr(scene, "dan_form_proportional_profile", "LINEAR"),
            radius=float(getattr(scene, "dan_form_proportional_radius", 0.0)),
        )
        _transform_session.commit(source, _workflow_dependencies())
        bpy.context.scene.dan_form_status = "Native Controller transform committed"
    except (ValueError, RuntimeError, KeyError) as exc:
        try:
            _transform_session.cancel(source, controller, _workflow_dependencies())
        except (ValueError, RuntimeError):
            runtime.NATIVE_TRANSFORM_SESSIONS.pop(source_ptr, None)
        if bpy.context.scene is not None:
            bpy.context.scene.dan_form_status = _friendly_error(exc)
    return None


@persistent
def _refresh_runtime(_unused=None, direction=None) -> None:
    runtime.PICK_SESSION += 1
    runtime.NATIVE_TRANSFORM_SESSIONS.clear()
    runtime.TOPOLOGY_STATES.clear()
    runtime.MODIFIER_SIGNATURES.clear()
    runtime.DANP_TRANSACTIONS.clear()
    # Undo/Redo may restore definitions, masks or coordinates.  Derived data
    # must be rebuilt from the restored Source rather than reused by identity.
    _MAPPING_CACHE.clear()
    _NETWORK_CACHE.clear()
    _PATCH_CACHE.clear()
    _PATCH_OVERLAY_CACHE.clear()
    _FACE_CACHE.clear()
    _OVERLAY_CACHE.clear()
    _refresh_binding_registry()
    # Undo/redo handlers run inside Blender's undo stack.  Defer Source mesh
    # writeback until the handler has returned; writing BMesh data re-entrantly
    # from undo_post can deadlock or invalidate the active edit mesh.
    if direction in {"UNDO", "REDO"} and runtime.NATIVE_UNDO_RECORDS and not runtime.NATIVE_UNDO_TIMER:
        runtime.NATIVE_UNDO_TIMER = True
        runtime.NATIVE_UNDO_DIRECTION = direction
        bpy.app.timers.register(
            lambda pending_direction=direction: _restore_native_undo_records(pending_direction),
            first_interval=0.05,
        )


@persistent
def _undo_post(_unused=None) -> None:
    _refresh_runtime(_unused, "UNDO")


@persistent
def _redo_post(_unused=None) -> None:
    _refresh_runtime(_unused, "REDO")


@persistent
def _load_post(_unused=None) -> None:
    runtime.INIT_TARGET_PROVENANCE.clear()
    runtime.NATIVE_UNDO_RECORDS.clear()
    runtime.SHAPE_PREVIEW_STATES.clear()
    runtime.CONTROLLER_EDIT_ACTIVE.clear()
    _refresh_binding_registry(clear=True)
    runtime.SHAPE_EVAL_SIGNATURES.clear()
    _refresh_runtime(_unused)
    _PICK_PREVIEW.clear()
    _MAPPING_CACHE.clear()
    _UI_SIGNATURES.clear()
    _PROXY_SNAPSHOTS.clear()
    _NETWORK_CACHE.clear()
    _PATCH_CACHE.clear()
    _PATCH_OVERLAY_CACHE.clear()
    _FACE_CACHE.clear()
    _OVERLAY_CACHE.clear()
    _cleanup_orphaned_owned_objects()
    try:
        for source, controller in _source_controller_pairs():
            _migrate_control_schema(source)
            _guard_proxy_topology(source, controller)
        _sync_context_ui_list(bpy.context)
    except (AttributeError, RuntimeError, ValueError) as exc:
        if str(exc).startswith("TOPOLOGY_CHANGED"):
            active_source, _ = _context_source(bpy.context)
            if active_source is not None:
                _set_topology_paused_status(active_source)
        elif str(exc).startswith("CONTROL_DATA_INVALID") and bpy.context.scene is not None:
            bpy.context.scene.dan_form_status = f"Error: {exc}"


def _update_revision(source: bpy.types.Object) -> None:
    update_revision(source)


def _positions_close(left, right, tolerance=1e-6) -> bool:
    if set(left) != set(right):
        return False
    return all((left[key] - right[key]).length <= tolerance for key in left)


def _active_target_matches(source, target_record) -> bool:
    if isinstance(target_record, str) and target_record == BASE_MESH_TARGET:
        return source.data.shape_keys is None and _active_shape_key(source) is None
    if not isinstance(target_record, dict):
        return False
    if target_record.get("kind") == "BASE":
        return source.data.shape_keys is None and _active_shape_key(source) is None
    try:
        target = _resolve_shape_key(source, target_record)
        return target is not None and _active_shape_key(source) == target
    except (AttributeError, ReferenceError, RuntimeError, ValueError):
        return False


def _restore_native_undo_records(direction: str):
    """Pair Blender's native proxy undo with the Source deformation state."""
    try:
        for source_ptr, record in list(runtime.NATIVE_UNDO_RECORDS.items()):
            source = next((obj for obj in bpy.data.objects if obj.as_pointer() == source_ptr), None)
            if source is None and record.get("source_uuid"):
                source = _find_source_by_uuid(record["source_uuid"])
            if source is None:
                runtime.NATIVE_UNDO_RECORDS.pop(source_ptr, None)
                continue
            if source.as_pointer() != source_ptr:
                runtime.NATIVE_UNDO_RECORDS[source.as_pointer()] = runtime.NATIVE_UNDO_RECORDS.pop(source_ptr)
            try:
                target_record = record.get("shape_key_target")
                _resolve_shape_key(source, target_record)
                source_now = _source_positions(source, target_record)
                history = record.get("history", [])
                controllers = {obj.as_pointer(): obj for obj in bpy.data.objects}

                def controller_for(item):
                    controller = controllers.get(item.get("controller"))
                    if controller is not None:
                        return controller
                    return _find_controller(source)

                def controller_pose_matches(item, expected_key):
                    controller = controller_for(item)
                    expected = item.get(expected_key, {})
                    if controller is None or not expected:
                        return False
                    try:
                        return _positions_close(
                            _transform_session.controller_positions(controller),
                            expected,
                        )
                    except (AttributeError, KeyError, RuntimeError, ValueError):
                        return False

                candidate = None
                if direction == "UNDO":
                    candidate = next(
                        (item for item in reversed(history)
                         if item.get("state") == "committed"
                         and (_positions_close(source_now, item.get("source_post", {}))
                              or _positions_close(source_now, item.get("source_pre", {})))
                         and controller_pose_matches(item, "controller_pre")),
                        None,
                    )
                elif direction == "REDO":
                    candidate = next(
                        (item for item in reversed(history)
                         if item.get("state") == "undone"
                         and (_positions_close(source_now, item.get("source_pre", {}))
                              or _positions_close(source_now, item.get("source_post", {})))
                         and controller_pose_matches(item, "controller_post")),
                        None,
                    )
                source_post = candidate.get("source_post", {}) if candidate else {}
                source_pre = candidate.get("source_pre", {}) if candidate else {}
                if direction == "UNDO" and candidate is not None and candidate.get("state") == "committed":
                    runtime.SYNC_GUARD = True
                    try:
                        target_key = candidate.get("shape_key_target")
                        if not _positions_close(source_now, source_pre):
                            _write_source_positions(source, source_pre, allow_locked=True, shape_key=target_key)
                        controller = controller_for(candidate)
                        target_is_active = _active_target_matches(source, target_key)
                        if controller is not None and target_is_active:
                            _sync_proxy(source, controller)
                    finally:
                        runtime.SYNC_GUARD = False
                    candidate["state"] = "undone"
                    record.update(candidate)
                elif direction == "REDO" and candidate is not None and candidate.get("state") == "undone":
                    runtime.SYNC_GUARD = True
                    try:
                        target_key = candidate.get("shape_key_target")
                        if not _positions_close(source_now, source_post):
                            _write_source_positions(source, source_post, allow_locked=True, shape_key=target_key)
                        controller = controller_for(candidate)
                        target_is_active = _active_target_matches(source, target_key)
                        if controller is not None and target_is_active:
                            _sync_proxy(source, controller)
                    finally:
                        runtime.SYNC_GUARD = False
                    candidate["state"] = "committed"
                    record.update(candidate)
            except (AttributeError, KeyError, RuntimeError, ValueError):
                continue
    finally:
        runtime.NATIVE_UNDO_TIMER = False
        runtime.NATIVE_UNDO_DIRECTION = None


__all__ = ["bind", "_depsgraph_update_post", "_refresh_runtime", "_undo_post", "_redo_post", "_load_post", "_update_revision", "_cleanup_orphaned_owned_objects", "_remember_binding", "_forget_binding", "_reconcile_duplicate_bindings", "_refresh_binding_registry"]
