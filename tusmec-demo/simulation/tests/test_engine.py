"""Engine tests: tick loop, world snapshot semantics, full-scenario integration."""
import numpy as np
import pytest

from src.agents import AMR, UAV, UGV
from src.coordination import ArtificialPotentialField
from src.engine import SimulationEngine
from src.environment import Environment, Obstacle
from src.math_utils import norm, vec


def make_engine(agents, obstacles=(), dt=0.05):
    env = Environment(width=100, height=100, ceiling=45)
    for o in obstacles:
        env.add_obstacle(o)
    return SimulationEngine(env, agents, dt=dt)


def test_invalid_dt_raises():
    with pytest.raises(ValueError):
        SimulationEngine(Environment(), [], dt=0.0)


def test_tick_advances_time_and_counter():
    engine = make_engine([AMR(vec(10, 10))])
    engine.tick()
    engine.tick()
    assert engine.ticks == 2
    assert engine.sim_time == pytest.approx(0.1)


def test_agents_stay_inside_world_bounds():
    apf = ArtificialPotentialField()
    # hedefi kasten dünyanın dışına koy
    agent = UAV(vec(95, 95, 20), goal=vec(500, 500, 20), strategy=apf)
    engine = make_engine([agent])
    engine.run(max_ticks=400, stop_when_done=False)
    env = engine.environment
    assert 0 <= agent.position[0] <= env.width
    assert 0 <= agent.position[1] <= env.height
    assert 0 <= agent.position[2] <= env.ceiling


def test_heterogeneous_swarm_reaches_goals():
    """KPI: 3 ajan tipi aynı anda simüle ediliyor ve APF çalışır durumda."""
    apf = ArtificialPotentialField()
    agents = [
        UAV(vec(10, 10), goal=vec(80, 80), strategy=apf),
        UGV(vec(10, 20), goal=vec(75, 70), strategy=apf),
        AMR(vec(20, 10), goal=vec(40, 32), strategy=apf),
    ]
    engine = make_engine(agents, obstacles=[Obstacle(center=(45.0, 45.0), radius=4.0, height=8.0)])
    stats = engine.run(max_ticks=4000)
    assert stats.goals_reached == 3
    assert set(stats.per_type) == {"UAV", "UGV", "AMR"}


def test_ground_agent_avoids_obstacle():
    """Ajan hiçbir tick'te engelin içine girmemeli."""
    apf = ArtificialPotentialField()
    obstacle = Obstacle(center=(50.0, 50.0), radius=5.0)
    agent = UGV(vec(20, 50), goal=vec(80, 50), strategy=apf)
    engine = make_engine([agent], obstacles=[obstacle])

    violations = []

    def check(e):
        if obstacle.contains(agent.position):
            violations.append(e.ticks)

    engine.run(max_ticks=4000, on_tick=check)
    assert not violations


def test_uav_flies_over_short_obstacle_straight():
    """20 m'de uçan UAV, 10 m'lik engeli algılamaz ve düz geçer."""
    apf = ArtificialPotentialField()
    obstacle = Obstacle(center=(50.0, 50.0), radius=5.0, height=10.0)
    uav = UAV(vec(20, 50, 20), goal=vec(80, 50, 20), strategy=apf)
    engine = make_engine([uav], obstacles=[obstacle])
    engine.run(max_ticks=2000)
    assert uav.at_goal()
    # düz hat ~60 m; sapma olsaydı yol belirgin uzardı
    assert uav.distance_travelled < 70.0


def test_agents_keep_separation():
    """Aynı hedefe giden iki ajan çarpışmamalı (min mesafe korunmalı)."""
    apf = ArtificialPotentialField()
    a = AMR(vec(10, 50), goal=vec(80, 50), strategy=apf)
    b = AMR(vec(10, 52), goal=vec(80, 52), strategy=apf)
    engine = make_engine([a, b])

    min_dist = [float("inf")]

    def track(e):
        min_dist[0] = min(min_dist[0], norm(a.position - b.position))

    engine.run(max_ticks=4000, on_tick=track)
    assert min_dist[0] > 0.5  # gövde çarpışması yok


def test_stats_accumulate():
    apf = ArtificialPotentialField()
    agent = AMR(vec(10, 10), goal=vec(30, 30), strategy=apf)
    engine = make_engine([agent])
    stats = engine.run(max_ticks=3000)
    assert stats.total_distance > 0
    assert stats.total_cost > 0
    assert stats.total_agents == 1


def test_run_stops_early_when_all_goals_reached():
    apf = ArtificialPotentialField()
    agent = AMR(vec(10, 10), goal=vec(12, 10), strategy=apf)  # çok yakın hedef
    engine = make_engine([agent])
    stats = engine.run(max_ticks=5000)
    assert stats.ticks < 5000
    assert engine.all_goals_reached()
