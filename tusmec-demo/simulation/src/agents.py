"""Agent hierarchy: BaseAgent (abstract) -> UAV, UGV, AMR.

Each agent runs a Sense -> Think -> Act cycle every tick:
  * sense(): gather neighbors and blocking obstacles within sensor range
  * think(): delegate to a coordination strategy (e.g. APF) -> desired accel
  * act():   integrate acceleration, apply type-specific kinematic constraints

Type-specific physics:
  * UAV: full 3D motion, altitude band [min_altitude, max_altitude], no friction
  * UGV: 2D (z=0), ground friction, limited turn rate (Ackermann-like)
  * AMR: 2D (z=0), ground friction, omnidirectional but slow
"""
from __future__ import annotations

import itertools
import math
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import numpy as np

from .math_utils import EPS, heading_of, limit, norm, vec, wrap_angle

if TYPE_CHECKING:  # pragma: no cover
    from .coordination import CoordinationStrategy
    from .environment import Environment, Obstacle


@dataclass(frozen=True)
class AgentSpec:
    """Per-type parameter set required by the Week 2 task.

    max_speed:      m/s
    max_accel:      m/s^2
    sensor_range:   m   (menzil / algılama yarıçapı)
    task_capacity:  kg  (görev/yük kapasitesi)
    cost_per_hour:  USD/saat (işletme maliyeti)
    friction:       1/s exponential-like ground damping (0 for aerial)
    max_turn_rate:  deg/s heading change limit (inf = omnidirectional)
    """

    max_speed: float
    max_accel: float
    sensor_range: float
    task_capacity: float
    cost_per_hour: float
    friction: float = 0.0
    max_turn_rate: float = math.inf


#: Default parameter sets (KPI: "her ajan tipine özgü parametre seti")
DEFAULT_SPECS: dict[str, AgentSpec] = {
    "UAV": AgentSpec(max_speed=80.0, max_accel=6.0, sensor_range=40.0,
                     task_capacity=2.5, cost_per_hour=120.0),
    "UGV": AgentSpec(max_speed=75.0, max_accel=2.5, sensor_range=20.0,
                     task_capacity=80.0, cost_per_hour=45.0,
                     friction=0.6, max_turn_rate=90.0),
    "AMR": AgentSpec(max_speed=63.0, max_accel=1.5, sensor_range=12.0,
                     task_capacity=30.0, cost_per_hour=25.0,
                     friction=0.8),
    "USV": AgentSpec(max_speed=8.0, max_accel=3.0, sensor_range=30.0,
                     task_capacity=200.0, cost_per_hour=60.0,
                     friction=0.5, max_turn_rate=60.0),
    "UUV": AgentSpec(max_speed=3.0, max_accel=1.2, sensor_range=15.0,
                     task_capacity=50.0, cost_per_hour=90.0,
                     friction=0.9, max_turn_rate=45.0),
    "ROCKET": AgentSpec(max_speed=30.0, max_accel=12.0, sensor_range=35.0,
                        task_capacity=10.0, cost_per_hour=300.0,
                        friction=0.0, max_turn_rate=25.0),
}


def limit_turn(
    previous_velocity: np.ndarray,
    candidate: np.ndarray,
    max_turn_rate_deg: float,
    dt: float,
) -> np.ndarray:
    """Clamp the horizontal heading change between two velocities.

    Shared by every non-holonomic agent (UGV, USV). The
    vertical component is left untouched.
    """
    if not math.isfinite(max_turn_rate_deg):
        return candidate
    prev_h = norm(previous_velocity[:2])
    cand_h = norm(candidate[:2])
    if prev_h < EPS or cand_h < EPS:
        return candidate
    current = heading_of(previous_velocity)
    desired = heading_of(candidate)
    diff = wrap_angle(desired - current)
    max_turn = math.radians(max_turn_rate_deg) * dt
    if abs(diff) <= max_turn:
        return candidate
    new_heading = current + math.copysign(max_turn, diff)
    out = candidate.copy()
    out[0] = math.cos(new_heading) * cand_h
    out[1] = math.sin(new_heading) * cand_h
    return out


@dataclass
class Perception:
    """Snapshot of what an agent perceives in a tick."""

    neighbors: list["BaseAgent"] = field(default_factory=list)
    obstacles: list["Obstacle"] = field(default_factory=list)


