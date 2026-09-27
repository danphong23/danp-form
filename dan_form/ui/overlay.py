"""Viewport overlay drawing and display-only patch visualization."""

from __future__ import annotations

import logging

import bmesh
import bpy

from ..constants import *

_LOGGER = logging.getLogger(__name__)
_DRAW_ERROR_REPORTED = False


def bind(api) -> None:
    for name in dir(api):
        if name.startswith("__"):
            continue
        if name in {"_register_overlay", "_unregister_overlay"}:
            continue
        if name.startswith("_") or name.startswith("DANFORM_") or name in {"OVERLAY_HANDLE"}:
            globals()[name] = getattr(api, name)


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


def _source_display_geometry(context, source, edge_ids, vertex_ids):
    """Resolve Source IDs to the exact visible edge chain.

    Identity and editing remain on the base BMesh.  When a viewport modifier
    is enabled, Blender draws the cage/evaluated edge rather than the raw base
    coordinates; use only the evaluated segments carrying the same persistent
    ``dan_form_eid`` for display.  This keeps the control on the edge Blender
    shows without allowing evaluated topology to redefine the control.
    """
    source_vertices = _source_vertices(source)
    vid_indices, _ = _source_id_maps(source)
    base_positions = {
        int(vid): source.matrix_world @ source_vertices[index].co
        for vid, index in vid_indices.items()
    }
    source_edges = _source_edge_vids(source)
    edge_segments = {}
    point_positions = {}
    wanted_edges = {int(edge_id) for edge_id in edge_ids}
    wanted_vertices = {int(vertex_id) for vertex_id in vertex_ids}
    # In Source Edit Mode the cage toggle is the contract for what Blender
    # actually exposes to the user.  A modifier may be enabled in the
    # viewport/edit stack while ``show_on_cage`` is off; in that state the
    # native editable edge is the base mesh and the overlay must stay there.
    # ``show_on_cage`` is deliberately a display decision only: persistent
    # control membership and IDs remain on the base topology.
    display_modifiers = [modifier for modifier in source.modifiers
                         if modifier.show_viewport and modifier.show_in_editmode
                         and modifier.show_on_cage]
    if display_modifiers:
        depsgraph = context.evaluated_depsgraph_get()
        evaluated = source.evaluated_get(depsgraph)
        mesh = evaluated.to_mesh(preserve_all_data_layers=True, depsgraph=depsgraph)
        try:
            eid_attr = mesh.attributes.get(EID_ATTR)
            vid_attr = mesh.attributes.get(VID_ATTR)
            if eid_attr is not None:
                for edge, item in zip(mesh.edges, eid_attr.data):
                    edge_id = int(item.value)
                    if edge_id not in wanted_edges:
                        continue
                    if edge.vertices[0] >= len(mesh.vertices) or edge.vertices[1] >= len(mesh.vertices):
                        continue
                    edge_segments.setdefault(edge_id, []).append((
                        source.matrix_world @ mesh.vertices[edge.vertices[0]].co,
                        source.matrix_world @ mesh.vertices[edge.vertices[1]].co,
                    ))
            if vid_attr is not None:
                candidates = {}
                for vertex, item in zip(mesh.vertices, vid_attr.data):
                    vertex_id = int(item.value)
                    if vertex_id in wanted_vertices:
                        candidates.setdefault(vertex_id, []).append(source.matrix_world @ vertex.co)
                for vertex_id in wanted_vertices:
                    options = candidates.get(vertex_id, ())
                    if options and vertex_id in base_positions:
                        point_positions[vertex_id] = min(
                            options,
                            key=lambda position: (position - base_positions[vertex_id]).length_squared,
                        )
        finally:
            evaluated.to_mesh_clear()

    # Unsupported modifiers, missing attributes, or a stale evaluated mesh
    # fall back per element to the exact Source edge/vertex rather than a
    # nearest-neighbor guess.
    for edge_id in wanted_edges:
        if edge_id in edge_segments:
            continue
        endpoints = source_edges.get(edge_id)
        if endpoints and all(vertex_id in base_positions for vertex_id in endpoints):
            edge_segments[edge_id] = [(base_positions[endpoints[0]], base_positions[endpoints[1]])]
    for vertex_id in wanted_vertices:
        point_positions.setdefault(vertex_id, base_positions.get(vertex_id))
    return edge_segments, {vertex_id: position for vertex_id, position in point_positions.items() if position is not None}


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
        _edge_ids, explicit_nodes = _control_intent(source, control)
        if not bool(control.get("enabled", True)):
            continue
        hidden_nodes = {
            int(value) for value in control.get("hidden_vertex_ids", [])
        }
        if scene.dan_form_overlay_hidden:
            point_ids.update(explicit_nodes)
        else:
            point_ids.update(explicit_nodes - hidden_nodes)
    selected_point_ids = set()
    if selected_control and bool(selected_control.get("enabled", True)):
        selected_point_ids = _control_intent(source, selected_control)[1] - {
            int(value) for value in selected_control.get("hidden_vertex_ids", [])
        }
    source_edge_segments = None
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
        display_vertices = set(vertex_ids) | point_ids
        source_edge_segments, positions = _source_display_geometry(context, source, edge_ids, display_vertices)
        edges = _source_edge_vids(source)
        native_selected_edges = set()
        native_selected_vertices = set()
    # In Controller Edit, native Blender selection must remain the top visual
    # authority.  Do not draw an orange duplicate over its selected wires.
    # In either Edit Mode Blender's native orange selection is authoritative.
    # The sidebar row remains the semantic active definition for Sync/Delete,
    # but it must not keep painting an old control as selected after the user
    # clicks another edge or clicks empty space to deselect.
    native_edit_selection = (
        overlay_mode == "controller_edit"
        or (overlay_mode == "source" and source.mode == "EDIT")
    )
    selected_edges_for_overlay = set() if native_edit_selection else selected_edges
    selected_points_for_overlay = set() if native_edit_selection else selected_point_ids & selected_vertices
    enabled_edges_for_overlay = (
        [edge_id for edge_id in edge_ids if edge_id not in native_selected_edges]
        if overlay_mode == "controller_edit" else edge_ids
    )
    point_ids_for_overlay = (
        point_ids - native_selected_vertices
        if overlay_mode == "controller_edit" else point_ids
    )
    if overlay_mode == "source" and source_edge_segments is not None:
        def flatten_segments(ids):
            return [position for edge_id in ids for segment in source_edge_segments.get(edge_id, ()) for position in segment]

        return {
            "edges": flatten_segments(enabled_edges_for_overlay),
            "selected_edges": flatten_segments(selected_edges_for_overlay),
            "points": [positions[vid] for vid in point_ids_for_overlay if vid in positions],
            "selected_points": [positions[vid] for vid in selected_points_for_overlay if vid in positions],
        }

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
    mapping_token = (source.data.as_pointer(), source.get(TOPOLOGY_KEY, ""),
                     len(source.data.vertices), len(source.data.edges), len(source.data.polygons))
    partition = _patch_partition(source)
    token = (mapping_token, tuple(source.matrix_world), tuple(
        (patch["patch_id"], tuple(patch["face_indices"])) for patch in partition["patches"]
    ))
    cached = _PATCH_OVERLAY_CACHE.get(source.as_pointer())
    if cached is not None and cached[0] == token:
        return cached[1], cached[2]
    faces = _source_face_records(source)
    vertices_by_id, _ = _source_id_maps(source)
    source_vertices = _source_vertices(source)
    shader = gpu.shader.from_builtin("UNIFORM_COLOR")
    # Group patches by palette color. Drawing one batch per patch made a
    # character with 100+ patches stall mode changes even though the geometry
    # was already cached. Patch identity remains in the partition/lookup API;
    # only the GPU submission is grouped.
    grouped_positions: dict[int, list] = {}
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
            grouped_positions.setdefault(patch_index % len(_PATCH_COLORS), []).extend(positions)
    batches = [
        (f"palette:{palette_index}", batch_for_shader(shader, "TRIS", {"pos": positions}),
         _PATCH_COLORS[palette_index])
        for palette_index, positions in sorted(grouped_positions.items())
    ]
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
    modifier_token = tuple((modifier.name, modifier.type, modifier.show_viewport,
                            modifier.show_in_editmode, modifier.show_on_cage)
                           for modifier in source.modifiers)
    token = (context.window.as_pointer() if context.window else 0,
             source.as_pointer(), source.data.as_pointer(), source.mode,
             controller.as_pointer(), controller.data.as_pointer(), controller.mode,
             controller.get(PROXY_GENERATION_KEY), overlay_mode,
             source.get(CONTROLS_KEY), source.get(HIDDEN_VIDS_KEY), source.get(HIDDEN_EIDS_KEY),
             scene.dan_form_selected_control, scene.dan_form_overlay_hidden, selection_token,
             tuple(tuple(row) for row in source.matrix_world),
             tuple(tuple(row) for row in controller.matrix_world),
             modifier_token)
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
    global _DRAW_ERROR_REPORTED
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
        finally:
            # Do not leak custom line/depth state into another draw callback.
            gpu.state.depth_test_set(previous_depth)
            gpu.state.line_width_set(previous_width)
            gpu.state.point_size_set(1.0)
            gpu.state.blend_set(previous_blend)
        _DRAW_ERROR_REPORTED = False
    except Exception:
        # Drawing must never break Blender's viewport.  Drop stale batches so
        # a failed evaluated-mesh read cannot leave an old line floating away
        # from the Source until an unrelated redraw happens. Report once per
        # consecutive failure streak: viewport draw callbacks can run many
        # times per second, so logging every frame would flood Blender's console.
        _OVERLAY_CACHE.clear()
        if not _DRAW_ERROR_REPORTED:
            _LOGGER.exception(
                "DANP Form viewport overlay draw failed; cached overlay was cleared. "
                "The viewport remains usable, but the overlay may be unavailable."
            )
            _DRAW_ERROR_REPORTED = True
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



__all__ = [
    "bind", "_tag_viewport_redraw", "_overlay_source", "_overlay_mode",
    "_overlay_geometry", "_PATCH_COLORS", "_patch_overlay_batches", "_overlay_batches",
    "_update_overlay_display", "_draw_control_overlay", "_register_overlay", "_unregister_overlay",
]
