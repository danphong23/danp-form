"""DANP Form Blender operators, picking and sidebar classes."""

from __future__ import annotations

import json
import math
import uuid
from types import SimpleNamespace

import bmesh
import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from mathutils import Euler, Matrix, Vector

from .constants import *
from . import runtime
from .core.operation import OperationTransform


# Helper names used by operator methods are bound to the facade at register time.
def bind(api) -> None:
    for name in dir(api):
        if name.startswith("_") or name.startswith("DANFORM_"):
            globals()[name] = getattr(api, name)


def _friendly_error(exc: Exception) -> str:
    """Translate stable machine errors into short recovery actions."""
    code = str(exc)
    if code in {"STALE_MAPPING", "TOPOLOGY_CHANGED"}:
        # STALE_MAPPING remains an accepted legacy diagnostic from old files;
        # users should see the recovery action, never an implementation code.
        return "DANP tạm dừng: topology mesh đã thay đổi. Undo để khôi phục mapping hoặc Reset DANP để tạo control mới."
    if code == "SOURCE_ID_LAYERS_MISSING":
        return "DANP không tìm thấy ID mesh. Hãy Sync hoặc Reset DANP trên mesh hiện tại."
    if code.startswith("CONTROL_DATA_INVALID"):
        return "Dữ liệu control bị lỗi; hãy Undo hoặc Reset DANP để tạo lại control trên mesh hiện tại."
    if code == "OPERATION_BUSY":
        return "Đang có thao tác G/R/S; hãy xác nhận hoặc hủy thao tác trước."
    if code == "OPERATION_STALE":
        return "Phiên chỉnh sửa đã cũ; hãy xác nhận/hủy thao tác rồi bắt đầu lại."
    if code == "WORLD_SPACE_MATRIX_REQUIRED":
        return "Transform WORLD cần ma trận Source; hãy dùng transform Source-local của DANP."
    if code == "SHAPE_KEY_LOCKED":
        return "Shape Key đang chọn bị khóa. Hãy mở khóa key rồi chọn Edit Control."
    if code == "SHAPE_KEY_TARGET_INVALID":
        return "Shape Key đích không còn hợp lệ. Hãy chọn lại key trên Source."
    if code in {"SHAPE_KEY_TARGET_CHANGED", "OPERATION_STALE_SHAPE_KEY"}:
        return "Shape Key đã đổi trong lúc thao tác; DANP đã hủy lần kéo này."
    if code in {"UUID_CONFLICT", "CONTROLLER_CONFLICT"}:
        return "DANP phát hiện nhiều cặp trùng hoặc Controller không rõ chủ sở hữu. Hãy chọn cặp cần giữ và tách danh tính trước khi sửa."
    if code == "SHARED_DATA":
        return "Mesh hoặc Controller đang dùng chung dữ liệu. Hãy Make Single User trước khi chỉnh bằng DANP."
    return code


_SOURCE_DANP_KEYS = (
    SOURCE_UUID_KEY, SCHEMA_KEY, CONTROLS_KEY, HIDDEN_VIDS_KEY,
    HIDDEN_EIDS_KEY, NEXT_VID_KEY, NEXT_EID_KEY, TOPOLOGY_KEY,
    NETWORK_REVISION_KEY, ORIGINAL_POSITIONS_KEY, ORIGINAL_TOPOLOGY_KEY,
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


class DANFORM_OT_initialize(bpy.types.Operator):
    bl_idname = "dan_form.initialize"
    bl_label = "Initialize DANP Form"
    bl_description = "Bind the selected mesh as a DANP Form Source and create its controller"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        active = context.view_layer.objects.active
        return _is_valid_source(active) and active.get(CONTROLLER_KEY) is None and active.mode in {"OBJECT", "EDIT"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        scene = context.scene
        source = context.view_layer.objects.active
        try:
            _reconcile_duplicate_bindings()
            _require_structural_idle(source)
            if not _is_valid_source(source):
                raise ValueError("SOURCE_NOT_EDITABLE")
            binding = _binding_status(source)
            if binding == "DUPLICATE_UNBOUND":
                _clear_duplicate_source_state(source)
            elif binding == "UUID_CONFLICT" and not _controller_children(source):
                # With no child Controller, the selected mesh can be explicitly
                # initialized as a clean independent Source; sibling objects
                # keep their own stored data and geometry.
                _clear_duplicate_source_state(source)
            elif binding in {"UUID_CONFLICT", "CONTROLLER_CONFLICT", "SHARED_DATA"}:
                raise ValueError(binding)
            controller = _find_controller(source)
            if controller is None:
                _ensure_source_ids(source)
                _source_uuid(source)
                _capture_original_snapshot(source)
                mesh = bpy.data.meshes.new(f"DANPFORM_CTRL_{source.name}")
                mesh.from_pydata([], [], [])
                mesh.update()
                controller = bpy.data.objects.new(f"DANPFORM_CTRL_{source.name}", mesh)
                _controller_collection(source, scene).objects.link(controller)
                controller[CONTROLLER_KEY] = source[ SOURCE_UUID_KEY ]
                controller[SCHEMA_KEY] = SCHEMA_VERSION
                controller["dan_form_source_name"] = source.name
                controller.display_type = "WIRE"
                controller.hide_render = True
                _rebuild_proxy(source, controller)
            else:
                _migrate_control_schema(source)
                _validate_source_topology(source)
                _guard_proxy_topology(source, controller)
                _capture_original_snapshot(source)
            source["dan_form_controller_name"] = controller.name
            source.pop(UNBOUND_COPY_KEY, None)
            _remember_binding(source, controller)
            _set_scene_context(context, source, controller)
            scene.dan_form_status = f"Ready: {source.name} / {controller.name}"
            self.report({"INFO"}, "DANP Form controller ready")
            return {"FINISHED"}
        except ValueError as exc:
            scene.dan_form_status = _friendly_error(exc)
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}


class DANFORM_OT_resolve_duplicate_pair(bpy.types.Operator):
    bl_idname = "dan_form.resolve_duplicate_pair"
    bl_label = "Keep This DANP Pair"
    bl_description = "Keep the selected Source/Controller relationship and assign a unique DANP identity"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        active = context.view_layer.objects.active
        if active is None or active.type != "MESH":
            return False
        source = active.parent if active.get(CONTROLLER_KEY) is not None else active
        return (
            source is not None and source.type == "MESH"
            and _binding_status(source) in {"UUID_CONFLICT", "CONTROLLER_CONFLICT"}
        )

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        active = context.view_layer.objects.active
        source = active.parent if active.get(CONTROLLER_KEY) is not None else active
        try:
            candidates = _controller_children(source)
            controller = active if active.get(CONTROLLER_KEY) is not None else None
            if controller is None:
                if len(candidates) != 1:
                    raise ValueError("CONTROLLER_CONFLICT")
                controller = candidates[0]
            if controller.parent != source or controller not in candidates:
                raise ValueError("CONTROLLER_CONFLICT")
            if getattr(source.data, "users", 1) > 1 or getattr(controller.data, "users", 1) > 1:
                raise ValueError("SHARED_DATA")
            source_uuid = str(source.get(SOURCE_UUID_KEY, ""))
            if not source_uuid:
                raise ValueError("CONTROLLER_CONFLICT")

            # The active Controller is an explicit choice when a Source has
            # several children. Detach other DANP-marked children while keeping
            # their visible world transforms and mesh data intact.
            for other in candidates:
                if other == controller:
                    continue
                world = other.matrix_world.copy()
                other.parent = None
                other.matrix_world = world
                other[UNBOUND_COPY_KEY] = True

            new_uuid = uuid.uuid4().hex
            while _source_objects_by_uuid(new_uuid):
                new_uuid = uuid.uuid4().hex
            source[SOURCE_UUID_KEY] = new_uuid
            source.pop(UNBOUND_COPY_KEY, None)
            controller[CONTROLLER_KEY] = new_uuid
            source["dan_form_controller_name"] = controller.name
            controller["dan_form_source_name"] = source.name
            for obj in bpy.data.objects:
                if obj.parent == source and obj.get(FACE_SOURCE_UUID_KEY) == source_uuid:
                    obj[FACE_SOURCE_UUID_KEY] = new_uuid
            for key, record in list(runtime.BINDING_OWNERS.items()):
                if record[0] == source.as_pointer():
                    runtime.BINDING_OWNERS.pop(key, None)
            _remember_binding(source, controller)
            _set_scene_context(context, source, controller)
            context.scene.dan_form_status = f"DANP pair resolved: {source.name}"
            self.report({"INFO"}, "Đã giữ cặp DANP được chọn và cấp danh tính riêng")
            return {"FINISHED"}
        except ValueError as exc:
            context.scene.dan_form_status = _friendly_error(exc)
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}


class DANFORM_OT_sync(bpy.types.Operator):
    bl_idname = "dan_form.sync_proxy"
    bl_label = "Sync Proxy"
    bl_description = "Refresh controller coordinates from the Source mesh"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        try:
            _require_structural_idle(source)
            if not _is_valid_source(source) or controller is None:
                raise ValueError("SOURCE_OR_CONTROLLER_MISSING")
            _ensure_source_ids(source)
            _sync_proxy(source, controller)
            _set_scene_context(context, source, controller)
            context.scene.dan_form_status = f"Synced: {controller.name}"
            return {"FINISHED"}
        except ValueError as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}


def _ui_item_name_update(item, context: bpy.types.Context) -> None:
    if runtime.UI_SYNC_GUARD:
        return
    source = _find_source_by_uuid(item.source_uuid)
    controls = _controls(source) if source is not None else []
    control = next((entry for entry in controls if entry.get("control_uuid") == item.control_uuid), None)
    if source is None or control is None:
        return
    new_name = item.control_name.strip()
    if not new_name:
        runtime.UI_SYNC_GUARD = True
        try:
            item.control_name = str(control.get("name", "Control"))
        finally:
            runtime.UI_SYNC_GUARD = False
        return
    if new_name != control.get("name"):
        control["name"] = new_name
        _json_set(source, CONTROLS_KEY, controls)
        if context is not None and getattr(context, "scene", None) is not None:
            context.scene.dan_form_selected_control = item.control_uuid
            context.scene.dan_form_status = f"Renamed: {new_name}"


