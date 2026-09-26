from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_controller_resolution_uses_direct_parentage_and_unique_binding() -> None:
    context = (ROOT / "dan_form" / "blender" / "context.py").read_text(encoding="utf-8")
    assert "obj.parent == source" in context
    assert "controller.parent" in context
    assert "DUPLICATE_UNBOUND" in context
    assert "UUID_CONFLICT" in context
    assert "matches[0] if len(matches) == 1" in context
    assert "return matches[0] if len(matches) == 1 else None" in context
    assert "def find_source_by_uuid" in context


def test_copy_lifecycle_rekeys_full_pair_and_clears_mesh_only_duplicate() -> None:
    lifecycle = (ROOT / "dan_form" / "blender" / "lifecycle.py").read_text(encoding="utf-8")
    operators = (ROOT / "dan_form" / "operator_actions" / "structure.py").read_text(encoding="utf-8")
    assert "def _reconcile_duplicate_bindings" in lifecycle
    assert "duplicate_source[SOURCE_UUID_KEY] = fresh_uuid" in lifecycle
    assert "_clear_duplicate_source_state(duplicate_source)" in lifecycle
    assert "if binding == \"DUPLICATE_UNBOUND\"" in operators
    assert "class DANFORM_OT_resolve_duplicate_pair" in operators


def test_duplicate_ownership_decision_is_documented() -> None:
    adr = (ROOT / "docs" / "decisions" / "ADR-014-source-controller-ownership.md").read_text(encoding="utf-8")
    assert "direct Blender" in adr
    assert "mesh-only" in adr.lower()
    assert "fails closed" in adr
