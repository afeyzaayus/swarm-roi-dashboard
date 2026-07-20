import unittest

from .calculator import RoiInputs, compute_roi, fleet_monthly_cost_from_simulation


class RoiTests(unittest.TestCase):
    def test_temel_ornek_elle_hesap(self):
        # Elle hesap: Tusmec aylık = 120 + 170 = 290
        # tasarruf = 450 - 290 = 160/ay, yıllık 1920
        # geri ödeme = 900 / 160 = 5.625 ay (5.6)
        # 5 yıl net tasarruf = 160 * 60 = 9600
        # yatırım (kurulum + 5 yıllık lisans) = 900 + 120*60 = 8100
        # ROI = (9600 - 8100) / 8100 * 100 = 18.518... (18.5)
        
        inp = RoiInputs(
            current_monthly_cost=450,
            tusmec_monthly_license=120,
            fleet_monthly_operating=170,
            setup_cost=900,
            usd_rate=35.0,
        )
        out = compute_roi(inp)
        
        print(f"\n[+] TEST: Temel Örnek")
        print(f"    GİRDİLER: Mevcut={inp.current_monthly_cost}, Lisans={inp.tusmec_monthly_license}, Filo={inp.fleet_monthly_operating}, Kurulum={inp.setup_cost}")
        print(f"    ÇIKTILAR: ROI=%{out.five_year_roi_pct}, Aylık Tasarruf={out.monthly_saving_tl}, Amorti={out.payback_months} ay")

        self.assertAlmostEqual(out.monthly_saving_tl, 160)
        self.assertAlmostEqual(out.annual_saving_tl, 1920)
        self.assertAlmostEqual(out.monthly_saving_usd, 4.57)
        self.assertAlmostEqual(out.payback_months, 5.6)
        self.assertAlmostEqual(out.five_year_roi_pct, 18.5)

    def test_saf_saas_kurulumsuz(self):
        # Kurulum yoksa geri ödeme 0 ay (ilk aydan tasarruf).
        inp = RoiInputs(100_000, 40_000, 20_000, setup_cost=0, usd_rate=40)
        out = compute_roi(inp)
        
        print(f"\n[+] TEST: Saf SaaS (Kurulum Ücreti Yok)")
        print(f"    GİRDİLER: Mevcut={inp.current_monthly_cost}, Kurulum={inp.setup_cost}")
        print(f"    ÇIKTILAR: Amorti={out.payback_months} ay, Aylık Tasarruf={out.monthly_saving_tl}")

        self.assertEqual(out.payback_months, 0.0)
        self.assertAlmostEqual(out.monthly_saving_tl, 40_000)

    def test_tasarruf_yoksa_geri_odeme_yok(self):
        inp = RoiInputs(100_000, 90_000, 30_000, setup_cost=500_000)
        out = compute_roi(inp)

        print(f"\n[+] TEST: Tasarruf Yoksa Geri Ödeme Yok")
        print(f"    GİRDİLER: Mevcut={inp.current_monthly_cost}, Lisans+Filo={inp.tusmec_monthly_license + inp.fleet_monthly_operating}")
        print(f"    ÇIKTILAR: Amorti={out.payback_months} (Yok), Aylık Tasarruf={out.monthly_saving_tl} (Zarar)")

        self.assertIsNone(out.payback_months)
        self.assertLess(out.monthly_saving_tl, 0)

    def test_kumulatif_egriler_kesisir(self):
        # Tasarruf varsa Tusmec eğrisi bir noktada mevcut durumun altına iner.
        inp = RoiInputs(450_000, 120_000, 80_000, setup_cost=900_000)
        out = compute_roi(inp)

        print(f"\n[+] TEST: Kümülatif Eğriler Kesişir")
        print(f"    ÇIKTILAR: 3. Ay (Mevcut: {out.cumulative_current[3]} < Tusmec: {out.cumulative_tusmec[3]}), 4. Ay (Mevcut: {out.cumulative_current[4]} > Tusmec: {out.cumulative_tusmec[4]})")

        self.assertEqual(len(out.cumulative_current), 61)
        # ay 4'te: mevcut 1.8M, tusmec 0.9M + 0.8M = 1.7M -> kesişme geçilmiş
        self.assertLess(out.cumulative_tusmec[4], out.cumulative_current[4])
        self.assertGreater(out.cumulative_tusmec[3], out.cumulative_current[3])

    def test_simulasyondan_filo_maliyeti(self):
        # 13 USD/saat * 40 TL * 8 saat (sabit) * 26 gün = 108_160 TL/ay
        tl = fleet_monthly_cost_from_simulation(13.0, 40.0)
        
        print(f"\n[+] TEST: Simülasyondan Filo Maliyeti")
        print(f"    GİRDİLER: Saatlik USD=13.0, Kur=40.0")
        print(f"    ÇIKTILAR: Aylık TL Maliyet={tl}")

        self.assertAlmostEqual(tl, 108_160)


if __name__ == "__main__":
    unittest.main()