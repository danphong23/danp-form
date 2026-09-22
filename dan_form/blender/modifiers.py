"""Modifier policy for Source-backed Controller proxies.

The Source owns the modifier stack.  A Controller is only a vertex/edge proxy,
so copying every Source modifier would be misleading: surface modifiers such as
Subdivision need faces and can change the selection/display contract.  The
allow-list below contains modifiers that preserve the proxy's edit semantics.
"""

from __future__ import annotations

from typing import Any

import bpy
from mathutils import Matrix, Vector


# Mirror is the first supported stack member.  Its native Merge/Clipping rules
# are exactly what Controller Edit Mode needs at the symmetry plane.  This is a
# policy boundary rather than an assumption that every future modifier is safe
# on a face-less proxy.
CONTROLLER_MODIFIER_TYPES = frozenset({"MIRROR"})
_NON_TRANSFERABLE_PROPERTIES = frozenset({"rna_type", "name", "type", "is_active"})


def _rna_value(value: Any):
    """Convert an RNA value into a stable, comparable signature value."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, bpy.types.ID):
        return (value.__class__.__name__, value.name, value.as_pointer())
    try:
        return tuple(_rna_value(item) for item in value)
    except TypeError:
        return repr(value)


def modifier_properties(modifier: bpy.types.Modifier) -> tuple:
    """Return editable RNA properties, including Mirror settings."""
    values = []
    for prop in modifier.bl_rna.properties:
        identifier = prop.identifier
        if identifier in _NON_TRANSFERABLE_PROPERTIES or prop.is_readonly:
            continue
        try:
            values.append((identifier, _rna_value(getattr(modifier, identifier))))
        except (AttributeError, TypeError, ValueError, RuntimeError):
            continue
    return tuple(values)


def stack_signature(source: bpy.types.Object | None) -> tuple:
    """Return the complete Source stack signature used for synchronization."""
    if source is None:
        return ()
    return tuple(
        (
            modifier.name,
            modifier.type,
            modifier.type in CONTROLLER_MODIFIER_TYPES,
            bool(modifier.show_viewport),
            bool(modifier.show_in_editmode),
            bool(getattr(modifier, "show_on_cage", False)),
            modifier_properties(modifier),
        )
        for modifier in source.modifiers
    )


def _copy_properties(source_modifier: bpy.types.Modifier,
                     target_modifier: bpy.types.Modifier) -> None:
    """Copy compatible RNA properties without relying on modifier-specific code."""
    for prop in source_modifier.bl_rna.properties:
        identifier = prop.identifier
        if identifier in _NON_TRANSFERABLE_PROPERTIES or prop.is_readonly:
            continue
        try:
            value = getattr(source_modifier, identifier)
            if isinstance(value, bpy.types.ID):
                setattr(target_modifier, identifier, value)
            else:
                setattr(target_modifier, identifier, value)
        except (AttributeError, TypeError, ValueError, RuntimeError):
            # Blender exposes version-specific RNA properties.  A property that
            # cannot be assigned on this version must not break initialization.
            continue


def sync_controller_modifiers(source: bpy.types.Object,
                              controller: bpy.types.Object) -> dict:
    """Synchronize the supported Source modifiers onto Controller.

    The complete Source signature is retained on the Controller so a later
    depsgraph event can distinguish a changed Mirror setting from a no-op mesh
    update. Unsupported modifiers are deliberately omitted and reported; they
    remain active on Source and therefore do not become a second geometry truth.
    """
    desired = [modifier for modifier in source.modifiers
               if modifier.type in CONTROLLER_MODIFIER_TYPES]
    previous = tuple(
        (modifier.name, modifier.type, modifier_properties(modifier))
        for modifier in controller.modifiers
    )
    current = tuple(
        (modifier.name, modifier.type, modifier_properties(modifier))
        for modifier in desired
    )
    changed = previous != current
    if changed:
        old_mode = controller.mode
        if old_mode == "EDIT":
            # Modifier collections are an Object Mode data API.  Preserve the
            # user's native Controller Edit context while replacing the
            # derived stack, including when a modifier is changed mid-session.
            bpy.ops.object.mode_set(mode="OBJECT")
        try:
            controller.modifiers.clear()
            for source_modifier in desired:
                target_modifier = controller.modifiers.new(
                    name=source_modifier.name,
                    type=source_modifier.type,
                )
                _copy_properties(source_modifier, target_modifier)
        finally:
            if old_mode == "EDIT" and controller.name in bpy.data.objects:
                controller.select_set(True)
                bpy.context.view_layer.objects.active = controller
                bpy.ops.object.mode_set(mode="EDIT")
    metadata = {
        "dan_form_source_modifier_signature": repr(stack_signature(source)),
        "dan_form_controller_modifier_types": ",".join(
            modifier.type for modifier in desired
        ),
        "dan_form_unsupported_source_modifiers": ",".join(
            modifier.name for modifier in source.modifiers
            if modifier.type not in CONTROLLER_MODIFIER_TYPES
        ),
    }
    for key, value in metadata.items():
        if controller.get(key) != value:
            controller[key] = value
    return {
        "changed": changed,
        "copied": tuple(modifier.name for modifier in desired),
        "skipped": tuple(modifier.name for modifier in source.modifiers
                          if modifier.type not in CONTROLLER_MODIFIER_TYPES),
    }


def apply_mirror_constraints(source: bpy.types.Object,
                             rest_positions: dict[int, Vector],
                             output_positions: dict[int, Vector]) -> dict[int, Vector]:
    """Apply Source-side Merge/Clipping to a DANP preview.

    Native Mirror protects Controller Edit Mode, but DANP writes preview
    coordinates directly to Source.  This adapter mirrors Blender's plane
    constraints for the supported stack without changing topology: seam
    vertices stay on the plane and clipped vertices cannot cross it.
    """
    mirrors = [modifier for modifier in source.modifiers if modifier.type == "MIRROR"]
    if not mirrors or not output_positions:
        return output_positions
    mirror = mirrors[0]
    axes = tuple(index for index, enabled in enumerate(mirror.use_axis) if enabled)
    if not axes:
        return output_positions
    mirror_object = mirror.mirror_object
    if mirror_object is None:
        to_mirror = Matrix.Identity(4)
        from_mirror = Matrix.Identity(4)
    else:
        to_mirror = mirror_object.matrix_world.inverted() @ source.matrix_world
        from_mirror = source.matrix_world.inverted() @ mirror_object.matrix_world
    threshold = float(getattr(mirror, "merge_threshold", 0.0))
    clipping = bool(getattr(mirror, "use_clip", False))
    merging = bool(getattr(mirror, "use_mirror_merge", False))
    constrained = {}
    for vertex_id, position in output_positions.items():
        rest = rest_positions.get(vertex_id)
        if rest is None:
            constrained[vertex_id] = position
            continue
        rest_mirror = to_mirror @ rest
        current_mirror = to_mirror @ position
        for axis in axes:
            rest_axis = float(rest_mirror[axis])
            current_axis = float(current_mirror[axis])
            on_plane = abs(rest_axis) <= threshold
            crossed = ((rest_axis > threshold and current_axis < 0.0)
                       or (rest_axis < -threshold and current_axis > 0.0))
            snapped = merging and abs(current_axis) <= threshold
            if on_plane or (clipping and crossed) or snapped:
                current_mirror[axis] = 0.0
        constrained[vertex_id] = from_mirror @ current_mirror
    return constrained


__all__ = [
    "CONTROLLER_MODIFIER_TYPES",
    "modifier_properties",
    "stack_signature",
    "sync_controller_modifiers",
    "apply_mirror_constraints",
]
