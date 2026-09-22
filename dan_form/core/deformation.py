"""Deformation preview computation over a captured Operation Rest."""

from __future__ import annotations

import math

from .graph import distances
from .proportional import alpha


def _vec(reference, values):
    """Create the vector type used by the caller without importing Blender."""
    values = tuple(float(value) for value in values)
    try:
        return reference.__class__(values)
    except (TypeError, ValueError):
        return reference.__class__(*values)


def _coords(value):
    return tuple(float(component) for component in value)


def _dot(left, right):
    return sum(a * b for a, b in zip(left, right))


def _cross(left, right):
    return (
        left[1] * right[2] - left[2] * right[1],
        left[2] * right[0] - left[0] * right[2],
        left[0] * right[1] - left[1] * right[0],
    )


def _length(value):
    return math.sqrt(_dot(value, value))


def _normalize(value):
    length = _length(value)
    if length <= 1e-12:
        return None
    return tuple(component / length for component in value)


def _subtract(left, right):
    return tuple(a - b for a, b in zip(left, right))


def _add(left, right):
    return tuple(a + b for a, b in zip(left, right))


def _scale(value, scalar):
    return tuple(component * scalar for component in value)


def _frame(points, center):
    """Build a stable orthonormal frame from a non-collinear point set."""
    vectors = [_subtract(_coords(point), center) for point in points]
    first = next((_normalize(vector) for vector in vectors if _length(vector) > 1e-10), None)
    if first is None:
        return None
    second = None
    for vector in vectors:
        projected = _subtract(vector, _scale(first, _dot(vector, first)))
        second = _normalize(projected)
        if second is not None:
            break
    if second is None:
        return None
    third = _normalize(_cross(first, second))
    if third is None:
        return None
    return (first, second, third)


def _transform_from_samples(p0, targets):
    """Fit a translation/rotation/scale transform from one control's samples.

    A frame-based fit deliberately avoids averaging displacement vectors.  It
    remains well-defined for the common ring-control case where all samples
    lie in one plane, while preserving the transform along the missing normal.
    The returned callable maps a Source-rest coordinate to the transformed
    coordinate.  With fewer than three useful samples it degrades to a
    translation, which is the only unambiguous transform available.
    """
    source_values = [_coords(p0[vertex_id]) for vertex_id in sorted(targets)]
    target_values = [_coords(targets[vertex_id]) for vertex_id in sorted(targets)]
    if not source_values:
        return None
    source_center = tuple(sum(value[index] for value in source_values) / len(source_values)
                          for index in range(3))
    target_center = tuple(sum(value[index] for value in target_values) / len(target_values)
                          for index in range(3))
    source_frame = _frame(source_values, source_center)
    target_frame = _frame(target_values, target_center)
    if source_frame is None or target_frame is None:
        delta = _subtract(target_center, source_center)

        def translate(point):
            return _vec(point, _add(_coords(point), delta))

        return translate

    source_axes = source_frame
    target_axes = target_frame
    scales = []
    for axis in range(3):
        source_lengths = []
        target_lengths = []
        for source, target in zip(source_values, target_values):
            source_lengths.append(abs(_dot(_subtract(source, source_center), source_axes[axis])))
            target_lengths.append(abs(_dot(_subtract(target, target_center), target_axes[axis])))
        source_sum = sum(source_lengths)
        scales.append(sum(target_lengths) / source_sum if source_sum > 1e-10 else 1.0)

    def apply(point):
        local = _subtract(_coords(point), source_center)
        result = target_center
        for axis in range(3):
            result = _add(result, _scale(target_axes[axis], _dot(local, source_axes[axis]) * scales[axis]))
        return _vec(point, result)

    return apply


