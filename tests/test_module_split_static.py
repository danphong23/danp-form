"""Static checks for the module-extraction boundary.

Blender integration checks still run through the existing live suites.  These
checks make sure the installable package contains every extracted module.
"""

from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_extracted_modules_exist() -> None:
    for relative in (
        "constants.py",
        "runtime.py",
        "storage.py",
        "core/controls.py",
        "core/graph.py",
        "core/patches.py",
        "core/proportional.py",
        "blender/context.py",
        "blender/mesh.py",
        "blender/proxy.py",
        "blender/selection.py",
        "blender/workflows.py",
        "blender/lifecycle.py",
        "registration.py",
        "operators.py",
        "ui/overlay.py",
    ):
        assert (ROOT / "dan_form" / relative).is_file()


def test_facade_uses_extracted_boundaries() -> None:
    source = (ROOT / "dan_form" / "__init__.py").read_text(encoding="utf-8")
    for symbol in (
        "from . import runtime as _runtime",
        "from .storage import controls as _controls",
        "from .core.controls import effective_elements as _core_effective_elements",
        "from .core.patches import partition_faces as _core_partition_faces",
        "from .blender.mesh import _source_id_maps as _source_id_maps",
        "from .blender.proxy import rebuild_proxy as _proxy_rebuild",
        "from .registration import register as _register_addon",
        "from . import operators as _operators",
        "from .ui import overlay as _overlay",
        "from .blender.workflows import WorkflowDeps as _WorkflowDeps",
    ):
        assert symbol in source


def test_edit_mode_ids_are_written_to_live_bmesh() -> None:
    source = (ROOT / "dan_form" / "blender" / "mesh.py").read_text(encoding="utf-8")
    for symbol in (
        'if source.mode == "EDIT":',
        "bmesh.from_edit_mesh(mesh)",
        "bm.verts.layers.int.new(VID_ATTR)",
        "bm.edges.layers.int.new(EID_ATTR)",
        "bmesh.update_edit_mesh(mesh, loop_triangles=False, destructive=False)",
    ):
        assert symbol in source


def test_mutable_ui_state_uses_shared_runtime() -> None:
    facade = (ROOT / "dan_form" / "__init__.py").read_text(encoding="utf-8")
    operators = (ROOT / "dan_form" / "operators.py").read_text(encoding="utf-8")
    registration = (ROOT / "dan_form" / "registration.py").read_text(encoding="utf-8")
    assert "_runtime.UI_SYNC_GUARD = True" in facade
    assert "runtime.UI_SYNC_GUARD" in operators
    assert "runtime.PICK_SESSION" in operators
    assert "api._runtime.PICK_SESSION += 1" in registration
