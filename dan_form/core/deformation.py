"""Deformation preview computation over a captured Operation Rest."""

from __future__ import annotations

import math

from .graph import metric_distances
from .harmonic import solve_displacements
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
    """Compute an absolute preview from individual control-vertex positions.

    Logical control groups identify vertices for selection; they do not affect
    the deformation. Each patch uses exact moved and stationary boundaries.
    """
    if set(targets) != set(selected) or selected.intersection(stationary):
        raise ValueError("TARGET_INVALID")
    if any(not all(math.isfinite(float(component)) for component in value)
           for value in targets.values()):
        raise ValueError("TARGET_INVALID")

    output = dict(p0)
    candidates: dict[int, list[object]] = {}
    for patch in patches:
        patch_vertices = {int(vertex_id) for vertex_id in patch["vertex_ids"]}
        patch_targets = {vertex_id: targets[vertex_id]
                         for vertex_id in selected.intersection(patch_vertices)}
        if not patch_targets:
            continue
        patch_stationary = stationary.intersection(patch_vertices)

        # With no fixed boundary, a coherent whole-control G/R/S can extend
        # through the patch as a rigid or affine transform. One or two samples
        # are underdetermined, so retain their translation fit. Nonuniform
        # Proportional Editing uses the vertex-constrained solve below.
        transform = None
        if not patch_stationary:
            transform = _transform_from_samples(p0, patch_targets)
            if transform is not None and len(patch_targets) > 2:
                for vertex_id, target in patch_targets.items():
                    predicted = transform(p0[vertex_id])
                    if math.dist(tuple(predicted), tuple(target)) > 1e-6:
                        transform = None
                        break

        if transform is not None:
            distances = metric_distances(edge_vids, patch_vertices, set(patch_targets), p0)
            for vertex_id, distance in distances.items():
                if vertex_id in patch_targets:
                    continue
                strength = alpha(distance, profile, float(radius))
                if strength <= 0.0:
                    continue
                rest = _coords(p0[vertex_id])
                transformed = _coords(transform(p0[vertex_id]))
                candidate = _vec(p0[vertex_id], (
                    rest[axis] + strength * (transformed[axis] - rest[axis])
                    for axis in range(3)
                ))
                candidates.setdefault(vertex_id, []).append(candidate)
            continue

        displacements = solve_displacements(
            p0, patch_vertices, edge_vids, patch_targets, patch_stationary
        )
        distances = (metric_distances(edge_vids, patch_vertices, set(patch_targets), p0)
                     if radius > 0.0 else {})
        for vertex_id, displacement in displacements.items():
            strength = (alpha(distances.get(vertex_id, math.inf), profile, float(radius))
                        if radius > 0.0 else 1.0)
            if strength <= 0.0:
                continue
            rest = _coords(p0[vertex_id])
            candidate = _vec(p0[vertex_id], (
                rest[axis] + strength * displacement[axis] for axis in range(3)
            ))
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
    changed = sum(output.get(vertex_id) != p0.get(vertex_id) for vertex_id in scope)
    return output, changed