"""Pure control-network regression tests (no Blender process required)."""

import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "dan_form_core_controls",
    ROOT / "dan_form" / "core" / "controls.py",
)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_hidden_edge_endpoints_do_not_become_standalone_vertices():
    controls = [{"edge_ids": [10], "vertex_ids": [1, 2]}]
    edge_vids = {10: (1, 2)}

    vertices, edges = MODULE.effective_elements(
        controls,
        {1, 2},
        edge_vids,
        hidden_vertices=set(),
        hidden_edges={10},
    )

    assert vertices == []
    assert edges == []


def test_standalone_point_remains_visible_until_its_node_is_hidden():
    controls = [{"edge_ids": [10], "vertex_ids": [1, 2, 99]}]
    edge_vids = {10: (1, 2)}

    vertices, edges = MODULE.effective_elements(
        controls,
        {1, 2, 99},
        edge_vids,
        hidden_vertices=set(),
        hidden_edges={10},
    )

    assert vertices == [99]
    assert edges == []


def test_revealed_edge_restores_endpoints_and_edge():
    controls = [{"edge_ids": [10], "vertex_ids": [1, 2]}]
    vertices, edges = MODULE.effective_elements(
        controls,
        {1, 2},
        {10: (1, 2)},
        hidden_vertices=set(),
        hidden_edges=set(),
    )

    assert vertices == [1, 2]
    assert edges == [10]


def test_control_selection_is_full_partial_none_and_empty_is_none():
    assert MODULE.selection_state({1, 2}, {1, 2, 3}) == "FULL"
    assert MODULE.selection_state({1, 2}, {2, 3}) == "PARTIAL"
    assert MODULE.selection_state({1, 2}, {3}) == "NONE"
    assert MODULE.selection_state(set(), {1, 2, 3}) == "NONE"


def test_overlapping_control_memberships_can_both_be_fully_selected():
    selected = {2, 3}
    assert MODULE.selection_state({2, 3}, selected) == "FULL"
    assert MODULE.selection_state({1, 2, 3}, selected) == "PARTIAL"


def test_hidden_membership_is_not_vacuously_selected():
    visible_membership = set()
    assert MODULE.selection_state(visible_membership, {1, 2, 3}) == "NONE"


def test_overlapping_controls_keep_shared_geometry_when_one_definition_hides_it():
    controls = [
        {
            "control_uuid": "a",
            "edge_ids": [10],
            "vertex_ids": [1, 2],
            "hidden_vertex_ids": [1],
        },
        {
            "control_uuid": "b",
            "edge_ids": [10],
            "vertex_ids": [1, 2],
            "hidden_vertex_ids": [],
        },
    ]

    vertices, edges = MODULE.effective_elements(
        controls,
        {1, 2},
        {10: (1, 2)},
        hidden_vertices=set(),
        hidden_edges=set(),
    )

    assert vertices == [1, 2]
    assert edges == [10]


def test_disabled_definition_releases_only_its_membership():
    controls = [
        {"control_uuid": "a", "edge_ids": [10], "vertex_ids": [1, 2], "enabled": False},
        {"control_uuid": "b", "edge_ids": [], "vertex_ids": [2], "enabled": True},
    ]

    vertices, edges = MODULE.effective_elements(
        controls,
        {1, 2},
        {10: (1, 2)},
        hidden_vertices=set(),
        hidden_edges=set(),
    )

    assert vertices == [2]
    assert edges == []
