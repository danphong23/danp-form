"""DAN Form Phase 1/2: Source binding, persistent controls, and exact proxy sync."""

from __future__ import annotations

import hashlib
import json
import sys
import uuid
from pathlib import Path

import bmesh
import bpy
from bpy.props import PointerProperty, StringProperty
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
_SYNC_GUARD = False

bl_info = {
    "name": "DAN Form",
    "author": "DAN Form",
    "version": (0, 2, 0),
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
    payload = {
        "vertices": len(mesh.vertices),
        "edges": [tuple(sorted(edge.vertices)) for edge in mesh.edges],
        "faces": [tuple(poly.vertices) for poly in mesh.polygons],
    }
    return hashlib.sha256(json.dumps(payload, separators=(",", ":")).encode("utf-8")).hexdigest()


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

    source[NEXT_VID_KEY] = max(next_vid, max(seen or {0}) + 1)
    source[NEXT_EID_KEY] = max(next_eid, max(seen or {0}) + 1)
    source[TOPOLOGY_KEY] = current_fingerprint
    if NETWORK_REVISION_KEY not in source:
        source[NETWORK_REVISION_KEY] = 0
    _json_set(source, CONTROLS_KEY, _controls(source))
    _json_set(source, HIDDEN_VIDS_KEY, sorted(_hidden(source, HIDDEN_VIDS_KEY)))
    _json_set(source, HIDDEN_EIDS_KEY, sorted(_hidden(source, HIDDEN_EIDS_KEY)))
    mesh.update()


def _source_id_maps(source: bpy.types.Object) -> tuple[dict[int, int], dict[int, int]]:
    _ensure_source_ids(source)
    vid_attr = source.data.attributes[VID_ATTR]
    eid_attr = source.data.attributes[EID_ATTR]
    vids = {int(item.value): index for index, item in enumerate(vid_attr.data)}
    eids = {int(item.value): index for index, item in enumerate(eid_attr.data)}
    return vids, eids


def _find_controller(source: bpy.types.Object) -> bpy.types.Object | None:
    source_uuid = source.get(SOURCE_UUID_KEY)
    if not source_uuid:
        return None
    for obj in bpy.data.objects:
        if obj.get(CONTROLLER_KEY) == source_uuid:
            return obj
    return None


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
            endpoint_ids = {
                int(source.data.attributes[VID_ATTR].data[vertex_index].value)
                for vertex_index in edge.vertices
            }
            if endpoint_ids & hidden_vids:
                continue
            visible_edges.add(edge_id)
            visible_vertices.update(endpoint_ids)
        # Vertex-only definitions are standalone points. For an edge-backed
        # definition, endpoint vertices are supported by the effective edges;
        # when those edges are hidden the endpoints must be released too.
        if not control.get("edge_ids"):
            for vertex_id in control.get("vertex_ids", []):
                vertex_id = int(vertex_id)
                if vertex_id not in hidden_vids and vertex_id in vid_to_index:
                    visible_vertices.add(vertex_id)
    return sorted(visible_vertices), sorted(visible_edges)


def _rebuild_proxy(source: bpy.types.Object, controller: bpy.types.Object) -> None:
    vertex_ids, edge_ids = _effective_proxy_elements(source)
    vid_to_index, eid_to_index = _source_id_maps(source)
    source_vid_attr = source.data.attributes[VID_ATTR]
    proxy_mesh = controller.data
    proxy_mesh.clear_geometry()
    proxy_vertices = [tuple(source.data.vertices[vid_to_index[vid]].co) for vid in vertex_ids]
    proxy_vertex_index = {vid: index for index, vid in enumerate(vertex_ids)}
    proxy_edges = []
    kept_edge_ids = []
    for edge_id in edge_ids:
        edge = source.data.edges[eid_to_index[edge_id]]
        endpoint_ids = [int(source_vid_attr.data[index].value) for index in edge.vertices]
        if all(endpoint in proxy_vertex_index for endpoint in endpoint_ids):
            proxy_edges.append(tuple(proxy_vertex_index[endpoint] for endpoint in endpoint_ids))
            kept_edge_ids.append(edge_id)
    proxy_mesh.from_pydata(proxy_vertices, proxy_edges, [])
    proxy_mesh.update()
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
    controller.hide_render = True
    controller[PROXY_GENERATION_KEY] = int(controller.get(PROXY_GENERATION_KEY, 0)) + 1
    proxy_mesh.update()


def _sync_proxy(source: bpy.types.Object, controller: bpy.types.Object) -> None:
    if controller is None or controller.data is None:
        return
    proxy_attr = controller.data.attributes.get(PROXY_VID_ATTR)
    if proxy_attr is None:
        return
    source_vids, _ = _source_id_maps(source)
    for index, item in enumerate(proxy_attr.data):
        source_index = source_vids.get(int(item.value))
        if source_index is not None and index < len(controller.data.vertices):
            controller.data.vertices[index].co = source.data.vertices[source_index].co
    controller.data.update()


def _update_revision(source: bpy.types.Object) -> None:
    source[NETWORK_REVISION_KEY] = int(source.get(NETWORK_REVISION_KEY, 0)) + 1


def _source_selection(source: bpy.types.Object) -> tuple[set[int], set[int]]:
    if source.mode != "EDIT" or bpy.context.view_layer.objects.active != source:
        raise ValueError("SOURCE_EDIT_MODE_REQUIRED")
    _ensure_source_ids(source)
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


def _mutate_masks(source: bpy.types.Object, vertex_ids: set[int], edge_ids: set[int], reveal: bool) -> bool:
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
        source_vid_attr = source.data.attributes[VID_ATTR]
        for edge_id in edge_ids:
            edge_index = edge_indices.get(edge_id)
            if edge_index is not None:
                hidden_vids.difference_update(
                    int(source_vid_attr.data[vertex_index].value)
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


def _sync_scene(scene: bpy.types.Scene) -> None:
    source = scene.dan_form_source
    controller = scene.dan_form_controller
    if source is not None and controller is not None:
        try:
            _sync_proxy(source, controller)
        except (KeyError, ValueError):
            pass


def _depsgraph_update_post(scene: bpy.types.Scene, depsgraph: bpy.types.Depsgraph) -> None:
    global _SYNC_GUARD
    if _SYNC_GUARD:
        return
    for current_scene in bpy.data.scenes:
        source = getattr(current_scene, "dan_form_source", None)
        controller = getattr(current_scene, "dan_form_controller", None)
        if source is None or controller is None:
            continue
        _SYNC_GUARD = True
        try:
            try:
                _sync_proxy(source, controller)
            except (KeyError, ValueError):
                # A stale topology is reported by the next explicit command;
                # the depsgraph callback must never escape into Blender.
                pass
        finally:
            _SYNC_GUARD = False


class DANFORM_OT_initialize(bpy.types.Operator):
    bl_idname = "dan_form.initialize"
    bl_label = "Initialize DAN Form"
    bl_description = "Bind the selected mesh as a DAN Form Source and create its controller"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        source = context.scene.dan_form_source
        return source is not None and source.type == "MESH"

    def execute(self, context: bpy.types.Context) -> set[str]:
        scene = context.scene
        source = scene.dan_form_source
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
            scene.dan_form_controller = controller
            scene.dan_form_status = f"Ready: {source.name} / {controller.name}"
            _select_only(context, controller)
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
        source = context.scene.dan_form_source
        controller = context.scene.dan_form_controller
        try:
            if not _is_valid_source(source) or controller is None:
                raise ValueError("SOURCE_OR_CONTROLLER_MISSING")
            _ensure_source_ids(source)
            _sync_proxy(source, controller)
            context.scene.dan_form_status = f"Synced: {controller.name}"
            return {"FINISHED"}
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class DANFORM_OT_create_control(bpy.types.Operator):
    bl_idname = "dan_form.create_control"
    bl_label = "Make Control from Source Selection"
    bl_description = "Create a Source-backed control from selected Source vertices and edges"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        source = context.scene.dan_form_source
        return source is not None and context.view_layer.objects.active == source and source.mode == "EDIT"

    def execute(self, context: bpy.types.Context) -> set[str]:
        source = context.scene.dan_form_source
        scene = context.scene
        try:
            _ensure_source_ids(source)
            vertex_ids, edge_ids = _source_selection(source)
            controls = _controls(source)
            identity = (sorted(vertex_ids), sorted(edge_ids))
            if any((sorted(item.get("vertex_ids", [])), sorted(item.get("edge_ids", []))) == identity for item in controls):
                raise ValueError("CONTROL_ALREADY_EXISTS")
            if source.mode == "EDIT":
                bpy.ops.object.mode_set(mode="OBJECT")
            controls.append({
                "control_uuid": uuid.uuid4().hex,
                "name": f"Control {len(controls) + 1}",
                "vertex_ids": sorted(vertex_ids),
                "edge_ids": sorted(edge_ids),
            })
            _json_set(source, CONTROLS_KEY, controls)
            _update_revision(source)
            controller = _find_controller(source)
            if controller is None:
                raise ValueError("CONTROLLER_MISSING")
            _rebuild_proxy(source, controller)
            _sync_proxy(source, controller)
            scene.dan_form_controller = controller
            scene.dan_form_status = f"Created {controls[-1]['name']} ({len(vertex_ids)}V/{len(edge_ids)}E)"
            _select_only(context, controller)
            self.report({"INFO"}, scene.dan_form_status)
            return {"FINISHED"}
        except ValueError as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}


class DANFORM_OT_hide_selected(bpy.types.Operator):
    bl_idname = "dan_form.hide_selected"
    bl_label = "Hide Selected Control"
    bl_description = "Release selected proxy vertices or edges from control constraints"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context: bpy.types.Context) -> bool:
        controller = context.scene.dan_form_controller
        return controller is not None and context.view_layer.objects.active == controller and controller.mode == "EDIT"

    def execute(self, context: bpy.types.Context) -> set[str]:
        source = context.scene.dan_form_source
        controller = context.scene.dan_form_controller
        try:
            vertex_ids, edge_ids = _proxy_selection(controller)
            if controller.mode == "EDIT":
                bpy.ops.object.mode_set(mode="OBJECT")
            changed = _mutate_masks(source, vertex_ids, edge_ids, reveal=False)
            if changed:
                _rebuild_proxy(source, controller)
                context.scene.dan_form_status = f"Hidden {len(vertex_ids)}V/{len(edge_ids)}E"
            else:
                context.scene.dan_form_status = "No visibility change"
            _select_only(context, controller)
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
        source = context.scene.dan_form_source
        controller = context.scene.dan_form_controller
        try:
            payload = json.loads(self.ids_json) if self.ids_json else {}
            vertex_ids = {int(item) for item in payload.get("vertex_ids", [])}
            edge_ids = {int(item) for item in payload.get("edge_ids", [])}
            changed = _mutate_masks(source, vertex_ids, edge_ids, reveal=True)
            if controller is not None and controller.mode == "EDIT":
                bpy.ops.object.mode_set(mode="OBJECT")
            if changed:
                _rebuild_proxy(source, controller)
            context.scene.dan_form_status = "Revealed all" if not vertex_ids and not edge_ids else "Revealed selection"
            _select_only(context, controller)
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
        return context.scene.dan_form_controller is not None

    def execute(self, context: bpy.types.Context) -> set[str]:
        scene = context.scene
        controller = scene.dan_form_controller
        source = scene.dan_form_source
        if controller is None or controller.name not in bpy.data.objects:
            scene.dan_form_controller = None
            scene.dan_form_status = "No controller"
            return {"CANCELLED"}
        bpy.data.objects.remove(controller, do_unlink=True)
        scene.dan_form_controller = None
        scene.dan_form_status = f"Source ready: {source.name}" if source else "No controller"
        self.report({"INFO"}, "Controller removed; Source definitions preserved")
        return {"FINISHED"}


