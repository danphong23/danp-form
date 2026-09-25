"""Resolve Source/controller ownership from the Blender parent relation.

UUIDs identify persisted DANP data. They are deliberately not used to choose an
object owner because Blender duplicates object custom properties.
"""

from __future__ import annotations

import bpy

from ..constants import CONTROLLER_KEY, FACE_SOURCE_UUID_KEY, SOURCE_UUID_KEY, UNBOUND_COPY_KEY


READY = "READY"
UNBOUND = "UNBOUND"
MISSING_CONTROLLER = "MISSING_CONTROLLER"
DUPLICATE_UNBOUND = "DUPLICATE_UNBOUND"
UUID_CONFLICT = "UUID_CONFLICT"
CONTROLLER_CONFLICT = "CONTROLLER_CONFLICT"
SHARED_DATA = "SHARED_DATA"
INVALID_SOURCE = "INVALID_SOURCE"


def _source_objects() -> list[bpy.types.Object]:
    return [
        obj for obj in bpy.data.objects
        if obj.type == "MESH" and obj.get(CONTROLLER_KEY) is None
    ]


def source_objects_by_uuid(source_uuid: str) -> list[bpy.types.Object]:
    if not source_uuid:
        return []
    return [obj for obj in _source_objects() if obj.get(SOURCE_UUID_KEY) == source_uuid]


def controller_children(source: bpy.types.Object) -> list[bpy.types.Object]:
    """Return DANP-marked mesh children, even when their UUID marker is stale."""
    if source is None:
        return []
    return [
        obj for obj in bpy.data.objects
        if obj.type == "MESH" and obj.parent == source and obj.get(CONTROLLER_KEY) is not None
    ]


def _matching_pair_sources(source_uuid: str) -> list[bpy.types.Object]:
    """Sources with one direct Controller child and matching ownership markers."""
    if not source_uuid:
        return []
    pairs = []
    for source in source_objects_by_uuid(source_uuid):
        if source.get(UNBOUND_COPY_KEY):
            continue
        children = controller_children(source)
        if len(children) == 1 and children[0].get(CONTROLLER_KEY) == source_uuid:
            pairs.append(source)
    return pairs


def binding_status(source: bpy.types.Object | None) -> str:
    """Classify a mesh without guessing when ownership is ambiguous."""
    if source is None or getattr(source, "type", None) != "MESH" or source.get(CONTROLLER_KEY) is not None:
        return INVALID_SOURCE

    source_uuid = source.get(SOURCE_UUID_KEY)
    if getattr(source.data, "users", 1) > 1:
        return SHARED_DATA
    if source.get(UNBOUND_COPY_KEY):
        return DUPLICATE_UNBOUND
    children = controller_children(source)
    if len(children) > 1:
        return CONTROLLER_CONFLICT
    if children:
        controller = children[0]
        if not source_uuid or controller.get(CONTROLLER_KEY) != source_uuid:
            return CONTROLLER_CONFLICT
        if getattr(source.data, "users", 1) > 1 or getattr(controller.data, "users", 1) > 1:
            return SHARED_DATA
        if len(source_objects_by_uuid(source_uuid)) > 1:
            return UUID_CONFLICT
        if len(_matching_pair_sources(source_uuid)) > 1:
            return UUID_CONFLICT
        return READY

    if not source_uuid:
        return UNBOUND
    same_uuid = source_objects_by_uuid(source_uuid)
    if len(same_uuid) > 1:
        return DUPLICATE_UNBOUND if any(_matching_pair_sources(source_uuid)) else UUID_CONFLICT
    return MISSING_CONTROLLER


def find_controller(source: bpy.types.Object) -> bpy.types.Object | None:
    if binding_status(source) != READY:
        return None
    children = controller_children(source)
    return children[0] if children else None


def source_for_controller(controller: bpy.types.Object | None) -> bpy.types.Object | None:
    if controller is None or controller.type != "MESH" or controller.get(CONTROLLER_KEY) is None:
        return None
    source = controller.parent
    if source is None or getattr(source, "type", None) != "MESH":
        return None
    if binding_status(source) != READY or find_controller(source) != controller:
        return None
    return source


def context_source(context: bpy.types.Context) -> tuple[bpy.types.Object | None, bpy.types.Object | None]:
    """Resolve the active model through its direct parent/child binding."""
    active = context.view_layer.objects.active
    if active is None:
        return None, None
    if active.type == "MESH" and active.get(CONTROLLER_KEY) is None:
        state = binding_status(active)
        if state in {DUPLICATE_UNBOUND, UUID_CONFLICT, CONTROLLER_CONFLICT, SHARED_DATA}:
            return None, None
        return active, find_controller(active)
    source = source_for_controller(active)
    if source is not None:
        return source, active
    return None, None


def find_source_by_uuid(source_uuid: str) -> bpy.types.Object | None:
    """Resolve a UUID only when it maps to exactly one valid bound Source."""
    if not source_uuid:
        return None
    if len(source_objects_by_uuid(source_uuid)) != 1:
        return None
    matches = [
        source for source in source_objects_by_uuid(source_uuid)
        if binding_status(source) == READY
    ]
    return matches[0] if len(matches) == 1 else None


def source_controller_pairs() -> list[tuple[bpy.types.Object, bpy.types.Object]]:
    pairs = []
    for source in _source_objects():
        if binding_status(source) != READY:
            continue
        controller = find_controller(source)
        if controller is not None:
            pairs.append((source, controller))
    return pairs


def orphaned_owned_objects() -> list[bpy.types.Object]:
    """Return marked objects without a valid structural owner.

    A duplicate or temporarily stale owner marker is not sufficient evidence to
    delete an object. Preserve such objects for explicit recovery.
    """
    source_uuids = {
        str(obj.get(SOURCE_UUID_KEY))
        for obj in _source_objects()
        if obj.get(SOURCE_UUID_KEY)
    }
    result = []
    for obj in bpy.data.objects:
        controller_owner = obj.get(CONTROLLER_KEY)
        face_owner = obj.get(FACE_SOURCE_UUID_KEY)
        if obj.get(UNBOUND_COPY_KEY):
            continue
        parent_is_source = getattr(obj.parent, "type", None) == "MESH" and obj.parent.get(CONTROLLER_KEY) is None
        # A Controller is owned only by its direct Source parent. A matching
        # copied UUID alone cannot make a detached Controller operational.
        if controller_owner and not parent_is_source:
            result.append(obj)
        elif face_owner and str(face_owner) not in source_uuids and not parent_is_source:
            result.append(obj)
    return result


def controller_collection(source: bpy.types.Object, scene: bpy.types.Scene) -> bpy.types.Collection:
    return source.users_collection[0] if source.users_collection else scene.collection


def select_only(context: bpy.types.Context, obj: bpy.types.Object) -> None:
    for candidate in context.view_layer.objects:
        candidate.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj
