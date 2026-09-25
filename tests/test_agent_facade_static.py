from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AGENT = (ROOT / "dan_form" / "agent.py").read_text(encoding="utf-8")
SELECTION = (ROOT / "dan_form" / "blender" / "selection.py").read_text(encoding="utf-8")


def test_agent_facade_uses_shared_ui_operator_and_persistent_selection():
    assert "create_control_from_current_selection" in AGENT
    assert "bpy.ops.dan_form.create_control" in AGENT
    assert "persistent_vertex_ids" in SELECTION
    assert "persistent_edge_ids" in SELECTION
    assert "mesh.vertices[" not in AGENT
    assert "mesh.edges[" not in AGENT


def test_agent_facade_exposes_validation_and_no_direct_json_write():
    assert "def validate_control" in AGENT
    assert "_source_id_maps" in AGENT
    assert "_validate_source_topology" in AGENT
    assert "_json_set" not in AGENT


def test_agent_facade_exposes_transaction_lifecycle():
    for name in ("begin_operation", "update_operation", "commit_operation", "cancel_operation"):
        assert f"def {name}" in AGENT
    for name in ("list_deformation_targets", "select_deformation_target", "set_knot_targets"):
        assert f"def {name}" in AGENT
    assert "agent_operation_id" in AGENT
    assert "TARGET_SET_MISMATCH" in AGENT
    assert "TARGET_REVISION_MISMATCH" in AGENT
    assert "_deform_begin" in AGENT
    assert "_deform_update" in AGENT
    assert "_deform_cancel" in AGENT
