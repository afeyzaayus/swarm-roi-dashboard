"""ROI modülü testleri — her beklenen değer elle hesaplanmıştır.

KPI: "ROI çıktıları doğru hesaplanıyor mu? Manuel doğrulama, ≥%75 doğruluk."
Bu dosya o manuel doğrulamanın kayıt altına alınmış hali; README'deki
doğrulama tablosuyla birebir aynı örnekleri kullanır.
"""
import unittest

from .calculator import RoiInputs, compute_roi, fleet_monthly_cost_from_simulation


class RoiTests(unittest.TestCase):
    def test_temel_ornek_elle_hesap(self):
        # Elle hesap: Tusmec aylık = 120k + 80k = 200k
        # tasarruf = 450k - 200k = 250k/ay, yıllık 3M
        # geri ödeme = 900k / 250k = 3.6 ay
        # 5 yıl: tasarruf 15M; yatırım = 900k + 200k*60 = 12.9M
        # ROI = (15M - 0.9M) / 12.9M * 100 = 109.3
        out = compute_roi(RoiInputs(
            current_monthly_cost=450_000,
            tusmec_monthly_license=120_000,
            fleet_monthly_operating=80_000,
            setup_cost=900_000,
            usd_rate=40.0,
        ))
        self.assertAlmostEqual(out.monthly_saving_tl, 250_000)
        self.assertAlmostEqual(out.annual_saving_tl, 3_000_000)
        self.assertAlmostEqual(out.monthly_saving_usd, 6_250)
        self.assertAlmostEqual(out.payback_months, 3.6)
        self.assertAlmostEqual(out.five_year_roi_pct, 109.3)

    def test_saf_saas_kurulumsuz(self):
        # Kurulum yoksa geri ödeme 0 ay (ilk aydan tasarruf).
        out = compute_roi(RoiInputs(100_000, 40_000, 20_000, setup_cost=0, usd_rate=40))
        self.assertEqual(out.payback_months, 0.0)
        self.assertAlmostEqual(out.monthly_saving_tl, 40_000)

    def test_tasarruf_yoksa_geri_odeme_yok(self):
        out = compute_roi(RoiInputs(100_000, 90_000, 30_000, setup_cost=500_000))
        self.assertIsNone(out.payback_months)
        self.assertLess(out.monthly_saving_tl, 0)

    def test_kumulatif_egriler_kesisir(self):
        # Tasarruf varsa Tusmec eğrisi bir noktada mevcut durumun altına iner.
        out = compute_roi(RoiInputs(450_000, 120_000, 80_000, setup_cost=900_000))
        self.assertEqual(len(out.cumulative_current), 61)
        # ay 4'te: mevcut 1.8M, tusmec 0.9M + 0.8M = 1.7M -> kesişme geçilmiş
        self.assertLess(out.cumulative_tusmec[4], out.cumulative_current[4])
        self.assertGreater(out.cumulative_tusmec[3], out.cumulative_current[3])

    def test_simulasyondan_filo_maliyeti(self):
        # 13 USD/saat * 40 TL * 8 saat * 26 gün = 108_160 TL/ay
        tl = fleet_monthly_cost_from_simulation(13.0, 8, 26, 40.0)
        self.assertAlmostEqual(tl, 108_160)


if __name__ == "__main__":
    unittest.main()
