"""DANP Form operator compatibility facade and keymap adapters."""

from __future__ import annotations

import json
import copy

import bmesh
import bpy
from mathutils import Vector

from .constants import *
from . import runtime
from .ui import panel as _panel
from .ui.panel import (
    DANFORM_PG_ControlItem,
    DANFORM_UL_controls,
    DANFORM_MT_control_menu,
    DANFORM_MT_manage,
    DANFORM_MT_shape_keys,
    DANFORM_PT_sidebar,
    _ui_item_name_update,
    _ui_control_index_update,
)
from .operator_actions import (
    deformation as _deformation_operators,
    navigation as _navigation_operators,
    selection as _selection_operators,
    shape_keys as _shape_key_operators,
    structure as _structure_operators,
    visibility as _visibility_operators,
)
from .operator_actions.deformation import (
    DANFORM_OT_topology_locked,
    DANFORM_OT_deform,
    DANFORM_OT_cancel_deform,
)
from .operator_actions.navigation import DANFORM_OT_focus_source, DANFORM_OT_focus_controller
from .operator_actions.selection import DANFORM_OT_select_control
from .operator_actions.shape_keys import DANFORM_OT_select_shape_key, DANFORM_OT_create_shape_key
from .operator_actions.structure import (
    DANFORM_OT_initialize,
    DANFORM_OT_resolve_duplicate_pair,
    DANFORM_OT_sync,
    DANFORM_OT_validate_topology,
    DANFORM_OT_repair_topology,
    DANFORM_OT_sync_control,
    DANFORM_OT_move_control,
    DANFORM_OT_create_control,
    DANFORM_OT_rename_control,
    DANFORM_OT_delete_control,
    DANFORM_OT_remove_controller,
    DANFORM_OT_remove,
    DANFORM_OT_reset,
    DANFORM_OT_unbind_orphaned_owned_object,
    DANFORM_OT_reset_source,
)
from .operator_actions.visibility import (
    DANFORM_OT_set_control_visibility,
    DANFORM_OT_hide_selected,
    DANFORM_OT_reveal,
    DANFORM_OT_reveal_controller,
    DANFORM_OT_toggle_viewport_controls,
)

# Helper names used by operator methods are bound to the facade at register time.
def bind(api) -> None:
    bindings = {
        name: getattr(api, name)
        for name in dir(api)
        if not name.startswith("__")
        and (name.startswith("_") or name.startswith("DANFORM_"))
    }
    bindings.update({
        name: value
        for name, value in globals().items()
        if not name.startswith("__")
        and (name.startswith("_") or name.startswith("DANFORM_"))
    })
    globals().update(bindings)
    _panel.bind(bindings)
    for module in (
        _structure_operators, _selection_operators, _visibility_operators,
        _deformation_operators, _shape_key_operators, _navigation_operators,
    ):
        module.bind(bindings)

