"""Static contract checks for topology pause, Reset and ownership cleanup."""

from pathlib import Path


ROOT = Path(__file__).parents[1]
PACKAGE = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "dan_form").rglob("*.py"))


def test_topology_changes_pause_instead_of_writing_stale_mapping():
    mesh = (ROOT / "dan_form" / "blender" / "mesh.py").read_text(encoding="utf-8")
    lifecycle = (ROOT / "dan_form" / "blender" / "lifecycle.py").read_text(encoding="utf-8")
    assert '"state": "PAUSED"' in mesh
    assert 'raise ValueError("TOPOLOGY_CHANGED")' in mesh
    assert "_set_topology_paused_status" in lifecycle


def test_reset_is_registered_and_undoable():
    operators = (ROOT / "dan_form" / "operators.py").read_text(encoding="utf-8")
    assert 'class DANFORM_OT_reset' in operators
    assert 'bl_idname = "dan_form.reset"' in operators
    assert 'class DANFORM_OT_reset_source' in operators
    assert 'bl_idname = "dan_form.reset_source"' in operators
    assert 'bl_options = {"REGISTER", "UNDO"}' in operators
    assert "_ensure_source_ids(source)" in operators
    assert "ORIGINAL_POSITIONS_KEY" in operators


def test_cleanup_requires_explicit_ownership_marker():
    context = (ROOT / "dan_form" / "blender" / "context.py").read_text(encoding="utf-8")
    lifecycle = (ROOT / "dan_form" / "blender" / "lifecycle.py").read_text(encoding="utf-8")
    assert "orphaned_owned_objects" in context
    assert "FACE_SOURCE_UUID_KEY" in context
    assert "_cleanup_orphaned_owned_objects" in lifecycle


def test_modifier_contract_mentions_base_mapping_and_evaluated_display():
    integration = (ROOT / "docs" / "blender" / "integration.md").read_text(encoding="utf-8")
    assert "unapplied modifier" in integration
    assert "Applying a modifier" in integration
    assert "base Source IDs" in integration
