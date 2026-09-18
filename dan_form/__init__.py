"""DANP Form Phase 1/2: Source binding, persistent controls, and exact proxy sync."""

from __future__ import annotations

import hashlib
import json
import uuid
from types import SimpleNamespace

import bmesh
import bpy
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from mathutils import Matrix


ADDON_ID = "dan_form"
SCHEMA_VERSION = "2"
SOURCE_UUID_KEY = "dan_form_source_uuid"
CONTROLLER_KEY = "dan_form_controller"
SCHEMA_KEY = "dan_form_schema_version"
VID_ATTR = "dan_form_vid"
EID_ATTR = "dan_form_eid"
PROXY_VID_ATTR = "dan_form_proxy_vid"
PROXY_EID_ATTR = "dan_form_proxy_eid"
CONTROLS_KEY = "dan_form_controls"
HIDDEN_VIDS_KEY = "dan_form_hidden_vertex_ids"
HIDDEN_EIDS_KEY = "dan_form_hidden_edge_ids"
NEXT_VID_KEY = "dan_form_next_vid"
NEXT_EID_KEY = "dan_form_next_eid"
TOPOLOGY_KEY = "dan_form_topology_fingerprint"
NETWORK_REVISION_KEY = "dan_form_control_network_revision"
PROXY_GENERATION_KEY = "dan_form_proxy_generation"
UI_SOURCE_UUID_KEY = "dan_form_ui_source_uuid"
OVERLAY_HANDLE = None
_SYNC_GUARD = False
_UI_SYNC_GUARD = False
_MAPPING_CACHE = {}
_UI_SIGNATURES = {}
_ACTIVE_CONTROL_UUIDS = {}
_RETURN_MODES = {}
_PROXY_SNAPSHOTS = {}
_TOPOLOGY_KEYMAPS = []
_CONTROL_KEYMAPS = []
_NETWORK_CACHE = {}
_PATCH_CACHE = {}
_PATCH_OVERLAY_CACHE = {}
_OVERLAY_CACHE = {}
_XRAY_SHOW_IN_FRONT = {}
_PICK_PREVIEW = {}
_PICK_SESSION = 0
VIEWPORT_HIDDEN_KEY = "dan_form_controls_viewport_hidden"

bl_info = {
    "name": "DANP Form",
    "author": "DANP Form",
    "version": (0, 3, 0),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar > DANP Form",
    "category": "Mesh",
    "description": "Source-backed controller shell for template mesh editing",
}


def _json_get(obj: bpy.types.ID, key: str, default):
    value = obj.get(key)
    if value is None:
        return default
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError):
            return default
        return decoded
    return value


def _json_set(obj: bpy.types.ID, key: str, value) -> None:
    obj[key] = json.dumps(value, separators=(",", ":"), sort_keys=True)


def _controls(source: bpy.types.Object) -> list[dict]:
    value = _json_get(source, CONTROLS_KEY, [])
    return value if isinstance(value, list) else []


def _control(source: bpy.types.Object | None, control_uuid: str) -> dict | None:
    if source is None:
        return None
    return next((item for item in _controls(source) if item.get("control_uuid") == control_uuid), None)


def _hidden(source: bpy.types.Object, key: str) -> set[int]:
    value = _json_get(source, key, [])
    return {int(item) for item in value if isinstance(item, int) or str(item).isdigit()}


def _source_uuid(source: bpy.types.Object) -> str:
    value = source.get(SOURCE_UUID_KEY)
    if not isinstance(value, str) or not value:
        value = uuid.uuid4().hex
        source[SOURCE_UUID_KEY] = value
    source[SCHEMA_KEY] = SCHEMA_VERSION
    return value


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
    if stored and stored != _topology_fingerprint(source) and _controls(source):
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
    mesh = source.data
    _MAPPING_CACHE.pop(source.as_pointer(), None)
    current_fingerprint = _topology_fingerprint(source)
    stored_fingerprint = source.get(TOPOLOGY_KEY)
    if stored_fingerprint and stored_fingerprint != current_fingerprint and _controls(source):
        raise ValueError("STALE_MAPPING")

    vid_attr = _ensure_attribute(mesh, VID_ATTR, "POINT")
    eid_attr = _ensure_attribute(mesh, EID_ATTR, "EDGE")
    next_vid = int(source.get(NEXT_VID_KEY, 1))
    next_eid = int(source.get(NEXT_EID_KEY, 1))

    seen: set[int] = set()
    for item in vid_attr.data:
        value = int(item.value)
        if value <= 0 or value in seen:
            while next_vid in seen:
                next_vid += 1
            item.value = next_vid
            value = next_vid
            next_vid += 1
        seen.add(value)
    max_vid = max(seen or {0})
    seen.clear()
    for item in eid_attr.data:
        value = int(item.value)
        if value <= 0 or value in seen:
            while next_eid in seen:
                next_eid += 1
            item.value = next_eid
            value = next_eid
            next_eid += 1
        seen.add(value)

    source[NEXT_VID_KEY] = max(next_vid, max_vid + 1)
    source[NEXT_EID_KEY] = max(next_eid, max(seen or {0}) + 1)
    source[TOPOLOGY_KEY] = current_fingerprint
    if NETWORK_REVISION_KEY not in source:
        source[NETWORK_REVISION_KEY] = 0
    _json_set(source, CONTROLS_KEY, _controls(source))
    _json_set(source, HIDDEN_VIDS_KEY, sorted(_hidden(source, HIDDEN_VIDS_KEY)))
    _json_set(source, HIDDEN_EIDS_KEY, sorted(_hidden(source, HIDDEN_EIDS_KEY)))
    mesh.update()


def _source_id_maps(source: bpy.types.Object) -> tuple[dict[int, int], dict[int, int]]:
    """Read stable IDs. Validation/assignment belongs to explicit operations only."""
    cache_key = source.as_pointer()
    signature = (source.data.as_pointer(), source.mode, len(source.data.vertices), len(source.data.edges))
    cached = _MAPPING_CACHE.get(cache_key)
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
    _MAPPING_CACHE[cache_key] = (signature, vids, eids, index_vids, edge_vids)
    return vids, eids


def _source_edge_vids(source):
    _source_id_maps(source)
    return _MAPPING_CACHE[source.as_pointer()][4]


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


def _find_controller(source: bpy.types.Object) -> bpy.types.Object | None:
    source_uuid = source.get(SOURCE_UUID_KEY)
    if not source_uuid:
        return None
    for obj in bpy.data.objects:
        if obj.get(CONTROLLER_KEY) == source_uuid and obj.type == "MESH":
            return obj
    return None


def _source_for_controller(controller: bpy.types.Object | None) -> bpy.types.Object | None:
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


def _context_source(context: bpy.types.Context) -> tuple[bpy.types.Object | None, bpy.types.Object | None]:
    """Resolve the active model; never reuse a stale scene pointer."""
    active = context.view_layer.objects.active
    if active is None:
        return None, None
    if active.type == "MESH" and active.get(CONTROLLER_KEY) is None:
        return active, _find_controller(active)
    source = _source_for_controller(active)
    if source is not None:
        return source, active
    return None, None


def _find_source_by_uuid(source_uuid: str) -> bpy.types.Object | None:
    if not source_uuid:
        return None
    return next(
        (obj for obj in bpy.data.objects if obj.type == "MESH" and obj.get(SOURCE_UUID_KEY) == source_uuid),
        None,
    )


def _control_state(source: bpy.types.Object, control: dict) -> tuple[str, int, int]:
    effective_vertices, effective_edges = _control_effective(source, control)
    total = len(control.get("vertex_ids", [])) + len(control.get("edge_ids", []))
    effective = len(effective_vertices) + len(effective_edges)
    state = "On" if effective == total else ("Hidden" if effective == 0 else "Partial")
    return state, effective, total


def _active_control(context: bpy.types.Context, source: bpy.types.Object) -> dict | None:
    scene = context.scene
    items = getattr(scene, "dan_form_control_items", None)
    index = int(getattr(scene, "dan_form_control_index", 0))
    if items is not None and 0 <= index < len(items):
        item = items[index]
        if item.source_uuid == source.get(SOURCE_UUID_KEY):
            return _control(source, item.control_uuid)
    return _control(source, getattr(scene, "dan_form_selected_control", ""))


def _sync_ui_list(scene: bpy.types.Scene, source: bpy.types.Object | None) -> None:
    """Project persistent definitions into a native Blender UIList collection."""
    global _UI_SYNC_GUARD
    items = getattr(scene, "dan_form_control_items", None)
    if items is None:
        return
    source_uuid = str(source.get(SOURCE_UUID_KEY, "")) if source is not None else ""
    token = (source_uuid, source.get(CONTROLS_KEY, "") if source is not None else "", source.get(HIDDEN_VIDS_KEY, "") if source is not None else "", source.get(HIDDEN_EIDS_KEY, "") if source is not None else "", source.mode if source is not None else "")
    if _UI_SIGNATURES.get(scene.as_pointer()) == token:
        return
    controls = _controls(source) if source is not None and source_uuid else []
    signature = []
    for control in controls:
        state, effective_count, total_count = _control_state(source, control)
        signature.append((str(control.get("control_uuid", "")), str(control.get("name", "Control")), state, effective_count, total_count))
    current_signature = [
        (item.control_uuid, item.control_name, item.state, item.effective_count, item.total_count)
        for item in items
        if item.source_uuid == source_uuid
    ]
    current_source = getattr(scene, "dan_form_ui_source_uuid", "")
    if current_source == source_uuid and current_signature == signature and len(items) == len(controls):
        _UI_SIGNATURES[scene.as_pointer()] = token
        return
    active_uuid = _ACTIVE_CONTROL_UUIDS.get(source_uuid, "")
    if current_source == source_uuid:
        active_uuid = getattr(scene, "dan_form_selected_control", "") or active_uuid
    _UI_SYNC_GUARD = True
    try:
        items.clear()
        for control in controls:
            item = items.add()
            item.control_uuid = str(control.get("control_uuid", ""))
            item.source_uuid = source_uuid
            item.control_name = str(control.get("name", "Control"))
            item.state, item.effective_count, item.total_count = _control_state(source, control)
        scene.dan_form_ui_source_uuid = source_uuid
        selected_index = next((i for i, item in enumerate(items) if item.control_uuid == active_uuid), 0)
        scene.dan_form_control_index = selected_index if items else 0
        scene.dan_form_selected_control = items[scene.dan_form_control_index].control_uuid if items else ""
        _ACTIVE_CONTROL_UUIDS[source_uuid] = scene.dan_form_selected_control
        _UI_SIGNATURES[scene.as_pointer()] = token
    finally:
        _UI_SYNC_GUARD = False


def _sync_context_ui_list(context: bpy.types.Context) -> None:
    source, _ = _context_source(context)
    _sync_ui_list(context.scene, source)
    _activate_ui_control(context.scene, context.scene.dan_form_selected_control)


def _activate_ui_control(scene: bpy.types.Scene, control_uuid: str) -> None:
    """Keep the row and UUID aligned after a rebuild triggers synchronous handlers."""
    global _UI_SYNC_GUARD
    for index, item in enumerate(scene.dan_form_control_items):
        if item.control_uuid != control_uuid:
            continue
        previous_guard = _UI_SYNC_GUARD
        _UI_SYNC_GUARD = True
        try:
            if scene.dan_form_control_index != index:
                scene.dan_form_control_index = index
            _ACTIVE_CONTROL_UUIDS[item.source_uuid] = control_uuid
        finally:
            _UI_SYNC_GUARD = previous_guard
        return


def _set_scene_context(context: bpy.types.Context, source: bpy.types.Object | None, controller: bpy.types.Object | None) -> None:
    scene = context.scene
    scene.dan_form_source = source
    scene.dan_form_controller = controller
    _update_overlay_display(scene, context)


def _source_controller_pairs() -> list[tuple[bpy.types.Object, bpy.types.Object]]:
    pairs = []
    for source in bpy.data.objects:
        if source.type != "MESH" or not source.get(SOURCE_UUID_KEY):
            continue
        controller = _find_controller(source)
        if controller is not None:
            pairs.append((source, controller))
    return pairs


def _controller_collection(source: bpy.types.Object, scene: bpy.types.Scene) -> bpy.types.Collection:
    return source.users_collection[0] if source.users_collection else scene.collection


def _select_only(context: bpy.types.Context, obj: bpy.types.Object) -> None:
    for candidate in context.view_layer.objects:
        candidate.select_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj


