"""DANP Form shape keys operators."""

from __future__ import annotations


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
            if controller is not None and controller.mode == "EDIT":
                runtime.SHAPE_PREVIEW_STATES.setdefault(
                    source.as_pointer(), bool(source.show_only_shape_key)
                )
                source.show_only_shape_key = True
            context.view_layer.update()
            _sync_proxy(source, controller)
            key = _active_shape_key(source)
            context.scene.dan_form_status = f"Editing Shape Key: {key.name}"
            _tag_viewport_redraw(context)
            return {"FINISHED"}
        except (RuntimeError, ValueError) as exc:
            context.scene.dan_form_status = _friendly_error(exc)
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}

class DANFORM_OT_create_shape_key(bpy.types.Operator):
    bl_idname = "dan_form.create_shape_key"
    bl_label = "New Shape Key"
    bl_description = "Create a new key from the current DANP target without changing existing key values"
    bl_options = {"REGISTER", "UNDO"}

    name: StringProperty(name="Name", default="DANP Shape")

    @classmethod
    def poll(cls, context):
        source, _controller = _context_source(context)
        return (source is not None and context.view_layer.objects.active == source
                and source.mode == "OBJECT" and source.library is None
                and source.data.library is None)

    def execute(self, context):
        source, controller = _context_source(context)
        if source is None or source.mode != "OBJECT":
            return {"CANCELLED"}
        added_basis = None
        new_key = None
        previous_index = int(source.active_shape_key_index)
        previous_preview = bool(source.show_only_shape_key)
        shape_keys = source.data.shape_keys
        previous_eval_time = float(shape_keys.eval_time) if shape_keys else None
        try:
            _require_structural_idle(source)
            if source.get(SOURCE_UUID_KEY) and _topology_state(source).get("state") == "PAUSED":
                raise ValueError("STALE_MAPPING")

            # Capture the selected target before adding a KeyBlock. If there
            # are no keys, read the base mesh and create Basis first.
            target_key = _active_shape_key(source)
            target_positions = _source_positions(source, target_key)
            source_vids, _source_eids = _source_id_maps(source)

            if source.data.shape_keys is None:
                added_basis = source.shape_key_add(name="Basis", from_mix=False)

            current_keys = source.data.shape_keys.key_blocks
            keys_are_relative = bool(source.data.shape_keys.use_relative)
            frame_floor = max(
                [float(key.frame) for key in current_keys]
                + [float(source.data.shape_keys.eval_time)]
            ) if not keys_are_relative else None

            if not keys_are_relative:
                candidate = frame_floor + 10.0
                occupied = {float(key.frame) for key in current_keys}
                while candidate in occupied:
                    candidate += 10.0
                # Blender assigns an absolute Shape Key's frame from eval_time
                # during creation; ShapeKey.frame itself is read-only.
                source.data.shape_keys.eval_time = candidate
            new_key = source.shape_key_add(name=self.name.strip() or "DANP Shape", from_mix=False)

            for vertex_id, index in source_vids.items():
                new_key.data[index].co = target_positions[vertex_id]
            new_key.value = 0.0
            if previous_eval_time is not None:
                source.data.shape_keys.eval_time = previous_eval_time

            source.active_shape_key_index = len(source.data.shape_keys.key_blocks) - 1
            source.show_only_shape_key = previous_preview
            context.view_layer.update()
            if controller is not None:
                _sync_proxy(source, controller)
            context.scene.dan_form_status = f"Created Shape Key: {new_key.name}"
            _tag_viewport_redraw(context)
            return {"FINISHED"}
        except (RuntimeError, ValueError, KeyError) as exc:
            if new_key is not None:
                try:
                    source.shape_key_remove(new_key)
                except (RuntimeError, ReferenceError):
                    pass
            if added_basis is not None and source.data.shape_keys is not None:
                try:
                    source.shape_key_remove(added_basis)
                except (RuntimeError, ReferenceError):
                    pass
            source.active_shape_key_index = min(
                previous_index,
                len(source.data.shape_keys.key_blocks) - 1 if source.data.shape_keys else 0,
            )
            source.show_only_shape_key = previous_preview
            if previous_eval_time is not None and source.data.shape_keys is not None:
                source.data.shape_keys.eval_time = previous_eval_time
            self.report({"ERROR"}, _friendly_error(exc))
            return {"CANCELLED"}

__all__ = ["bind", 'DANFORM_OT_select_shape_key', 'DANFORM_OT_create_shape_key']
