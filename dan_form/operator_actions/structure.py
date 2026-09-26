"""DANP Form structure operators."""

from __future__ import annotations

import copy
import uuid

import bpy
from bpy.props import IntProperty, StringProperty

from .. import runtime
from ..constants import *


def bind(api) -> None:
    """Bind Source/Controller workflow adapters from the compatibility facade."""
    bindings = api.items() if isinstance(api, dict) else (
        (name, getattr(api, name)) for name in dir(api)
    )
    for name, value in bindings:
        if name.startswith("_") or name.startswith("DANFORM_"):
            globals()[name] = value


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
        was_editing_source = source is not None and source.mode == "EDIT"
        previous_guard = runtime.SYNC_GUARD
        created_controller = None
        created_mesh = None
        new_source_binding = False
        try:
            _require_structural_idle(source)
            if not _is_valid_source(source):
                raise ValueError("SOURCE_NOT_EDITABLE")
            # A live Edit BMesh is newer than Mesh.attributes and evaluated_get().
            # Flush it before creating IDs or reading evaluated coordinates, then
            # return to the user's Edit Mode and original selection afterward.
            runtime.SYNC_GUARD = True
            if was_editing_source:
                bpy.ops.object.mode_set(mode="OBJECT")
            _reconcile_duplicate_bindings()
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
            new_source_binding = not bool(source.get(SOURCE_UUID_KEY))
            controller = _find_controller(source)
            if controller is None:
                _ensure_source_ids(source)
                _source_uuid(source)
                _capture_original_snapshot(source)
                mesh = bpy.data.meshes.new(f"DANPFORM_CTRL_{source.name}")
                mesh.from_pydata([], [], [])
                mesh.update()
                controller = bpy.data.objects.new(f"DANPFORM_CTRL_{source.name}", mesh)
                created_controller = controller
                created_mesh = mesh
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
            if _find_controller(source) != controller or controller.parent != source:
                raise ValueError("CONTROLLER_BINDING_INCOMPLETE")
            source["dan_form_controller_name"] = controller.name
            source.pop(UNBOUND_COPY_KEY, None)
            _remember_binding(source, controller)
            _set_scene_context(context, source, controller)
            scene.dan_form_status = f"Ready: {source.name} / {controller.name}"
            self.report({"INFO"}, "DANP Form controller ready")
            return {"FINISHED"}
        except (ValueError, RuntimeError) as exc:
            if created_controller is not None and created_controller.name in bpy.data.objects:
                bpy.data.objects.remove(created_controller, do_unlink=True)
            if created_mesh is not None and created_mesh.users == 0:
                bpy.data.meshes.remove(created_mesh)
            if new_source_binding:
                _clear_duplicate_source_state(source)
            scene.dan_form_controller = None
            scene.dan_form_status = _friendly_error(exc)
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}
        finally:
            try:
                if was_editing_source and source is not None and source.name in bpy.data.objects:
                    if source.mode == "OBJECT":
                        context.view_layer.objects.active = source
                        bpy.ops.object.mode_set(mode="EDIT")
            finally:
                runtime.SYNC_GUARD = previous_guard

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
            self.report({"INFO"}, "The selected DANP pair now has a unique identity")
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
        except (ValueError, RuntimeError) as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}

class DANFORM_OT_validate_topology(bpy.types.Operator):
    bl_idname = "dan_form.validate_topology"
    bl_label = "Validate Topology Recovery"
    bl_description = "Preview whether this Source topology can be repaired without changing controls or Shape Keys"

    def execute(self, context):
        source, _controller = _context_source(context)
        try:
            if source is None:
                raise ValueError("SOURCE_OR_CONTROLLER_MISSING")
            report = _topology_repair_analysis(source)
            summary = (f"Topology repair is safe: +{report['added_vertices']} vertices, "
                       f"+{report['added_edges']} edges, -{report['removed_vertices']} vertices, "
                       f"-{report['removed_edges']} edges; {report['protected_faces']} protected faces unchanged")
            context.scene.dan_form_status = summary
            self.report({"INFO"}, summary)
            return {"FINISHED"}
        except (AttributeError, RuntimeError, ValueError) as exc:
            message = _friendly_error(exc)
            context.scene.dan_form_status = message
            self.report({"WARNING"}, message)
            return {"CANCELLED"}