def _effective_proxy_elements(source: bpy.types.Object) -> tuple[list[int], list[int]]:
    controls = _controls(source)
    hidden_vids = _hidden(source, HIDDEN_VIDS_KEY)
    hidden_eids = _hidden(source, HIDDEN_EIDS_KEY)
    vid_to_index, eid_to_index = _source_id_maps(source)
    visible_edges: set[int] = set()
    cache_key = source.as_pointer()
    mapping = _MAPPING_CACHE[cache_key]
    token = (source.get(CONTROLS_KEY), source.get(HIDDEN_VIDS_KEY), source.get(HIDDEN_EIDS_KEY))
    cached = _NETWORK_CACHE.get(cache_key)
    if cached is not None and cached[0] is mapping and cached[1] == token:
        return list(cached[2]), list(cached[3])
    edge_vids = mapping[4]
    visible_vertices: set[int] = set()
    for control in controls:
        for edge_id in control.get("edge_ids", []):
            edge_id = int(edge_id)
            edge_index = eid_to_index.get(edge_id)
            if edge_index is None or edge_id in hidden_eids:
                continue
            endpoint_ids = set(edge_vids[edge_id])
            if endpoint_ids & hidden_vids:
                continue
            visible_edges.add(edge_id)
            visible_vertices.update(endpoint_ids)
        # Explicit point membership remains meaningful in mixed controls. For an
        # edge-only definition, endpoints are supplied by the effective edges.
        endpoint_ids = set()
        for edge_id in control.get("edge_ids", []):
            edge_index = eid_to_index.get(int(edge_id))
            if edge_index is not None:
                endpoint_ids.update(edge_vids[int(edge_id)])
        for vertex_id in control.get("vertex_ids", []):
            vertex_id = int(vertex_id)
            if vertex_id not in hidden_vids and vertex_id in vid_to_index and (
                not control.get("edge_ids") or vertex_id not in endpoint_ids
            ):
                visible_vertices.add(vertex_id)
    vertices, edges = sorted(visible_vertices), sorted(visible_edges)
    _NETWORK_CACHE[cache_key] = (mapping, token, vertices, edges)
    return list(vertices), list(edges)


def _control_intent(source: bpy.types.Object, control: dict) -> tuple[set[int], set[int]]:
    """Return edge and explicit-node intent for whole-definition actions."""
    _, edge_indices = _source_id_maps(source)
    edge_vids = _source_edge_vids(source)
    endpoint_ids: set[int] = set()
    for edge_id in control.get("edge_ids", []):
        edge_index = edge_indices.get(int(edge_id))
        if edge_index is None:
            continue
        endpoint_ids.update(edge_vids[int(edge_id)])
    edge_ids = {int(edge_id) for edge_id in control.get("edge_ids", []) if int(edge_id) in edge_indices}
    node_ids = {int(vertex_id) for vertex_id in control.get("vertex_ids", [])}
    if edge_ids:
        node_ids.difference_update(endpoint_ids)
    return edge_ids, node_ids


def _control_effective(source: bpy.types.Object, control: dict) -> tuple[set[int], set[int]]:
    hidden_vids = _hidden(source, HIDDEN_VIDS_KEY)
    hidden_eids = _hidden(source, HIDDEN_EIDS_KEY)
    _, edge_indices = _source_id_maps(source)
    edge_vids = _source_edge_vids(source)
    effective_edges: set[int] = set()
    effective_vertices: set[int] = set()
    for edge_id in control.get("edge_ids", []):
        edge_id = int(edge_id)
        edge_index = edge_indices.get(edge_id)
        if edge_index is None or edge_id in hidden_eids:
            continue
        endpoints = set(edge_vids[edge_id])
        if endpoints & hidden_vids:
            continue
        effective_edges.add(edge_id)
        effective_vertices.update(endpoints)
    _, explicit_nodes = _control_intent(source, control)
    effective_vertices.update(explicit_nodes - hidden_vids)
    return effective_vertices, effective_edges


def _source_face_records(source: bpy.types.Object) -> list[dict]:
    """Read Source faces using persistent vertex/edge IDs, never Blender indices."""
    vertex_ids, edge_ids = _source_id_maps(source)
    reverse_vertices = {index: vertex_id for vertex_id, index in vertex_ids.items()}
    reverse_edges = {index: edge_id for edge_id, index in edge_ids.items()}
    if source.mode == "EDIT":
        bm = bmesh.from_edit_mesh(source.data)
        bm.faces.ensure_lookup_table()
        return [
            {
                "face_id": "f:" + ":".join(str(reverse_vertices[v.index]) for v in sorted(face.verts, key=lambda item: reverse_vertices[item.index])),
                "vertex_ids": tuple(reverse_vertices[v.index] for v in face.verts),
                "edge_ids": tuple(reverse_edges[e.index] for e in face.edges),
            }
            for face in bm.faces
        ]
    return [
        {
            "face_id": "f:" + ":".join(str(reverse_vertices[index]) for index in sorted(polygon.vertices, key=lambda item: reverse_vertices[item])),
            "vertex_ids": tuple(reverse_vertices[index] for index in polygon.vertices),
            "edge_ids": tuple(reverse_edges[edge.index] for edge in source.data.edges
                               if set(edge.vertices).issubset(set(polygon.vertices))),
        }
        for polygon in source.data.polygons
    ]


def _patch_partition(source: bpy.types.Object) -> dict:
    """Derive connected Source face patches after removing enabled control cuts.

    The result is runtime data. Face/vertex/edge identity comes from Source IDs;
    the partition is never stored as a second geometric truth.
    """
    mapping = _source_id_maps(source)
    faces = _source_face_records(source)
    controls_token = source.get(CONTROLS_KEY, "")
    hidden_vertices = source.get(HIDDEN_VIDS_KEY, "")
    hidden_edges = source.get(HIDDEN_EIDS_KEY, "")
    topology = source.get(TOPOLOGY_KEY, "")
    token = (mapping, topology, controls_token, hidden_vertices, hidden_edges,
             tuple((face["face_id"], face["edge_ids"]) for face in faces))
    cached = _PATCH_CACHE.get(source.as_pointer())
    if cached is not None and cached[0] == token:
        return cached[1]

    _, effective_edges = _effective_proxy_elements(source)
    cut_edges = set(effective_edges)
    face_by_edge: dict[int, list[int]] = {}
    for index, face in enumerate(faces):
        for edge_id in face["edge_ids"]:
            face_by_edge.setdefault(int(edge_id), []).append(index)
    adjacency = [set() for _ in faces]
    for edge_id, incident in face_by_edge.items():
        if edge_id in cut_edges:
            continue
        for left in incident:
            adjacency[left].update(other for other in incident if other != left)

    face_patch: dict[int, str] = {}
    patches: list[dict] = []
    for seed in range(len(faces)):
        if seed in face_patch:
            continue
        stack = [seed]
        component = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(adjacency[current] - component)
        face_ids = sorted(faces[index]["face_id"] for index in component)
        patch_id = "p:" + hashlib.sha1("|".join(face_ids).encode("utf-8")).hexdigest()[:16]
        for index in component:
            face_patch[index] = patch_id
        component_edges = sorted({edge_id for index in component for edge_id in faces[index]["edge_ids"]})
        component_vertices = sorted({vertex_id for index in component for vertex_id in faces[index]["vertex_ids"]})
        boundary_edges = sorted({edge_id for edge_id in component_edges
                                 if len(face_by_edge.get(edge_id, [])) != 2
                                 or any(face_patch.get(other) != patch_id
                                        for other in face_by_edge.get(edge_id, []))})
        patches.append({
            "patch_id": patch_id,
            "face_ids": face_ids,
            "face_indices": sorted(component),
            "vertex_ids": component_vertices,
            "edge_ids": component_edges,
            "boundary_edge_ids": boundary_edges,
            "incident_control_uuids": [],
        })

    patch_by_id = {patch["patch_id"]: patch for patch in patches}
    for patch in patches:
        patch_edges = set(patch["boundary_edge_ids"])
        patch_vertices = set(patch["vertex_ids"])
        incident = []
        for control in _controls(source):
            effective_vertices, effective_control_edges = _control_effective(source, control)
            _, explicit_nodes = _control_intent(source, control)
            # Edge-backed controls are incident through their boundary edge.
            # Their shared endpoints can belong to both neighboring patches,
            # but must not make a boundary line appear incident everywhere.
            touches = (patch_edges & effective_control_edges)
            touches |= patch_vertices & (effective_vertices & explicit_nodes)
            if touches:
                incident.append(str(control.get("control_uuid")))
        patch["incident_control_uuids"] = sorted(incident)
    result = {
        "revision": int(source.get(NETWORK_REVISION_KEY, 0)),
        "patches": patches,
        "face_patch_ids": {faces[index]["face_id"]: patch_id for index, patch_id in face_patch.items()},
        "edge_patch_ids": {
            str(edge_id): sorted({face_patch[index] for index in incident})
            for edge_id, incident in face_by_edge.items()
        },
        "control_patch_ids": {
            str(control.get("control_uuid")): sorted({patch["patch_id"] for patch in patches
                                                        if str(control.get("control_uuid")) in patch["incident_control_uuids"]})
            for control in _controls(source)
        },
    }
    _PATCH_CACHE[source.as_pointer()] = (token, result)
    return result


def _patches_for_control(source: bpy.types.Object, control_uuid: str) -> list[dict]:
    """Return incident patches for Phase 4 scope capture and diagnostics."""
    partition = _patch_partition(source)
    ids = set(partition["control_patch_ids"].get(str(control_uuid), []))
    return [patch for patch in partition["patches"] if patch["patch_id"] in ids]


def _invalidate_patch_cache(source: bpy.types.Object | None = None) -> None:
    if source is None:
        _PATCH_CACHE.clear()
        _PATCH_OVERLAY_CACHE.clear()
    else:
        _PATCH_CACHE.pop(source.as_pointer(), None)
        _PATCH_OVERLAY_CACHE.pop(source.as_pointer(), None)


def _rebuild_proxy(source: bpy.types.Object, controller: bpy.types.Object) -> None:
    global _SYNC_GUARD
    previous_guard = _SYNC_GUARD
    _SYNC_GUARD = True
    try:
        _OVERLAY_CACHE.clear()
        _PATCH_OVERLAY_CACHE.pop(source.as_pointer(), None)
        _PICK_PREVIEW.clear()
        _rebuild_proxy_impl(source, controller)
        _PROXY_SNAPSHOTS.pop(controller.as_pointer(), None)
        _guard_proxy_topology(source, controller)
    finally:
        _SYNC_GUARD = previous_guard


def _rebuild_proxy_impl(source: bpy.types.Object, controller: bpy.types.Object) -> None:
    _validate_source_topology(source)
    vertex_ids, edge_ids = _effective_proxy_elements(source)
    vid_to_index, eid_to_index = _source_id_maps(source)
    proxy_mesh = controller.data
    old_pose = _proxy_state(controller)
    kept_positions = {item[0]: item[1] for item in old_pose[0]} if old_pose else {}
    selected_ids = _proxy_selection_snapshot(controller) if controller.mode == "EDIT" and old_pose else (set(), set())
    old_active = bpy.context.view_layer.objects.active
    old_mode = old_active.mode if old_active is not None else "OBJECT"
    old_selected = [obj for obj in bpy.context.selected_objects]
    if controller.mode == "EDIT":
        # Blender cannot rebuild a Mesh datablock while its edit BMesh owns it.
        # Temporarily leave only the controller edit context, then restore it.
        bpy.ops.object.mode_set(mode="OBJECT")
    proxy_mesh.clear_geometry()
    source_vertices = _source_vertices(source)
    edge_vids = _source_edge_vids(source)
    # Keep the pose of surviving handles. Newly revealed IDs sample Source;
    # hiding a different control must not reset the user's visible edits.
    proxy_vertices = [kept_positions.get(vid, tuple(source_vertices[vid_to_index[vid]].co)) for vid in vertex_ids]
    proxy_vertex_index = {vid: index for index, vid in enumerate(vertex_ids)}
    proxy_edges = []
    kept_edge_ids = []
    for edge_id in edge_ids:
        endpoint_ids = edge_vids[edge_id]
        if all(endpoint in proxy_vertex_index for endpoint in endpoint_ids):
            proxy_edges.append(tuple(proxy_vertex_index[endpoint] for endpoint in endpoint_ids))
            kept_edge_ids.append(edge_id)
    proxy_mesh.from_pydata(proxy_vertices, proxy_edges, [])
    proxy_mesh.update()
    for attr_name in (PROXY_VID_ATTR, PROXY_EID_ATTR):
        old_attr = proxy_mesh.attributes.get(attr_name)
        if old_attr is not None:
            proxy_mesh.attributes.remove(old_attr)
    proxy_vid_attr = proxy_mesh.attributes.new(name=PROXY_VID_ATTR, type="INT", domain="POINT")
    for index, vertex_id in enumerate(vertex_ids):
        proxy_vid_attr.data[index].value = vertex_id
    proxy_eid_attr = proxy_mesh.attributes.new(name=PROXY_EID_ATTR, type="INT", domain="EDGE")
    for index, edge_id in enumerate(kept_edge_ids):
        proxy_eid_attr.data[index].value = edge_id
    controller.parent = source
    controller.matrix_parent_inverse = Matrix.Identity(4)
    controller.matrix_basis = Matrix.Identity(4)
    controller.display_type = "WIRE"
    controller.color = (0.05, 0.75, 1.0, 1.0)
    controller.show_wire = True
    controller.show_all_edges = True
    controller.hide_render = True
    controller[PROXY_GENERATION_KEY] = int(controller.get(PROXY_GENERATION_KEY, 0)) + 1
    proxy_mesh.update()
    if old_active is not None and old_active != controller and old_active.name in bpy.data.objects:
        for obj in bpy.context.selected_objects:
            obj.select_set(False)
        for obj in old_selected:
            if obj.name in bpy.data.objects:
                obj.select_set(True)
        bpy.context.view_layer.objects.active = old_active
    if old_active == controller and old_mode == "EDIT" and controller.name in bpy.data.objects:
        bpy.context.view_layer.objects.active = controller
        controller.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        _select_proxy_ids(controller, *selected_ids)


