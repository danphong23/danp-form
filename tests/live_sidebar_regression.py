"""Run only via MCP in the already-open Blender; restore the user's scene in finally."""

import statistics
import sys
import time
from types import SimpleNamespace

import bmesh
import bpy


def _addon_module():
    candidates = [module for name, module in sys.modules.items()
                  if (name == "dan_form" or name.endswith(".dan_form"))
                  and hasattr(module, "_context_source")]
    if len(candidates) != 1:
        raise RuntimeError("DANP Form module is not uniquely loaded")
    return candidates[0]


def run():
    addon = _addon_module()
    context = bpy.context
    source, controller = addon._context_source(context)
    if source is None or controller is None or not addon._controls(source):
        raise RuntimeError('Select an existing DANP Form model/controller before the live regression')
    active = context.view_layer.objects.active
    if active.mode not in {'OBJECT', 'EDIT'}:
        raise RuntimeError('Unsupported mode; do not interrupt the user workflow')
    original_mode = active.mode
    selected_objects = list(context.selected_objects)
    source_keys = (addon.CONTROLS_KEY, addon.HIDDEN_VIDS_KEY, addon.HIDDEN_EIDS_KEY,
                   addon.NETWORK_REVISION_KEY)
    snapshot = {key: source.get(key) for key in source_keys}
    proxy_generation = controller.get(addon.PROXY_GENERATION_KEY)
    viewport_hidden = controller.hide_get(view_layer=context.view_layer)
    select_mode = tuple(context.tool_settings.mesh_select_mode)
    scene = context.scene
    addon._sync_context_ui_list(context)
    original_uuid = scene.dan_form_selected_control
    original_status = scene.dan_form_status
    source_selection = None
    proxy_selection = None
    proxy_coordinates = None
    coordinates = None
    report = {'file': bpy.data.filepath, 'dirty_before': bpy.data.is_dirty, 'checks': [], 'timings_ms': {}}

    def check(condition, name):
        if not condition:
            raise AssertionError(name)
        report['checks'].append(name)

    def select_source(vertex_id):
        addon._select_source_ids(source, {vertex_id}, set())

    try:
        if active.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        source_selection = ([v.select for v in source.data.vertices], [e.select for e in source.data.edges], [f.select for f in source.data.polygons])
        proxy_selection = ([v.select for v in controller.data.vertices], [e.select for e in controller.data.edges])
        proxy_coordinates = {item.value: tuple(vertex.co) for item, vertex in
                             zip(controller.data.attributes[addon.PROXY_VID_ATTR].data,
                                 controller.data.vertices)}
        coordinates = [tuple(v.co) for v in source.data.vertices]
        addon._select_only(context, source)
        addon._refresh_runtime()
        check(addon._overlay_mode(context) == 'source', 'model selection keeps Source-backed color overlay')
        for name, function in (
            ('id_maps', lambda: addon._source_id_maps(source)),
            ('ui_list_idle', lambda: addon._sync_ui_list(scene, source)),
            ('proxy_sync_noop', lambda: addon._sync_proxy(source, controller)),
        ):
            function()
            samples = []
            for _ in range(30):
                start = time.perf_counter()
                function()
                samples.append((time.perf_counter() - start) * 1000)
            report['timings_ms'][name] = round(statistics.median(samples), 4)

        original_ensure = addon._ensure_source_ids
        original_sync = addon._sync_proxy
        calls = []

        def forbidden_ensure(_source):
            raise AssertionError('Read-only sidebar/draw assigned Source IDs')

        def counted_sync(*args):
            calls.append(True)
            return original_sync(*args)

        addon._ensure_source_ids = forbidden_ensure
        addon._sync_proxy = counted_sync
        try:
            row_pointers = [item.as_pointer() for item in scene.dan_form_control_items]
            for _ in range(20):
                addon._source_id_maps(source)
                addon._sync_ui_list(scene, source)
                addon._depsgraph_update_post(scene, SimpleNamespace(updates=[]))
            check(not calls, 'idle depsgraph skips proxy sync')
            check(row_pointers == [item.as_pointer() for item in scene.dan_form_control_items], 'idle list keeps row instances')
            check(snapshot == {key: source.get(key) for key in source_keys}, 'read-only lookups do not write Source')
        finally:
            addon._ensure_source_ids = original_ensure
            addon._sync_proxy = original_sync

        controls = addon._controls(source)
        target_index = 1 if len(controls) > 1 else 0
        scene.dan_form_control_index = target_index
        target_uuid = controls[target_index]['control_uuid']
        check(scene.dan_form_selected_control == target_uuid and source.mode == 'OBJECT', 'row click highlights without leaving Object Mode')
        masks_before = (source.get(addon.HIDDEN_VIDS_KEY), source.get(addon.HIDDEN_EIDS_KEY))
        generation_before = controller.get(addon.PROXY_GENERATION_KEY)
        check(bpy.ops.dan_form.toggle_viewport_controls() == {'FINISHED'}, 'Hide Controls operator')
        check(not any(addon._effective_proxy_elements(source)), 'Hide All empties effective network')
        check(all(addon._control_state(source, c)[0] == 'Hidden' for c in addon._controls(source)), 'Hide All synchronizes every eye')
        check(generation_before != controller.get(addon.PROXY_GENERATION_KEY), 'canonical Hide All rebuilds proxy')
        check(bpy.ops.dan_form.toggle_viewport_controls() == {'FINISHED'}, 'Show Controls operator')
        check(all(addon._control_state(source, c)[0] == 'On' for c in addon._controls(source)), 'Show All synchronizes every eye')

        check(bpy.ops.dan_form.focus_controller() == {'FINISHED'}, 'Edit Control navigation')
        check(context.view_layer.objects.active == controller and controller.mode == 'EDIT', 'Edit Control enters proxy Edit Mode')
        check(addon._overlay_mode(context) == 'controller_edit', 'Controller Edit uses live control overlay')
        context.tool_settings.mesh_select_mode = (True, False, False)
        scene.dan_form_control_index = 0
        expected_vertices, expected_edges = addon._control_effective(source, controls[0])
        check(bpy.ops.dan_form.select_control(control_uuid=controls[0]['control_uuid']) == {'FINISHED'},
              'row name selection button selects the active proxy definition')
        selected_vertices, selected_edges = addon._proxy_selection(controller)
        check(selected_vertices == expected_vertices and selected_edges == expected_edges, 'row action selects proxy IDs')
        check(bpy.ops.dan_form.focus_source() == {'FINISHED'}, 'Back to Model navigation')
        check(context.view_layer.objects.active == source and source.mode == 'OBJECT', 'Back restores model Object Mode')
        check(addon._overlay_mode(context) == 'source', 'Back to Model restores Source overlay')
        addon._select_only(context, controller)
        check(addon._overlay_mode(context) == 'controller', 'Controller Object Mode uses controller-backed overlay')
        addon._select_only(context, source)

        bpy.ops.object.mode_set(mode='EDIT')
        scene.dan_form_control_index = target_index
        check(bpy.ops.dan_form.select_control(control_uuid=controls[target_index]['control_uuid']) == {'FINISHED'},
              'row name selection button selects the active Source definition')
        source_vertices, source_edges = addon._source_selection(source)
        check(source_vertices == set(controls[target_index]['vertex_ids']) and source_edges == set(controls[target_index]['edge_ids']), 'row action selects Source IDs')
        bpy.ops.dan_form.focus_controller()
        bpy.ops.dan_form.focus_source()
        check(source.mode == 'EDIT', 'Back restores previous model Edit Mode')

        bpy.ops.dan_form.focus_controller()
        check(not bpy.ops.dan_form.create_control.poll(), 'controller rejects definition creation')
        check(not bpy.ops.dan_form.sync_control.poll(), 'controller rejects membership Sync')
        bpy.ops.dan_form.focus_source()
        definition_count = len(addon._controls(source))
        check(bpy.ops.dan_form.create_control() == {'FINISHED'}, 'temporary definition for controller deletion')
        temporary_uuid = addon._controls(source)[-1]['control_uuid']
        bpy.ops.dan_form.focus_controller()
        check(bpy.ops.dan_form.delete_control.poll(), 'controller accepts definition deletion')
        check(bpy.ops.dan_form.delete_control(control_uuid=temporary_uuid) == {'FINISHED'}, 'controller deletes definition')
        check(len(addon._controls(source)) == definition_count, 'controller deletion preserves remaining definitions')
        bpy.ops.dan_form.focus_source()

        # Regression: Sync must persist the changed list, not serialize a fresh unchanged list.
        scene.dan_form_control_index = 0
        vertex_ids, _ = addon._source_id_maps(source)
        new_vertex_id = next(vid for vid in vertex_ids if vid not in controls[0]['vertex_ids'])
        select_source(new_vertex_id)
        revision_before = source.get(addon.NETWORK_REVISION_KEY)
        check(bpy.ops.dan_form.sync_control() == {'FINISHED'}, 'Sync replacement operator')
        updated = addon._control(source, controls[0]['control_uuid'])
        check(updated['vertex_ids'] == [new_vertex_id] and updated['edge_ids'] == [], 'Sync persists replacement membership')
        revision_after = source.get(addon.NETWORK_REVISION_KEY)
        check(revision_after == revision_before + 1, 'Sync changes revision once')
        check(bpy.ops.dan_form.sync_control() == {'FINISHED'} and source.get(addon.NETWORK_REVISION_KEY) == revision_after, 'Sync no-op keeps revision')
        check(bpy.ops.dan_form.create_control() == {'FINISHED'}, 'create duplicate point definition')
        duplicate = addon._controls(source)[-1]['control_uuid']
        check(bpy.ops.dan_form.delete_control(control_uuid=duplicate) == {'FINISHED'}, 'delete overlap definition')
        check(new_vertex_id in addon._effective_proxy_elements(source)[0], 'delete preserves shared point')
        bpy.ops.object.mode_set(mode='OBJECT')

        samples = []
        for _ in range(3):
            start = time.perf_counter()
            bpy.ops.dan_form.set_control_visibility(control_uuid=controls[0]['control_uuid'], reveal=False)
            bpy.ops.dan_form.set_control_visibility(control_uuid=controls[0]['control_uuid'], reveal=True)
            samples.append((time.perf_counter() - start) * 500)
        report['timings_ms']['eye_operator_mean'] = round(statistics.median(samples), 3)
        check(coordinates == [tuple(v.co) for v in source.data.vertices], 'sidebar operations preserve Source coordinates')

        # External Source coordinate edit must refresh the proxy without unconditional writes.
        mapping, _ = addon._source_id_maps(source)
        effective_vids, _ = addon._effective_proxy_elements(source)
        vid = effective_vids[0]
        index = mapping[vid]
        source.data.vertices[index].co.x += 0.01
        source.data.update()
        context.view_layer.update()
        addon._sync_proxy(source, controller)
        proxy_index = next(i for i, item in enumerate(controller.data.attributes[addon.PROXY_VID_ATTR].data) if item.value == vid)
        check((controller.data.vertices[proxy_index].co - source.data.vertices[index].co).length < 1e-7, 'Source coordinate changes still sync proxy')
        report['status'] = 'PASS'
    finally:
        current_active = context.view_layer.objects.active
        if current_active is not None and current_active.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        for key, value in snapshot.items():
            if value is None:
                if key in source:
                    del source[key]
            else:
                source[key] = value
        if coordinates is not None:
            for vertex, position in zip(source.data.vertices, coordinates):
                vertex.co = position
            source.data.update()
        addon._MAPPING_CACHE.clear()
        addon._rebuild_proxy(source, controller)
        if proxy_generation is not None:
            controller[addon.PROXY_GENERATION_KEY] = proxy_generation
        if proxy_coordinates is not None:
            for item, vertex in zip(controller.data.attributes[addon.PROXY_VID_ATTR].data,
                                    controller.data.vertices):
                vertex.co = proxy_coordinates[item.value]
            controller.data.update()
        if source_selection is not None:
            for elements, values in zip((source.data.vertices, source.data.edges, source.data.polygons), source_selection):
                for element, value in zip(elements, values):
                    element.select = value
        if proxy_selection is not None:
            for elements, values in zip((controller.data.vertices, controller.data.edges), proxy_selection):
                for element, value in zip(elements, values):
                    element.select = value
        controller.hide_set(viewport_hidden, view_layer=context.view_layer)
        context.tool_settings.mesh_select_mode = select_mode
        for obj in context.selected_objects:
            obj.select_set(False)
        for obj in selected_objects:
            obj.select_set(True)
        context.view_layer.objects.active = active
        if original_mode != 'OBJECT':
            bpy.ops.object.mode_set(mode=original_mode)
        scene.dan_form_selected_control = original_uuid
        addon._UI_SIGNATURES.clear()
        addon._refresh_runtime()
        scene.dan_form_status = original_status
        report['dirty_after'] = bpy.data.is_dirty
        report['restored_mode'] = active.mode
        report['restored_active'] = active.name
        report['source_restored'] = snapshot == {key: source.get(key) for key in source_keys}
    return report


result = run()
