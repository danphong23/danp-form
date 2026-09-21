"""Mesh and persistent-ID adapter for Source objects."""

from __future__ import annotations

import hashlib
import json
import bmesh
import bpy

from .. import runtime
from ..constants import *
from ..storage import controls, hidden, json_set, migrate_control_schema, validate_control_storage

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
    if stored and stored != _topology_fingerprint(source) and controls(source):
        raise ValueError("STALE_MAPPING")


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
        raise ValueError("STALE_MAPPING")

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


def _source_vertices(source):
    """Borrow vertices for one synchronous read, never across callbacks or undo."""
    if source.mode == "EDIT":
        bm = bmesh.from_edit_mesh(source.data)
        bm.verts.ensure_lookup_table()
        return bm.verts
    return source.data.vertices


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
    return source.data.vertices[vertex_index].co