def _friendly_error(exc: Exception) -> str:
    """Translate stable machine errors into short recovery actions."""
    code = str(exc)
    if code in {"STALE_MAPPING", "TOPOLOGY_CHANGED"}:
        # STALE_MAPPING remains an accepted legacy diagnostic from old files;
        # users should see the recovery action, never an implementation code.
        return "DANP Form is paused. Validate the topology, then Repair if safe, or use Undo or Reset DANP."
    if code == "TOPOLOGY_SNAPSHOT_MISSING":
        return "The original topology map is missing. Use Undo or Reset DANP to create a new mapping."
    if code == "TOPOLOGY_SNAPSHOT_INVALID":
        return "The topology record is invalid. Use Undo or Reset DANP before editing."
    if code == "SOURCE_ID_LAYERS_MISSING":
        return "Source mesh IDs are missing. Sync or Reset DANP on this mesh."
    if code.startswith("CONTROL_DATA_INVALID"):
        return "Control data is invalid. Use Undo or Reset DANP to rebuild the controls."
    if code == "OPERATION_BUSY":
        return "A transform is in progress. Confirm or cancel it before continuing."
    if code == "OPERATION_STALE":
        return "The edit session is stale. Confirm or cancel the transform, then try again."
    if code == "OPERATION_OWNER_MISMATCH":
        return "This transform belongs to another edit operation. Finish that operation first."
    if code == "WORLD_SPACE_MATRIX_REQUIRED":
        return "A world-space transform needs the Source matrix. Use Source-local coordinates instead."
    if code == "WORLD_SPACE_MATRIX_SINGULAR":
        return "The Source transform cannot be inverted. Apply or correct its object transform before using world coordinates."
    if code == "WORLD_SPACE_MATRIX_INVALID":
        return "The Source transform contains invalid values. Correct the object transform and try again."
    if code == "TARGET_OUTSIDE_CONTROLLER_MAPPING":
        return "A target is not represented by this Controller. Sync or rebuild the Controller before editing."
    if code == "SHAPE_KEY_LOCKED":
        return "The selected Shape Key is locked. Unlock it before editing the Controller."
    if code == "SHAPE_KEY_TARGET_INVALID":
        return "The Shape Key target is no longer valid. Select it again on the Source."
    if code in {"SHAPE_KEY_TARGET_CHANGED", "OPERATION_STALE_SHAPE_KEY"}:
        return "The Shape Key changed during the transform. DANP Form cancelled that edit."
    if code in {"UUID_CONFLICT", "CONTROLLER_CONFLICT"}:
        return "Controller ownership is ambiguous. Select the pair to keep and resolve its identity."
    if code == "SHARED_DATA":
        return "The mesh or Controller shares data. Make it single-user before editing."
    if code == "SOURCE_NOT_EDITABLE":
        return "Select a local, single-user mesh to initialize DANP Form."
    if code == "CONTROL_HAS_NO_EFFECTIVE_MEMBERSHIP":
        return "This control has no visible handles to select. Reveal it first."
    if code == "EVALUATED_SOURCE_ID_MAPPING_UNAVAILABLE":
        return "Evaluated Source vertices could not be matched to the mesh. Check the modifier stack and retry."
    if code == "CONTROLLER_BINDING_INCOMPLETE":
        return "Controller setup did not create a valid child. Initialization was rolled back."
    if code.isupper() and "_" in code:
        return f"DANP Form could not complete this action ({code})."
    return code

def _capture_control_structure(source, controller):
    """Capture persisted control state and proxy data for a structural rollback."""
    source_keys = (CONTROLS_KEY, HIDDEN_VIDS_KEY, HIDDEN_EIDS_KEY,
                   NETWORK_REVISION_KEY, TOPOLOGY_KEY, NEXT_VID_KEY,
                   NEXT_EID_KEY, TOPOLOGY_SNAPSHOT_KEY,
                   TOPOLOGY_SNAPSHOT_FINGERPRINT_KEY)
    controller_keys = (PROXY_GENERATION_KEY,)
    pointer = controller.as_pointer() if controller is not None else None
    return {
        "source": {key: source.get(key) for key in source_keys if key in source},
        "source_keys": source_keys,
        "controller": ({key: controller.get(key) for key in controller_keys
                        if key in controller} if controller is not None else {}),
        "controller_keys": controller_keys,
        "controller_data": controller.data.copy() if controller is not None else None,
        "proxy_snapshot": copy.deepcopy(_PROXY_SNAPSHOTS.get(pointer)) if pointer is not None else None,
        "pointer": pointer,
    }

def _restore_control_structure(source, controller, snapshot):
    for key in snapshot["source_keys"]:
        if key in snapshot["source"]:
            source[key] = snapshot["source"][key]
        else:
            source.pop(key, None)
    if controller is not None:
        for key in snapshot["controller_keys"]:
            if key in snapshot["controller"]:
                controller[key] = snapshot["controller"][key]
            else:
                controller.pop(key, None)
        previous_data = snapshot.get("controller_data")
        if previous_data is not None:
            failed_data = controller.data
            controller.data = previous_data
            if failed_data is not previous_data and failed_data.users == 0:
                bpy.data.meshes.remove(failed_data)
        pointer = snapshot.get("pointer")
        if pointer is not None:
            if snapshot["proxy_snapshot"] is None:
                _PROXY_SNAPSHOTS.pop(pointer, None)
            else:
                _PROXY_SNAPSHOTS[pointer] = snapshot["proxy_snapshot"]
    if snapshot.get("controller_data") is not None and controller is None:
        bpy.data.meshes.remove(snapshot["controller_data"])
    _MAPPING_CACHE.pop(source.as_pointer(), None)
    _NETWORK_CACHE.pop(source.as_pointer(), None)
    _PATCH_CACHE.pop(source.as_pointer(), None)
    _PATCH_OVERLAY_CACHE.pop(source.as_pointer(), None)
    _FACE_CACHE.pop(source.as_pointer(), None)
    _OVERLAY_CACHE.clear()

