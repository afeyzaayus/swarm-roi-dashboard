"""Coordination strategies. Week 2 requirement: at least one working
algorithm — implemented here as Artificial Potential Fields (APF).

APF treats the world as a potential landscape:
  * the goal generates an attractive force  F_att = k_att * (goal - pos)
  * obstacles generate a repulsive force inside an influence radius d0:
        F_rep = k_rep * (1/d - 1/d0) * (1/d^2) * u        (Khatib, 1986)
  * nearby agents generate a separation force with the same repulsive shape,
    which doubles as collision avoidance inside the swarm.

Everything is computed with numpy vector operations.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import numpy as np

from .agents import BaseAgent, Perception
from .math_utils import EPS, limit, norm, normalize


def normalize_horizontal(v: np.ndarray) -> np.ndarray:
    """Unit vector of the horizontal (xy) component — cylinders push sideways."""
    flat = v.copy()
    flat[2] = 0.0
    return normalize(flat)


class CoordinationStrategy(ABC):
    """Interface every coordination algorithm must implement."""

    @abstractmethod
    def compute(self, agent: BaseAgent, perception: Perception) -> np.ndarray:
        """Return the desired acceleration vector for this tick."""


class ArtificialPotentialField(CoordinationStrategy):
    """Classic APF with goal attraction, obstacle repulsion and agent separation."""

    def __init__(
        self,
        k_att: float = 1.2,
        k_rep: float = 60.0,
        k_sep: float = 25.0,
        k_tangent: float = 0.6,
        attraction_saturation: float = 5.0,
        obstacle_influence: float = 8.0,
        separation_distance: float = 5.0,
        damping: float = 0.8,
    ) -> None:
        self.k_att = k_att
        self.k_rep = k_rep
        self.k_sep = k_sep
        self.k_tangent = k_tangent
        self.attraction_saturation = attraction_saturation
        self.obstacle_influence = obstacle_influence
        self.separation_distance = separation_distance
        self.damping = damping

    # ------------------------------------------------------------ components
    def attractive_force(self, agent: BaseAgent) -> np.ndarray:
        if agent.goal is None:
            return np.zeros(3)
        error = agent.goal - agent.position
        # Linear near the goal, saturated far away — otherwise a distant goal
        # produces an attraction no repulsion could ever counteract.
        return limit(self.k_att * error, self.k_att * self.attraction_saturation)

    def repulsive_force(
        self,
        agent: BaseAgent,
        perception: Perception,
        position: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        """Obstacle repulsion evaluated at `position` (default: where the agent
        actually is). PAPF re-evaluates this at a virtual lookahead point."""
        pos = agent.position if position is None else position
        force = np.zeros(3)
        d0 = self.obstacle_influence
        goal_dir = normalize(agent.goal - pos) if agent.goal is not None else np.zeros(3)
        for obstacle in perception.obstacles:
            d = max(obstacle.surface_distance(pos), 0.2)
            if d >= d0:
                continue
            center = np.array([obstacle.center[0], obstacle.center[1], 0.0])
            away = normalize_horizontal(pos - center)
            magnitude = self.k_rep * (1.0 / d - 1.0 / d0) / (d * d)
            force += magnitude * away

            # Tangential component: steers *around* the obstacle instead of
            # only pushing back. This breaks the classic head-on local minimum
            # of APF (attraction and repulsion perfectly anti-parallel).
            tangent = np.array([-away[1], away[0], 0.0])
            if float(np.dot(tangent, goal_dir)) < 0.0:
                tangent = -tangent
            force += self.k_tangent * magnitude * tangent
        return force

    def separation_force(
        self,
        agent: BaseAgent,
        perception: Perception,
        position: Optional[np.ndarray] = None,
    ) -> np.ndarray:
        pos = agent.position if position is None else position
        force = np.zeros(3)
        d0 = self.separation_distance
        for other in perception.neighbors:
            offset = pos - other.position
            d = max(norm(offset), 0.2)
            if d >= d0:
                continue
            magnitude = self.k_sep * (1.0 / d - 1.0 / d0) / (d * d)
            force += magnitude * normalize(offset)
        return force

    # --------------------------------------------------------------- combine
    def compute(self, agent: BaseAgent, perception: Perception) -> np.ndarray:
        total = (
            self.attractive_force(agent)
            + self.repulsive_force(agent, perception)
            + self.separation_force(agent, perception)
            - self.damping * agent.velocity  # velocity damping prevents orbiting
        )
        if norm(total) < EPS:
            return np.zeros(3)
        return limit(total, agent.spec.max_accel)


class PredictiveArtificialPotentialField(ArtificialPotentialField):
    """PAPF — Predictive APF.

    Classic APF only feels an obstacle once the agent is already inside its
    influence radius, which forces late, sharp corrections. PAPF additionally
    takes a *virtual step* of length `step_length` (d) along the agent's
    current direction of motion and re-evaluates the repulsive/separation
    field at that imaginary lookahead point:

        p_virtual = p + d * unit(v)          (toward the goal if stationary)
        F = F_att(p) + F_rep(p) + w * F_rep(p_virtual) - damping * v

    Because the path is bent by what *would* happen d meters ahead, larger d
    makes the agent commit to avoidance earlier and follow wider, smoother
    paths; smaller d converges to plain APF behavior.
    """

    DEFAULT_STEP_LENGTH = 3.0

    def __init__(
        self,
        step_length: float = DEFAULT_STEP_LENGTH,
        predictive_weight: float = 1.0,
        **apf_kwargs,
    ) -> None:
        super().__init__(**apf_kwargs)
        if step_length <= 0:
            raise ValueError("step_length (d) must be positive")
        self.step_length = step_length
        self.predictive_weight = predictive_weight

    def lookahead_position(self, agent: BaseAgent) -> np.ndarray:
        """The imaginary step: d meters along the current motion direction
        (or toward the goal when the agent hasn't started moving yet)."""
        if agent.speed > EPS:
            direction = normalize(agent.velocity)
        elif agent.goal is not None:
            direction = normalize(agent.goal - agent.position)
        else:
            return agent.position.copy()
        return agent.position + self.step_length * direction

    def compute(self, agent: BaseAgent, perception: Perception) -> np.ndarray:
        p_virtual = self.lookahead_position(agent)
        total = (
            self.attractive_force(agent)
            + self.repulsive_force(agent, perception)
            + self.separation_force(agent, perception)
            + self.predictive_weight
            * (
                self.repulsive_force(agent, perception, position=p_virtual)
                + self.separation_force(agent, perception, position=p_virtual)
            )
            - self.damping * agent.velocity
        )
        if norm(total) < EPS:
            return np.zeros(3)
        return limit(total, agent.spec.max_accel)
