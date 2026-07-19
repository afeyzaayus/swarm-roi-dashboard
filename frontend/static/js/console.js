/* Sürü Demo Konsolu — /api/sim/state'i 10 Hz poll edip canvas'a çizer.
   Pygame görselleştiricideki dil korunur: tip renkleri, HUD, iz (trail).
   Engeller pointer ile sürüklenip canlı simülasyonda taşınabilir. */
const canvas = document.getElementById("field");
const ctx = canvas.getContext("2d");
const engineBadge = document.getElementById("engine");
const statbar = document.getElementById("statbar");

/* Tema değişince canvas renkleri de değişsin diye CSS değişkenlerini oku */
function cssVar(name) {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
window.addEventListener("themechange", () => { if (lastSnap) draw(lastSnap); });

const COLORS = { uav: "#4da3ff", ugv: "#57d98a", amr: "#ffb84d" };
const trails = new Map();          // agent_id -> son N konum
let world = { width: 100, height: 100 };
let lastSnap = null;
let pollTimer = null;

/* --- koordinat dönüşümü: kare dünyayı orana sadık (letterbox) yerleştir --- */
function scale() {
  return Math.min(canvas.width / world.width, canvas.height / world.height);
}
function offsets(s) {
  return [ (canvas.width - world.width * s) / 2,
           (canvas.height - world.height * s) / 2 ];
}
function toPx(x, y) {
  const s = scale(), [ox, oy] = offsets(s);
  return [ ox + x * s, canvas.height - oy - y * s ];
}
function toWorld(px, py) {
  const s = scale(), [ox, oy] = offsets(s);
  return [ (px - ox) / s, (canvas.height - oy - py) / s ];
}

/* ------------------------------- çizim ------------------------------- */
function draw(snap) {
  lastSnap = snap;
  world = snap.world;
  const s = scale(), [ox, oy] = offsets(s);
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // dünya çerçevesi + ızgara
  ctx.strokeStyle = cssVar("--grid"); ctx.lineWidth = 1;
  for (let i = 0; i <= 10; i++) {
    const wx = (world.width / 10) * i;
    const [gx] = toPx(wx, 0);
    ctx.beginPath(); ctx.moveTo(gx, oy); ctx.lineTo(gx, canvas.height - oy); ctx.stroke();
    const [, gy] = toPx(0, (world.height / 10) * i);
    ctx.beginPath(); ctx.moveTo(ox, gy); ctx.lineTo(canvas.width - ox, gy); ctx.stroke();
  }

  // engeller (silindir kuşbakışı) + yükseklik etiketi
  for (const ob of snap.obstacles) {
    const pos = drag.index === ob.index && drag.pos ? drag.pos : [ob.x, ob.y];
    const [x, y] = toPx(pos[0], pos[1]);
    const r = ob.radius * s;
    ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = drag.index === ob.index ? cssVar("--ob-fill-drag") : cssVar("--ob-fill");
    ctx.fill();
    ctx.strokeStyle = drag.index === ob.index ? cssVar("--teal") : cssVar("--ob");
    ctx.lineWidth = drag.index === ob.index ? 2 : 1; ctx.stroke();
    ctx.fillStyle = cssVar("--canvas-label");
    ctx.font = "10px monospace"; ctx.textAlign = "center";
    ctx.fillText(ob.infinite ? "∞" : `h: ${ob.height}m`, x, y - 4);
    ctx.fillText(`w: ${(ob.radius * 2).toFixed(1)}m`, x, y + 8);
    ctx.textAlign = "start";
  }

  // izler ve ajanlar
  for (const a of snap.agents) {
    const trail = trails.get(a.id) || [];
    trail.push([a.x, a.y]);
    if (trail.length > 120) trail.shift();
    trails.set(a.id, trail);

    const color = COLORS[a.type] || "#e8eef7";
    ctx.strokeStyle = color; ctx.globalAlpha = 0.35; ctx.lineWidth = 1.5;
    ctx.beginPath();
    trail.forEach(([tx, ty], i) => {
      const [px, py] = toPx(tx, ty);
      i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
    });
    ctx.stroke(); ctx.globalAlpha = 1;

    if (a.goal && !a.reached) {
      const [gx, gy] = toPx(a.goal[0], a.goal[1]);
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.globalAlpha = 0.6;
      ctx.beginPath();
      ctx.moveTo(gx - 4, gy - 4);
      ctx.lineTo(gx + 4, gy + 4);
      ctx.moveTo(gx + 4, gy - 4);
      ctx.lineTo(gx - 4, gy + 4);
      ctx.stroke();
      ctx.globalAlpha = 1;
    }

    const [x, y] = toPx(a.x, a.y);
    const emojis = { uav: "🚁", ugv: "🚙", amr: "🤖" };
    const emoji = emojis[a.type] || "🔹";
    ctx.font = "14px Arial";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(emoji, x, y);
    ctx.textAlign = "start";
    ctx.textBaseline = "alphabetic";
    
    if (a.z > 0.5) {
      ctx.fillStyle = cssVar("--canvas-label"); ctx.font = "10px monospace";
      ctx.fillText(`+${Math.round(a.z)}m`, x + 10, y - 8);
    }
  }


  const st = snap.stats;
  if (statbar) statbar.innerHTML =
    `t = <b>${st.sim_time}s</b> · hedefe ulaşan <b>${st.goals_reached}/${st.total_agents}</b>` +
    ` · toplam mesafe <b>${st.total_distance} m</b> · işletme maliyeti <b>$${st.total_cost_usd}</b>`;
  engineBadge.textContent = snap.engine;
  syncStopButton(!!snap.running);
  engineBadge.className = snap.engine;
}

/* -------------------- engel sürükle-bırak (pointer) -------------------- */
const drag = { index: -1, pos: null, lastSent: 0 };

function canvasPoint(e) {
  const rect = canvas.getBoundingClientRect();
  return [ (e.clientX - rect.left) * (canvas.width / rect.width),
           (e.clientY - rect.top) * (canvas.height / rect.height) ];
}

function hitObstacle(px, py) {
  if (!lastSnap) return -1;
  const s = scale();
  for (const ob of lastSnap.obstacles) {
    const [x, y] = toPx(ob.x, ob.y);
    if (Math.hypot(px - x, py - y) <= ob.radius * s + 6) return ob.index;
  }
  return -1;
}

async function sendObstacle(index, wx, wy) {
  await fetch("/api/sim/obstacle", {
    method: "POST",
    body: JSON.stringify({ index, x: wx, y: wy }),
  });
}

canvas.addEventListener("pointerdown", (e) => {
  const [px, py] = canvasPoint(e);
  const idx = hitObstacle(px, py);
  if (idx < 0) return;
  drag.index = idx;
  drag.pos = toWorld(px, py);
  canvas.setPointerCapture(e.pointerId);
  canvas.style.cursor = "grabbing";
});

canvas.addEventListener("pointermove", (e) => {
  const [px, py] = canvasPoint(e);
  if (drag.index < 0) {
    canvas.style.cursor = hitObstacle(px, py) >= 0 ? "grab" : "default";
    return;
  }
  drag.pos = toWorld(px, py);
  const now = performance.now();          // ağı boğmamak için ~12 Hz gönder
  if (now - drag.lastSent > 80) {
    drag.lastSent = now;
    sendObstacle(drag.index, drag.pos[0], drag.pos[1]);
  }
});

canvas.addEventListener("pointerup", async (e) => {
  if (drag.index < 0) return;
  const [px, py] = canvasPoint(e);
  const [wx, wy] = toWorld(px, py);
  await sendObstacle(drag.index, wx, wy);  // son konumu kesinleştir
  drag.index = -1; drag.pos = null;
  canvas.style.cursor = "default";
});

/* ------------------------------ kontrol ------------------------------ */
async function poll() {
  try {
    const res = await fetch("/api/sim/state");
    if (!res.ok) return;
    draw(await res.json());
  } catch (_) { /* sonraki turda dener */ }
}

/* Görev tipi (= senaryo şablonu) değişince alan + filo varsayılanlarını doldur */
let SCENARIO_DEFAULTS = {};
async function loadScenarios() {
  const res = await fetch("/api/scenarios");
  SCENARIO_DEFAULTS = (await res.json()).scenarios;
  const sel = document.getElementById("task");
  sel.addEventListener("change", () => {
    const sc = SCENARIO_DEFAULTS[sel.value];
    if (!sc) return;
    document.getElementById("area").value = sc.area_m2;
    for (const t of ["uav", "ugv", "amr"])
      document.getElementById(t).value = sc.fleet[t];
  });
  sel.dispatchEvent(new Event("change"));  // açılışta seçili görev tipiyle doldur
}

document.getElementById("start").addEventListener("click", async () => {
  trails.clear();
  const body = {
    task_type: document.getElementById("task").value,
    area_m2: +document.getElementById("area").value,
    uav: +document.getElementById("uav").value,
    ugv: +document.getElementById("ugv").value,
    amr: +document.getElementById("amr").value,
    n_obstacles: +document.getElementById("obs-n").value,
    obstacle_h_min: +document.getElementById("obs-hmin").value,
    obstacle_h_max: +document.getElementById("obs-hmax").value,
    seed: Math.floor(Math.random() * 1e6),   // her başlatmada farklı rastgele yerleşim
  };
  await fetch("/api/sim/start", { method: "POST", body: JSON.stringify(body) });
  if (!pollTimer) pollTimer = setInterval(poll, 100); // 10 Hz
});

/* Durdur ⇄ Devam et: buton etiketi snapshot'taki `running` durumundan
   türetilir; böylece başlat/durdur/devam ve oturumun kendi kendine bitmesi
   (süre sınırı/hata) hepsi otomatik senkron kalır. */
const stopBtn = document.getElementById("stop");
let simRunning = false;

function syncStopButton(running) {
  simRunning = running;
  stopBtn.textContent = running ? "Durdur" : "Devam et";
}

stopBtn.addEventListener("click", async () => {
  const url = simRunning ? "/api/sim/stop" : "/api/sim/resume";
  await fetch(url, { method: "POST" });
  syncStopButton(!simRunning);   // iyimser güncelle; poll zaten doğrular
});

document.getElementById("goto-roi").addEventListener("click", () => {
  const q = new URLSearchParams({
    task: document.getElementById("task").value,
    area: document.getElementById("area").value,
    uav: document.getElementById("uav").value,
    ugv: document.getElementById("ugv").value,
    amr: document.getElementById("amr").value,
  });
  window.open("/roi?" + q.toString(), "_blank");
});

loadScenarios();