def _discard_control_structure_snapshot(snapshot):
    mesh = snapshot.get("controller_data")
    if mesh is not None and mesh.users == 0 and bpy.data.meshes.get(mesh.name) is mesh:
        bpy.data.meshes.remove(mesh)

def _atomic_control_structure(source, controller, mutation):
    """Run one control/mask mutation with rollback across storage and proxy."""
    snapshot = _capture_control_structure(source, controller)
    try:
        result = mutation()
    except Exception:
        _restore_control_structure(source, controller, snapshot)
        raise
    _discard_control_structure_snapshot(snapshot)
    return result

def _capture_source_id_layers(source):
    """Capture persistent vertex/edge IDs from the authoritative mesh mode."""
    result = {}
    if source.mode == "EDIT":
        bm = bmesh.from_edit_mesh(source.data)
        for name, collection, domain in (
            (VID_ATTR, bm.verts, "POINT"), (EID_ATTR, bm.edges, "EDGE"),
        ):
            layer = collection.layers.int.get(name)
            if layer is not None:
                result[name] = ("INT", domain,
                                [int(item[layer]) for item in collection])
    else:
        for name in (VID_ATTR, EID_ATTR):
            attribute = source.data.attributes.get(name)
            if attribute is not None:
                result[name] = (attribute.data_type, attribute.domain,
                                [int(item.value) for item in attribute.data])
    return result

def _restore_source_id_layers(source, saved):
    if source.mode == "EDIT":
        bm = bmesh.from_edit_mesh(source.data)
        for name, collection in ((VID_ATTR, bm.verts), (EID_ATTR, bm.edges)):
            values = saved.get(name)
            layer = collection.layers.int.get(name)
            if values is None:
                if layer is not None:
                    collection.layers.int.remove(layer)
                continue
            if layer is None:
                layer = collection.layers.int.new(name)
            if len(collection) != len(values[2]):
                raise ValueError("SOURCE_TOPOLOGY_CHANGED_DURING_ROLLBACK")
            for item, value in zip(collection, values[2]):
                item[layer] = value
        bmesh.update_edit_mesh(source.data, loop_triangles=False, destructive=False)
        return
    for name in (VID_ATTR, EID_ATTR):
        attribute = source.data.attributes.get(name)
        if attribute is not None:
            source.data.attributes.remove(attribute)
    for name, (data_type, domain, values) in saved.items():
        attribute = source.data.attributes.new(name=name, type=data_type, domain=domain)
        if len(attribute.data) != len(values):
            raise ValueError("SOURCE_TOPOLOGY_CHANGED_DURING_ROLLBACK")
        for item, value in zip(attribute.data, values):
            item.value = value

_SOURCE_DANP_KEYS = (
    SOURCE_UUID_KEY, SCHEMA_KEY, CONTROLS_KEY, HIDDEN_VIDS_KEY,
    HIDDEN_EIDS_KEY, NEXT_VID_KEY, NEXT_EID_KEY, TOPOLOGY_KEY,
    NETWORK_REVISION_KEY, ORIGINAL_POSITIONS_KEY, ORIGINAL_TOPOLOGY_KEY,
    TOPOLOGY_SNAPSHOT_KEY, TOPOLOGY_SNAPSHOT_FINGERPRINT_KEY,
    ORIGINAL_SHAPE_KEY_NAME_KEY,
    ORIGINAL_TARGET_KIND_KEY,
    "dan_form_controller_name", UNBOUND_COPY_KEY,
)

def _clear_duplicate_source_state(source) -> None:
    """Turn a mesh-only duplicate into a clean Source without touching its owner."""
    source_uuid = str(source.get(SOURCE_UUID_KEY, ""))
    uuid_is_shared = any(other != source for other in _source_objects_by_uuid(source_uuid)) if source_uuid else False
    _discard_source_runtime(source)
    for key in _SOURCE_DANP_KEYS:
        if key in source:
            del source[key]
    if getattr(source.data, "users", 1) == 1:
        for name in (VID_ATTR, EID_ATTR):
            attribute = source.data.attributes.get(name)
            if attribute is not None:
                source.data.attributes.remove(attribute)
    _MAPPING_CACHE.pop(source.as_pointer(), None)
    _NETWORK_CACHE.pop(source.as_pointer(), None)
    _invalidate_patch_cache(source)
    _OVERLAY_CACHE.clear()
    if not uuid_is_shared:
        _ACTIVE_CONTROL_UUIDS.pop(source_uuid, None)
        _RETURN_MODES.pop(source_uuid, None)

