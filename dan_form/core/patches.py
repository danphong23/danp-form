"""Pure face-graph partitioning for Source-backed control cuts."""

from __future__ import annotations

import hashlib


def partition_faces(
    faces: list[dict],
    cut_edges: set[int],
    controls: list[dict],
    control_incidence: list[tuple[str, set[int], set[int], set[int]]],
    revision: int = 0,
) -> dict:
    """Return connected face patches and control-to-patch membership."""
    face_by_edge: dict[int, list[int]] = {}
    for index, face in enumerate(faces):
        for edge_id in face["edge_ids"]:
            face_by_edge.setdefault(int(edge_id), []).append(index)

    adjacency = [set() for _ in faces]
    for edge_id, incident in face_by_edge.items():
        if edge_id in cut_edges:
            continue
        for left in incident:
            adjacency[left].update(other for other in incident if other != left)

    face_patch: dict[int, str] = {}
    patches: list[dict] = []
    for seed in range(len(faces)):
        if seed in face_patch:
            continue
        stack = [seed]
        component = set()
        while stack:
            current = stack.pop()
            if current in component:
                continue
            component.add(current)
            stack.extend(adjacency[current] - component)
        face_ids = sorted(faces[index]["face_id"] for index in component)
        patch_id = "p:" + hashlib.sha1("|".join(face_ids).encode("utf-8")).hexdigest()[:16]
        for index in component:
            face_patch[index] = patch_id
        component_edges = sorted({edge_id for index in component for edge_id in faces[index]["edge_ids"]})
        component_vertices = sorted({vertex_id for index in component for vertex_id in faces[index]["vertex_ids"]})
        boundary_edges = sorted({
            edge_id for edge_id in component_edges
            if len(face_by_edge.get(edge_id, [])) != 2
            or any(face_patch.get(other) != patch_id for other in face_by_edge.get(edge_id, []))
        })
        patches.append({
            "patch_id": patch_id,
            "face_ids": face_ids,
            "face_indices": sorted(component),
            "vertex_ids": component_vertices,
            "edge_ids": component_edges,
            "boundary_edge_ids": boundary_edges,
            "incident_control_uuids": [],
        })

    for patch in patches:
        patch_edges = set(patch["boundary_edge_ids"])
        patch_vertices = set(patch["vertex_ids"])
        incident = []
        for control_uuid, effective_vertices, effective_control_edges, explicit_nodes in control_incidence:
            touches = patch_edges.intersection(effective_control_edges)
            touches.update(patch_vertices.intersection(effective_vertices.intersection(explicit_nodes)))
            if touches:
                incident.append(control_uuid)
        patch["incident_control_uuids"] = sorted(incident)

    return {
        "revision": int(revision),
        "patches": patches,
        "face_patch_ids": {faces[index]["face_id"]: patch_id for index, patch_id in face_patch.items()},
        "edge_patch_ids": {
            str(edge_id): sorted({face_patch[index] for index in incident})
            for edge_id, incident in face_by_edge.items()
        },
        "control_patch_ids": {
            str(control.get("control_uuid")): sorted({
                patch["patch_id"] for patch in patches
                if str(control.get("control_uuid")) in patch["incident_control_uuids"]
            })
            for control in controls
        },
    }

