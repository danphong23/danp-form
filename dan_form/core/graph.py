"""Topology graph helpers over persistent Source IDs."""

from __future__ import annotations

from collections import deque
from heapq import heappop, heappush
import math


def distances(edge_vids: dict[int, tuple[int, int]], allowed: set[int], seeds: set[int]) -> dict[int, int]:
    adjacency = {vertex_id: set() for vertex_id in allowed}
    for first, second in edge_vids.values():
        if first in allowed and second in allowed:
            adjacency[first].add(second)
            adjacency[second].add(first)
    result = {vertex_id: 0 for vertex_id in seeds if vertex_id in allowed}
    queue = deque(result)
    while queue:
        current = queue.popleft()
        for neighbor in adjacency.get(current, ()):
            if neighbor not in result:
                result[neighbor] = result[current] + 1
                queue.append(neighbor)
    return result


def metric_distances(
    edge_vids: dict[int, tuple[int, int]],
    allowed: set[int],
    seeds: set[int],
    positions: dict[int, object],
) -> dict[int, float]:
    """Shortest distances along the current Source mesh, in object-space units."""
    adjacency: dict[int, list[tuple[int, float]]] = {vertex_id: [] for vertex_id in allowed}
    for first, second in edge_vids.values():
        if first not in adjacency or second not in adjacency:
            continue
        length = math.dist(tuple(positions[first]), tuple(positions[second]))
        # Degenerate edges still connect vertices; zero cost is valid here.
        adjacency[first].append((second, length))
        adjacency[second].append((first, length))
    result = {vertex_id: 0.0 for vertex_id in seeds if vertex_id in adjacency}
    queue = []
    for vertex_id in result:
        heappush(queue, (0.0, vertex_id))
    while queue:
        distance, current = heappop(queue)
        if distance > result[current]:
            continue
        for neighbor, edge_length in adjacency[current]:
            candidate = distance + edge_length
            if candidate < result.get(neighbor, math.inf):
                result[neighbor] = candidate
                heappush(queue, (candidate, neighbor))
    return result
