"""Demo scenario builder with agent-type filtering.

The full roster contains all six agent types. `build_demo_scenario` can filter
the swarm down to a subset, driven by CLI flags in main.py:

    python main.py                  -> all agents (default)
    python main.py uav              -> only UAVs
    python main.py uav ugv rocket   -> only those three types
"""
from __future__ import annotations

from typing import Iterable, Optional

from .agents import AMR, UAV, UGV, USV, UUV, BaseAgent, Rocket
from .coordination import ArtificialPotentialField
from .engine import SimulationEngine
from .environment import Environment, Obstacle
from .math_utils import vec

#: CLI keyword -> agent class
AGENT_TYPES: dict[str, type[BaseAgent]] = {
    "uav": UAV,
    "ugv": UGV,
    "amr": AMR,
    "usv": USV,
    "uuv": UUV,
    "rocket": Rocket,
}


def normalize_types(types: Optional[Iterable[str]]) -> set[str]:
    """Validate and lower-case a list of type keywords (None/empty = all)."""
    if not types:
        return set(AGENT_TYPES)
    selected = {t.lower() for t in types}
    unknown = selected - set(AGENT_TYPES)
    if unknown:
        valid = ", ".join(sorted(AGENT_TYPES))
        raise ValueError(f"Unknown agent type(s): {', '.join(sorted(unknown))}. Valid: {valid}")
    return selected


def build_demo_scenario(
    types: Optional[Iterable[str]] = None,
    strategy: Optional[object] = None,
) -> SimulationEngine:
    """Heterogeneous swarm crossing an obstacle field diagonally.

    strategy: a CoordinationStrategy instance shared by all agents
              (default: plain ArtificialPotentialField).

    Obstacle layout demonstrates altitude/depth heterogeneity:
      * UAVs cruising at 20 m ignore the 10 m-high obstacles entirely
      * the infinite column at (65, 30) blocks air and ground alike
      * the seamount (base -30 m, top -8 m) blocks UUVs at -12 m
      * rockets cruise at 35 m — above every finite obstacle, so only the
        infinite no-fly column could ever affect them
    """
    selected = normalize_types(types)

    env = Environment(width=100.0, height=100.0, ceiling=45.0, floor=-30.0)
    env.add_obstacle(Obstacle(center=(35.0, 40.0), radius=6.0, height=25.0))
    env.add_obstacle(Obstacle(center=(55.0, 60.0), radius=3.0, height=10.0))
    env.add_obstacle(Obstacle(center=(65.0, 30.0), radius=7.0))              # infinite: no-fly column
    env.add_obstacle(Obstacle(center=(45.0, 75.0), radius=4.0, height=8.0))
    env.add_obstacle(Obstacle(center=(60.0, 55.0), radius=6.0, height=22.0, base=-30.0))  # seamount

    apf = strategy if strategy is not None else ArtificialPotentialField()

    roster: list[tuple[str, BaseAgent]] = [
        # UAVs at 20 m never even "see" the 10 m obstacles
        ("uav", UAV(vec(8, 10), goal=vec(90, 88), strategy=apf, cruise_altitude=20.0)),
        ("uav", UAV(vec(12, 6), goal=vec(85, 92), strategy=apf, cruise_altitude=20.0)),
        ("uav", UAV(vec(5, 15), goal=vec(92, 80), strategy=apf, cruise_altitude=20.0)),
        ("ugv", UGV(vec(10, 20), goal=vec(88, 75), strategy=apf)),
        ("ugv", UGV(vec(15, 12), goal=vec(80, 85), strategy=apf)),
        ("ugv", UGV(vec(6, 25), goal=vec(90, 70), strategy=apf)),
        ("amr", AMR(vec(20, 8), goal=vec(60, 45), strategy=apf)),
        ("amr", AMR(vec(25, 12), goal=vec(55, 50), strategy=apf)),
        ("usv", USV(vec(8, 40), goal=vec(85, 60), strategy=apf)),
        ("usv", USV(vec(5, 35), goal=vec(90, 55), strategy=apf)),
        # UUVs cruise at -12 m: the seamount (top -8 m) blocks them
        ("uuv", UUV(vec(15, 55), goal=vec(85, 45), strategy=apf, cruise_depth=12.0)),
        ("uuv", UUV(vec(10, 60), goal=vec(88, 40), strategy=apf, cruise_depth=12.0)),
        # rockets cruise at 35 m: above every finite obstacle in the map
        ("rocket", Rocket(vec(5, 50), goal=vec(95, 65), strategy=apf)),
        ("rocket", Rocket(vec(8, 45), goal=vec(92, 72), strategy=apf)),
    ]

    agents = [agent for key, agent in roster if key in selected]
    return SimulationEngine(env, agents, dt=0.05)
