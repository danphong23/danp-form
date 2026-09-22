"""Application workflows for Source-backed control operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import bmesh
import bpy
from mathutils import Vector

from ..constants import *
from ..core.deformation import compute_preview
from ..core.operation import OperationTransform, targets_from_transform


@dataclass(frozen=True)
class WorkflowDeps:
    transactions: dict
    overlay_cache: dict
    patch_overlay_cache: dict
    validate_source_topology: Callable
    controller_selected_source_ids: Callable
    source_positions: Callable
    patch_partition: Callable
    effective_proxy_elements: Callable
    source_edge_vids: Callable
    source_id_maps: Callable
    sync_proxy: Callable
    control_intent: Callable
    control_effective: Callable
    controls: Callable
    hidden: Callable
    json_set: Callable
    source_controller_pairs: Callable


def update_revision(source: bpy.types.Object) -> None:
    source[NETWORK_REVISION_KEY] = int(source.get(NETWORK_REVISION_KEY, 0)) + 1


def deform_begin(source: bpy.types.Object, controller: bpy.types.Object, deps) -> dict:
    """Capture one immutable operation rest and its incident patch scope."""
    key = source.as_pointer()
    if key in deps.transactions and not deps.transactions[key].get("closed"):
        raise ValueError("OPERATION_BUSY")
    if source.mode not in {"OBJECT", "EDIT"} or controller.mode != "EDIT":
        raise ValueError("CONTROLLER_EDIT_MODE_REQUIRED")
    deps.validate_source_topology(source)
    selected = deps.controller_selected_source_ids(controller)
    current = deps.source_positions(source)
    hidden = deps.hidden(source, HIDDEN_VIDS_KEY)
    selected.difference_update(hidden)
    if not selected:
        raise ValueError("CONTROL_HIDDEN")
    partition = deps.patch_partition(source)
    scope = set(selected)
    for patch in partition["patches"]:
        if selected.intersection(set(patch["vertex_ids"])):
            scope.update(int(v) for v in patch["vertex_ids"])
    tx = {
        "source": source.as_pointer(), "controller": controller.as_pointer(),
        "source_uuid": source.get(SOURCE_UUID_KEY), "topology": source.get(TOPOLOGY_KEY),
        "network": source.get(NETWORK_REVISION_KEY), "p0": current,
        "selected": selected, "selection": set(selected), "scope": scope,
        "closed": False, "preview": None,
        "control_groups": {
            str(control.get("control_uuid")): set(deps.control_effective(source, control)[0])
            for control in deps.controls(source)
        },
    }
    deps.transactions[key] = tx
    return tx


def write_source_positions(source: bpy.types.Object, positions: dict[int, Vector], deps) -> bool:
    vids, _ = deps.source_id_maps(source)
    changed = False
    if source.mode == "EDIT":
        bm = bmesh.from_edit_mesh(source.data)
        bm.verts.ensure_lookup_table(); layer = bm.verts.layers.int.get(VID_ATTR)
        if layer is None: raise ValueError("SOURCE_ID_LAYERS_MISSING")
        for vert in bm.verts:
            position = positions.get(int(vert[layer]))
            if position is not None and (vert.co - position).length_squared > 1e-16:
                vert.co = position
                changed = True
        if changed:
            bmesh.update_edit_mesh(source.data, loop_triangles=False, destructive=False)
    else:
        for vid, position in positions.items():
            index = vids.get(int(vid))
            if index is not None and (source.data.vertices[index].co - position).length_squared > 1e-16:
                source.data.vertices[index].co = position
                changed = True
        if changed:
            source.data.update()
    return changed


def deform_update(source: bpy.types.Object, controller: bpy.types.Object, deps,
                   delta=(0.0, 0.0, 0.0), profile="LINEAR", radius=0.0,
                   targets: dict[int, Vector] | None = None,
                   sync_controller: bool = True,
                   operation_transform: OperationTransform | None = None) -> dict:
    key = source.as_pointer(); tx = deps.transactions.get(key)
    if tx is None or tx.get("closed"): raise ValueError("OPERATION_CLOSED")
    if source.get(TOPOLOGY_KEY) != tx["topology"] or source.get(NETWORK_REVISION_KEY) != tx["network"]:
        raise ValueError("OPERATION_STALE")
    p0 = tx["p0"]
    # ``None`` means the ordinary delta path.  An explicitly supplied empty
    # mapping is a valid no-op sample when Proportional Editing has returned
    # every Controller vertex to its pre-transform coordinates.
    if targets is None and operation_transform is not None:
        targets = targets_from_transform(p0, tx["selected"], operation_transform)
    if targets is None:
        targets = {vid: p0[vid] + Vector(delta) for vid in tx["selected"]}
    selected = set(targets)
    partition = deps.patch_partition(source)
    for patch in partition["patches"]:
        if selected.intersection(set(patch["vertex_ids"])):
            tx["scope"].update(int(v) for v in patch["vertex_ids"])
    stationary = set(deps.effective_proxy_elements(source)[0]) - selected
    output, changed_vertices = compute_preview(
        p0,
        selected,
        set(tx["scope"]),
        partition["patches"],
        deps.source_edge_vids(source),
        targets,
        stationary,
        profile,
        float(radius),
        control_groups=tx.get("control_groups"),
    )
    write_source_positions(source, {vid: output[vid] for vid in tx["scope"] if vid in output}, deps)
    # During native Controller Edit transforms Blender owns the proxy
    # coordinates.  Syncing it back here would erase the live G/R/S preview;
    # the bridge commits/cancels the proxy only after Blender finishes.
    if sync_controller:
        deps.sync_proxy(source, controller)
    deps.overlay_cache.clear(); deps.patch_overlay_cache.pop(source.as_pointer(), None)
    tx["preview"] = output
    return {"changed_vertices": changed_vertices,
            "selected_vertices": len(selected), "scope_vertices": len(tx["scope"])}


def deform_commit(source: bpy.types.Object, deps) -> None:
    tx = deps.transactions.get(source.as_pointer())
    if tx is None or tx.get("closed"): raise ValueError("OPERATION_CLOSED")
    tx["closed"] = True; deps.transactions.pop(source.as_pointer(), None)


def deform_cancel(source: bpy.types.Object, controller: bpy.types.Object, deps) -> None:
    tx = deps.transactions.get(source.as_pointer())
    if tx is None or tx.get("closed"): raise ValueError("OPERATION_CLOSED")
    write_source_positions(source, tx["p0"], deps)
    deps.sync_proxy(source, controller)
    tx["closed"] = True; deps.transactions.pop(source.as_pointer(), None)


def mutate_masks(source: bpy.types.Object, vertex_ids: set[int], edge_ids: set[int], reveal: bool, deps) -> bool:
    deps.validate_source_topology(source)
    definitions = deps.controls(source)
    before = repr(definitions)
    for control in definitions:
        members = set(int(value) for value in control.get("vertex_ids", []))
        edges = set(int(value) for value in control.get("edge_ids", []))
        hidden_vertices = set(int(value) for value in control.get("hidden_vertex_ids", []))
        hidden_edges = set(int(value) for value in control.get("hidden_edge_ids", []))
        if reveal and not vertex_ids and not edge_ids:
            control["enabled"] = True
            hidden_vertices.clear()
            hidden_edges.clear()
        elif reveal:
            hidden_vertices.difference_update(vertex_ids.intersection(members))
            hidden_edges.difference_update(edge_ids.intersection(edges))
            edge_vids = deps.source_edge_vids(source)
            for edge_id in edge_ids:
                hidden_vertices.difference_update(edge_vids.get(edge_id, ()))
        else:
            hidden_vertices.update(vertex_ids.intersection(members))
            hidden_edges.update(edge_ids.intersection(edges))
        control["hidden_vertex_ids"] = sorted(hidden_vertices)
        control["hidden_edge_ids"] = sorted(hidden_edges)
    changed = before != repr(definitions)
    if changed:
        deps.json_set(source, CONTROLS_KEY, definitions)
        # Clear legacy shared masks if an old file reaches this path before its
        # explicit initialization migration.
        deps.json_set(source, HIDDEN_VIDS_KEY, [])
        deps.json_set(source, HIDDEN_EIDS_KEY, [])
        update_revision(source)
    return changed


def mutate_control_visibility(source: bpy.types.Object, control: dict, reveal: bool, deps) -> bool:
    definitions = deps.controls(source)
    target = next((item for item in definitions
                   if item.get("control_uuid") == control.get("control_uuid")), None)
    if target is None:
        return False
    before = repr(target)
    was_enabled = bool(target.get("enabled", True))
    target["enabled"] = bool(reveal)
    target.setdefault("hidden_vertex_ids", [])
    target.setdefault("hidden_edge_ids", [])
    # An enabled definition whose every member is masked is a legacy/partial
    # hide result.  Clicking its eye is an explicit reveal, so clear those
    # masks.  A definition disabled by the eye retains its partial masks and
    # restores them when enabled again.
    if reveal and was_enabled:
        target["hidden_vertex_ids"] = []
        target["hidden_edge_ids"] = []
    if repr(target) != before:
        deps.json_set(source, CONTROLS_KEY, definitions)
        update_revision(source)
        return True
    return False


def mutate_control_masks(source: bpy.types.Object, control: dict, vertex_ids: set[int],
                         edge_ids: set[int], reveal: bool, deps) -> bool:
    """Hide/reveal selected membership only inside one control definition."""
    definitions = deps.controls(source)
    target = next((item for item in definitions
                   if item.get("control_uuid") == control.get("control_uuid")), None)
    if target is None:
        return False
    members = set(int(value) for value in target.get("vertex_ids", []))
    edges = set(int(value) for value in target.get("edge_ids", []))
    hidden_vertices = set(int(value) for value in target.get("hidden_vertex_ids", []))
    hidden_edges = set(int(value) for value in target.get("hidden_edge_ids", []))
    before = (hidden_vertices.copy(), hidden_edges.copy())
    if reveal:
        hidden_vertices.difference_update(vertex_ids.intersection(members))
        hidden_edges.difference_update(edge_ids.intersection(edges))
    else:
        hidden_vertices.update(vertex_ids.intersection(members))
        hidden_edges.update(edge_ids.intersection(edges))
    target["hidden_vertex_ids"] = sorted(hidden_vertices)
    target["hidden_edge_ids"] = sorted(hidden_edges)
    changed = before != (hidden_vertices, hidden_edges)
    if changed:
        deps.json_set(source, CONTROLS_KEY, definitions)
        update_revision(source)
    return changed


def prune_masks_after_remove(source: bpy.types.Object, deps) -> None:
    definitions = deps.controls(source)
    edge_vids = deps.source_edge_vids(source)
    for control in definitions:
        members = set(int(value) for value in control.get("vertex_ids", []))
        edges = set(int(value) for value in control.get("edge_ids", []))
        endpoints = {vid for eid in edges for vid in edge_vids.get(eid, ())}
        allowed = members | endpoints
        control["hidden_vertex_ids"] = sorted(
            set(int(value) for value in control.get("hidden_vertex_ids", [])) & allowed
        )
        control["hidden_edge_ids"] = sorted(
            set(int(value) for value in control.get("hidden_edge_ids", [])) & edges
        )
        control["enabled"] = bool(control.get("enabled", True))
    deps.json_set(source, CONTROLS_KEY, definitions)
    deps.json_set(source, HIDDEN_VIDS_KEY, [])
    deps.json_set(source, HIDDEN_EIDS_KEY, [])


def sync_scene(scene: bpy.types.Scene, deps) -> None:
    for source, controller in deps.source_controller_pairs():
        try:
            deps.sync_proxy(source, controller)
        except (KeyError, ValueError):
            pass
