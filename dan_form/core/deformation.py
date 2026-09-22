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


def _solve_3x3(matrix, rhs):
    """Solve one 3x3 linear system with deterministic pivoting."""
    augmented = [list(matrix[row]) + [float(rhs[row])] for row in range(3)]
    for column in range(3):
        pivot = max(range(column, 3), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) <= 1e-14:
            return None
        if pivot != column:
            augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        divisor = augmented[column][column]
        for index in range(column, 4):
            augmented[column][index] /= divisor
        for row in range(3):
            if row == column:
                continue
            factor = augmented[row][column]
            if factor == 0.0:
                continue
            for index in range(column, 4):
                augmented[row][index] -= factor * augmented[column][index]
    return tuple(augmented[row][3] for row in range(3))


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
    """Fit one continuous affine transform from one control's samples.

    Blender's non-uniform Scale can contain shear when viewed in a control's
    local plane.  A frame-only fit represents only rotation plus three axis
    scales, so its residual used to switch abruptly to the harmonic solver.
    Here the measured samples determine the affine part directly.  A small
    regularization toward the frame fit supplies the missing normal of a
    planar ring without changing the measured in-plane targets.  The same
    formula is used for every scale/rotation and every control shape.
    """
    source_values = [_coords(p0[vertex_id]) for vertex_id in sorted(targets)]
    target_values = [_coords(targets[vertex_id]) for vertex_id in sorted(targets)]
    if not source_values:
        return None
    source_center = tuple(sum(value[index] for value in source_values) / len(source_values)
                          for index in range(3))
    target_center = tuple(sum(value[index] for value in target_values) / len(target_values)
                          for index in range(3))
    if len(source_values) < 3:
        delta = _subtract(target_center, source_center)

        def translate(point):
            return _vec(point, _add(_coords(point), delta))

        return translate

    source_frame = _frame(source_values, source_center)
    target_frame = _frame(target_values, target_center)
    prior = ((1.0, 0.0, 0.0),
             (0.0, 1.0, 0.0),
             (0.0, 0.0, 1.0))
    if source_frame is not None and target_frame is not None:
        source_axes = source_frame
        target_axes = target_frame
        scales = []
        for axis in range(3):
            source_sum = sum(
                abs(_dot(_subtract(source, source_center), source_axes[axis]))
                for source in source_values
            )
            target_sum = sum(
                abs(_dot(_subtract(target, target_center), target_axes[axis]))
                for target in target_values
            )
            scales.append(target_sum / source_sum if source_sum > 1e-10 else 1.0)
        prior = tuple(
            tuple(sum(target_axes[axis][row] * source_axes[axis][column] * scales[axis]
                      for axis in range(3)) for column in range(3))
            for row in range(3)
        )

    covariance = [[0.0] * 3 for _ in range(3)]
    cross = [[0.0] * 3 for _ in range(3)]
    for source, target in zip(source_values, target_values):
        source_delta = _subtract(source, source_center)
        target_delta = _subtract(target, target_center)
        for row in range(3):
            for column in range(3):
                covariance[row][column] += source_delta[row] * source_delta[column]
                cross[row][column] += target_delta[row] * source_delta[column]
    regularization = max(1.0, sum(covariance[index][index] for index in range(3))) * 1e-10
    system = [
        [covariance[row][column] + (regularization if row == column else 0.0)
         for column in range(3)]
        for row in range(3)
    ]
    affine_rows = []
    for row in range(3):
        rhs = tuple(cross[row][column] + regularization * prior[row][column]
                    for column in range(3))
        solved = _solve_3x3(system, rhs)
        if solved is None:
            delta = _subtract(target_center, source_center)

            def translate(point):
                return _vec(point, _add(_coords(point), delta))

            return translate
        affine_rows.append(solved)

    def apply(point):
        local = _subtract(_coords(point), source_center)
        result = tuple(
            target_center[row] + sum(affine_rows[row][column] * local[column] for column in range(3))
            for row in range(3)
        )
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
                # An affine field is valid only when it reproduces every
                # moved sample.  Proportional Editing may intentionally give
                # each vertex a different target; those targets need the
                # constrained displacement solve below so hard samples stay
                # exact.  This is a target-shape check, not a time or
                # scene-specific heuristic.
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
