"""Mesh and persistent-ID adapter for Source objects."""

from __future__ import annotations

import base64
import hashlib
import json
import bmesh
import bpy
import zlib

from .. import runtime
from ..constants import *
from ..storage import controls, hidden, json_set, migrate_control_schema, validate_control_storage
from ..core.controls import control_effective
from ..core.patches import partition_faces


def _topology_records(source: bpy.types.Object, allow_unassigned: bool = False) -> dict:
    """Read ID-addressed topology without trusting Blender element indices."""
    mesh = source.data
    if source.mode == "EDIT":
        bm = bmesh.from_edit_mesh(mesh)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.faces.ensure_lookup_table()
        vertex_layer = bm.verts.layers.int.get(VID_ATTR)
        edge_layer = bm.edges.layers.int.get(EID_ATTR)
        if vertex_layer is None or edge_layer is None:
            raise ValueError("SOURCE_ID_LAYERS_MISSING")
        vertex_ids = [int(vertex[vertex_layer]) for vertex in bm.verts]
        edge_ids = [int(edge[edge_layer]) for edge in bm.edges]
        index_vid = {vertex.index: int(vertex[vertex_layer]) for vertex in bm.verts}
        edges = [
            {"id": int(edge[edge_layer]),
             "vertices": sorted(index_vid[vertex.index] for vertex in edge.verts)}
            for edge in bm.edges
        ]
        faces = []
        for face_index, face in enumerate(bm.faces):
            vertices = sorted(index_vid[vertex.index] for vertex in face.verts)
            edge_ids = sorted(int(edge[edge_layer]) for edge in face.edges)
            face_id = (f"new:{face_index}" if any(value <= 0 for value in vertices)
                       else "f:" + ":".join(map(str, vertices)))
            faces.append({"id": face_id,
                          "vertices": vertices, "edges": edge_ids})
    else:
        vertex_layer = mesh.attributes.get(VID_ATTR)
        edge_layer = mesh.attributes.get(EID_ATTR)
        if vertex_layer is None or edge_layer is None:
            raise ValueError("SOURCE_ID_LAYERS_MISSING")
        if (vertex_layer.domain != "POINT" or vertex_layer.data_type != "INT"
                or edge_layer.domain != "EDGE" or edge_layer.data_type != "INT"
                or len(vertex_layer.data) != len(mesh.vertices)
                or len(edge_layer.data) != len(mesh.edges)):
            raise ValueError("STALE_MAPPING")
        vertex_ids = [int(item.value) for item in vertex_layer.data]
        edge_ids = [int(item.value) for item in edge_layer.data]
        index_vid = list(vertex_ids)
        edges = [
            {"id": int(edge_layer.data[edge.index].value),
             "vertices": sorted(index_vid[index] for index in edge.vertices)}
            for edge in mesh.edges
        ]
        edge_by_vertices = {
            frozenset(edge.vertices): int(edge_layer.data[edge.index].value)
            for edge in mesh.edges
        }
        faces = []
        for face_index, polygon in enumerate(mesh.polygons):
            vertices = sorted(index_vid[index] for index in polygon.vertices)
            edge_ids_for_face = sorted(
                edge_by_vertices[frozenset((polygon.vertices[index],
                                             polygon.vertices[(index + 1) % len(polygon.vertices)]))]
                for index in range(len(polygon.vertices))
            )
            face_id = (f"new:{face_index}" if any(value <= 0 for value in vertices)
                       else "f:" + ":".join(map(str, vertices)))
            faces.append({"id": face_id,
                          "vertices": vertices, "edges": edge_ids_for_face})

    for values in (vertex_ids, edge_ids):
        nonzero = [value for value in values if value > 0]
        if not allow_unassigned and any(value <= 0 for value in values):
            raise ValueError("STALE_MAPPING")
        if len(nonzero) != len(set(nonzero)):
            raise ValueError("STALE_MAPPING")
        if not allow_unassigned and len(nonzero) != len(values):
            raise ValueError("STALE_MAPPING")
    if len({face["id"] for face in faces}) != len(faces):
        raise ValueError("STALE_MAPPING")
    return {"vertices": vertex_ids, "edges": edges, "faces": faces}


