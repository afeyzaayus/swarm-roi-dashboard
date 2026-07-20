"""Simülasyon motorunun ince bir taklidi.

Yalnızca web katmanını motorsuz geliştirebilmek için var. Gerçek motor
simulation/src altına kopyalandığında bu dosya devre dışı kalır.
Arayüz, SimulationEngine ile bilinçli olarak aynı tutulmuştur.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field


@dataclass
class MockSpec:
    type_name: str
    max_speed: float
    cost_per_hour: float  # USD — ROI modülü bu alanı kullanır
    altitude: float


SPECS = {
    "uav": MockSpec("UAV", max_speed=12.0, cost_per_hour=6.0, altitude=20.0),
    "ugv": MockSpec("UGV", max_speed=4.0, cost_per_hour=4.5, altitude=0.0),
    "amr": MockSpec("AMR", max_speed=2.0, cost_per_hour=2.5, altitude=0.0),
}


@dataclass
class MockObstacle:
    center: tuple
    radius: float
    height: float


@dataclass
class MockEnvironment:
    width: float
    height: float
    obstacles: list = field(default_factory=list)


class MockAgent:
    _next_id = 0

    def __init__(self, type_key: str, position, goal):
        MockAgent._next_id += 1
        self.agent_id = MockAgent._next_id
        self.spec = SPECS[type_key]
        self.type_key = type_key
        self.position = list(position)
        self.goal = list(goal)
        self.velocity = [0.0, 0.0, 0.0]
        self.distance_travelled = 0.0
        self.reached = False

    def step(self, dt: float, obstacles):
        if self.reached:
            return
        dx = self.goal[0] - self.position[0]
        dy = self.goal[1] - self.position[1]
        dist = math.hypot(dx, dy)
        if dist < 1.0:
            self.reached = True
            return
        # hedefe doğru + engelden basit kaçınma (APF karikatürü)
        fx, fy = dx / dist, dy / dist
        for ob in obstacles:
            ox = self.position[0] - ob.center[0]
            oy = self.position[1] - ob.center[1]
            d = max(math.hypot(ox, oy) - ob.radius, 0.3)
            if d < 6.0 and self.spec.altitude < ob.height:
                push = 1.5 / (d * d)
                fx += push * ox / (d + ob.radius)
                fy += push * oy / (d + ob.radius)
        norm = math.hypot(fx, fy) or 1.0
        speed = self.spec.max_speed
        step = speed * dt
        self.position[0] += step * fx / norm
        self.position[1] += step * fy / norm
        self.position[2] = self.spec.altitude
        self.distance_travelled += step


@dataclass
class MockStats:
    ticks: int = 0
    sim_time: float = 0.0
    goals_reached: int = 0
    total_agents: int = 0
    total_distance: float = 0.0
    total_cost: float = 0.0


class SimulationEngine:
    """Gerçek motordaki sınıfla aynı ada ve tick() sözleşmesine sahip."""

    def __init__(self, environment: MockEnvironment, agents, dt: float = 0.1):
        self.environment = environment
        self.agents = agents
        self.dt = dt
        self.stats = MockStats(total_agents=len(agents))

    def tick(self):
        for agent in self.agents:
            agent.step(self.dt, self.environment.obstacles)
        self.stats.ticks += 1
        self.stats.sim_time += self.dt
        self.stats.goals_reached = sum(1 for a in self.agents if a.reached)
        self.stats.total_distance = sum(a.distance_travelled for a in self.agents)
        hours = self.dt / 3600.0
        self.stats.total_cost += sum(a.spec.cost_per_hour for a in self.agents) * hours


def build_scenario(area_m2: float, fleet: dict, n_obstacles: int = 5,
                   obstacle_h_min: float = 8.0, obstacle_h_max: float = 25.0,
                   seed: int = 42) -> SimulationEngine:
    """Web formundan gelen parametrelerle mock senaryo kurar.

    fleet: {"uav": 3, "ugv": 2, "amr": 4} gibi.
    """
    rng = random.Random(seed)
    side = max(math.sqrt(max(area_m2, 100.0)), 20.0)
    env = MockEnvironment(width=side, height=side)
    h_lo, h_hi = sorted((obstacle_h_min, obstacle_h_max))
    attempts = 0
    target_obs = max(0, int(n_obstacles))
    while len(env.obstacles) < target_obs and attempts < 100 * target_obs:
        attempts += 1
        r = rng.uniform(2.0, max(2.5, side * 0.06))
        cx = rng.uniform(0.2, 0.8) * side
        cy = rng.uniform(0.2, 0.8) * side
        
        overlap = False
        for ob in env.obstacles:
            if math.hypot(cx - ob.center[0], cy - ob.center[1]) < (r + ob.radius + 1.0):
                overlap = True
                break
                
        if not overlap:
            env.obstacles.append(
                MockObstacle(
                    center=(cx, cy),
                    radius=r,
                    height=rng.uniform(h_lo, h_hi),
                )
            )
    agents = []
    for type_key, count in fleet.items():
        for _ in range(int(count)):
            start = (rng.uniform(0, side * 0.15), rng.uniform(0, side), 0.0)
            goal = (rng.uniform(side * 0.85, side), rng.uniform(0, side), 0.0)
            agents.append(MockAgent(type_key, start, goal))
    return SimulationEngine(env, agents)
