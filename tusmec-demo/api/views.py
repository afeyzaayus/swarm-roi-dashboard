"""REST API — motoru saran ince katman.

POST /api/sim/start   {area_m2, uav, ugv, amr, scenario?}  -> oturum başlatır
GET  /api/sim/state                                        -> güncel snapshot
POST /api/sim/stop                                         -> oturumu durdurur
GET  /api/scenarios                                        -> 3 segment şablonu
POST /api/roi         RoiInputs alanları                   -> ROI çıktıları
"""
import json
from dataclasses import asdict

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from roi.calculator import RoiInputs, compute_roi, fleet_monthly_cost_from_simulation
from roi.scenarios import SCENARIOS
from simbridge.session import MANAGER


def _body(request) -> dict:
    if not request.body:
        return {}
    try:
        return json.loads(request.body)
    except json.JSONDecodeError:
        return {}


@csrf_exempt
@require_POST
def sim_start(request):
    config = _body(request)
    scenario_key = config.pop("scenario", None)
    if scenario_key in SCENARIOS:
        base = SCENARIOS[scenario_key]
        merged = {"area_m2": base["area_m2"], **base["fleet"]}
        merged.update(config)  # kullanıcı girdisi şablonu ezebilir
        config = merged
    session = MANAGER.start(config)
    return JsonResponse({"ok": True, "session_id": session.session_id,
                         "engine": session.engine_kind})


@require_GET
def sim_state(request):
    session = MANAGER.current()
    if session is None:
        return JsonResponse({"ok": False, "error": "Aktif simülasyon yok. Önce /api/sim/start çağırın."}, status=404)
    return JsonResponse({"ok": True, **session.snapshot()})


@csrf_exempt
@require_POST
def sim_stop(request):
    MANAGER.stop()
    return JsonResponse({"ok": True})


@csrf_exempt
@require_POST
def obstacle_move(request):
    """Sürükle-bırak: {index, x, y} — engeli canlı simülasyonda taşır."""
    session = MANAGER.current()
    if session is None:
        return JsonResponse({"ok": False, "error": "Aktif simülasyon yok."}, status=404)
    data = _body(request)
    try:
        moved = session.move_obstacle(int(data["index"]), float(data["x"]), float(data["y"]))
    except (KeyError, TypeError, ValueError) as exc:
        return JsonResponse({"ok": False, "error": f"Eksik/geçersiz alan: {exc}"}, status=400)
    if not moved:
        return JsonResponse({"ok": False, "error": "Geçersiz engel indeksi."}, status=400)
    return JsonResponse({"ok": True})


@require_GET
def scenarios(request):
    return JsonResponse({"ok": True, "scenarios": SCENARIOS})


@csrf_exempt
@require_POST
def roi(request):
    data = _body(request)
    try:
        usd_rate = float(data.get("usd_rate", 1.0))
        fleet_op = data.get("fleet_monthly_operating")
        if fleet_op is None:
            # Girilmemişse simülasyonun saatlik maliyetinden türet.
            session = MANAGER.current()
            cph = 0.0
            if session is not None:
                snap = session.snapshot()
                sim_time_h = max(snap["stats"]["sim_time"] / 3600.0, 1e-9)
                cph = snap["stats"]["total_cost_usd"] / sim_time_h
            fleet_op = fleet_monthly_cost_from_simulation(
                cph,
                float(data.get("days_per_month", 26)),
                usd_rate,
            )
        inputs = RoiInputs(
            current_monthly_cost=float(data["current_monthly_cost"]),
            tusmec_monthly_license=float(data["tusmec_monthly_license"]),
            fleet_monthly_operating=float(fleet_op),
            setup_cost=float(data.get("setup_cost", 0)),
            usd_rate=usd_rate,
        )
    except (KeyError, TypeError, ValueError) as exc:
        return JsonResponse({"ok": False, "error": f"Eksik/geçersiz alan: {exc}"}, status=400)
    out = compute_roi(inputs)
    return JsonResponse({
        "ok": True,
        "task_type": data.get("task_type"),
        "inputs": asdict(inputs),
        "outputs": asdict(out),
    })