def _capture_original_snapshot(source) -> None:
    """Capture the first Init pose by persistent Source vertex ID."""
    if source.get(ORIGINAL_POSITIONS_KEY):
        # Existing snapshots have no trustworthy KeyBlock identity. Do not
        # synthesize provenance from a key name or index.
        return
    key = _active_shape_key(source)
    positions = _source_positions(source)
    _json_set(source, ORIGINAL_POSITIONS_KEY, {
        str(vertex_id): [float(component) for component in coordinates]
        for vertex_id, coordinates in positions.items()
    })
    source[ORIGINAL_TOPOLOGY_KEY] = str(source.get(TOPOLOGY_KEY, ""))
    source[ORIGINAL_SHAPE_KEY_NAME_KEY] = str(key.name) if key is not None else ""
    source[ORIGINAL_TARGET_KIND_KEY] = "KEY" if key is not None else "BASE"
    shape_keys = source.data.shape_keys.key_blocks if source.data.shape_keys else ()
    runtime.INIT_TARGET_PROVENANCE[source.as_pointer()] = {
        "mesh": source.data.as_pointer(),
        "key": key.as_pointer() if key is not None else None,
        "reference": key,
        "stack": tuple((item.as_pointer(), str(item.name)) for item in shape_keys),
        "valid": True,
    }

def _original_snapshot(source) -> dict[int, Vector]:
    raw = source.get(ORIGINAL_POSITIONS_KEY)
    if not raw:
        raise ValueError("ORIGINAL_SNAPSHOT_MISSING")
    try:
        payload = json.loads(raw) if isinstance(raw, str) else raw
        if not isinstance(payload, dict):
            raise ValueError
        return {int(vertex_id): Vector(value) for vertex_id, value in payload.items()}
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("ORIGINAL_SNAPSHOT_INVALID") from exc

def _discard_source_runtime(source: bpy.types.Object | None) -> None:
    """Drop transient deformation state when a Source/controller is removed."""
    if source is None:
        return
    key = source.as_pointer()
    runtime.INIT_TARGET_PROVENANCE.pop(key, None)
    _forget_binding(source)
    runtime.DANP_TRANSACTIONS.pop(key, None)
    runtime.NATIVE_TRANSFORM_SESSIONS.pop(key, None)
    runtime.NATIVE_UNDO_RECORDS.pop(key, None)
    runtime.TOPOLOGY_STATES.pop(key, None)
    if not runtime.NATIVE_UNDO_RECORDS:
        runtime.NATIVE_UNDO_TIMER = False
        runtime.NATIVE_UNDO_DIRECTION = None

def _require_structural_idle(source: bpy.types.Object | None) -> None:
    """Reject definition/mask/rebuild edits while a native transform is live."""
    if source is not None and (
            source.as_pointer() in runtime.NATIVE_TRANSFORM_SESSIONS
            or source.as_pointer() in runtime.DANP_TRANSACTIONS):
        raise ValueError("OPERATION_BUSY")

def _register_topology_keymaps():
    config = bpy.context.window_manager.keyconfigs.addon
    if config is None:
        return
    km = config.keymaps.new(name="Mesh", space_type="EMPTY")
    # Keep Controller Edit identical to Blender Edit Mode except for edits
    # that change topology.  Selection, navigation and all transforms must
    # pass through Blender unchanged.  The guarded set covers deletion,
    # extrusion/inset, fill/bridge, knife, subdivide, merge and dissolve.
    shortcuts = [
        ("X", {}), ("DEL", {}),
        ("E", {}), ("I", {}), ("F", {}),
        ("K", {}), ("J", {}), ("M", {}), ("V", {}), ("P", {}),
        ("D", {"shift": True}), ("R", {"ctrl": True}),
        ("B", {"ctrl": True}), ("B", {"ctrl": True, "shift": True}),
        ("V", {"alt": True}), ("M", {"alt": True}),
    ]
    for key, modifiers in shortcuts:
        item = km.keymap_items.new("dan_form.topology_locked", key, "PRESS", head=True, **modifiers)
        _TOPOLOGY_KEYMAPS.append((km, item))

