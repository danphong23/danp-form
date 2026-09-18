"""MCP-only regression in the user's open Blender, using a removable fixture."""
import sys
from types import SimpleNamespace

import bmesh
import bpy


class LayoutRecorder:
    def __init__(self, records, alert=False):
        self.records = records
        self.alert = alert

    def row(self, **kwargs):
        return LayoutRecorder(self.records, self.alert)

    column = row

    def operator(self, identifier, **kwargs):
        self.records.append((identifier, kwargs.get('text'), self.alert))
        return SimpleNamespace()

    def label(self, **kwargs):
        pass

    def separator(self):
        pass

    def menu(self, *args, **kwargs):
        pass

    def prop(self, *args, **kwargs):
        pass

    def template_list(self, *args, **kwargs):
        pass


def run():
    addon = sys.modules['bl_ext.user_default.dan_form']
    ctx = bpy.context
    original = ctx.view_layer.objects.active
    if original is not None and original.mode != 'OBJECT':
        raise RuntimeError('Run when the user is in Object Mode')
    selected = list(ctx.selected_objects)
    status = ctx.scene.dan_form_status
    scene_source = ctx.scene.dan_form_source
    scene_controller = ctx.scene.dan_form_controller
    mesh_select_mode = tuple(ctx.tool_settings.mesh_select_mode)
    report = {'file': bpy.data.filepath, 'dirty_before': bpy.data.is_dirty, 'checks': []}
    model = None
    mesh = bpy.data.meshes.new('DANP_LIFECYCLE_TEST')
    mesh.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [], [(0, 1, 2, 3)])
    coordinates = [tuple(v.co) for v in mesh.vertices]
    connectivity = [tuple(e.vertices) for e in mesh.edges]
    mesh.attributes.new('keep_attribute', 'FLOAT', 'POINT')
    model = bpy.data.objects.new('DANP_LIFECYCLE_TEST', mesh)
    ctx.scene.collection.objects.link(model)
    model['keep_property'] = 'untouched'

    def check(condition, message):
        if not condition:
            raise AssertionError(message)
        report['checks'].append(message)

    def panel_records():
        records = []
        addon.DANFORM_PT_sidebar.draw(SimpleNamespace(layout=LayoutRecorder(records)), ctx)
        return records

    def pose():
        state = addon._proxy_state(controller)
        return ({v[0]: v[1] for v in state[0]}, {e[0]: e[1] for e in state[1]}) if state else None

    try:
        addon._select_only(ctx, model)
        check(addon.DANFORM_PT_sidebar.bl_label == 'DANP Form' and addon.DANFORM_PT_sidebar.bl_category == 'DANP Form', 'DANP product and sidebar names')
        check(any(r[0] == 'dan_form.initialize' for r in panel_records()), 'unbound model shows Init')
        check(not bpy.ops.dan_form.remove.poll(), 'Remove disabled before Init')
        check(bpy.ops.dan_form.initialize() == {'FINISHED'}, 'Init model')
        controller = addon._find_controller(model)
        records = panel_records()
        check(any(r[0] == 'dan_form.initialize' for r in records), 'bound model keeps Init')
        check(any(r[0] == 'dan_form.remove' and r[2] for r in records), 'model shows red Remove DANP Form')
        original_controller = controller
        check(bpy.ops.dan_form.initialize() == {'FINISHED'} and addon._find_controller(model) == original_controller, 'repeat Init reuses controller')
        bpy.ops.object.mode_set(mode='EDIT')
        ctx.tool_settings.mesh_select_mode = (True, False, False)
        bpy.ops.mesh.select_all(action='SELECT')
        check(bpy.ops.dan_form.create_control() == {'FINISHED'}, 'Source Edit creates mapped control')
        check(any(r[0] == 'dan_form.sync_control' for r in panel_records()), 'Sync visible only in model Edit')
        check(bpy.ops.dan_form.focus_controller() == {'FINISHED'}, 'enter Controller Edit')
        records = panel_records()
        check(not any(r[0] in {'dan_form.sync_control', 'dan_form.create_control', 'dan_form.delete_control'} for r in records), 'controller panel has no Sync or plus/minus')
        menu_records = []
        addon.DANFORM_MT_control_menu.draw(SimpleNamespace(layout=LayoutRecorder(menu_records)), ctx)
        check(not any(r[0] == 'dan_form.sync_control' for r in menu_records), 'controller menu also omits Sync')
        check(bpy.ops.dan_form.topology_locked.poll(), 'topology shortcut guard scoped to Controller Edit')
        check(not bpy.ops.dan_form.remove.poll(), 'full removal belongs to model')

        # Accept a coordinate edit first. Invalid topology must preserve that
        # pose, not snap every control back to the Source or drop IDs.
        bm = bmesh.from_edit_mesh(controller.data)
        next(iter(bm.verts)).co.x += 0.125
        bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=False)
        ctx.view_layer.update()
        accepted_pose = pose()
        check(any(co[0] == 0.125 for co in accepted_pose[0].values()), 'coordinate edits remain allowed')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.duplicate()
        ctx.view_layer.update()
        check(pose() == accepted_pose, 'native Duplicate automatically restores topology and valid pose')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.delete(type='VERT')
        ctx.view_layer.update()
        check(pose() == accepted_pose, 'native Delete automatically restores vertices and edges')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.subdivide(number_cuts=1)
        ctx.view_layer.update()
        check(pose() == accepted_pose, 'native Subdivide automatically rejected')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.edge_face_add()
        ctx.view_layer.update()
        check(pose() == accepted_pose, 'native Fill face automatically rejected')

        # Counts alone are insufficient: same count with changed edge endpoints
        # must also be rejected, including direct agent/BMesh mutations.
        bm = bmesh.from_edit_mesh(controller.data)
        bm.verts.ensure_lookup_table()
        edge = next(iter(bm.edges))
        eid = edge[bm.edges.layers.int[addon.PROXY_EID_ATTR]]
        target = next((a, b) for a in bm.verts for b in bm.verts if a != b and bm.edges.get((a, b)) is None)
        bm.edges.remove(edge)
        replacement = bm.edges.new(target)
        replacement[bm.edges.layers.int[addon.PROXY_EID_ATTR]] = eid
        bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=True)
        ctx.view_layer.update()
        check(pose() == accepted_pose, 'same-count rewire rejected by IDs and connectivity')
        bm = bmesh.from_edit_mesh(controller.data)
        bm.verts.layers.int.remove(bm.verts.layers.int[addon.PROXY_VID_ATTR])
        bmesh.update_edit_mesh(controller.data, loop_triangles=False, destructive=True)
        ctx.view_layer.update()
        check(pose() == accepted_pose, 'missing mapping layer recovered')
        check(coordinates == [tuple(v.co) for v in mesh.vertices], 'controller protection never changes Source coordinates')
        check(connectivity == [tuple(e.vertices) for e in mesh.edges], 'controller protection never changes Source connectivity')
        check(bpy.context.view_layer.objects.active == controller and controller.mode == 'EDIT', 'protection retains controller Edit context')
        check(len(addon._TOPOLOGY_KEYMAPS) == 16, 'all topology shortcuts registered once')

        bpy.ops.dan_form.focus_source()
        check(model.mode == 'EDIT' and not bpy.ops.dan_form.topology_locked.poll(), 'Back restores Source Edit with native modeling available')
        # Navigation may resync Source -> proxy in Phase 2. Give the proxy a
        # valid pose in this Source context to isolate repeated Init behavior.
        controller.data.vertices[0].co.z += 0.25
        controller.data.update()
        ctx.view_layer.update()
        before_init_pose = pose()
        check(bpy.ops.dan_form.initialize() == {'FINISHED'} and pose() == before_init_pose
              and model.mode == 'EDIT', 'repeat Init preserves adjusted controller pose and Source Edit mode')
        old_controller_name = controller.name
        old_mesh_name = controller.data.name
        check(bpy.ops.dan_form.remove() == {'FINISHED'} and model.mode == 'EDIT', 'Remove from Source Edit preserves mode')
        check(old_controller_name not in bpy.data.objects and old_mesh_name not in bpy.data.meshes, 'Remove deletes controller and its unused mesh')
        bpy.ops.object.mode_set(mode='OBJECT')
        check(not any(k.startswith('dan_form_') for k in model.keys()), 'Remove clears addon binding and definitions')
        check(mesh.attributes.get(addon.VID_ATTR) is None and mesh.attributes.get(addon.EID_ATTR) is None, 'Remove clears addon ID layers')
        check(model['keep_property'] == 'untouched' and mesh.attributes.get('keep_attribute') is not None, 'Remove preserves unrelated properties and attributes')
        check(coordinates == [tuple(v.co) for v in mesh.vertices] and connectivity == [tuple(e.vertices) for e in mesh.edges], 'Remove preserves model geometry')
        check(not bpy.ops.dan_form.remove.poll(), 'Remove disabled after cleanup')
        check(bpy.ops.dan_form.initialize() == {'FINISHED'} and addon._controls(model) == [], 're-Init starts clean')
        check(bpy.ops.dan_form.remove() == {'FINISHED'}, 'Remove empty controller from Object Mode')
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.subdivide(number_cuts=1)
        ctx.view_layer.update()
        check(len(bmesh.from_edit_mesh(mesh).verts) > len(coordinates), 'ordinary model topology editing remains available')
        report['status'] = 'PASS'
    finally:
        active = ctx.view_layer.objects.active
        if active is not None and active.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        if model is not None and model.name in bpy.data.objects:
            controller = addon._find_controller(model)
            if controller is not None:
                controller_mesh = controller.data
                addon._PROXY_SNAPSHOTS.pop(controller.as_pointer(), None)
                bpy.data.objects.remove(controller, do_unlink=True)
                if controller_mesh.users == 0:
                    bpy.data.meshes.remove(controller_mesh)
            addon._MAPPING_CACHE.pop(model.as_pointer(), None)
            bpy.data.objects.remove(model, do_unlink=True)
        if mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        for obj in ctx.selected_objects:
            obj.select_set(False)
        for obj in selected:
            obj.select_set(True)
        ctx.view_layer.objects.active = original
        ctx.tool_settings.mesh_select_mode = mesh_select_mode
        ctx.scene.dan_form_source = scene_source
        ctx.scene.dan_form_controller = scene_controller
        addon._sync_context_ui_list(ctx)
        ctx.scene.dan_form_status = status
        report['restored_active'] = original.name if original else None
        report['dirty_after'] = bpy.data.is_dirty
        report['fixture_removed'] = not any(obj.name.startswith('DANP_LIFECYCLE_TEST') for obj in bpy.data.objects)
    return report


result = run()
