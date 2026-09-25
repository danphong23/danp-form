"""Blender background checks for H05 target display and new-key workflow."""

from __future__ import annotations

import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import dan_form as addon  # noqa: E402


def _near(left, right, epsilon=1e-6):
    return (left - right).length <= epsilon


def run():
    addon.register()
    scene = bpy.context.scene
    checks = []

    def check(value, message):
        if not value:
            raise AssertionError(message)
        checks.append(message)

    mesh = bpy.data.meshes.new("H05_SourceMesh")
    mesh.from_pydata(
        [(-1, 0, 0), (1, 0, 0), (1, 0, 2), (-1, 0, 2)],
        [], [(0, 1, 2, 3)],
    )
    source = bpy.data.objects.new("H05_Source", mesh)
    scene.collection.objects.link(source)
    try:
        base_coordinates = [vertex.co.copy() for vertex in mesh.vertices]
        addon._select_only(bpy.context, source)
        check(bpy.ops.dan_form.initialize() == {"FINISHED"}, "initialize Source without keys")
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.select_all(action="SELECT")
        check(bpy.ops.dan_form.create_control() == {"FINISHED"}, "create one control for target-mode checks")
        bpy.ops.object.mode_set(mode="OBJECT")
        check(bpy.ops.dan_form.create_shape_key(name="From Base") == {"FINISHED"},
              "New Shape Key creates Basis and target when Source had no keys")
        keys = source.data.shape_keys.key_blocks
        check(len(keys) == 2 and keys[0].name == "Basis", "Basis is created before the new key")
        check(all(_near(keys[0].data[i].co, base_coordinates[i]) for i in range(4)),
              "new Basis preserves Base mesh coordinates")
        check(all(_near(keys[1].data[i].co, base_coordinates[i]) for i in range(4)),
              "new key copies the original Base coordinates")
        check(keys[1].value == 0.0 and source.active_shape_key_index == 1,
              "new key is active with zero relative value")

        source.show_only_shape_key = False
        check(bpy.ops.dan_form.focus_controller() == {"FINISHED"},
              "entering Controller Edit succeeds for active target")
        check(source.show_only_shape_key and context_mode_is(bpy, controller="EDIT"),
              f"Controller Edit isolates the active key for preview (show_only={source.show_only_shape_key}, active={bpy.context.view_layer.objects.active.name if bpy.context.view_layer.objects.active else None}, mode={bpy.context.view_layer.objects.active.mode if bpy.context.view_layer.objects.active else None})")
        check(bpy.ops.dan_form.select_shape_key(key_index=1) == {"FINISHED"},
              "target selector changes target while Controller Edit is active")
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.context.view_layer.update()
        check(not source.show_only_shape_key,
              "leaving Controller Edit through Blender mode switch restores prior preview")
        check(bpy.ops.dan_form.focus_source() == {"FINISHED"},
              "returning from Controller Edit restores Source")
        check(not source.show_only_shape_key,
              "leaving Controller Edit restores the previous preview setting")

        expression = source.shape_key_add(name="Expression", from_mix=False)
        expression.data[0].co.z += 0.35
        expression.value = 0.42
        expression.mute = True
        basis = keys[0]
        basis.value = 0.73
        basis.mute = False
        expression.mute = False
        expression.value = 0.42
        expression_driver = expression.driver_add("value")
        expression_driver.driver.type = "SCRIPTED"
        expression_driver.driver.expression = "0.42"
        source.active_shape_key_index = 2
        source.show_only_shape_key = True
        source.data.shape_keys.use_relative = True
        relative_before = {key.name: (key.value, key.mute) for key in keys}
        relative_coordinates_before = {
            key.name: [point.co.copy() for point in key.data]
            for key in keys
        }
        drivers_before = [
            (curve.data_path, curve.array_index, curve.mute,
             curve.driver.type, curve.driver.expression)
            for curve in source.data.shape_keys.animation_data.drivers
        ]
        target_before = [point.co.copy() for point in expression.data]
        check(bpy.ops.dan_form.create_shape_key(name="Relative Copy") == {"FINISHED"},
              "New Shape Key succeeds from active relative target")
        relative_new = source.data.shape_keys.key_blocks[-1]
        check(all(_near(relative_new.data[i].co, target_before[i]) for i in range(4)),
              "relative key copies active target stored coordinates")
        check(relative_new.relative_key == basis,
              "new relative key uses the stable Basis as its relative reference")
        check(all((key.value, key.mute) == relative_before[key.name]
                  for key in source.data.shape_keys.key_blocks if key.name in relative_before),
              "adding a relative key preserves all existing values and mute states")
        check(all(
            _near(key.data[index].co, relative_coordinates_before[key.name][index])
            for key in source.data.shape_keys.key_blocks if key.name in relative_coordinates_before
            for index in range(len(key.data))
        ), "adding a relative key preserves existing key coordinates")
        drivers_after = [
            (curve.data_path, curve.array_index, curve.mute,
             curve.driver.type, curve.driver.expression)
            for curve in source.data.shape_keys.animation_data.drivers
        ]
        check(drivers_after == drivers_before,
              "adding a relative key preserves existing Shape Key drivers")
        check(source.show_only_shape_key and source.data.shape_keys.use_relative,
              "relative creation preserves target preview and stack mode")

        keys = source.data.shape_keys
        keys.use_relative = False
        keys.eval_time = 15.0
        source.active_shape_key_index = 2
        source.show_only_shape_key = False
        expression.data[1].co.y = 0.2
        source.data.update()
        bpy.context.view_layer.update()
        absolute_visible_before = {
            index: source.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices[index].co.copy()
            for index in range(len(mesh.vertices))
        }
        absolute_eval_time = keys.eval_time
        absolute_max_frame = max(float(key.frame) for key in keys.key_blocks)
        absolute_values = {key.name: (key.value, key.mute) for key in keys.key_blocks}
        absolute_coordinates_before = {
            key.name: [point.co.copy() for point in key.data]
            for key in keys.key_blocks
        }
        absolute_drivers_before = [
            (curve.data_path, curve.array_index, curve.mute,
             curve.driver.type, curve.driver.expression)
            for curve in keys.animation_data.drivers
        ]
        target_before = [point.co.copy() for point in expression.data]
        check(bpy.ops.dan_form.create_shape_key(name="Absolute Copy") == {"FINISHED"},
              "New Shape Key succeeds from active absolute target")
        absolute_new = source.data.shape_keys.key_blocks[-1]
        check(absolute_new.frame > max(absolute_eval_time, absolute_max_frame),
              "absolute key receives a unique frame beyond the current evaluation")
        check(keys.eval_time == absolute_eval_time and not keys.use_relative,
              "absolute creation preserves evaluation time and stack mode")
        check(all(_near(absolute_new.data[i].co, target_before[i]) for i in range(4)),
              "absolute key copies active target stored coordinates")
        check(all((key.value, key.mute) == absolute_values[key.name]
                  for key in keys.key_blocks if key.name in absolute_values),
              "adding an absolute key preserves all existing values and mute states")
        check(all(
            _near(key.data[index].co, absolute_coordinates_before[key.name][index])
            for key in keys.key_blocks if key.name in absolute_coordinates_before
            for index in range(len(key.data))
        ), "adding an absolute key preserves existing key coordinates")
        absolute_drivers_after = [
            (curve.data_path, curve.array_index, curve.mute,
             curve.driver.type, curve.driver.expression)
            for curve in keys.animation_data.drivers
        ]
        check(absolute_drivers_after == absolute_drivers_before,
              "adding an absolute key preserves existing Shape Key drivers")
        absolute_visible_after = {
            index: source.evaluated_get(bpy.context.evaluated_depsgraph_get()).data.vertices[index].co.copy()
            for index in range(len(mesh.vertices))
        }
        check(all(_near(absolute_visible_after[i], absolute_visible_before[i]) for i in absolute_visible_before),
              "adding an absolute key does not change the current evaluated pose")
        check(not source.show_only_shape_key,
              "absolute creation preserves the previous key preview setting")

        result = {
            "status": "PASS",
            "checks": checks,
            "shape_key_count": len(keys.key_blocks),
            "absolute_eval_time": keys.eval_time,
            "active_target": keys.key_blocks[source.active_shape_key_index].name,
            "blender_version": bpy.app.version_string,
        }
        print("DANP_RESULT_JSON=" + __import__("json").dumps(result))
    finally:
        addon.unregister()
        bpy.data.objects.remove(source, do_unlink=True)
        bpy.data.meshes.remove(mesh)


def context_mode_is(module, controller="EDIT"):
    active = module.context.view_layer.objects.active
    return active is not None and active.mode == controller


result = run()
