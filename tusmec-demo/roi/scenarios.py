"""Müşteri segmentine göre 3 örnek senaryo şablonu (görev zorunluluğu).

Segmentler Hafta 1 raporundaki müşteri portföyü ve çözüm hatlarıyla uyumlu:
- Depo:    OMNIBOT / AMR ağırlıklı iç lojistik (rapor §5.2, en büyük segment)
- Tarım:   Agraden İHA + Farswarm İKA koordinasyonu (rapor §5.1)
- Savunma: İHA-İKA eş güdümlü devriye/keşif (rapor §5.4)

Maliyet rakamları temsili PLACEHOLDER'dır — rapor §9'daki kendi önerin
uyarınca segment bazlı gerçek işçilik/yakıt/bakım kalemleri danışmandan
alınıp buradaki değerlerle değiştirilmelidir.
"""

SCENARIOS = {
    "depo_lojistigi": {
        "label": "Depo Lojistiği",
        "description": "E-ticaret deposunda sipariş toplama ve palet transferi — OMNIBOT/AMR filosu",
        "task_type": "depo_lojistigi",
        "area_m2": 8_000,
        "fleet": {"uav": 0, "ugv": 1, "amr": 6},
        "current_monthly_cost": 450_000,   # TL — 6 depo personeli + forklift yakıt/bakım (temsili)
        "tusmec_monthly_license": 120_000, # TL — aylık SaaS (temsili)
        "setup_cost": 900_000,             # TL — robot kurulum/devreye alma (temsili)
    },
    "tarim": {
        "label": "Tarım",
        "description": "İlaçlama ve mahsul izleme — Agraden İHA + Farswarm İKA koordinasyonu",
        "task_type": "tarim",
        "area_m2": 200_000,
        "fleet": {"uav": 4, "ugv": 2, "amr": 0},
        "current_monthly_cost": 300_000,
        "tusmec_monthly_license": 90_000,
        "setup_cost": 600_000,
    },
    "guvenlik_devriyesi": {
        "label": "Güvenlik / Savunma Devriyesi",
        "description": "Tesis çevre güvenliği — İHA-İKA eş güdümlü devriye ve gözetleme",
        "task_type": "guvenlik_devriyesi",
        "area_m2": 50_000,
        "fleet": {"uav": 3, "ugv": 3, "amr": 0},
        "current_monthly_cost": 600_000,
        "tusmec_monthly_license": 180_000,
        "setup_cost": 1_500_000,
    },
}
