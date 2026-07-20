"""Hafta 2 simülasyon motorunu yükler.

Gerçek motor `simulation/src/` altında beklenir (Hafta 2 projesinin `src`
klasörünü olduğu gibi buraya kopyala). Bulunamazsa, aynı arayüzü taklit eden
küçük bir yedek (mock) motor kullanılır ki web katmanı motorsuz da
geliştirilebilsin. Sunucu açılırken hangi motorun yüklendiği loglanır.

Web katmanının motordan beklediği asgari arayüz:
    engine.tick()                      -> bir simülasyon adımı
    engine.agents                      -> her biri .position (np array [x,y,z])
                                          ve tip adı taşıyan ajan listesi
    engine.stats                       -> ticks, sim_time, goals_reached,
                                          total_distance, total_cost alanları
    engine.environment.obstacles       -> .center (x,y), .radius, .height
    engine.environment.width / .height (ya da bounds)
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

log = logging.getLogger(__name__)

SIMULATION_DIR = Path(__file__).resolve().parent.parent / "simulation"


def _try_real_engine():
    """simulation/src varsa Hafta 2 motorunu import eder."""
    if not (SIMULATION_DIR / "src").exists():
        return None
    if str(SIMULATION_DIR) not in sys.path:
        sys.path.insert(0, str(SIMULATION_DIR))
    try:
        from src.engine import SimulationEngine          # noqa: F401
        from src.environment import Environment          # noqa: F401
        from src import agents as agent_module           # noqa: F401
        log.info("Gerçek simülasyon motoru yüklendi: %s", SIMULATION_DIR / "src")
        return {
            "kind": "real",
            "SimulationEngine": SimulationEngine,
            "Environment": Environment,
            "agents": agent_module,
        }
    except Exception as exc:  # pragma: no cover - ortama bağlı
        log.warning("simulation/src bulundu ama import edilemedi: %s", exc)
        return None


def load_engine_module():
    real = _try_real_engine()
    if real is not None:
        return real
    from . import mock_engine
    log.warning(
        "Simülasyon motoru bulunamadı, MOCK motor kullanılıyor. "
        "Gerçek motor için simülasyon projesinin src/ klasörünü %s altına kopyala.",
        SIMULATION_DIR,
    )
    return {"kind": "mock", "module": mock_engine}
