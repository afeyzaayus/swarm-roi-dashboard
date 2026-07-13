"""Filo maliyet yardımcısı — ROI sayfası bağımsız çalışabilsin diye.

ROI sayfası ayrı sekmede açıldığında canlı simülasyon oturumu olmayabilir.
Bu durumda filo işletme maliyeti, motor spec'lerindeki cost_per_hour
değerlerinden (gerçek motor varsa src.agents.SPECS, yoksa mock SPECS)
doğrudan filo adetleriyle hesaplanır.
"""
from __future__ import annotations

from .engine_loader import load_engine_module


def fleet_cost_per_hour(fleet: dict) -> float:
    """{"uav": 3, "ugv": 2, "amr": 3} -> toplam USD/saat."""
    module = load_engine_module()
    if module["kind"] == "real":
        from src.agents import DEFAULT_SPECS
        table = {
            "uav": DEFAULT_SPECS["UAV"].cost_per_hour,
            "ugv": DEFAULT_SPECS["UGV"].cost_per_hour,
            "amr": DEFAULT_SPECS["AMR"].cost_per_hour,
        }
    else:
        specs = module["module"].SPECS
        table = {k: specs[k].cost_per_hour for k in ("uav", "ugv", "amr")}
    return sum(table.get(k, 0.0) * int(n or 0) for k, n in fleet.items())
