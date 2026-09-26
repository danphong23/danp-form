"""DANP Form deformation operators."""

from __future__ import annotations

import json

import bpy
from bpy.props import EnumProperty, FloatProperty, StringProperty
from mathutils import Vector

from ..constants import *
from ..core.operation import OperationTransform


def bind(api) -> None:
    """Bind Source/Controller workflow adapters from the compatibility facade."""
    bindings = api.items() if isinstance(api, dict) else (
        (name, getattr(api, name)) for name in dir(api)
    )
    for name, value in bindings:
        if name.startswith("_") or name.startswith("DANFORM_"):
            globals()[name] = value


class DANFORM_OT_topology_locked(bpy.types.Operator):
    bl_idname = "dan_form.topology_locked"
    bl_label = "Controller Topology Locked"
    bl_description = "The Controller edits positions only; create or remove control lines on the model"
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
        owned_tx = None
        try:
            owned_tx = _deform_begin(source, controller)
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
                if (owned_tx is not None
                        and _DANP_TRANSACTIONS.get(source.as_pointer()) is owned_tx):
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

__all__ = ["bind", 'DANFORM_OT_topology_locked', 'DANFORM_OT_deform', 'DANFORM_OT_cancel_deform']
