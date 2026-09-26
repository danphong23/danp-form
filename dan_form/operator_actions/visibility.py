"""DANP Form visibility operators."""

from __future__ import annotations

import json

import bpy
from bpy.props import BoolProperty, StringProperty

from ..constants import *


def bind(api) -> None:
    """Bind Source/Controller workflow adapters from the compatibility facade."""
    bindings = api.items() if isinstance(api, dict) else (
        (name, getattr(api, name)) for name in dir(api)
    )
    for name, value in bindings:
        if name.startswith("_") or name.startswith("DANFORM_"):
            globals()[name] = value


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
        try:
            def mutate():
                changed_state = _mutate_control_visibility(source, control, self.reveal)
                if changed_state:
                    _rebuild_proxy(source, controller)
                return changed_state

            changed = _atomic_control_structure(source, controller, mutate)
            _set_scene_context(context, source, controller)
            context.scene.dan_form_selected_control = self.control_uuid
            context.scene.dan_form_status = ("Revealed " if self.reveal else "Hidden ") + control.get("name", "Control")
            _sync_context_ui_list(context)
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}

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
            def mutate():
                # Visibility masks belong to the Source network, not the active
                # list row. Apply persistent IDs across overlapping definitions.
                changed_state = _mutate_masks(source, vertex_ids, edge_ids, reveal=False)
                if changed_state:
                    _rebuild_proxy(source, controller)
                return changed_state

            changed = _atomic_control_structure(source, controller, mutate)
            if changed:
                context.scene.dan_form_status = f"Hidden {len(vertex_ids)}V/{len(edge_ids)}E"
            else:
                context.scene.dan_form_status = "No visibility change"
            _set_scene_context(context, source, controller)
            _sync_context_ui_list(context)
            if controller.mode == "EDIT":
                _select_proxy_ids(controller, vertex_ids - _hidden(source, HIDDEN_VIDS_KEY), edge_ids - _hidden(source, HIDDEN_EIDS_KEY))
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}

class DANFORM_OT_hide_unselected(bpy.types.Operator):
    bl_idname = "dan_form.hide_unselected"
    bl_label = "Hide Unselected Controls"
    bl_description = "Keep selected Controller handles and hide the rest using DANP visibility"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        _, controller = _context_source(context)
        return controller is not None and context.view_layer.objects.active == controller and controller.mode == "EDIT"

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        try:
            _require_structural_idle(source)
            visible_vertices, visible_edges = _effective_proxy_elements(source)
            selected_vertices, selected_edges = _proxy_selection_snapshot(controller)
            mode = tuple(context.tool_settings.mesh_select_mode)
            edge_vids = _source_edge_vids(source)

            if mode[1]:
                keep_edges = set(selected_edges)
                keep_vertices = {vertex_id for edge_id in keep_edges
                                 for vertex_id in edge_vids.get(edge_id, ())}
                hide_vertices = set(visible_vertices) - keep_vertices
                hide_edges = set(visible_edges) - keep_edges
            elif mode[0]:
                keep_vertices = set(selected_vertices)
                keep_edges = {
                    edge_id for edge_id in visible_edges
                    if set(edge_vids.get(edge_id, ())).issubset(keep_vertices)
                }
                hide_vertices = set(visible_vertices) - keep_vertices
                hide_edges = set(visible_edges) - keep_edges
            else:
                self.report({"WARNING"}, "Controller handles have no face components. Switch to Vertex or Edge Select mode.")
                return {"CANCELLED"}

            def mutate():
                changed_state = _mutate_masks(source, hide_vertices, hide_edges, reveal=False)
                if changed_state:
                    _rebuild_proxy(source, controller)
                return changed_state

            changed = _atomic_control_structure(source, controller, mutate)
            context.scene.dan_form_status = (
                "Hidden unselected controls" if changed else "No visibility change"
            )
            _set_scene_context(context, source, controller)
            _sync_context_ui_list(context)
            return {"FINISHED"}
        except Exception as exc:
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

            def mutate():
                changed_state = _mutate_masks(source, vertex_ids, edge_ids, reveal=True)
                proxy_state = _proxy_state(controller)
                native_hidden = proxy_state is not None and (
                    any(vertex[3] for vertex in proxy_state[0])
                    or any(edge[3] for edge in proxy_state[1])
                )
                if changed_state or native_hidden:
                    _rebuild_proxy(source, controller)
                return changed_state

            changed = _atomic_control_structure(source, controller, mutate)
            context.scene.dan_form_status = "Revealed all" if not vertex_ids and not edge_ids else "Revealed selection"
            _set_scene_context(context, source, controller)
            _sync_context_ui_list(context)
            return {"FINISHED"}
        except Exception as exc:
            message = (
                "The reveal request is invalid. Check the vertex and edge IDs."
                if isinstance(exc, (json.JSONDecodeError, TypeError))
                else _friendly_error(exc)
            )
            self.report({"ERROR"}, message)
            return {"CANCELLED"}

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

        def mutate():
            if hide:
                edges, nodes = set(), set()
                for control in _controls(source):
                    control_edges, control_nodes = _control_intent(source, control)
                    edges.update(control_edges)
                    nodes.update(control_nodes)
                changed_state = _mutate_masks(source, nodes, edges, reveal=False)
            else:
                changed_state = _mutate_masks(source, set(), set(), reveal=True)
            proxy_state = _proxy_state(controller)
            native_hidden = proxy_state is not None and (
                any(vertex[3] for vertex in proxy_state[0])
                or any(edge[3] for edge in proxy_state[1])
            )
            if changed_state or native_hidden:
                _rebuild_proxy(source, controller)
            return changed_state

        try:
            changed = _atomic_control_structure(source, controller, mutate)
        except (ValueError, RuntimeError) as exc:
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}
        controller.hide_set(False, view_layer=context.view_layer)
        _sync_context_ui_list(context)
        context.scene.dan_form_status = "Hidden all controls" if hide else "Revealed all controls"
        _tag_viewport_redraw(context)
        return {"FINISHED"}

__all__ = ["bind", 'DANFORM_OT_set_control_visibility', 'DANFORM_OT_hide_selected', 'DANFORM_OT_hide_unselected', 'DANFORM_OT_reveal', 'DANFORM_OT_reveal_controller', 'DANFORM_OT_toggle_viewport_controls']
