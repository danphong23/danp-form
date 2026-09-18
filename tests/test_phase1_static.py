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
