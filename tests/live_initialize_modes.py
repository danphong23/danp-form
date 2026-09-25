"""Blender regression: Init is atomic and works from Source Edit Mode."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import bmesh
import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import dan_form as addon  # noqa: E402
from dan_form import operators  # noqa: E402
from dan_form.blender import lifecycle  # noqa: E402


class LayoutRecorder:
    def __init__(self, operators_seen):
        self.operators_seen = operators_seen

    def row(self, **_kwargs):
        return self

    column = row
    box = row

    def operator(self, identifier, **_kwargs):
        self.operators_seen.append(identifier)
        return SimpleNamespace()

    def label(self, **_kwargs):
        return None

    def menu(self, *_args, **_kwargs):
        return None

    def prop(self, *_args, **_kwargs):
        return None

    def separator(self, *_args, **_kwargs):
        return None

    def template_list(self, *_args, **_kwargs):
        return None


def run():
    addon.register()
    checks = []

    def check(value, label):
        if not value:
            raise AssertionError(label)
        checks.append(label)

    def make_source(name):
        mesh = bpy.data.meshes.new(name + " Mesh")
        mesh.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [], [(0, 1, 2, 3)])
        source = bpy.data.objects.new(name, mesh)
        bpy.context.scene.collection.objects.link(source)
        for obj in bpy.context.view_layer.objects:
            obj.select_set(False)
        source.select_set(True)
        bpy.context.view_layer.objects.active = source
        return source

    def panel_operators():
        seen = []
        addon.DANFORM_PT_sidebar.draw(SimpleNamespace(layout=LayoutRecorder(seen)), bpy.context)
        return seen

    try:
        source = make_source("DANP Init Edit Source")
        bpy.ops.object.mode_set(mode="EDIT")
        bm = bmesh.from_edit_mesh(source.data)
        bm.verts.ensure_lookup_table()
        bm.verts[0].co.x += 0.25
        for vert in bm.verts:
            vert.select = True
        for edge in bm.edges:
            edge.select = True
        bmesh.update_edit_mesh(source.data, loop_triangles=False, destructive=False)
        check(bpy.ops.dan_form.initialize() == {"FINISHED"}, "Init succeeds in Source Edit Mode")
        controller = addon._find_controller(source)
        check(source.mode == "EDIT" and bpy.context.view_layer.objects.active == source,
              "Init restores Source Edit Mode and active object")
        check(controller is not None and controller.parent == source
              and len(addon._controller_children(source)) == 1,
              "Init creates exactly one bound direct Controller child")
        check(len([obj for obj in bpy.data.objects if obj.get(addon.CONTROLLER_KEY)]) == 1,
              "Init leaves no orphan Controller object")
        check("dan_form.reset_source" in panel_operators()
              and "dan_form.initialize" not in panel_operators(),
              "sidebar shows bound controls only for the real child")
        check(bpy.ops.dan_form.create_control() == {"FINISHED"},
              "selected Edit Mesh geometry can create a control immediately")
        check(len(controller.data.vertices) == 4 and len(controller.data.edges) == 4,
              "new control proxy contains selected source geometry")
        check(any(abs(vertex.co.x - 0.25) < 1e-6 for vertex in controller.data.vertices),
              "proxy uses current Edit Mesh coordinates")
        bpy.ops.object.mode_set(mode="OBJECT")

        failed_source = make_source("DANP Failed Init Source")
        bpy.ops.object.mode_set(mode="EDIT")
        original_rebuild = operators._rebuild_proxy
        operators._rebuild_proxy = lambda _source, _controller: (_ for _ in ()).throw(ValueError("INJECTED_FAILURE"))
        try:
            try:
                failed_result = bpy.ops.dan_form.initialize()
            except RuntimeError:
                failed_result = {"CANCELLED"}
        finally:
            operators._rebuild_proxy = original_rebuild
        check(failed_result == {"CANCELLED"}, "failed Init is reported as cancelled")
        check(failed_source.mode == "EDIT", "failed Init restores Source Edit Mode")
        check(not failed_source.get(addon.SOURCE_UUID_KEY)
              and not addon._controller_children(failed_source),
              "failed Init clears new Source binding and child")
        check(len([obj for obj in bpy.data.objects if obj.get(addon.CONTROLLER_KEY)]) == 1,
              "failed Init removes the newly created orphan Controller")
        check("dan_form.initialize" in panel_operators()
              and "dan_form.reset_source" not in panel_operators(),
              "sidebar returns to Init after failed initialization")
        bpy.ops.object.mode_set(mode="OBJECT")

        failed_source[addon.SOURCE_UUID_KEY] = "legacy-incomplete-init"
        detached_mesh = bpy.data.meshes.new("Detached Controller Mesh")
        detached_mesh.from_pydata([(0, 0, 0)], [], [])
        detached = bpy.data.objects.new("Detached Legacy Controller", detached_mesh)
        bpy.context.scene.collection.objects.link(detached)
        detached[addon.CONTROLLER_KEY] = "legacy-incomplete-init"
        for obj in bpy.context.view_layer.objects:
            obj.select_set(False)
        detached.select_set(True)
        bpy.context.view_layer.objects.active = detached
        check("dan_form.unbind_stale_object" in panel_operators(),
              "detached Controller offers Unbind before any lifecycle handler runs")
        for obj in bpy.context.view_layer.objects:
            obj.select_set(False)
        failed_source.select_set(True)
        bpy.context.view_layer.objects.active = failed_source
        lifecycle._cleanup_orphaned_owned_objects()
        check(detached.get(addon.ORPHANED_OWNED_KEY) is True,
              "detached legacy Controller is marked as unowned despite matching UUID")
        check("dan_form.initialize" in panel_operators()
              and "dan_form.reset_source" not in panel_operators(),
              "Source with UUID but no child offers Rebuild, not initialized controls")
        for obj in bpy.context.view_layer.objects:
            obj.select_set(False)
        detached.select_set(True)
        bpy.context.view_layer.objects.active = detached
        check("dan_form.unbind_stale_object" in panel_operators(),
              "detached Controller offers explicit non-destructive unbind")
        check(bpy.ops.dan_form.unbind_stale_object() == {"FINISHED"}
              and detached.data is detached_mesh
              and detached.get(addon.CONTROLLER_KEY) is None,
              "legacy object can be unbound while preserving its mesh")
        for obj in bpy.context.view_layer.objects:
            obj.select_set(False)
        failed_source.select_set(True)
        bpy.context.view_layer.objects.active = failed_source
        check(bpy.ops.dan_form.initialize() == {"FINISHED"}
              and addon._find_controller(failed_source) is not None,
              "legacy Source can rebuild a valid child after explicit unbind")

        object_source = make_source("DANP Init Object Source")
        check(bpy.ops.dan_form.initialize() == {"FINISHED"},
              "Object Mode initialization remains available")
        check(addon._find_controller(object_source) is not None,
              "Object Mode initialization creates a bound child")
        return {"status": "PASS", "checks": checks,
                "blender_version": bpy.app.version_string}
    finally:
        if bpy.context.view_layer.objects.active is not None and bpy.context.view_layer.objects.active.mode == "EDIT":
            bpy.ops.object.mode_set(mode="OBJECT")
        addon.unregister()


result = run()
print("DANP_RESULT_JSON=" + json.dumps(result))
