"""DANP Form navigation operators."""

from __future__ import annotations


import bpy

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
            runtime.CONTROLLER_EDIT_ACTIVE.discard(source.as_pointer())
            previous_preview = runtime.SHAPE_PREVIEW_STATES.pop(source.as_pointer(), None)
            if previous_preview is not None:
                source.show_only_shape_key = bool(previous_preview)
                context.view_layer.update()
                _sync_proxy(source, controller)
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
                context.view_layer.update()
                _sync_proxy(source, controller)
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

__all__ = ["bind", 'DANFORM_OT_focus_source', 'DANFORM_OT_focus_controller']
