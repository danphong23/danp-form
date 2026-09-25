"""Create a disposable two-control Source for the native transform gate."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import dan_form as addon  # noqa: E402


def run():
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if len(args) != 1:
        raise ValueError("Pass one disposable .blend output path after --")
    output = Path(args[0]).resolve()
    addon.register()
    vertices = [(x, 0.0, float(row)) for row in range(5) for x in (0.0, 1.0)]
    faces = [(2 * row, 2 * row + 1, 2 * row + 3, 2 * row + 2) for row in range(4)]
    mesh = bpy.data.meshes.new("DANP Native Transform Fixture Mesh")
    mesh.from_pydata(vertices, [], faces)
    source = bpy.data.objects.new("DANP Native Transform Fixture", mesh)
    bpy.context.scene.collection.objects.link(source)
    for obj in bpy.context.view_layer.objects:
        obj.select_set(False)
    source.select_set(True)
    bpy.context.view_layer.objects.active = source
    if bpy.ops.dan_form.initialize() != {"FINISHED"}:
        raise AssertionError("Could not initialize native transform fixture")
    controller = addon._find_controller(source)
    if controller is None:
        raise AssertionError("Fixture Controller is not bound")
    vids, _ = addon._source_id_maps(source)
    edge_vids = addon._source_edge_vids(source)
    bpy.ops.object.mode_set(mode="EDIT")
    for row in (0, 4):
        ring = {vertex_id for vertex_id, index in vids.items() if index in (2 * row, 2 * row + 1)}
        ring_edges = {edge_id for edge_id, endpoints in edge_vids.items() if set(endpoints) == ring}
        addon._select_source_ids(source, ring, ring_edges)
        if bpy.ops.dan_form.create_control() != {"FINISHED"}:
            raise AssertionError("Could not create fixture control")
    bpy.ops.object.mode_set(mode="OBJECT")
    if len(addon._controls(source)) != 2:
        raise AssertionError("Fixture needs two controls")
    bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False)
    return {"status": "PASS", "file": str(output), "controls": 2,
            "source_vertices": len(source.data.vertices)}


result = run()
print("DANP_RESULT_JSON=" + json.dumps(result))