def _sync_proxy(source: bpy.types.Object, controller: bpy.types.Object) -> None:
    if controller is None or controller.data is None:
        return
    proxy_attr = controller.data.attributes.get(PROXY_VID_ATTR)
    if proxy_attr is None:
        return
    source_vids, _ = _source_id_maps(source)
    source_vertices = _source_vertices(source)
    changed = False
    if controller.mode == "EDIT":
        bm = bmesh.from_edit_mesh(controller.data)
        layer = bm.verts.layers.int.get(PROXY_VID_ATTR)
        if layer is None:
            return
        for vert in bm.verts:
            source_index = source_vids.get(int(vert[layer]))
            if source_index is not None:
                position = source_vertices[source_index].co
                if (vert.co - position).length_squared > 1e-16:
                    vert.co = position
                    changed = True
        if changed:
            bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=False)
            _guard_proxy_topology(source, controller)
        return
    for index, item in enumerate(proxy_attr.data):
        source_index = source_vids.get(int(item.value))
        if source_index is not None and index < len(controller.data.vertices):
            position = source_vertices[source_index].co
            vert = controller.data.vertices[index]
            if (vert.co - position).length_squared > 1e-16:
                vert.co = position
                changed = True
    if changed:
        controller.data.update()
        _guard_proxy_topology(source, controller)


def _proxy_state(controller):
    """Read ID connectivity and current coordinates; indices are never identity."""
    owned = controller.mode != "EDIT"
    bm = bmesh.new() if owned else bmesh.from_edit_mesh(controller.data)
    try:
        if owned:
            bm.from_mesh(controller.data)
        vl = bm.verts.layers.int.get(PROXY_VID_ATTR)
        el = bm.edges.layers.int.get(PROXY_EID_ATTR)
        if vl is None or el is None or bm.faces:
            return None
        vertices = [(int(v[vl]), tuple(v.co), v.select, v.hide) for v in bm.verts]
        edges = [(int(e[el]), tuple(sorted(int(v[vl]) for v in e.verts)), e.select, e.hide) for e in bm.edges]
        return vertices, edges
    finally:
        if owned:
            bm.free()


def _guard_proxy_topology(source, controller) -> bool:
    """Reject native topology edits while preserving the last valid control pose.

    Only Source definitions/masks may rebuild proxy topology. Coordinate-only
    controller edits update a runtime recovery snapshot, never Source geometry.
    """
    key = controller.as_pointer()
    token = (controller.data.as_pointer(), controller.get(PROXY_GENERATION_KEY),
             source.get(CONTROLS_KEY), source.get(HIDDEN_VIDS_KEY), source.get(HIDDEN_EIDS_KEY))
    snapshot = _PROXY_SNAPSHOTS.get(key)
    if snapshot is None or snapshot[0] != token:
        _validate_source_topology(source)
        vids, eids = _effective_proxy_elements(source)
        vmap, emap = _source_id_maps(source)
        edge_vids = _source_edge_vids(source)
        source_vertices = _source_vertices(source)
        expected_edges = {eid: tuple(sorted(edge_vids[eid])) for eid in eids}
        vertices = [(vid, tuple(source_vertices[vmap[vid]].co), False, False) for vid in vids]
        edges = [(eid, expected_edges[eid], False, False) for eid in eids]
        snapshot = (token, set(vids), expected_edges, (vertices, edges))
    state = _proxy_state(controller)
    if state is not None:
        vertices, edges = state
        valid = (len(vertices) == len(snapshot[1]) and len(edges) == len(snapshot[2])
                 and {v[0] for v in vertices} == snapshot[1]
                 and {e[0]: e[1] for e in edges} == snapshot[2])
        if valid:
            _PROXY_SNAPSHOTS[key] = (*snapshot[:3], state)
            return False
    # A menu, tool or MCP call bypassed the shortcut guard. Restore in-place;
    # no mode switch or Source write is allowed inside the depsgraph callback.
    owned = controller.mode != "EDIT"
    bm = bmesh.new() if owned else bmesh.from_edit_mesh(controller.data)
    try:
        bm.clear()
        vl = bm.verts.layers.int.get(PROXY_VID_ATTR)
        if vl is None:
            vl = bm.verts.layers.int.new(PROXY_VID_ATTR)
        el = bm.edges.layers.int.get(PROXY_EID_ATTR)
        if el is None:
            el = bm.edges.layers.int.new(PROXY_EID_ATTR)
        verts = {}
        for vid, co, selected, hidden in snapshot[3][0]:
            vert = bm.verts.new(co)
            vert[vl], vert.select, vert.hide = vid, selected, hidden
            verts[vid] = vert
        for eid, endpoints, selected, hidden in snapshot[3][1]:
            edge = bm.edges.new(tuple(verts[vid] for vid in endpoints))
            edge[el], edge.select, edge.hide = eid, selected, hidden
        if owned:
            bm.to_mesh(controller.data)
            controller.data.update()
        else:
            bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=True)
    finally:
        if owned:
            bm.free()
    _PROXY_SNAPSHOTS[key] = snapshot
    bpy.context.scene.dan_form_status = "Controller chỉ chỉnh vị trí; tạo/xóa đường trên model"
    return True


def _update_revision(source: bpy.types.Object) -> None:
    source[NETWORK_REVISION_KEY] = int(source.get(NETWORK_REVISION_KEY, 0)) + 1


def _source_selection(source: bpy.types.Object) -> tuple[set[int], set[int]]:
    if source.mode != "EDIT" or bpy.context.view_layer.objects.active != source:
        raise ValueError("SOURCE_EDIT_MODE_REQUIRED")
    _validate_source_topology(source)
    bm = bmesh.from_edit_mesh(source.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    vid_layer = bm.verts.layers.int.get(VID_ATTR)
    eid_layer = bm.edges.layers.int.get(EID_ATTR)
    if vid_layer is None or eid_layer is None:
        raise ValueError("SOURCE_ID_LAYERS_MISSING")
    vertex_ids = {int(vert[vid_layer]) for vert in bm.verts if vert.select}
    edge_ids = {int(edge[eid_layer]) for edge in bm.edges if edge.select}
    for edge_id in edge_ids:
        edge = next(edge for edge in bm.edges if int(edge[eid_layer]) == edge_id)
        vertex_ids.update(int(vert[vid_layer]) for vert in edge.verts)
    if not vertex_ids and not edge_ids:
        raise ValueError("NO_SOURCE_SELECTION")
    return vertex_ids, edge_ids


def _proxy_selection(controller: bpy.types.Object) -> tuple[set[int], set[int]]:
    if controller.mode != "EDIT" or bpy.context.view_layer.objects.active != controller:
        raise ValueError("CONTROLLER_EDIT_MODE_REQUIRED")
    bm = bmesh.from_edit_mesh(controller.data)
    bm.verts.ensure_lookup_table()
    bm.edges.ensure_lookup_table()
    vid_layer = bm.verts.layers.int.get(PROXY_VID_ATTR)
    eid_layer = bm.edges.layers.int.get(PROXY_EID_ATTR)
    if vid_layer is None or eid_layer is None:
        raise ValueError("PROXY_MAPPING_MISSING")
    selected_vids = {int(vert[vid_layer]) for vert in bm.verts if vert.select}
    selected_eids = {int(edge[eid_layer]) for edge in bm.edges if edge.select}
    mode = tuple(bpy.context.tool_settings.mesh_select_mode)
    if mode[1]:
        selected_vids = set()
    if not selected_vids and not selected_eids:
        raise ValueError("NO_PROXY_SELECTION")
    return selected_vids, selected_eids


def _select_source_ids(source: bpy.types.Object, vertex_ids: set[int], edge_ids: set[int], add: bool = False) -> None:
    if source.mode != "EDIT":
        raise ValueError("SOURCE_EDIT_MODE_REQUIRED")
    bm = bmesh.from_edit_mesh(source.data)
    vid_layer = bm.verts.layers.int.get(VID_ATTR)
    eid_layer = bm.edges.layers.int.get(EID_ATTR)
    if vid_layer is None or eid_layer is None:
        raise ValueError("SOURCE_ID_LAYERS_MISSING")
    if not add:
        for vert in bm.verts:
            vert.select = False
        for edge in bm.edges:
            edge.select = False
    for vert in bm.verts:
        if int(vert[vid_layer]) in vertex_ids:
            vert.select = True
    for edge in bm.edges:
        if int(edge[eid_layer]) in edge_ids:
            edge.select = True
    bmesh.update_edit_mesh(source.data, loop_triangles=False, destructive=False)


def _select_proxy_ids(controller: bpy.types.Object, vertex_ids: set[int], edge_ids: set[int], add: bool = False) -> None:
    if controller.mode != "EDIT":
        raise ValueError("CONTROLLER_EDIT_MODE_REQUIRED")
    bm = bmesh.from_edit_mesh(controller.data)
    vid_layer = bm.verts.layers.int.get(PROXY_VID_ATTR)
    eid_layer = bm.edges.layers.int.get(PROXY_EID_ATTR)
    if vid_layer is None or eid_layer is None:
        raise ValueError("PROXY_MAPPING_MISSING")
    if not add:
        for vert in bm.verts:
            vert.select = False
        for edge in bm.edges:
            edge.select = False
    for vert in bm.verts:
        if int(vert[vid_layer]) in vertex_ids:
            vert.select = True
    for edge in bm.edges:
        if int(edge[eid_layer]) in edge_ids:
            edge.select = True
    bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=False)


def _mutate_masks(source: bpy.types.Object, vertex_ids: set[int], edge_ids: set[int], reveal: bool) -> bool:
    _validate_source_topology(source)
    hidden_vids = _hidden(source, HIDDEN_VIDS_KEY)
    hidden_eids = _hidden(source, HIDDEN_EIDS_KEY)
    before = (hidden_vids.copy(), hidden_eids.copy())
    if reveal and not vertex_ids and not edge_ids:
        hidden_vids.clear()
        hidden_eids.clear()
    elif reveal:
        hidden_vids.difference_update(vertex_ids)
        hidden_eids.difference_update(edge_ids)
        edge_vids = _source_edge_vids(source)
        for edge_id in edge_ids:
            hidden_vids.difference_update(edge_vids.get(edge_id, ()))
    else:
        hidden_vids.update(vertex_ids)
        hidden_eids.update(edge_ids)
    changed = before != (hidden_vids, hidden_eids)
    if changed:
        _json_set(source, HIDDEN_VIDS_KEY, sorted(hidden_vids))
        _json_set(source, HIDDEN_EIDS_KEY, sorted(hidden_eids))
        _update_revision(source)
    return changed


def _mutate_control_visibility(source: bpy.types.Object, control: dict, reveal: bool) -> bool:
    edge_ids, node_ids = _control_intent(source, control)
    if reveal:
        return _mutate_masks(source, node_ids, edge_ids, reveal=True)
    return _mutate_masks(source, node_ids, edge_ids, reveal=False)


def _prune_masks_after_remove(source: bpy.types.Object) -> None:
    defined_edges: set[int] = set()
    defined_nodes: set[int] = set()
    for control in _controls(source):
        edges, nodes = _control_intent(source, control)
        defined_edges.update(edges)
        defined_nodes.update(nodes)
    edge_vids = _source_edge_vids(source)
    for control in _controls(source):
        for edge_id in control.get("edge_ids", []):
            defined_nodes.update(edge_vids.get(int(edge_id), ()))
    hidden_vids = _hidden(source, HIDDEN_VIDS_KEY) & defined_nodes
    hidden_eids = _hidden(source, HIDDEN_EIDS_KEY) & defined_edges
    _json_set(source, HIDDEN_VIDS_KEY, sorted(hidden_vids))
    _json_set(source, HIDDEN_EIDS_KEY, sorted(hidden_eids))


def _sync_scene(scene: bpy.types.Scene) -> None:
    for source, controller in _source_controller_pairs():
        try:
            _sync_proxy(source, controller)
        except (KeyError, ValueError):
            pass


@persistent
def _depsgraph_update_post(scene: bpy.types.Scene, depsgraph: bpy.types.Depsgraph) -> None:
    global _SYNC_GUARD
    if _SYNC_GUARD:
        return
    _SYNC_GUARD = True
    try:
        changed_geometry = {update.id.original.as_pointer() for update in depsgraph.updates if update.is_updated_geometry}
        for source, controller in _source_controller_pairs():
            source_changed = source.as_pointer() in changed_geometry or source.data.as_pointer() in changed_geometry
            controller_changed = controller.as_pointer() in changed_geometry or controller.data.as_pointer() in changed_geometry
            if not source_changed and not controller_changed:
                continue
            _OVERLAY_CACHE.clear()
            _PATCH_OVERLAY_CACHE.pop(source.as_pointer(), None)
            try:
                if source_changed:
                    _MAPPING_CACHE.pop(source.as_pointer(), None)
                    _validate_source_topology(source)
                _guard_proxy_topology(source, controller)
                if source_changed:
                    _sync_proxy(source, controller)
            except (KeyError, ValueError):
                # A stale topology is reported by the next explicit command;
                # the depsgraph callback must never escape into Blender.
                pass
        active_source, _ = _context_source(bpy.context)
        _sync_ui_list(bpy.context.scene, active_source)
    except (AttributeError, RuntimeError, ValueError):
        pass
    finally:
        _SYNC_GUARD = False


