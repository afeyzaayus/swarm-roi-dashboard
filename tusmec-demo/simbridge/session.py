"""Web oturum katmanı — ros2_bridge.py'nin web kardeşi.

SimulationSession bir SimulationEngine örneğini arka plan thread'inde
gerçek zamanlı tick'ler ve her tick sonrası kilit altında bir JSON snapshot
günceller. API katmanı yalnızca bu snapshot'ı okur; motor koduna dokunmaz.
"""
from __future__ import annotations

import threading
import time
import uuid

from .engine_loader import load_engine_module

TICK_HZ = 20          # motor saniyede kaç kez tick'lenir
MAX_SIM_SECONDS = 600  # emniyet: 10 dk sonra oturum kendini durdurur


def _agent_type(agent) -> str:
    """Gerçek ve mock ajanlar için tip adını tek biçime indirger."""
    for attr in ("type_key",):
        if hasattr(agent, attr):
            return str(getattr(agent, attr)).lower()
    spec = getattr(agent, "spec", None)
    for attr in ("type_name", "name"):
        if spec is not None and hasattr(spec, attr):
            return str(getattr(spec, attr)).lower()
    return type(agent).__name__.lower()


class SimulationSession:
    def __init__(self, config: dict):
        self.session_id = uuid.uuid4().hex[:8]
        self.config = config
        self._engine = self._build_engine(config)
        self._lock = threading.Lock()
        self._snapshot: dict = {}
        self._running = False
        self._thread: threading.Thread | None = None
        self._refresh_snapshot()

    # ------------------------------------------------------------- kurulum
    def _build_engine(self, config: dict):
        module = load_engine_module()
        area = float(config.get("area_m2", 10_000))
        fleet = {
            "uav": int(config.get("uav", 0)),
            "ugv": int(config.get("ugv", 0)),
            "amr": int(config.get("amr", 0)),
        }
        if sum(fleet.values()) == 0:
            fleet = {"uav": 3, "ugv": 2, "amr": 3}
        import random
        seed_val = config.get("seed")
        if seed_val is None:
            seed_val = random.randint(1, 999999)
        else:
            seed_val = int(seed_val)

        obstacle_cfg = {
            "n_obstacles": int(config.get("n_obstacles", config.get("obs-n", 5))),
            "obstacle_h_min": float(config.get("obstacle_h_min", 8)),
            "obstacle_h_max": float(config.get("obstacle_h_max", 25)),
            "seed": seed_val,
        }

        if module["kind"] == "mock":
            self.engine_kind = "mock"
            return module["module"].build_scenario(area, fleet, **obstacle_cfg)

        self.engine_kind = "real"
        from . import web_scenario  # engine_loader sys.path'i ayarladı
        return web_scenario.build_web_scenario(area_m2=area, fleet=fleet, **obstacle_cfg)

    # --------------------------------------------------------------- döngü
    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def _loop(self):
        dt = 1.0 / TICK_HZ
        started = time.monotonic()
        while self._running:
            t0 = time.monotonic()
            self._engine.tick()
            self._refresh_snapshot()
            if time.monotonic() - started > MAX_SIM_SECONDS:
                self._running = False
                break
            elapsed = time.monotonic() - t0
            time.sleep(max(0.0, dt - elapsed))

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    # ------------------------------------------------------------ snapshot
    def _refresh_snapshot(self):
        import math

        env = getattr(self._engine, "environment", None)
        # Gerçek motorda stats bir metot, mock'ta attribute — ikisini de destekle.
        stats = getattr(self._engine, "stats", None)
        if callable(stats):
            stats = stats()
        agents = []
        for agent in getattr(self._engine, "agents", []):
            pos = agent.position
            goal = getattr(agent, "goal", None)
            if hasattr(agent, "at_goal"):
                reached = bool(agent.at_goal())
            else:
                reached = bool(getattr(agent, "reached", False))
            agents.append(
                {
                    "id": getattr(agent, "agent_id", id(agent) % 100000),
                    "type": _agent_type(agent),
                    "x": float(pos[0]),
                    "y": float(pos[1]),
                    "z": float(pos[2]) if len(pos) > 2 else 0.0,
                    "goal": [float(goal[0]), float(goal[1])] if goal is not None else None,
                    "reached": reached,
                }
            )
        obstacles = []
        if env is not None:
            for i, ob in enumerate(getattr(env, "obstacles", [])):
                h = float(getattr(ob, "height", 10.0))
                obstacles.append(
                    {
                        "index": i,
                        "x": float(ob.center[0]),
                        "y": float(ob.center[1]),
                        "radius": float(ob.radius),
                        # inf JSON'a yazılamaz: None + infinite bayrağı
                        "height": None if math.isinf(h) else round(h, 1),
                        "infinite": math.isinf(h),
                    }
                )
        snapshot = {
            "session_id": self.session_id,
            "engine": self.engine_kind,
            "running": self._running,
            "world": {
                "width": float(getattr(env, "width", 100.0)),
                "height": float(getattr(env, "height", 100.0)),
            },
            "agents": agents,
            "obstacles": obstacles,
            "stats": {
                "ticks": getattr(stats, "ticks", 0),
                "sim_time": round(getattr(stats, "sim_time", 0.0), 2),
                "goals_reached": getattr(stats, "goals_reached", 0),
                "total_agents": len(agents),
                "total_distance": round(getattr(stats, "total_distance", 0.0), 1),
                "total_cost_usd": round(getattr(stats, "total_cost", 0.0), 4),
            },
        }
        with self._lock:
            self._snapshot = snapshot

    def move_obstacle(self, index: int, x: float, y: float) -> bool:
        """Sürükle-bırak: engelin merkezini canlı simülasyonda taşır.

        Ajanlar bir sonraki tick'te engeli yeni yerinde algılar (sense
        aşaması engelleri her tick yeniden okur) — motor kodunda değişiklik
        gerekmez. Merkez, dünya sınırlarına kısıtlanır.
        """
        env = getattr(self._engine, "environment", None)
        obstacles = getattr(env, "obstacles", []) if env else []
        if not 0 <= index < len(obstacles):
            return False
        ob = obstacles[index]
        x = min(max(float(x), 0.0), float(env.width))
        y = min(max(float(y), 0.0), float(env.height))
        ob.center = (x, y)
        self._refresh_snapshot()
        return True

    def snapshot(self) -> dict:
        with self._lock:
            snap = dict(self._snapshot)
        snap["running"] = self._running
        return snap


class SessionManager:
    """Demo için tek aktif oturum tutan basit yönetici (thread-safe)."""

    def __init__(self):
        self._lock = threading.Lock()
        self._session: SimulationSession | None = None

    def start(self, config: dict) -> SimulationSession:
        with self._lock:
            if self._session is not None:
                self._session.stop()
            self._session = SimulationSession(config)
            self._session.start()
            return self._session

    def current(self) -> SimulationSession | None:
        with self._lock:
            return self._session

    def stop(self):
        with self._lock:
            if self._session is not None:
                self._session.stop()


MANAGER = SessionManager()