def _unregister_topology_keymaps():
    for km, item in _TOPOLOGY_KEYMAPS:
        km.keymap_items.remove(item)
    _TOPOLOGY_KEYMAPS.clear()

def _register_control_keymaps():
    config = bpy.context.window_manager.keyconfigs.addon
    if config is None:
        return
    km = config.keymaps.new(name="Mesh", space_type="EMPTY")
    for operator, key, modifiers in (
        ("dan_form.hide_selected", "H", {}),
        ("dan_form.reveal_controller", "H", {"alt": True}),
    ):
        item = km.keymap_items.new(operator, key, "PRESS", head=True, **modifiers)
        _CONTROL_KEYMAPS.append((km, item))

def _unregister_control_keymaps():
    for km, item in _CONTROL_KEYMAPS:
        km.keymap_items.remove(item)
    _CONTROL_KEYMAPS.clear()

CLASSES = (
    DANFORM_PG_ControlItem,
    DANFORM_UL_controls,
    DANFORM_OT_initialize,
    DANFORM_OT_resolve_duplicate_pair,
    DANFORM_OT_sync,
    DANFORM_OT_validate_topology,
    DANFORM_OT_repair_topology,
    DANFORM_OT_create_control,
    DANFORM_OT_sync_control,
    DANFORM_OT_move_control,
    DANFORM_OT_rename_control,
    DANFORM_OT_select_control,
    DANFORM_OT_set_control_visibility,
    DANFORM_OT_delete_control,
    DANFORM_OT_hide_selected,
    DANFORM_OT_reveal,
    DANFORM_OT_remove_controller,
    DANFORM_OT_remove,
    DANFORM_OT_reset,
    DANFORM_OT_reset_source,
    DANFORM_OT_unbind_orphaned_owned_object,
    DANFORM_OT_topology_locked,
    DANFORM_OT_deform,
    DANFORM_OT_cancel_deform,
    DANFORM_OT_reveal_controller,
    DANFORM_OT_toggle_viewport_controls,
    DANFORM_OT_focus_source,
    DANFORM_OT_focus_controller,
    DANFORM_OT_select_shape_key,
    DANFORM_OT_create_shape_key,
    DANFORM_MT_shape_keys,
    DANFORM_MT_control_menu,
    DANFORM_MT_manage,
    DANFORM_PT_sidebar,
)

__all__ = [
    "bind",
    "CLASSES",
    "_clear_duplicate_source_state",
    "DANFORM_PG_ControlItem",
    "DANFORM_UL_controls",
    "DANFORM_MT_control_menu",
    "DANFORM_MT_shape_keys",
    "DANFORM_MT_manage",
    "DANFORM_OT_select_shape_key",
    "DANFORM_OT_create_shape_key",
    "DANFORM_PT_sidebar",
    "DANFORM_OT_initialize",
    "DANFORM_OT_resolve_duplicate_pair",
    "DANFORM_OT_sync",
    "DANFORM_OT_sync_control",
    "DANFORM_OT_validate_topology",
    "DANFORM_OT_repair_topology",
    "DANFORM_OT_move_control",
    "DANFORM_OT_create_control",
    "DANFORM_OT_rename_control",
    "DANFORM_OT_select_control",
    "DANFORM_OT_set_control_visibility",
    "DANFORM_OT_delete_control",
    "DANFORM_OT_hide_selected",
    "DANFORM_OT_reveal",
    "DANFORM_OT_remove_controller",
    "DANFORM_OT_remove",
    "DANFORM_OT_reset",
    "DANFORM_OT_reset_source",
    "DANFORM_OT_unbind_orphaned_owned_object",
    "DANFORM_OT_topology_locked",
    "DANFORM_OT_deform",
    "DANFORM_OT_cancel_deform",
    "DANFORM_OT_reveal_controller",
    "DANFORM_OT_toggle_viewport_controls",
    "DANFORM_OT_focus_source",
    "DANFORM_OT_focus_controller",
    "_ui_item_name_update",
    "_ui_control_index_update",
    "_register_topology_keymaps",
    "_unregister_topology_keymaps",
    "_register_control_keymaps",
    "_unregister_control_keymaps",
]
