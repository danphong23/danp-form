"""Pure control-network rules.

The functions operate on persistent IDs and plain mappings.  Blender adapters
remain responsible for reading Mesh/BMesh attributes and writing masks.
"""

from __future__ import annotations


def control_intent(control: dict, edge_vids: dict[int, tuple[int, int]], valid_edges: set[int] | None = None):
    """Return edge intent and explicit-node intent for one definition."""
    valid_edges = set(edge_vids) if valid_edges is None else valid_edges
    edge_ids = {int(edge_id) for edge_id in control.get("edge_ids", []) if int(edge_id) in valid_edges}
    endpoints = {vertex_id for edge_id in edge_ids for vertex_id in edge_vids[edge_id]}
    node_ids = {int(vertex_id) for vertex_id in control.get("vertex_ids", [])}
    if edge_ids:
        node_ids.difference_update(endpoints)
    return edge_ids, node_ids


def control_effective(
    control: dict,
    edge_vids: dict[int, tuple[int, int]],
    hidden_vertices: set[int],
    hidden_edges: set[int],
    valid_edges: set[int] | None = None,
):
    """Return effective vertices and edges after canonical masks."""
    if not bool(control.get("enabled", True)):
        return set(), set()
    # Version 3 keeps masks on the definition that owns the membership.  The
    # optional arguments remain for reading legacy data during migration.
    hidden_vertices = set(hidden_vertices) | {
        int(value) for value in control.get("hidden_vertex_ids", [])
    }
    hidden_edges = set(hidden_edges) | {
        int(value) for value in control.get("hidden_edge_ids", [])
    }
    edge_ids, explicit_nodes = control_intent(control, edge_vids, valid_edges)
    effective_edges = set()
    effective_vertices = set(explicit_nodes) - set(hidden_vertices)
    for edge_id in edge_ids:
        endpoints = set(edge_vids[edge_id])
        if edge_id in hidden_edges or endpoints.intersection(hidden_vertices):
            continue
        effective_edges.add(edge_id)
        effective_vertices.update(endpoints)
    return effective_vertices, effective_edges


def effective_elements(
    controls: list[dict],
    vertex_ids: set[int],
    edge_vids: dict[int, tuple[int, int]],
    hidden_vertices: set[int],
    hidden_edges: set[int],
):
    """Resolve the visible controller geometry from Source-backed definitions."""
    visible_vertices = set()
    visible_edges = set()
    valid_edges = set(edge_vids)
    for control in controls:
        effective_vertices, effective_control_edges = control_effective(
            control, edge_vids, hidden_vertices, hidden_edges, valid_edges
        )
        visible_edges.update(effective_control_edges)
        visible_vertices.update(effective_vertices)
        # ``control_effective`` already separates explicit standalone points
        # from edge endpoints.  Do not add the raw ``vertex_ids`` again here:
        # doing so resurrects every endpoint after its edge is hidden and makes
        # bulk Hide/Show unable to distinguish an empty network from a network
        # containing orphaned vertices.
    return sorted(visible_vertices.intersection(vertex_ids)), sorted(visible_edges)


def selection_state(membership: set[int], selected_ids: set[int]) -> str:
    """Classify a control's persistent vertex membership against a mesh selection.

    Empty or fully hidden memberships are deliberately unselected; otherwise
    the usual subset/intersection rules distinguish full, partial and none.
    """
    membership = set(membership)
    selected_ids = set(selected_ids)
    if not membership:
        return "NONE"
    overlap = membership & selected_ids
    if not overlap:
        return "NONE"
    return "FULL" if membership <= selected_ids else "PARTIAL"
