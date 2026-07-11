# Heterojen Sürü Simülasyon Motoru

Python ile geliştirilmiş, heterojen çok-ajanlı sürü simülasyon motoru:
**UAV, UGV, AMR, USV, UUV ve Roket** olmak üzere altı ajan tipi.

![Simülasyon Penceresi](docs/screenshot.png)

*Pygame penceresi: ajanlar emoji olarak çizilir, sol üstte istatistik HUD'u,
sol altta emoji açıklamaları (legend). Hava araçlarının yanında irtifa
(20m, 35m), UUV'lerin yanında derinlik (−12m) etiketleri görünür.*

---

## 1. Kurulum

```bash
git clone <repo-url>
cd simulation
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Gereksinimler: Python ≥ 3.10, `numpy`, `pygame` (görselleştirme), `matplotlib`
(grafik çıktısı), `pytest` + `pytest-cov` (testler). ROS2 köprüsü için ayrıca
kurulu bir ROS2 dağıtımı (Humble/Jazzy) gerekir — bkz. Bölüm 7.

## 2. Çalıştırma

```bash
python main.py                        # varsayılan: TÜM ajan tipleri, PAPF (d=5)
python main.py --algo apf             # klasik APF ile çalıştır
python main.py --d=10                 # PAPF, sanal adım uzunluğu 10 m
python main.py --headless             # GUI olmadan çalıştır, istatistikleri yazdır
python main.py --headless --plot out.png  # yörünge grafiğini PNG olarak kaydet
python main.py --ticks 10000          # maksimum tick sayısını değiştir
```

### Koordinasyon algoritması seçimi

`--algo papf` (varsayılan) tahminli APF'i, `--algo apf` klasik APF'i kullanır.
`--d` yalnızca PAPF'in sanal adım uzunluğunu (metre) belirler; yazılmazsa
varsayılan **d = 5.0 m** kullanılır.

```bash
python main.py uav rocket --d=12      # filtreleme + PAPF adım uzunluğu birlikte
```

### Ajan tipi filtreleme

Pozisyonel argüman olarak tip adı verilirse **yalnızca o tipler** simüle edilir
ve görüntülenir. Hiçbir tip verilmezse tüm ajanlar çalışır (varsayılan).

```bash
python main.py uav                    # sadece UAV'ler
python main.py rocket                 # sadece sualtı roketleri
python main.py uav ugv                # sadece UAV + UGV
python main.py usv uuv rocket         # sadece deniz araçları
```

Geçerli tip adları: `uav`, `ugv`, `amr`, `usv`, `uuv`, `rocket`
(büyük/küçük harf duyarsız). Pencerenin sol altındaki legend yalnızca o an
simülasyonda bulunan tipleri listeler.

### Pencere işaretleri (legend)

Ajanlar pencerede emoji olarak gösterilir:

| Emoji | Ajan |
|---|---|
| ✈️ | UAV — hava aracı |
| 🚗 | UGV — kara aracı |
| 🤖 | AMR — iç mekân robotu |
| 🚤 | USV — su üstü aracı |
| 🤿 | UUV — sualtı aracı |
| 🚀 | Roket — yüksek irtifa |

Sistemde renkli emoji fontu yoksa (Noto Color Emoji, Segoe UI Emoji vb.)
görselleştirici otomatik olarak renkli geometrik şekillere düşer (mavi üçgen =
UAV, yeşil kare = UGV, ...) ve legend metni buna göre güncellenir. Linux'ta
emoji fontu için: `sudo apt install fonts-noto-color-emoji`

Kırmızı çarpılar hedefleri, gri diskler engelleri gösterir. `h=25m` engel
yüksekliğini, `z:-30..-8m` sualtı engelinin derinlik aralığını belirtir.
Pencereden `ESC` ile çıkılır.

### Testler

```bash
python -m pytest --cov --cov-report=term
```

Mevcut durum: **83 test, %98 satır coverage** (KPI eşiği: ≥%60).
Testler KPI'da istenen **HIZ** (max hız aşımı yok), **İVME** (ivme limiti),
**KONUM** (pozisyon entegrasyonu, düzlem/irtifa/derinlik kısıtları)
doğrulamalarını altı ajan tipi için de içerir.

## 3. Mimari

```text
simulation/
├── dae/                    # RViz için ajanların 3D modelleri (UAV, UGV vb.)
├── docs/                   # Dokümantasyon görselleri (ekran görüntüleri, grafikler)
├── src/
│   ├── agents.py           # BaseAgent (ABC) → UAV, UGV, AMR, USV, UUV, Rocket
│   ├── coordination.py     # APF + PAPF (tahminli) koordinasyon algoritmaları
│   ├── engine.py           # Sense → Think → Act tick döngüsü
│   ├── environment.py      # Dünya sınırları + derinlik bantlı silindirik engeller
│   ├── math_utils.py       # numpy vektör yardımcıları
│   ├── ros2_bridge.py      # [BONUS] ROS2 node sarmalayıcı (RViz yayını)
│   ├── scenario.py         # Demo senaryosu + ajan tipi filtreleme
│   └── visualizer.py       # pygame kuşbakışı görselleştirme (İngilizce arayüz)
├── tests/
│   ├── test_agents.py      # Ajan kinematiği (hız, ivme, konum) testleri
│   ├── test_coordination.py# APF algoritması testleri
│   ├── test_engine.py      # Tick mekanizması ve sistem entegrasyonu testleri
│   ├── test_math_utils.py  # Vektör yardımcı fonksiyonları testleri
│   ├── test_new_agents.py  # USV, UUV ve Roket için özel fizik testleri
│   └── test_papf.py        # Tahminli APF (PAPF) doğrulama testleri
├── main.py                 # CLI giriş noktası (tip filtreleme flag'leri)
├── pytest.ini              # pytest yapılandırması
└── requirements.txt        # Proje bağımlılıkları
```

### Sense → Think → Act döngüsü

Motorun kalbi `SimulationEngine.tick()` içindeki üç fazlı döngüdür:

1. **Algı (Sense):** Her ajan, sensör menzili içindeki komşularını ve
   *kendi irtifasını/derinliğini bloklayan* engelleri tarar.
2. **Karar (Think):** Koordinasyon stratejisi (APF) hedef, engel ve komşu
   bilgisinden `numpy` vektör işlemleriyle bir ivme vektörü hesaplar.
3. **Hareket (Act):** İvme entegre edilir, tip-özgü kinematik kısıtlar
   uygulanır ve konum güncellenir.

Önemli detay: bir tick içinde **önce tüm ajanlar algılar ve karar verir, sonra
hepsi birden hareket eder**. Böylece her karar aynı dünya anlık görüntüsüne
dayanır ve ajan sıralamasından kaynaklanan yanlılık oluşmaz.

### OOP hiyerarşisi

```
BaseAgent (ABC)
├── UAV               → 3B hareket, irtifa bandı [min, max], sürtünmesiz
│   └── Rocket        → en hızlı ajan; tavana yakın uçar (35 m), kanatçık
│                        kısıtlı geniş dönüşler (25°/s)
├── GroundAgent       → z=0 düzlemine sabit, zemin/gövde sürtünmesi
│   ├── UGV           → dönüş hızı kısıtı (araç direksiyonu, 90°/s)
│   ├── AMR           → omnidirectional ama yavaş (iç mekân robotu)
│   └── USV           → su yüzeyi, gövde sürüklemesi + dümen kısıtı (60°/s)
└── UnderwaterAgent   → negatif z, derinlik bandı, 3 eksende su direnci
    └── UUV           → yavaş sonar keşif denizaltısı (45°/s)
