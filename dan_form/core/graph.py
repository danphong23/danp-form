"""Topology graph helpers over persistent Source IDs."""

from __future__ import annotations

from collections import deque


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

