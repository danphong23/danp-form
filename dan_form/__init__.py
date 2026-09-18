"""DAN Form Phase 1/2: Source binding, persistent controls, and exact proxy sync."""

from __future__ import annotations

import hashlib
import json
import uuid

import bmesh
import bpy
from bpy.app.handlers import persistent
from bpy.props import BoolProperty, CollectionProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
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
VIEWPORT_HIDDEN_KEY = "dan_form_controls_viewport_hidden"

bl_info = {
    "name": "DAN Form",
    "author": "DAN Form",
    "version": (0, 2, 1),
    "blender": (5, 1, 0),
    "location": "View3D > Sidebar > DAN Form",
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
        vid_layer = bm.verts.layers.int.get(VID_ATTR)
        eid_layer = bm.edges.layers.int.get(EID_ATTR)
        if vid_layer is None or eid_layer is None:
            raise ValueError("SOURCE_ID_LAYERS_MISSING")
        vids = {int(vert[vid_layer]): vert.index for vert in bm.verts}
        eids = {int(edge[eid_layer]): edge.index for edge in bm.edges}
    else:
        vid_attr = source.data.attributes.get(VID_ATTR)
        eid_attr = source.data.attributes.get(EID_ATTR)
        if vid_attr is None or eid_attr is None:
            raise ValueError("SOURCE_ID_LAYERS_MISSING")
        vids = {int(item.value): index for index, item in enumerate(vid_attr.data)}
        eids = {int(item.value): index for index, item in enumerate(eid_attr.data)}
    _MAPPING_CACHE[cache_key] = (signature, vids, eids)
    return vids, eids


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
    visible_vertices: set[int] = set()
    for control in controls:
        for edge_id in control.get("edge_ids", []):
            edge_id = int(edge_id)
            edge_index = eid_to_index.get(edge_id)
            if edge_index is None or edge_id in hidden_eids:
                continue
            edge = source.data.edges[edge_index]
            endpoint_ids = {_source_vid(source, vertex_index) for vertex_index in edge.vertices}
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
                endpoint_ids.update(_source_vid(source, vertex_index) for vertex_index in source.data.edges[edge_index].vertices)
        for vertex_id in control.get("vertex_ids", []):
            vertex_id = int(vertex_id)
            if vertex_id not in hidden_vids and vertex_id in vid_to_index and (
                not control.get("edge_ids") or vertex_id not in endpoint_ids
            ):
                visible_vertices.add(vertex_id)
    return sorted(visible_vertices), sorted(visible_edges)


def _control_intent(source: bpy.types.Object, control: dict) -> tuple[set[int], set[int]]:
    """Return edge and explicit-node intent for whole-definition actions."""
    _, edge_indices = _source_id_maps(source)
    endpoint_ids: set[int] = set()
    for edge_id in control.get("edge_ids", []):
        edge_index = edge_indices.get(int(edge_id))
        if edge_index is None:
            continue
        endpoint_ids.update(_source_vid(source, vertex_index) for vertex_index in source.data.edges[edge_index].vertices)
    edge_ids = {int(edge_id) for edge_id in control.get("edge_ids", []) if int(edge_id) in edge_indices}
    node_ids = {int(vertex_id) for vertex_id in control.get("vertex_ids", [])}
    if edge_ids:
        node_ids.difference_update(endpoint_ids)
    return edge_ids, node_ids


def _control_effective(source: bpy.types.Object, control: dict) -> tuple[set[int], set[int]]:
    hidden_vids = _hidden(source, HIDDEN_VIDS_KEY)
    hidden_eids = _hidden(source, HIDDEN_EIDS_KEY)
    _, edge_indices = _source_id_maps(source)
    effective_edges: set[int] = set()
    effective_vertices: set[int] = set()
    for edge_id in control.get("edge_ids", []):
        edge_id = int(edge_id)
        edge_index = edge_indices.get(edge_id)
        if edge_index is None or edge_id in hidden_eids:
            continue
        endpoints = {_source_vid(source, index) for index in source.data.edges[edge_index].vertices}
        if endpoints & hidden_vids:
            continue
        effective_edges.add(edge_id)
        effective_vertices.update(endpoints)
    _, explicit_nodes = _control_intent(source, control)
    effective_vertices.update(explicit_nodes - hidden_vids)
    return effective_vertices, effective_edges


def _rebuild_proxy(source: bpy.types.Object, controller: bpy.types.Object) -> None:
    _validate_source_topology(source)
    vertex_ids, edge_ids = _effective_proxy_elements(source)
    vid_to_index, eid_to_index = _source_id_maps(source)
    proxy_mesh = controller.data
    old_active = bpy.context.view_layer.objects.active
    old_mode = old_active.mode if old_active is not None else "OBJECT"
    old_selected = [obj for obj in bpy.context.selected_objects]
    if controller.mode == "EDIT":
        # Blender cannot rebuild a Mesh datablock while its edit BMesh owns it.
        # Temporarily leave only the controller edit context, then restore it.
        bpy.ops.object.mode_set(mode="OBJECT")
    proxy_mesh.clear_geometry()
    proxy_vertices = [tuple(_source_co(source, vid_to_index[vid])) for vid in vertex_ids]
    proxy_vertex_index = {vid: index for index, vid in enumerate(vertex_ids)}
    proxy_edges = []
    kept_edge_ids = []
    for edge_id in edge_ids:
        edge = source.data.edges[eid_to_index[edge_id]]
        endpoint_ids = [_source_vid(source, index) for index in edge.vertices]
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


def _sync_proxy(source: bpy.types.Object, controller: bpy.types.Object) -> None:
    if controller is None or controller.data is None:
        return
    proxy_attr = controller.data.attributes.get(PROXY_VID_ATTR)
    if proxy_attr is None:
        return
    source_vids, _ = _source_id_maps(source)
    changed = False
    if controller.mode == "EDIT":
        bm = bmesh.from_edit_mesh(controller.data)
        layer = bm.verts.layers.int.get(PROXY_VID_ATTR)
        if layer is None:
            return
        for vert in bm.verts:
            source_index = source_vids.get(int(vert[layer]))
            if source_index is not None:
                position = _source_co(source, source_index)
                if (vert.co - position).length_squared > 1e-16:
                    vert.co = position
                    changed = True
        if changed:
            bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=False)
        return
    for index, item in enumerate(proxy_attr.data):
        source_index = source_vids.get(int(item.value))
        if source_index is not None and index < len(controller.data.vertices):
            position = _source_co(source, source_index)
            vert = controller.data.vertices[index]
            if (vert.co - position).length_squared > 1e-16:
                vert.co = position
                changed = True
    if changed:
        controller.data.update()


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
        _, edge_indices = _source_id_maps(source)
        for edge_id in edge_ids:
            edge_index = edge_indices.get(edge_id)
            if edge_index is not None:
                hidden_vids.difference_update(
                    _source_vid(source, vertex_index)
                    for vertex_index in source.data.edges[edge_index].vertices
                )
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
    _, edge_indices = _source_id_maps(source)
    for control in _controls(source):
        for edge_id in control.get("edge_ids", []):
            index = edge_indices.get(int(edge_id))
            if index is not None:
                defined_nodes.update(
                    _source_vid(source, vertex_index)
                    for vertex_index in source.data.edges[index].vertices
                )
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
            if source.as_pointer() not in changed_geometry and source.data.as_pointer() not in changed_geometry:
                continue
            _MAPPING_CACHE.pop(source.as_pointer(), None)
            try:
                _validate_source_topology(source)
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
    _MAPPING_CACHE.clear()
    _UI_SIGNATURES.clear()
    try:
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
    the colored line exactly on the editable control geometry.  Controller
    Edit Mode already has Blender's selected mesh display, so drawing a
    second Source overlay would only create a confusing duplicate.
    """
    source, controller = _context_source(context)
    active = context.view_layer.objects.active
    if source is None or controller is None or active is None:
        return "none"
    if active == controller:
        return "controller_edit_hidden" if controller.mode == "EDIT" else "controller"
    if active == source:
        return "source"
    return "none"


def _draw_control_overlay() -> None:
    """Draw the contextual control overlay without modifying mesh data."""
    try:
        import gpu
        from gpu_extras.batch import batch_for_shader

        context = bpy.context
        scene = context.scene
        if not getattr(scene, "dan_form_overlay_enabled", True):
            return
        overlay_mode = _overlay_mode(context)
        # In Controller Edit Mode the actual proxy mesh is the authoritative
        # display.  Suppressing this callback avoids a duplicate Source wire
        # that can appear offset while the user moves proxy vertices.
        if overlay_mode == "controller_edit_hidden" or overlay_mode == "none":
            return
        source, controller = _context_source(context)
        if source is None or controller is None or source.type != "MESH" or not source.get(SOURCE_UUID_KEY):
            return
        if overlay_mode == "source" and (
            source.get(VIEWPORT_HIDDEN_KEY, False)
        ):
            return
        selected_uuid = getattr(scene, "dan_form_selected_control", "")
        selected_control = _control(source, selected_uuid)

        if overlay_mode == "controller":
            # Controller Object Mode must use the current proxy coordinates,
            # including edits made before returning to Object Mode.  Mapping
            # only supplies selection colors; it never supplies positions.
            proxy_mesh = controller.data
            proxy_vid_attr = proxy_mesh.attributes.get(PROXY_VID_ATTR)
            proxy_eid_attr = proxy_mesh.attributes.get(PROXY_EID_ATTR)
            if proxy_vid_attr is None or proxy_eid_attr is None:
                return
            vid_to_index = {int(item.value): index for index, item in enumerate(proxy_vid_attr.data)}
            eid_to_index = {int(item.value): index for index, item in enumerate(proxy_eid_attr.data)}
            vertex_ids = list(vid_to_index)
            edge_positions = []
            for edge in proxy_mesh.edges:
                edge_positions.extend(
                    controller.matrix_world @ proxy_mesh.vertices[index].co
                    for index in edge.vertices
                )
            selected_positions = []
            selected_vertices = set()
            if selected_control:
                selected_vertices, selected_edges = _control_effective(source, selected_control)
                for edge_id in selected_edges:
                    edge_index = eid_to_index.get(edge_id)
                    if edge_index is not None:
                        selected_positions.extend(
                            controller.matrix_world @ proxy_mesh.vertices[index].co
                            for index in proxy_mesh.edges[edge_index].vertices
                        )
            standalone = [controller.matrix_world @ vertex.co for vertex in proxy_mesh.vertices]
            selected_points = [
                controller.matrix_world @ proxy_mesh.vertices[vid_to_index[vertex_id]].co
                for vertex_id in selected_vertices
                if vertex_id in vid_to_index
            ]
        else:
            vertex_ids, edge_ids = _effective_proxy_elements(source)
            if getattr(scene, "dan_form_overlay_hidden", False):
                _, all_edge_indices = _source_id_maps(source)
                edge_ids = sorted({int(edge_id) for c in _controls(source) for edge_id in c.get("edge_ids", []) if int(edge_id) in all_edge_indices})
                vertex_ids = sorted({int(vertex_id) for c in _controls(source) for vertex_id in c.get("vertex_ids", [])})
                for edge_id in edge_ids:
                    edge = source.data.edges[all_edge_indices[edge_id]]
                    vertex_ids.extend(_source_vid(source, index) for index in edge.vertices)
                vertex_ids = sorted(set(vertex_ids))
            vid_to_index, eid_to_index = _source_id_maps(source)
            edge_positions = []
            for edge_id in edge_ids:
                edge_index = eid_to_index.get(edge_id)
                if edge_index is None:
                    continue
                edge = source.data.edges[edge_index]
                edge_positions.extend(
                    (source.matrix_world @ _source_co(source, index)) for index in edge.vertices
                )
            selected_positions = []
            if selected_control:
                _, selected_edges = _control_effective(source, selected_control)
                for edge_id in selected_edges:
                    edge_index = eid_to_index.get(edge_id)
                    if edge_index is not None:
                        selected_positions.extend(
                            (source.matrix_world @ _source_co(source, index))
                            for index in source.data.edges[edge_index].vertices
                        )
            standalone = []
            for vertex_id in vertex_ids:
                index = vid_to_index.get(vertex_id)
                if index is not None:
                    standalone.append(source.matrix_world @ _source_co(source, index))
            selected_points = []
            if selected_control:
                selected_vertices, _ = _control_effective(source, selected_control)
                selected_points = [
                    source.matrix_world @ _source_co(source, vid_to_index[vertex_id])
                    for vertex_id in selected_vertices
                    if vertex_id in vid_to_index
                ]

        shader = gpu.shader.from_builtin("UNIFORM_COLOR")
        if getattr(scene, "dan_form_overlay_xray", False):
            try:
                gpu.state.depth_test_set("NONE")
            except Exception:
                pass
        if edge_positions:
            batch = batch_for_shader(shader, "LINES", {"pos": edge_positions})
            shader.bind()
            shader.uniform_float("color", (0.05, 0.75, 1.0, 0.95))
            gpu.state.line_width_set(float(getattr(scene, "dan_form_overlay_width", 3.0)))
            batch.draw(shader)
        if selected_positions:
            batch = batch_for_shader(shader, "LINES", {"pos": selected_positions})
            shader.bind()
            shader.uniform_float("color", (1.0, 0.45, 0.05, 1.0))
            gpu.state.line_width_set(float(getattr(scene, "dan_form_overlay_width", 3.0)) + 1.0)
            batch.draw(shader)
        if standalone:
            batch = batch_for_shader(shader, "POINTS", {"pos": standalone})
            shader.bind()
            shader.uniform_float("color", (0.2, 1.0, 0.7, 1.0))
            gpu.state.point_size_set(6.0)
            batch.draw(shader)
        if selected_points:
            batch = batch_for_shader(shader, "POINTS", {"pos": selected_points})
            shader.bind()
            shader.uniform_float("color", (1.0, 0.45, 0.05, 1.0))
            gpu.state.point_size_set(8.0)
            batch.draw(shader)
        if getattr(scene, "dan_form_overlay_xray", False):
            try:
                gpu.state.depth_test_set("LESS_EQUAL")
            except Exception:
                pass
    except Exception:
        # Drawing must never break Blender's viewport; the next redraw retries.
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
    bl_label = "Initialize DAN Form"
    bl_description = "Bind the selected mesh as a DAN Form Source and create its controller"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        active = context.view_layer.objects.active
        return active is not None and active.type == "MESH" and active.get(CONTROLLER_KEY) is None

    def execute(self, context: bpy.types.Context) -> set[str]:
        scene = context.scene
        source = context.view_layer.objects.active
        try:
            if not _is_valid_source(source):
                raise ValueError("SOURCE_NOT_EDITABLE")
            _source_uuid(source)
            _ensure_source_ids(source)
            controller = _find_controller(source)
            if controller is None:
                mesh = bpy.data.meshes.new(f"DANFORM_CTRL_{source.name}")
                mesh.from_pydata([], [], [])
                mesh.update()
                controller = bpy.data.objects.new(f"DANFORM_CTRL_{source.name}", mesh)
                _controller_collection(source, scene).objects.link(controller)
                controller[CONTROLLER_KEY] = source[ SOURCE_UUID_KEY ]
                controller[SCHEMA_KEY] = SCHEMA_VERSION
                controller["dan_form_source_name"] = source.name
                controller.display_type = "WIRE"
                controller.hide_render = True
            _rebuild_proxy(source, controller)
            source["dan_form_controller_name"] = controller.name
            _set_scene_context(context, source, controller)
            scene.dan_form_status = f"Ready: {source.name} / {controller.name}"
            self.report({"INFO"}, "DAN Form controller ready")
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

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        controls = _controls(source) if source is not None else []
        active_control = _active_control(context, source) if source is not None else None
        control = next((item for item in controls if active_control is not None and item.get("control_uuid") == active_control.get("control_uuid")), None)
        active = context.view_layer.objects.active
        if source is None or control is None or active not in {source, controller} or active.mode != "EDIT":
            self.report({"ERROR"}, "EDIT_SOURCE_OR_CONTROLLER_REQUIRED")
            return {"CANCELLED"}
        try:
            if active == source:
                vertex_ids, edge_ids = _source_selection(source)
            else:
                vertex_ids, edge_ids = _proxy_selection(controller)
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
        layout.operator("dan_form.select_control", text="Select Active", icon="RESTRICT_SELECT_OFF")
        layout.operator("dan_form.sync_control", text="Sync Membership", icon="FILE_REFRESH")
        layout.separator()
        layout.operator("dan_form.reveal", text="Reveal All", icon="HIDE_OFF")
        layout.operator("dan_form.hide_selected", text="Hide Selected", icon="HIDE_ON")
        layout.separator()
        layout.prop(context.scene, "dan_form_overlay_enabled", text="Control Overlay")
        layout.prop(context.scene, "dan_form_overlay_hidden", text="Show Hidden Controls")
        layout.operator("dan_form.remove_controller", text="Remove Controller", icon="TRASH")


class DANFORM_OT_create_control(bpy.types.Operator):
    bl_idname = "dan_form.create_control"
    bl_label = "Make Control from Source Selection"
    bl_description = "Create a Source-backed control from selected Source vertices and edges"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        source, controller = _context_source(context)
        active = context.view_layer.objects.active
        return source is not None and active in {source, controller} and active.mode == "EDIT"

    def execute(self, context: bpy.types.Context) -> set[str]:
        source, controller = _context_source(context)
        scene = context.scene
        try:
            active = context.view_layer.objects.active
            if active == source:
                vertex_ids, edge_ids = _source_selection(source)
            elif active == controller:
                vertex_ids, edge_ids = _proxy_selection(controller)
            else:
                raise ValueError("EDIT_SOURCE_OR_CONTROLLER_REQUIRED")
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
    bl_description = "Remove only the DAN Form controller object; keep Source definitions"
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
        bpy.data.objects.remove(controller, do_unlink=True)
        _set_scene_context(context, source, None)
        scene.dan_form_status = f"Source ready: {source.name}" if source else "No controller"
        self.report({"INFO"}, "Controller removed; Source definitions preserved")
        return {"FINISHED"}


class DANFORM_OT_toggle_viewport_controls(bpy.types.Operator):
    bl_idname = "dan_form.toggle_viewport_controls"
    bl_label = "Hide/Show Controls"
    bl_description = "Show or hide all control wires in the viewport; keep control influence and masks"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        source, controller = _context_source(context)
        active = context.view_layer.objects.active
        return source is not None and controller is not None and active.mode in {"OBJECT", "EDIT"}

    def execute(self, context):
        source, controller = _context_source(context)
        hidden = not bool(source.get(VIEWPORT_HIDDEN_KEY, False))
        if hidden and context.view_layer.objects.active == controller:
            bpy.ops.dan_form.focus_source()
        source[VIEWPORT_HIDDEN_KEY] = hidden
        controller.hide_set(hidden, view_layer=context.view_layer)
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
        return source is not None and controller is not None and bool(_controls(source)) and active.mode in {"OBJECT", "EDIT"}

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
    bl_label = "DAN Form"
    bl_idname = "DANFORM_PT_sidebar"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DAN Form"
    bl_ui_units_x = 46

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        scene = context.scene
        source, controller = _context_source(context)
        active = context.view_layer.objects.active
        if source is None:
            layout.label(text="Chọn một mesh DAN Form hoặc controller", icon="INFO")
            return
        if source.get(SOURCE_UUID_KEY) is None:
            layout.operator(DANFORM_OT_initialize.bl_idname, icon="OUTLINER_OB_MESH")
            return
        if controller is None:
            layout.operator(DANFORM_OT_initialize.bl_idname, icon="OUTLINER_OB_MESH")
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
        hidden = bool(source.get(VIEWPORT_HIDDEN_KEY, False))
        navigation.operator(DANFORM_OT_toggle_viewport_controls.bl_idname, text="Show Controls" if hidden else "Hide Controls", icon="HIDE_ON" if hidden else "HIDE_OFF")
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
        buttons.operator(DANFORM_OT_create_control.bl_idname, text="", icon="ADD")
        buttons.operator(DANFORM_OT_delete_control.bl_idname, text="", icon="REMOVE")
        buttons.separator()
        buttons.menu(DANFORM_MT_control_menu.bl_idname, text="", icon="DOWNARROW_HLT")
        buttons.separator()
        move_up = buttons.operator(DANFORM_OT_move_control.bl_idname, text="", icon="TRIA_UP")
        move_up.direction = -1
        move_down = buttons.operator(DANFORM_OT_move_control.bl_idname, text="", icon="TRIA_DOWN")
        move_down.direction = 1
        edit_context = active in {source, controller} and active.mode == "EDIT"
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
        name="DAN Form Source",
        type=bpy.types.Object,
        poll=lambda _self, obj: obj.type == "MESH",
    )
    bpy.types.Scene.dan_form_controller = PointerProperty(name="DAN Form Controller", type=bpy.types.Object)
    bpy.types.Scene.dan_form_status = StringProperty(name="DAN Form Status", default="Select a mesh Source")
    bpy.types.Scene.dan_form_selected_control = StringProperty(name="Selected Control", default="")
    bpy.types.Scene.dan_form_control_items = CollectionProperty(type=DANFORM_PG_ControlItem)
    bpy.types.Scene.dan_form_control_index = IntProperty(name="Active Control", default=0, min=0, update=_ui_control_index_update)
    bpy.types.Scene.dan_form_ui_source_uuid = StringProperty(name="UI Source UUID", default="")
    bpy.types.Scene.dan_form_overlay_enabled = BoolProperty(name="Control Overlay", default=True)
    bpy.types.Scene.dan_form_overlay_hidden = BoolProperty(name="Show Hidden Controls", default=False)
    bpy.types.Scene.dan_form_overlay_xray = BoolProperty(name="X-Ray", default=False)
    bpy.types.Scene.dan_form_overlay_width = FloatProperty(name="Line Width", default=3.0, min=1.0, max=8.0)
    if _depsgraph_update_post not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_depsgraph_update_post)
    for handlers in (bpy.app.handlers.undo_post, bpy.app.handlers.redo_post, bpy.app.handlers.load_post):
        if _refresh_runtime not in handlers:
            handlers.append(_refresh_runtime)
    _refresh_runtime()
    _register_overlay()


def unregister() -> None:
    _unregister_overlay()
    if _depsgraph_update_post in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_depsgraph_update_post)
    for handlers in (bpy.app.handlers.undo_post, bpy.app.handlers.redo_post, bpy.app.handlers.load_post):
        if _refresh_runtime in handlers:
            handlers.remove(_refresh_runtime)
    _MAPPING_CACHE.clear()
    _UI_SIGNATURES.clear()
    _ACTIVE_CONTROL_UUIDS.clear()
    _RETURN_MODES.clear()
    for prop in (
        "dan_form_overlay_width",
        "dan_form_overlay_xray",
        "dan_form_overlay_hidden",
        "dan_form_overlay_enabled",
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
