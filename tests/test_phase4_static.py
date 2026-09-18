from pathlib import Path


SOURCE = (Path(__file__).parents[1] / "dan_form" / "__init__.py").read_text(encoding="utf-8")


def test_phase4_transaction_primitives_exist():
    for name in ("_deform_begin", "_deform_update", "_deform_commit", "_deform_cancel"):
        assert f"def {name}" in SOURCE


def test_phase4_hard_constraints_and_profiles_are_present():
    assert "stationary = set(_effective_proxy_elements(source)[0]) - selected" in SOURCE
    assert "if vid in selected or vid in stationary" in SOURCE
    assert '"SMOOTH"' in SOURCE and '"UNIFORM"' in SOURCE


def test_phase4_operator_and_ui_are_registered():
    assert 'bl_idname = "dan_form.deform"' in SOURCE
    assert 'DANFORM_OT_deform,' in SOURCE
    assert 'dan_form_proportional_profile' in SOURCE
    assert 'item.properties.operation = {"G": "MOVE", "R": "ROTATE", "S": "SCALE"}[key]' in SOURCE
