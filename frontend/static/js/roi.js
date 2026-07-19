/* ROI sayfası — dört zorunlu girdi grubu + dört zorunlu çıktı + grafik + PDF.
   İki eğrinin kesiştiği nokta geri ödeme anıdır; grafik bunu görünür kılar. */
let roiChart = null;
let lastResult = null;   // PDF için son hesap saklanır
let SCENARIO_DEFAULTS = {};

const TL = (v) =>
  v.toLocaleString("tr-TR", { maximumFractionDigits: 0 }) + " TL";
const USD = (v) =>
  "$" + v.toLocaleString("en-US", { maximumFractionDigits: 0 });

const TASK_LABELS = {
  depo_lojistigi: "Depo Lojistiği",
  tarim: "Tarım",
  guvenlik_devriyesi: "Güvenlik / Savunma Devriyesi",
};

function num(id) {
  const raw = document.getElementById(id).value;
  return raw === "" ? null : +raw;
}
function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}

/* ------------------------- ön-doldurma ------------------------- */
async function init() {
  const res = await fetch("/api/scenarios");
  SCENARIO_DEFAULTS = (await res.json()).scenarios;

  const sel = document.getElementById("task");
  sel.addEventListener("change", () => {
    const sc = SCENARIO_DEFAULTS[sel.value];
    if (!sc) return;
    document.getElementById("area").value = sc.area_m2;
    for (const t of ["uav", "ugv", "amr"])
      document.getElementById(t).value = sc.fleet[t];
    document.getElementById("roi-current").value = sc.current_monthly_cost;
    document.getElementById("roi-license").value = sc.tusmec_monthly_license;
    document.getElementById("roi-setup").value = sc.setup_cost;
  });

  // Simülasyon sayfasından gelen sorgu parametreleri şablonu ezer
  const q = new URLSearchParams(location.search);
  if (q.get("task")) {
    sel.value = q.get("task");
    sel.dispatchEvent(new Event("change"));
    for (const [param, id] of [["area", "area"], ["uav", "uav"], ["ugv", "ugv"], ["amr", "amr"]])
      if (q.get(param) !== null) document.getElementById(id).value = q.get(param);
  } else {
    sel.dispatchEvent(new Event("change"));
  }
}

/* --------------------------- hesap --------------------------- */
async function calcRoi() {
  const body = {
    task_type: document.getElementById("task").value,
    area_m2: num("area"),
    uav: num("uav") ?? 0,
    ugv: num("ugv") ?? 0,
    amr: num("amr") ?? 0,
    current_monthly_cost: num("roi-current"),
    tusmec_monthly_license: num("roi-license"),
    setup_cost: num("roi-setup") ?? 0,
    usd_rate: num("roi-rate") ?? 1,
  };
  const uavCost = num("cost-uav") ?? 0;
  const ugvCost = num("cost-ugv") ?? 0;
  const amrCost = num("cost-amr") ?? 0;

  const uavCount = body.uav;
  const ugvCount = body.ugv;
  const amrCount = body.amr;

  body.fleet_monthly_operating = (uavCount * uavCost) + (ugvCount * ugvCost) + (amrCount * amrCost);

  const note = document.getElementById("roi-note");
  const res = await fetch("/api/roi", { method: "POST", body: JSON.stringify(body) });
  const data = await res.json();
  if (!data.ok) { note.textContent = "Hata: " + data.error; return; }

  lastResult = { request: body, response: data };
  document.getElementById("roi-pdf").disabled = false;

  const o = data.outputs;
  note.textContent = "";

  document.getElementById("roi-results").hidden = false;
  document.getElementById("roi-empty").hidden = true;

  const mEl = document.getElementById("r-monthly");
  mEl.textContent = TL(o.monthly_saving_tl);
  mEl.classList.toggle("neg", o.monthly_saving_tl < 0);
  document.getElementById("r-monthly-usd").textContent = USD(o.monthly_saving_usd) + "/ay";
  document.getElementById("r-annual").textContent = TL(o.annual_saving_tl);
  document.getElementById("r-annual-usd").textContent = USD(o.annual_saving_usd) + "/yıl";
  document.getElementById("r-payback").textContent =
    o.payback_months === null ? "tasarruf yok"
    : o.payback_months === 0 ? "ilk aydan itibaren"
    : o.payback_months + " ay";
  document.getElementById("r-roi").textContent = "%" + o.five_year_roi_pct;

  drawChart(o);
}

/* --------------------------- grafik --------------------------- */
function drawChart(o) {
  const labels = o.cumulative_current.map((_, i) => i);
  const ctx = document.getElementById("roi-chart");
  if (roiChart) roiChart.destroy();
  const ink = cssVar("--ink"), dim = cssVar("--ink-dim"),
        grid = cssVar("--grid"), teal = cssVar("--teal");
  roiChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        { label: "Mevcut durum", data: o.cumulative_current,
          borderColor: dim, backgroundColor: "transparent", pointRadius: 0, borderWidth: 2 },
        { label: "Tusmec çözümü", data: o.cumulative_tusmec,
          borderColor: teal, backgroundColor: "transparent", pointRadius: 0, borderWidth: 2 },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: ink } },
        tooltip: { callbacks: { label: (c) => c.dataset.label + ": " + TL(c.parsed.y) } },
      },
      scales: {
        x: { title: { display: true, text: "Ay", color: dim },
             ticks: { color: dim, maxTicksLimit: 13 }, grid: { color: grid } },
        y: { title: { display: true, text: "Kümülatif maliyet (TL)", color: dim },
             ticks: { color: dim, callback: (v) => {
               if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
               if (v >= 1e3) return (v / 1e3).toFixed(1) + "K";
               return v;
             } }, grid: { color: grid } },
      },
    },
  });
}
// Tema değişince grafiği yeni renklerle yeniden çiz
window.addEventListener("themechange", () => {
  if (lastResult) drawChart(lastResult.response.outputs);
});

/* ----------------------------- PDF ----------------------------- */
async function downloadPdf() {
  if (!lastResult) return;
  const btn = document.getElementById("roi-pdf");
  btn.disabled = true; btn.textContent = "PDF hazırlanıyor…";
  try {
    const req = lastResult.request, resp = lastResult.response;
    const fleetDesc = `${req.uav} UAV · ${req.ugv} UGV · ${req.amr} AMR`;
    const payload = {
      task_label: TASK_LABELS[req.task_type] || req.task_type,
      area_m2: req.area_m2,
      fleet_desc: fleetDesc,
      fleet_source: req.fleet_monthly_operating !== undefined ? "" : ` (${resp.fleet_source})`,
      inputs: resp.inputs,
      outputs: resp.outputs,
      chart_png: roiChart ? roiChart.toBase64Image() : "",
    };
    const res = await fetch("/api/roi/pdf", { method: "POST", body: JSON.stringify(payload) });
    if (!res.ok) throw new Error("PDF üretilemedi");
    const blob = await res.blob();
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "tusmec-roi-raporu.pdf";
    a.click();
    URL.revokeObjectURL(a.href);
  } catch (err) {
    document.getElementById("roi-note").textContent = "Hata: " + err.message;
  } finally {
    btn.disabled = false; btn.textContent = "ROI raporunu PDF indir";
  }
}

document.getElementById("roi-calc").addEventListener("click", calcRoi);
document.getElementById("roi-pdf").addEventListener("click", downloadPdf);
init();
