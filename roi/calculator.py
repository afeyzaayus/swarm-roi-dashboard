"""ROI hesaplama modülü — Django'dan bağımsız saf fonksiyonlar.

KPI gereği çıktılar manuel doğrulamayla karşılaştırılacağı için tüm hesap
burada, yan etkisiz fonksiyonlarda tutulur ve tests/ altında elle hesaplanmış
örneklerle doğrulanır.

Varsayımlar (danışmanla teyit edilecek):
- Tusmec modeli SaaS ağırlıklı (Hafta 1 raporu, hibrit gelir modeli):
  aylık lisans + opsiyonel bir defalık kurulum maliyeti (capex).
- Filo işletme maliyeti simülasyondan (cost_per_hour toplamı) veya
  kullanıcı girdisinden gelebilir; ikisi de desteklenir.
"""
from __future__ import annotations

from dataclasses import dataclass

HORIZON_MONTHS = 60  # 5 yıl


@dataclass(frozen=True)
class RoiInputs:
    current_monthly_cost: float      # mevcut operasyon: işçilik + yakıt + bakım (TL/ay)
    tusmec_monthly_license: float    # aylık SaaS lisansı (TL/ay)
    fleet_monthly_operating: float   # filo işletme maliyeti (TL/ay)
    setup_cost: float = 0.0          # bir defalık kurulum/capex (TL), opsiyonel
    usd_rate: float = 1.0            # 1 USD kaç TL (USD çıktıları için)


@dataclass(frozen=True)
class RoiOutputs:
    monthly_saving_tl: float
    annual_saving_tl: float
    monthly_saving_usd: float
    annual_saving_usd: float
    payback_months: float | None     # None: tasarruf yoksa geri ödeme yok
    five_year_roi_pct: float
    cumulative_current: list         # 0..60 ay, mevcut durum kümülatif maliyet
    cumulative_tusmec: list          # 0..60 ay, Tusmec kümülatif maliyet


def fleet_monthly_cost_from_simulation(
    cost_per_hour_usd: float, hours_per_day: float, days_per_month: float, usd_rate: float
) -> float:
    """Simülasyonun ürettiği saatlik filo maliyetini aylık TL'ye çevirir.

    Demo'nun satış toplantısındaki asıl kozu: bu rakam uydurma değil,
    motorun cost_per_hour verisinden geliyor.
    """
    return cost_per_hour_usd * usd_rate * hours_per_day * days_per_month


def compute_roi(inp: RoiInputs) -> RoiOutputs:
    tusmec_monthly = inp.tusmec_monthly_license + inp.fleet_monthly_operating
    monthly_saving = inp.current_monthly_cost - tusmec_monthly

    # Geri ödeme: kurulum maliyetinin aylık tasarrufla amorti edilmesi.
    if monthly_saving <= 0:
        payback = None
    elif inp.setup_cost <= 0:
        payback = 0.0  # saf SaaS: ilk aydan itibaren tasarruf
    else:
        payback = inp.setup_cost / monthly_saving

    # 5 yıllık ROI: net kazanç / toplam Tusmec yatırımı.
    total_saving = monthly_saving * HORIZON_MONTHS
    total_investment = inp.setup_cost + tusmec_monthly * HORIZON_MONTHS
    roi_pct = (total_saving - inp.setup_cost) / total_investment * 100 if total_investment > 0 else 0.0

    # Karşılaştırma grafiği için kümülatif eğriler (ay 0..60).
    cum_current, cum_tusmec = [], []
    for m in range(HORIZON_MONTHS + 1):
        cum_current.append(round(inp.current_monthly_cost * m, 2))
        cum_tusmec.append(round(inp.setup_cost + tusmec_monthly * m, 2))

    r = inp.usd_rate if inp.usd_rate > 0 else 1.0
    return RoiOutputs(
        monthly_saving_tl=round(monthly_saving, 2),
        annual_saving_tl=round(monthly_saving * 12, 2),
        monthly_saving_usd=round(monthly_saving / r, 2),
        annual_saving_usd=round(monthly_saving * 12 / r, 2),
        payback_months=None if payback is None else round(payback, 1),
        five_year_roi_pct=round(roi_pct, 1),
        cumulative_current=cum_current,
        cumulative_tusmec=cum_tusmec,
    )
