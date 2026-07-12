/* ROI paneli — dört zorunlu çıktı + kümülatif karşılaştırma grafiği.
   İki eğrinin kesiştiği nokta geri ödeme anıdır; grafik bunu görünür kılar. */
let roiChart = null;

const TL = (v) =>
  v.toLocaleString("tr-TR", { maximumFractionDigits: 0 }) + " TL";
const USD = (v) =>
  "$" + v.toLocaleString("en-US", { maximumFractionDigits: 0 });

function num(id) {
  const raw = document.getElementById(id).value;
  return raw === "" ? null : +raw;
}

async function calcRoi() {
  const body = {
    task_type: document.getElementById("task").value,
    current_monthly_cost: num("roi-current"),
    tusmec_monthly_license: num("roi-license"),
    setup_cost: num("roi-setup") ?? 0,
    usd_rate: num("roi-rate") ?? 1,
    hours_per_day: 8,
  };
  const fleetManual = num("roi-fleet");
  if (fleetManual !== null) body.fleet_monthly_operating = fleetManual;

  const note = document.getElementById("roi-note");
  const res = await fetch("/api/roi", {
    method: "POST",
    body: JSON.stringify(body),
  });
  const data = await res.json();
  if (!data.ok) {
    note.textContent = "Hata: " + data.error;
    return;
  }
  const o = data.outputs;
  note.textContent =
    fleetManual === null
      ? `Filo işletme maliyeti simülasyondan türetildi: ${TL(data.inputs.fleet_monthly_operating)}/ay`
      : "";

  document.getElementById("roi-results").hidden = false;
  document.getElementById("roi-empty").hidden = true;

  const mEl = document.getElementById("r-monthly");
  mEl.textContent = TL(o.monthly_saving_tl);
  mEl.classList.toggle("neg", o.monthly_saving_tl < 0);
  document.getElementById("r-monthly-usd").textContent = USD(o.monthly_saving_usd) + "/ay";
  document.getElementById("r-annual").textContent = TL(o.annual_saving_tl);
  document.getElementById("r-annual-usd").textContent = USD(o.annual_saving_usd) + "/yıl";
  document.getElementById("r-payback").textContent =
    o.payback_months === null
      ? "tasarruf yok"
      : o.payback_months === 0
        ? "ilk aydan itibaren"
        : o.payback_months + " ay";
  document.getElementById("r-roi").textContent = "%" + o.five_year_roi_pct;

  drawChart(o);
}

function drawChart(o) {
  const labels = o.cumulative_current.map((_, i) => i);
  const ctx = document.getElementById("roi-chart");
  if (roiChart) roiChart.destroy();
  roiChart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [
        {
          label: "Mevcut durum (kümülatif maliyet)",
          data: o.cumulative_current,
          borderColor: "#8fa3bf",
          backgroundColor: "transparent",
          pointRadius: 0,
          borderWidth: 2,
        },
        {
          label: "Tusmec çözümü (kurulum + SaaS + filo)",
          data: o.cumulative_tusmec,
          borderColor: "#2bbfc4",
          backgroundColor: "rgba(43,191,196,.12)",
          fill: false,
          pointRadius: 0,
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      interaction: { mode: "index", intersect: false },
      plugins: {
        legend: { labels: { color: "#e8eef7" } },
        tooltip: {
          callbacks: { label: (c) => c.dataset.label + ": " + TL(c.parsed.y) },
        },
      },
      scales: {
        x: {
          title: { display: true, text: "Ay", color: "#8fa3bf" },
          ticks: { color: "#8fa3bf", maxTicksLimit: 13 },
          grid: { color: "rgba(58,76,104,.3)" },
        },
        y: {
          title: { display: true, text: "Kümülatif maliyet (TL)", color: "#8fa3bf" },
          ticks: {
            color: "#8fa3bf",
            callback: (v) => {
              if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
              if (v >= 1e3) return (v / 1e3).toFixed(1) + "K";
              return v;
            },
          },
          grid: { color: "rgba(58,76,104,.3)" },
        },
      },
    },
  });
}

document.getElementById("roi-calc").addEventListener("click", calcRoi);
