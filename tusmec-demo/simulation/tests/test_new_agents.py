"""Tests for USV / UUV / underwater rocket, obstacle depth bands and the
agent-type filtering of the demo scenario."""
import math

import numpy as np
import pytest

from src.agents import DEFAULT_SPECS, UAV, USV, UUV, Rocket
from src.coordination import ArtificialPotentialField
from src.engine import SimulationEngine
from src.environment import Environment, Obstacle
from src.math_utils import norm, vec
from src.scenario import AGENT_TYPES, build_demo_scenario, normalize_types

DT = 0.05


# ------------------------------------------------------------------------ USV
def test_usv_stays_on_water_surface():
    usv = USV(vec(10, 10))
    for _ in range(200):
        usv.act(vec(1, 1, 5), DT)
        assert usv.position[2] == 0.0
        assert usv.velocity[2] == 0.0


def test_usv_turn_rate_is_limited():
    usv = USV(vec(10, 10))
    usv.velocity = vec(3, 0, 0)
    usv.act(vec(0, usv.spec.max_accel, 0), DT)
    heading = math.degrees(math.atan2(usv.velocity[1], usv.velocity[0]))
    assert abs(heading) <= usv.spec.max_turn_rate * DT + 1e-6


# ---------------------------------------------------------------- underwater
def test_uuv_spawns_at_cruise_depth_and_stays_submerged():
    uuv = UUV(vec(10, 10), goal=vec(50, 50), cruise_depth=12.0)
    assert uuv.position[2] == pytest.approx(-12.0)
    assert uuv.goal[2] == pytest.approx(-12.0)
    for _ in range(400):
        uuv.act(vec(0, 0, 10), DT)  # try to surface
        assert uuv.position[2] <= -uuv.min_depth


def test_uuv_respects_max_depth():
    uuv = UUV(vec(10, 10), max_depth=25.0)
    for _ in range(600):
        uuv.act(vec(0, 0, -10), DT)  # dive hard
    assert uuv.position[2] == pytest.approx(-25.0)


def test_rocket_is_fast_but_turns_wide():
    spec = DEFAULT_SPECS["ROCKET"]
    assert spec.max_speed > DEFAULT_SPECS["UAV"].max_speed
    assert spec.max_turn_rate < DEFAULT_SPECS["UGV"].max_turn_rate

    rocket = Rocket(vec(10, 10))
    rocket.velocity = vec(10, 0, 0)
    rocket.act(vec(0, spec.max_accel, 0), DT)
    heading = math.degrees(math.atan2(rocket.velocity[1], rocket.velocity[0]))
    assert abs(heading) <= spec.max_turn_rate * DT + 1e-6


def test_rocket_is_aerial_and_flies_highest():
    """Rocket cruises near the ceiling, above every other agent type."""
    rocket = Rocket(vec(10, 10), goal=vec(80, 80))
    uav = UAV(vec(10, 10), goal=vec(80, 80))
    assert rocket.position[2] > uav.position[2]
    assert rocket.goal[2] == pytest.approx(35.0)
    # respects its altitude band like a UAV
    for _ in range(400):
        rocket.act(vec(0, 0, 20), DT)  # push up hard
    assert rocket.position[2] == pytest.approx(rocket.max_altitude)


def test_rocket_has_no_drag():
    rocket = Rocket(vec(10, 10))
    rocket.velocity = vec(10, 0, 0)
    rocket.act(vec(0, 0, 0), DT)  # no thrust
    assert norm(rocket.velocity) == pytest.approx(10.0)


def test_water_drag_slows_underwater_agents():
    uuv = UUV(vec(10, 10))
    uuv.velocity = vec(2, 0, 0)
    uuv.act(vec(0, 0, 0), DT)  # no thrust
    assert norm(uuv.velocity) < 2.0


# --------------------------------------------------------- depth-banded engel
def test_surface_obstacle_does_not_block_underwater_agent():
    obstacle = Obstacle(center=(12.0, 0.0), radius=2.0, height=10.0)  # z: 0..10
    uuv = UUV(vec(10, 0), cruise_depth=10.0)  # z = -10
    assert not obstacle.blocks(uuv.position)


def test_seamount_blocks_uuv_but_not_aerial_rocket():
    seamount = Obstacle(center=(12.0, 0.0), radius=2.0, height=22.0, base=-30.0)  # z: -30..-8
    deep = UUV(vec(10, 0), cruise_depth=12.0)   # z = -12 -> blocked
    rocket = Rocket(vec(10, 0))                 # z = +35 -> far above
    assert seamount.blocks(deep.position)
    assert not seamount.blocks(rocket.position)


def test_environment_floor_clamp():
    env = Environment(floor=-30.0, ceiling=45.0)
    clamped = env.clamp(vec(10, 10, -100))
    assert clamped[2] == pytest.approx(-30.0)


# --------------------------------------------------------------- integration
def test_underwater_and_aerial_extremes_reach_goals():
    """UUV threads around the seamount at -12 m while the rocket at +35 m
    flies over the same map in a straight line — max heterogeneity."""
    apf = ArtificialPotentialField()
    env = Environment(width=100, height=100, ceiling=45, floor=-30)
    env.add_obstacle(Obstacle(center=(50.0, 50.0), radius=5.0, height=22.0, base=-30.0))
    agents = [
        UUV(vec(15, 50), goal=vec(85, 50), strategy=apf, cruise_depth=12.0),
        Rocket(vec(10, 45), goal=vec(90, 55), strategy=apf),
    ]
    engine = SimulationEngine(env, agents, dt=0.05)
    stats = engine.run(max_ticks=5000)
    assert stats.goals_reached == 2
    # rocket at +35 m ignores the seamount entirely -> nearly straight path
    assert agents[1].distance_travelled < 95.0


# ------------------------------------------------------------------ filtering
def test_default_scenario_contains_all_types():
    engine = build_demo_scenario()
    present = {a.TYPE_NAME for a in engine.agents}
    assert present == {"UAV", "UGV", "AMR", "USV", "UUV", "ROCKET"}


@pytest.mark.parametrize(
    "selection,expected",
    [
        (["uav"], {"UAV"}),
        (["rocket"], {"ROCKET"}),
        (["uav", "ugv"], {"UAV", "UGV"}),
        (["usv", "uuv", "rocket"], {"USV", "UUV", "ROCKET"}),
    ],
)
def test_scenario_filters_agent_types(selection, expected):
    engine = build_demo_scenario(selection)
    assert {a.TYPE_NAME for a in engine.agents} == expected


def test_scenario_filter_is_case_insensitive():
    engine = build_demo_scenario(["UAV", "Rocket"])
    assert {a.TYPE_NAME for a in engine.agents} == {"UAV", "ROCKET"}


def test_unknown_type_raises():
    with pytest.raises(ValueError, match="Unknown agent type"):
        normalize_types(["submarine"])


def test_agent_types_registry_is_complete():
    assert set(AGENT_TYPES) == {"uav", "ugv", "amr", "usv", "uuv", "rocket"}
