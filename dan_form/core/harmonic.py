"""Patch-local displacement interpolation with exact vertex constraints."""

from __future__ import annotations

from collections import deque
import math

try:
    import numpy as np
except ImportError:  # Pure-Python core fixtures do not require Blender's NumPy.
    np = None


def _solve_numpy(free, diagonal, free_neighbors, rhs):
    count = len(free)
    diag = np.asarray(diagonal, dtype=np.float64)
    boundary = np.asarray(rhs, dtype=np.float64)
    rows = np.asarray([row for row, neighbors in enumerate(free_neighbors)
                       for _neighbor, _weight in neighbors], dtype=np.int32)
    columns = np.asarray([neighbor for neighbors in free_neighbors
                          for neighbor, _weight in neighbors], dtype=np.int32)
    weights = np.asarray([weight for neighbors in free_neighbors
                          for _neighbor, weight in neighbors], dtype=np.float64)

    def multiply(values):
        product = diag[:, None] * values
        for axis in range(3):
            product[:, axis] -= np.bincount(
                rows, weights * values[columns, axis], minlength=count
            )
        return product

    result = np.zeros_like(boundary)
    residual = boundary.copy()
    initial_norm = float(np.linalg.norm(residual))
    if initial_norm == 0.0:
        return {vertex_id: (0.0, 0.0, 0.0) for vertex_id in free}
    preconditioned = residual / diag[:, None]
    direction = preconditioned.copy()
    residual_product = float(np.sum(residual * preconditioned))
    tolerance = max(initial_norm * 1e-9, 1e-12)
    for _iteration in range(min(4 * count, 1024)):
        product = multiply(direction)
        denominator = float(np.sum(direction * product))
        if denominator <= 0.0 or not math.isfinite(denominator):
            raise ValueError("SOLVER_INVALID")
        step = residual_product / denominator
        result += step * direction
        residual -= step * product
        if float(np.linalg.norm(residual)) <= tolerance:
            break
        preconditioned = residual / diag[:, None]
        next_product = float(np.sum(residual * preconditioned))
        direction = preconditioned + (next_product / residual_product) * direction
        residual_product = next_product
    else:
        raise ValueError("SOLVER_NOT_CONVERGED")
    return {vertex_id: tuple(result[index]) for index, vertex_id in enumerate(free)}


def solve_displacements(positions, vertices, edge_vids, targets, stationary):
    """Return free-vertex displacements for one patch.

    Moving control vertices have their measured displacement; stationary
    control vertices have zero displacement.  Every other vertex minimizes
    weighted edge differences.  Edge resistance follows its rest length, so
    a one-dimensional strip preserves its original spacing ratios.
    """
    vertices = set(vertices)
    anchors = {
        vertex_id: tuple(float(a) - float(b) for a, b in zip(target, positions[vertex_id]))
        for vertex_id, target in targets.items() if vertex_id in vertices
    }
    anchors.update({vertex_id: (0.0, 0.0, 0.0)
                    for vertex_id in stationary if vertex_id in vertices})
    if not anchors:
        return {}

    adjacency = {vertex_id: [] for vertex_id in vertices}
    for first, second in edge_vids.values():
        if first not in adjacency or second not in adjacency or first == second:
            continue
        length = math.dist(tuple(positions[first]), tuple(positions[second]))
        weight = 1.0 / max(length, 1e-12)
        adjacency[first].append((second, weight))
        adjacency[second].append((first, weight))

    # A disconnected island with no control constraint must retain its rest.
    reachable = set(anchors)
    queue = deque(anchors)
    while queue:
        for neighbor, _weight in adjacency[queue.popleft()]:
            if neighbor not in reachable:
                reachable.add(neighbor)
                queue.append(neighbor)
    free = sorted(reachable.difference(anchors))
    if not free:
        return {}

    indices = {vertex_id: index for index, vertex_id in enumerate(free)}
    diagonal = []
    free_neighbors = []
    rhs = []
    for vertex_id in free:
        neighbors = adjacency[vertex_id]
        diagonal.append(sum(weight for _neighbor, weight in neighbors))
        free_neighbors.append([(indices[neighbor], weight) for neighbor, weight in neighbors
                               if neighbor in indices])
        boundary = [0.0, 0.0, 0.0]
        for neighbor, weight in neighbors:
            if neighbor in anchors:
                for axis in range(3):
                    boundary[axis] += weight * anchors[neighbor][axis]
        rhs.append(boundary)

    if np is not None:
        return _solve_numpy(free, diagonal, free_neighbors, rhs)

    def dot(left, right):
        return sum(sum(a * b for a, b in zip(left[index], right[index]))
                   for index in range(len(free)))

    def multiply(values):
        result = []
        for index in range(len(free)):
            row = [diagonal[index] * value for value in values[index]]
            for neighbor, weight in free_neighbors[index]:
                for axis in range(3):
                    row[axis] -= weight * values[neighbor][axis]
            result.append(row)
        return result

    result = [[0.0, 0.0, 0.0] for _vertex_id in free]
    residual = [row.copy() for row in rhs]
    initial_norm = math.sqrt(dot(residual, residual))
    if initial_norm == 0.0:
        return {vertex_id: (0.0, 0.0, 0.0) for vertex_id in free}
    preconditioned = [[value / diagonal[index] for value in row]
                      for index, row in enumerate(residual)]
    direction = [row.copy() for row in preconditioned]
    residual_product = dot(residual, preconditioned)
    tolerance = max(initial_norm * 1e-9, 1e-12)
    for _iteration in range(min(4 * len(free), 1024)):
        product = multiply(direction)
        denominator = dot(direction, product)
        if denominator <= 0.0 or not math.isfinite(denominator):
            raise ValueError("SOLVER_INVALID")
        step = residual_product / denominator
        for index in range(len(free)):
            for axis in range(3):
                result[index][axis] += step * direction[index][axis]
                residual[index][axis] -= step * product[index][axis]
        if math.sqrt(dot(residual, residual)) <= tolerance:
            break
        preconditioned = [[value / diagonal[index] for value in row]
                          for index, row in enumerate(residual)]
        next_product = dot(residual, preconditioned)
        factor = next_product / residual_product
        for index in range(len(free)):
            for axis in range(3):
                direction[index][axis] = preconditioned[index][axis] + factor * direction[index][axis]
        residual_product = next_product
    else:
        raise ValueError("SOLVER_NOT_CONVERGED")
    return {vertex_id: tuple(result[index]) for index, vertex_id in enumerate(free)}
