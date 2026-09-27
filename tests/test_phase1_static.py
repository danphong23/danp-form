"""Static checks for the Phase 1 package; live checks run in the open Blender session."""

from pathlib import Path


ROOT = Path(__file__).parents[1]


def package_source() -> str:
    return "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "dan_form").rglob("*.py"))


def test_manifest_and_package_exist() -> None:
    assert (ROOT / "blender_manifest.toml").is_file()
    assert (ROOT / "dan_form" / "__init__.py").is_file()


def test_distribution_license_matches_manifest() -> None:
    manifest = (ROOT / "blender_manifest.toml").read_text(encoding="utf-8")
    license_text = (ROOT / "LICENSE.md").read_text(encoding="utf-8")
    assert '"SPDX:GPL-3.0-or-later"' in manifest
    assert "GPL-3.0-or-later" in license_text
    assert "GNU GENERAL PUBLIC LICENSE" in license_text
    assert "END OF TERMS AND CONDITIONS" in license_text
    assert "No production code is included" not in license_text


def test_third_party_notice_is_packaged() -> None:
    from scripts.release_package import PACKAGE_ROOT_FILES

    notices = (ROOT / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "THIRD_PARTY_NOTICES.md" in PACKAGE_ROOT_FILES
    assert "NumPy is not included" in notices
    assert "pure-Python fallback" in notices


def test_distribution_sources_do_not_leak_machine_paths_or_test_asset_names() -> None:
    from scripts.release_package import _validate_public_content, package_entries

    entries = package_entries()
    assert {"README.md", "README_VI.md", "CHANGELOG.md"}.issubset(entries)
    assert not any(member.startswith(("docs/", "tasks/", "tests/")) for member in entries)
    for member, path in entries.items():
        _validate_public_content(member, path.read_bytes())


def test_release_report_redacts_local_machine_paths() -> None:
    import runpy

    runner = runpy.run_path(str(ROOT / "tests" / "run_release_gates.py"))
    sanitize = runner["_sanitize_report_value"]
    sample = {
        "temp": r"C:\Users\abc\AppData\Local\Temp\danp\fixture.blend",
        "project": r"C:\Users\abc\.AI\Code\danp-animation\Project\character.blend",
    }
    cleaned = sanitize(sample)
    assert cleaned["temp"] == r"<TEMP>\danp\fixture.blend"
    assert cleaned["project"] == r"<PROJECT_ROOT>\Project\character.blend"


def test_large_preview_benchmark_uses_the_source_owning_scene() -> None:
    benchmark = (ROOT / "tests" / "benchmark_h09_large_preview.py").read_text(encoding="utf-8")
    assert "scene.objects.get(controller.name) == controller" in benchmark
    assert "window.scene = source_scene" in benchmark
    assert "source_scene.view_layers.get(window.view_layer.name) is None" in benchmark


def test_destructive_selection_fixture_refuses_live_ui() -> None:
    fixture = (ROOT / "tests" / "live_control_multiselect.py").read_text(encoding="utf-8")
    guard = fixture.index("if not bpy.app.background:")
    registration = fixture.index("addon.register()")
    fixture_creation = fixture.index('bpy.data.meshes.new("Selection Fixture Mesh")')
    assert guard < registration < fixture_creation


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
        "DANFORM_OT_hide_unselected",
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