class DANFORM_OT_repair_topology(bpy.types.Operator):
    bl_idname = "dan_form.repair_topology"
    bl_label = "Repair DANP Mapping"
    bl_description = "Assign IDs to unambiguous new mesh elements and rebuild DANP controls"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        source, controller = _context_source(context)
        return source is not None and controller is not None and _topology_state(source).get("state") == "PAUSED"

    def execute(self, context):
        source, controller = _context_source(context)
        snapshot = None
        id_attributes = {}
        topology_state = None
        try:
            _require_structural_idle(source)
            if source is None or controller is None:
                raise ValueError("SOURCE_OR_CONTROLLER_MISSING")
            snapshot = _capture_control_structure(source, controller)
            pointer = source.as_pointer()
            topology_state = copy.deepcopy(runtime.TOPOLOGY_STATES.get(pointer))
            id_attributes = _capture_source_id_layers(source)
            report = _repair_source_topology(source)
            _update_revision(source)
            _rebuild_proxy(source, controller)
            _remember_binding(source, controller)
            _set_scene_context(context, source, controller)
            summary = (f"DANP mapping repaired: +{report['added_vertices']} vertices, "
                       f"+{report['added_edges']} edges; controls and Shape Keys preserved")
            context.scene.dan_form_status = summary
            self.report({"INFO"}, summary)
            _discard_control_structure_snapshot(snapshot)
            snapshot = None
            return {"FINISHED"}
        except Exception as exc:
            if snapshot is not None:
                _restore_control_structure(source, controller, snapshot)
                _restore_source_id_layers(source, id_attributes)
                if topology_state is None:
                    runtime.TOPOLOGY_STATES.pop(source.as_pointer(), None)
                else:
                    runtime.TOPOLOGY_STATES[source.as_pointer()] = topology_state
            message = _friendly_error(exc)
            context.scene.dan_form_status = message
            self.report({"ERROR"}, message)
            return {"CANCELLED"}

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

            def mutate():
                control["vertex_ids"] = new_membership[0]
                control["edge_ids"] = new_membership[1]
                _json_set(source, CONTROLS_KEY, controls)
                _prune_masks_after_remove(source)
                _update_revision(source)
                if controller is not None:
                    _rebuild_proxy(source, controller)
                    _sync_proxy(source, controller)

            _atomic_control_structure(source, controller, mutate)
            _set_scene_context(context, source, controller)
            context.scene.dan_form_status = f"Synced {control.get('name', 'Control')}"
            _sync_context_ui_list(context)
            return {"FINISHED"}
        except Exception as exc:
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
            controller = controller or _find_controller(source)
            if controller is None:
                raise ValueError("CONTROLLER_MISSING")

            def mutate():
                _json_set(source, CONTROLS_KEY, controls)
                _update_revision(source)
                _rebuild_proxy(source, controller)
                _sync_proxy(source, controller)

            _atomic_control_structure(source, controller, mutate)
            _set_scene_context(context, source, controller)
            scene.dan_form_selected_control = controls[-1]["control_uuid"]
            scene.dan_form_status = f"Created {controls[-1]['name']} ({len(vertex_ids)}V/{len(edge_ids)}E)"
            _sync_context_ui_list(context)
            self.report({"INFO"}, scene.dan_form_status)
            return {"FINISHED"}
        except Exception as exc:
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
        try:
            def mutate():
                _json_set(source, CONTROLS_KEY, remaining)
                _prune_masks_after_remove(source)
                _update_revision(source)
                if controller is not None:
                    _rebuild_proxy(source, controller)

            _atomic_control_structure(source, controller, mutate)
        except Exception as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}
        _set_scene_context(context, source, controller)
        context.scene.dan_form_selected_control = ""
        context.scene.dan_form_status = "Control deleted"
        _sync_context_ui_list(context)
        if context.scene.dan_form_control_items:
            context.scene.dan_form_control_index = min(
                deleted_index, len(context.scene.dan_form_control_items) - 1
            )
        return {"FINISHED"}

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
    bl_description = "Remove the Controller and DANP Form setup while preserving the model geometry"
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
            context.scene.dan_form_status = "DANP Form removed"
            _tag_viewport_redraw(context)
            self.report({"INFO"}, "DANP Form removed; model geometry preserved")
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
        source_properties = {
            key: copy.deepcopy(source.get(key))
            for key in _SOURCE_DANP_KEYS if key in source
        }
        source_attributes = _capture_source_id_layers(source)
        old_controller_marker = controller.get(CONTROLLER_KEY) if controller is not None else None
        active_control_before = _ACTIVE_CONTROL_UUIDS.get(old_uuid)
        return_mode_before = _RETURN_MODES.get(old_uuid)
        provenance_before = runtime.INIT_TARGET_PROVENANCE.get(source.as_pointer())
        owned_faces = [obj for obj in bpy.data.objects
                       if obj.get(FACE_SOURCE_UUID_KEY) == old_uuid]
        fresh = None
        if was_edit:
            bpy.ops.object.mode_set(mode="OBJECT")
        try:
            _discard_source_runtime(source)
            if controller is not None:
                # Preserve the old object until the replacement is complete.
                # Its marker is temporarily removed to avoid ambiguous binding.
                controller.pop(CONTROLLER_KEY, None)
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
            # Commit replacement only after source mapping, proxy and UI bind
            # have succeeded. DANP-owned face assets are left untouched on
            # every earlier failure path.
            for obj in [*owned_faces, *([controller] if controller is not None else [])]:
                if obj is None or obj.name not in bpy.data.objects:
                    continue
                mesh_data = getattr(obj, "data", None)
                _PROXY_SNAPSHOTS.pop(obj.as_pointer(), None)
                bpy.data.objects.remove(obj, do_unlink=True)
                if (mesh_data is not None and mesh_data.users == 0
                        and bpy.data.meshes.get(mesh_data.name) is mesh_data):
                    bpy.data.meshes.remove(mesh_data)
            context.scene.dan_form_status = (
                f"DANP reset: created a new mapping for the current topology of {source.name}"
            )
            self.report({"INFO"}, "DANP reset complete; current mesh topology is now the mapping source")
            return {"FINISHED"}
        except Exception as exc:
            if fresh is not None and fresh.name in bpy.data.objects:
                mesh_data = fresh.data
                _PROXY_SNAPSHOTS.pop(fresh.as_pointer(), None)
                bpy.data.objects.remove(fresh, do_unlink=True)
                if mesh_data.users == 0 and bpy.data.meshes.get(mesh_data.name) is mesh_data:
                    bpy.data.meshes.remove(mesh_data)
            _restore_source_id_layers(source, source_attributes)
            for key in _SOURCE_DANP_KEYS:
                if key in source:
                    del source[key]
            for key, value in source_properties.items():
                source[key] = value
            if controller is not None and controller.name in bpy.data.objects:
                if old_controller_marker is not None:
                    controller[CONTROLLER_KEY] = old_controller_marker
                _remember_binding(source, controller)
            _ACTIVE_CONTROL_UUIDS.pop(old_uuid, None)
            if active_control_before is not None:
                _ACTIVE_CONTROL_UUIDS[old_uuid] = active_control_before
            _RETURN_MODES.pop(old_uuid, None)
            if return_mode_before is not None:
                _RETURN_MODES[old_uuid] = return_mode_before
            if provenance_before is not None:
                runtime.INIT_TARGET_PROVENANCE[source.as_pointer()] = provenance_before
            _MAPPING_CACHE.pop(source.as_pointer(), None)
            _NETWORK_CACHE.pop(source.as_pointer(), None)
            _invalidate_patch_cache(source)
            _OVERLAY_CACHE.clear()
            _set_scene_context(context, source, controller)
            _select_only(context, source)
            if was_edit:
                bpy.ops.object.mode_set(mode="EDIT")
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
            and (bool(active.get(ORPHANED_OWNED_KEY))
                 or (active.get(CONTROLLER_KEY) is not None and active.parent is None))
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
            f"Removed stale DANP ownership from {obj.name}; mesh data preserved"
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
            context.scene.dan_form_status = "Model restored to the pose captured at DANP initialization"
            self.report({"INFO"}, "Source restored to the original Init pose")
            return {"FINISHED"}
        except (RuntimeError, ValueError) as exc:
            if str(exc) == "ORIGINAL_SNAPSHOT_TOPOLOGY_CHANGED":
                message = "The topology changed. Use Undo or Reset DANP before restoring the original pose."
            elif str(exc) == "ORIGINAL_SNAPSHOT_TARGET_MISMATCH":
                message = "The Init snapshot belongs to another Shape Key. Select that key before Reset Model."
            elif str(exc) == "ORIGINAL_SNAPSHOT_TARGET_PROVENANCE_UNKNOWN":
                message = "The original Shape Key snapshot cannot be verified. Reset DANP to capture a new snapshot."
            elif str(exc) in {"ORIGINAL_SNAPSHOT_MISSING", "ORIGINAL_SNAPSHOT_INVALID"}:
                message = "This mesh has no Init snapshot. Remove DANP Form and initialize it again."
            else:
                message = _friendly_error(exc)
            context.scene.dan_form_status = message
            self.report({"ERROR"}, message)
            return {"CANCELLED"}

__all__ = ["bind", 'DANFORM_OT_initialize', 'DANFORM_OT_resolve_duplicate_pair', 'DANFORM_OT_sync', 'DANFORM_OT_validate_topology', 'DANFORM_OT_repair_topology', 'DANFORM_OT_sync_control', 'DANFORM_OT_move_control', 'DANFORM_OT_create_control', 'DANFORM_OT_rename_control', 'DANFORM_OT_delete_control', 'DANFORM_OT_remove_controller', 'DANFORM_OT_remove', 'DANFORM_OT_reset', 'DANFORM_OT_unbind_orphaned_owned_object', 'DANFORM_OT_reset_source']
