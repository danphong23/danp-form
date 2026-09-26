"""Static checks for the Phase 1 package; live checks run in the open Blender session."""

from pathlib import Path


ROOT = Path(__file__).parents[1]


def package_source() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "dan_form").rglob("*.py"))


def test_manifest_and_package_exist() -> None:
    assert (ROOT / "blender_manifest.toml").is_file()
    assert (ROOT / "dan_form" / "__init__.py").is_file()


def test_phase1_contract_symbols() -> None:
    source = package_source()
    for symbol in (
        "DANFORM_OT_initialize",
        "DANFORM_OT_remove_controller",
        "DANFORM_PT_sidebar",
        "dan_form_source",
        "dan_form_controller",
        "matrix_parent_inverse",
    ):
        assert symbol in source


def test_phase2_contract_symbols() -> None:
    source = package_source()
    for symbol in (
        "dan_form_vid",
        "dan_form_eid",
        "dan_form_proxy_vid",
        "dan_form_proxy_eid",
        "DANFORM_OT_create_control",
        "DANFORM_OT_hide_selected",
        "DANFORM_OT_reveal",
        "_depsgraph_update_post",
        "STALE_MAPPING",
        "_context_source",
        "DANFORM_OT_rename_control",
        "DANFORM_OT_select_control",
        "_update_overlay_display",
        "DANFORM_OT_delete_control",
        "hidden_vertex_ids",
        "hidden_edge_ids",
        "migrate_control_schema",
        'toggle.reveal = item.state == "Hidden"',
        "_draw_control_overlay",
        "controller_edit",
        "bmesh.from_edit_mesh(controller.data)",
        "dan_form_overlay_enabled",
        'gpu.state.depth_test_set("NONE" if xray else "LESS_EQUAL")',
        'gpu.state.depth_test_set(previous_depth)',
    ):
        assert symbol in source


def test_phase2_ux_documents_exist() -> None:
    assert (ROOT / "docs" / "roadmap" / "phase-02-ux-upgrade.md").is_file()
    assert (ROOT / "tasks" / "phase-02-ux-upgrade.md").is_file()


def test_native_control_list_contract_symbols() -> None:
    source = package_source()
    for symbol in (
        "DANFORM_PG_ControlItem",
        "DANFORM_UL_controls",
        "DANFORM_MT_control_menu",
        "DANFORM_OT_sync_control",
        "DANFORM_OT_move_control",
        "dan_form_control_items",
        "dan_form_control_index",
        "_sync_ui_list",
        "_control_selection_states",
        "selected_source_vertex_ids",
        "Shift-click to add or remove it; click it again to deselect",
        "_UI_SELECTION_STATES",
    ):
        assert symbol in source
    select = source.split("class DANFORM_OT_select_control(", 1)[1].split("class ", 1)[0]
    assert 'self.add_to_selection = bool(event.shift)' in select
    assert 'bl_options = {"REGISTER"}' in select
    assert 'text=item.control_name' in source
    assert '"dan_form.rename_control"' in source
    assert (ROOT / "docs" / "roadmap" / "phase-02-native-list-ux.md").is_file()
    assert (ROOT / "tasks" / "phase-02-native-list-ux.md").is_file()


def test_phase3_patch_contract_symbols() -> None:
    source = package_source()
    for symbol in (
        "_source_face_records",
        "_patch_partition",
        "_patches_for_control",
        "_patch_overlay_batches",
        "_invalidate_patch_cache",
        "dan_form_patches_enabled",
        "PATCH_COLORS",
    ):
        assert symbol in source
    assert (ROOT / "tasks" / "phase-03-patch-visualization.md").is_file()
