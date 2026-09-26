"""Historical 0.2.5 fixture; do not run against the current add-on.

The custom picker and its Scene properties are no longer registered. Retained
only to explain the historical reports; excluded from run_release_gates.py.

Behavior regressions for native Blender input and DANP hover picking.

Run only in the already-open Blender, from Object Mode. All mutations use an
owned fixture; selection, view, display options and user context are restored.
"""
import math
import sys
from types import SimpleNamespace, MethodType

import bmesh
import bpy
from mathutils import Quaternion, Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d


def _addon_module():
    candidates = [module for name, module in sys.modules.items()
                  if (name == "dan_form" or name.endswith(".dan_form"))
                  and hasattr(module, "_context_source")]
    if len(candidates) != 1:
        raise RuntimeError("DANP Form module is not uniquely loaded")
    return candidates[0]


def run():
    a = _addon_module()
    ctx = bpy.context
    original = ctx.object
    if original and original.mode != 'OBJECT':
        raise RuntimeError('Run from Object Mode')
    selected = list(ctx.selected_objects)
    scene = ctx.scene
    ui = (scene.dan_form_source, scene.dan_form_controller,
          scene.dan_form_selected_control, scene.dan_form_status)
    options = (scene.dan_form_overlay_xray, scene.dan_form_add_to_selection,
               tuple(ctx.tool_settings.mesh_select_mode))
    area = next(x for x in ctx.screen.areas if x.type == 'VIEW_3D')
    region = next(x for x in area.regions if x.type == 'WINDOW')
    rv = area.spaces.active.region_3d
    view = (rv.view_rotation.copy(), rv.view_location.copy(), rv.view_distance, rv.view_perspective)
    shading = area.spaces.active.shading
    shade = (shading.type, shading.show_xray)
    checks = []
    model = controller = None
    mesh = bpy.data.meshes.new('DANP_PICK_UX_TEST')
    mesh.from_pydata([(-1,-1,-1),(1,-1,-1),(1,1,-1),(-1,1,-1),
                      (-1,-1,1),(1,-1,1),(1,1,1),(-1,1,1)], [],
                     [(0,1,2,3),(4,7,6,5),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)])

    def check(ok, name):
        if not ok:
            raise AssertionError(name)
        checks.append(name)

    def picker(tool='SEGMENT', add=False):
        fake = SimpleNamespace(tool=tool, add_to_selection=add,
            _session=a._runtime.PICK_SESSION, _controller=controller.as_pointer(),
            _generation=controller.get(a.PROXY_GENERATION_KEY), _area=area,
            _committed=False, _navigating=False, _last_target=None, _last_edge_id=None)
        for name in ('_finish', '_in_viewport', '_preview', 'modal'):
            setattr(fake, name, MethodType(getattr(a.DANFORM_OT_pick_selection_tool, name), fake))
        return fake

    def event(edge_id, kind='MOUSEMOVE', shift=False, ctrl=False):
        bm = bmesh.from_edit_mesh(controller.data)
        el = bm.edges.layers.int[a.PROXY_EID_ATTR]
        edge = next(e for e in bm.edges if int(e[el]) == edge_id)
        point = controller.matrix_world @ ((edge.verts[0].co + edge.verts[1].co) / 2)
        p = location_3d_to_region_2d(region, rv, point)
        # Deliberately incorrect sidebar-relative values reproduce the old bug.
        return SimpleNamespace(type=kind, value='PRESS', shift=shift, ctrl=ctrl,
            mouse_x=p.x+region.x, mouse_y=p.y+region.y,
            mouse_region_x=-200, mouse_region_y=-200)

    try:
        model = bpy.data.objects.new('DANP_PICK_UX_TEST', mesh)
        scene.collection.objects.link(model)
        a._select_only(ctx, model)
        bpy.ops.dan_form.initialize()
        controller = a._find_controller(model)
        bpy.ops.object.mode_set(mode='EDIT')
        ctx.tool_settings.mesh_select_mode = (False, True, False)
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.dan_form.create_control()
        definition = a._controls(model)[0]
        bpy.ops.dan_form.focus_controller()
        scene.dan_form_overlay_xray = False
        scene.dan_form_add_to_selection = False
        shading.type, shading.show_xray = 'SOLID', False
        rv.view_rotation = Quaternion((1,0,0), math.pi/2)
        rv.view_location, rv.view_distance, rv.view_perspective = Vector((0,0,0)), 8, 'ORTHO'
        rv.update()
        with ctx.temp_override(area=area, region=region):
            bm = bmesh.from_edit_mesh(controller.data)
            el = bm.edges.layers.int[a.PROXY_EID_ATTR]
            front = [int(e[el]) for e in bm.edges if all(abs(v.co.y+1)<1e-6 for v in e.verts)]
            check(len(front)==4, 'front fixture has upper/lower and both side edges')
            for eid in front:
                picked = a._view3d_pick_edge(ctx, event(eid))
                check(picked==eid, 'sidebar-started pick reaches each front boundary')
            check(a._pick_point_visible(ctx, model, Vector((0,-1,0))), 'front surface remains pickable')
            check(not a._pick_point_visible(ctx, model, Vector((0,1,0))), 'opaque Source excludes back surface')
            scene.dan_form_overlay_xray = True
            check(a._pick_point_visible(ctx, model, Vector((0,1,0))), 'X-Ray permits back surface')
            check(controller.show_in_front, 'X-Ray also exposes native proxy wire')
            scene.dan_form_overlay_xray = False
            check(not controller.show_in_front, 'X-Ray off restores native wire depth')
            shading.show_xray = True
            check(a._pick_point_visible(ctx, model, Vector((0,1,0))), 'native viewport X-Ray permits back surface')
            shading.show_xray = False

            import gpu
            bpy.ops.mesh.select_all(action='DESELECT')
            a._OVERLAY_CACHE.clear()
            prior_depth, prior_width = gpu.state.depth_test_get(), gpu.state.line_width_get()
            gpu.state.depth_test_set('NONE'); gpu.state.line_width_set(5.0)
            try:
                a._draw_control_overlay()
                check(bool(a._OVERLAY_CACHE.get('batches')) and gpu.state.depth_test_get()=='NONE', 'overlay restores prior GPU depth state')
                check(abs(gpu.state.line_width_get()-5.0)<1e-6, 'overlay restores prior GPU line width')
            finally:
                gpu.state.depth_test_set(prior_depth); gpu.state.line_width_set(prior_width)

            bpy.ops.mesh.select_all(action='DESELECT')
            initial = a._proxy_selection_snapshot(controller)
            fake = picker()
            fake._preview(ctx, event(front[0]))
            check(a._proxy_selection_snapshot(controller)==initial, 'hover preview never changes native selection')
            check(bool(a._PICK_PREVIEW.get('batch')), 'hover has a separate visual preview')
            for key in ('WHEELUPMOUSE','WHEELDOWNMOUSE','TRACKPADPAN','TRACKPADZOOM'):
                check(fake.modal(ctx, SimpleNamespace(type=key,value='PRESS'))=={'PASS_THROUGH'}, 'navigation input passes through')
            check(fake.modal(ctx, SimpleNamespace(type='MIDDLEMOUSE',value='PRESS'))=={'PASS_THROUGH'}, 'MMB starts native orbit/pan')
            check(fake.modal(ctx, event(front[0]))=={'PASS_THROUGH'} and not a._PICK_PREVIEW, 'orbit does not run hover selection')
            fake.modal(ctx, SimpleNamespace(type='MIDDLEMOUSE',value='RELEASE'))
            fake._preview(ctx, event(front[0]))
            check(fake.modal(ctx, SimpleNamespace(type='RIGHTMOUSE',value='PRESS'))=={'CANCELLED'}, 'right click cancels preview')
            check(a._proxy_selection_snapshot(controller)==initial and not a._PICK_PREVIEW, 'cancel leaves selection unchanged')
            fake = picker()
            fake._preview(ctx, event(front[0]))
            check(fake.modal(ctx, SimpleNamespace(type='ESC',value='PRESS'))=={'CANCELLED'}, 'Esc cancels preview')

            fake = picker()
            fake._preview(ctx, event(front[0]))
            result = fake.modal(ctx, SimpleNamespace(type='B',value='PRESS'))
            check(result=={'FINISHED','PASS_THROUGH'}, 'B stops hover and dispatches native Box Select')
            check(not a._PICK_PREVIEW, 'native command clears auxiliary preview')
            check(bpy.ops.view3d.select_box('EXEC_DEFAULT', wait_for_input=False,
                xmin=0,xmax=region.width,ymin=0,ymax=region.height, mode='SET')=={'FINISHED'}, 'native Box Select executes')
            check(bool(a._proxy_selection_snapshot(controller)[0]), 'Box Select selects actual controller vertices')
            bpy.ops.mesh.select_all(action='DESELECT')
            fake = picker()
            click_event = event(front[0],'LEFTMOUSE')
            click_result = fake.modal(ctx,click_event)
            check(click_result=={'FINISHED'}, 'LMB confirms without prior mousemove')
            check(a._proxy_selection_snapshot(controller)[1]=={front[0]}, 'click commits one segment')
            fake = picker(add=True)
            check(fake.modal(ctx,event(front[1],'LEFTMOUSE'))=={'RUNNING_MODAL'}, 'Add permits repeated picks')
            check(a._proxy_selection_snapshot(controller)[1]==set(front[:2]), 'Add keeps earlier segments')
            check(fake.modal(ctx,event(front[0],'LEFTMOUSE',ctrl=True))=={'RUNNING_MODAL'}, 'Ctrl removes a picked segment')
            check(a._proxy_selection_snapshot(controller)[1]=={front[1]}, 'subtract retains remaining selected edges')
            check(fake.modal(ctx,SimpleNamespace(type='ESC',value='PRESS'))=={'FINISHED'}, 'ending repeat pick keeps committed choices')
            scene.dan_form_selected_control = definition['control_uuid']
            fake = picker(tool='CONTROL')
            check(fake.modal(ctx,event(front[0],'LEFTMOUSE'))=={'FINISHED'}, 'whole-control hover pick confirms')
            check(len(a._proxy_selection_snapshot(controller)[1])==12, 'whole-control pick selects all its edges')

            bpy.ops.mesh.select_all(action='DESELECT')
            cached = a._overlay_batches(ctx,'controller_edit',model,controller)[1]
            bpy.ops.mesh.select_all(action='SELECT')
            selected_batches = a._overlay_batches(ctx,'controller_edit',model,controller)[1]
            check(selected_batches is not cached, 'native selection invalidates cyan batches')
            bpy.ops.mesh.select_all(action='DESELECT')
            deselected_batches = a._overlay_batches(ctx,'controller_edit',model,controller)[1]
            check(deselected_batches is not selected_batches and len(a._overlay_geometry(ctx,'controller_edit',model,controller)['edges'])==24,
                  'native deselection restores cyan on every edge')
            check(a._overlay_batches(ctx,'controller_edit',model,controller)[1] is deselected_batches, 'idle selection still reuses GPU batches')

            bm = bmesh.from_edit_mesh(controller.data)
            vl = bm.verts.layers.int[a.PROXY_VID_ATTR]
            moved = next(iter(bm.verts)); moved_id=int(moved[vl])
            moved.co.z += .1; expected=moved.co.copy()
            bmesh.update_edit_mesh(controller.data,loop_triangles=False,destructive=False)
            a._mutate_masks(model,set(),{front[0]},False)
            a._rebuild_proxy(model,controller)
            bm=bmesh.from_edit_mesh(controller.data); vl=bm.verts.layers.int[a.PROXY_VID_ATTR]
            check(any(int(v[vl])==moved_id and (v.co-expected).length<1e-7 for v in bm.verts), 'Hide keeps surviving controller pose')
            check(bpy.ops.dan_form.toggle_viewport_controls()=={'FINISHED'}, 'Hide All from controller Edit')
            check(bpy.ops.dan_form.toggle_viewport_controls()=={'FINISHED'}, 'Show All from empty controller Edit')
            check(a._proxy_selection_snapshot(controller)==(set(),set()), 'Show All does not select new geometry automatically')
            check(len(a._overlay_geometry(ctx,'controller_edit',model,controller)['edges'])==24, 'Show All restores cyan without clicking a row')
        return {'status':'PASS','checks':checks,'file':bpy.data.filepath}
    finally:
        a._PICK_PREVIEW.clear()
        area.header_text_set(None)
        if ctx.object and ctx.object.mode!='OBJECT': bpy.ops.object.mode_set(mode='OBJECT')
        if controller and controller.name in bpy.data.objects:
            pm=controller.data; a._PROXY_SNAPSHOTS.pop(controller.as_pointer(),None)
            bpy.data.objects.remove(controller,do_unlink=True)
            if pm.users==0: bpy.data.meshes.remove(pm)
        if model and model.name in bpy.data.objects:
            a._MAPPING_CACHE.pop(model.as_pointer(),None); a._NETWORK_CACHE.pop(model.as_pointer(),None)
            bpy.data.objects.remove(model,do_unlink=True)
        if mesh.users==0: bpy.data.meshes.remove(mesh)
        a._select_only(ctx,original) if original else None
        for obj in selected: obj.select_set(True)
        ctx.view_layer.objects.active=original
        scene.dan_form_source,scene.dan_form_controller=ui[:2]
        scene.dan_form_selected_control,scene.dan_form_status=ui[2:]
        scene.dan_form_overlay_xray,scene.dan_form_add_to_selection=options[:2]
        ctx.tool_settings.mesh_select_mode=options[2]
        rv.view_rotation,rv.view_location,rv.view_distance,rv.view_perspective=view
        rv.update()
        shading.type,shading.show_xray=shade
        a._OVERLAY_CACHE.clear(); a._sync_context_ui_list(ctx)


result = run()
