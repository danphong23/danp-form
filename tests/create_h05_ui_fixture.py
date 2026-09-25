"""Build a disposable UI fixture; run only in a separate background Blender."""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import bpy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import dan_form as addon  # noqa: E402


def make_source(name, keys=(), absolute=False):
    mesh = bpy.data.meshes.new(f"{name} | Mesh")
    mesh.from_pydata(
        [(-1, 0, 0), (1, 0, 0), (1, 0, 2), (-1, 0, 2)],
        [], [(0, 1, 2, 3)],
    )
    source = bpy.data.objects.new(name, mesh)
    bpy.context.scene.collection.objects.link(source)
    if keys:
        source.shape_key_add(name="Basis", from_mix=False)
        for key_name, offset in keys:
            key = source.shape_key_add(name=key_name, from_mix=False)
            key.data[0].co.z += offset
            key.data[1].co.z += offset
        if absolute:
            mesh.shape_keys.use_relative = False
            mesh.shape_keys.eval_time = 15.0
        source.active_shape_key_index = min(1, len(mesh.shape_keys.key_blocks) - 1)
    bpy.ops.object.select_all(action="DESELECT")
    source.select_set(True)
    bpy.context.view_layer.objects.active = source
    bpy.ops.dan_form.initialize()
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.dan_form.create_control(control_name="Test Control")
    bpy.ops.object.mode_set(mode="OBJECT")
    return source


def build():
    addon.register()
    for obj in list(bpy.data.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    make_source("H05 | Base Target")
    relative = make_source("H05 | Relative Targets", [("Smile", 0.35), ("Blink", -0.2)])
    relative.data.shape_keys.key_blocks[1].value = 0.4
    relative.data.shape_keys.key_blocks[2].lock_shape = True
    absolute = make_source("H05 | Absolute Target", [("A", 0.2), ("B", 0.6)], absolute=True)
    absolute.data.shape_keys.eval_time = 15.0
    bpy.ops.object.select_all(action="DESELECT")
    relative.select_set(True)
    bpy.context.view_layer.objects.active = relative
    bpy.context.scene.dan_form_source = relative
    bpy.context.scene.dan_form_controller = addon._find_controller(relative)
    output = Path(tempfile.gettempdir()) / "danp_h05_ui_safe_copy.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(output), check_existing=False)
    print(f"H05_UI_FIXTURE={output}")


build()