def _encode_topology_snapshot(records: dict) -> str:
    payload = {
        "v": sorted(records["vertices"]),
        "e": sorted([[item["id"], *item["vertices"]] for item in records["edges"]]),
        "f": sorted([[item["id"], item["vertices"], item["edges"]]
                     for item in records["faces"]]),
    }
    packed = zlib.compress(json.dumps(payload, separators=(",", ":"),
                                   sort_keys=True).encode("utf-8"), level=9)
    return base64.b64encode(packed).decode("ascii")


def _decode_topology_snapshot(source: bpy.types.Object) -> dict:
    encoded = source.get(TOPOLOGY_SNAPSHOT_KEY)
    if not isinstance(encoded, str) or not encoded:
        raise ValueError("TOPOLOGY_SNAPSHOT_MISSING")
    if str(source.get(TOPOLOGY_SNAPSHOT_FINGERPRINT_KEY, "")) != str(source.get(TOPOLOGY_KEY, "")):
        raise ValueError("TOPOLOGY_SNAPSHOT_INVALID")
    try:
        payload = json.loads(zlib.decompress(base64.b64decode(encoded)).decode("utf-8"))
        if set(payload) != {"v", "e", "f"}:
            raise ValueError
        vertices = {int(value) for value in payload["v"]}
        edges = {int(item[0]): tuple(sorted((int(item[1]), int(item[2]))))
                 for item in payload["e"]}
        faces = {str(item[0]): {"id": str(item[0]),
                                "vertices": sorted(int(value) for value in item[1]),
                                "edges": sorted(int(value) for value in item[2])}
                 for item in payload["f"]}
        if (any(value <= 0 for value in vertices)
                or len(edges) != len(payload["e"])
                or len(faces) != len(payload["f"])
                or any(edge_id <= 0 or len(set(endpoints)) != 2
                       or not set(endpoints) <= vertices for edge_id, endpoints in edges.items())
                or any(face["id"] != "f:" + ":".join(map(str, face["vertices"]))
                       or len(face["vertices"]) < 3
                       or len(face["vertices"]) != len(set(face["vertices"]))
                       or not set(face["vertices"]) <= vertices
                       or len(face["edges"]) < 3
                       or len(face["edges"]) != len(set(face["edges"]))
                       or not set(face["edges"]) <= set(edges)
                       for face in faces.values())):
            raise ValueError
        return {"vertices": vertices, "edges": edges, "faces": faces}
    except (IndexError, KeyError, TypeError, ValueError, zlib.error, base64.binascii.Error) as exc:
        raise ValueError("TOPOLOGY_SNAPSHOT_INVALID") from exc


