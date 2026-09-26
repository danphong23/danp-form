"""Static checks for the module-extraction boundary.

Blender integration checks still run through the existing live suites.  These
checks make sure the installable package contains every extracted module.
"""

import ast
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
        "operator_actions/structure.py",
        "operator_actions/selection.py",
        "operator_actions/visibility.py",
        "operator_actions/deformation.py",
        "operator_actions/shape_keys.py",
        "operator_actions/navigation.py",
        "ui/overlay.py",
        "ui/panel.py",
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
    panel = (ROOT / "dan_form" / "ui" / "panel.py").read_text(encoding="utf-8")
    assert "runtime.UI_SYNC_GUARD" in panel
    selection = (ROOT / "dan_form" / "operator_actions" / "selection.py").read_text(encoding="utf-8")
    assert "PICK_SESSION" not in registration
    runtime = (ROOT / "dan_form" / "runtime.py").read_text(encoding="utf-8")
    assert "PICK_SESSION" not in runtime


def test_unregistered_legacy_picker_implementation_is_removed() -> None:
    package = "\n".join(path.read_text(encoding="utf-8")
                         for path in (ROOT / "dan_form").rglob("*.py"))
    selection = (ROOT / "dan_form" / "operator_actions" / "selection.py").read_text(encoding="utf-8")
    assert "DANFORM_OT_select_segment" not in package
    assert "DANFORM_OT_pick_selection_tool" not in package
    assert "DANFORM_OT_select_control_at_cursor" not in package
    assert 'bl_idname = "dan_form.select_segment"' not in package
    assert "_PICK_PREVIEW" not in package
    assert "class DANFORM_OT_select_control" in selection


def test_sidebar_classes_have_a_ui_module_boundary() -> None:
    operators = (ROOT / "dan_form" / "operators.py").read_text(encoding="utf-8")
    panel = (ROOT / "dan_form" / "ui" / "panel.py").read_text(encoding="utf-8")
    assert "class DANFORM_PT_sidebar" not in operators
    assert "class DANFORM_PT_sidebar" in panel
    assert "from .ui.panel import" in operators
    assert "_panel.bind(bindings)" in operators


def test_action_operator_domains_have_explicit_bindings() -> None:
    operators = (ROOT / "dan_form" / "operators.py").read_text(encoding="utf-8")
    for name in ("_structure_operators", "_selection_operators",
                 "_visibility_operators", "_deformation_operators",
                 "_shape_key_operators", "_navigation_operators"):
        assert name in operators
    assert "module.bind(bindings)" in operators


def test_danp_classes_are_registered_or_not_defined() -> None:
    registered_tree = ast.parse((ROOT / "dan_form" / "operators.py").read_text(encoding="utf-8"))
    classes_assignment = next(
        node for node in registered_tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "CLASSES"
                for target in node.targets)
    )
    registered = {
        item.id for item in classes_assignment.value.elts
        if isinstance(item, ast.Name)
    }
    declared = set()
    for path in (ROOT / "dan_form").rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        declared.update(
            node.name for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name.startswith("DANFORM_")
        )
    assert declared == registered
