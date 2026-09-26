"""Canonical operation inputs shared by UI and agent callers."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class OperationTransform:
    """Absolute G/R/S intent captured relative to Operation Rest."""

    operation: str = "MOVE"
    pivot: tuple[float, float, float] = (0.0, 0.0, 0.0)
    translation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    scale: tuple[float, float, float] = (1.0, 1.0, 1.0)
    space: str = "SOURCE_LOCAL"

    def __post_init__(self):
        if self.operation not in {"MOVE", "ROTATE", "SCALE"}:
            raise ValueError("OPERATION_INVALID")
        if self.space not in {"SOURCE_LOCAL", "WORLD"}:
            raise ValueError("SPACE_INVALID")
        values = (*self.pivot, *self.translation, *self.rotation, *self.scale)
        if any(not math.isfinite(float(value)) for value in values):
            raise ValueError("TARGET_INVALID")
        if self.operation == "SCALE" and any(abs(float(value)) <= 1e-12 for value in self.scale):
            raise ValueError("SCALE_INVALID")


def targets_from_transform(p0, selected, transform: OperationTransform,
                           source_to_world=None):
    """Resolve canonical operation intent to absolute Source-local targets.

    The core solver stores coordinates in Source-local space.  A WORLD-space
    request therefore needs the caller's object matrix; silently treating a
    world request as local would produce plausible but incorrect geometry.
    The Blender facade currently emits Source-local transforms, while agent
    callers can provide a 4x4 ``source_to_world`` matrix when world support is
    needed.
    """
    world_to_source = None
    if transform.space == "WORLD":
        if source_to_world is None or not hasattr(source_to_world, "inverted"):
            raise ValueError("WORLD_SPACE_MATRIX_REQUIRED")
        try:
            rows = tuple(tuple(float(value) for value in row) for row in source_to_world)
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError("WORLD_SPACE_MATRIX_INVALID") from exc
        if len(rows) != 4 or any(len(row) != 4 for row in rows):
            raise ValueError("WORLD_SPACE_MATRIX_INVALID")
        if any(not math.isfinite(value) for row in rows for value in row):
            raise ValueError("WORLD_SPACE_MATRIX_INVALID")
        try:
            world_to_source = source_to_world.inverted()
        except (ValueError, ZeroDivisionError, TypeError, OverflowError) as exc:
            raise ValueError("WORLD_SPACE_MATRIX_SINGULAR") from exc

    def matrix_point(matrix, value, reference):
        try:
            transformed = matrix @ reference.__class__(value)
        except (TypeError, ValueError):
            transformed = matrix @ tuple(value)
        return tuple(float(component) for component in transformed[:3])
    pivot = tuple(float(value) for value in transform.pivot)
    translation = tuple(float(value) for value in transform.translation)
    rx, ry, rz = (float(value) for value in transform.rotation)
    sx, sy, sz = (float(value) for value in transform.scale)
    cx, sxn = math.cos(rx), math.sin(rx)
    cy, syn = math.cos(ry), math.sin(ry)
    cz, szn = math.cos(rz), math.sin(rz)

    def rotate(value):
        x, y, z = value
        # XYZ Euler matrix, matching Blender's Euler(..., "XYZ").to_matrix():
        # apply Rx, then Ry, then Rz to a column vector.  The previous code
        # applied Ry before Rx, so rotations with more than one non-zero axis
        # (and the X-only path in particular) produced a different target than
        # Blender's native transform.
        y1, z1 = cx * y - sxn * z, sxn * y + cx * z
        x2, z2 = cy * x + syn * z1, -syn * x + cy * z1
        return (cz * x2 - szn * y1, szn * x2 + cz * y1, z2)

    targets = {}
    for vertex_id in selected:
        reference = p0[vertex_id]
        source = tuple(float(value) for value in reference)
        working = (matrix_point(source_to_world, source, reference)
                   if transform.space == "WORLD" else source)
        relative = tuple(working[index] - pivot[index] for index in range(3))
        if transform.operation == "MOVE":
            moved = relative
        elif transform.operation == "SCALE":
            moved = (relative[0] * sx, relative[1] * sy, relative[2] * sz)
        else:
            moved = rotate(relative)
        result = tuple(pivot[index] + moved[index] + translation[index] for index in range(3))
        if world_to_source is not None:
            result = matrix_point(world_to_source, result, reference)
        try:
            targets[vertex_id] = reference.__class__(result)
        except (TypeError, ValueError):
            targets[vertex_id] = reference.__class__(*result)
    return targets


__all__ = ["OperationTransform", "targets_from_transform"]
