import requests
import json

resp = requests.post("http://127.0.0.1:8000/api/sim/start", json={
    "scenario": "depo",
    "area_m2": 10000,
    "uav": 3,
    "ugv": 2,
    "amr": 3,
    "n_obstacles": 8,
    "seed": 99999
})
print("Start response:", resp.text)
state = requests.get("http://127.0.0.1:8000/api/sim/state").json()
print("Obstacles count:", len(state.get("obstacles", [])))
