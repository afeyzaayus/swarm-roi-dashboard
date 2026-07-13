"""Web formundan gelen parametrelerle GERÇEK motor senaryosu kurar.

build_demo_scenario'nun parametreli kardeşi. src/ klasörüne dokunmaz;
motorun genel API'sini (Environment, Obstacle, ajan sınıfları,
SimulationEngine) kullanarak dışarıdan senaryo inşa eder.

Kurallar:
- Alan: kare dünya, kenar = sqrt(area_m2). Motor birimi metre olduğundan
  m² doğrudan ölçeklenir.
- Engeller: sayısı ve yükseklik aralığı kullanıcıdan, konum/yarıçap rastgele
  (seed ile tekrarlanabilir). Konumlar orta banda atılır ki başlangıç ve
  hedef bölgeleri kapanmasın.
- Ajanlar: sol bantta başlar, sağ banttaki hedeflere gider; UAV'ler 20 m
  seyir irtifasında (10-15 m'lik engellerin üstünden aşar — Hafta 2'deki
  heterojenlik gösterimi aynen korunur).
"""
from __future__ import annotations

import math
import random

from src.agents import AMR, UAV, UGV
from src.coordination import ArtificialPotentialField, PredictiveArtificialPotentialField
from src.engine import SimulationEngine
from src.environment import Environment, Obstacle
from src.math_utils import vec

UAV_CRUISE = 20.0
MIN_SIDE = 40.0  # çok küçük alanlarda ajanlar üst üste binmesin


def _free_point(rng: random.Random, env: Environment,
                x_lo: float, x_hi: float) -> tuple[float, float]:
    """Verilen x bandında, hiçbir engelin içine düşmeyen rastgele nokta."""
    for _ in range(200):
        x = rng.uniform(x_lo, x_hi)
        y = rng.uniform(0.05 * env.height, 0.95 * env.height)
        if all(math.hypot(x - o.center[0], y - o.center[1]) > o.radius + 2.0
               for o in env.obstacles):
            return x, y
    return x_lo, env.height / 2  # teorik köşe durumu


def build_web_scenario(
    area_m2: float,
    fleet: dict,
    n_obstacles: int = 5,
    obstacle_h_min: float = 8.0,
    obstacle_h_max: float = 25.0,
    seed: int = 42,
    strategy=None,
) -> SimulationEngine:
    rng = random.Random(seed)
    side = max(math.sqrt(max(area_m2, 100.0)), MIN_SIDE)
    env = Environment(width=side, height=side, ceiling=45.0, floor=0.0)

    h_lo, h_hi = sorted((float(obstacle_h_min), float(obstacle_h_max)))
    
    attempts = 0
    target_obs = max(0, int(n_obstacles))
    while len(env.obstacles) < target_obs and attempts < 100 * target_obs:
        attempts += 1
        r = rng.uniform(max(2.0, side * 0.02), max(3.0, side * 0.06))
        cx = rng.uniform(0.25, 0.80) * side
        cy = rng.uniform(0.10, 0.90) * side
        
        overlap = False
        for ob in env.obstacles:
            if math.hypot(cx - ob.center[0], cy - ob.center[1]) < (r + ob.radius + 1.0):
                overlap = True
                break
                
        if not overlap:
            env.add_obstacle(Obstacle(
                center=(cx, cy),
                radius=r,
                height=rng.uniform(h_lo, h_hi),
            ))

    apf = strategy if strategy is not None else PredictiveArtificialPotentialField()
    classes = {"uav": UAV, "ugv": UGV, "amr": AMR}
    agents = []
    for key, count in fleet.items():
        cls = classes.get(key)
        if cls is None:
            continue
        for _ in range(int(count)):
            sx, sy = _free_point(rng, env, 0.02 * side, 0.15 * side)
            gx, gy = _free_point(rng, env, 0.85 * side, 0.98 * side)
            kwargs = {"strategy": apf}
            if cls is UAV:
                kwargs["cruise_altitude"] = UAV_CRUISE
            agents.append(cls(vec(sx, sy), goal=vec(gx, gy), **kwargs))
    return SimulationEngine(env, agents, dt=0.05)