@persistent
def _refresh_runtime(_unused=None) -> None:
    global _PICK_SESSION
    _PICK_SESSION += 1
    _PICK_PREVIEW.clear()
    _MAPPING_CACHE.clear()
    _UI_SIGNATURES.clear()
    _PROXY_SNAPSHOTS.clear()
    _NETWORK_CACHE.clear()
    _PATCH_CACHE.clear()
    _PATCH_OVERLAY_CACHE.clear()
    _OVERLAY_CACHE.clear()
    try:
        for source, controller in _source_controller_pairs():
            _guard_proxy_topology(source, controller)
        _sync_context_ui_list(bpy.context)
    except (AttributeError, RuntimeError, ValueError):
        pass


def _tag_viewport_redraw(context: bpy.types.Context) -> None:
    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


def _overlay_source(context: bpy.types.Context) -> bpy.types.Object | None:
    source, _ = _context_source(context)
    return source


def _overlay_mode(context: bpy.types.Context) -> str:
    """Return the coordinate source used by the viewport color overlay.

    The model view is Source-backed so users can see where controls live.  A
    controller in Object Mode is drawn from its own proxy mesh, which keeps
    the colored line exactly on the editable control geometry.  Controller Edit
    uses the live controller BMesh so enabled control edges remain readable;
    Blender's own native selection colors remain visible above that base layer.
    """
    source, controller = _context_source(context)
    active = context.view_layer.objects.active
    if source is None or controller is None or active is None:
        return "none"
    if active == controller:
        return "controller_edit" if controller.mode == "EDIT" else "controller"
    if active == source:
        return "source"
    return "none"


def _overlay_geometry(context, overlay_mode, source, controller):
    """Collect one frame of world-space positions from a single mesh read."""
    scene = context.scene
    selected_control = _control(source, scene.dan_form_selected_control)
    selected_vertices, selected_edges = _control_effective(source, selected_control) if selected_control else (set(), set())
    # Edge vertices are already legible through the colored lines and native
    # Edit selection. Only explicit point handles need an extra dot; painting
    # every endpoint makes dense contours (especially fingers) into solid blobs.
    point_ids = set()
    for control in _controls(source):
        point_ids.update(_control_intent(source, control)[1])
    selected_point_ids = _control_intent(source, selected_control)[1] if selected_control else set()
    if overlay_mode in {"controller", "controller_edit"}:
        mesh = controller.data
        vl = mesh.attributes.get(PROXY_VID_ATTR)
        el = mesh.attributes.get(PROXY_EID_ATTR)
        if vl is None or el is None:
            return {}
        if overlay_mode == "controller_edit":
            # Mesh datablock coordinates can lag behind an active Edit BMesh.
            # Borrow this BMesh for one synchronous read and never retain it.
            bm = bmesh.from_edit_mesh(controller.data)
            bm.verts.ensure_lookup_table()
            bm.edges.ensure_lookup_table()
            proxy_vl = bm.verts.layers.int.get(PROXY_VID_ATTR)
            proxy_el = bm.edges.layers.int.get(PROXY_EID_ATTR)
            if proxy_vl is None or proxy_el is None:
                return {}
            matrix = controller.matrix_world
            positions = {int(vertex[proxy_vl]): matrix @ vertex.co for vertex in bm.verts}
            edges = {int(edge[proxy_el]): tuple(int(vertex[proxy_vl]) for vertex in edge.verts) for edge in bm.edges if not edge.hide}
            # Let Blender's native Edit selection color sit above the cyan
            # enabled-control layer. Selected elements are omitted from the
            # custom batch instead of being painted cyan a second time.
            native_selected_edges = {int(edge[proxy_el]) for edge in bm.edges if edge.select}
            native_selected_vertices = {int(vertex[proxy_vl]) for vertex in bm.verts if vertex.select}
        else:
            matrix = controller.matrix_world
            positions = {int(item.value): matrix @ vert.co for item, vert in zip(vl.data, mesh.vertices)}
            index_vids = [int(item.value) for item in vl.data]
            edges = {int(item.value): tuple(index_vids[i] for i in edge.vertices) for item, edge in zip(el.data, mesh.edges)}
            native_selected_edges = set()
            native_selected_vertices = set()
        vertex_ids, edge_ids = list(positions), list(edges)
    else:
        vid_indices, _ = _source_id_maps(source)
        edges = _source_edge_vids(source)
        vertex_ids, edge_ids = _effective_proxy_elements(source)
        if scene.dan_form_overlay_hidden:
            controls = _controls(source)
            edge_ids = sorted({int(eid) for control in controls for eid in control.get("edge_ids", []) if int(eid) in edges})
            vertex_ids = sorted({int(vid) for control in controls for vid in control.get("vertex_ids", []) if int(vid) in vid_indices}
                                | {vid for eid in edge_ids for vid in edges[eid]})
        vertices = _source_vertices(source)
        matrix = source.matrix_world
        positions = {vid: matrix @ vertices[vid_indices[vid]].co for vid in vertex_ids if vid in vid_indices}
    # In Controller Edit, native Blender selection must remain the top visual
    # authority.  Do not draw an orange duplicate over its selected wires.
    selected_edges_for_overlay = set() if overlay_mode == "controller_edit" else selected_edges
    selected_points_for_overlay = set() if overlay_mode == "controller_edit" else selected_point_ids & selected_vertices
    enabled_edges_for_overlay = (
        [edge_id for edge_id in edge_ids if edge_id not in native_selected_edges]
        if overlay_mode == "controller_edit" else edge_ids
    )
    point_ids_for_overlay = (
        point_ids - native_selected_vertices
        if overlay_mode == "controller_edit" else point_ids
    )
    return {
        "edges": [positions[vid] for eid in enabled_edges_for_overlay for vid in edges[eid] if vid in positions],
        "selected_edges": [positions[vid] for eid in selected_edges_for_overlay if eid in edges for vid in edges[eid] if vid in positions],
        "points": [positions[vid] for vid in point_ids_for_overlay if vid in positions and overlay_mode != "controller_edit"],
        "selected_points": [positions[vid] for vid in selected_points_for_overlay if vid in positions],
    }


_PATCH_COLORS = (
    (0.18, 0.55, 0.95, 0.18),
    (0.95, 0.38, 0.28, 0.18),
    (0.25, 0.78, 0.42, 0.18),
    (0.85, 0.45, 0.92, 0.18),
    (0.95, 0.70, 0.20, 0.18),
    (0.20, 0.78, 0.82, 0.18),
)


def _patch_overlay_batches(context, source):
    """Build translucent triangles for the Source patch display only."""
    import gpu
    from gpu_extras.batch import batch_for_shader

    if not getattr(context.scene, "dan_form_patches_enabled", False):
        return None, []
    mapping = _source_id_maps(source)
    partition = _patch_partition(source)
    token = (mapping, source.matrix_world.copy(), tuple(
        (patch["patch_id"], tuple(patch["face_indices"])) for patch in partition["patches"]
    ))
    cached = _PATCH_OVERLAY_CACHE.get(source.as_pointer())
    if cached is not None and cached[0] == token:
        return cached[1], cached[2]
    faces = _source_face_records(source)
    vertices_by_id, _ = _source_id_maps(source)
    source_vertices = _source_vertices(source)
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    batches = []
    for patch_index, patch in enumerate(partition["patches"]):
        positions = []
        for face_index in patch["face_indices"]:
            face_vertices = faces[face_index]["vertex_ids"]
            if len(face_vertices) < 3:
                continue
            origin = source_vertices[vertices_by_id[face_vertices[0]]].co
            for index in range(1, len(face_vertices) - 1):
                for vertex_id in (face_vertices[0], face_vertices[index], face_vertices[index + 1]):
                    positions.append(source.matrix_world @ source_vertices[vertices_by_id[vertex_id]].co)
        if positions:
            batches.append((patch["patch_id"], batch_for_shader(shader, "TRIS", {"pos": positions}),
                            _PATCH_COLORS[patch_index % len(_PATCH_COLORS)]))
    _PATCH_OVERLAY_CACHE[source.as_pointer()] = (token, shader, batches)
    return shader, batches


def _overlay_batches(context, overlay_mode, source, controller):
    """Retain GPU buffers on idle redraw; handlers invalidate changed geometry."""
    import gpu
    from gpu_extras.batch import batch_for_shader

    scene = context.scene
    # Selection-only changes do not reliably emit a geometry depsgraph update.
    # Keep omitted native-selected elements synchronized after Box Select,
    # clicking empty space and Reveal, without rereading coordinates on idle.
    selection_token = None
    if overlay_mode == "controller_edit":
        bm = bmesh.from_edit_mesh(controller.data)
        selection_token = (tuple(v.select for v in bm.verts),
                           tuple((e.select, e.hide) for e in bm.edges))
    token = (context.window.as_pointer() if context.window else 0,
             source.as_pointer(), source.data.as_pointer(), source.mode,
             controller.as_pointer(), controller.data.as_pointer(), controller.mode,
             controller.get(PROXY_GENERATION_KEY), overlay_mode,
             source.get(CONTROLS_KEY), source.get(HIDDEN_VIDS_KEY), source.get(HIDDEN_EIDS_KEY),
             scene.dan_form_selected_control, scene.dan_form_overlay_hidden, selection_token,
             tuple(tuple(row) for row in source.matrix_world),
             tuple(tuple(row) for row in controller.matrix_world))
    if _OVERLAY_CACHE.get("token") != token:
        geometry = _overlay_geometry(context, overlay_mode, source, controller)
        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        batches = {name: batch_for_shader(shader, "LINES" if "edges" in name else "POINTS", {"pos": positions})
                   for name, positions in geometry.items() if positions}
        _OVERLAY_CACHE.update(token=token, shader=shader, batches=batches)
    return _OVERLAY_CACHE["shader"], _OVERLAY_CACHE["batches"]


def _update_overlay_display(scene: bpy.types.Scene, _context: bpy.types.Context | None = None) -> None:
    """Apply the user-facing X-Ray switch to both overlay depth and proxy wire display."""
    for controller in scene.objects:
        if controller.type != "MESH" or not controller.get(PROXY_GENERATION_KEY):
            continue
        key = controller.as_pointer()
        if scene.dan_form_overlay_xray:
            if key not in _XRAY_SHOW_IN_FRONT:
                _XRAY_SHOW_IN_FRONT[key] = bool(controller.show_in_front)
            controller.show_in_front = True
        elif key in _XRAY_SHOW_IN_FRONT:
            controller.show_in_front = _XRAY_SHOW_IN_FRONT.pop(key)
    if bpy.context.window_manager is not None:
        _tag_viewport_redraw(bpy.context)


def _draw_control_overlay() -> None:
    """Draw cached Source/Object or live Controller Edit control buffers."""
    try:
        import gpu

        context = bpy.context
        scene = context.scene
        overlay_enabled = getattr(scene, "dan_form_overlay_enabled", True)
        overlay_mode = _overlay_mode(context)
        if overlay_mode == "none":
            return
        source, controller = _context_source(context)
        if source is None or controller is None or not source.get(SOURCE_UUID_KEY):
            return
        if overlay_mode == "source" and source.get(VIEWPORT_HIDDEN_KEY, False):
            return
        shader, batches = _overlay_batches(context, overlay_mode, source, controller)
        if not overlay_enabled:
            batches = {}
        shading = context.space_data.shading
        xray = scene.dan_form_overlay_xray or shading.show_xray or shading.type == "WIREFRAME"
        # POST_VIEW runs after the regular viewport draw.  Set the depth state
        # explicitly so the normal overlay follows the opaque mesh surface;
        # without this, lines can appear in front even when X-Ray is disabled.
        previous_depth = gpu.state.depth_test_get()
        previous_width = gpu.state.line_width_get()
        previous_blend = gpu.state.blend_get() if hasattr(gpu.state, "blend_get") else "NONE"
        gpu.state.depth_test_set("NONE" if xray else "LESS_EQUAL")
        try:
            if overlay_mode == "source" and scene.dan_form_patches_enabled:
                patch_shader, patch_batches = _patch_overlay_batches(context, source)
                if patch_shader is not None:
                    gpu.state.blend_set("ALPHA")
                    for _patch_id, patch_batch, patch_color in patch_batches:
                        patch_shader.bind()
                        patch_shader.uniform_float("color", patch_color)
                        patch_batch.draw(patch_shader)
            width = min(scene.dan_form_overlay_width, 1.5) if overlay_mode == "controller_edit" else scene.dan_form_overlay_width
            for name, color, size in (
                ("edges", (0.05, 0.75, 1.0, 0.95), width),
                ("selected_edges", (1.0, 0.45, 0.05, 1.0), width + 1.0),
                ("points", (0.2, 1.0, 0.7, 1.0), 6.0),
                ("selected_points", (1.0, 0.45, 0.05, 1.0), 8.0),
            ):
                batch = batches.get(name)
                if batch is None:
                    continue
                shader.bind()
                shader.uniform_float("color", color)
                if "edges" in name:
                    gpu.state.line_width_set(float(size))
                else:
                    gpu.state.point_size_set(float(size))
                batch.draw(shader)
            preview = _PICK_PREVIEW
            if (preview.get("controller") == controller.as_pointer()
                    and preview.get("area") == context.area.as_pointer()
                    and preview.get("batch") is not None):
                shader.bind()
                shader.uniform_float("color", (1.0, 0.2, 0.8, 1.0))
                gpu.state.line_width_set(3.0)
                preview["batch"].draw(shader)
        finally:
            # Do not leak custom line/depth state into another draw callback.
            gpu.state.depth_test_set(previous_depth)
            gpu.state.line_width_set(previous_width)
            gpu.state.point_size_set(1.0)
            gpu.state.blend_set(previous_blend)
    except Exception:
        # Drawing must never break Blender's viewport; retry on next redraw.
        return