def _ui_control_index_update(scene, context: bpy.types.Context) -> None:
    if runtime.UI_SYNC_GUARD or context is None:
        return
    source, controller = _context_source(context)
    if source is None:
        return
    index = scene.dan_form_control_index
    items = scene.dan_form_control_items
    if not 0 <= index < len(items) or items[index].source_uuid != source.get(SOURCE_UUID_KEY):
        return
    control = _control(source, items[index].control_uuid)
    if control is None:
        return
    if controller is not None:
        try:
            _transform_session.finalize_active(source, controller, _workflow_dependencies())
        except (ValueError, RuntimeError, KeyError):
            scene.dan_form_status = "Không thể chốt thao tác điều khiển trước khi đổi control"
            return
    scene.dan_form_selected_control = control["control_uuid"]
    _ACTIVE_CONTROL_UUIDS[items[index].source_uuid] = control["control_uuid"]
    active = context.view_layer.objects.active
    try:
        if active == source and source.mode == "EDIT":
            _select_source_ids(source, set(control.get("vertex_ids", [])), set(control.get("edge_ids", [])))
        elif active == controller and controller.mode == "EDIT":
            vertex_ids, edge_ids = _control_effective(source, control)
            _select_proxy_ids(controller, vertex_ids, edge_ids)
    except (ValueError, RuntimeError):
        pass
    _tag_viewport_redraw(context)


class DANFORM_PG_ControlItem(bpy.types.PropertyGroup):
    control_uuid: StringProperty(options={"HIDDEN"})
    source_uuid: StringProperty(options={"HIDDEN"})
    control_name: StringProperty(name="Control Name", update=_ui_item_name_update)
    state: StringProperty(options={"HIDDEN"})
    effective_count: IntProperty(options={"HIDDEN"})
    total_count: IntProperty(options={"HIDDEN"})


class DANFORM_UL_controls(bpy.types.UIList):
    bl_idname = "DANFORM_UL_controls"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        row = layout.row(align=True)
        toggle = row.operator(
            "dan_form.set_control_visibility",
            text="",
            icon="HIDE_ON" if item.state == "Hidden" else "HIDE_OFF",
        )
        toggle.control_uuid = item.control_uuid
        # The eye toggles the whole definition.  A Partial definition is
        # still enabled; hiding it keeps its partial masks so a second click
        # restores the same effective membership.  A fully masked definition
        # is revealed explicitly by ``mutate_control_visibility``.
        toggle.reveal = item.state == "Hidden"
        row.prop(item, "control_name", text="", emboss=False)
        if item.state == "Partial":
            row.label(text="~")


class DANFORM_OT_sync_control(bpy.types.Operator):
    bl_idname = "dan_form.sync_control"
    bl_label = "Sync Control Membership"
    bl_description = "Replace the active control membership from the current edit selection"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        source, _ = _context_source(context)
        active = context.view_layer.objects.active
        return source is not None and active == source and source.mode == "EDIT" and _active_control(context, source) is not None

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        try:
            _require_structural_idle(source)
        except ValueError as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}
        controls = _controls(source) if source is not None else []
        active_control = _active_control(context, source) if source is not None else None
        control = next((item for item in controls if active_control is not None and item.get("control_uuid") == active_control.get("control_uuid")), None)
        active = context.view_layer.objects.active
        if source is None or control is None or active != source or source.mode != "EDIT":
            self.report({"ERROR"}, "SOURCE_EDIT_MODE_REQUIRED")
            return {"CANCELLED"}
        try:
            vertex_ids, edge_ids = _source_selection(source)
            if not vertex_ids and not edge_ids:
                self.report({"ERROR"}, "EMPTY_SELECTION")
                return {"CANCELLED"}
            old_membership = (
                sorted(int(value) for value in control.get("vertex_ids", [])),
                sorted(int(value) for value in control.get("edge_ids", [])),
            )
            new_membership = (sorted(vertex_ids), sorted(edge_ids))
            if old_membership == new_membership:
                context.scene.dan_form_status = "Control membership unchanged"
                return {"FINISHED"}
            control["vertex_ids"] = new_membership[0]
            control["edge_ids"] = new_membership[1]
            _json_set(source, CONTROLS_KEY, controls)
            _prune_masks_after_remove(source)
            _update_revision(source)
            if controller is not None:
                _rebuild_proxy(source, controller)
                _sync_proxy(source, controller)
            _set_scene_context(context, source, controller)
            context.scene.dan_form_status = f"Synced {control.get('name', 'Control')}"
            _sync_context_ui_list(context)
            return {"FINISHED"}
        except (ValueError, RuntimeError) as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}


class DANFORM_OT_move_control(bpy.types.Operator):
    bl_idname = "dan_form.move_control"
    bl_label = "Move Control"
    bl_description = "Reorder the active control definition"
    bl_options = {"REGISTER", "UNDO"}
    direction: IntProperty(default=1, options={"HIDDEN"})

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        try:
            _require_structural_idle(source)
        except ValueError as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}
        if source is None:
            return {"CANCELLED"}
        controls = _controls(source)
        active_control = _active_control(context, source)
        if active_control is None:
            return {"CANCELLED"}
        index = next((i for i, item in enumerate(controls) if item.get("control_uuid") == active_control.get("control_uuid")), -1)
        target = index + (1 if self.direction > 0 else -1)
        if index < 0 or target < 0 or target >= len(controls):
            return {"CANCELLED"}
        controls[index], controls[target] = controls[target], controls[index]
        _json_set(source, CONTROLS_KEY, controls)
        _set_scene_context(context, source, controller)
        context.scene.dan_form_selected_control = active_control.get("control_uuid", "")
        _sync_context_ui_list(context)
        context.scene.dan_form_status = "Control order updated"
        return {"FINISHED"}


class DANFORM_MT_control_menu(bpy.types.Menu):
    bl_idname = "DANFORM_MT_control_menu"
    bl_label = "Control Menu"

    def draw(self, context):
        layout = self.layout
        source, _ = _context_source(context)
        layout.operator("dan_form.select_control", text="Select Active", icon="RESTRICT_SELECT_OFF")
        if source is not None and context.view_layer.objects.active == source and source.mode == "EDIT":
            layout.operator("dan_form.sync_control", text="Sync Membership", icon="FILE_REFRESH")
        layout.separator()
        layout.operator("dan_form.reveal", text="Reveal All", icon="HIDE_OFF")
        layout.operator("dan_form.hide_selected", text="Hide Selected", icon="HIDE_ON")
        layout.separator()
        layout.prop(context.scene, "dan_form_overlay_enabled", text="Control Overlay")
        if context.view_layer.objects.active == source:
            layout.prop(context.scene, "dan_form_patches_enabled", text="Show Patches")
        layout.prop(context.scene, "dan_form_overlay_xray", text="X-Ray")
        if context.view_layer.objects.active == source:
            layout.prop(context.scene, "dan_form_overlay_hidden", text="Preview Hidden Controls")


class DANFORM_MT_manage(bpy.types.Menu):
    bl_idname = "DANFORM_MT_manage"
    bl_label = "Manage DANP Form"

    def draw(self, _context):
        layout = self.layout
        layout.operator(DANFORM_OT_reset.bl_idname, text="Reset DANP Controls", icon="FILE_REFRESH")
        layout.separator()
        layout.operator(DANFORM_OT_remove.bl_idname, text="Remove DANP Form", icon="TRASH")


class DANFORM_OT_create_control(bpy.types.Operator):
    bl_idname = "dan_form.create_control"
    bl_label = "Make Control from Source Selection"
    bl_description = "Create a Source-backed control from selected Source vertices and edges"
    bl_options = {"REGISTER", "UNDO"}
    control_name: StringProperty(name="Control Name", default="", options={"HIDDEN"})
    # Agent-facing metadata.  The UI may leave these empty; keeping them on the
    # definition makes left/right and semantic region explicit instead of
    # forcing callers to encode meaning in a display name.
    side: StringProperty(name="Side", default="", options={"HIDDEN"})
    region: StringProperty(name="Region", default="", options={"HIDDEN"})

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        source, _ = _context_source(context)
        active = context.view_layer.objects.active
        return source is not None and active == source and source.mode == "EDIT" and bool(source.get(SOURCE_UUID_KEY))

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        scene = context.scene
        try:
            _require_structural_idle(source)
            active = context.view_layer.objects.active
            if active == source:
                vertex_ids, edge_ids = _source_selection(source)
            else:
                raise ValueError("SOURCE_EDIT_MODE_REQUIRED")
            if not vertex_ids and not edge_ids:
                raise ValueError("EMPTY_SELECTION")
            controls = _controls(source)
            name = self.control_name.strip() or f"Control {len(controls) + 1}"
            # Names are display metadata, but duplicates make agent/UI
            # reconciliation ambiguous. Keep the requested label when unique
            # and add a deterministic suffix otherwise.
            existing_names = {str(item.get("name", "")).casefold() for item in controls}
            base_name = name
            suffix = 2
            while name.casefold() in existing_names:
                name = f"{base_name} ({suffix})"
                suffix += 1
            definition = {
                "control_uuid": uuid.uuid4().hex,
                "name": name,
                "vertex_ids": sorted(vertex_ids),
                "edge_ids": sorted(edge_ids),
                "enabled": True,
                "hidden_vertex_ids": [],
                "hidden_edge_ids": [],
            }
            side = self.side.strip().upper()
            region = self.region.strip().upper()
            if side:
                if side not in {"LEFT", "RIGHT", "CENTER", ""}:
                    raise ValueError("INVALID_CONTROL_SIDE")
                definition["side"] = side
            if region:
                definition["region"] = region
            controls.append(definition)
            _json_set(source, CONTROLS_KEY, controls)
            _update_revision(source)
            controller = controller or _find_controller(source)
            if controller is None:
                raise ValueError("CONTROLLER_MISSING")
            _rebuild_proxy(source, controller)
            _sync_proxy(source, controller)
            _set_scene_context(context, source, controller)
            scene.dan_form_selected_control = controls[-1]["control_uuid"]
            scene.dan_form_status = f"Created {controls[-1]['name']} ({len(vertex_ids)}V/{len(edge_ids)}E)"
            _sync_context_ui_list(context)
            self.report({"INFO"}, scene.dan_form_status)
            return {"FINISHED"}
        except ValueError as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}


class DANFORM_OT_rename_control(bpy.types.Operator):
    bl_idname = "dan_form.rename_control"
    bl_label = "Rename Control"
    bl_description = "Rename a control definition without changing its geometry"
    bl_options = {"REGISTER", "UNDO"}
    control_uuid: StringProperty(default="")
    new_name: StringProperty(name="Name", default="")

    def invoke(self, context, event):
        source, _ = _context_source(context)
        control = _control(source, self.control_uuid)
        self.new_name = control.get("name", "") if control else ""
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        controls = _controls(source)
        control = next((item for item in controls if item.get("control_uuid") == self.control_uuid), None)
        if source is None or control is None or not self.new_name.strip():
            return {"CANCELLED"}
        control["name"] = self.new_name.strip()
        _json_set(source, CONTROLS_KEY, controls)
        _set_scene_context(context, source, controller)
        context.scene.dan_form_selected_control = self.control_uuid
        context.scene.dan_form_status = f"Renamed: {control['name']}"
        _sync_context_ui_list(context)
        return {"FINISHED"}


