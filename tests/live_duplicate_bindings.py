"""Isolated Blender integration checks for Source/Controller copy ownership.

Run with Blender in background from the add-on directory:
  blender --background --factory-startup --python tests/live_duplicate_bindings.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bmesh
import bpy


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import dan_form  # noqa: E402


def _select(objects, active):
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = active


def _mesh_object(name, collection):
    mesh = bpy.data.meshes.new(name + "Data")
    mesh.from_pydata(
        [(-1, 0, 0), (1, 0, 0), (1, 0, 2), (-1, 0, 2)],
        [],
        [(0, 1, 2, 3)],
    )
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    collection.objects.link(obj)
    return obj


def _coordinates(obj):
    return [tuple(vertex.co) for vertex in obj.data.vertices]


def _controls(obj):
    value = obj.get(dan_form.CONTROLS_KEY, "[]")
    return json.loads(value) if isinstance(value, str) else value


def run():
    if not hasattr(bpy.types.Scene, "dan_form_status"):
        dan_form.register()
    report = {"blender": bpy.app.version_string, "checks": []}
    collection = bpy.data.collections.new("DANP_DUPLICATE_TESTS")
    bpy.context.scene.collection.children.link(collection)
    fixtures = []

    def check(ok, label):
        if not ok:
            raise AssertionError(label)
        report["checks"].append(label)

    try:
        source = _mesh_object("DANP_DUP_SOURCE", collection)
        fixtures.append(source)
        _select([source], source)
        check(bpy.ops.dan_form.initialize() == {"FINISHED"}, "initialize source")
        controller = dan_form._find_controller(source)
        check(controller is not None and controller.parent == source, "controller is the direct child")

        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        check(bpy.ops.dan_form.create_control() == {"FINISHED"}, "create source control")
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.context.view_layer.update()
        check(bool(_controls(source)), "source has a persisted control")

        original_uuid = source[dan_form.SOURCE_UUID_KEY]
        original_positions = _coordinates(source)
        original_controls = json.dumps(_controls(source), sort_keys=True)
        original_controller = controller

        # Copy only the Source object. The lifecycle resolver must turn it into
        # an unbound plain mesh without reaching the original Controller.
        _select([source], source)
        bpy.ops.object.duplicate()
        mesh_copy = bpy.context.view_layer.objects.active
        fixtures.append(mesh_copy)
        bpy.context.view_layer.update()
        dan_form._reconcile_duplicate_bindings()
        check(mesh_copy.get(dan_form.UNBOUND_COPY_KEY, False), "mesh-only duplicate is marked unbound")
        check(dan_form._binding_status(mesh_copy) == "DUPLICATE_UNBOUND", "mesh-only duplicate has no DANP binding")
        check(mesh_copy.get(dan_form.SOURCE_UUID_KEY) is None, "mesh-only duplicate no longer carries the original UUID")
        check(dan_form._find_controller(mesh_copy) is None, "mesh-only duplicate cannot resolve original Controller")
        _select([mesh_copy], mesh_copy)
        check(not bpy.ops.dan_form.remove.poll() and not bpy.ops.dan_form.reset.poll(),
              "Remove and Reset are disabled on a mesh-only duplicate")
        check(dan_form._find_controller(source) == original_controller, "original retains its Controller")
        check(_coordinates(source) == original_positions, "mesh-only copy leaves original coordinates unchanged")
        check(json.dumps(_controls(source), sort_keys=True) == original_controls, "mesh-only copy leaves original controls unchanged")

        _select([mesh_copy], mesh_copy)
        check(bpy.ops.dan_form.initialize() == {"FINISHED"}, "initialize mesh-only copy independently")
        copy_controller = dan_form._find_controller(mesh_copy)
        fixtures.append(copy_controller)
        check(mesh_copy[dan_form.SOURCE_UUID_KEY] != original_uuid, "initialized mesh copy gets a fresh UUID")
        check(copy_controller is not None and copy_controller.parent == mesh_copy, "initialized mesh copy owns its Controller")
        check(_controls(mesh_copy) == [], "mesh-only copy starts with no inherited controls")
        check(_coordinates(source) == original_positions, "initializing copy leaves original geometry unchanged")
        check(json.dumps(_controls(source), sort_keys=True) == original_controls, "initializing copy leaves original controls unchanged")

        # Duplicate the complete original pair. The dependency-graph observer
        # sees the new parent/child pair and gives only that pair a fresh UUID.
        _select([source, original_controller], source)
        bpy.ops.object.duplicate()
        pair_source = bpy.context.view_layer.objects.active
        pair_controller = next(obj for obj in bpy.context.selected_objects if obj != pair_source)
        fixtures.extend([pair_source, pair_controller])
        bpy.context.view_layer.update()
        dan_form._reconcile_duplicate_bindings()
        check(pair_controller.parent == pair_source, "complete duplicate preserves direct parenting")
        check(pair_source[dan_form.SOURCE_UUID_KEY] != original_uuid, "complete pair duplicate gets a fresh UUID")
        check(pair_controller.get(dan_form.CONTROLLER_KEY) == pair_source[dan_form.SOURCE_UUID_KEY], "duplicate Controller owner marker follows new UUID")
        check(_controls(pair_source) == _controls(source), "complete pair duplicate preserves its controls")

        # A Controller Edit on the copied pair must deform only that pair.
        _select([pair_source, pair_controller], pair_source)
        check(bpy.ops.dan_form.focus_controller() == {"FINISHED"}, "enter duplicate Controller Edit")
        pair_before = _coordinates(pair_source)
        original_before_pair_edit = _coordinates(source)
        bm = bmesh.from_edit_mesh(pair_controller.data)
        bm.verts.ensure_lookup_table()
        bm.verts[0].co.z += 0.2
        bmesh.update_edit_mesh(pair_controller.data, loop_triangles=False, destructive=False)
        bpy.context.view_layer.update()
        check(bpy.ops.dan_form.focus_source() == {"FINISHED"}, "finish duplicate Controller edit")
        check(_coordinates(pair_source) != pair_before, "duplicate Controller edit deforms its own Source")
        check(_coordinates(source) == original_before_pair_edit, "duplicate Controller edit leaves original Source unchanged")

        pair_before = _coordinates(pair_source)
        original_before_pair_edit = _coordinates(source)
        pair_source.data.vertices[0].co.x += 0.375
        pair_source.data.update()
        bpy.context.view_layer.update()
        check(_coordinates(source) == original_before_pair_edit, "editing duplicate Source does not alter original Source")
        check(_coordinates(pair_source) != pair_before, "duplicate Source edit was applied locally")

        # Duplicate only the Controller. The known original remains parented;
        # the new object is detached with its world pose preserved.
        world_before = original_controller.matrix_world.copy()
        _select([original_controller], original_controller)
        bpy.ops.object.duplicate()
        controller_copy = bpy.context.view_layer.objects.active
        fixtures.append(controller_copy)
        bpy.context.view_layer.update()
        dan_form._reconcile_duplicate_bindings()
        check(original_controller.parent == source, "original Controller stays parented to original Source")
        check(controller_copy.parent is None, "Controller-only duplicate is detached")
        check(controller_copy.get(dan_form.UNBOUND_COPY_KEY, False), "Controller-only duplicate is marked unbound")
        check((controller_copy.matrix_world.translation - world_before.translation).length < 1e-6,
              "detaching Controller copy preserves world position")
        check(dan_form._find_controller(source) == original_controller, "original Controller remains uniquely resolvable")

        # Simulate an ambiguous file loaded without a runtime owner registry.
        old_uuid = source[dan_form.SOURCE_UUID_KEY]
        pair_source[dan_form.SOURCE_UUID_KEY] = old_uuid
        pair_controller[dan_form.CONTROLLER_KEY] = old_uuid
        dan_form._runtime.BINDING_OWNERS.clear()
        check(dan_form._binding_status(source) == "UUID_CONFLICT", "loaded UUID collision is detected")
        check(dan_form._find_source_by_uuid(old_uuid) is None, "agent UUID lookup rejects ambiguous owners")
        _select([pair_source], pair_source)
        check(bpy.ops.dan_form.resolve_duplicate_pair() == {"FINISHED"}, "explicit pair resolution succeeds")
        check(pair_source[dan_form.SOURCE_UUID_KEY] != source[dan_form.SOURCE_UUID_KEY], "resolution isolates chosen pair identity")
        check(pair_controller.parent == pair_source, "resolution preserves chosen pair parentage")
        check(dan_form._find_controller(pair_source) == pair_controller, "resolved pair is usable")
        check(_coordinates(source) == original_before_pair_edit, "resolving duplicate does not alter original geometry")

        # Alt+D uses the same Mesh datablock. DANP must reject edits before
        # either object can write through to the other.
        shared_copy = source.copy()
        shared_copy.name = "DANP_DUP_SHARED_COPY"
        shared_copy.data = source.data
        collection.objects.link(shared_copy)
        fixtures.append(shared_copy)
        bpy.context.view_layer.update()
        _select([shared_copy], shared_copy)
        check(not bpy.ops.dan_form.initialize.poll(), "shared-data duplicate cannot initialize")
        check(dan_form._binding_status(shared_copy) == "SHARED_DATA", "Alt+D copy reports shared mesh data")
        check(dan_form._binding_status(source) == "SHARED_DATA", "shared mesh blocks the original DANP binding too")
        check(_coordinates(source) == original_before_pair_edit, "shared-data rejection leaves Source coordinates unchanged")
        report["status"] = "PASS"
        return report
    finally:
        active = bpy.context.view_layer.objects.active
        if active is not None and active.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for obj in list(fixtures):
            if obj is not None and bpy.data.objects.get(obj.name) is obj:
                bpy.data.objects.remove(obj, do_unlink=True)
        for obj in list(bpy.data.objects):
            if obj.name.startswith("DANP_DUP_") and obj not in fixtures:
                bpy.data.objects.remove(obj, do_unlink=True)
        if bpy.data.collections.get(collection.name) is collection:
            bpy.data.collections.remove(collection)
        for mesh in list(bpy.data.meshes):
            if mesh.users == 0 and mesh.name.startswith(("DANP_DUP_", "DANPFORM_CTRL_DANP_DUP_")):
                bpy.data.meshes.remove(mesh)
        dan_form._runtime.BINDING_OWNERS.clear()


if __name__ == "__main__":
    try:
        print(json.dumps(run(), sort_keys=True))
    finally:
        if hasattr(bpy.types.Scene, "dan_form_status"):
            dan_form.unregister()
