"""APF coordination tests: attraction, repulsion, separation."""
import numpy as np
import pytest

from src.agents import AMR, UAV, Perception
from src.coordination import ArtificialPotentialField
from src.environment import Environment, Obstacle
from src.math_utils import norm, normalize, vec


@pytest.fixture
def apf():
    return ArtificialPotentialField()


def test_attractive_force_points_to_goal(apf):
    agent = AMR(vec(0, 0), goal=vec(10, 0))
    force = apf.attractive_force(agent)
    assert force[0] > 0
    assert force[1] == pytest.approx(0.0)


def test_attractive_force_zero_without_goal(apf):
    agent = AMR(vec(0, 0))
    assert norm(apf.attractive_force(agent)) == 0.0


def test_repulsive_force_pushes_away_from_obstacle(apf):
    agent = AMR(vec(10, 0))
    obstacle = Obstacle(center=(13.0, 0.0), radius=1.0)  # sağda, yüzeye 2 m
    perception = Perception(obstacles=[obstacle])
    force = apf.repulsive_force(agent, perception)
    assert force[0] < 0  # engelden uzağa (sola) iter


def test_repulsion_zero_outside_influence(apf):
    agent = AMR(vec(0, 0))
    obstacle = Obstacle(center=(50.0, 0.0), radius=1.0)
    perception = Perception(obstacles=[obstacle])
    assert norm(apf.repulsive_force(agent, perception)) == 0.0


def test_repulsion_grows_as_agent_gets_closer(apf):
    obstacle = Obstacle(center=(10.0, 0.0), radius=1.0)
    near = AMR(vec(8.0, 0.0))   # yüzeye 1 m
    far = AMR(vec(4.0, 0.0))    # yüzeye 5 m
    f_near = norm(apf.repulsive_force(near, Perception(obstacles=[obstacle])))
    f_far = norm(apf.repulsive_force(far, Perception(obstacles=[obstacle])))
    assert f_near > f_far


def test_separation_pushes_agents_apart(apf):
    a = AMR(vec(0, 0))
    b = AMR(vec(1, 0))
    force = apf.separation_force(a, Perception(neighbors=[b]))
    assert force[0] < 0  # komşusundan uzağa


def test_compute_respects_max_accel(apf):
    agent = AMR(vec(0, 0), goal=vec(1000, 1000))
    accel = apf.compute(agent, Perception())
    assert norm(accel) <= agent.spec.max_accel + 1e-9


def test_apf_moves_agent_toward_goal_over_time(apf):
    """Entegrasyon: APF ile ajan gerçekten hedefe yaklaşmalı."""
    agent = UAV(vec(5, 5, 15), goal=vec(60, 60, 15), strategy=apf)
    env = Environment()
    start = norm(agent.goal - agent.position)
    for _ in range(600):
        perception = agent.sense(env, [agent])
        agent.act(agent.think(perception), 0.05)
    end = norm(agent.goal - agent.position)
    assert end < start * 0.2  # en az %80 yaklaşmış olmalı