def _topology_repair_analysis(source: bpy.types.Object) -> dict:
    """Classify a topology edit against stored control-patch connectivity."""
    baseline = _decode_topology_snapshot(source)
    current = _topology_records(source, allow_unassigned=True)
    vertex_ids = current["vertices"]
    edge_ids = [item["id"] for item in current["edges"]]
    if (any(value < 0 for value in vertex_ids + edge_ids)
            or len([value for value in vertex_ids if value > 0]) != len(set(value for value in vertex_ids if value > 0))
            or len([value for value in edge_ids if value > 0]) != len(set(value for value in edge_ids if value > 0))):
        raise ValueError("STALE_MAPPING")

    current_vertices = {value for value in vertex_ids if value > 0}
    current_edges = {item["id"]: tuple(item["vertices"]) for item in current["edges"] if item["id"] > 0}
    missing_vertices = baseline["vertices"] - current_vertices
    missing_edges = set(baseline["edges"]) - set(current_edges)
    definitions = controls(source)
    referenced_vertices = set(hidden(source, HIDDEN_VIDS_KEY))
    referenced_edges = set(hidden(source, HIDDEN_EIDS_KEY))
    for control in definitions:
        referenced_vertices.update(int(value) for field in ("vertex_ids", "hidden_vertex_ids")
                                   for value in control.get(field, []))
        referenced_edges.update(int(value) for field in ("edge_ids", "hidden_edge_ids")
                                for value in control.get(field, []))
    if (not referenced_vertices <= baseline["vertices"]
            or not referenced_edges <= set(baseline["edges"])):
        raise ValueError("STALE_MAPPING")
    if missing_vertices & referenced_vertices or missing_edges & referenced_edges:
        raise ValueError("STALE_MAPPING")

    old_edge_vids = baseline["edges"]
    hidden_vertices = set(hidden(source, HIDDEN_VIDS_KEY))
    hidden_edges = set(hidden(source, HIDDEN_EIDS_KEY))
    incidences = []
    cut_edges = set()
    effective_control_vertices = set()
    effective_control_edges = set()
    for control in definitions:
        protection_control = dict(control)
        protection_control["enabled"] = True
        protection_control["hidden_vertex_ids"] = []
        protection_control["hidden_edge_ids"] = []
        effective_vertices, effective_edges = control_effective(
            protection_control, old_edge_vids, set(), set(), set(old_edge_vids)
        )
        explicit_nodes = set(effective_vertices)
        explicit_nodes.difference_update(
            vertex for edge_id in effective_edges for vertex in old_edge_vids[edge_id]
        )
        incidences.append((str(control.get("control_uuid")), effective_vertices,
                           effective_edges, explicit_nodes))
        cut_edges.update(effective_edges)
        effective_control_vertices.update(effective_vertices)
        effective_control_edges.update(effective_edges)
    old_face_records = list(baseline["faces"].values())
    old_face_records = [
        {"face_id": face["id"], "vertex_ids": face["vertices"],
         "edge_ids": face["edges"]}
        for face in old_face_records
    ]
    old_partition = partition_faces(old_face_records, cut_edges, definitions, incidences)
    protected_face_ids = {
        face_id
        for control in definitions
        for patch_id in old_partition["control_patch_ids"].get(str(control.get("control_uuid")), [])
        for patch in old_partition["patches"] if patch["patch_id"] == patch_id
        for face_id in patch["face_ids"]
    }
    protected_faces = {face_id: baseline["faces"][face_id] for face_id in protected_face_ids}
    protected_vertices = {value for face in protected_faces.values() for value in face["vertices"]}
    protected_edges = {value for face in protected_faces.values() for value in face["edges"]}
    protected_vertices.update(effective_control_vertices)
    protected_edges.update(effective_control_edges)
    protected_edges.update(
        edge_id for edge_id, endpoints in baseline["edges"].items()
        if effective_control_vertices.intersection(endpoints)
    )
    current_faces = {item["id"]: item for item in current["faces"]}
    if any(current_faces.get(face_id) != face for face_id, face in protected_faces.items()):
        raise ValueError("STALE_MAPPING")
    if any(face_id not in baseline["faces"] and
           (set(face["vertices"]) & protected_vertices or set(face["edges"]) & protected_edges)
           for face_id, face in current_faces.items()):
        raise ValueError("STALE_MAPPING")
    if any((edge["id"] == 0 or edge["id"] not in baseline["edges"])
           and set(edge["vertices"]) & protected_vertices for edge in current["edges"]):
        raise ValueError("STALE_MAPPING")
    if any(current_edges.get(edge_id) != baseline["edges"].get(edge_id)
           for edge_id in protected_edges):
        raise ValueError("STALE_MAPPING")

    return {
        "safe": True,
        "added_vertices": len([value for value in vertex_ids if value == 0]) +
                          len(current_vertices - baseline["vertices"]),
        "added_edges": len([value for value in edge_ids if value == 0]) +
                       len(set(current_edges) - set(baseline["edges"])),
        "removed_vertices": len(missing_vertices),
        "removed_edges": len(missing_edges),
        "protected_faces": len(protected_faces),
        "changed_topology": _topology_fingerprint(source) != str(source.get(TOPOLOGY_KEY, "")),
    }


def _capture_topology_snapshot(source: bpy.types.Object) -> None:
    source[TOPOLOGY_SNAPSHOT_KEY] = _encode_topology_snapshot(_topology_records(source))
    source[TOPOLOGY_SNAPSHOT_FINGERPRINT_KEY] = str(source.get(TOPOLOGY_KEY, ""))