class DANFORM_OT_select_control(bpy.types.Operator):
    bl_idname = "dan_form.select_control"
    bl_label = "Select Control"
    bl_description = "Select this definition in the current Source or controller edit context"
    bl_options = {"REGISTER", "UNDO"}
    control_uuid: StringProperty(default="")
    add_to_selection: BoolProperty(name="Add to Selection", default=False)

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        if not self.control_uuid and source is not None:
            active_control = _active_control(context, source)
            self.control_uuid = active_control.get("control_uuid", "") if active_control else ""
        control = _control(source, self.control_uuid)
        if source is None or control is None:
            return {"CANCELLED"}
        active = context.view_layer.objects.active
        try:
            if controller is not None:
                _transform_session.finalize_active(source, controller, _workflow_dependencies())
            vertex_ids = {int(value) for value in control.get("vertex_ids", [])}
            edge_ids = {int(value) for value in control.get("edge_ids", [])}
            context.scene.dan_form_selected_control = self.control_uuid
            if active == source and source.mode == "EDIT":
                _select_source_ids(source, vertex_ids, edge_ids, self.add_to_selection)
            elif active == controller and controller.mode == "EDIT":
                effective_vertices, effective_edges = _control_effective(source, control)
                _select_proxy_ids(controller, effective_vertices, effective_edges, self.add_to_selection)
            elif active == source and source.mode == "OBJECT":
                _select_only(context, source)
                bpy.ops.object.mode_set(mode="EDIT")
                _select_source_ids(source, vertex_ids, edge_ids, self.add_to_selection)
            else:
                raise ValueError("EDIT_SOURCE_OR_CONTROLLER_REQUIRED")
            context.scene.dan_form_status = f"Selected {control.get('name', 'Control')}"
            return {"FINISHED"}
        except ValueError as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}


class DANFORM_OT_set_control_visibility(bpy.types.Operator):
    bl_idname = "dan_form.set_control_visibility"
    bl_label = "Hide/Reveal Control"
    bl_description = "Hide or reveal one definition using canonical Source masks"
    bl_options = {"REGISTER", "UNDO"}
    control_uuid: StringProperty(default="")
    reveal: BoolProperty(default=False)

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        try:
            _require_structural_idle(source)
        except ValueError as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}
        control = _control(source, self.control_uuid)
        if source is None or control is None:
            return {"CANCELLED"}
        active = context.view_layer.objects.active
        was_controller_edit = active == controller and controller.mode == "EDIT"
        try:
            changed = _mutate_control_visibility(source, control, self.reveal)
            if changed:
                _rebuild_proxy(source, controller)
            _set_scene_context(context, source, controller)
            context.scene.dan_form_selected_control = self.control_uuid
            context.scene.dan_form_status = ("Revealed " if self.reveal else "Hidden ") + control.get("name", "Control")
            if was_controller_edit and controller.name in bpy.data.objects:
                effective_vertices, effective_edges = _control_effective(source, control)
                _select_proxy_ids(controller, effective_vertices, effective_edges)
            _sync_context_ui_list(context)
            return {"FINISHED"}
        except (ValueError, RuntimeError) as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}


class DANFORM_OT_delete_control(bpy.types.Operator):
    bl_idname = "dan_form.delete_control"
    bl_label = "Delete Control"
    bl_description = "Remove only this definition and preserve shared Source geometry"
    bl_options = {"REGISTER", "UNDO"}
    control_uuid: StringProperty(default="")

    @classmethod
    def poll(cls, context):
        source, controller = _context_source(context)
        active = context.view_layer.objects.active
        return (
            source is not None
            and active in {source, controller}
            and active is not None
            and active.mode in {"OBJECT", "EDIT"}
            and bool(_controls(source))
        )

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        try:
            _require_structural_idle(source)
        except ValueError as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}
        if source is None:
            return {"CANCELLED"}
        if not self.control_uuid:
            active_control = _active_control(context, source)
            self.control_uuid = active_control.get("control_uuid", "") if active_control else ""
        controls = _controls(source)
        deleted_index = next((i for i, item in enumerate(controls) if item.get("control_uuid") == self.control_uuid), -1)
        remaining = [item for item in controls if item.get("control_uuid") != self.control_uuid]
        if deleted_index < 0:
            return {"CANCELLED"}
        _json_set(source, CONTROLS_KEY, remaining)
        _prune_masks_after_remove(source)
        _update_revision(source)
        if controller is not None:
            _rebuild_proxy(source, controller)
        _set_scene_context(context, source, controller)
        context.scene.dan_form_selected_control = ""
        context.scene.dan_form_status = "Control deleted"
        _sync_context_ui_list(context)
        if context.scene.dan_form_control_items:
            context.scene.dan_form_control_index = min(
                deleted_index, len(context.scene.dan_form_control_items) - 1
            )
        return {"FINISHED"}


class DANFORM_OT_hide_selected(bpy.types.Operator):
    bl_idname = "dan_form.hide_selected"
    bl_label = "Hide Selected Control"
    bl_description = "Release selected proxy vertices or edges from control constraints"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        _, controller = _context_source(context)
        return controller is not None and context.view_layer.objects.active == controller and controller.mode == "EDIT"

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        try:
            _require_structural_idle(source)
            vertex_ids, edge_ids = _proxy_selection(controller)
            if context.tool_settings.mesh_select_mode[1]:
                # Edge endpoints are incidental selection, not explicit node Hide.
                endpoints = {vid for eid in edge_ids for vid in _source_edge_vids(source).get(eid, ())}
                vertex_ids.difference_update(endpoints)
            else:
                edge_ids.clear()
            active_control = _active_control(context, source)
            if active_control is not None:
                changed = _mutate_control_masks(
                    source, active_control, vertex_ids, edge_ids, reveal=False
                )
            else:
                changed = _mutate_masks(source, vertex_ids, edge_ids, reveal=False)
            if changed:
                _rebuild_proxy(source, controller)
                context.scene.dan_form_status = f"Hidden {len(vertex_ids)}V/{len(edge_ids)}E"
            else:
                context.scene.dan_form_status = "No visibility change"
            _set_scene_context(context, source, controller)
            if controller.mode == "EDIT":
                _select_proxy_ids(controller, vertex_ids - _hidden(source, HIDDEN_VIDS_KEY), edge_ids - _hidden(source, HIDDEN_EIDS_KEY))
            return {"FINISHED"}
        except ValueError as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}


class DANFORM_OT_reveal(bpy.types.Operator):
    bl_idname = "dan_form.reveal"
    bl_label = "Reveal Controls"
    bl_description = "Reveal all controls, or Source IDs supplied in ids_json"
    bl_options = {"REGISTER", "UNDO"}
    ids_json: StringProperty(name="IDs JSON", default="")

    @classmethod
    def poll(cls, context):
        source, controller = _context_source(context)
        active = context.view_layer.objects.active
        return source is not None and controller is not None and active.mode in {"OBJECT", "EDIT"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        try:
            _require_structural_idle(source)
            payload = json.loads(self.ids_json) if self.ids_json else {}
            vertex_ids = {int(item) for item in payload.get("vertex_ids", [])}
            edge_ids = {int(item) for item in payload.get("edge_ids", [])}
            changed = _mutate_masks(source, vertex_ids, edge_ids, reveal=True)
            if changed:
                _rebuild_proxy(source, controller)
            context.scene.dan_form_status = "Revealed all" if not vertex_ids and not edge_ids else "Revealed selection"
            _set_scene_context(context, source, controller)
            return {"FINISHED"}
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.report({"ERROR"}, f"INVALID_REVEAL_IDS: {exc}")
            return {"CANCELLED"}


class DANFORM_OT_remove_controller(bpy.types.Operator):
    bl_idname = "dan_form.remove_controller"
    bl_label = "Remove Controller"
    bl_description = "Remove only the DANP Form controller object; keep Source definitions"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        source, controller = _context_source(context)
        return source is not None and controller is not None

    def execute(self, context: bpy.types.Context) -> set[str]:
        scene = context.scene
        source, controller = _context_source(context)
        try:
            _require_structural_idle(source)
        except ValueError as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}
        if controller is None or controller.name not in bpy.data.objects:
            scene.dan_form_controller = None
            scene.dan_form_status = "No controller"
            return {"CANCELLED"}
        if controller.mode == "EDIT":
            bpy.ops.object.mode_set(mode="OBJECT")
            _select_only(context, source)
        _discard_source_runtime(source)
        mesh = controller.data
        _PROXY_SNAPSHOTS.pop(controller.as_pointer(), None)
        bpy.data.objects.remove(controller, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        _set_scene_context(context, source, None)
        scene.dan_form_status = f"Source ready: {source.name}" if source else "No controller"
        self.report({"INFO"}, "Controller removed; Source definitions preserved")
        return {"FINISHED"}


class DANFORM_OT_remove(bpy.types.Operator):
    bl_idname = "dan_form.remove"
    bl_label = "Remove DANP Form"
    bl_description = "Gỡ controller và toàn bộ thiết lập DANP Form; giữ nguyên hình học model"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        source, _ = _context_source(context)
        return source is not None and context.view_layer.objects.active == source and source.mode in {"OBJECT", "EDIT"} and bool(source.get(SOURCE_UUID_KEY)) and _is_valid_source(source)

    def execute(self, context):
        source, controller = _context_source(context)
        try:
            _require_structural_idle(source)
        except ValueError as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}
        if not self.poll(context):
            return {"CANCELLED"}
        was_edit = source.mode == "EDIT"
        source_uuid = source.get(SOURCE_UUID_KEY)
        if was_edit:
            bpy.ops.object.mode_set(mode="OBJECT")
        try:
            _discard_source_runtime(source)
            if controller is not None:
                mesh = controller.data
                _PROXY_SNAPSHOTS.pop(controller.as_pointer(), None)
                bpy.data.objects.remove(controller, do_unlink=True)
                if mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
            for name in (VID_ATTR, EID_ATTR):
                attr = source.data.attributes.get(name)
                if attr is not None:
                    source.data.attributes.remove(attr)
            for key in _SOURCE_DANP_KEYS:
                if key in source:
                    del source[key]
            _MAPPING_CACHE.pop(source.as_pointer(), None)
            _NETWORK_CACHE.pop(source.as_pointer(), None)
            _invalidate_patch_cache(source)
            _OVERLAY_CACHE.clear()
            _ACTIVE_CONTROL_UUIDS.pop(source_uuid, None)
            _RETURN_MODES.pop(source_uuid, None)
            for scene in bpy.data.scenes:
                if scene.dan_form_source == source:
                    scene.dan_form_source = None
                    scene.dan_form_controller = None
                if scene.dan_form_ui_source_uuid == source_uuid:
                    _UI_SIGNATURES.pop(scene.as_pointer(), None)
                    _sync_ui_list(scene, None)
            _sync_context_ui_list(context)
            context.scene.dan_form_status = "Đã gỡ DANP Form"
            _tag_viewport_redraw(context)
            self.report({"INFO"}, "Đã gỡ DANP Form; model giữ nguyên")
            return {"FINISHED"}
        finally:
            if was_edit:
                bpy.ops.object.mode_set(mode="EDIT")


