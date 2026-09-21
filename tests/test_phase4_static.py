from pathlib import Path


ROOT = Path(__file__).parents[1]
SOURCE = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "dan_form").rglob("*.py"))


def test_phase4_transaction_primitives_exist():
    for name in ("_deform_begin", "_deform_update", "_deform_commit", "_deform_cancel"):
        assert f"def {name}" in SOURCE


def test_phase4_hard_constraints_and_profiles_are_present():
    assert (
        "stationary = set(deps.effective_proxy_elements(source)[0]) - selected" in SOURCE
        or "stationary = set(_effective_proxy_elements(source)[0]) - selected" in SOURCE
    )
    assert (
        "if vertex_id in selected or vertex_id in stationary" in SOURCE
        or "if vid in selected or vid in stationary" in SOURCE
    )
    assert '"SMOOTH"' in SOURCE and '"UNIFORM"' in SOURCE


def test_explicit_target_mapping_is_not_replaced_by_delta_defaults():
    workflows = (ROOT / "dan_form" / "blender" / "workflows.py").read_text(encoding="utf-8")
    assert "if targets is None:" in workflows


def test_phase4_operator_and_ui_are_registered():
    assert 'bl_idname = "dan_form.deform"' in SOURCE
    assert 'DANFORM_OT_deform,' in SOURCE
    assert 'dan_form_proportional_profile' in SOURCE


def test_native_grs_is_wrapped_by_explicit_begin_finish_macros():
    operators = (ROOT / "dan_form" / "operators.py").read_text(encoding="utf-8")
    session = (ROOT / "dan_form" / "blender" / "transform_session.py").read_text(encoding="utf-8")
    lifecycle = (ROOT / "dan_form" / "blender" / "lifecycle.py").read_text(encoding="utf-8")
    assert 'bl_idname = "dan_form.native_begin"' in operators
    assert 'bl_idname = "dan_form.native_finish"' in operators
    assert 'bl_idname = "dan_form.native_move"' in operators
    assert 'bl_idname = "dan_form.native_rotate"' in operators
    assert 'bl_idname = "dan_form.native_scale"' in operators
    assert "macro.define(transform_operator)" in operators
    assert "managed_by_macro" in session
    assert "NATIVE_TRANSFORM_SESSIONS" in session
    assert 'text="Apply Move"' not in operators
    assert "dan_form_proportional_profile" in lifecycle
    assert "dan_form_proportional_radius" in lifecycle
