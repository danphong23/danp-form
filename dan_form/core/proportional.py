"""Replaceable proportional attenuation candidates."""

from __future__ import annotations


def alpha(distance: float, profile: str, radius: float) -> float:
    if radius <= 0.0:
        return 1.0
    x = max(0.0, min(1.0, 1.0 - distance / radius))
    if profile == "SMOOTH":
        return x * x * (3.0 - 2.0 * x)
    if profile == "UNIFORM":
        return 1.0 if distance < radius else 0.0
    return x