class DANFORM_OT_reset(bpy.types.Operator):
    bl_idname = "dan_form.reset"
    bl_label = "Reset DANP Form"
    bl_description = "Discard old control mapping and create a fresh controller for the current mesh topology"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        source, _controller = _context_source(context)
        return (
            source is not None
            and context.view_layer.objects.active == source
            and source.mode in {"OBJECT", "EDIT"}
            and bool(source.get(SOURCE_UUID_KEY))
            and _is_valid_source(source)
        )

    def execute(self, context):
        source, controller = _context_source(context)
        try:
            _require_structural_idle(source)
        except ValueError as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}
        if not self.poll(context):
            return {"CANCELLED"}
        was_edit = source.mode == "EDIT"
        old_uuid = str(source.get(SOURCE_UUID_KEY, ""))
        if was_edit:
            bpy.ops.object.mode_set(mode="OBJECT")
        try:
            _discard_source_runtime(source)
            # Remove only explicitly DANP-owned runtime objects.  Face assets
            # without the ownership marker remain untouched user data.
            owned = [obj for obj in bpy.data.objects
                     if obj.get(FACE_SOURCE_UUID_KEY) == old_uuid]
            if controller is not None:
                owned.append(controller)
            for obj in list(dict.fromkeys(owned)):
                mesh = getattr(obj, "data", None)
                _PROXY_SNAPSHOTS.pop(obj.as_pointer(), None)
                bpy.data.objects.remove(obj, do_unlink=True)
                if mesh is not None and getattr(mesh, "users", 0) == 0 and bpy.data.meshes.get(mesh.name) is mesh:
                    bpy.data.meshes.remove(mesh)
            for name in (VID_ATTR, EID_ATTR):
                attr = source.data.attributes.get(name)
                if attr is not None:
                    source.data.attributes.remove(attr)
            for key in _SOURCE_DANP_KEYS:
                if key in source:
                    del source[key]
            _MAPPING_CACHE.pop(source.as_pointer(), None)
            _NETWORK_CACHE.pop(source.as_pointer(), None)
            _invalidate_patch_cache(source)
            _OVERLAY_CACHE.clear()
            _ACTIVE_CONTROL_UUIDS.pop(old_uuid, None)
            _RETURN_MODES.pop(old_uuid, None)

            _ensure_source_ids(source)
            source_uuid = _source_uuid(source)
            _capture_original_snapshot(source)
            mesh = bpy.data.meshes.new(f"DANPFORM_CTRL_{source.name}")
            mesh.from_pydata([], [], [])
            mesh.update()
            fresh = bpy.data.objects.new(f"DANPFORM_CTRL_{source.name}", mesh)
            _controller_collection(source, context.scene).objects.link(fresh)
            fresh[CONTROLLER_KEY] = source_uuid
            fresh[SCHEMA_KEY] = SCHEMA_VERSION
            fresh["dan_form_source_name"] = source.name
            fresh.display_type = "WIRE"
            fresh.hide_render = True
            _rebuild_proxy(source, fresh)
            _remember_binding(source, fresh)
            source["dan_form_controller_name"] = fresh.name
            _set_scene_context(context, source, fresh)
            _select_only(context, source)
            if was_edit:
                bpy.ops.object.mode_set(mode="EDIT")
            context.scene.dan_form_status = (
                f"Đã reset DANP: tạo mapping mới cho topology hiện tại của {source.name}"
            )
            self.report({"INFO"}, "DANP reset complete; current mesh topology is now the mapping source")
            return {"FINISHED"}
        except (RuntimeError, ValueError) as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}


class DANFORM_OT_unbind_orphaned_owned_object(bpy.types.Operator):
    bl_idname = "dan_form.unbind_stale_object"
    bl_label = "Unbind Stale DANP Object"
    bl_description = "Keep this mesh and its geometry, but remove stale DANP ownership markers"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        active = context.view_layer.objects.active
        return (
            active is not None
            and active.type == "MESH"
            and bool(active.get(ORPHANED_OWNED_KEY))
            and active.mode == "OBJECT"
        )

    def execute(self, context):
        obj = context.view_layer.objects.active
        if not self.poll(context):
            return {"CANCELLED"}
        world = obj.matrix_world.copy()
        obj.parent = None
        obj.matrix_world = world
        obj.pop(CONTROLLER_KEY, None)
        obj.pop(FACE_SOURCE_UUID_KEY, None)
        obj.pop(ORPHANED_OWNED_KEY, None)
        obj[UNBOUND_COPY_KEY] = True
        context.scene.dan_form_status = (
            f"Đã bỏ liên kết DANP cũ trên {obj.name}; mesh và dữ liệu được giữ nguyên"
        )
        self.report({"INFO"}, "Stale DANP ownership removed; mesh data preserved")
        return {"FINISHED"}


class DANFORM_OT_reset_source(bpy.types.Operator):
    bl_idname = "dan_form.reset_source"
    bl_label = "Reset Model"
    bl_description = "Restore the Source mesh to the pose captured when DANP Form was initialized"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        source, _controller = _context_source(context)
        return (
            source is not None
            and context.view_layer.objects.active == source
            and source.mode in {"OBJECT", "EDIT"}
            and bool(source.get(ORIGINAL_POSITIONS_KEY))
        )

    def execute(self, context):
        source, controller = _context_source(context)
        try:
            _require_structural_idle(source)
        except ValueError as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}
        if not self.poll(context):
            return {"CANCELLED"}
        try:
            _validate_source_topology(source)
            if str(source.get(ORIGINAL_TOPOLOGY_KEY, "")) != str(source.get(TOPOLOGY_KEY, "")):
                raise ValueError("ORIGINAL_SNAPSHOT_TOPOLOGY_CHANGED")
            active_key = _active_shape_key(source)
            target_kind = str(source.get(ORIGINAL_TARGET_KIND_KEY, ""))
            provenance = runtime.INIT_TARGET_PROVENANCE.get(source.as_pointer())
            if provenance is None and not target_kind:
                # Legacy snapshots are identifiable as BASE only when the
                # mesh has no Shape Key datablock at all.
                if active_key is None and source.data.shape_keys is None:
                    target_kind = "BASE"
                else:
                    raise ValueError("ORIGINAL_SNAPSHOT_TARGET_PROVENANCE_UNKNOWN")
            if target_kind == "BASE":
                if active_key is not None or source.data.shape_keys is not None:
                    raise ValueError("ORIGINAL_SNAPSHOT_TARGET_MISMATCH")
                target = BASE_MESH_TARGET
            elif target_kind == "KEY":
                if (provenance is None or not provenance.get("valid")
                        or provenance.get("mesh") != source.data.as_pointer()):
                    raise ValueError("ORIGINAL_SNAPSHOT_TARGET_PROVENANCE_UNKNOWN")
                key_reference = provenance.get("reference")
                try:
                    key_pointer = key_reference.as_pointer()
                except (AttributeError, ReferenceError, RuntimeError):
                    raise ValueError("ORIGINAL_SNAPSHOT_TARGET_PROVENANCE_UNKNOWN")
                if key_pointer != provenance.get("key"):
                    raise ValueError("ORIGINAL_SNAPSHOT_TARGET_PROVENANCE_UNKNOWN")
                live_keys = source.data.shape_keys.key_blocks if source.data.shape_keys else ()
                live_stack = tuple((item.as_pointer(), str(item.name)) for item in live_keys)
                if live_stack != provenance.get("stack"):
                    raise ValueError("ORIGINAL_SNAPSHOT_TARGET_PROVENANCE_UNKNOWN")
                proven_key = next((key for key in live_keys
                                   if key.as_pointer() == key_pointer), None)
                if proven_key is None:
                    raise ValueError("ORIGINAL_SNAPSHOT_TARGET_PROVENANCE_UNKNOWN")
                if active_key is None or active_key.as_pointer() != key_pointer:
                    raise ValueError("ORIGINAL_SNAPSHOT_TARGET_MISMATCH")
                target = proven_key
            else:
                raise ValueError("ORIGINAL_SNAPSHOT_TARGET_PROVENANCE_UNKNOWN")
            positions = _original_snapshot(source)
            _workflow_write_source_positions(source, positions, _workflow_dependencies(),
                                             shape_key=target)
            if controller is not None:
                _sync_proxy(source, controller)
            _OVERLAY_CACHE.clear()
            _PATCH_OVERLAY_CACHE.pop(source.as_pointer(), None)
            _set_scene_context(context, source, controller)
            context.scene.dan_form_status = "Đã reset model về dáng gốc lúc Init DANP"
            self.report({"INFO"}, "Source restored to the original Init pose")
            return {"FINISHED"}
        except (RuntimeError, ValueError) as exc:
            if str(exc) == "ORIGINAL_SNAPSHOT_TOPOLOGY_CHANGED":
                message = "Không thể reset dáng gốc vì topology đã đổi; hãy Undo hoặc Reset DANP trước."
            elif str(exc) == "ORIGINAL_SNAPSHOT_TARGET_MISMATCH":
                message = "Snapshot Init thuộc Shape Key khác. Hãy chọn key ban đầu trước khi Reset Model."
            elif str(exc) == "ORIGINAL_SNAPSHOT_TARGET_PROVENANCE_UNKNOWN":
                message = "Không xác minh được Shape Key của snapshot Init cũ. Hãy Reset DANP để tạo snapshot mới an toàn."
            elif str(exc) in {"ORIGINAL_SNAPSHOT_MISSING", "ORIGINAL_SNAPSHOT_INVALID"}:
                message = "Mesh này chưa có snapshot Init; hãy Remove rồi Init DANP lại."
            else:
                message = _friendly_error(exc)
            context.scene.dan_form_status = message
            self.report({"ERROR"}, message)
            return {"CANCELLED"}


