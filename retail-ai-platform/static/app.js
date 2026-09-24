const CUR = document.body.dataset.currency || "₹";
// Indian-style short numbers: K (thousand), L (lakh), Cr (crore)
const short = (n) => {
  const a = Math.abs(n);
  const f = (v, u) => `${+v.toFixed(v >= 100 ? 0 : 1)}${u}`;
  if (a >= 1e7) return f(n / 1e7, "Cr");
  if (a >= 1e5) return f(n / 1e5, "L");
  if (a >= 1e3) return f(n / 1e3, "K");
  return String(Math.round(n));
};
const full = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const money = (n) => `${CUR}${short(n)}`;
const moneyFull = (n) => `${CUR}${full.format(n)}`;
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const $ = (sel) => document.querySelector(sel);

async function api(path, opts) {
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(`${path} returned ${res.status}`);
  return res.json();
}

/* ---------- Forecast ---------- */
let chart;
async function loadForecast(days = 14) {
  const d = await api(`/api/forecast?days=${days}`);
  const labels = [...d.history.map((r) => r.date), ...d.forecast.map((r) => r.date)];
  const nH = d.history.length, nF = d.forecast.length;
  const pad = (arr, before) => [...Array(before).fill(null), ...arr];

  const lastHist = d.history[nH - 1].revenue;
  const histLine = [...d.history.map((r) => r.revenue), ...Array(nF).fill(null)];
  const fcLine = pad([lastHist, ...d.forecast.map((r) => r.revenue)], nH - 1).slice(0, nH + nF);
  const lower = pad([lastHist, ...d.forecast.map((r) => r.lower)], nH - 1).slice(0, nH + nF);
  const upper = pad([lastHist, ...d.forecast.map((r) => r.upper)], nH - 1).slice(0, nH + nF);

  const recent = d.history.slice(-days).reduce((a, r) => a + r.revenue, 0);
  const total = d.metrics.total_forecast;
  const change = recent ? ((total / recent - 1) * 100) : 0;
  const dir = change >= 0 ? "above" : "below";
  $("#forecast-headline").innerHTML =
    `Expect <b>${money(total)}</b> over the next ${days} days, ${Math.abs(change).toFixed(0)}% ${dir} the last ${days}.`;
  $("#forecast-note").textContent =
    `Shaded band shows the likely range. On the last 28 days held back for testing, daily forecasts were off by about ${d.metrics.holdout_mape_pct}% on average.`;

  const data = {
    labels,
    datasets: [
      { label: "Actual", data: histLine, borderColor: "#14202b", borderWidth: 2, pointRadius: 0, tension: 0 },
      { label: "Upper range", data: upper, borderColor: "transparent", backgroundColor: "rgba(14,124,123,0.14)", pointRadius: 0, fill: "+1", tension: 0 },
      { label: "Lower range", data: lower, borderColor: "transparent", pointRadius: 0, fill: false, tension: 0 },
      { label: "Forecast", data: fcLine, borderColor: "#0e7c7b", borderWidth: 2.5, borderDash: [6, 4], pointRadius: 0, tension: 0 },
    ],
  };
  const options = {
    responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
    plugins: {
      legend: { labels: { filter: (i) => !i.text.includes("range"), usePointStyle: true, boxWidth: 8 } },
      tooltip: {
        filter: (i) => !i.dataset.label.includes("range"),
        callbacks: { label: (c) => `${c.dataset.label}: ${moneyFull(c.parsed.y)}` },
      },
    },
    scales: {
      x: { ticks: { maxTicksLimit: 8, callback(v) { return this.getLabelForValue(v).slice(5); } }, grid: { display: false } },
      y: { ticks: { callback: (v) => money(v) }, grid: { color: "#edf0f3" }, beginAtZero: true },
    },
  };
  if (chart) { chart.data = data; chart.update(); } else { chart = new Chart($("#forecastChart"), { type: "line", data, options }); }
}

/* ---------- KPIs ---------- */
async function loadSummary() {
  const s = await api("/api/summary");
  const g = s.growth_pct;
  const growth = g === null ? "" : `<div class="d ${g >= 0 ? "up" : "down"}">${g >= 0 ? "Up" : "Down"} ${Math.abs(g)}% on the previous 30 days</div>`;
  const alert = s.stock_alerts
    ? `<div class="d down">${s.stock_alerts} product${s.stock_alerts > 1 ? "s" : ""} need action</div>` : `<div class="d up">All stocked</div>`;
  $("#kpis").innerHTML = `
    <div class="kpi"><div class="v">${money(s.last30_revenue)}</div><div class="l">Revenue, last 30 days</div>${growth}</div>
    <div class="kpi"><div class="v">${money(s.revenue)}</div><div class="l">Revenue, past year</div></div>
    <div class="kpi"><div class="v">${full.format(s.orders)}</div><div class="l">Orders</div></div>
    <div class="kpi"><div class="v">${full.format(s.customers)}</div><div class="l">Customers</div></div>
    <div class="kpi"><div class="v">${moneyFull(s.avg_order_value)}</div><div class="l">Average order</div></div>
    <div class="kpi"><div class="v">${s.stock_alerts}</div><div class="l">Stock alerts</div>${alert}</div>`;
}