def _register_overlay() -> None:
    global OVERLAY_HANDLE
    if OVERLAY_HANDLE is None:
        OVERLAY_HANDLE = bpy.types.SpaceView3D.draw_handler_add(
            _draw_control_overlay, (), "WINDOW", "POST_VIEW"
        )


def _unregister_overlay() -> None:
    global OVERLAY_HANDLE
    if OVERLAY_HANDLE is not None:
        bpy.types.SpaceView3D.draw_handler_remove(OVERLAY_HANDLE, "WINDOW")
        OVERLAY_HANDLE = None


class DANFORM_OT_initialize(bpy.types.Operator):
    bl_idname = "dan_form.initialize"
    bl_label = "Initialize DANP Form"
    bl_description = "Bind the selected mesh as a DANP Form Source and create its controller"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        active = context.view_layer.objects.active
        return _is_valid_source(active) and active.get(CONTROLLER_KEY) is None and active.mode in {"OBJECT", "EDIT"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        scene = context.scene
        source = context.view_layer.objects.active
        try:
            if not _is_valid_source(source):
                raise ValueError("SOURCE_NOT_EDITABLE")
            controller = _find_controller(source)
            if controller is None:
                _source_uuid(source)
                _ensure_source_ids(source)
                mesh = bpy.data.meshes.new(f"DANPFORM_CTRL_{source.name}")
                mesh.from_pydata([], [], [])
                mesh.update()
                controller = bpy.data.objects.new(f"DANPFORM_CTRL_{source.name}", mesh)
                _controller_collection(source, scene).objects.link(controller)
                controller[CONTROLLER_KEY] = source[ SOURCE_UUID_KEY ]
                controller[SCHEMA_KEY] = SCHEMA_VERSION
                controller["dan_form_source_name"] = source.name
                controller.display_type = "WIRE"
                controller.hide_render = True
                _rebuild_proxy(source, controller)
            else:
                _validate_source_topology(source)
                _guard_proxy_topology(source, controller)
            source["dan_form_controller_name"] = controller.name
            _set_scene_context(context, source, controller)
            scene.dan_form_status = f"Ready: {source.name} / {controller.name}"
            self.report({"INFO"}, "DANP Form controller ready")
            return {"FINISHED"}
        except ValueError as exc:
            scene.dan_form_status = f"Error: {exc}"
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class DANFORM_OT_sync(bpy.types.Operator):
    bl_idname = "dan_form.sync_proxy"
    bl_label = "Sync Proxy"
    bl_description = "Refresh controller coordinates from the Source mesh"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        try:
            if not _is_valid_source(source) or controller is None:
                raise ValueError("SOURCE_OR_CONTROLLER_MISSING")
            _ensure_source_ids(source)
            _sync_proxy(source, controller)
            _set_scene_context(context, source, controller)
            context.scene.dan_form_status = f"Synced: {controller.name}"
            return {"FINISHED"}
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


def _ui_item_name_update(item, context: bpy.types.Context) -> None:
    global _UI_SYNC_GUARD
    if _UI_SYNC_GUARD:
        return
    source = _find_source_by_uuid(item.source_uuid)
    controls = _controls(source) if source is not None else []
    control = next((entry for entry in controls if entry.get("control_uuid") == item.control_uuid), None)
    if source is None or control is None:
        return
    new_name = item.control_name.strip()
    if not new_name:
        _UI_SYNC_GUARD = True
        try:
            item.control_name = str(control.get("name", "Control"))
        finally:
            _UI_SYNC_GUARD = False
        return
    if new_name != control.get("name"):
        control["name"] = new_name
        _json_set(source, CONTROLS_KEY, controls)
        if context is not None and getattr(context, "scene", None) is not None:
            context.scene.dan_form_selected_control = item.control_uuid
            context.scene.dan_form_status = f"Renamed: {new_name}"


def _ui_control_index_update(scene, context: bpy.types.Context) -> None:
    if _UI_SYNC_GUARD or context is None:
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
    scene.dan_form_selected_control = control["control_uuid"]
    _ACTIVE_CONTROL_UUIDS[items[index].source_uuid] = control["control_uuid"]
    active = context.view_layer.objects.active
    try:
        if active == source and source.mode == "EDIT":
            _select_source_ids(source, set(control.get("vertex_ids", [])), set(control.get("edge_ids", [])))
        elif active == controller and controller.mode == "EDIT":
            vertex_ids, edge_ids = _control_effective(source, control)
            _select_proxy_ids(controller, vertex_ids, edge_ids)
    except (ValueError, RuntimeError):
        pass
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
        toggle.reveal = item.state in {"Hidden", "Partial"}
        row.prop(item, "control_name", text="", emboss=False)
        if item.state == "Partial":
            row.label(text="~")


class DANFORM_OT_sync_control(bpy.types.Operator):
    bl_idname = "dan_form.sync_control"
    bl_label = "Sync Control Membership"
    bl_description = "Replace the active control membership from the current edit selection"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        source, _ = _context_source(context)
        active = context.view_layer.objects.active
        return source is not None and active == source and source.mode == "EDIT" and _active_control(context, source) is not None

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        controls = _controls(source) if source is not None else []
        active_control = _active_control(context, source) if source is not None else None
        control = next((item for item in controls if active_control is not None and item.get("control_uuid") == active_control.get("control_uuid")), None)
        active = context.view_layer.objects.active
        if source is None or control is None or active != source or source.mode != "EDIT":
            self.report({"ERROR"}, "SOURCE_EDIT_MODE_REQUIRED")
            return {"CANCELLED"}
        try:
            vertex_ids, edge_ids = _source_selection(source)
            if not vertex_ids and not edge_ids:
                self.report({"ERROR"}, "EMPTY_SELECTION")
                return {"CANCELLED"}
            old_membership = (
                sorted(int(value) for value in control.get("vertex_ids", [])),
                sorted(int(value) for value in control.get("edge_ids", [])),
            )
            new_membership = (sorted(vertex_ids), sorted(edge_ids))
            if old_membership == new_membership:
                context.scene.dan_form_status = "Control membership unchanged"
                return {"FINISHED"}
            control["vertex_ids"] = new_membership[0]
            control["edge_ids"] = new_membership[1]
            _json_set(source, CONTROLS_KEY, controls)
            _prune_masks_after_remove(source)
            _update_revision(source)
            if controller is not None:
                _rebuild_proxy(source, controller)
                _sync_proxy(source, controller)
            _set_scene_context(context, source, controller)
            context.scene.dan_form_status = f"Synced {control.get('name', 'Control')}"
            _sync_context_ui_list(context)
            return {"FINISHED"}
        except (ValueError, RuntimeError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class DANFORM_OT_move_control(bpy.types.Operator):
    bl_idname = "dan_form.move_control"
    bl_label = "Move Control"
    bl_description = "Reorder the active control definition"
    bl_options = {"REGISTER", "UNDO"}
    direction: IntProperty(default=1, options={"HIDDEN"})

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        if source is None:
            return {"CANCELLED"}
        controls = _controls(source)
        active_control = _active_control(context, source)
        if active_control is None:
            return {"CANCELLED"}
        index = next((i for i, item in enumerate(controls) if item.get("control_uuid") == active_control.get("control_uuid")), -1)
        target = index + (1 if self.direction > 0 else -1)
        if index < 0 or target < 0 or target >= len(controls):
            return {"CANCELLED"}
        controls[index], controls[target] = controls[target], controls[index]
        _json_set(source, CONTROLS_KEY, controls)
        _set_scene_context(context, source, controller)
        context.scene.dan_form_selected_control = active_control.get("control_uuid", "")
        _sync_context_ui_list(context)
        context.scene.dan_form_status = "Control order updated"
        return {"FINISHED"}


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
        layout.operator("dan_form.select_control_at_cursor", text="Select Whole Control Under Cursor", icon="OUTLINER_OB_MESH")
        layout.operator("dan_form.select_segment", text="Select Segment Between Junctions", icon="EDGESEL")
        layout.operator("dan_form.pick_selection_tool", text="Hover Pick Segment", icon="EYEDROPPER")
        layout.operator("dan_form.pick_selection_tool", text="Hover Pick Control", icon="EYEDROPPER").tool = "CONTROL"
        layout.separator()
        layout.prop(context.scene, "dan_form_overlay_enabled", text="Control Overlay")
        if context.view_layer.objects.active == source:
            layout.prop(context.scene, "dan_form_patches_enabled", text="Show Patches")
        layout.prop(context.scene, "dan_form_overlay_xray", text="X-Ray")
        if context.view_layer.objects.active == source:
            layout.prop(context.scene, "dan_form_overlay_hidden", text="Preview Hidden Controls")


class DANFORM_OT_create_control(bpy.types.Operator):
    bl_idname = "dan_form.create_control"
    bl_label = "Make Control from Source Selection"
    bl_description = "Create a Source-backed control from selected Source vertices and edges"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        source, _ = _context_source(context)
        active = context.view_layer.objects.active
        return source is not None and active == source and source.mode == "EDIT" and bool(source.get(SOURCE_UUID_KEY))

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        scene = context.scene
        try:
            active = context.view_layer.objects.active
            if active == source:
                vertex_ids, edge_ids = _source_selection(source)
            else:
                raise ValueError("SOURCE_EDIT_MODE_REQUIRED")
            if not vertex_ids and not edge_ids:
                raise ValueError("EMPTY_SELECTION")
            controls = _controls(source)
            controls.append({
                "control_uuid": uuid.uuid4().hex,
                "name": f"Control {len(controls) + 1}",
                "vertex_ids": sorted(vertex_ids),
                "edge_ids": sorted(edge_ids),
            })
            _json_set(source, CONTROLS_KEY, controls)
            _update_revision(source)
            controller = controller or _find_controller(source)
            if controller is None:
                raise ValueError("CONTROLLER_MISSING")
            _rebuild_proxy(source, controller)
            _sync_proxy(source, controller)
            _set_scene_context(context, source, controller)
            scene.dan_form_selected_control = controls[-1]["control_uuid"]
            scene.dan_form_status = f"Created {controls[-1]['name']} ({len(vertex_ids)}V/{len(edge_ids)}E)"
            _sync_context_ui_list(context)
            self.report({"INFO"}, scene.dan_form_status)
            return {"FINISHED"}
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class DANFORM_OT_rename_control(bpy.types.Operator):
    bl_idname = "dan_form.rename_control"
    bl_label = "Rename Control"
    bl_description = "Rename a control definition without changing its geometry"
    bl_options = {"REGISTER", "UNDO"}
    control_uuid: StringProperty(default="")
    new_name: StringProperty(name="Name", default="")

    def invoke(self, context, event):
        source, _ = _context_source(context)
        control = _control(source, self.control_uuid)
        self.new_name = control.get("name", "") if control else ""
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        controls = _controls(source)
        control = next((item for item in controls if item.get("control_uuid") == self.control_uuid), None)
        if source is None or control is None or not self.new_name.strip():
            return {"CANCELLED"}
        control["name"] = self.new_name.strip()
        _json_set(source, CONTROLS_KEY, controls)
        _set_scene_context(context, source, controller)
        context.scene.dan_form_selected_control = self.control_uuid
        context.scene.dan_form_status = f"Renamed: {control['name']}"
        _sync_context_ui_list(context)
        return {"FINISHED"}


class DANFORM_OT_select_control(bpy.types.Operator):
    bl_idname = "dan_form.select_control"
    bl_label = "Select Control"
    bl_description = "Select this definition in the current Source or controller edit context"
    bl_options = {"REGISTER", "UNDO"}
    control_uuid: StringProperty(default="")
    add_to_selection: BoolProperty(name="Add to Selection", default=False)

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        if not self.control_uuid and source is not None:
            active_control = _active_control(context, source)
            self.control_uuid = active_control.get("control_uuid", "") if active_control else ""
        control = _control(source, self.control_uuid)
        if source is None or control is None:
            return {"CANCELLED"}
        active = context.view_layer.objects.active
        try:
            vertex_ids = {int(value) for value in control.get("vertex_ids", [])}
            edge_ids = {int(value) for value in control.get("edge_ids", [])}
            context.scene.dan_form_selected_control = self.control_uuid
            if active == source and source.mode == "EDIT":
                _select_source_ids(source, vertex_ids, edge_ids, self.add_to_selection)
            elif active == controller and controller.mode == "EDIT":
                effective_vertices, effective_edges = _control_effective(source, control)
                _select_proxy_ids(controller, effective_vertices, effective_edges, self.add_to_selection)
            elif active == source and source.mode == "OBJECT":
                _select_only(context, source)
                bpy.ops.object.mode_set(mode="EDIT")
                _select_source_ids(source, vertex_ids, edge_ids, self.add_to_selection)
            else:
                raise ValueError("EDIT_SOURCE_OR_CONTROLLER_REQUIRED")
            context.scene.dan_form_status = f"Selected {control.get('name', 'Control')}"
            return {"FINISHED"}
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class DANFORM_OT_set_control_visibility(bpy.types.Operator):
    bl_idname = "dan_form.set_control_visibility"
    bl_label = "Hide/Reveal Control"
    bl_description = "Hide or reveal one definition using canonical Source masks"
    bl_options = {"REGISTER", "UNDO"}
    control_uuid: StringProperty(default="")
    reveal: BoolProperty(default=False)

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        control = _control(source, self.control_uuid)
        if source is None or control is None:
            return {"CANCELLED"}
        active = context.view_layer.objects.active
        was_controller_edit = active == controller and controller.mode == "EDIT"
        try:
            changed = _mutate_control_visibility(source, control, self.reveal)
            if changed:
                _rebuild_proxy(source, controller)
            _set_scene_context(context, source, controller)
            context.scene.dan_form_selected_control = self.control_uuid
            context.scene.dan_form_status = ("Revealed " if self.reveal else "Hidden ") + control.get("name", "Control")
            if was_controller_edit and controller.name in bpy.data.objects:
                effective_vertices, effective_edges = _control_effective(source, control)
                _select_proxy_ids(controller, effective_vertices, effective_edges)
            _sync_context_ui_list(context)
            return {"FINISHED"}
        except (ValueError, RuntimeError) as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class DANFORM_OT_delete_control(bpy.types.Operator):
    bl_idname = "dan_form.delete_control"
    bl_label = "Delete Control"
    bl_description = "Remove only this definition and preserve shared Source geometry"
    bl_options = {"REGISTER", "UNDO"}
    control_uuid: StringProperty(default="")

    @classmethod
    def poll(cls, context):
        source, _ = _context_source(context)
        return source is not None and context.view_layer.objects.active == source and source.mode in {"OBJECT", "EDIT"} and bool(_controls(source))

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        if source is None:
            return {"CANCELLED"}
        if not self.control_uuid:
            active_control = _active_control(context, source)
            self.control_uuid = active_control.get("control_uuid", "") if active_control else ""
        controls = _controls(source)
        deleted_index = next((i for i, item in enumerate(controls) if item.get("control_uuid") == self.control_uuid), -1)
        remaining = [item for item in controls if item.get("control_uuid") != self.control_uuid]
        if deleted_index < 0:
            return {"CANCELLED"}
        _json_set(source, CONTROLS_KEY, remaining)
        _prune_masks_after_remove(source)
        _update_revision(source)
        if controller is not None:
            _rebuild_proxy(source, controller)
        _set_scene_context(context, source, controller)
        context.scene.dan_form_selected_control = ""
        context.scene.dan_form_status = "Control deleted"
        _sync_context_ui_list(context)
        if context.scene.dan_form_control_items:
            context.scene.dan_form_control_index = min(
                deleted_index, len(context.scene.dan_form_control_items) - 1
            )
        return {"FINISHED"}


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
            vertex_ids, edge_ids = _proxy_selection(controller)
            if context.tool_settings.mesh_select_mode[1]:
                # Edge endpoints are incidental selection, not explicit node Hide.
                endpoints = {vid for eid in edge_ids for vid in _source_edge_vids(source).get(eid, ())}
                vertex_ids.difference_update(endpoints)
            else:
                edge_ids.clear()
            changed = _mutate_masks(source, vertex_ids, edge_ids, reveal=False)
            if changed:
                _rebuild_proxy(source, controller)
                context.scene.dan_form_status = f"Hidden {len(vertex_ids)}V/{len(edge_ids)}E"
            else:
                context.scene.dan_form_status = "No visibility change"
            _set_scene_context(context, source, controller)
            if controller.mode == "EDIT":
                _select_proxy_ids(controller, vertex_ids - _hidden(source, HIDDEN_VIDS_KEY), edge_ids - _hidden(source, HIDDEN_EIDS_KEY))
            return {"FINISHED"}
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
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
            payload = json.loads(self.ids_json) if self.ids_json else {}
            vertex_ids = {int(item) for item in payload.get("vertex_ids", [])}
            edge_ids = {int(item) for item in payload.get("edge_ids", [])}
            changed = _mutate_masks(source, vertex_ids, edge_ids, reveal=True)
            if changed:
                _rebuild_proxy(source, controller)
            context.scene.dan_form_status = "Revealed all" if not vertex_ids and not edge_ids else "Revealed selection"
            _set_scene_context(context, source, controller)
            return {"FINISHED"}
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.report({"ERROR"}, f"INVALID_REVEAL_IDS: {exc}")
            return {"CANCELLED"}


class DANFORM_OT_remove_controller(bpy.types.Operator):
    bl_idname = "dan_form.remove_controller"
    bl_label = "Remove Controller"
    bl_description = "Remove only the DANP Form controller object; keep Source definitions"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        source, controller = _context_source(context)
        return source is not None and controller is not None

    def execute(self, context: bpy.types.Context) -> set[str]:
        scene = context.scene
        source, controller = _context_source(context)
        if controller is None or controller.name not in bpy.data.objects:
            scene.dan_form_controller = None
            scene.dan_form_status = "No controller"
            return {"CANCELLED"}
        if controller.mode == "EDIT":
            bpy.ops.object.mode_set(mode="OBJECT")
            _select_only(context, source)
        mesh = controller.data
        _PROXY_SNAPSHOTS.pop(controller.as_pointer(), None)
        bpy.data.objects.remove(controller, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        _set_scene_context(context, source, None)
        scene.dan_form_status = f"Source ready: {source.name}" if source else "No controller"
        self.report({"INFO"}, "Controller removed; Source definitions preserved")
        return {"FINISHED"}


class DANFORM_OT_remove(bpy.types.Operator):
    bl_idname = "dan_form.remove"
    bl_label = "Remove DANP Form"
    bl_description = "Gỡ controller và toàn bộ thiết lập DANP Form; giữ nguyên hình học model"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        source, _ = _context_source(context)
        return source is not None and context.view_layer.objects.active == source and source.mode in {"OBJECT", "EDIT"} and bool(source.get(SOURCE_UUID_KEY)) and _is_valid_source(source)

    def execute(self, context):
        source, controller = _context_source(context)
        if not self.poll(context):
            return {"CANCELLED"}
        was_edit = source.mode == "EDIT"
        source_uuid = source.get(SOURCE_UUID_KEY)
        if was_edit:
            bpy.ops.object.mode_set(mode="OBJECT")
        try:
            if controller is not None:
                mesh = controller.data
                _PROXY_SNAPSHOTS.pop(controller.as_pointer(), None)
                bpy.data.objects.remove(controller, do_unlink=True)
                if mesh.users == 0:
                    bpy.data.meshes.remove(mesh)
            for name in (VID_ATTR, EID_ATTR):
                attr = source.data.attributes.get(name)
                if attr is not None:
                    source.data.attributes.remove(attr)
            for key in (SOURCE_UUID_KEY, SCHEMA_KEY, CONTROLS_KEY, HIDDEN_VIDS_KEY,
                        HIDDEN_EIDS_KEY, NEXT_VID_KEY, NEXT_EID_KEY, TOPOLOGY_KEY,
                        NETWORK_REVISION_KEY, VIEWPORT_HIDDEN_KEY, "dan_form_controller_name"):
                if key in source:
                    del source[key]
            _MAPPING_CACHE.pop(source.as_pointer(), None)
            _NETWORK_CACHE.pop(source.as_pointer(), None)
            _invalidate_patch_cache(source)
            _OVERLAY_CACHE.clear()
            _ACTIVE_CONTROL_UUIDS.pop(source_uuid, None)
            _RETURN_MODES.pop(source_uuid, None)
            for scene in bpy.data.scenes:
                if scene.dan_form_source == source:
                    scene.dan_form_source = None
                    scene.dan_form_controller = None
                if scene.dan_form_ui_source_uuid == source_uuid:
                    _UI_SIGNATURES.pop(scene.as_pointer(), None)
                    _sync_ui_list(scene, None)
            _sync_context_ui_list(context)
            context.scene.dan_form_status = "Đã gỡ DANP Form"
            _tag_viewport_redraw(context)
            self.report({"INFO"}, "Đã gỡ DANP Form; model giữ nguyên")
            return {"FINISHED"}
        finally:
            if was_edit:
                bpy.ops.object.mode_set(mode="EDIT")


class DANFORM_OT_topology_locked(bpy.types.Operator):
    bl_idname = "dan_form.topology_locked"
    bl_label = "Controller Topology Locked"
    bl_description = "Controller chỉ chỉnh vị trí; tạo/xóa đường control trên model"
    bl_options = {"INTERNAL"}

    @classmethod
    def poll(cls, context):
        source, controller = _context_source(context)
        return source is not None and controller is not None and context.view_layer.objects.active == controller and controller.mode == "EDIT"

    def execute(self, context):
        self.report({"INFO"}, self.bl_description)
        return {"FINISHED"}


def _register_topology_keymaps():
    config = bpy.context.window_manager.keyconfigs.addon
    if config is None:
        return
    km = config.keymaps.new(name="Mesh", space_type="EMPTY")
    shortcuts = [
        ("X", {}), ("DEL", {}), ("E", {}), ("F", {}), ("K", {}),
        ("J", {}), ("M", {}), ("V", {}), ("I", {}), ("P", {}),
        ("D", {"shift": True}), ("R", {"ctrl": True}),
        ("B", {"ctrl": True}), ("B", {"ctrl": True, "shift": True}),
        ("V", {"alt": True}), ("M", {"alt": True}),
    ]
    for key, modifiers in shortcuts:
        item = km.keymap_items.new("dan_form.topology_locked", key, "PRESS", head=True, **modifiers)
        _TOPOLOGY_KEYMAPS.append((km, item))


def _unregister_topology_keymaps():
    for km, item in _TOPOLOGY_KEYMAPS:
        km.keymap_items.remove(item)
    _TOPOLOGY_KEYMAPS.clear()


def _proxy_segment(controller, seed_id):
    """Return a visible maximal edge span; logical definitions never split it."""
    bm = bmesh.from_edit_mesh(controller.data)
    el = bm.edges.layers.int.get(PROXY_EID_ATTR)
    vl = bm.verts.layers.int.get(PROXY_VID_ATTR)
    if el is None or vl is None:
        raise ValueError("PROXY_MAPPING_MISSING")
    seed = next((e for e in bm.edges if int(e[el]) == seed_id and not e.hide), None)
    if seed is None:
        raise ValueError("VISIBLE_CONTROL_EDGE_REQUIRED")
    edges = {seed}
    for start in seed.verts:
        vert, previous = start, seed
        while len([e for e in vert.link_edges if not e.hide]) == 2:
            following = next(e for e in vert.link_edges if e != previous and not e.hide)
            if following in edges:
                break
            edges.add(following)
            vert, previous = following.other_vert(vert), following
    return ({int(v[vl]) for e in edges for v in e.verts}, {int(e[el]) for e in edges})


def _pick_controller_edge_id(context, event) -> int:
    """Resolve the nearest mapped proxy edge under a View3D mouse position."""
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    from mathutils import Vector

    source, controller = _context_source(context)
    bm = bmesh.from_edit_mesh(controller.data)
    layer = bm.edges.layers.int.get(PROXY_EID_ATTR)
    if layer is None:
        raise ValueError("PROXY_MAPPING_MISSING")
    mouse = Vector((event.mouse_region_x, event.mouse_region_y))
    candidates = []
    for edge in bm.edges:
        if edge.hide:
            continue
        world = [controller.matrix_world @ vertex.co for vertex in edge.verts]
        screen = [location_3d_to_region_2d(context.region, context.region_data, point) for point in world]
        if any(point is None for point in screen):
            continue
        a, b = screen
        delta = b - a
        factor = max(0.0, min(1.0, (mouse - a).dot(delta) / delta.length_squared)) if delta.length_squared else 0.0
        distance = (mouse - (a + factor * delta)).length
        if distance <= 12.0:
            midpoint = world[0].lerp(world[1], factor)
            depth = -(context.region_data.view_matrix @ midpoint).z
            if not _pick_point_visible(context, source, midpoint):
                continue
            candidates.append((distance, depth, int(edge[layer])))
    if not candidates:
        raise ValueError("CONTROL_EDGE_NOT_FOUND")
    return min(candidates)[2]


def _pick_point_visible(context, source, point) -> bool:
    """Use the same opaque Source occlusion policy as the control overlay."""
    if (context.scene.dan_form_overlay_xray or source is None
            or not source.visible_get(view_layer=context.view_layer)
            or context.space_data.shading.type == "WIREFRAME"
            or context.space_data.shading.show_xray):
        return True
    from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_origin_3d

    screen = location_3d_to_region_2d(context.region, context.region_data, point)
    if screen is None:
        return False
    # Clamp orthographic origins to the model's scale to avoid far-clip precision loss.
    scale = max(source.dimensions.length, 1.0)
    origin = region_2d_to_origin_3d(context.region, context.region_data, screen, clamp=scale * 4)
    inv = source.matrix_world.inverted_safe()
    local_origin, local_point = inv @ origin, inv @ point
    ray = local_point - local_origin
    if ray.length < 1e-8:
        return True
    hit, location, _normal, _index = source.ray_cast(local_origin, ray.normalized(), distance=ray.length)
    return not hit or (location - local_point).length <= scale * 1e-4


def _proxy_selection_snapshot(controller: bpy.types.Object) -> tuple[set[int], set[int]]:
    """Capture exact proxy selection flags without applying edge-mode filtering."""
    bm = bmesh.from_edit_mesh(controller.data)
    vid_layer = bm.verts.layers.int.get(PROXY_VID_ATTR)
    eid_layer = bm.edges.layers.int.get(PROXY_EID_ATTR)
    if vid_layer is None or eid_layer is None:
        raise ValueError("PROXY_MAPPING_MISSING")
    return (
        {int(vertex[vid_layer]) for vertex in bm.verts if vertex.select},
        {int(edge[eid_layer]) for edge in bm.edges if edge.select},
    )


def _control_for_edge(source: bpy.types.Object, edge_id: int, scene: bpy.types.Scene | None = None) -> dict:
    candidates = [
        control for control in _controls(source)
        if edge_id in {int(value) for value in control.get("edge_ids", [])}
    ]
    active_uuid = getattr(scene or bpy.context.scene, "dan_form_selected_control", "")
    selected = next((control for control in candidates if control.get("control_uuid") == active_uuid), None)
    if selected is None and len(candidates) == 1:
        selected = candidates[0]
    if selected is None:
        if not candidates:
            raise ValueError("CONTROL_EDGE_NOT_IN_DEFINITION")
        raise ValueError("CONTROL_EDGE_SHARED_SELECT_FROM_LIST")
    return selected


def _selection_target_for_edge(source: bpy.types.Object, controller: bpy.types.Object, edge_id: int, tool: str, scene: bpy.types.Scene | None = None) -> tuple[set[int], set[int], str]:
    """Resolve a hover-picked edge into a segment or whole-control selection."""
    if tool == "SEGMENT":
        vertices, edges = _proxy_segment(controller, edge_id)
        return vertices, edges, ""
    control = _control_for_edge(source, edge_id, scene)
    vertices, edges = _control_effective(source, control)
    if not vertices and not edges:
        raise ValueError("CONTROL_HIDDEN")
    return vertices, edges, control.get("control_uuid", "")


def _view3d_pick_edge(context: bpy.types.Context, event) -> int:
    """Pick in the View3D window even when the modal tool starts from the sidebar."""
    area = context.area if context.area and context.area.type == "VIEW_3D" else None
    if area is None and context.screen is not None:
        area = next((item for item in context.screen.areas if item.type == "VIEW_3D"), None)
    if area is None:
        raise ValueError("VIEW_3D_REQUIRED")
    region = next((item for item in area.regions if item.type == "WINDOW"), None)
    if region is None or area.spaces.active.region_3d is None:
        raise ValueError("VIEW_3D_REQUIRED")
    # Modal events retain the invocation region (UI when started in sidebar).
    # temp_override does not convert event.mouse_region_x/y into WINDOW space.
    if hasattr(event, "mouse_x") and hasattr(event, "mouse_y"):
        event = SimpleNamespace(mouse_region_x=event.mouse_x - region.x,
                                mouse_region_y=event.mouse_y - region.y)
    with context.temp_override(area=area, region=region, region_data=area.spaces.active.region_3d):
        return _pick_controller_edge_id(context, event)


def _apply_proxy_pick_selection(context, controller, vertices, edges, operation="SET") -> None:
    if operation == "ADD":
        _select_proxy_ids(controller, vertices, edges, add=True)
        return
    if operation == "SUBTRACT":
        old_vertices, old_edges = _proxy_selection_snapshot(controller)
        vertices, edges = old_vertices - vertices, old_edges - edges
        if context.tool_settings.mesh_select_mode[1]:
            bm = bmesh.from_edit_mesh(controller.data)
            vl, el = bm.verts.layers.int[PROXY_VID_ATTR], bm.edges.layers.int[PROXY_EID_ATTR]
            vertices.update(int(v[vl]) for e in bm.edges if int(e[el]) in edges for v in e.verts)
    _select_proxy_ids(controller, vertices, edges)


def _set_pick_preview(context, controller, edge_ids) -> None:
    import gpu
    from gpu_extras.batch import batch_for_shader

    bm = bmesh.from_edit_mesh(controller.data)
    layer = bm.edges.layers.int[PROXY_EID_ATTR]
    positions = [controller.matrix_world @ v.co for e in bm.edges
                 if int(e[layer]) in edge_ids and not e.hide for v in e.verts]
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    _PICK_PREVIEW.update(controller=controller.as_pointer(), area=context.area.as_pointer(),
                         batch=batch_for_shader(shader, "LINES", {"pos": positions}))
    _tag_viewport_redraw(context)


class DANFORM_OT_pick_selection_tool(bpy.types.Operator):
    bl_idname = "dan_form.pick_selection_tool"
    bl_label = "Pick DANP Selection"
    bl_description = "Hover a control edge to preview a segment or whole-control selection; click to confirm"
    bl_options = {"REGISTER", "UNDO"}
    tool: EnumProperty(
        name="Tool",
        items=(
            ("SEGMENT", "Segment", "Select the visible span between junctions"),
            ("CONTROL", "Control", "Select the whole logical control"),
        ),
        default="SEGMENT",
        options={"HIDDEN"},
    )
    add_to_selection: BoolProperty(name="Add to Selection", default=False, options={"HIDDEN"})

    def _finish(self, context, cancelled=False) -> set[str]:
        if self._session == _PICK_SESSION:
            _PICK_PREVIEW.clear()
            if self._area is not None:
                self._area.header_text_set(None)
        _tag_viewport_redraw(context)
        context.scene.dan_form_status = "Pick stopped" if cancelled else "Selection confirmed"
        return {"FINISHED"} if self._committed or not cancelled else {"CANCELLED"}

    def _in_viewport(self, event) -> bool:
        if self._area is None:
            return False
        x, y = event.mouse_x, event.mouse_y
        for region in self._area.regions:
            if region.type in {"UI", "TOOLS"} and region.width > 0 and region.height > 0:
                if region.x <= x < region.x + region.width and region.y <= y < region.y + region.height:
                    return False
        region = next((r for r in self._area.regions if r.type == "WINDOW"), None)
        return bool(region and region.x <= x < region.x + region.width and region.y <= y < region.y + region.height)

    def _preview(self, context, event) -> None:
        source, controller = _context_source(context)
        if source is None or controller is None:
            return
        try:
            edge_id = _view3d_pick_edge(context, event)
            target = _selection_target_for_edge(source, controller, edge_id, self.tool, context.scene)
        except ValueError as exc:
            _PICK_PREVIEW.clear()
            self._last_target = None
            self._last_edge_id = None
            if str(exc) == "CONTROL_EDGE_SHARED_SELECT_FROM_LIST":
                context.scene.dan_form_status = "Cạnh chung: chọn control trong danh sách trước"
            _tag_viewport_redraw(context)
            return
        if self._last_target is not None and target == self._last_target:
            return
        _set_pick_preview(context, controller, target[1])
        context.scene.dan_form_status = f"Preview: {len(target[1])} edges; click to select"
        self._last_edge_id = edge_id
        self._last_target = target
        for area in context.screen.areas if context.screen else ():
            if area.type == "VIEW_3D":
                area.tag_redraw()

    @classmethod
    def poll(cls, context):
        return DANFORM_OT_topology_locked.poll(context)

    def invoke(self, context, event):
        global _PICK_SESSION
        source, controller = _context_source(context)
        if source is None or controller is None:
            return {"CANCELLED"}
        self.add_to_selection = bool(getattr(event, "shift", False) or context.scene.dan_form_add_to_selection)
        _PICK_SESSION += 1
        self._session = _PICK_SESSION
        self._controller = controller.as_pointer()
        self._generation = controller.get(PROXY_GENERATION_KEY)
        self._area = context.area
        self._committed = False
        self._navigating = False
        _PICK_PREVIEW.clear()
        self._last_edge_id = None
        self._last_target = None
        context.scene.dan_form_status = (
            f"Hover để xem trước {'đoạn' if self.tool == 'SEGMENT' else 'control'}, click để chọn; Esc để hủy"
        )
        if self._area is not None:
            self._area.header_text_set("DANP Pick: LMB chọn · Shift cộng · Ctrl bỏ chọn · RMB/Esc dừng · MMB/Wheel điều hướng")
        context.window_manager.modal_handler_add(self)
        return {"RUNNING_MODAL"}

    def modal(self, context, event):
        _, controller = _context_source(context)
        if (self._session != _PICK_SESSION or controller is None or controller.mode != "EDIT"
                or controller.as_pointer() != self._controller or controller.get(PROXY_GENERATION_KEY) != self._generation):
            return self._finish(context, cancelled=True)
        if event.type in {"ESC", "RIGHTMOUSE"} and event.value == "PRESS":
            return self._finish(context, cancelled=True)
        if event.type == "MIDDLEMOUSE":
            self._navigating = event.value != "RELEASE"
            _PICK_PREVIEW.clear()
            self._last_target = None
            return {"PASS_THROUGH"}
        if event.type in {"WHEELUPMOUSE", "WHEELDOWNMOUSE", "TRACKPADPAN", "TRACKPADZOOM", "MOUSEROTATE", "MOUSESMARTZOOM"}:
            _PICK_PREVIEW.clear()
            self._last_target = None
            return {"PASS_THROUGH"}
        if event.type == "MOUSEMOVE":
            if self._navigating or not self._in_viewport(event):
                _PICK_PREVIEW.clear()
                self._last_target = None
                return {"PASS_THROUGH"}
            self._preview(context, event)
            return {"PASS_THROUGH"}
        if event.type == "LEFTMOUSE" and event.value == "PRESS":
            if not self._in_viewport(event):
                return self._finish(context) | {"PASS_THROUGH"}
            # Resolve again after zoom/pan or a click without a prior move.
            self._last_target = None
            self._preview(context, event)
            if self._last_target is None:
                return self._finish(context) | {"PASS_THROUGH"}
            operation = "SUBTRACT" if event.ctrl else ("ADD" if event.shift or self.add_to_selection else "SET")
            _apply_proxy_pick_selection(context, controller, self._last_target[0], self._last_target[1], operation)
            if self._last_target[2]:
                context.scene.dan_form_selected_control = self._last_target[2]
                _activate_ui_control(context.scene, self._last_target[2])
            self._committed = True
            _PICK_PREVIEW.clear()
            self._last_target = None
            if self.add_to_selection or event.shift or event.ctrl:
                return {"RUNNING_MODAL"}
            return self._finish(context)
        # A, B, C, G/R/S, Tab, undo and other native commands retain their keys.
        # End preview before dispatch, rather than stealing their mouse events.
        if event.value == "PRESS" and event.type not in {"LEFT_SHIFT", "RIGHT_SHIFT", "LEFT_CTRL", "RIGHT_CTRL", "LEFT_ALT", "RIGHT_ALT", "LEFTMOUSE"}:
            return self._finish(context) | {"PASS_THROUGH"}
        return {"PASS_THROUGH"}


class DANFORM_OT_select_control_at_cursor(bpy.types.Operator):
    bl_idname = "dan_form.select_control_at_cursor"
    bl_label = "Select Control Under Cursor"
    bl_description = "Ctrl+Shift+Click a control edge to select the whole mapped control"
    bl_options = {"REGISTER", "UNDO"}
    edge_id: IntProperty(name="Source Edge ID", default=0, min=0)
    extend: BoolProperty(name="Add to Selection", default=False)

    @classmethod
    def poll(cls, context):
        return DANFORM_OT_topology_locked.poll(context)

    def invoke(self, context, event):
        if event.type != "LEFTMOUSE":
            return self.execute(context)
        if context.region is None or context.region.type != "WINDOW" or context.region_data is None:
            return {"CANCELLED"}
        try:
            # Shift is part of this shortcut itself; it must not force Add.
            self.extend = bool(self.extend or context.scene.dan_form_add_to_selection)
            self.edge_id = _pick_controller_edge_id(context, event)
            return self.execute(context)
        except ValueError as exc:
            self.report({"INFO"}, str(exc))
            return {"CANCELLED"}

    def execute(self, context):
        source, controller = _context_source(context)
        if source is None or controller is None:
            return {"CANCELLED"}
        edge_id = self.edge_id
        if not edge_id:
            bm = bmesh.from_edit_mesh(controller.data)
            layer = bm.edges.layers.int.get(PROXY_EID_ATTR)
            active = bm.select_history.active
            if isinstance(active, bmesh.types.BMEdge) and layer is not None:
                edge_id = int(active[layer])
            else:
                selected = [edge for edge in bm.edges if edge.select]
                if len(selected) == 1 and layer is not None:
                    edge_id = int(selected[0][layer])
        try:
            selected = _control_for_edge(source, edge_id, context.scene)
        except ValueError as exc:
            if str(exc) == "CONTROL_EDGE_SHARED_SELECT_FROM_LIST":
                self.report({"WARNING"}, str(exc))
            else:
                self.report({"INFO"}, str(exc))
            return {"CANCELLED"}
        effective_vertices, effective_edges = _control_effective(source, selected)
        if not effective_vertices and not effective_edges:
            self.report({"INFO"}, "CONTROL_HIDDEN")
            return {"CANCELLED"}
        _select_proxy_ids(controller, effective_vertices, effective_edges, add=self.extend)
        context.scene.dan_form_selected_control = selected.get("control_uuid", "")
        context.scene.dan_form_status = f"Selected {selected.get('name', 'Control')}"
        _sync_context_ui_list(context)
        return {"FINISHED"}


class DANFORM_OT_select_segment(bpy.types.Operator):
    bl_idname = "dan_form.select_segment"
    bl_label = "Select Segment Between Junctions"
    bl_description = "Ctrl+Alt+Click an edge; Shift adds a span. Stop at junctions/endpoints; select a full uncut loop"
    bl_options = {"REGISTER", "UNDO"}
    edge_id: IntProperty(name="Source Edge ID", default=0, min=0)
    extend: BoolProperty(name="Extend Selection", default=False)

    @classmethod
    def poll(cls, context):
        return DANFORM_OT_topology_locked.poll(context)

    def invoke(self, context, event):
        if event.type != "LEFTMOUSE":
            return self.execute(context)
        if context.region is None or context.region.type != "WINDOW" or context.region_data is None:
            return {"CANCELLED"}
        try:
            self.edge_id = _pick_controller_edge_id(context, event)
        except ValueError as exc:
            self.report({"INFO"}, str(exc))
            return {"CANCELLED"}
        context.tool_settings.mesh_select_mode = (False, True, False)
        return self.execute(context)

    def execute(self, context):
        _, controller = _context_source(context)
        seed_id = self.edge_id
        if not seed_id:
            bm = bmesh.from_edit_mesh(controller.data)
            layer = bm.edges.layers.int.get(PROXY_EID_ATTR)
            active = bm.select_history.active
            if isinstance(active, bmesh.types.BMEdge) and layer is not None:
                seed_id = int(active[layer])
            else:
                selected = [e for e in bm.edges if e.select]
                if len(selected) == 1 and layer is not None:
                    seed_id = int(selected[0][layer])
        try:
            vertices, edges = _proxy_segment(controller, seed_id)
            _select_proxy_ids(controller, vertices, edges, add=self.extend)
            context.scene.dan_form_status = f"Selected span: {len(edges)} edges"
            return {"FINISHED"}
        except ValueError as exc:
            self.report({"WARNING"}, str(exc))
            return {"CANCELLED"}


class DANFORM_OT_clear_selection(bpy.types.Operator):
    bl_idname = "dan_form.clear_selection"
    bl_label = "Clear Selection"
    bl_description = "Clear the current controller selection without changing control definitions"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return DANFORM_OT_topology_locked.poll(context)

    def execute(self, context):
        _, controller = _context_source(context)
        _select_proxy_ids(controller, set(), set())
        context.scene.dan_form_status = "Controller selection cleared"
        return {"FINISHED"}


class DANFORM_OT_select_all_controls(bpy.types.Operator):
    bl_idname = "dan_form.select_all_controls"
    bl_label = "Select All Controls"
    bl_description = "Select every currently enabled control element"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        return DANFORM_OT_topology_locked.poll(context)

    def execute(self, context):
        source, controller = _context_source(context)
        vertices, edges = _effective_proxy_elements(source)
        _select_proxy_ids(controller, vertices, edges)
        context.scene.dan_form_status = f"Selected all controls: {len(edges)} edges"
        return {"FINISHED"}


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


def _register_control_keymaps():
    config = bpy.context.window_manager.keyconfigs.addon
    if config is None:
        return
    km = config.keymaps.new(name="Mesh", space_type="EMPTY")
    for operator, key, modifiers in (
        ("dan_form.hide_selected", "H", {}),
        ("dan_form.reveal_controller", "H", {"alt": True}),
        ("dan_form.pick_selection_tool", "S", {"ctrl": True, "alt": True}),
        ("dan_form.pick_selection_tool", "C", {"ctrl": True, "alt": True}),
        ("dan_form.select_control_at_cursor", "LEFTMOUSE", {"ctrl": True, "shift": True}),
        ("dan_form.select_segment", "LEFTMOUSE", {"ctrl": True, "alt": True}),
        ("dan_form.select_segment", "LEFTMOUSE", {"ctrl": True, "alt": True, "shift": True}),
    ):
        item = km.keymap_items.new(operator, key, "PRESS", head=True, **modifiers)
        if operator == "dan_form.pick_selection_tool":
            item.properties.tool = "SEGMENT" if key == "S" else "CONTROL"
        if operator == "dan_form.select_segment":
            item.properties.extend = modifiers.get("shift", False)
        _CONTROL_KEYMAPS.append((km, item))


def _unregister_control_keymaps():
    for km, item in _CONTROL_KEYMAPS:
        km.keymap_items.remove(item)
    _CONTROL_KEYMAPS.clear()


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
        if hide:
            edges, nodes = set(), set()
            for control in _controls(source):
                control_edges, control_nodes = _control_intent(source, control)
                edges.update(control_edges)
                nodes.update(control_nodes)
            changed = _mutate_masks(source, nodes, edges, reveal=False)
        else:
            changed = _mutate_masks(source, set(), set(), reveal=True)
        source[VIEWPORT_HIDDEN_KEY] = False  # Migrate the old display-only flag.
        controller.hide_set(False, view_layer=context.view_layer)
        if changed:
            _rebuild_proxy(source, controller)
        _sync_context_ui_list(context)
        context.scene.dan_form_status = "Hidden all controls" if hide else "Revealed all controls"
        _tag_viewport_redraw(context)
        return {"FINISHED"}


class DANFORM_OT_focus_source(bpy.types.Operator):
    bl_idname = "dan_form.focus_source"
    bl_label = "Back to Model"
    bl_description = "Return to the model in the mode used before editing controls"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        if source is None:
            return {"CANCELLED"}
        try:
            active = context.view_layer.objects.active
            if active is not None and active.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            _select_only(context, source)
            if _RETURN_MODES.pop(source.get(SOURCE_UUID_KEY), "OBJECT") == "EDIT":
                bpy.ops.object.mode_set(mode="EDIT")
            _set_scene_context(context, source, controller)
            _sync_context_ui_list(context)
            return {"FINISHED"}
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class DANFORM_OT_focus_controller(bpy.types.Operator):
    bl_idname = "dan_form.focus_controller"
    bl_label = "Edit Control"
    bl_description = "Enter controller Edit Mode and select the active control"
    bl_options = {"REGISTER", "UNDO"}

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
            active = context.view_layer.objects.active
            if active == source:
                _RETURN_MODES[source.get(SOURCE_UUID_KEY)] = source.mode
            if active is not None and active.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            if source.get(VIEWPORT_HIDDEN_KEY, False):
                source[VIEWPORT_HIDDEN_KEY] = False
            controller.hide_set(False, view_layer=context.view_layer)
            _select_only(context, controller)
            bpy.ops.object.mode_set(mode="EDIT")
            control = _active_control(context, source)
            if control is not None:
                vertex_ids, edge_ids = _control_effective(source, control)
                _select_proxy_ids(controller, vertex_ids, edge_ids)
            _set_scene_context(context, source, controller)
            _sync_context_ui_list(context)
            return {"FINISHED"}
        except RuntimeError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


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
        if source is None:
            layout.label(text="Chọn một mesh DANP Form hoặc controller", icon="INFO")
            return
        if active == source:
            lifecycle = layout.row(align=True)
            lifecycle.enabled = source.mode in {"OBJECT", "EDIT"}
            lifecycle.operator(DANFORM_OT_initialize.bl_idname, text="Init DANP Form", icon="ADD")
            remove = lifecycle.row(align=True)
            remove.alert = True
            remove.operator(DANFORM_OT_remove.bl_idname, text="Remove DANP Form", icon="TRASH")
        if source.get(SOURCE_UUID_KEY) is None:
            return
        if controller is None:
            layout.label(text="Nhấn Init để dựng lại controller", icon="INFO")
            return
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
            if controller.mode == "OBJECT":
                navigation.operator(DANFORM_OT_focus_controller.bl_idname, text="Edit Control", icon="EDITMODE_HLT")
        else:
            navigation.operator(DANFORM_OT_focus_controller.bl_idname, text="Edit Control", icon="EDITMODE_HLT")
        hidden = not bool(_effective_proxy_elements(source)[0])
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
            pick_row = setup.row(align=True)
            segment = pick_row.operator(DANFORM_OT_pick_selection_tool.bl_idname, text="Pick Segment", icon="EDGESEL")
            segment.tool = "SEGMENT"
            control = pick_row.operator(DANFORM_OT_pick_selection_tool.bl_idname, text="Pick Control", icon="OUTLINER_OB_MESH")
            control.tool = "CONTROL"
            setup.prop(scene, "dan_form_add_to_selection", text="Add to Selection")
            selection_row = setup.row(align=True)
            selection_row.operator(DANFORM_OT_clear_selection.bl_idname, text="Clear", icon="X")
            selection_row.operator(DANFORM_OT_select_all_controls.bl_idname, text="All Controls", icon="SELECT_EXTEND")
            setup.label(text="LMB chọn · Shift cộng · Ctrl bỏ chọn", icon="INFO")
            setup.label(text="RMB/Esc dừng · MMB/Wheel điều hướng")
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
            buttons.operator(DANFORM_OT_delete_control.bl_idname, text="", icon="REMOVE")
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
            layout.label(text="Edit Source rồi chọn điểm/cạnh để nhấn +", icon="INFO")


CLASSES = (
    DANFORM_PG_ControlItem,
    DANFORM_UL_controls,
    DANFORM_OT_initialize,
    DANFORM_OT_sync,
    DANFORM_OT_create_control,
    DANFORM_OT_sync_control,
    DANFORM_OT_move_control,
    DANFORM_OT_rename_control,
    DANFORM_OT_select_control,
    DANFORM_OT_set_control_visibility,
    DANFORM_OT_delete_control,
    DANFORM_OT_hide_selected,
    DANFORM_OT_reveal,
    DANFORM_OT_remove_controller,
    DANFORM_OT_remove,
    DANFORM_OT_topology_locked,
    DANFORM_OT_pick_selection_tool,
    DANFORM_OT_select_control_at_cursor,
    DANFORM_OT_select_segment,
    DANFORM_OT_clear_selection,
    DANFORM_OT_select_all_controls,
    DANFORM_OT_reveal_controller,
    DANFORM_OT_toggle_viewport_controls,
    DANFORM_OT_focus_source,
    DANFORM_OT_focus_controller,
    DANFORM_MT_control_menu,
    DANFORM_PT_sidebar,
)


def register() -> None:
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.dan_form_source = PointerProperty(
        name="DANP Form Source",
        type=bpy.types.Object,
        poll=lambda _self, obj: obj.type == "MESH",
    )
    bpy.types.Scene.dan_form_controller = PointerProperty(name="DANP Form Controller", type=bpy.types.Object)
    bpy.types.Scene.dan_form_status = StringProperty(name="DANP Form Status", default="Select a mesh Source")
    bpy.types.Scene.dan_form_selected_control = StringProperty(name="Selected Control", default="")
    bpy.types.Scene.dan_form_control_items = CollectionProperty(type=DANFORM_PG_ControlItem)
    bpy.types.Scene.dan_form_control_index = IntProperty(name="Active Control", default=0, min=0, update=_ui_control_index_update)
    bpy.types.Scene.dan_form_ui_source_uuid = StringProperty(name="UI Source UUID", default="")
    bpy.types.Scene.dan_form_overlay_enabled = BoolProperty(name="Control Overlay", default=True)
    bpy.types.Scene.dan_form_patches_enabled = BoolProperty(name="Show Patches", default=False)
    bpy.types.Scene.dan_form_overlay_hidden = BoolProperty(name="Show Hidden Controls", default=False)
    bpy.types.Scene.dan_form_overlay_xray = BoolProperty(name="X-Ray", default=False, update=_update_overlay_display)
    bpy.types.Scene.dan_form_overlay_width = FloatProperty(name="Line Width", default=3.0, min=1.0, max=8.0)
    bpy.types.Scene.dan_form_add_to_selection = BoolProperty(name="Add to Selection", default=False)
    if _depsgraph_update_post not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_depsgraph_update_post)
    for handlers in (bpy.app.handlers.undo_post, bpy.app.handlers.redo_post, bpy.app.handlers.load_post):
        if _refresh_runtime not in handlers:
            handlers.append(_refresh_runtime)
    _refresh_runtime()
    _update_overlay_display(bpy.context.scene)
    _register_overlay()
    _register_topology_keymaps()
    _register_control_keymaps()


def unregister() -> None:
    global _PICK_SESSION
    _PICK_SESSION += 1
    _PICK_PREVIEW.clear()
    _unregister_control_keymaps()
    _unregister_topology_keymaps()
    _unregister_overlay()
    for controller in bpy.data.objects:
        previous = _XRAY_SHOW_IN_FRONT.pop(controller.as_pointer(), None)
        if previous is not None:
            controller.show_in_front = previous
    _XRAY_SHOW_IN_FRONT.clear()
    if _depsgraph_update_post in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_depsgraph_update_post)
    for handlers in (bpy.app.handlers.undo_post, bpy.app.handlers.redo_post, bpy.app.handlers.load_post):
        if _refresh_runtime in handlers:
            handlers.remove(_refresh_runtime)
    _MAPPING_CACHE.clear()
    _UI_SIGNATURES.clear()
    _ACTIVE_CONTROL_UUIDS.clear()
    _RETURN_MODES.clear()
    _PROXY_SNAPSHOTS.clear()
    _NETWORK_CACHE.clear()
    _PATCH_CACHE.clear()
    _PATCH_OVERLAY_CACHE.clear()
    _OVERLAY_CACHE.clear()
    for prop in (
        "dan_form_overlay_width",
        "dan_form_overlay_xray",
        "dan_form_overlay_hidden",
        "dan_form_overlay_enabled",
        "dan_form_patches_enabled",
        "dan_form_add_to_selection",
        "dan_form_selected_control",
        "dan_form_ui_source_uuid",
        "dan_form_control_index",
        "dan_form_control_items",
        "dan_form_status",
        "dan_form_controller",
        "dan_form_source",
    ):
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass


if __name__ == "__main__":
    register()