class DANFORM_OT_topology_locked(bpy.types.Operator):
    bl_idname = "dan_form.topology_locked"
    bl_label = "Controller Topology Locked"
    bl_description = "Controller chỉ chỉnh vị trí; tạo/xóa đường control trên model"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        source, controller = _context_source(context)
        # Blender's transform modal keymap must receive axis keys directly.
        # Without this guard the controller's topology-lock ``X`` shortcut can
        # consume the first X after G/R/S, forcing users to press it twice.
        native_transform = _transform_session.native_transform_active(context)
        return (
            not native_transform
            and source is not None
            and controller is not None
            and context.view_layer.objects.active == controller
            and controller.mode == "EDIT"
        )

    def execute(self, context):
        self.report({"INFO"}, self.bl_description)
        return {"FINISHED"}


class DANFORM_OT_deform(bpy.types.Operator):
    bl_idname = "dan_form.deform"
    bl_label = "Apply DANP Deformation"
    bl_description = "Move the selected controller vertices and propagate the change through incident patches"
    bl_options = {"REGISTER", "UNDO"}
    delta: bpy.props.FloatVectorProperty(name="Move", size=3, default=(0.0, 0.0, 0.0), subtype="TRANSLATION")
    operation: EnumProperty(name="Operation", items=(("MOVE", "Move", ""), ("ROTATE", "Rotate", ""), ("SCALE", "Scale", "")), default="MOVE", options={"HIDDEN"})
    scale: bpy.props.FloatVectorProperty(name="Scale", size=3, default=(1.0, 1.0, 1.0), subtype="XYZ")
    rotation: bpy.props.FloatVectorProperty(name="Rotation", size=3, default=(0.0, 0.0, 0.0), subtype="EULER")
    profile: EnumProperty(name="Profile", items=(("LINEAR", "Linear", ""), ("SMOOTH", "Smooth", ""), ("UNIFORM", "Uniform", "")), default="LINEAR")
    radius: FloatProperty(name="Radius", default=0.0, min=0.0)
    targets_json: StringProperty(name="Targets JSON", default="", options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        source, controller = _context_source(context)
        return source is not None and controller is not None and controller.mode == "EDIT"

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        self.layout.prop(self, "profile")
        self.layout.prop(self, "radius")
        if self.operation == "MOVE":
            self.layout.prop(self, "delta")
        elif self.operation == "SCALE":
            self.layout.prop(self, "scale")
        else:
            self.layout.prop(self, "rotation")

    def execute(self, context):
        source, controller = _context_source(context)
        if source is None or controller is None:
            return {"CANCELLED"}
        try:
            _deform_begin(source, controller)
            targets = None
            operation_transform = None
            if self.targets_json:
                raw = json.loads(self.targets_json)
                targets = {int(k): Vector(v) for k, v in raw.items()}
            else:
                p0 = _DANP_TRANSACTIONS[source.as_pointer()]["p0"]
                selected = _DANP_TRANSACTIONS[source.as_pointer()]["selected"]
                pivot = sum((p0[v] for v in selected), Vector()) / max(len(selected), 1)
                operation_transform = OperationTransform(
                    operation=self.operation,
                    pivot=tuple(pivot),
                    translation=tuple(self.delta) if self.operation == "MOVE" else (0.0, 0.0, 0.0),
                    rotation=tuple(self.rotation),
                    scale=tuple(self.scale),
                )
            result = _deform_update(
                source, controller, self.delta, self.profile, self.radius, targets,
                operation_transform=operation_transform,
            )
            _deform_commit(source)
            context.scene.dan_form_status = f"Deformed {result['changed_vertices']} vertices"
            _tag_viewport_redraw(context)
            return {"FINISHED"}
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            try:
                if source.as_pointer() in _DANP_TRANSACTIONS:
                    _deform_cancel(source, controller)
            except (ValueError, RuntimeError):
                pass
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}


class DANFORM_OT_cancel_deform(bpy.types.Operator):
    bl_idname = "dan_form.cancel_deform"
    bl_label = "Cancel DANP Deformation"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        source, controller = _context_source(context)
        if source is None or controller is None:
            return {"CANCELLED"}
        try:
            _deform_cancel(source, controller)
            context.scene.dan_form_status = "Deformation cancelled"
            return {"FINISHED"}
        except ValueError as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}


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


def _proxy_segment(controller, seed_id):
    """Return a visible maximal edge span; logical definitions never split it."""
    bm = bmesh.from_edit_mesh(controller.data)
    el = bm.edges.layers.int.get(PROXY_EID_ATTR)
    vl = bm.verts.layers.int.get(PROXY_VID_ATTR)
    if el is None or vl is None:
        raise ValueError("PROXY_MAPPING_MISSING")
    seed = next((e for e in bm.edges if int(e[el]) == seed_id and not e.hide), None)
    if seed is None:
        raise ValueError("VISIBLE_CONTROL_EDGE_REQUIRED")
    edges = {seed}
    for start in seed.verts:
        vert, previous = start, seed
        while len([e for e in vert.link_edges if not e.hide]) == 2:
            following = next(e for e in vert.link_edges if e != previous and not e.hide)
            if following in edges:
                break
            edges.add(following)
            vert, previous = following.other_vert(vert), following
    return ({int(v[vl]) for e in edges for v in e.verts}, {int(e[el]) for e in edges})


def _pick_controller_edge_id(context, event) -> int:
    """Resolve the nearest mapped proxy edge under a View3D mouse position."""
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    from mathutils import Vector

    source, controller = _context_source(context)
    bm = bmesh.from_edit_mesh(controller.data)
    layer = bm.edges.layers.int.get(PROXY_EID_ATTR)
    if layer is None:
        raise ValueError("PROXY_MAPPING_MISSING")
    mouse = Vector((event.mouse_region_x, event.mouse_region_y))
    candidates = []
    for edge in bm.edges:
        if edge.hide:
            continue
        world = [controller.matrix_world @ vertex.co for vertex in edge.verts]
        screen = [location_3d_to_region_2d(context.region, context.region_data, point) for point in world]
        if any(point is None for point in screen):
            continue
        a, b = screen
        delta = b - a
        factor = max(0.0, min(1.0, (mouse - a).dot(delta) / delta.length_squared)) if delta.length_squared else 0.0
        distance = (mouse - (a + factor * delta)).length
        if distance <= 12.0:
            midpoint = world[0].lerp(world[1], factor)
            depth = -(context.region_data.view_matrix @ midpoint).z
            if not _pick_point_visible(context, source, midpoint):
                continue
            candidates.append((distance, depth, int(edge[layer])))
    if not candidates:
        raise ValueError("CONTROL_EDGE_NOT_FOUND")
    return min(candidates)[2]


def _pick_point_visible(context, source, point) -> bool:
    """Use the same opaque Source occlusion policy as the control overlay."""
    if (context.scene.dan_form_overlay_xray or source is None
            or not source.visible_get(view_layer=context.view_layer)
            or context.space_data.shading.type == "WIREFRAME"
            or context.space_data.shading.show_xray):
        return True
    from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_origin_3d

    screen = location_3d_to_region_2d(context.region, context.region_data, point)
    if screen is None:
        return False
    # Clamp orthographic origins to the model's scale to avoid far-clip precision loss.
    scale = max(source.dimensions.length, 1.0)
    origin = region_2d_to_origin_3d(context.region, context.region_data, screen, clamp=scale * 4)
    inv = source.matrix_world.inverted_safe()
    local_origin, local_point = inv @ origin, inv @ point
    ray = local_point - local_origin
    if ray.length < 1e-8:
        return True
    hit, location, _normal, _index = source.ray_cast(local_origin, ray.normalized(), distance=ray.length)
    return not hit or (location - local_point).length <= scale * 1e-4


def _proxy_selection_snapshot(controller: bpy.types.Object) -> tuple[set[int], set[int]]:
    """Capture exact proxy selection flags without applying edge-mode filtering."""
    bm = bmesh.from_edit_mesh(controller.data)
    vid_layer = bm.verts.layers.int.get(PROXY_VID_ATTR)
    eid_layer = bm.edges.layers.int.get(PROXY_EID_ATTR)
    if vid_layer is None or eid_layer is None:
        raise ValueError("PROXY_MAPPING_MISSING")
    return (
        {int(vertex[vid_layer]) for vertex in bm.verts if vertex.select},
        {int(edge[eid_layer]) for edge in bm.edges if edge.select},
    )


def _control_for_edge(source: bpy.types.Object, edge_id: int, scene: bpy.types.Scene | None = None) -> dict:
    candidates = [
        control for control in _controls(source)
        if edge_id in {int(value) for value in control.get("edge_ids", [])}
    ]
    active_uuid = getattr(scene or bpy.context.scene, "dan_form_selected_control", "")
    selected = next((control for control in candidates if control.get("control_uuid") == active_uuid), None)
    if selected is None and len(candidates) == 1:
        selected = candidates[0]
    if selected is None:
        if not candidates:
            raise ValueError("CONTROL_EDGE_NOT_IN_DEFINITION")
        raise ValueError("CONTROL_EDGE_SHARED_SELECT_FROM_LIST")
    return selected


def _selection_target_for_edge(source: bpy.types.Object, controller: bpy.types.Object, edge_id: int, tool: str, scene: bpy.types.Scene | None = None) -> tuple[set[int], set[int], str]:
    """Resolve a hover-picked edge into a segment or whole-control selection."""
    if tool == "SEGMENT":
        vertices, edges = _proxy_segment(controller, edge_id)
        return vertices, edges, ""
    control = _control_for_edge(source, edge_id, scene)
    vertices, edges = _control_effective(source, control)
    if not vertices and not edges:
        raise ValueError("CONTROL_HIDDEN")
    return vertices, edges, control.get("control_uuid", "")


