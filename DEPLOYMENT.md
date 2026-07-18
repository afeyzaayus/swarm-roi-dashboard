# Deployment Talimatları — Tusmec Sürü Demo Platformu

Bu belge, projeyi sıfır bir makinede ayağa kaldırmak isteyen bir geliştirici
için adım adım kurulum talimatlarını içerir. Hedef ortam **Ubuntu 22.04+**
(24.04'te doğrulanmıştır); macOS/Windows notları en sonda verilmiştir.

---

## 1. Ön Koşullar

| Gereksinim | Sürüm | Kontrol komutu |
|---|---|---|
| Python | 3.10 veya üzeri | `python3 --version` |
| pip + venv | Python ile birlikte | `python3 -m pip --version` |
| Git (klonlama için) | herhangi | `git --version` |

Eksikse:

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv git
```

> Not: `pygame`, `matplotlib` ve ROS2 **web platformu için gerekli değildir**.
> Bunlar yalnızca Hafta 2 motorunun masaüstü görselleştiricisi (`main.py`)
> ve RViz köprüsü içindir.

## 2. Projeyi Edinme

```bash
git clone <repo-adresi> swarm-roi-dashboard
cd swarm-roi-dashboard
```

(Zip ile geldiyse: `unzip swarm-roi-dashboard.zip && cd swarm-roi-dashboard`)

## 3. Sanal Ortam ve Bağımlılıklar

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-web.txt
```

`requirements-web.txt` içeriği: Django, numpy, pillow, reportlab.

## 4. Veritabanı ve Sunucu

```bash
python manage.py migrate
python manage.py runserver
```

Tarayıcıda **http://127.0.0.1:8000** adresini aç.
Farklı porttan yayınlamak için: `python manage.py runserver 0.0.0.0:8080`
(aynı ağdaki başka cihazlardan — örn. mobil testte telefondan — erişim sağlar).

## 5. Kurulum Doğrulama Kontrol Listesi

| # | Kontrol | Beklenen |
|---|---|---|
| 1 | `http://127.0.0.1:8000/` açılıyor | Simülasyon konsolu görünür |
| 2 | "Simülasyonu başlat" → sol alttaki **Motor** rozeti | **real** (yeşil) |
| 3 | Canvas'ta ajanlar hareket ediyor | 🚁 🚙 🤖 emojileri hedefe ilerler |
| 4 | Bir engele basılı tutup sürükle | Engel taşınır, ajanlar kaçınır |
| 5 | "ROI Hesaplama →" butonu | `/roi` yeni sekmede açılır |
| 6 | ROI hesapla → "ROI raporunu PDF indir" | `tusmec-roi-raporu.pdf` iner |
| 7 | Birim testleri | `python manage.py test roi` → **OK (5 test)** |
| 8 | Motor testleri (opsiyonel) | `pip install pytest && cd simulation && pytest tests -q` |

## 6. Sorun Giderme

**Motor rozeti "mock" (turuncu) gösteriyor.**
Gerçek motor bulunamamış demektir. `simulation/src/` klasörünün proje kökünde
olduğundan emin ol; `engine.py`, `agents.py`, `environment.py` dosyaları
orada olmalı. Sunucuyu yeniden başlat.

**`ModuleNotFoundError: No module named 'numpy'`**
Sanal ortam aktif değil (`source .venv/bin/activate`) veya bağımlılıklar
kurulmamış (`pip install -r requirements-web.txt`).

**ROI grafiği görünmüyor.**
Chart.js CDN üzerinden yüklenir (`cdnjs.cloudflare.com`); internet bağlantısı
gerekir. Çevrimdışı demo için `chart.umd.min.js` dosyasını indirip
`frontend/static/js/` altına koy ve `roi.html`'deki script yolunu
`/static/js/chart.umd.min.js` olarak değiştir.

**PDF'te Türkçe karakterler bozuk.**
Rapor DejaVu Sans fontunu `/usr/share/fonts/truetype/dejavu/` altında arar.
Yoksa: `sudo apt install fonts-dejavu-core`. Bulunamazsa Helvetica'ya düşer
(ş/ğ/İ bozulur ama PDF üretimi çalışır).

**Port 8000 dolu.**
`python manage.py runserver 8001` ile farklı port kullan.

**Zaman aşımı / donan simülasyon.**
Oturum emniyet için 10 dakikada kendini durdurur
(`simbridge/session.py` → `MAX_SIM_SECONDS`). Yeniden "Simülasyonu başlat".

## 7. Üretim (Production) Notları — Opsiyonel

Demo `runserver` ile yapılır; kalıcı bir sunucuda yayınlanacaksa:

```bash
pip install gunicorn
export DJANGO_DEBUG=False        # settings.py'de DEBUG'ı bu değişkene bağla
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 1
```

Önemli: simülasyon oturumu **süreç içi** tutulduğundan `--workers 1`
kullanılmalıdır (çok işçili yapı için oturumun Redis benzeri paylaşımlı bir
katmana taşınması gerekir — bkz. README "Yapılacaklar").
`ALLOWED_HOSTS` ve `SECRET_KEY` değerlerini üretim için güncellemeyi unutma.

## 8. macOS / Windows Notları

- macOS: `brew install python3`; adımlar aynıdır. DejaVu fontu için PDF
  modülü `_FONT_DIRS` listesine `/Library/Fonts` eklenebilir.
- Windows: `py -m venv .venv` + `.venv\Scripts\activate`; kalan adımlar aynı.
  Font yolu olarak `C:\Windows\Fonts` altına DejaVuSans.ttf kopyalanabilir.

---

*Son güncelleme: 14 Temmuz 2026 · Hafta 4 teslimatı kapsamında hazırlanmıştır.*