def _repair_source_topology(source: bpy.types.Object) -> dict:
    """Assign IDs only to unassigned additions after a passing preflight."""
    report = _topology_repair_analysis(source)
    next_vid = max(int(source.get(NEXT_VID_KEY, 1)), 1)
    next_eid = max(int(source.get(NEXT_EID_KEY, 1)), 1)
    if source.mode == "EDIT":
        bm = bmesh.from_edit_mesh(source.data)
        vertex_layer = bm.verts.layers.int.get(VID_ATTR)
        edge_layer = bm.edges.layers.int.get(EID_ATTR)
        if vertex_layer is None or edge_layer is None:
            raise ValueError("SOURCE_ID_LAYERS_MISSING")
        used_vertices = {int(vertex[vertex_layer]) for vertex in bm.verts if int(vertex[vertex_layer]) > 0}
        used_edges = {int(edge[edge_layer]) for edge in bm.edges if int(edge[edge_layer]) > 0}
        for vertex in bm.verts:
            if int(vertex[vertex_layer]) <= 0:
                while next_vid in used_vertices:
                    next_vid += 1
                vertex[vertex_layer] = next_vid
                used_vertices.add(next_vid)
                next_vid += 1
        for edge in bm.edges:
            if int(edge[edge_layer]) <= 0:
                while next_eid in used_edges:
                    next_eid += 1
                edge[edge_layer] = next_eid
                used_edges.add(next_eid)
                next_eid += 1
        bmesh.update_edit_mesh(source.data, loop_triangles=False, destructive=False)
    else:
        vertex_attr = source.data.attributes.get(VID_ATTR)
        edge_attr = source.data.attributes.get(EID_ATTR)
        if vertex_attr is None or edge_attr is None:
            raise ValueError("SOURCE_ID_LAYERS_MISSING")
        used_vertices = {int(item.value) for item in vertex_attr.data if int(item.value) > 0}
        used_edges = {int(item.value) for item in edge_attr.data if int(item.value) > 0}
        for item in vertex_attr.data:
            if int(item.value) <= 0:
                while next_vid in used_vertices:
                    next_vid += 1
                item.value = next_vid
                used_vertices.add(next_vid)
                next_vid += 1
        for item in edge_attr.data:
            if int(item.value) <= 0:
                while next_eid in used_edges:
                    next_eid += 1
                item.value = next_eid
                used_edges.add(next_eid)
                next_eid += 1
        source.data.update()
    source[NEXT_VID_KEY] = max(next_vid, max(used_vertices or {0}) + 1)
    source[NEXT_EID_KEY] = max(next_eid, max(used_edges or {0}) + 1)
    source[TOPOLOGY_KEY] = _topology_fingerprint(source)
    _capture_topology_snapshot(source)
    runtime.TOPOLOGY_STATES.pop(source.as_pointer(), None)
    runtime.MAPPING_CACHE.pop(source.as_pointer(), None)
    runtime.PATCH_CACHE.pop(source.as_pointer(), None)
    runtime.PATCH_OVERLAY_CACHE.pop(source.as_pointer(), None)
    runtime.FACE_CACHE.pop(source.as_pointer(), None)
    runtime.OVERLAY_CACHE.clear()
    return report


def _is_valid_source(obj: bpy.types.Object | None) -> bool:
    return (
        obj is not None
        and obj.type == "MESH"
        and obj.library is None
        and obj.data is not None
        and obj.data.users == 1
    )


def _topology_fingerprint(source: bpy.types.Object) -> str:
    mesh = source.data
    if source.mode == "EDIT":
        bm = bmesh.from_edit_mesh(mesh)
        bm.verts.index_update()
        payload = {"vertices": len(bm.verts), "edges": [tuple(sorted(vert.index for vert in edge.verts)) for edge in bm.edges], "faces": [tuple(vert.index for vert in face.verts) for face in bm.faces]}
    else:
        payload = {
            "vertices": len(mesh.vertices),
            "edges": [tuple(sorted(edge.vertices)) for edge in mesh.edges],
            "faces": [tuple(poly.vertices) for poly in mesh.polygons],
        }
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode("utf-8")).hexdigest()


