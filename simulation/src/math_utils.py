"""Vector math helpers used across the simulation.

All positions and velocities are numpy arrays of shape (3,) — ground agents
simply keep their z component at 0. Keeping a single dimensionality makes the
engine, APF and tests uniform.
"""
from __future__ import annotations

import math

import numpy as np

EPS = 1e-9


def vec(x: float, y: float, z: float = 0.0) -> np.ndarray:
    """Convenience constructor for a 3D float vector."""
    return np.array([x, y, z], dtype=float)


def norm(v: np.ndarray) -> float:
    """Euclidean length of a vector."""
    return float(np.linalg.norm(v))


def distance(a: np.ndarray, b: np.ndarray) -> float:
    """Euclidean distance between two points."""
    return norm(np.asarray(a, dtype=float) - np.asarray(b, dtype=float))


def horizontal_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Distance ignoring the z axis (used for ground obstacles)."""
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return float(np.linalg.norm(a[:2] - b[:2]))


def normalize(v: np.ndarray) -> np.ndarray:
    """Unit vector in the direction of v (zero vector stays zero)."""
    n = norm(v)
    if n < EPS:
        return np.zeros_like(np.asarray(v, dtype=float))
    return np.asarray(v, dtype=float) / n


def limit(v: np.ndarray, max_magnitude: float) -> np.ndarray:
    """Clamp the magnitude of a vector to max_magnitude."""
    v = np.asarray(v, dtype=float)
    n = norm(v)
    if n > max_magnitude and n > EPS:
        return v * (max_magnitude / n)
    return v


def wrap_angle(angle: float) -> float:
    """Wrap an angle to the interval (-pi, pi]."""
    return math.atan2(math.sin(angle), math.cos(angle))

def heading_of(v: np.ndarray) -> float:
    """Heading (radians) of the horizontal component of a vector."""
    return math.atan2(float(v[1]), float(v[0]))
