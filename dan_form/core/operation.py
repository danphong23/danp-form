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


def targets_from_transform(p0, selected, transform: OperationTransform):
    """Resolve canonical operation intent to absolute Source-local targets."""
    pivot = tuple(float(value) for value in transform.pivot)
    translation = tuple(float(value) for value in transform.translation)
    rx, ry, rz = (float(value) for value in transform.rotation)
    sx, sy, sz = (float(value) for value in transform.scale)
    cx, sxn = math.cos(rx), math.sin(rx)
    cy, syn = math.cos(ry), math.sin(ry)
    cz, szn = math.cos(rz), math.sin(rz)

    def rotate(value):
        x, y, z = value
        # XYZ Euler matrix, matching Blender's Euler(..., "XYZ").to_matrix().
        y1, z1 = cy * y - syn * z, syn * y + cy * z
        x2, z2 = cx * x + sxn * z1, -sxn * x + cx * z1
        return (cz * x2 - szn * y1, szn * x2 + cz * y1, z2)

    targets = {}
    for vertex_id in selected:
        source = tuple(float(value) for value in p0[vertex_id])
        relative = tuple(source[index] - pivot[index] for index in range(3))
        if transform.operation == "MOVE":
            moved = relative
        elif transform.operation == "SCALE":
            moved = (relative[0] * sx, relative[1] * sy, relative[2] * sz)
        else:
            moved = rotate(relative)
        result = tuple(pivot[index] + moved[index] + translation[index] for index in range(3))
        reference = p0[vertex_id]
        try:
            targets[vertex_id] = reference.__class__(result)
        except (TypeError, ValueError):
            targets[vertex_id] = reference.__class__(*result)
    return targets


__all__ = ["OperationTransform", "targets_from_transform"]
