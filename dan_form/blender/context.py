"""Resolve Source/controller ownership from the active Blender context."""

from __future__ import annotations

import bpy

from ..constants import CONTROLLER_KEY, SOURCE_UUID_KEY


def find_controller(source: bpy.types.Object) -> bpy.types.Object | None:
    source_uuid = source.get(SOURCE_UUID_KEY)
    if not source_uuid:
        return None
    for obj in bpy.data.objects:
        if obj.get(CONTROLLER_KEY) == source_uuid and obj.type == "MESH":
            return obj
    return None


def source_for_controller(controller: bpy.types.Object | None) -> bpy.types.Object | None:
    if controller is None or controller.get(CONTROLLER_KEY) is None:
        return None
    source_uuid = controller.get(CONTROLLER_KEY)
    parent = controller.parent
    for source in bpy.data.objects:
        if (
            source.type == "MESH"
            and source.get(SOURCE_UUID_KEY) == source_uuid
            and (parent is None or parent == source)
        ):
            return source
    return None


def context_source(context: bpy.types.Context) -> tuple[bpy.types.Object | None, bpy.types.Object | None]:
    """Resolve the active model; never reuse a stale scene pointer."""
    active = context.view_layer.objects.active
    if active is None:
        return None, None
    if active.type == "MESH" and active.get(CONTROLLER_KEY) is None:
        return active, find_controller(active)
    source = source_for_controller(active)
    if source is not None:
        return source, active
    return None, None


def find_source_by_uuid(source_uuid: str) -> bpy.types.Object | None:
    if not source_uuid:
        return None
    return next(
        (obj for obj in bpy.data.objects if obj.type == "MESH" and obj.get(SOURCE_UUID_KEY) == source_uuid),
        None,
    )


def source_controller_pairs() -> list[tuple[bpy.types.Object, bpy.types.Object]]:
    pairs = []
    for source in bpy.data.objects:
        if source.type != "MESH" or not source.get(SOURCE_UUID_KEY):
            continue
        controller = find_controller(source)
        if controller is not None:
            pairs.append((source, controller))
    return pairs


def controller_collection(source: bpy.types.Object, scene: bpy.types.Scene) -> bpy.types.Collection:
    return source.users_collection[0] if source.users_collection else scene.collection


def select_only(context: bpy.types.Context, obj: bpy.types.Object) -> None:
    for candidate in context.view_layer.objects:
        candidate.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