def _validate_source_topology(source: bpy.types.Object) -> None:
    stored = source.get(TOPOLOGY_KEY)
    actual = _topology_fingerprint(source)
    if stored and stored != actual and controls(source):
        runtime.TOPOLOGY_STATES[source.as_pointer()] = {
            "state": "PAUSED", "expected": str(stored), "actual": actual,
        }
        raise ValueError("TOPOLOGY_CHANGED")
    runtime.TOPOLOGY_STATES.pop(source.as_pointer(), None)


def _topology_state(source: bpy.types.Object | None) -> dict:
    if source is None:
        return {"state": "UNBOUND"}
    if source.get(UNBOUND_COPY_KEY):
        return {"state": "UNBOUND"}
    state = runtime.TOPOLOGY_STATES.get(source.as_pointer())
    if state is not None:
        return dict(state)
    stored = str(source.get(TOPOLOGY_KEY, ""))
    if stored and controls(source):
        actual = _topology_fingerprint(source)
        if actual != stored:
            state = {"state": "PAUSED", "expected": stored, "actual": actual}
            runtime.TOPOLOGY_STATES[source.as_pointer()] = state
            return dict(state)
    return {"state": "READY" if source.get(SOURCE_UUID_KEY) else "UNBOUND"}


def _modifier_signature(source: bpy.types.Object | None) -> tuple:
    """Return display-relevant modifier identity without evaluating geometry."""
    if source is None:
        return ()
    return tuple(
        (
            modifier.name,
            modifier.type,
            bool(modifier.show_viewport),
            bool(modifier.show_in_editmode),
            bool(getattr(modifier, "show_on_cage", False)),
        )
        for modifier in source.modifiers
    )


def _ensure_attribute(mesh: bpy.types.Mesh, name: str, domain: str):
    attr = mesh.attributes.get(name)
    if attr is not None and (attr.data_type != "INT" or attr.domain != domain):
        mesh.attributes.remove(attr)
        attr = None
    return attr or mesh.attributes.new(name=name, type="INT", domain=domain)


def _ensure_source_ids(source: bpy.types.Object) -> None:
    if not _is_valid_source(source):
        raise ValueError("SOURCE_NOT_EDITABLE")
    validate_control_storage(source)
    mesh = source.data
    runtime.MAPPING_CACHE.pop(source.as_pointer(), None)
    current_fingerprint = _topology_fingerprint(source)
    stored_fingerprint = source.get(TOPOLOGY_KEY)
    if stored_fingerprint and stored_fingerprint != current_fingerprint and controls(source):
        runtime.TOPOLOGY_STATES[source.as_pointer()] = {
            "state": "PAUSED", "expected": str(stored_fingerprint),
            "actual": current_fingerprint,
        }
        raise ValueError("TOPOLOGY_CHANGED")

    next_vid = int(source.get(NEXT_VID_KEY, 1))
    next_eid = int(source.get(NEXT_EID_KEY, 1))

    if source.mode == "EDIT":
        # Mesh.attributes is not the authoritative store while Blender is in
        # Edit Mode.  Creating/writing attributes there leaves the live BMesh
        # layers at their default value (zero), collapsing every selected
        # element to the same persistent ID.  Work on the edit BMesh directly
        # so +, Sync and control selection see the IDs immediately.
        bm = bmesh.from_edit_mesh(mesh)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.verts.index_update()
        bm.edges.index_update()
        vid_layer = bm.verts.layers.int.get(VID_ATTR) or bm.verts.layers.int.new(VID_ATTR)
        eid_layer = bm.edges.layers.int.get(EID_ATTR) or bm.edges.layers.int.new(EID_ATTR)

        seen_vids: set[int] = set()
        for vert in bm.verts:
            value = int(vert[vid_layer])
            if value <= 0 or value in seen_vids:
                while next_vid in seen_vids:
                    next_vid += 1
                vert[vid_layer] = next_vid
                value = next_vid
                next_vid += 1
            seen_vids.add(value)

        seen_eids: set[int] = set()
        for edge in bm.edges:
            value = int(edge[eid_layer])
            if value <= 0 or value in seen_eids:
                while next_eid in seen_eids:
                    next_eid += 1
                edge[eid_layer] = next_eid
                value = next_eid
                next_eid += 1
            seen_eids.add(value)
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
    else:
        vid_attr = _ensure_attribute(mesh, VID_ATTR, "POINT")
        eid_attr = _ensure_attribute(mesh, EID_ATTR, "EDGE")

        seen_vids = set()
        for item in vid_attr.data:
            value = int(item.value)
            if value <= 0 or value in seen_vids:
                while next_vid in seen_vids:
                    next_vid += 1
                item.value = next_vid
                value = next_vid
                next_vid += 1
            seen_vids.add(value)

        seen_eids = set()
        for item in eid_attr.data:
            value = int(item.value)
            if value <= 0 or value in seen_eids:
                while next_eid in seen_eids:
                    next_eid += 1
                item.value = next_eid
                value = next_eid
                next_eid += 1
            seen_eids.add(value)

    source[NEXT_VID_KEY] = max(next_vid, max(seen_vids or {0}) + 1)
    source[NEXT_EID_KEY] = max(next_eid, max(seen_eids or {0}) + 1)
    source[TOPOLOGY_KEY] = current_fingerprint
    if NETWORK_REVISION_KEY not in source:
        source[NETWORK_REVISION_KEY] = 0
    migrate_control_schema(source, _source_edge_vids(source))
    json_set(source, CONTROLS_KEY, controls(source))
    json_set(source, HIDDEN_VIDS_KEY, sorted(hidden(source, HIDDEN_VIDS_KEY)))
    json_set(source, HIDDEN_EIDS_KEY, sorted(hidden(source, HIDDEN_EIDS_KEY)))
    mesh.update()
    if (str(source.get(TOPOLOGY_SNAPSHOT_FINGERPRINT_KEY, ""))
            != str(source.get(TOPOLOGY_KEY, ""))):
        _capture_topology_snapshot(source)


