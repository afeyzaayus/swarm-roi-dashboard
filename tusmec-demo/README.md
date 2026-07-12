# Tusmec Hafta 3 — Web Arayüzü + ROI Modülü (İskelet)

Django tabanlı demo konsolu. Hafta 2 sürü simülasyon motorunu API olarak
sunar, tarayıcıda gerçek zamanlı görselleştirir ve ROI hesaplar.

## Kurulum (Ubuntu)

```bash
python3 -m venv venv
source venv/bin/activate
pip install django numpy
python manage.py migrate
python manage.py runserver
# tarayıcı: http://127.0.0.1:8000
```

Hafta 2 motorunu bağlamak için: `simulation/README.md`.
Motor yoksa aynı arayüzlü bir MOCK motor devreye girer (arayüzde rozet
"mock" gösterir) — web katmanı motorsuz da geliştirilebilir.

## Mimari

```
tusmec-demo/
├── simulation/          # Hafta 2 motoru (src/ buraya kopyalanır, DOKUNULMAZ)
├── simbridge/           # ros2_bridge'in web kardeşi
│   ├── engine_loader.py #   gerçek motoru bul / mock'a düş
│   ├── mock_engine.py   #   motorsuz geliştirme için taklit
│   └── session.py       #   arka plan thread'inde tick + JSON snapshot
├── api/                 # REST endpoint'leri
├── roi/                 # ROI hesap modülü + birim testleri + senaryolar
└── frontend/            # şablon + canvas JS (10 Hz polling)
```

## API

| Endpoint | Metot | Açıklama |
|---|---|---|
| `/api/sim/start` | POST | `{scenario?, area_m2, uav, ugv, amr}` — oturum başlatır |
| `/api/sim/state` | GET | Ajan konumları, engeller, istatistikler (JSON) |
| `/api/sim/stop` | POST | Oturumu durdurur |
| `/api/scenarios` | GET | Depo / Tarım / Savunma şablonları |
| `/api/roi` | POST | ROI hesaplar (aşağıda) |

### ROI girdileri
`current_monthly_cost`, `tusmec_monthly_license`, `setup_cost` (ops.),
`usd_rate`, `fleet_monthly_operating` (ops. — verilmezse çalışan
simülasyonun `cost_per_hour` verisinden türetilir: `hours_per_day` ×
`days_per_month` ile).

### ROI doğrulama tablosu (KPI: manuel doğrulama)
| Girdi | Elle hesap | Modül çıktısı |
|---|---|---|
| 450k mevcut, 120k lisans, 80k filo, 900k kurulum | tasarruf 250k/ay | 250.000 ✓ |
| aynı | geri ödeme 900k/250k = 3,6 ay | 3,6 ✓ |
| aynı | 5 yıl ROI (15M−0,9M)/12,9M = %109,3 | %109,3 ✓ |
| 300k mevcut, 90k lisans, 60k filo, 600k kurulum | tasarruf 150k/ay; geri ödeme 4,0 ay; ROI (9M−0,6M)/9,6M = %87,5 | 150.000 / 4,0 / %87,5 ✓ |

Testler: `python manage.py test roi` (5 test, hepsi elle hesaplı).

## Gerçek motor entegrasyonu (TAMAM)
Hafta 2 motoru `simulation/src` altında, hiçbir dosyası değiştirilmeden
çalışıyor. Parametreli senaryo kurucusu `simbridge/web_scenario.py`'de —
form girdilerinden (alan, filo, engel sayısı/yükseklik aralığı, seed)
Environment + ajanlar + SimulationEngine inşa eder. Kurulum: `pip install
django numpy` yeterli (pygame/matplotlib web için gerekmez).

## Engeller
- Sayı ve yükseklik aralığı formdan girilir; konum ve yarıçap rastgele
  atanır (her başlatmada farklı seed).
- Canvas'ta bir engele basılı tutup sürükleyerek canlı simülasyonda
  taşıyabilirsin (`POST /api/sim/obstacle {index, x, y}`). Ajanlar bir
  sonraki tick'te engeli yeni yerinde algılar; motor kodu değişmedi çünkü
  sense aşaması engelleri her tick yeniden okur.
- Sonsuz yükseklikli engel (no-fly kolonu) JSON'da `height: null,
  infinite: true` olarak taşınır ve canvas'ta ∞ etiketiyle çizilir.

## ÖNEMLİ — maliyet kalibrasyonu
Hafta 2 spec'lerindeki `cost_per_hour` değerleri (UAV 120, UGV 45, AMR 25
USD/saat) simülasyon amaçlı yer tutuculardır. "Filo maliyetini
simülasyondan türet" modu bu değerlerle çalıştığında (örn. 3+2+3 filo =
525 USD/saat ≈ 4,37M TL/ay) şablonlardaki temsili mevcut maliyetlerden
büyük çıkar ve tasarruf negatif görünür. Demo öncesi ya spec'lerdeki
cost_per_hour değerleri danışmandan alınacak gerçekçi rakamlarla
güncellenmeli ya da toplantıda filo maliyeti alanı elle girilmelidir.
Matematik doğrudur; kalibre edilmesi gereken veridir.

## Yapılacaklar (hafta planı)
- [ ] cost_per_hour / şablon maliyetlerini danışman verisiyle kalibre et
- [ ] Mobil ince ayar, Chart.js'i yerelleştir (çevrimdışı demo)
- [ ] PDF export (WeasyPrint), Tusmec logo, demo video

## Danışmana sorulacaklar
- Kurulum (capex) maliyeti var mı, yoksa saf SaaS mı? (geri ödeme formülünü etkiler)
- Segment bazlı gerçek işçilik/yakıt/bakım kalemleri (Hafta 1 raporu §9'daki öneri)