```

Alt sınıflar yalnızca `_constrain_velocity()` ve `_post_move()` kancalarını
override eder; sense/think/act akışı tamamen `BaseAgent`'ta yaşar (template
method deseni). Dönüş kısıtı mantığı `limit_turn()` fonksiyonunda ortaktır ve
UGV, USV ve roket tarafından paylaşılır.

## 4. Koordinasyon Algoritmaları: APF ve PAPF

### APF (klasik)

`ArtificialPotentialField` üç kuvvet bileşenini toplar:

| Bileşen | Formül | Amaç |
|---|---|---|
| Çekim | `k_att · (goal − pos)`, doygunluk yarıçapıyla sınırlı | hedefe yönelme |
| İtme | `k_rep · (1/d − 1/d₀) · 1/d²` | engel kaçınma |
| Ayrışma | itme ile aynı biçim, komşu ajanlara | sürü içi çarpışma önleme |

İki pratik iyileştirme eklendi:

* **Teğetsel bileşen (`k_tangent`):** Engel tam hedef doğrultusundayken çekim
  ve itme anti-paralel kalır ve ajan lokal minimuma saplanır. İtme kuvvetine
  hedef yönüne uyumlu bir teğet bileşen eklenerek ajan engelin *etrafından*
  yönlendirilir.
* **Çekim doygunluğu (`attraction_saturation`):** Uzak hedeflerde çekim
  sınırsız büyüyüp itmeyi ezmesin diye çekim kuvveti belirli mesafeden sonra
  sabitlenir.

### PAPF (tahminli / predictive)

Klasik APF bir engeli ancak etki yarıçapına (d₀ = 8 m) girdikten sonra
"hisseder" ve geç, sert düzeltmeler yapar. `PredictiveArtificialPotentialField`
buna **sanal (hayali) adım** ekler: ajan, mevcut hareket yönünde `d` metre
ilerideki hayali konumunu hesaplar ve itme/ayrışma alanını o noktada da
değerlendirir:

```
p_sanal = p + d · birim(v)         (duruyorsa hedef yönünde)
F = F_çekim(p) + F_itme(p) + w · F_itme(p_sanal) − sönümleme · v
```

Yol, `d` metre ileride *olacak olana* göre büküldüğü için ajan kaçınmaya
engele varmadan başlar. `--d` flag'i bu adım uzunluğunu belirler
(varsayılan 5.0 m).

![APF vs PAPF](docs/apf_vs_papf.png)

Kafa kafaya senaryoda ölçülen davranış (UGV, r=5 m engel):

| Algoritma | Min. engel mesafesi | Yol uzunluğu |
|---|---|---|
| APF (klasik) | 0.41 m | — (yüzeyi sıyırır) |
| PAPF d=2 | 2.23 m | 73.9 m |
| PAPF d=5 (varsayılan) | 2.22 m | 72.5 m |
| PAPF d=12 | 1.62 m | 71.7 m |

PAPF her `d` değerinde klasik APF'ten **3–5 kat daha fazla güvenlik payı**
bırakır. `d` büyüdükçe kaçınma daha erken başlar ve yol kısalır; geçiş
anındaki minimum mesafeyi ise ağırlıkla anlık (tahminsiz) terim belirlediği
için hafifçe azalır — yani `d`, erken tepki ↔ yol verimliliği dengesini
ayarlayan bir tasarım parametresidir. Bu davranışlar
`tests/test_papf.py` içinde doğrulanır.

## 5. Ajan Parametre Setleri

| Parametre | UAV | UGV | AMR | USV | UUV | Roket |
|---|---|---|---|---|---|---|
| Maks. hız (m/s) | 15.0 | 5.0 | 2.0 | 8.0 | 3.0 | 30.0 |
| Maks. ivme (m/s²) | 6.0 | 2.5 | 1.5 | 3.0 | 1.2 | 12.0 |
| Sensör menzili (m) | 40 | 20 | 12 | 30 | 15 | 35 |
| Görev kapasitesi (kg) | 2.5 | 80 | 30 | 200 | 50 | 10 |
| Maliyet ($/saat) | 120 | 45 | 25 | 60 | 90 | 300 |
| Sürtünme/direnç (1/s) | — | 0.6 | 0.8 | 0.5 | 0.9 | — |
| Maks. dönüş hızı (°/s) | ∞ | 90 | ∞ | 60 | 45 | 25 |

Parametreler `src/agents.py` içindeki `DEFAULT_SPECS` sözlüğünde tanımlıdır ve
`AgentSpec` dataclass'ı ile her ajan örneğine ayrı ayrı verilebilir.

### Engel modeli: derinlik bantları

Engeller `[base, base + height)` aralığında uzanan dikey silindirlerdir ve bir
ajanı yalnızca ajanın z koordinatı bu banttaysa etkiler:

* `h=10m` (base=0): 20 m'de uçan UAV hiç algılamaz, yer araçları dolaşır.
* `height=inf`: uçuşa yasak sütun — hava ve kara için de geçilemez.
* `z:-30..-8m` deniz tepesi (seamount): −12 m'de seyreden UUV'yi bloklar;
  UAV/UGV ve 35 m'de uçan roket hiç etkilenmez.
* Roket 35 m'de, haritadaki tüm sonlu engellerin üzerinde uçar — onu yalnızca
  sonsuz yükseklikteki uçuşa yasak sütun etkileyebilir.

## 6. KPI Karşılığı

| KPI | Durum |
|---|---|
| ≥3 ajan tipi simüle ediliyor mu? | ✅ 6 tip: UAV + UGV + AMR + USV + UUV + Roket (✈️🚗🤖🚤🤿🚀) |
| Koordinasyon algoritması | ✅ APF + PAPF (tahminli), ikisi de test edilmiş ve çalışır durumda |
| Tip-özgü parametre seti | ✅ hız, menzil, kapasite, maliyet/saat (`DEFAULT_SPECS`) |
| Birim test coverage ≥ %60 | ✅ %99 (70 test; hız/ivme/konum doğrulamaları dahil) |
| README.md | ✅ kurulum, çalıştırma, parametre açıklamaları |
| [BONUS] ROS2 node + RViz | ✅ `src/ros2_bridge.py` (aşağıda) |

## 7. [BONUS] ROS2 Node + RViz Görselleştirmesi

![RViz Penceresi](docs/rviz2.png)

`SimulationEngine` görselleştirmeden tamamen bağımsız olduğu için ROS2
sarmalayıcı yalnızca bir timer callback'inde `engine.tick()` çağırıp durumu
yayınlar. `main.py` ile **birebir aynı flag'leri** kabul eder: tip filtreleme,
`--algo {apf, papf}` ve `--d`. Algoritma motorun içinde (Strategy deseni)
yaşadığı için RViz görselleştirmesi APF ve PAPF için aynı topic'lerle,
ek bir yapılandırma gerekmeden çalışır.

```bash
source /opt/ros/humble/setup.bash          # veya jazzy
python -m src.ros2_bridge                  # tüm tipler, PAPF d=5 (varsayılan)
python -m src.ros2_bridge --algo apf       # klasik APF
python -m src.ros2_bridge --d=10           # PAPF, sanal adım 10 m
python -m src.ros2_bridge uav rocket --d=12  # filtreleme + PAPF birlikte
```

Seçilen algoritma başlangıçta node log'una yazılır
(`Coordination: PAPF (d=10.0 m)`), böylece hangi kipte yayın yapıldığı
`ros2 node` çıktısından doğrulanabilir.

Yayınlanan topic'ler:

| Topic | Mesaj tipi | İçerik |
|---|---|---|
| `/swarm/markers` | `visualization_msgs/MarkerArray` | ajanlar (tip-renkli primitifler) + engeller (silindir) |
| `/swarm/poses` | `geometry_msgs/PoseArray` | ham ajan konumları |

RViz kurulumu: **Fixed Frame** = `map`, ardından `/swarm/markers` topic'ine bir
**MarkerArray** display'i ekleyin. Ajan renkleri pygame görselleştiricisiyle
aynıdır; engeller yarı saydam gri silindirler olarak çizilir. `rclpy` kurulu
değilse modül açıklayıcı bir hata mesajıyla çıkar.

## 8. Gelecek Çalışma

* Ek koordinasyon stratejileri (Reynolds Flocking, GWO) — `CoordinationStrategy`
  arayüzü sayesinde motor koduna dokunmadan eklenebilir.

