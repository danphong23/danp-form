"""Run through MCP in the open Blender; owned fixtures and restored UI only."""
import json
import sys
from types import SimpleNamespace
import bpy


def run():
    a = sys.modules['bl_ext.user_default.dan_form']
    ctx = bpy.context
    original = ctx.view_layer.objects.active
    if original and original.mode != 'OBJECT':
        raise RuntimeError('Run from Object Mode')
    selected = list(ctx.selected_objects)
    settings = tuple(ctx.tool_settings.mesh_select_mode)
    ui = (ctx.scene.dan_form_source, ctx.scene.dan_form_controller,
          ctx.scene.dan_form_selected_control, ctx.scene.dan_form_status)
    report = {'file': bpy.data.filepath, 'checks': []}
    mesh = bpy.data.meshes.new('DANP_SEGMENT_TEST')
    mesh.from_pydata([(-2,0,0),(-1,0,0),(0,0,0),(1,0,0),(2,0,0),
                      (0,0,1),(0,0,2),(0,0,-1),(0,0,-2),
                      (4,0,0),(5,0,0),(5,0,1),(4,0,1)],
                     [(0,1),(1,2),(2,3),(3,4),(2,5),(5,6),(2,7),(7,8),
                      (9,10),(10,11),(11,12),(12,9)], [])
    model = bpy.data.objects.new('DANP_SEGMENT_TEST', mesh)
    ctx.scene.collection.objects.link(model)
    controller = None

    def check(value, name):
        if not value:
            raise AssertionError(name)
        report['checks'].append(name)

    try:
        a._select_only(ctx, model)
        check(bpy.ops.dan_form.initialize() == {'FINISHED'}, 'fixture Init')
        controller = a._find_controller(model)
        vids = [i.value for i in mesh.attributes[a.VID_ATTR].data]
        eids = [i.value for i in mesh.attributes[a.EID_ATTR].data]
        coordinates = [tuple(v.co) for v in mesh.vertices]
        bpy.ops.object.mode_set(mode='EDIT')
        ctx.tool_settings.mesh_select_mode = (False, True, False)
        for indices in (range(4), range(4,8), range(8,12), range(12)):
            edges = {eids[i] for i in indices}
            vertices = {v for e in edges for v in a._source_edge_vids(model)[e]}
            a._select_source_ids(model, vertices, edges)
            check(bpy.ops.dan_form.create_control() == {'FINISHED'}, 'create logical edge group')
        controls = a._controls(model)
        check(tuple(map(len, a._effective_proxy_elements(model))) == (13,12), 'overlapping groups deduplicate graph')
        check(not bpy.ops.dan_form.select_segment.poll() and not bpy.ops.dan_form.reveal_controller.poll(), 'controller shortcuts do not intercept Source')
        bpy.ops.dan_form.focus_controller()
        check(len(a._CONTROL_KEYMAPS) == 7, 'seven scoped selection/visibility shortcuts')
        whole_control = controls[-1]
        check(bpy.ops.dan_form.clear_selection() == {'FINISHED'}, 'setup Clear selection')
        check(a._proxy_selection_snapshot(controller) == (set(), set()), 'setup Clear empties proxy selection')
        check(bpy.ops.dan_form.select_all_controls() == {'FINISHED'}, 'setup Select All Controls')
        all_vertices, all_edges = a._effective_proxy_elements(model)
        selected_vertices, selected_edges = a._proxy_selection_snapshot(controller)
        check(selected_vertices == set(all_vertices) and selected_edges == set(all_edges), 'setup Select All covers enabled graph')
        check(bpy.ops.dan_form.select_control_at_cursor(edge_id=eids[0]) == {'FINISHED'}, 'canonical edge selects whole control')
        check(a._proxy_selection(controller)[1] == set(whole_control['edge_ids']), 'whole-control shortcut selects every mapped edge')
        ctx.scene.dan_form_selected_control = ''
        check(bpy.ops.dan_form.select_control_at_cursor(edge_id=eids[0]) == {'CANCELLED'}, 'shared edge never guesses a control')
        ctx.scene.dan_form_selected_control = whole_control['control_uuid']
        check(a._proxy_segment(controller,eids[0]) == ({vids[0],vids[1],vids[2]},set(eids[:2])), 'span stops at shared junction')
        check(a._proxy_segment(controller,eids[2])[1] == set(eids[2:4]), 'seed chooses one branch at junction')
        check(a._proxy_segment(controller,eids[8])[1] == set(eids[8:]), 'uncut closed loop selects fully')
        from bpy_extras.view3d_utils import location_3d_to_region_2d
        area = next(area for area in ctx.screen.areas if area.type == 'VIEW_3D')
        region = next(region for region in area.regions if region.type == 'WINDOW')
        with ctx.temp_override(area=area,region=region):
            fake = SimpleNamespace(edge_id=0,extend=False,report=lambda *_: None)
            fake.execute = lambda context: a.DANFORM_OT_select_segment.execute(fake,context)
            midpoint = controller.matrix_world @ ((mesh.vertices[9].co + mesh.vertices[10].co) * 0.5)
            screen = location_3d_to_region_2d(region,ctx.region_data,midpoint)
            event = SimpleNamespace(type='LEFTMOUSE',mouse_region_x=screen.x,mouse_region_y=screen.y)
            whole_pick = SimpleNamespace(edge_id=0,report=lambda *_: None)
            whole_pick.execute = lambda context: a.DANFORM_OT_select_control_at_cursor.execute(whole_pick,context)
            check(a.DANFORM_OT_select_control_at_cursor.invoke(whole_pick,ctx,event) == {'FINISHED'}, 'viewport projection picks whole control')
            check(a._proxy_selection(controller)[1] == set(whole_control['edge_ids']), 'projected whole-control pick selects all mapped edges')
            check(a.DANFORM_OT_select_segment.invoke(fake,ctx,event) == {'FINISHED'}, 'viewport projection pick executes span')
            check(fake.edge_id == eids[8], 'projected midpoint resolves canonical edge ID')
            check(a._proxy_selection(controller)[1] == set(eids[8:]), 'projected loop pick selects complete loop')
        check(bpy.ops.dan_form.select_segment(edge_id=eids[0]) == {'FINISHED'}, 'canonical edge-ID span operator')
        check(a._proxy_selection(controller)[1] == set(eids[:2]), 'span replaces selection')
        bpy.ops.dan_form.select_segment(edge_id=eids[2],extend=True)
        check(a._proxy_selection(controller)[1] == set(eids[:4]), 'Shift span adds selection')
        bpy.ops.dan_form.select_segment(edge_id=eids[0])
        check(bpy.ops.dan_form.hide_selected() == {'FINISHED'} and controller.mode == 'EDIT', 'edge span Hide preserves Edit Mode')
        check(not a._hidden(model,a.HIDDEN_VIDS_KEY), 'edge endpoints do not become hidden nodes')
        check(set(eids[4:8]).issubset(a._effective_proxy_elements(model)[1]), 'perpendicular control retains shared junction')
        check(a._control_state(model,controls[0])[0] == 'Partial', 'partial line reports Partial eye')
        check(a._proxy_segment(controller,eids[2])[1] == set(eids[2:4]), 'selection follows effective visible graph')
        check(bpy.ops.dan_form.reveal(ids_json=json.dumps({'edge_ids':eids[:2]})) == {'FINISHED'}, 'selective edge reveal')
        check(all(a._control_state(model,c)[0] == 'On' for c in controls), 'selective reveal restores eyes')
        ctx.tool_settings.mesh_select_mode = (True,False,False)
        a._select_proxy_ids(controller,{vids[2]},set())
        bpy.ops.dan_form.hide_selected()
        check(vids[2] in a._hidden(model,a.HIDDEN_VIDS_KEY), 'explicit node Hide masks node')
        check(not set([eids[1],eids[2],eids[4],eids[6]]) & set(a._effective_proxy_elements(model)[1]), 'node Hide releases all incident edges')
        check(bpy.ops.dan_form.reveal_controller() == {'FINISHED'}, 'Alt-H canonical reveal operator')
        check(bpy.ops.dan_form.toggle_viewport_controls() == {'FINISHED'} and controller.mode == 'EDIT', 'Hide All stays in controller Edit')
        check(not any(a._effective_proxy_elements(model)), 'Hide All empties graph')
        check(all(a._control_state(model,c)[0] == 'Hidden' for c in controls), 'Hide All every eye Hidden')
        check(bpy.ops.dan_form.toggle_viewport_controls() == {'FINISHED'}, 'Show All in empty controller Edit')
        check(all(a._control_state(model,c)[0] == 'On' for c in controls), 'Show All every eye On')
        bpy.ops.dan_form.focus_source()
        bpy.ops.object.mode_set(mode='OBJECT')
        check(coordinates == [tuple(v.co) for v in mesh.vertices], 'visibility and selection preserve Source coordinates')
        check(controller.parent == model, 'bulk visibility preserves parenting')
        report['status'] = 'PASS'
    finally:
        if ctx.object and ctx.object.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        if controller and controller.name in bpy.data.objects:
            pm = controller.data
            a._PROXY_SNAPSHOTS.pop(controller.as_pointer(),None)
            bpy.data.objects.remove(controller,do_unlink=True)
            if pm.users == 0:
                bpy.data.meshes.remove(pm)
        a._MAPPING_CACHE.pop(model.as_pointer(),None)
        a._NETWORK_CACHE.pop(model.as_pointer(),None)
        a._RETURN_MODES.pop(model.get(a.SOURCE_UUID_KEY),None)
        bpy.data.objects.remove(model,do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        for obj in ctx.selected_objects:
            obj.select_set(False)
        for obj in selected:
            obj.select_set(True)
        ctx.view_layer.objects.active = original
        ctx.tool_settings.mesh_select_mode = settings
        ctx.scene.dan_form_source,ctx.scene.dan_form_controller = ui[:2]
        ctx.scene.dan_form_selected_control = ui[2]
        a._refresh_runtime()
        a._activate_ui_control(ctx.scene,ui[2])
        ctx.scene.dan_form_status = ui[3]
        report['fixture_removed'] = not any(o.name.startswith('DANP_SEGMENT_TEST') for o in bpy.data.objects)
    return report


result = run()