class BaseAgent(ABC):
    """Abstract base class for every swarm member."""

    TYPE_NAME = "BASE"
    _ids = itertools.count(1)

    def __init__(
        self,
        position: np.ndarray,
        spec: AgentSpec,
        goal: Optional[np.ndarray] = None,
        strategy: Optional["CoordinationStrategy"] = None,
        goal_tolerance: float = 1.5,
    ) -> None:
        self.id: int = next(BaseAgent._ids)
        self.position: np.ndarray = np.asarray(position, dtype=float).copy()
        self.velocity: np.ndarray = np.zeros(3)
        self.spec = spec
        self.goal: Optional[np.ndarray] = (
            None if goal is None else np.asarray(goal, dtype=float).copy()
        )
        self.strategy = strategy
        self.goal_tolerance = goal_tolerance
        self.distance_travelled: float = 0.0
        self.trail: list[np.ndarray] = [self.position.copy()]

    def sense(self, environment: "Environment", agents: list["BaseAgent"]) -> Perception:
        """Scan surroundings: neighbors and blocking obstacles in sensor range."""
        neighbors = [
            other
            for other in agents
            if other is not self
            and norm(other.position - self.position) <= self.spec.sensor_range
        ]
        obstacles = environment.obstacles_near(self.position, self.spec.sensor_range)
        return Perception(neighbors=neighbors, obstacles=obstacles)

    def think(self, perception: Perception) -> np.ndarray:
        """Compute the desired acceleration for this tick."""
        if self.goal is None or self.at_goal():
            # brake softly toward zero velocity
            return limit(-self.velocity, self.spec.max_accel)
        if self.strategy is None:
            return np.zeros(3)
        return limit(self.strategy.compute(self, perception), self.spec.max_accel)

    def act(self, acceleration: np.ndarray, dt: float) -> None:
        """Integrate motion with type-specific constraints."""
        acceleration = limit(np.asarray(acceleration, dtype=float), self.spec.max_accel)
        v = self.velocity + acceleration * dt
        v = self._constrain_velocity(v, dt)
        v = limit(v, self.spec.max_speed)
        self.velocity = v
        self.position = self.position + v * dt
        self._post_move()
        self.distance_travelled += norm(v) * dt
        self.trail.append(self.position.copy())

    # ------------------------------------------------------------- lifecycle
    def at_goal(self) -> bool:
        if self.goal is None:
            return False
        return norm(self.goal - self.position) <= self.goal_tolerance

    @property
    def speed(self) -> float:
        return norm(self.velocity)

    # ------------------------------------------------------ subclass contract
    @abstractmethod
    def _constrain_velocity(self, v: np.ndarray, dt: float) -> np.ndarray:
        """Apply type-specific kinematic constraints to a candidate velocity."""

    def _post_move(self) -> None:
        """Hook for post-integration fixes (e.g. altitude clamping)."""

    def __repr__(self) -> str:  # pragma: no cover
        p = self.position
        return f"<{self.TYPE_NAME}#{self.id} pos=({p[0]:.1f},{p[1]:.1f},{p[2]:.1f})>"


class UAV(BaseAgent):
    """Aerial agent: moves freely in 3D within an altitude band."""

    TYPE_NAME = "UAV"

    def __init__(
        self,
        position: np.ndarray,
        spec: AgentSpec = DEFAULT_SPECS["UAV"],
        goal: Optional[np.ndarray] = None,
        strategy: Optional["CoordinationStrategy"] = None,
        min_altitude: float = 2.0,
        max_altitude: float = 40.0,
        cruise_altitude: float = 15.0,
    ) -> None:
        position = np.asarray(position, dtype=float).copy()
        if position[2] <= 0.0:
            position[2] = cruise_altitude
        if goal is not None:
            goal = np.asarray(goal, dtype=float).copy()
            if goal[2] <= 0.0:
                goal[2] = cruise_altitude
        super().__init__(position, spec, goal=goal, strategy=strategy)
        self.min_altitude = min_altitude
        self.max_altitude = max_altitude

    def _constrain_velocity(self, v: np.ndarray, dt: float) -> np.ndarray:
        # No friction, no turn limit: a multirotor is fully holonomic in 3D.
        return v

    def _post_move(self) -> None:
        self.position[2] = min(max(self.position[2], self.min_altitude), self.max_altitude)


class GroundAgent(BaseAgent):
    """Shared 2D physics for ground vehicles: z is pinned to 0, friction damps
    velocity every tick."""

    def _constrain_velocity(self, v: np.ndarray, dt: float) -> np.ndarray:
        v = v.copy()
        v[2] = 0.0
        v *= max(0.0, 1.0 - self.spec.friction * dt)
        return v

    def _post_move(self) -> None:
        self.position[2] = 0.0


