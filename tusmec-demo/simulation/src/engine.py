"""Simulation engine: the heart of the simulator.

Every tick runs the classic three-phase loop for the whole swarm:

    1. Sense  — each agent scans its surroundings
    2. Think  — each agent computes a desired acceleration (APF etc.)
    3. Act    — all agents integrate their motion simultaneously

Sense/Think are completed for *all* agents before any of them moves, so every
decision in a tick is based on the same world snapshot (no ordering bias).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

from .agents import BaseAgent
from .environment import Environment


@dataclass
class SimulationStats:
    ticks: int = 0
    sim_time: float = 0.0
    goals_reached: int = 0
    total_agents: int = 0
    total_distance: float = 0.0
    total_cost: float = 0.0  # USD, from cost_per_hour of each agent
    per_type: dict = field(default_factory=dict)


class SimulationEngine:
    """Owns the world, the swarm and the tick loop."""

    def __init__(self, environment: Environment, agents: list[BaseAgent], dt: float = 0.05):
        if dt <= 0:
            raise ValueError("dt must be positive")
        self.environment = environment
        self.agents = list(agents)
        self.dt = dt
        self.ticks = 0
        self.sim_time = 0.0

    # ------------------------------------------------------------------ tick
    def tick(self) -> None:
        """Advance the simulation by one time step (Sense -> Think -> Act)."""
        # Phase 1 + 2: everyone senses and decides on the same snapshot
        decisions: list[np.ndarray] = []
        for agent in self.agents:
            perception = agent.sense(self.environment, self.agents)   # Sense
            decisions.append(agent.think(perception))                 # Think

        # Phase 3: everyone moves
        for agent, acceleration in zip(self.agents, decisions):
            agent.act(acceleration, self.dt)                          # Act
            agent.position = self.environment.clamp(agent.position)

        self.ticks += 1
        self.sim_time += self.dt

    # ------------------------------------------------------------------- run
    def run(
        self,
        max_ticks: int = 2000,
        stop_when_done: bool = True,
        on_tick: Optional[Callable[["SimulationEngine"], None]] = None,
    ) -> SimulationStats:
        """Main loop. Runs until every agent reaches its goal (or max_ticks)."""
        while self.ticks < max_ticks:
            self.tick()
            if on_tick is not None:
                on_tick(self)
            if stop_when_done and self.all_goals_reached():
                break
        return self.stats()

    # ----------------------------------------------------------------- state
    def all_goals_reached(self) -> bool:
        return all(a.at_goal() for a in self.agents if a.goal is not None)

    def stats(self) -> SimulationStats:
        hours = self.sim_time / 3600.0
        per_type: dict[str, dict] = {}
        for agent in self.agents:
            entry = per_type.setdefault(
                agent.TYPE_NAME, {"count": 0, "reached": 0, "distance": 0.0}
            )
            entry["count"] += 1
            entry["reached"] += int(agent.at_goal())
            entry["distance"] += agent.distance_travelled
        return SimulationStats(
            ticks=self.ticks,
            sim_time=self.sim_time,
            goals_reached=sum(a.at_goal() for a in self.agents),
            total_agents=len(self.agents),
            total_distance=sum(a.distance_travelled for a in self.agents),
            total_cost=sum(a.spec.cost_per_hour for a in self.agents) * hours,
            per_type=per_type,
        )
