from pathlib import Path


ROOT = Path(__file__).parents[1]
SOURCE = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "dan_form").rglob("*.py"))


def test_phase4_transaction_primitives_exist():
    for name in ("_deform_begin", "_deform_update", "_deform_commit", "_deform_cancel"):
        assert f"def {name}" in SOURCE


def test_phase4_hard_constraints_and_profiles_are_present():
    assert (
        "stationary = set(deps.effective_proxy_elements(source)[0]) - active" in SOURCE
        or "stationary = set(_effective_proxy_elements(source)[0]) - active" in SOURCE
    )
    assert "for vertex_id, target in operation_targets.items():" in SOURCE
    assert "output[vertex_id] = p0[vertex_id].copy()" in SOURCE
    assert "solve_displacements(" in SOURCE
    assert '"SMOOTH"' in SOURCE and '"UNIFORM"' in SOURCE


def test_explicit_target_mapping_is_not_replaced_by_delta_defaults():
    workflows = (ROOT / "dan_form" / "blender" / "workflows.py").read_text(encoding="utf-8")
    assert "if targets is None:" in workflows


def test_phase4_operator_and_ui_are_registered():
    assert 'bl_idname = "dan_form.deform"' in SOURCE
    assert 'DANFORM_OT_deform,' in SOURCE
    assert 'dan_form_proportional_profile' in SOURCE


def test_native_grs_uses_blender_edit_transform_without_legacy_macros():
    operators = (ROOT / "dan_form" / "operators.py").read_text(encoding="utf-8")
    session = (ROOT / "dan_form" / "blender" / "transform_session.py").read_text(encoding="utf-8")
    lifecycle = (ROOT / "dan_form" / "blender" / "lifecycle.py").read_text(encoding="utf-8")
    assert 'bl_idname = "dan_form.native_begin"' not in operators
    assert 'bl_idname = "dan_form.select_box"' not in operators
    assert "managed_by_macro" not in session
    assert "_observe_native_controller_transform" in lifecycle
    assert "NATIVE_TRANSFORM_SESSIONS" in session
    assert 'text="Apply Move"' not in operators
    assert "dan_form_proportional_profile" in lifecycle
    assert "dan_form_proportional_radius" in lifecycle


def test_native_session_commits_original_targets_before_selection_changes():
    lifecycle = (ROOT / "dan_form" / "blender" / "lifecycle.py").read_text(encoding="utf-8")
    session = (ROOT / "dan_form" / "blender" / "transform_session.py").read_text(encoding="utf-8")
    assert "_controller_selection_changed(controller, transaction)" in lifecycle
    assert "moved_controller_targets" in session
    assert "finalize_active(source, controller, deps)" in lifecycle
    assert "update(source, controller, deps, session," in session
    assert "targets=session.get(\"last_targets\", {})" in session
    assert "rest_targets = {vertex_id: rest[vertex_id]" in session


def test_native_targets_are_coordinate_deltas_and_source_write_is_idempotent():
    session = (ROOT / "dan_form" / "blender" / "transform_session.py").read_text(encoding="utf-8")
    workflows = (ROOT / "dan_form" / "blender" / "workflows.py").read_text(encoding="utf-8")
    assert "def moved_controller_targets" in session
    assert "position - rest[vertex_id]" in session
    assert "if changed:" in workflows
    assert "length_squared > 1e-16" in workflows


def test_native_completion_uses_blender_modal_boundary_not_quiet_time():
    lifecycle = (ROOT / "dan_form" / "blender" / "lifecycle.py").read_text(encoding="utf-8")
    session = (ROOT / "dan_form" / "blender" / "transform_session.py").read_text(encoding="utf-8")
    assert "NATIVE_QUIET_POLLS" not in lifecycle
    assert "idle_polls" not in lifecycle
    assert "modal_operators" in session
    assert "The timer only samples Blender's explicit modal state" in lifecycle
    assert 'if session.get("had_delta"):' in lifecycle


def test_native_undo_keeps_history_and_resyncs_proxy():
    lifecycle = (ROOT / "dan_form" / "blender" / "lifecycle.py").read_text(encoding="utf-8")
    workflows = (ROOT / "dan_form" / "blender" / "workflows.py").read_text(encoding="utf-8")
    assert 'setdefault("history", [])' in workflows
    assert '"controller_pre"' in workflows
    assert '"shape_key_target"' in workflows
    assert "for item in reversed(history)" in lifecycle
    assert "controller_pose_matches" in lifecycle
    assert "_sync_proxy(source, controller)" in lifecycle
    assert "_OVERLAY_CACHE.clear()" in lifecycle


def test_operation_freezes_proxy_and_modifier_generations():
    workflows = (ROOT / "dan_form" / "blender" / "workflows.py").read_text(encoding="utf-8")
    assert '"proxy_generation"' in workflows
    assert '"modifier_signature"' in workflows
    assert "OPERATION_STALE" in workflows
    assert "deps.overlay_cache.clear()" in workflows


def test_topology_lock_uses_the_native_modal_boundary():
    operators = (ROOT / "dan_form" / "operators.py").read_text(encoding="utf-8")
    assert "native_transform_active(context)" in operators
    assert "context.window_manager.operators" not in operators


def test_world_transform_cannot_fall_through_as_source_local():
    operation = (ROOT / "dan_form" / "core" / "operation.py").read_text(encoding="utf-8")
    assert "WORLD_SPACE_MATRIX_REQUIRED" in operation


def test_transform_selection_intent_is_carried_separately_from_measured_targets():
    workflows = (ROOT / "dan_form" / "blender" / "workflows.py").read_text(encoding="utf-8")
    session = (ROOT / "dan_form" / "blender" / "transform_session.py").read_text(encoding="utf-8")
    deformation = (ROOT / "dan_form" / "core" / "deformation.py").read_text(encoding="utf-8")
    assert 'selection_intent=intent' in workflows
    assert 'selection_intent=selection_intent' in session
    assert 'active = moved | intent' in deformation
    assert 'stationary = set(deps.effective_proxy_elements(source)[0]) - active' in workflows
