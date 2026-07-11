from simbridge.session import MANAGER
from simbridge.mock_engine import build_scenario
from simbridge.session import SimulationSession

print("Trying SimulationSession directly with n_obstacles=8, seed=1234")
s = SimulationSession({
    "area_m2": 10000,
    "n_obstacles": 8,
    "seed": 1234,
})
print("Direct obstacles:", len(s.snapshot()["obstacles"]))

print("Trying SimulationSession with scenario='depo', n_obstacles=8, seed=1234")
# Like what sim_start does
config = {
    "scenario": "depo",
    "area_m2": 10000,
    "n_obstacles": 8,
    "seed": 1234,
    "fleet": {"uav":0, "ugv":1, "amr":6}
}
from api.views import SCENARIOS
scenario_key = config.pop("scenario", None)
if scenario_key in SCENARIOS:
    base = SCENARIOS[scenario_key]
    merged = {"area_m2": base["area_m2"], **base["fleet"]}
    merged.update(config)
    config = merged

print("Config to MANAGER:", config)
sess = MANAGER.start(config)
print("Obstacles count:", len(sess.snapshot()["obstacles"]))