class DANFORM_PT_sidebar(bpy.types.Panel):
    bl_label = "DAN Form"
    bl_idname = "DANFORM_PT_sidebar"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "DAN Form"

    def draw(self, context: bpy.types.Context) -> None:
        layout = self.layout
        scene = context.scene
        source = scene.dan_form_source
        controls = _controls(source) if source else []
        layout.prop(scene, "dan_form_source", text="Source")
        layout.operator(DANFORM_OT_initialize.bl_idname, icon="OUTLINER_OB_MESH")
        layout.operator(DANFORM_OT_sync.bl_idname, icon="FILE_REFRESH")
        row = layout.row()
        row.enabled = source is not None and source == context.view_layer.objects.active and source.mode == "EDIT"
        row.operator(DANFORM_OT_create_control.bl_idname, icon="MESH_DATA")
        row = layout.row()
        row.enabled = scene.dan_form_controller is not None and scene.dan_form_controller == context.view_layer.objects.active and scene.dan_form_controller.mode == "EDIT"
        row.operator(DANFORM_OT_hide_selected.bl_idname, icon="HIDE_ON")
        row = layout.row()
        row.enabled = scene.dan_form_controller is not None
        row.operator(DANFORM_OT_reveal.bl_idname, icon="HIDE_OFF", text="Reveal All")
        row = layout.row()
        row.enabled = scene.dan_form_controller is not None
        row.operator(DANFORM_OT_remove_controller.bl_idname, icon="TRASH")
        layout.separator()
        layout.label(text=scene.dan_form_status or "Select a mesh Source")
        layout.label(text=f"Controls: {len(controls)}")
        if scene.dan_form_controller is not None:
            layout.label(text=f"Proxy: {scene.dan_form_controller.name}")
            layout.label(text="Phase 2: Source-backed wires")


CLASSES = (
    DANFORM_OT_initialize,
    DANFORM_OT_sync,
    DANFORM_OT_create_control,
    DANFORM_OT_hide_selected,
    DANFORM_OT_reveal,
    DANFORM_OT_remove_controller,
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
    if _depsgraph_update_post not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_depsgraph_update_post)


def unregister() -> None:
    if _depsgraph_update_post in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_depsgraph_update_post)
    for prop in ("dan_form_status", "dan_form_controller", "dan_form_source"):
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)
    for cls in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(cls)
        except RuntimeError:
            pass


if __name__ == "__main__":
    register()
