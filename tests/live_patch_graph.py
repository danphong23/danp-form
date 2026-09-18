"""Live Phase 3 patch partition and display-only regression suite."""

import sys

import bpy


def run():
    addon = sys.modules["bl_ext.user_default.dan_form"]
    context = bpy.context
    scene = context.scene
    original = context.object
    selected = list(context.selected_objects)
    original_mode = original.mode if original else "OBJECT"
    original_patches = scene.dan_form_patches_enabled
    fixture = None
    mesh = None
    checks = []

    def check(value, name):
        if not value:
            raise AssertionError(name)
        checks.append(name)

    try:
        if original and original.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        mesh = bpy.data.meshes.new("DANP_PATCH_GRAPH_TEST_MESH")
        # Two quads share the vertical middle edge (1,4). That edge is a
        # genuine cut; a boundary edge and a loose point are not cuts.
        mesh.from_pydata(
            [(0, 0, 0), (1, 0, 0), (2, 0, 0),
             (0, 1, 0), (1, 1, 0), (2, 1, 0)],
            [],
            [(0, 1, 4, 3), (1, 2, 5, 4)],
        )
        mesh.update()
        fixture = bpy.data.objects.new("DANP_PATCH_GRAPH_TEST", mesh)
        scene.collection.objects.link(fixture)
        addon._select_only(context, fixture)
        addon._ensure_source_ids(fixture)
        vertex_attr = fixture.data.attributes[addon.VID_ATTR]
        edge_attr = fixture.data.attributes[addon.EID_ATTR]
        vertex_ids = {index: int(item.value) for index, item in enumerate(vertex_attr.data)}
        edge_ids = {tuple(sorted(edge.vertices)): int(edge_attr.data[edge.index].value)
                    for edge in fixture.data.edges}
        middle_edge = edge_ids[(1, 4)]
        boundary_edge = edge_ids[(0, 1)]
        point_id = vertex_ids[0]
        controls = [
            {"control_uuid": "middle", "name": "Middle Cut", "vertex_ids": [], "edge_ids": [middle_edge]},
            {"control_uuid": "boundary", "name": "Boundary", "vertex_ids": [], "edge_ids": [boundary_edge]},
            {"control_uuid": "point", "name": "Point", "vertex_ids": [point_id], "edge_ids": []},
        ]
        addon._json_set(fixture, addon.CONTROLS_KEY, controls)
        addon._json_set(fixture, addon.HIDDEN_VIDS_KEY, [])
        addon._json_set(fixture, addon.HIDDEN_EIDS_KEY, [])
        addon._invalidate_patch_cache(fixture)

        partition = addon._patch_partition(fixture)
        records = addon._source_face_records(fixture)
        check(addon._source_face_records(fixture) is records,
              "face connectivity cache reuses unchanged topology")
        check(len(partition["patches"]) == 2, "internal enabled edge splits two face patches")
        check(set(partition["face_patch_ids"].values()) == {p["patch_id"] for p in partition["patches"]},
              "every face belongs to exactly one patch")
        check(len(addon._patches_for_control(fixture, "middle")) == 2,
              "cut control reports both incident patches")
        check(len(addon._patches_for_control(fixture, "boundary")) == 1,
              "boundary control reports its single incident patch")
        check(len(addon._patches_for_control(fixture, "point")) == 1,
              "point control reports its containing patch")
        check(addon._patch_partition(fixture) is partition, "unchanged partition uses cache")

        scene.dan_form_patches_enabled = True
        bpy.ops.object.mode_set(mode="EDIT")
        edit_partition = addon._patch_partition(fixture)
        bpy.ops.object.mode_set(mode="OBJECT")
        check(len(edit_partition["patches"]) == len(partition["patches"]),
              "mode switch preserves patch partition")

        revision = int(fixture.get(addon.NETWORK_REVISION_KEY, 0))
        coordinates = [tuple(vertex.co) for vertex in fixture.data.vertices]
        scene.dan_form_patches_enabled = True
        shader, batches = addon._patch_overlay_batches(context, fixture)
        check(shader is not None and len(batches) == 2, "patch overlay builds one batch per patch")
        scene.dan_form_patches_enabled = False
        check(addon._patch_overlay_batches(context, fixture) == (None, []),
              "patch display toggle has no geometry side effect")
        check([tuple(vertex.co) for vertex in fixture.data.vertices] == coordinates,
              "patch display preserves Source coordinates")
        check(int(fixture.get(addon.NETWORK_REVISION_KEY, 0)) == revision,
              "patch display preserves network revision")

        addon._json_set(fixture, addon.HIDDEN_EIDS_KEY, [middle_edge])
        addon._invalidate_patch_cache(fixture)
        merged = addon._patch_partition(fixture)
        check(len(merged["patches"]) == 1, "hiding the cut merges the two patches")
        addon._json_set(fixture, addon.HIDDEN_EIDS_KEY, [])
        addon._invalidate_patch_cache(fixture)
        revealed = addon._patch_partition(fixture)
        check(len(revealed["patches"]) == 2, "revealing the cut restores the partition")

        addon._json_set(fixture, addon.HIDDEN_EIDS_KEY, [boundary_edge])
        addon._invalidate_patch_cache(fixture)
        check(len(addon._patch_partition(fixture)["patches"]) == 2,
              "hiding a boundary control does not change interior partition")
        return {"status": "PASS", "checks": checks, "patches": len(revealed["patches"])}
    finally:
        scene.dan_form_patches_enabled = original_patches
        if fixture is not None and fixture.name in bpy.data.objects:
            bpy.data.objects.remove(fixture, do_unlink=True)
            if mesh.users == 0:
                bpy.data.meshes.remove(mesh)
        addon._invalidate_patch_cache()
        if context.object and context.object.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for obj in context.selected_objects:
            obj.select_set(False)
        for obj in selected:
            if obj.name in bpy.data.objects:
                obj.select_set(True)
        if original and original.name in bpy.data.objects:
            context.view_layer.objects.active = original
            if original_mode != "OBJECT":
                bpy.ops.object.mode_set(mode=original_mode)


result = run()
