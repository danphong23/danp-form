"""Static checks for the Phase 1 package; live checks run in the open Blender session."""

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_manifest_and_package_exist() -> None:
    assert (ROOT / "blender_manifest.toml").is_file()
    assert (ROOT / "dan_form" / "__init__.py").is_file()


def test_phase1_contract_symbols() -> None:
    source = (ROOT / "dan_form" / "__init__.py").read_text(encoding="utf-8")
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
    source = (ROOT / "dan_form" / "__init__.py").read_text(encoding="utf-8")
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
        "DANFORM_OT_delete_control",
        "_draw_control_overlay",
        "dan_form_overlay_enabled",
    ):
        assert symbol in source


def test_phase2_ux_documents_exist() -> None:
    assert (ROOT / "docs" / "roadmap" / "phase-02-ux-upgrade.md").is_file()
    assert (ROOT / "tasks" / "phase-02-ux-upgrade.md").is_file()
