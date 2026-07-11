import json

from simbridge.session import SimulationSession

config = {
    "n_obstacles": 8,
    "seed": 123456
}

sess = SimulationSession(config)
snap = sess.snapshot()
print("Obstacles count:", len(snap["obstacles"]))
print("Obstacles 0:", snap["obstacles"][0] if snap["obstacles"] else None)