def _view3d_pick_edge(context: bpy.types.Context, event) -> int:
    """Pick in the View3D window even when the modal tool starts from the sidebar."""
    area = context.area if context.area and context.area.type == "VIEW_3D" else None
    if area is None and context.screen is not None:
        area = next((item for item in context.screen.areas if item.type == "VIEW_3D"), None)
    if area is None:
        raise ValueError("VIEW_3D_REQUIRED")
    region = next((item for item in area.regions if item.type == "WINDOW"), None)
    if region is None or area.spaces.active.region_3d is None:
        raise ValueError("VIEW_3D_REQUIRED")
    # Modal events retain the invocation region (UI when started in sidebar).
    # temp_override does not convert event.mouse_region_x/y into WINDOW space.
    if hasattr(event, "mouse_x") and hasattr(event, "mouse_y"):
        event = SimpleNamespace(mouse_region_x=event.mouse_x - region.x,
                                mouse_region_y=event.mouse_y - region.y)
    with context.temp_override(area=area, region=region, region_data=area.spaces.active.region_3d):
        return _pick_controller_edge_id(context, event)


def _apply_proxy_pick_selection(context, controller, vertices, edges, operation="SET") -> None:
    if operation == "ADD":
        _select_proxy_ids(controller, vertices, edges, add=True)
        return
    if operation == "SUBTRACT":
        old_vertices, old_edges = _proxy_selection_snapshot(controller)
        vertices, edges = old_vertices - vertices, old_edges - edges
        if context.tool_settings.mesh_select_mode[1]:
            bm = bmesh.from_edit_mesh(controller.data)
            vl, el = bm.verts.layers.int[PROXY_VID_ATTR], bm.edges.layers.int[PROXY_EID_ATTR]
            vertices.update(int(v[vl]) for e in bm.edges if int(e[el]) in edges for v in e.verts)
    _select_proxy_ids(controller, vertices, edges)


def _set_pick_preview(context, controller, edge_ids) -> None:
    import gpu
    from gpu_extras.batch import batch_for_shader

    view_area = context.area if context.area and context.area.type == "VIEW_3D" else None
    if view_area is None and context.screen is not None:
        view_area = next((area for area in context.screen.areas if area.type == "VIEW_3D"), None)
    if view_area is None:
        _PICK_PREVIEW.clear()
        return
    bm = bmesh.from_edit_mesh(controller.data)
    layer = bm.edges.layers.int[PROXY_EID_ATTR]
    positions = [controller.matrix_world @ v.co for e in bm.edges
                 if int(e[layer]) in edge_ids and not e.hide for v in e.verts]
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    _PICK_PREVIEW.update(controller=controller.as_pointer(), area=view_area.as_pointer(),
                         batch=batch_for_shader(shader, "LINES", {"pos": positions}))
    _tag_viewport_redraw(context)


class DANFORM_OT_pick_selection_tool(bpy.types.Operator):
    bl_idname = "dan_form.pick_selection_tool"
    bl_label = "Pick DANP Selection"
    bl_description = "Hover a control edge to preview a segment or whole-control selection; click to confirm"
    bl_options = {"REGISTER", "UNDO"}
    tool: EnumProperty(
        name="Tool",
        items=(
            ("SEGMENT", "Segment", "Select the visible span between junctions"),
            ("CONTROL", "Control", "Select the whole logical control"),
        ),
        default="SEGMENT",
        options={"HIDDEN"},
    )
    add_to_selection: BoolProperty(name="Add to Selection", default=False, options={"HIDDEN"})

    def _finish(self, context, cancelled=False) -> set[str]:
        if self._session == runtime.PICK_SESSION:
            _PICK_PREVIEW.clear()
            if self._area is not None:
                self._area.header_text_set(None)
        _tag_viewport_redraw(context)
        context.scene.dan_form_status = "Pick stopped" if cancelled else "Selection confirmed"
        return {"FINISHED"} if self._committed or not cancelled else {"CANCELLED"}

    def _in_viewport(self, event) -> bool:
        if self._area is None:
            return False
        x, y = event.mouse_x, event.mouse_y
        for region in self._area.regions:
            if region.type in {"UI", "TOOLS"} and region.width > 0 and region.height > 0:
                if region.x <= x < region.x + region.width and region.y <= y < region.y + region.height:
                    return False
        region = next((r for r in self._area.regions if r.type == "WINDOW"), None)
        return bool(region and region.x <= x < region.x + region.width and region.y <= y < region.y + region.height)

    def _preview(self, context, event) -> None:
        source, controller = _context_source(context)
        if source is None or controller is None:
            return
        try:
            edge_id = _view3d_pick_edge(context, event)
            target = _selection_target_for_edge(source, controller, edge_id, self.tool, context.scene)
        except ValueError as exc:
            _PICK_PREVIEW.clear()
            self._last_target = None
            self._last_edge_id = None
            if str(exc) == "CONTROL_EDGE_SHARED_SELECT_FROM_LIST":
                context.scene.dan_form_status = "Cạnh chung: chọn control trong danh sách trước"
            _tag_viewport_redraw(context)
            return
        if self._last_target is not None and target == self._last_target:
            return
        _set_pick_preview(context, controller, target[1])
        context.scene.dan_form_status = f"Preview: {len(target[1])} edges; click to select"
        self._last_edge_id = edge_id
        self._last_target = target
        for area in context.screen.areas if context.screen else ():
            if area.type == "VIEW_3D":
                area.tag_redraw()

    @classmethod
    def poll(cls, context):
        return DANFORM_OT_topology_locked.poll(context)

    def invoke(self, context, event):
        source, controller = _context_source(context)
        if source is None or controller is None:
            return {"CANCELLED"}
        self.add_to_selection = bool(getattr(event, "shift", False) or context.scene.dan_form_add_to_selection)
        runtime.PICK_SESSION += 1
        self._session = runtime.PICK_SESSION
        self._controller = controller.as_pointer()
        self._generation = controller.get(PROXY_GENERATION_KEY)
        self._area = context.area if context.area and context.area.type == "VIEW_3D" else None
        if self._area is None and context.screen is not None:
            self._area = next((area for area in context.screen.areas if area.type == "VIEW_3D"), None)
        if self._area is None:
            return {"CANCELLED"}
        self._committed = False
        self._navigating = False
        _PICK_PREVIEW.clear()
        self._last_edge_id = None
        self._last_target = None
        context.scene.dan_form_status = (
            f"Hover để xem trước {'đoạn' if self.tool == 'SEGMENT' else 'control'}, click để chọn; Esc để hủy"
        )
        if self._area is not None:
            self._area.header_text_set("DANP Pick: LMB chọn · Shift cộng · Ctrl bỏ chọn · RMB/Esc dừng · MMB/Wheel điều hướng")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        _, controller = _context_source(context)
        if (self._session != runtime.PICK_SESSION or controller is None or controller.mode != "EDIT"
                or controller.as_pointer() != self._controller or controller.get(PROXY_GENERATION_KEY) != self._generation):
            return self._finish(context, cancelled=True)
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            return self._finish(context, cancelled=True)
        if event.type == "MIDDLEMOUSE":
            self._navigating = event.value != "RELEASE"
            _PICK_PREVIEW.clear()
            self._last_target = None
            return {"PASS_THROUGH"}
        if event.type in {"WHEELUPMOUSE", "WHEELDOWNMOUSE", "TRACKPADPAN", "TRACKPADZOOM", "MOUSEROTATE", "MOUSESMARTZOOM"}:
            _PICK_PREVIEW.clear()
            self._last_target = None
            return {"PASS_THROUGH"}
        if event.type == "MOUSEMOVE":
            if self._navigating or not self._in_viewport(event):
                _PICK_PREVIEW.clear()
                self._last_target = None
                return {"PASS_THROUGH"}
            self._preview(context, event)
            return {"PASS_THROUGH"}
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            if not self._in_viewport(event):
                return self._finish(context, cancelled=True) | {"PASS_THROUGH"}
            # Resolve again after zoom/pan or a click without a prior move.
            self._last_target = None
            self._preview(context, event)
            if self._last_target is None:
                return self._finish(context) | {"PASS_THROUGH"}
            operation = "SUBTRACT" if event.ctrl else ("ADD" if event.shift or self.add_to_selection else "SET")
            _apply_proxy_pick_selection(context, controller, self._last_target[0], self._last_target[1], operation)
            if self._last_target[2]:
                context.scene.dan_form_selected_control = self._last_target[2]
                _activate_ui_control(context.scene, self._last_target[2])
            self._committed = True
            _PICK_PREVIEW.clear()
            self._last_target = None
            if self.add_to_selection or event.shift or event.ctrl:
                return {"RUNNING_MODAL"}
            return self._finish(context)
        # A, B, C, G/R/S, Tab, undo and other native commands retain their keys.
        # End preview before dispatch, rather than stealing their mouse events.
        if event.value == "PRESS" and event.type not in {"LEFT_SHIFT", "RIGHT_SHIFT", "LEFT_CTRL", "RIGHT_CTRL", "LEFT_ALT", "RIGHT_ALT", "LEFTMOUSE"}:
            return self._finish(context) | {"PASS_THROUGH"}
        return {"PASS_THROUGH"}


class DANFORM_OT_select_control_at_cursor(bpy.types.Operator):
    bl_idname = "dan_form.select_control_at_cursor"
    bl_label = "Select Control Under Cursor"
    bl_description = "Ctrl+Shift+Click a control edge to select the whole mapped control"
    bl_options = {"REGISTER", "UNDO"}
    edge_id: IntProperty(name="Source Edge ID", default=0, min=0)
    extend: BoolProperty(name="Add to Selection", default=False)

    @classmethod
    def poll(cls, context):
        return DANFORM_OT_topology_locked.poll(context)

    def invoke(self, context, event):
        if event.type != "LEFTMOUSE":
            return self.execute(context)
        if context.region is None or context.region.type != "WINDOW" or context.region_data is None:
            return {"CANCELLED"}
        try:
            # Shift is part of this shortcut itself; it must not force Add.
            self.extend = bool(self.extend or context.scene.dan_form_add_to_selection)
            self.edge_id = _pick_controller_edge_id(context, event)
            return self.execute(context)
        except ValueError as exc:
            self.report({"INFO"}, str(exc))
            return {"CANCELLED"}

    def execute(self, context):
        source, controller = _context_source(context)
        if source is None or controller is None:
            return {"CANCELLED"}
        edge_id = self.edge_id
        if not edge_id:
            bm = bmesh.from_edit_mesh(controller.data)
            layer = bm.edges.layers.int.get(PROXY_EID_ATTR)
            active = bm.select_history.active
            if isinstance(active, bmesh.types.BMEdge) and layer is not None:
                edge_id = int(active[layer])
            else:
                selected = [edge for edge in bm.edges if edge.select]
                if len(selected) == 1 and layer is not None:
                    edge_id = int(selected[0][layer])
        try:
            selected = _control_for_edge(source, edge_id, context.scene)
        except ValueError as exc:
            if str(exc) == "CONTROL_EDGE_SHARED_SELECT_FROM_LIST":
                self.report({"WARNING"}, str(exc))
            else:
                self.report({"INFO"}, str(exc))
            return {"CANCELLED"}
        effective_vertices, effective_edges = _control_effective(source, selected)
        if not effective_vertices and not effective_edges:
            self.report({"INFO"}, "CONTROL_HIDDEN")
            return {"CANCELLED"}
        _select_proxy_ids(controller, effective_vertices, effective_edges, add=self.extend)
        context.scene.dan_form_selected_control = selected.get("control_uuid", "")
        context.scene.dan_form_status = f"Selected {selected.get('name', 'Control')}"
        _sync_context_ui_list(context)
        return {"FINISHED"}


