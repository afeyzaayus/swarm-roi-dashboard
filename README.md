# Tusmec Web Arayüzü + ROI Modülü (İskelet)

Django tabanlı demo konsolu. Hafta 2 sürü simülasyon motorunu API olarak
sunar, tarayıcıda gerçek zamanlı görselleştirir ve ROI hesaplar.

## Kurulum (Ubuntu)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-web.txt
python manage.py migrate
python manage.py runserver
# tarayıcı: http://127.0.0.1:8000
```

## Mimari

```
swarm-roi-dashboard/
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
-r requirements-web.txt` yeterli (pygame/matplotlib web için gerekmez).

## Sayfalar
- `/` — Görev parametreleri + tam sayfa simülasyon konsolu. Görev tipi
  seçimi alan/filo varsayılanlarını doldurur (senaryo şablonu kaldırıldı;
  şablon = görev tipi). "ROI Hesaplama →" butonu form değerlerini sorgu
  parametresiyle taşıyarak `/roi`'yi yeni sekmede açar.
- `/roi` — Bağımsız ROI sayfası: dört zorunlu girdi grubu, dört zorunlu
  çıktı, Chart.js karşılaştırma grafiği ve PDF raporu indirme
  (`POST /api/roi/pdf`, ReportLab + DejaVu, bonus +15). Filo işletme
  maliyeti girilmezse filo adetleri × spec cost_per_hour'dan türetilir —
  canlı simülasyon oturumu gerektirmez.
- Dark/light mod: sağ üstteki düğme, tercih localStorage'da; canvas ve
  grafik renkleri CSS değişkenlerinden okunur, tema değişince yeniden çizilir.

## Engeller
- Sayı ve yükseklik aralığı formdan girilir; konum ve yarıçap rastgele
  atanır (her başlatmada farklı seed).
- Canvas'ta bir engele basılı tutup sürükleyerek canlı simülasyonda
  taşıyabilirsin (`POST /api/sim/obstacle {index, x, y}`). Ajanlar bir
  sonraki tick'te engeli yeni yerinde algılar; motor kodu değişmedi çünkü
  sense aşaması engelleri her tick yeniden okur.
- Sonsuz yükseklikli engel (no-fly kolonu) JSON'da `height: null,
  infinite: true` olarak taşınır ve canvas'ta ∞ etiketiyle çizilir.
