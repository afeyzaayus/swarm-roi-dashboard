"""Environment model: world bounds and cylindrical obstacles.

Obstacles are vertical cylinders with a finite height. A UAV flying above an
obstacle's height is *not* blocked by it — this is one of the places where the
heterogeneity of the swarm actually matters.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from .math_utils import horizontal_distance


@dataclass
class Obstacle:
    """Vertical cylinder obstacle spanning z in [base, base + height).

    center: (x, y) of the cylinder axis
    radius: cylinder radius in meters
    height: cylinder height in meters (math.inf = full-height wall)
    base:   z coordinate of the cylinder bottom (negative = underwater)
    """

    center: tuple[float, float]
    radius: float
    height: float = math.inf
    base: float = 0.0

    #aracın engelin dış yüzeyine olan uzaklığı
    def surface_distance(self, position: np.ndarray) -> float:
        """Horizontal distance from a point to the obstacle surface (>= 0)."""
        c = np.array([self.center[0], self.center[1], 0.0])
        d = horizontal_distance(position, c) - self.radius
        return max(d, 0.0)

    @property
    def top(self) -> float:
        return self.base + self.height

    def blocks(self, position: np.ndarray) -> bool:
        """True if an agent at this altitude/depth is affected by the obstacle."""
        z = float(position[2])
        return self.base <= z < self.top

    def contains(self, position: np.ndarray) -> bool:
        """True if the point is inside the cylinder volume."""
        c = np.array([self.center[0], self.center[1], 0.0])
        return self.blocks(position) and horizontal_distance(position, c) < self.radius


@dataclass
class Environment:
    """Rectangular world with obstacles.

    width/height are in meters; ceiling is the max flight altitude for UAVs
    and floor is the seabed depth for underwater agents (0 = no water column).
    """

    width: float = 100.0
    height: float = 100.0
    ceiling: float = 50.0
    floor: float = 0.0
    obstacles: list[Obstacle] = field(default_factory=list)

    def add_obstacle(self, obstacle: Obstacle) -> None:
        self.obstacles.append(obstacle)

    def obstacles_near(self, position: np.ndarray, sensor_range: float) -> list[Obstacle]:
        """Obstacles whose surface is within sensor range *and* whose height
        actually blocks an agent at this altitude."""
        return [
            o
            for o in self.obstacles
            if o.blocks(position) and o.surface_distance(position) <= sensor_range
        ]

    def clamp(self, position: np.ndarray) -> np.ndarray:
        """Keep a position inside world bounds (between floor and ceiling)."""
        clamped = position.copy()
        clamped[0] = min(max(clamped[0], 0.0), self.width)
        clamped[1] = min(max(clamped[1], 0.0), self.height)
        clamped[2] = min(max(clamped[2], self.floor), self.ceiling)
        return clamped
