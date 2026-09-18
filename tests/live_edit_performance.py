"""MCP-only cache/invalidation regression in the already-open Blender scene."""
import sys
from types import SimpleNamespace

import bmesh
import bpy


def run():
    addon = sys.modules['bl_ext.user_default.dan_form']
    ctx = bpy.context
    original = ctx.view_layer.objects.active
    if original is not None and original.mode != 'OBJECT':
        raise RuntimeError('Run in Object Mode without interrupting a modal edit')
    selected = list(ctx.selected_objects)
    scene_source, scene_controller = ctx.scene.dan_form_source, ctx.scene.dan_form_controller
    status = ctx.scene.dan_form_status
    select_mode = tuple(ctx.tool_settings.mesh_select_mode)
    xray, width, show_hidden = ctx.scene.dan_form_overlay_xray, ctx.scene.dan_form_overlay_width, ctx.scene.dan_form_overlay_hidden
    report = {'file': bpy.data.filepath, 'dirty_before': bpy.data.is_dirty, 'checks': []}
    mesh = bpy.data.meshes.new('DANP_EDIT_CACHE_TEST')
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)], [], [(0, 1, 2, 3)])
    model = bpy.data.objects.new('DANP_EDIT_CACHE_TEST', mesh)
    ctx.scene.collection.objects.link(model)
    controller = None

    def check(condition, name):
        if not condition:
            raise AssertionError(name)
        report['checks'].append(name)

    def geometry(mode='source'):
        return addon._overlay_geometry(ctx, mode, model, controller)

    def batches(mode='source'):
        return addon._overlay_batches(ctx, mode, model, controller)[1]

    def choose(uuid):
        ctx.scene.dan_form_selected_control = uuid
        addon._activate_ui_control(ctx.scene, uuid)

    try:
        addon._select_only(ctx, model)
        check(bpy.ops.dan_form.initialize() == {'FINISHED'}, 'fixture Init')
        controller = addon._find_controller(model)
        bpy.ops.object.mode_set(mode='EDIT')
        ctx.tool_settings.mesh_select_mode = (False, True, False)
        bpy.ops.mesh.select_all(action='SELECT')
        check(bpy.ops.dan_form.create_control() == {'FINISHED'}, 'Source Edit creates edge control')
        edge_control = addon._controls(model)[0]
        check(tuple(map(len, addon._effective_proxy_elements(model))) == (4, 4), 'network union includes mapped loop')
        original_reader = addon._source_vid
        addon._source_vid = lambda *_: (_ for _ in ()).throw(AssertionError('per-vertex Source ID read'))
        try:
            addon._control_effective(model, edge_control)
            addon._control_intent(model, edge_control)
            data = geometry()
            check(len(data['edges']) == 8, 'Edit overlay uses bulk ID connectivity')
        finally:
            addon._source_vid = original_reader
        check(not data['points'] and not data['selected_points'], 'edge endpoints do not create dense auxiliary dots')
        cached = batches()
        check(batches() is cached and batches() is cached, 'idle redraw retains GPU buffers')
        original_builder = addon._overlay_geometry
        addon._overlay_geometry = lambda *_: (_ for _ in ()).throw(AssertionError('idle geometry rebuild'))
        try:
            check(batches() is cached, 'idle redraw never rereads mesh geometry')
        finally:
            addon._overlay_geometry = original_builder

        bm = bmesh.from_edit_mesh(mesh)
        vl = bm.verts.layers.int[addon.VID_ATTR]
        vertex = next(iter(bm.verts))
        vid, original_co = vertex[vl], vertex.co.copy()
        vertex.co.x += 0.125
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        ctx.view_layer.update()
        check(batches() is not cached, 'Source geometry event invalidates GPU buffers')
        changed_world = model.matrix_world @ vertex.co
        check(any((p - changed_world).length < 1e-7 for p in geometry()['edges']), 'Source Edit overlay follows current BMesh positions')
        check(any(v[0] == vid and abs(v[1][0] - vertex.co.x) < 1e-7 for v in addon._proxy_state(controller)[0]), 'Source Edit event still syncs proxy')
        vertex.co = original_co
        bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)
        ctx.view_layer.update()
        check(any((p - model.matrix_world @ original_co).length < 1e-7 for p in geometry()['edges']), 'restoring Source pose refreshes overlay')

        for face in bm.faces:
            face.select = False
        addon._select_source_ids(model, {vid}, set())
        check(bpy.ops.dan_form.create_control() == {'FINISHED'}, 'explicit point definition')
        point_control = addon._controls(model)[-1]
        choose(point_control['control_uuid'])
        data = geometry()
        check(len(data['points']) == 1 and len(data['selected_points']) == 1, 'explicit shared point keeps its visible highlight')
        point_batches = batches()
        choose(edge_control['control_uuid'])
        check(batches() is not point_batches and not geometry()['selected_points'], 'row highlight invalidates only its cached display')
        style_batches = batches()
        ctx.scene.dan_form_overlay_width = width + 1
        ctx.scene.dan_form_overlay_xray = not xray
        check(batches() is style_batches, 'line width and X-Ray reuse position buffers')

        check(bpy.ops.dan_form.set_control_visibility(control_uuid=point_control['control_uuid'], reveal=False) == {'FINISHED'}, 'hide shared point')
        hidden_data = geometry()
        check(len(hidden_data['edges']) == 4 and not hidden_data['points'], 'canonical node mask changes visible network')
        hidden_batches = batches()
        ctx.scene.dan_form_overlay_hidden = True
        check(len(geometry()['edges']) == 8 and batches() is not hidden_batches, 'Show Hidden refreshes display without changing masks')
        check(vid in addon._hidden(model, addon.HIDDEN_VIDS_KEY), 'display toggle preserves canonical mask')
        ctx.scene.dan_form_overlay_hidden = False
        check(bpy.ops.dan_form.set_control_visibility(control_uuid=point_control['control_uuid'], reveal=True) == {'FINISHED'}, 'reveal shared point')
        check(len(geometry()['edges']) == 8 and len(geometry()['points']) == 1, 'Reveal updates network cache')

        bpy.ops.object.mode_set(mode='OBJECT')
        cached = batches()
        previous_x = geometry()['edges'][0].x
        model.location.x += 0.25
        ctx.view_layer.update()
        check(batches() is not cached and abs(geometry()['edges'][0].x - previous_x - 0.25) < 1e-7, 'Source object transform updates world-space overlay')
        addon._select_only(ctx, controller)
        controller_batches = batches('controller')
        controller.data.vertices[0].co.x += 0.2
        controller.data.update()
        ctx.view_layer.update()
        check(batches('controller') is not controller_batches, 'controller Object geometry event invalidates buffers')
        changed = controller.matrix_world @ controller.data.vertices[0].co
        check(any((p - changed).length < 1e-7 for p in geometry('controller')['edges']), 'controller Object overlay reads proxy pose directly')
        check(tuple(mesh.vertices[0].co) == tuple(original_co), 'controller pose does not deform Source in Phase 2')
        bpy.ops.object.mode_set(mode='EDIT')
        check(addon._overlay_mode(ctx) == 'controller_edit', 'controller Edit enables live control highlight')
        edit_bm = bmesh.from_edit_mesh(controller.data)
        for vertex in edit_bm.verts:
            vertex.select = False
        for edge in edit_bm.edges:
            edge.select = False
        bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=False)
        edit_batches = batches('controller_edit')
        edit_geometry = geometry('controller_edit')
        edit_eid_layer = edit_bm.edges.layers.int.get(addon.PROXY_EID_ATTR)
        selected_edit_edges = {int(edge[edit_eid_layer]) for edge in edit_bm.edges if edge.select}
        effective_edge_count = len(addon._effective_proxy_elements(model)[1])
        check(len(edit_geometry['edges']) == 2 * (effective_edge_count - len(selected_edit_edges)) and not edit_geometry['selected_edges'], 'controller Edit cyan base excludes native selected edges')
        check(len(edit_geometry['edges']) + 2 * len(selected_edit_edges) == 2 * effective_edge_count, 'controller Edit cyan plus native selection covers every proxy edge')
        check(batches('controller_edit') is edit_batches, 'controller Edit idle redraw retains GPU buffers')
        bm = bmesh.from_edit_mesh(controller.data)
        proxy_layer = bm.verts.layers.int.get(addon.PROXY_VID_ATTR)
        live_vertex = next(vertex for vertex in bm.verts if int(vertex[proxy_layer]) == vid)
        live_vertex.co.x += 0.15
        bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=False)
        ctx.view_layer.update()
        refreshed_edit_batches = batches('controller_edit')
        refreshed_edit_geometry = geometry('controller_edit')
        check(refreshed_edit_batches is not edit_batches, 'controller Edit coordinate event invalidates buffers')
        expected_live = controller.matrix_world @ live_vertex.co
        check(any((point - expected_live).length < 1e-7 for point in refreshed_edit_geometry['edges']), 'controller Edit highlight reads live BMesh coordinates')
        ctx.tool_settings.mesh_select_mode = (False, True, False)
        for edge in bm.edges:
            edge.select = False
        bm.edges[0].select = True
        bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=False)
        check(not geometry('controller_edit')['selected_edges'], 'native selection is not painted over by overlay')
        addon._draw_control_overlay()
        check(True, 'controller Edit draw path completes with live overlay')
        for edge in bm.edges:
            edge.select = False
        bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=False)
        visible_before_hide = len(geometry('controller_edit')['edges'])
        bm = bmesh.from_edit_mesh(controller.data)
        bm.edges[0].select = True
        bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=False)
        check(bpy.ops.dan_form.hide_selected() == {'FINISHED'}, 'controller Edit Hide updates canonical mask')
        hidden_controller_geometry = geometry('controller_edit')
        check(len(hidden_controller_geometry['edges']) < visible_before_hide, f"Controller Edit highlight removes hidden edges ({visible_before_hide}->{len(hidden_controller_geometry['edges'])}, masks={len(addon._hidden(model, addon.HIDDEN_EIDS_KEY))}/{len(addon._hidden(model, addon.HIDDEN_VIDS_KEY))})")
        check(bpy.ops.dan_form.reveal() == {'FINISHED'}, 'controller Edit Reveal restores current Source positions')
        restored_controller_geometry = geometry('controller_edit')
        restored_bm = bmesh.from_edit_mesh(controller.data)
        restored_layer = restored_bm.edges.layers.int.get(addon.PROXY_EID_ATTR)
        restored_selected = sum(1 for edge in restored_bm.edges if edge.select and restored_layer is not None)
        check(len(restored_controller_geometry['edges']) + 2 * restored_selected == visible_before_hide, f"Controller Edit highlight restores revealed edges ({visible_before_hide}->{len(restored_controller_geometry['edges'])}+{restored_selected} native)")
        old_mapping = addon._MAPPING_CACHE.get(model.as_pointer())
        addon._refresh_runtime()
        check(not addon._OVERLAY_CACHE and addon._MAPPING_CACHE.get(model.as_pointer()) is not old_mapping, 'runtime refresh drops overlay and stale topology mapping')
        report['status'] = 'PASS'
    finally:
        if ctx.object is not None and ctx.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        if controller is not None and controller.name in bpy.data.objects:
            proxy_mesh = controller.data
            addon._PROXY_SNAPSHOTS.pop(controller.as_pointer(), None)
            bpy.data.objects.remove(controller, do_unlink=True)
            if proxy_mesh.users == 0:
                bpy.data.meshes.remove(proxy_mesh)
        addon._MAPPING_CACHE.pop(model.as_pointer(), None)
        addon._NETWORK_CACHE.pop(model.as_pointer(), None)
        bpy.data.objects.remove(model, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        addon._OVERLAY_CACHE.clear()
        for obj in ctx.selected_objects:
            obj.select_set(False)
        for obj in selected:
            obj.select_set(True)
        ctx.view_layer.objects.active = original
        ctx.tool_settings.mesh_select_mode = select_mode
        ctx.scene.dan_form_overlay_xray, ctx.scene.dan_form_overlay_width, ctx.scene.dan_form_overlay_hidden = xray, width, show_hidden
        ctx.scene.dan_form_source, ctx.scene.dan_form_controller = scene_source, scene_controller
        addon._sync_context_ui_list(ctx)
        ctx.scene.dan_form_status = status
        report['restored_active'] = original.name if original else None
        report['dirty_after'] = bpy.data.is_dirty
        report['fixture_removed'] = not any(o.name.startswith('DANP_EDIT_CACHE_TEST') for o in bpy.data.objects)
    return report


result = run()