def _source_id_maps(source: bpy.types.Object) -> tuple[dict[int, int], dict[int, int]]:
    """Read stable IDs. Validation/assignment belongs to explicit operations only."""
    cache_key = source.as_pointer()
    signature = (source.data.as_pointer(), source.mode, len(source.data.vertices), len(source.data.edges))
    cached = runtime.MAPPING_CACHE.get(cache_key)
    if cached is not None and cached[0] == signature:
        return cached[1], cached[2]
    if source.mode == "EDIT":
        bm = bmesh.from_edit_mesh(source.data)
        bm.verts.ensure_lookup_table()
        bm.edges.ensure_lookup_table()
        bm.verts.index_update()
        bm.edges.index_update()
        vid_layer = bm.verts.layers.int.get(VID_ATTR)
        eid_layer = bm.edges.layers.int.get(EID_ATTR)
        if vid_layer is None or eid_layer is None:
            raise ValueError("SOURCE_ID_LAYERS_MISSING")
        vids = {int(vert[vid_layer]): vert.index for vert in bm.verts}
        eids = {int(edge[eid_layer]): edge.index for edge in bm.edges}
        index_vids = [int(vert[vid_layer]) for vert in bm.verts]
        edge_vids = {int(edge[eid_layer]): tuple(int(v[vid_layer]) for v in edge.verts) for edge in bm.edges}
    else:
        vid_attr = source.data.attributes.get(VID_ATTR)
        eid_attr = source.data.attributes.get(EID_ATTR)
        if vid_attr is None or eid_attr is None:
            raise ValueError("SOURCE_ID_LAYERS_MISSING")
        vids = {int(item.value): index for index, item in enumerate(vid_attr.data)}
        eids = {int(item.value): index for index, item in enumerate(eid_attr.data)}
        index_vids = [int(item.value) for item in vid_attr.data]
        edge_vids = {int(eid_attr.data[edge.index].value): tuple(index_vids[i] for i in edge.vertices) for edge in source.data.edges}
    runtime.MAPPING_CACHE[cache_key] = (signature, vids, eids, index_vids, edge_vids)
    return vids, eids