def compute_preview(
    p0: dict[int, object],
    selected: set[int],
    scope: set[int],
    patches: list[dict],
    edge_vids: dict[int, tuple[int, int]],
    targets: dict[int, object],
    stationary: set[int],
    profile: str,
    radius: float,
    control_groups: dict[str, set[int]] | None = None,
) -> tuple[dict[int, object], int]:
    """Compute one absolute preview without reading or writing Blender data."""
    if set(targets) != set(selected):
        raise ValueError("TARGET_INVALID")
    if any(not all(math.isfinite(float(component)) for component in value) for value in targets.values()):
        raise ValueError("TARGET_INVALID")

    # ``control_groups`` is the canonical transform-field path.  The legacy
    # displacement path remains available for pure callers that have not yet
    # supplied persistent control membership.
    if control_groups is None:
        return _compute_displacement_preview(
            p0, selected, scope, patches, edge_vids, targets, stationary, profile, radius
        )

    transforms = {}
    for control_uuid, members in control_groups.items():
        selected_members = selected.intersection(members)
        samples = {vertex_id: targets[vertex_id] for vertex_id in selected_members}
        transform = _transform_from_samples(p0, samples)
        if transform is None:
            # An enabled but unselected control is an identity transform, not
            # an absent sample.  Keeping it in the field is what pins the
            # opposite boundary of a shared patch.
            transform = lambda point: point.copy()
        transforms[control_uuid] = transform

    output = dict(p0)
    candidates: dict[int, list[object]] = {}
    for patch in patches:
        patch_vertices = {int(vertex_id) for vertex_id in patch["vertex_ids"]}
        seeds = selected.intersection(patch_vertices)
        if not seeds:
            continue
        incident = [str(control_uuid) for control_uuid in patch.get("incident_control_uuids", [])]
        if not incident:
            incident = [control_uuid for control_uuid, members in control_groups.items()
                        if patch_vertices.intersection(members)]
        incident = [control_uuid for control_uuid in incident if control_uuid in control_groups]
        if not incident:
            continue
        # A patch with one incident control is owned by that control.  This is
        # the key semantic difference from averaging boundary displacements.
        control_distances = {
            control_uuid: distances(
                edge_vids,
                patch_vertices,
                patch_vertices.intersection(control_groups[control_uuid]),
            )
            for control_uuid in incident
        }
        # Radius 0 means the complete patch participates, while the original
        # template proportions between the moving and stationary boundaries
        # are preserved.  A free vertex receives the moving field according to
        # its normalized graph distance: 0 at the selected boundary and 1 at
        # the stationary boundary.  Without this factor a pure translation of
        # one cylinder ring was copied unchanged to every free ring, collapsing
        # the spacing instead of forming an even taper.
        selected_distances = distances(edge_vids, patch_vertices, seeds)
        stationary_boundary = stationary.intersection(patch_vertices)
        stationary_distances = distances(edge_vids, patch_vertices, stationary_boundary)
        for vertex_id in patch_vertices:
            if vertex_id in selected or vertex_id in stationary:
                continue
            contributions = []
            for control_uuid in incident:
                transform = transforms.get(control_uuid)
                if transform is None:
                    continue
                distance = control_distances[control_uuid].get(vertex_id)
                if distance is None:
                    continue
                weight = alpha(distance, profile, float(radius))
                if weight <= 0.0:
                    continue
                transformed = transform(p0[vertex_id])
                displacement = transformed - p0[vertex_id]
                if radius <= 0.0:
                    moving_distance = selected_distances.get(vertex_id)
                    stationary_distance = stationary_distances.get(vertex_id)
                    if moving_distance is not None and stationary_distance is not None:
                        span = float(moving_distance + stationary_distance)
                        blend = (float(stationary_distance) / span) if span > 0.0 else 1.0
                        displacement = displacement * blend
                if len(incident) == 1 and radius <= 0.0:
                    contributions = [(displacement, 1.0)]
                    break
                weight = weight / max(float(distance), 1e-12) ** 2
                contributions.append((displacement, weight))
            if contributions:
                total_weight = sum(weight for _value, weight in contributions)
                displacement = None
                for value, weight in contributions:
                    part = value * (weight / total_weight)
                    displacement = part if displacement is None else displacement + part
                candidates.setdefault(vertex_id, []).append(p0[vertex_id] + displacement)

    for vertex_id, values in candidates.items():
        reference = values[0]
        for candidate in values[1:]:
            if any(abs(float(a) - float(b)) > 1e-7 for a, b in zip(reference, candidate)):
                raise ValueError("TARGET_CONFLICT")
        output[vertex_id] = reference
    for vertex_id, target in targets.items():
        output[vertex_id] = target.copy()
    for vertex_id in stationary:
        output[vertex_id] = p0[vertex_id].copy()
    changed = len([vertex_id for vertex_id in scope if output.get(vertex_id) != p0.get(vertex_id)])
    return output, changed


def _compute_displacement_preview(
    p0, selected, scope, patches, edge_vids, targets, stationary, profile, radius
):
    """Compatibility implementation for callers without control groups."""
    # Keep one displacement sample per selected Source vertex.  This path is
    # retained for old fixtures; Blender workflows now pass control_groups.
    displacement = {vertex_id: targets[vertex_id] - p0[vertex_id] for vertex_id in selected}
    output = dict(p0)
    candidates: dict[int, list[object]] = {}
    for patch in patches:
        patch_vertices = {int(vertex_id) for vertex_id in patch["vertex_ids"]}
        seeds = selected.intersection(patch_vertices)
        if not seeds:
            continue
        # Interpolate from every enabled control vertex in this patch.  The
        # stationary samples have a zero displacement and therefore anchor the
        # opposite boundary while a moving loop influences the patch between
        # them.  This is deliberately patch-local: distances never cross an
        # effective control cut.
        samples = (selected | stationary).intersection(patch_vertices)
        sample_distances = {
            sample: distances(edge_vids, patch_vertices, {sample})
            for sample in samples
        }
        moving_distances = distances(edge_vids, patch_vertices, seeds)
        for vertex_id, distance in moving_distances.items():
            if vertex_id in selected or vertex_id in stationary:
                continue
            weight = alpha(distance, profile, float(radius))
            if weight <= 0.0:
                continue
            weighted = None
            weight_sum = 0.0
            for sample, graph_distance in sample_distances.items():
                sample_distance = graph_distance.get(vertex_id)
                if sample_distance is None:
                    continue
                # A non-control vertex is never itself a sample, nevertheless
                # retain the epsilon for degenerate/duplicate graph inputs.
                sample_weight = 1.0 / max(float(sample_distance), 1e-12) ** 2
                weight_sum += sample_weight
                vector = displacement.get(sample)
                if vector is None:
                    continue  # stationary sample: displacement is exactly zero
                if weighted is None:
                    weighted = vector * sample_weight
                else:
                    weighted += vector * sample_weight
            if weighted is not None and weight_sum > 0.0:
                candidate = p0[vertex_id] + (weighted / weight_sum) * weight
                # A free vertex may occur in more than one incident patch.
                # Collect every patch-local candidate and validate agreement
                # before writeback; patch iteration order must never resolve a
                # conflict implicitly.
                candidates.setdefault(vertex_id, []).append(candidate)

    for vertex_id, values in candidates.items():
        reference = values[0]
        for candidate in values[1:]:
            if any(abs(float(a) - float(b)) > 1e-7 for a, b in zip(reference, candidate)):
                raise ValueError("TARGET_CONFLICT")
        output[vertex_id] = reference

    for vertex_id, target in targets.items():
        output[vertex_id] = target.copy()
    for vertex_id in stationary:
        output[vertex_id] = p0[vertex_id].copy()
    changed = len([vertex_id for vertex_id in scope if output.get(vertex_id) != p0.get(vertex_id)])
    return output, changed
