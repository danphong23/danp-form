"""DANP Form sidebar, list rows and menu classes."""

from __future__ import annotations

import bpy
from bpy.props import IntProperty, StringProperty

from .. import runtime
from ..constants import *

_UI_SELECTION_STATES: dict[str, str] = {}


def bind(api) -> None:
    """Bind compatibility adapters used by the UI classes."""
    bindings = api.items() if isinstance(api, dict) else (
        (name, getattr(api, name)) for name in dir(api)
    )
    for name, value in bindings:
        if name.startswith("_") or name.startswith("DANFORM_"):
            globals()[name] = value


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
            scene.dan_form_status = "Finish or cancel the current transform before switching controls"
            return
    scene.dan_form_selected_control = control["control_uuid"]
    _ACTIVE_CONTROL_UUIDS[items[index].source_uuid] = control["control_uuid"]
    # Index changes establish the active definition only.  Mesh selection is
    # handled by the row's Select Control button, whose invoke receives Shift.
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
        selection_state = _UI_SELECTION_STATES.get(item.control_uuid, "NONE")
        marker_icon = {
            "FULL": "CHECKBOX_HLT",
            "PARTIAL": "RADIOBUT_ON",
            "NONE": "CHECKBOX_DEHLT",
        }.get(selection_state, "CHECKBOX_DEHLT")
        select = row.operator(
            "dan_form.select_control",
            text=item.control_name,
            icon=marker_icon,
            emboss=False,
        )
        select.control_uuid = item.control_uuid
        rename = row.operator(
            "dan_form.rename_control",
            text="",
            icon="GREASEPENCIL",
            emboss=False,
        )
        rename.control_uuid = item.control_uuid
        if item.state == "Partial":
            row.label(text="~")

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

class DANFORM_MT_shape_keys(bpy.types.Menu):
    bl_label = "Select Shape Key"
    bl_idname = "DANFORM_MT_shape_keys"

    def draw(self, context):
        layout = self.layout
        source, _controller = _context_source(context)
        if source is None or source.data.shape_keys is None:
            layout.label(text="This mesh has no Shape Keys")
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
        global _UI_SELECTION_STATES
        _UI_SELECTION_STATES = _control_selection_states(source, active) if source is not None else {}
        if source is None:
            if active is not None and active.type == "MESH":
                if (active.get(ORPHANED_OWNED_KEY)
                        or (active.get(CONTROLLER_KEY) is not None and active.parent is None)):
                    box = layout.box()
                    box.alert = True
                    box.label(text="This object has no valid DANP owner", icon="ERROR")
                    box.label(text="Unbind it to keep the mesh as a separate object")
                    box.operator(
                        DANFORM_OT_unbind_orphaned_owned_object.bl_idname,
                        text="Unbind DANP, Keep Mesh",
                        icon="UNLINKED",
                    )
                    return
                state_source = active.parent if active.get(CONTROLLER_KEY) is not None else active
                state = _binding_status(state_source)
                if state == "DUPLICATE_UNBOUND":
                    layout.label(text="This mesh copy has no DANP Controller", icon="INFO")
                    layout.operator(DANFORM_OT_initialize.bl_idname, text="Init DANP Form", icon="ADD")
                    return
                if state in {"UUID_CONFLICT", "CONTROLLER_CONFLICT"}:
                    layout.label(text="DANP Controller ownership is ambiguous", icon="ERROR")
                    if active.get(CONTROLLER_KEY) is not None or len(_controller_children(state_source)) == 1:
                        layout.operator(DANFORM_OT_resolve_duplicate_pair.bl_idname, text="Keep This Pair", icon="LINKED")
                    elif not _controller_children(state_source):
                        layout.label(text="Initializing creates independent controls for this mesh")
                        layout.operator(DANFORM_OT_initialize.bl_idname, text="Initialize This Mesh", icon="ADD")
                    else:
                        layout.label(text="Select the Controller to keep, then resolve the pair", icon="INFO")
                    return
                if state == "SHARED_DATA":
                    layout.label(text="The mesh or Controller shares data", icon="ERROR")
                    layout.label(text="Make it single-user before using DANP Form")
                    return
            layout.label(text="Select a DANP Form mesh or Controller", icon="INFO")
            return
        if active == source:
            lifecycle = layout.row(align=True)
            lifecycle.enabled = source.mode in {"OBJECT", "EDIT"}
            if controller is None and not source.get(SOURCE_UUID_KEY):
                lifecycle.operator(DANFORM_OT_initialize.bl_idname, text="Init DANP Form", icon="ADD")
            elif controller is None:
                lifecycle.operator(DANFORM_OT_initialize.bl_idname, text="Rebuild Controller", icon="FILE_REFRESH")
            else:
                lifecycle.operator(DANFORM_OT_reset_source.bl_idname, text="Reset Model", icon="LOOP_BACK")
                lifecycle.menu(DANFORM_MT_manage.bl_idname, text="Manage", icon="DOWNARROW_HLT")
        if controller is None:
            if source.get(SOURCE_UUID_KEY):
                layout.label(text="No Controller child is bound to this mesh", icon="INFO")
            return
        topology = _topology_state(source)
        if topology.get("state") == "PAUSED":
            warning = layout.box()
            warning.alert = True
            warning.label(text="DANP Form is paused: topology changed", icon="ERROR")
            warning.label(text="Validate first; Repair only if the control patches are intact")
            recovery = warning.row(align=True)
            recovery.operator(DANFORM_OT_validate_topology.bl_idname, text="Validate", icon="VIEWZOOM")
            recovery.operator(DANFORM_OT_repair_topology.bl_idname, text="Repair", icon="FILE_REFRESH")
            warning.operator(DANFORM_OT_reset.bl_idname, text="Reset DANP", icon="LOOP_BACK")
        key = _active_shape_key(source)
        key_row = layout.row(align=True)
        key_row.label(text="Editing target:")
        key_row.label(text=key.name if key is not None else "Base Mesh", icon="SHAPEKEY_DATA" if key is not None else "MESH_DATA")
        if source.data.shape_keys is not None:
            key_row.menu(DANFORM_MT_shape_keys.bl_idname, text="", icon="DOWNARROW_HLT")
        if key is not None and key.lock_shape:
            warning = layout.box()
            warning.alert = True
            warning.label(text=f"Shape Key '{key.name}' is locked", icon="LOCKED")
            warning.label(text="Unlock the key before editing with the Controller")
        if active == source:
            create_key = layout.row(align=True)
            create_key.enabled = (
                source.mode == "OBJECT" and not source.library and not source.data.library
                and topology.get("state") != "PAUSED"
            )
            create_key.operator(DANFORM_OT_create_shape_key.bl_idname, text="New Shape Key", icon="ADD")
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
            layout.label(text="Edit the Source and select vertices or edges, then press +", icon="INFO")

__all__ = [
    "bind", "DANFORM_PG_ControlItem", "DANFORM_UL_controls",
    "DANFORM_MT_control_menu", "DANFORM_MT_manage", "DANFORM_MT_shape_keys",
    "DANFORM_PT_sidebar", "_ui_item_name_update", "_ui_control_index_update",
]