def _source_edge_vids(source):
    _source_id_maps(source)
    return runtime.MAPPING_CACHE[source.as_pointer()][4]


def _source_vertices(source, shape_key=None):
    """Borrow the selected Shape Key coordinates, or base vertices when absent."""
    if source.mode == "EDIT":
        bm = bmesh.from_edit_mesh(source.data)
        bm.verts.ensure_lookup_table()
        return bm.verts
    if isinstance(shape_key, str) and shape_key == BASE_MESH_TARGET:
        return source.data.vertices
    key = shape_key if shape_key is not None else _active_shape_key(source)
    if key is not None:
        return key.data
    return source.data.vertices


def _active_shape_key(source: bpy.types.Object | None):
    """Return Source's active key; ShapeKey.data is the editable coordinate store."""
    if source is None or source.type != "MESH" or source.data is None:
        return None
    shape_keys = source.data.shape_keys
    if shape_keys is None or not shape_keys.key_blocks:
        return None
    index = int(source.active_shape_key_index)
    if not 0 <= index < len(shape_keys.key_blocks):
        raise ValueError("SHAPE_KEY_TARGET_INVALID")
    return shape_keys.key_blocks[index]


def _resolve_shape_key(source: bpy.types.Object, target=None):
    """Resolve an explicit key reference and reject stale/foreign KeyBlocks."""
    if target is None:
        return _active_shape_key(source)
    if isinstance(target, str):
        if target == BASE_MESH_TARGET and source.data.shape_keys is None:
            return None
        raise ValueError("SHAPE_KEY_TARGET_INVALID")
    if isinstance(target, dict):
        kind = target.get("kind")
        if kind == "BASE":
            if source.data.shape_keys is None:
                return None
            raise ValueError("SHAPE_KEY_TARGET_INVALID")
        if kind != "KEY":
            raise ValueError("SHAPE_KEY_TARGET_INVALID")
        blocks = source.data.shape_keys.key_blocks if source.data.shape_keys else ()
        for index, key in enumerate(blocks):
            if (int(key.as_pointer()) == target.get("pointer")
                    and str(key.name) == target.get("name")
                    and index == target.get("index")):
                return key
        raise ValueError("SHAPE_KEY_TARGET_INVALID")
    try:
        target_pointer = target.as_pointer()
        target_name = str(target.name)
        blocks = source.data.shape_keys.key_blocks if source.data.shape_keys else ()
        for key in blocks:
            if key.as_pointer() == target_pointer and key.name == target_name:
                return key
    except (AttributeError, ReferenceError, RuntimeError):
        pass
    raise ValueError("SHAPE_KEY_TARGET_INVALID")


def _shape_key_signature(source: bpy.types.Object) -> tuple:
    """Capture the active target identity and write permission for one operation."""
    key = _active_shape_key(source)
    if key is None:
        return (source.data.as_pointer(), None, "", False, len(source.data.vertices),
                False, int(source.active_shape_key_index))
    return (
        source.data.as_pointer(), key.as_pointer(), str(key.name),
        bool(key.lock_shape), len(key.data), bool(source.data.shape_keys.use_relative),
        int(source.active_shape_key_index),
    )


def _shape_key_evaluation_signature(source: bpy.types.Object) -> tuple:
    """Capture properties that can change the evaluated Source surface."""
    shape_keys = source.data.shape_keys if source.type == "MESH" and source.data else None
    if shape_keys is None:
        return (source.data.as_pointer(), None, bool(source.show_only_shape_key))
    return (
        source.data.as_pointer(), shape_keys.as_pointer(), bool(shape_keys.use_relative),
        float(shape_keys.eval_time), bool(source.show_only_shape_key),
        int(source.active_shape_key_index),
        tuple((key.as_pointer(), str(key.name), float(key.value), bool(key.mute))
              for key in shape_keys.key_blocks),
    )


