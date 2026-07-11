"""Agent kinematics tests — KPI: HIZ (speed), İVME (acceleration), KONUM (position)."""
import math

import numpy as np
import pytest

from src.agents import AMR, DEFAULT_SPECS, UAV, UGV, USV, UUV, AgentSpec, BaseAgent, Rocket
from src.environment import Environment, Obstacle
from src.math_utils import norm, vec

DT = 0.05


# ----------------------------------------------------------------- HIZ (speed)
@pytest.mark.parametrize("cls", [UAV, UGV, AMR, USV, UUV, Rocket])
def test_speed_never_exceeds_max_speed(cls):
    agent = cls(vec(10, 10))
    for _ in range(500):
        agent.act(vec(100, 100, 100), DT)  # absürt büyük komut
        assert agent.speed <= agent.spec.max_speed + 1e-6


def test_type_speeds_are_heterogeneous():
    assert DEFAULT_SPECS["UAV"].max_speed > DEFAULT_SPECS["UGV"].max_speed > DEFAULT_SPECS["AMR"].max_speed


# ---------------------------------------------------------- İVME (acceleration)
@pytest.mark.parametrize("cls", [UAV, UGV, AMR, USV, UUV, Rocket])
def test_acceleration_is_limited(cls):
    agent = cls(vec(10, 10))
    v_before = agent.velocity.copy()
    agent.act(vec(1000, 0, 0), DT)
    dv = norm(agent.velocity - v_before)
    # friction can only reduce dv, so max_accel*dt is a valid upper bound
    assert dv <= agent.spec.max_accel * DT + 1e-6


# ------------------------------------------------------------- KONUM (position)
def test_position_updates_by_velocity_times_dt():
    uav = UAV(vec(10, 10, 20))
    uav.act(vec(1, 0, 0), 1.0)  # v = 1 m/s sonrası konum +v*dt
    assert uav.position[0] == pytest.approx(10 + uav.velocity[0], rel=1e-6)


def test_ground_agents_stay_on_the_plane():
    for cls in (UGV, AMR):
        agent = cls(vec(10, 10))
        for _ in range(200):
            agent.act(vec(1, 1, 5), DT)  # z yönünde itmeye çalış
            assert agent.position[2] == 0.0
            assert agent.velocity[2] == 0.0


def test_uav_moves_in_3d_and_respects_altitude_band():
    uav = UAV(vec(10, 10, 20), min_altitude=2.0, max_altitude=40.0)
    for _ in range(400):
        uav.act(vec(0, 0, 10), DT)  # sürekli yukarı it
    assert uav.position[2] == pytest.approx(40.0)
    for _ in range(800):
        uav.act(vec(0, 0, -10), DT)  # sürekli aşağı it
    assert uav.position[2] == pytest.approx(2.0)


def test_uav_spawns_at_cruise_altitude_when_z_missing():
    uav = UAV(vec(5, 5), cruise_altitude=17.0, goal=vec(50, 50))
    assert uav.position[2] == pytest.approx(17.0)
    assert uav.goal[2] == pytest.approx(17.0)


def test_ugv_friction_slows_it_down():
    ugv = UGV(vec(10, 10))
    ugv.velocity = vec(4, 0, 0)
    ugv.act(vec(0, 0, 0), DT)  # gaz yok
    assert norm(ugv.velocity) < 4.0


def test_ugv_turn_rate_is_limited():
    ugv = UGV(vec(10, 10))
    ugv.velocity = vec(3, 0, 0)  # doğuya gidiyor
    ugv.act(vec(0, ugv.spec.max_accel, 0), DT)  # sert kuzey komutu
    heading = math.degrees(math.atan2(ugv.velocity[1], ugv.velocity[0]))
    max_turn_deg = ugv.spec.max_turn_rate * DT
    assert abs(heading) <= max_turn_deg + 1e-6


def test_amr_is_omnidirectional():
    amr = AMR(vec(10, 10))
    amr.velocity = vec(1, 0, 0)
    amr.act(vec(0, amr.spec.max_accel, 0), DT)
    # AMR'de dönüş kısıtı yok. y bileşeni tam olarak accel*dt (sürtünme çarpanı hariç) kadar artar
    assert amr.velocity[1] > 0


# ------------------------------------------------------------------ parametre
def test_each_type_has_its_own_parameter_set():
    keys = {"UAV", "UGV", "AMR", "USV", "UUV", "ROCKET"}
    assert set(DEFAULT_SPECS) == keys
    for spec in DEFAULT_SPECS.values():
        assert spec.max_speed > 0
        assert spec.sensor_range > 0
        assert spec.task_capacity > 0
        assert spec.cost_per_hour > 0


def test_agent_ids_are_unique():
    a, b, c = UAV(vec(0, 0)), UGV(vec(1, 1)), AMR(vec(2, 2))
    assert len({a.id, b.id, c.id}) == 3


# ----------------------------------------------------------------------- sense
def test_sense_filters_by_sensor_range():
    spec = AgentSpec(max_speed=5, max_accel=2, sensor_range=10,
                     task_capacity=1, cost_per_hour=1)
    a = AMR(vec(0, 0), spec=spec)
    near = AMR(vec(5, 0), spec=spec)
    far = AMR(vec(50, 0), spec=spec)
    env = Environment()
    perception = a.sense(env, [a, near, far])
    assert near in perception.neighbors
    assert far not in perception.neighbors
    assert a not in perception.neighbors


def test_sense_ignores_obstacles_above_uav():
    env = Environment()
    env.add_obstacle(Obstacle(center=(12.0, 0.0), radius=2.0, height=10.0))
    low_uav = UAV(vec(10, 0, 5))
    high_uav = UAV(vec(10, 0, 25))
    assert len(low_uav.sense(env, []).obstacles) == 1
    assert len(high_uav.sense(env, []).obstacles) == 0


def test_at_goal_with_tolerance():
    amr = AMR(vec(0, 0), goal=vec(1, 0))
    assert amr.at_goal()  # varsayılan tolerans 1.5 m
    amr2 = AMR(vec(0, 0), goal=vec(10, 0))
    assert not amr2.at_goal()


def test_base_agent_is_abstract():
    with pytest.raises(TypeError):
        BaseAgent(vec(0, 0), DEFAULT_SPECS["AMR"])  # type: ignore[abstract]
