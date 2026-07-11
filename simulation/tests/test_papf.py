"""PAPF (Predictive APF) tests.

The defining property: the virtual step lets the agent react to obstacles it
would meet d meters ahead — *before* they enter the plain-APF influence zone —
and the resulting path depends on d.
"""
import numpy as np
import pytest

from src.agents import UGV, UAV, Perception
from src.coordination import (
    ArtificialPotentialField,
    PredictiveArtificialPotentialField,
)
from src.engine import SimulationEngine
from src.environment import Environment, Obstacle
from src.math_utils import norm, vec
from src.scenario import build_demo_scenario


def test_papf_is_an_apf():
    assert issubclass(PredictiveArtificialPotentialField, ArtificialPotentialField)


def test_papf_default_step_length():
    papf = PredictiveArtificialPotentialField()
    assert papf.step_length == PredictiveArtificialPotentialField.DEFAULT_STEP_LENGTH


def test_papf_rejects_nonpositive_d():
    with pytest.raises(ValueError):
        PredictiveArtificialPotentialField(step_length=0)
    with pytest.raises(ValueError):
        PredictiveArtificialPotentialField(step_length=-3)


def test_lookahead_follows_velocity_direction():
    papf = PredictiveArtificialPotentialField(step_length=10.0)
    agent = UGV(vec(0, 0), goal=vec(100, 0))
    agent.velocity = vec(2, 0, 0)
    p_virtual = papf.lookahead_position(agent)
    assert p_virtual[0] == pytest.approx(10.0)
    assert p_virtual[1] == pytest.approx(0.0)


def test_lookahead_uses_goal_direction_when_stationary():
    papf = PredictiveArtificialPotentialField(step_length=10.0)
    agent = UGV(vec(0, 0), goal=vec(0, 100))
    p_virtual = papf.lookahead_position(agent)
    assert p_virtual[1] == pytest.approx(10.0)


def test_papf_reacts_before_plain_apf():
    """Obstacle 12 m ahead: outside APF influence (8 m) but inside the d=10
    lookahead horizon — only PAPF produces a repulsive response."""
    obstacle = Obstacle(center=(13.0, 0.0), radius=1.0)  # surface 12 m ahead
    agent = UGV(vec(0, 0), goal=vec(100, 0))
    agent.velocity = vec(3, 0, 0)
    perception = Perception(obstacles=[obstacle])

    apf = ArtificialPotentialField()
    papf = PredictiveArtificialPotentialField(step_length=10.0)

    assert norm(apf.repulsive_force(agent, perception)) == 0.0
    p_virtual = papf.lookahead_position(agent)
    assert norm(papf.repulsive_force(agent, perception, position=p_virtual)) > 0.0

    # ... and the total PAPF command therefore differs from plain APF
    assert not np.allclose(apf.compute(agent, perception), papf.compute(agent, perception))


def _run_head_on(strategy, ticks=3000):
    """Single UGV heading straight at an obstacle; returns (agent, min clearance)."""
    obstacle = Obstacle(center=(50.0, 50.0), radius=5.0)
    agent = UGV(vec(15, 50), goal=vec(85, 50), strategy=strategy)
    env = Environment(width=100, height=100)
    env.add_obstacle(obstacle)
    engine = SimulationEngine(env, [agent], dt=0.05)

    min_clearance = [float("inf")]

    def track(e):
        min_clearance[0] = min(min_clearance[0], obstacle.surface_distance(agent.position))

    engine.run(max_ticks=ticks, on_tick=track)
    return agent, min_clearance[0]


def test_path_changes_with_step_length():
    """The imaginary step bends the path: different d -> different trajectory."""
    agent_small, _ = _run_head_on(PredictiveArtificialPotentialField(step_length=2.0))
    agent_large, _ = _run_head_on(PredictiveArtificialPotentialField(step_length=12.0))
    trail_small = np.array(agent_small.trail[:1500])
    trail_large = np.array(agent_large.trail[:1500])
    n = min(len(trail_small), len(trail_large))
    assert not np.allclose(trail_small[:n], trail_large[:n])


def test_papf_keeps_more_clearance_than_plain_apf():
    """Measured behavior: PAPF's early reaction leaves a 3-5x larger safety
    margin than plain APF (~0.4 m -> ~1.3-2.2 m in the head-on scenario).
    Within PAPF, larger d starts the avoidance earlier and shortens the path,
    while min clearance is governed mostly by the immediate (non-predictive)
    term — so we assert the APF-vs-PAPF gap, which is the robust claim."""
    _, clearance_apf = _run_head_on(ArtificialPotentialField())
    for d in (2.0, 12.0):
        _, clearance_papf = _run_head_on(PredictiveArtificialPotentialField(step_length=d))
        assert clearance_papf > clearance_apf * 2


def test_papf_agents_reach_goals():
    agent, _ = _run_head_on(PredictiveArtificialPotentialField())
    assert agent.at_goal()


def test_full_scenario_with_papf():
    engine = build_demo_scenario(
        strategy=PredictiveArtificialPotentialField(step_length=8.0)
    )
    stats = engine.run(max_ticks=8000)
    assert stats.goals_reached == stats.total_agents


def test_papf_never_penetrates_obstacle():
    obstacle = Obstacle(center=(50.0, 50.0), radius=5.0)
    agent = UGV(vec(15, 50), goal=vec(85, 50),
                strategy=PredictiveArtificialPotentialField(step_length=10.0))
    env = Environment(width=100, height=100)
    env.add_obstacle(obstacle)
    engine = SimulationEngine(env, [agent], dt=0.05)

    violations = []

    def check(e):
        if obstacle.contains(agent.position):
            violations.append(e.ticks)

    engine.run(max_ticks=4000, on_tick=check)
    assert not violations