def _positions_by_source_id(mesh, expected_ids, coordinates=None) -> dict[int, object]:
    """Read one-to-one Source coordinates from a mesh carrying DANP vertex IDs."""
    ids = mesh.attributes.get(VID_ATTR)
    if ids is None or ids.domain != "POINT" or ids.data_type != "INT":
        raise ValueError("EVALUATED_SOURCE_ID_MAPPING_UNAVAILABLE")
    if len(ids.data) != len(mesh.vertices):
        raise ValueError("EVALUATED_SOURCE_ID_MAPPING_UNAVAILABLE")
    if coordinates is None:
        coordinates = mesh.vertices
    if len(coordinates) != len(mesh.vertices):
        raise ValueError("EVALUATED_SOURCE_ID_MAPPING_UNAVAILABLE")
    positions = {}
    for index, item in enumerate(ids.data):
        vertex_id = int(item.value)
        if vertex_id not in expected_ids or vertex_id in positions:
            raise ValueError("EVALUATED_SOURCE_ID_MAPPING_UNAVAILABLE")
        positions[vertex_id] = coordinates[index].co.copy()
    if positions.keys() != expected_ids.keys():
        raise ValueError("EVALUATED_SOURCE_ID_MAPPING_UNAVAILABLE")
    return positions


def _evaluated_source_positions(source: bpy.types.Object) -> dict[int, object]:
    """Read visible Source coordinates by persistent ID on the Source cage.

    Deforming modifiers can preserve a one-to-one ID mapping and are included.
    Topology-changing modifiers such as Subdivision duplicate or discard Source
    IDs. In that case, ask Blender to mix Shape Keys on an independent temporary
    mesh, keeping the Controller on Source cage vertices. An unlinked object's
    evaluated_get() does not reliably apply its Shape Key values.
    """
    expected_ids, _ = _source_id_maps(source)
    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = source.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
    if mesh is None:
        raise ValueError("EVALUATED_SOURCE_UNAVAILABLE")
    mapping_unavailable = False
    try:
        try:
            return _positions_by_source_id(mesh, expected_ids)
        except ValueError as exc:
            if str(exc) != "EVALUATED_SOURCE_ID_MAPPING_UNAVAILABLE":
                raise
            mapping_unavailable = True
    finally:
        evaluated.to_mesh_clear()

    if not mapping_unavailable:
        raise ValueError("EVALUATED_SOURCE_UNAVAILABLE")

    temporary = source.copy()
    temporary_mesh = None
    try:
        temporary_mesh = source.data.copy()
        temporary.data = temporary_mesh
        for modifier in list(temporary.modifiers):
            temporary.modifiers.remove(modifier)
        mixed_key = temporary.shape_key_add(name="DANP Temporary Mix", from_mix=True)
        return _positions_by_source_id(temporary_mesh, expected_ids, mixed_key.data)
    finally:
        bpy.data.objects.remove(temporary, do_unlink=True)
        if temporary_mesh is not None and temporary_mesh.users == 0:
            bpy.data.meshes.remove(temporary_mesh)


def _shape_key_target_record(source: bpy.types.Object, target) -> dict:
    """Store stable scalar identity in Undo history, never a KeyBlock RNA wrapper."""
    if isinstance(target, str) and target == BASE_MESH_TARGET:
        return {"kind": "BASE"}
    key = _resolve_shape_key(source, target)
    if key is None:
        return {"kind": "BASE"}
    blocks = source.data.shape_keys.key_blocks
    return {
        "kind": "KEY", "pointer": int(key.as_pointer()), "name": str(key.name),
        "index": next(index for index, item in enumerate(blocks) if item == key),
    }


def _source_vid(source: bpy.types.Object, vertex_index: int) -> int:
    if source.mode == "EDIT":
        bm = bmesh.from_edit_mesh(source.data)
        bm.verts.ensure_lookup_table()
        layer = bm.verts.layers.int.get(VID_ATTR)
        if layer is None:
            raise ValueError("SOURCE_ID_LAYERS_MISSING")
        return int(bm.verts[vertex_index][layer])
    return int(source.data.attributes[VID_ATTR].data[vertex_index].value)


def _source_co(source: bpy.types.Object, vertex_index: int):
    if source.mode == "EDIT":
        bm = bmesh.from_edit_mesh(source.data)
        bm.verts.ensure_lookup_table()
        return bm.verts[vertex_index].co
    return _source_vertices(source)[vertex_index].co
