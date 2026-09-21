"""Storage migration must not erase malformed Source definitions."""

import importlib.util
import json
import sys
import types
from pathlib import Path


ROOT = Path(__file__).parents[1] / "dan_form"


def _storage():
    package = types.ModuleType("dan_form_storage_test")
    package.__path__ = [str(ROOT)]
    bpy = types.ModuleType("bpy")
    bpy.types = types.SimpleNamespace(ID=object, Object=object)
    old_bpy = sys.modules.get("bpy")
    sys.modules["bpy"] = bpy
    sys.modules[package.__name__] = package
    try:
        spec = importlib.util.spec_from_file_location(
            package.__name__ + ".storage", ROOT / "storage.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        if old_bpy is None:
            sys.modules.pop("bpy", None)
        else:
            sys.modules["bpy"] = old_bpy


def test_corrupt_definitions_fail_before_any_migration_write():
    storage = _storage()
    for value in ('[{', '[{"control_uuid":"ok"}, null]', '{"wrong":true}'):
        source = {storage.CONTROLS_KEY: value, storage.SCHEMA_KEY: "2"}
        original = dict(source)
        try:
            storage.migrate_control_schema(source)
        except ValueError as exc:
            assert "CONTROL_DATA_INVALID" in str(exc)
        else:
            raise AssertionError("Malformed definitions were accepted")
        assert source == original


def test_invalid_membership_and_masks_do_not_drop_a_definition():
    storage = _storage()
    valid = {"control_uuid": "a", "name": "A", "vertex_ids": [1], "edge_ids": []}
    for corrupted in ({**valid, "vertex_ids": [1, "broken"]},
                      {**valid, "enabled": "false"},
                      {**valid, "control_uuid": ""}):
        source = {storage.CONTROLS_KEY: json.dumps([valid, corrupted]), storage.SCHEMA_KEY: "2"}
        original = dict(source)
        try:
            storage.migrate_control_schema(source)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid definition was silently normalized")
        assert source == original


def test_valid_legacy_masks_project_onto_overlapping_controls():
    storage = _storage()
    definition = {"control_uuid": "a", "name": "A", "vertex_ids": [1, 2], "edge_ids": [10]}
    second = {**definition, "control_uuid": "b"}
    source = {storage.CONTROLS_KEY: json.dumps([definition, second]),
              storage.HIDDEN_VIDS_KEY: "[1]", storage.HIDDEN_EIDS_KEY: "[10]",
              storage.SCHEMA_KEY: "2"}
    result = storage.migrate_control_schema(source, {10: (1, 2)})
    assert len(result) == 2
    assert all(item["hidden_vertex_ids"] == [1] and item["hidden_edge_ids"] == [10]
               for item in result)
    assert source[storage.SCHEMA_KEY] == storage.SCHEMA_VERSION