class DANFORM_OT_select_segment(bpy.types.Operator):
    bl_idname = "dan_form.select_segment"
    bl_label = "Select Segment Between Junctions"
    bl_description = "Ctrl+Alt+Click an edge; Shift adds a span. Stop at junctions/endpoints; select a full uncut loop"
    bl_options = {"REGISTER", "UNDO"}
    edge_id: IntProperty(name="Source Edge ID", default=0, min=0)
    extend: BoolProperty(name="Extend Selection", default=False)

    @classmethod
    def poll(cls, context):
        return DANFORM_OT_topology_locked.poll(context)

    def invoke(self, context, event):
        if event.type != "LEFTMOUSE":
            return self.execute(context)
        if context.region is None or context.region.type != "WINDOW" or context.region_data is None:
            return {"CANCELLED"}
        try:
            self.edge_id = _pick_controller_edge_id(context, event)
        except ValueError as exc:
            self.report({"INFO"}, str(exc))
            return {"CANCELLED"}
        context.tool_settings.mesh_select_mode = (False, True, False)
        return self.execute(context)

    def execute(self, context):
        _, controller = _context_source(context)
        seed_id = self.edge_id
        if not seed_id:
            bm = bmesh.from_edit_mesh(controller.data)
            layer = bm.edges.layers.int.get(PROXY_EID_ATTR)
            active = bm.select_history.active
            if isinstance(active, bmesh.types.BMEdge) and layer is not None:
                seed_id = int(active[layer])
            else:
                selected = [e for e in bm.edges if e.select]
                if len(selected) == 1 and layer is not None:
                    seed_id = int(selected[0][layer])
        try:
            vertices, edges = _proxy_segment(controller, seed_id)
            _select_proxy_ids(controller, vertices, edges, add=self.extend)
            context.scene.dan_form_status = f"Selected span: {len(edges)} edges"
            return {"FINISHED"}
        except ValueError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}


class DANFORM_OT_clear_selection(bpy.types.Operator):
    bl_idname = "dan_form.clear_selection"
    bl_label = "Clear Selection"
    bl_description = "Clear the current controller selection without changing control definitions"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return DANFORM_OT_topology_locked.poll(context)

    def execute(self, context):
        _, controller = _context_source(context)
        _select_proxy_ids(controller, set(), set())
        context.scene.dan_form_status = "Controller selection cleared"
        return {"FINISHED"}


class DANFORM_OT_select_all_controls(bpy.types.Operator):
    bl_idname = "dan_form.select_all_controls"
    bl_label = "Select All Controls"
    bl_description = "Select every currently enabled control element"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return DANFORM_OT_topology_locked.poll(context)

    def execute(self, context):
        source, controller = _context_source(context)
        vertices, edges = _effective_proxy_elements(source)
        _select_proxy_ids(controller, vertices, edges)
        context.scene.dan_form_status = f"Selected all controls: {len(edges)} edges"
        return {"FINISHED"}


class DANFORM_OT_reveal_controller(bpy.types.Operator):
    bl_idname = "dan_form.reveal_controller"
    bl_label = "Reveal Hidden Controls"
    bl_description = "Alt+H reveals canonical hidden controls using current Source positions"
    bl_options = {"INTERNAL", "UNDO"}

    @classmethod
    def poll(cls, context):
        return DANFORM_OT_topology_locked.poll(context)

    def execute(self, context):
        return bpy.ops.dan_form.reveal()


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


class DANFORM_OT_toggle_viewport_controls(bpy.types.Operator):
    bl_idname = "dan_form.toggle_viewport_controls"
    bl_label = "Hide/Show Controls"
    bl_description = "Hide or reveal every control, including all list eyes and control constraints"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        source, controller = _context_source(context)
        active = context.view_layer.objects.active
        return source is not None and controller is not None and bool(_controls(source)) and active.mode in {"OBJECT", "EDIT"}

    def execute(self, context):
        source, controller = _context_source(context)
        visible_vertices, visible_edges = _effective_proxy_elements(source)
        hide = bool(visible_vertices or visible_edges)
        if hide:
            edges, nodes = set(), set()
            for control in _controls(source):
                control_edges, control_nodes = _control_intent(source, control)
                edges.update(control_edges)
                nodes.update(control_nodes)
            changed = _mutate_masks(source, nodes, edges, reveal=False)
        else:
            changed = _mutate_masks(source, set(), set(), reveal=True)
        controller.hide_set(False, view_layer=context.view_layer)
        if changed:
            _rebuild_proxy(source, controller)
        _sync_context_ui_list(context)
        context.scene.dan_form_status = "Hidden all controls" if hide else "Revealed all controls"
        _tag_viewport_redraw(context)
        return {"FINISHED"}


class DANFORM_OT_focus_source(bpy.types.Operator):
    bl_idname = "dan_form.focus_source"
    bl_label = "Back to Model"
    bl_description = "Return to the model in the mode used before editing controls"
    # Navigation must not create an undo step.  Undoing a mode switch can
    # restore a different edit context and make the Source/controller bridge
    # appear to reset even after a valid transform was committed.
    bl_options = {"REGISTER"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        if source is None:
            return {"CANCELLED"}
        try:
            active = context.view_layer.objects.active
            if active == controller:
                session = runtime.NATIVE_TRANSFORM_SESSIONS.get(source.as_pointer())
                if session is not None:
                    # Finalize the live controller pose before changing the
                    # active object.  Once the mode changes Blender may no
                    # longer expose the edit BMesh to the observer timer.
                    _transform_session.update(
                        source, controller, _workflow_dependencies(), session,
                        profile=getattr(context.scene, "dan_form_proportional_profile", "LINEAR"),
                        radius=float(getattr(context.scene, "dan_form_proportional_radius", 0.0)),
                    )
                    if session.get("had_delta"):
                        _transform_session.commit(source, _workflow_dependencies())
                    else:
                        _transform_session.cancel(source, controller, _workflow_dependencies())
            if active is not None and active.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            previous_preview = runtime.SHAPE_PREVIEW_STATES.pop(source.as_pointer(), None)
            if previous_preview is not None:
                source.show_only_shape_key = bool(previous_preview)
            _select_only(context, source)
            if _RETURN_MODES.pop(source.get(SOURCE_UUID_KEY), "OBJECT") == "EDIT":
                bpy.ops.object.mode_set(mode="EDIT")
            _set_scene_context(context, source, controller)
            _sync_context_ui_list(context)
            return {"FINISHED"}
        except (RuntimeError, ValueError) as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}


class DANFORM_OT_focus_controller(bpy.types.Operator):
    bl_idname = "dan_form.focus_controller"
    bl_label = "Edit Control"
    bl_description = "Enter controller Edit Mode and select the active control"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        source, controller = _context_source(context)
        active = context.view_layer.objects.active
        return source is not None and controller is not None and bool(_effective_proxy_elements(source)[0]) and active.mode in {"OBJECT", "EDIT"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        if source is None or controller is None:
            return {"CANCELLED"}
        try:
            key = _active_shape_key(source)
            if key is not None and key.lock_shape:
                raise ValueError("SHAPE_KEY_LOCKED")
            active = context.view_layer.objects.active
            if active == source:
                _RETURN_MODES[source.get(SOURCE_UUID_KEY)] = source.mode
            if active is not None and active.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            _sync_proxy(source, controller)
            runtime.SHAPE_PREVIEW_STATES.setdefault(source.as_pointer(), bool(source.show_only_shape_key))
            if key is not None:
                source.show_only_shape_key = True
            controller.hide_set(False, view_layer=context.view_layer)
            _select_only(context, controller)
            bpy.ops.object.mode_set(mode="EDIT")
            control = _active_control(context, source)
            if control is not None:
                vertex_ids, edge_ids = _control_effective(source, control)
                _select_proxy_ids(controller, vertex_ids, edge_ids)
            _guard_proxy_topology(source, controller)
            _set_scene_context(context, source, controller)
            _sync_context_ui_list(context)
            return {"FINISHED"}
        except (RuntimeError, ValueError) as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}


class DANFORM_OT_select_shape_key(bpy.types.Operator):
    bl_idname = "dan_form.select_shape_key"
    bl_label = "Select Shape Key"
    bl_description = "Choose which Source Shape Key DANP Form edits"
    key_index: IntProperty(name="Shape Key Index", min=0)

    @classmethod
    def poll(cls, context):
        source, _controller = _context_source(context)
        return source is not None and source.data.shape_keys is not None

    def execute(self, context):
        source, controller = _context_source(context)
        if source is None or source.data.shape_keys is None:
            return {"CANCELLED"}
        try:
            _require_structural_idle(source)
            blocks = source.data.shape_keys.key_blocks
            if not 0 <= self.key_index < len(blocks):
                raise ValueError("SHAPE_KEY_TARGET_INVALID")
            source.active_shape_key_index = self.key_index
            _sync_proxy(source, controller)
            if controller is not None and controller.mode == "EDIT":
                source.show_only_shape_key = True
            key = _active_shape_key(source)
            context.scene.dan_form_status = f"Đang chỉnh Shape Key: {key.name}"
            _tag_viewport_redraw(context)
            return {"FINISHED"}
        except (RuntimeError, ValueError) as exc:
            context.scene.dan_form_status = _friendly_error(exc)
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}


class DANFORM_MT_shape_keys(bpy.types.Menu):
    bl_label = "Chọn Shape Key"
    bl_idname = "DANFORM_MT_shape_keys"

    def draw(self, context):
        layout = self.layout
        source, _controller = _context_source(context)
        if source is None or source.data.shape_keys is None:
            layout.label(text="Mesh không có Shape Key")
            return
        for index, key in enumerate(source.data.shape_keys.key_blocks):
            op = layout.operator(
                DANFORM_OT_select_shape_key.bl_idname,
                text=key.name,
                icon="LOCKED" if key.lock_shape else "SHAPEKEY_DATA",
                depress=index == source.active_shape_key_index,
            )
            op.key_index = index