/* ---------- Inventory ---------- */
async function loadInventory() {
  const rows = (await api("/api/inventory")).filter((r) => r.status !== "healthy").slice(0, 8);
  const body = $("#stockTable tbody");
  if (!rows.length) {
    body.innerHTML = `<tr><td colspan="5" class="empty">Nothing is at risk right now.</td></tr>`;
    return;
  }
  body.innerHTML = rows.map((r) => `
    <tr><td>${esc(r.name)}<span class="pill ${r.status}">${r.status === "critical" ? "Will run out" : "Running low"}</span></td>
    <td class="num">${r.stock}</td><td class="num">${r.daily_demand}</td>
    <td class="num">${r.days_of_cover}</td><td class="num"><b>${r.suggested_order_qty}</b></td></tr>`).join("");
}

/* ---------- Segments ---------- */
async function loadSegments() {
  const { segments } = await api("/api/segments");
  const max = Math.max(...segments.map((s) => s.customers));
  $("#segments").innerHTML = segments.map((s) => `
    <div class="segrow">
      <div class="segtop"><span>${esc(s.segment)}</span><span>${s.customers} customers</span></div>
      <div class="bar"><i style="width:${(s.customers / max) * 100}%"></i></div>
      <div class="segmeta">Avg spend ${moneyFull(s.avg_spend)}, last bought ${Math.round(s.avg_recency_days)} days ago.</div>
      <div class="segmeta">${esc(s.recommended_action)}</div>
    </div>`).join("");
}

/* ---------- Recommendations ---------- */
async function loadProducts() {
  const products = await api("/api/products");
  $("#productSelect").innerHTML = products.map((p) => `<option value="${p.id}">${esc(p.name)} (${esc(p.category)})</option>`).join("");
  $("#productSelect").addEventListener("change", (e) => loadRecs(e.target.value));
  await loadRecs(products[0].id);
}
async function loadRecs(id) {
  const recs = await api(`/api/recommendations/product/${id}?n=5`);
  $("#recList").innerHTML = recs.length
    ? recs.map((r) => `<li><span>${esc(r.name)}<span class="cat">${esc(r.category)}, ${moneyFull(r.price)}</span></span><span class="match">${Math.round(r.score * 100)}% match</span></li>`).join("")
    : `<li class="empty">No purchase history for this product yet.</li>`;
}

/* ---------- Sentiment ---------- */
async function loadSentiment() {
  const rows = (await api("/api/sentiment")).slice(0, 5);
  $("#sentList").innerHTML = rows.map((r) => `
    <div class="sentrow">
      <div class="top2"><span>${esc(r.name)}</span><span>${r.avg_rating} stars, ${r.reviews} reviews</span></div>
      <div class="split" title="${r.positive_pct}% positive, ${r.negative_pct}% negative">
        <span class="p" style="width:${r.positive_pct}%"></span><span class="n" style="width:${r.negative_pct}%"></span>
      </div>
    </div>`).join("");
}
$("#analyzeForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const text = $("#reviewText").value.trim();
  const out = $("#analyzeResult");
  if (!text) { out.textContent = "Type a review first."; return; }
  try {
    const r = await api("/api/sentiment/analyze", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) });
    out.textContent = `This reads as ${r.label} (score ${r.score}).`;
  } catch { out.textContent = "Could not check this review. Try again."; }
});

/* ---------- Boot ---------- */
document.querySelectorAll(".seg button").forEach((b) =>
  b.addEventListener("click", () => {
    document.querySelectorAll(".seg button").forEach((x) => x.classList.remove("on"));
    b.classList.add("on");
    loadForecast(+b.dataset.days);
  }));

Promise.all([loadForecast(14), loadSummary(), loadInventory(), loadSegments(), loadProducts(), loadSentiment()])
  .then(() => { $("#status").textContent = "Data up to date"; })
  .catch((err) => { console.error(err); $("#status").textContent = "Some data failed to load. Check the server log."; $("#status").classList.add("err"); });
