from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_modifier_sync_has_a_proxy_policy_and_mirror_allowlist():
    source = (ROOT / "dan_form" / "blender" / "modifiers.py").read_text(encoding="utf-8")
    assert "CONTROLLER_MODIFIER_TYPES" in source
    assert 'frozenset({"MIRROR"})' in source
    assert "sync_controller_modifiers" in source
    assert "unsupported_source_modifiers" in source


def test_proxy_rebuild_syncs_modifiers_before_edit_mode_is_restored():
    source = (ROOT / "dan_form" / "blender" / "proxy.py").read_text(encoding="utf-8")
    assert "sync_controller_modifiers" in source
    assert "bpy.ops.object.mode_set(mode=\"OBJECT\")" in source


def test_lifecycle_tracks_full_modifier_properties_and_undo_reload():
    source = (ROOT / "dan_form" / "blender" / "mesh.py").read_text(encoding="utf-8")
    lifecycle = (ROOT / "dan_form" / "blender" / "lifecycle.py").read_text(encoding="utf-8")
    assert "return stack_signature(source)" in source
    assert "_sync_controller_modifiers(source, controller)" in lifecycle
    assert "modifier_changed = previous_modifiers != current_modifiers" in lifecycle


def test_source_writeback_applies_mirror_constraints():
    modifiers = (ROOT / "dan_form" / "blender" / "modifiers.py").read_text(encoding="utf-8")
    workflows = (ROOT / "dan_form" / "blender" / "workflows.py").read_text(encoding="utf-8")
    assert "def apply_mirror_constraints" in modifiers
    assert "use_clip" in modifiers and "merge_threshold" in modifiers
    assert "output = apply_mirror_constraints(source, p0, output)" in workflows