class DANFORM_PT_sidebar(bpy.types.Panel):
    bl_label = "DANP Form"
    bl_idname = "DANFORM_PT_sidebar"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DANP Form"
    bl_ui_units_x = 46

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        scene = context.scene
        source, controller = _context_source(context)
        active = context.view_layer.objects.active
        if source is None:
            if active is not None and active.type == "MESH":
                if active.get(ORPHANED_OWNED_KEY):
                    box = layout.box()
                    box.alert = True
                    box.label(text="Object có liên kết DANP cũ chưa xác minh", icon="ERROR")
                    box.label(text="Dữ liệu mesh được giữ; chọn cách bỏ liên kết để dùng riêng")
                    box.operator(
                        DANFORM_OT_unbind_orphaned_owned_object.bl_idname,
                        text="Bỏ liên kết DANP cũ, giữ mesh",
                        icon="UNLINKED",
                    )
                    return
                state_source = active.parent if active.get(CONTROLLER_KEY) is not None else active
                state = _binding_status(state_source)
                if state == "DUPLICATE_UNBOUND":
                    layout.label(text="Bản sao mesh chưa có Controller DANP", icon="INFO")
                    layout.operator(DANFORM_OT_initialize.bl_idname, text="Init DANP Form", icon="ADD")
                    return
                if state in {"UUID_CONFLICT", "CONTROLLER_CONFLICT"}:
                    layout.label(text="Quan hệ DANP đang trùng hoặc chưa rõ", icon="ERROR")
                    if active.get(CONTROLLER_KEY) is not None or len(_controller_children(state_source)) == 1:
                        layout.operator(DANFORM_OT_resolve_duplicate_pair.bl_idname, text="Keep This Pair", icon="LINKED")
                    elif not _controller_children(state_source):
                        layout.label(text="Init mesh này sẽ tạo DANP riêng, control cũ trên mesh này bị xóa")
                        layout.operator(DANFORM_OT_initialize.bl_idname, text="Init Mesh Riêng", icon="ADD")
                    else:
                        layout.label(text="Chọn Controller muốn giữ rồi giải quyết cặp", icon="INFO")
                    return
                if state == "SHARED_DATA":
                    layout.label(text="Mesh/Controller dùng chung dữ liệu", icon="ERROR")
                    layout.label(text="Make Single User trước khi dùng DANP")
                    return
            layout.label(text="Chọn một mesh DANP Form hoặc controller", icon="INFO")
            return
        if active == source:
            lifecycle = layout.row(align=True)
            lifecycle.enabled = source.mode in {"OBJECT", "EDIT"}
            if not source.get(SOURCE_UUID_KEY):
                lifecycle.operator(DANFORM_OT_initialize.bl_idname, text="Init DANP Form", icon="ADD")
            else:
                if controller is None:
                    lifecycle.operator(DANFORM_OT_initialize.bl_idname, text="Rebuild Controller", icon="FILE_REFRESH")
                else:
                    lifecycle.operator(DANFORM_OT_reset_source.bl_idname, text="Reset Model", icon="LOOP_BACK")
                lifecycle.menu(DANFORM_MT_manage.bl_idname, text="Manage", icon="DOWNARROW_HLT")
        if source.get(SOURCE_UUID_KEY) is None:
            return
        topology = _topology_state(source)
        if topology.get("state") == "PAUSED":
            warning = layout.box()
            warning.alert = True
            warning.label(text="DANP tạm dừng: topology đã thay đổi", icon="ERROR")
            warning.label(text="Undo để khôi phục hoặc Reset để tạo mapping mới")
        if controller is None:
            layout.label(text="Nhấn Init để dựng lại controller", icon="INFO")
            return
        key = _active_shape_key(source)
        key_row = layout.row(align=True)
        key_row.label(text="Đang chỉnh:")
        key_row.label(text=key.name if key is not None else "Mesh gốc", icon="SHAPEKEY_DATA" if key is not None else "MESH_DATA")
        if source.data.shape_keys is not None:
            key_row.menu(DANFORM_MT_shape_keys.bl_idname, text="", icon="DOWNARROW_HLT")
        if key is not None and key.lock_shape:
            warning = layout.box()
            warning.alert = True
            warning.label(text=f"Shape Key ‘{key.name}’ đang khóa", icon="LOCKED")
            warning.label(text="Mở khóa key để chỉnh bằng Controller")
        header = layout.row()
        header.label(text=source.name, icon="MESH_DATA")
        if active == source and source.mode == "EDIT":
            header.label(text="Edit Source", icon="EDITMODE_HLT")
        elif active == controller and controller.mode == "EDIT":
            header.label(text="Edit Controller", icon="EDITMODE_HLT")
        else:
            header.label(text="Object", icon="OBJECT_DATA")
        navigation = layout.row(align=True)
        navigation.enabled = active.mode in {"OBJECT", "EDIT"}
        if active == controller:
            navigation.operator(DANFORM_OT_focus_source.bl_idname, text="Back to Model", icon="LOOP_BACK")
        if active != controller or controller.mode == "OBJECT":
            edit_row = navigation.row(align=True)
            edit_row.enabled = key is None or not key.lock_shape
            edit_row.operator(DANFORM_OT_focus_controller.bl_idname, text="Edit Control", icon="EDITMODE_HLT")
        effective_vertices, effective_edges = _effective_proxy_elements(source)
        hidden = not bool(effective_vertices or effective_edges)
        navigation.operator(DANFORM_OT_toggle_viewport_controls.bl_idname, text="Show Controls" if hidden else "Hide Controls", icon="HIDE_ON" if hidden else "HIDE_OFF")
        setup = layout.box()
        setup.label(text="Setup", icon="TOOL_SETTINGS")
        display = setup.row(align=True)
        display.prop(scene, "dan_form_overlay_enabled", text="Overlay")
        if active == source:
            display.prop(scene, "dan_form_patches_enabled", text="Patches")
        display.prop(scene, "dan_form_overlay_xray", text="X-Ray")
        if active == source:
            display.prop(scene, "dan_form_overlay_hidden", text="Preview Hidden")
        if active == controller and controller.mode == "EDIT":
            deform = layout.box()
            deform.label(text="Native G/R/S Proportional", icon="CONSTRAINT_BONE")
            deform.prop(scene, "dan_form_proportional_profile", text="Profile")
            deform.prop(scene, "dan_form_proportional_radius", text="Radius")
        list_row = layout.row(align=True)
        list_row.enabled = active.mode in {"OBJECT", "EDIT"}
        list_row.template_list(
            DANFORM_UL_controls.bl_idname,
            "DANFORM_CONTROLS",
            scene,
            "dan_form_control_items",
            scene,
            "dan_form_control_index",
            rows=5,
            maxrows=5,
        )
        buttons = list_row.column(align=True)
        if active == source:
            buttons.operator(DANFORM_OT_create_control.bl_idname, text="", icon="ADD")
        if active in {source, controller}:
            # Pass the row UUID explicitly. Relying on the scene index alone
            # can race Blender's UIList update after a row click.
            delete = buttons.operator(DANFORM_OT_delete_control.bl_idname, text="", icon="REMOVE")
            selected_item = (
                scene.dan_form_control_items[scene.dan_form_control_index]
                if 0 <= scene.dan_form_control_index < len(scene.dan_form_control_items)
                else None
            )
            delete.control_uuid = (
                selected_item.control_uuid
                if selected_item is not None and selected_item.source_uuid == source.get(SOURCE_UUID_KEY)
                else scene.dan_form_selected_control
            )
        buttons.separator()
        buttons.menu(DANFORM_MT_control_menu.bl_idname, text="", icon="DOWNARROW_HLT")
        buttons.separator()
        move_up = buttons.operator(DANFORM_OT_move_control.bl_idname, text="", icon="TRIA_UP")
        move_up.direction = -1
        move_down = buttons.operator(DANFORM_OT_move_control.bl_idname, text="", icon="TRIA_DOWN")
        move_down.direction = 1
        edit_context = active == source and source.mode == "EDIT"
        if edit_context:
            actions = layout.row(align=True)
            actions.operator(DANFORM_OT_sync_control.bl_idname, text="Sync", icon="FILE_REFRESH")
        elif not scene.dan_form_control_items:
            layout.label(text="Edit Source rồi chọn điểm/cạnh để nhấn +", icon="INFO")


CLASSES = (
    DANFORM_PG_ControlItem,
    DANFORM_UL_controls,
    DANFORM_OT_initialize,
    DANFORM_OT_resolve_duplicate_pair,
    DANFORM_OT_sync,
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
    DANFORM_MT_shape_keys,
    DANFORM_MT_control_menu,
    DANFORM_MT_manage,
    DANFORM_PT_sidebar,
)



__all__ = [
    "bind", "CLASSES",
    "_clear_duplicate_source_state",
    "DANFORM_PG_ControlItem", "DANFORM_UL_controls", "DANFORM_MT_control_menu", "DANFORM_MT_shape_keys", "DANFORM_MT_manage",
    "DANFORM_OT_select_shape_key",
    "DANFORM_PT_sidebar", "DANFORM_OT_initialize", "DANFORM_OT_resolve_duplicate_pair", "DANFORM_OT_sync",
    "DANFORM_OT_sync_control", "DANFORM_OT_move_control", "DANFORM_OT_create_control",
    "DANFORM_OT_rename_control", "DANFORM_OT_select_control", "DANFORM_OT_set_control_visibility",
    "DANFORM_OT_delete_control", "DANFORM_OT_hide_selected", "DANFORM_OT_reveal",
    "DANFORM_OT_remove_controller", "DANFORM_OT_remove", "DANFORM_OT_reset", "DANFORM_OT_reset_source", "DANFORM_OT_unbind_orphaned_owned_object", "DANFORM_OT_topology_locked",
    "DANFORM_OT_deform", "DANFORM_OT_cancel_deform", "DANFORM_OT_reveal_controller", "DANFORM_OT_toggle_viewport_controls",
    "DANFORM_OT_focus_source", "DANFORM_OT_focus_controller",
    "_ui_item_name_update", "_ui_control_index_update", "_register_topology_keymaps",
    "_unregister_topology_keymaps", "_proxy_segment", "_pick_controller_edge_id",
    "_pick_point_visible", "_proxy_selection_snapshot", "_control_for_edge",
    "_selection_target_for_edge", "_view3d_pick_edge", "_apply_proxy_pick_selection",
    "_set_pick_preview", "_register_control_keymaps", "_unregister_control_keymaps",
]