class UGV(GroundAgent):
    """Ground vehicle with a limited turn rate (car-like steering)."""

    TYPE_NAME = "UGV"

    def __init__(
        self,
        position: np.ndarray,
        spec: AgentSpec = DEFAULT_SPECS["UGV"],
        goal: Optional[np.ndarray] = None,
        strategy: Optional["CoordinationStrategy"] = None,
    ) -> None:
        super().__init__(position, spec, goal=goal, strategy=strategy)

    def _constrain_velocity(self, v: np.ndarray, dt: float) -> np.ndarray:
        v = super()._constrain_velocity(v, dt)
        return limit_turn(self.velocity, v, self.spec.max_turn_rate, dt)


class AMR(GroundAgent):
    """Autonomous mobile robot: omnidirectional but slow, indoor-scale."""

    TYPE_NAME = "AMR"

    def __init__(
        self,
        position: np.ndarray,
        spec: AgentSpec = DEFAULT_SPECS["AMR"],
        goal: Optional[np.ndarray] = None,
        strategy: Optional["CoordinationStrategy"] = None,
    ) -> None:
        super().__init__(position, spec, goal=goal, strategy=strategy)


class USV(GroundAgent):
    """Unmanned surface vehicle: sails on the water plane (z = 0) with hull
    drag and a rudder-limited turn rate."""

    TYPE_NAME = "USV"

    def __init__(
        self,
        position: np.ndarray,
        spec: AgentSpec = DEFAULT_SPECS["USV"],
        goal: Optional[np.ndarray] = None,
        strategy: Optional["CoordinationStrategy"] = None,
    ) -> None:
        super().__init__(position, spec, goal=goal, strategy=strategy)

    def _constrain_velocity(self, v: np.ndarray, dt: float) -> np.ndarray:
        v = super()._constrain_velocity(v, dt)
        return limit_turn(self.velocity, v, self.spec.max_turn_rate, dt)


class UnderwaterAgent(BaseAgent):
    """Shared physics for submerged vehicles: 3D motion at negative z within a
    depth band [-max_depth, -min_depth], water drag on all axes and a limited
    horizontal turn rate."""

    def __init__(
        self,
        position: np.ndarray,
        spec: AgentSpec,
        goal: Optional[np.ndarray] = None,
        strategy: Optional["CoordinationStrategy"] = None,
        min_depth: float = 1.0,
        max_depth: float = 25.0,
        cruise_depth: float = 10.0,
    ) -> None:
        position = np.asarray(position, dtype=float).copy()
        if position[2] >= 0.0:
            position[2] = -cruise_depth
        if goal is not None:
            goal = np.asarray(goal, dtype=float).copy()
            if goal[2] >= 0.0:
                goal[2] = -cruise_depth
        super().__init__(position, spec, goal=goal, strategy=strategy)
        self.min_depth = min_depth
        self.max_depth = max_depth

    def _constrain_velocity(self, v: np.ndarray, dt: float) -> np.ndarray:
        v = v * max(0.0, 1.0 - self.spec.friction * dt)  # water drag (3D)
        return limit_turn(self.velocity, v, self.spec.max_turn_rate, dt)

    def _post_move(self) -> None:
        self.position[2] = min(max(self.position[2], -self.max_depth), -self.min_depth)


class UUV(UnderwaterAgent):
    """Unmanned underwater vehicle: slow, sonar-limited survey submarine."""

    TYPE_NAME = "UUV"

    def __init__(
        self,
        position: np.ndarray,
        spec: AgentSpec = DEFAULT_SPECS["UUV"],
        goal: Optional[np.ndarray] = None,
        strategy: Optional["CoordinationStrategy"] = None,
        **kwargs,
    ) -> None:
        super().__init__(position, spec, goal=goal, strategy=strategy, **kwargs)


class Rocket(UAV):
    """Aerial rocket: the fastest agent in the swarm. Flies higher than
    everything else (near the world ceiling), has no drag, but its fins only
    allow wide, missile-like turns (small max_turn_rate)."""

    TYPE_NAME = "ROCKET"

    def __init__(
        self,
        position: np.ndarray,
        spec: AgentSpec = None,  # resolved below to DEFAULT_SPECS["ROCKET"]
        goal: Optional[np.ndarray] = None,
        strategy: Optional["CoordinationStrategy"] = None,
        min_altitude: float = 5.0,
        max_altitude: float = 45.0,
        cruise_altitude: float = 35.0,
    ) -> None:
        super().__init__(
            position,
            spec if spec is not None else DEFAULT_SPECS["ROCKET"],
            goal=goal,
            strategy=strategy,
            min_altitude=min_altitude,
            max_altitude=max_altitude,
            cruise_altitude=cruise_altitude,
        )

    def _constrain_velocity(self, v: np.ndarray, dt: float) -> np.ndarray:
        # Aerodynamically free like a UAV, but the turn is fin-limited.
        return limit_turn(self.velocity, v, self.spec.max_turn_rate, dt)
