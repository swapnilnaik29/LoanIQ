/**
 * Cash-Flow Forecasting & Analytics Module for LoanIQ.
 * Easy-to-understand visualizations, horizon filtering (3, 7, 15, 30 days),
 * metric toggling, daily breakdown table, and zero dependency on CDN.
 */

import { api } from "./api.js";
import { getCurrentMerchantId, formatINR } from "./auth.js";

let forecastChart = null;
let currentForecastData = null;
let currentHorizon = 30;

export async function loadForecast(horizon = 30) {
  const merchantId = getCurrentMerchantId();
  if (!merchantId) return;

  currentHorizon = horizon;
  updateHorizonButtons(horizon);

  try {
    currentForecastData = await api.merchants.getForecast(merchantId, horizon);
    renderForecastSummary(currentForecastData);
    renderForecastChart(currentForecastData);
    renderForecastDailyTable(currentForecastData);
  } catch (err) {
    console.error("Failed to load forecast:", err);
  }
}

export async function handleRefreshForecast() {
  const merchantId = getCurrentMerchantId();
  if (!merchantId) return;

  const btn = document.getElementById("refresh-forecast-btn");
  if (btn) {
    btn.disabled = true;
    btn.textContent = "Refreshing...";
  }

  try {
    currentForecastData = await api.merchants.refreshForecast(merchantId);
    renderForecastSummary(currentForecastData);
    renderForecastChart(currentForecastData);
    renderForecastDailyTable(currentForecastData);
  } catch (err) {
    console.error("Forecast refresh error:", err);
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = "🔄 Refresh Forecast";
    }
  }
}

function updateHorizonButtons(horizon) {
  document.querySelectorAll(".horizon-btn").forEach(b => {
    const h = parseInt(b.getAttribute("data-horizon"));
    b.classList.toggle("active", h === horizon);
  });
}

function renderForecastSummary(fc) {
  const elInflow = document.getElementById("fc-sum-inflow");
  const elExpense = document.getElementById("fc-sum-expense");
  const elNet = document.getElementById("fc-sum-net");
  const elAvgDaily = document.getElementById("fc-avg-daily-net");
  const elTime = document.getElementById("fc-timestamp");

  if (elInflow) elInflow.textContent = formatINR(fc.summary_inflow);
  if (elExpense) elExpense.textContent = formatINR(fc.summary_expense);
  if (elNet) elNet.textContent = formatINR(fc.summary_net_cashflow);
  if (elAvgDaily) elAvgDaily.textContent = formatINR(fc.avg_daily_net_cashflow) + "/day";
  if (elTime && fc.generated_at) {
    try {
      elTime.textContent = new Date(fc.generated_at).toLocaleString();
    } catch (e) {
      elTime.textContent = fc.generated_at;
    }
  }

  // Clear or render liquidity alert banner if daily net is negative
  const alertBox = document.getElementById("fc-liquidity-alert");
  if (alertBox) {
    if (fc.avg_daily_net_cashflow < 0) {
      alertBox.innerHTML = `
        <div class="disclaimer-banner" style="background:#fef2f2; border-color:#fecaca; color:#991b1b;">
          ⚠️ <strong>Cashflow Notice:</strong> Forecast average daily expenses exceed sales inflow. Consider working capital support.
        </div>
      `;
      alertBox.style.display = "block";
    } else {
      alertBox.style.display = "none";
    }
  }
}

function renderForecastChart(fc) {
  const canvas = document.getElementById("forecastChart");
  if (!canvas) return;

  const rows = fc.rows || [];
  if (rows.length === 0) return;

  const labels = rows.map(r => {
    // Format YYYY-MM-DD to DD MMM (e.g. 01 Nov)
    const parts = r.forecast_date.split("-");
    if (parts.length === 3) {
      const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
      const mIdx = parseInt(parts[1], 10) - 1;
      return `${parts[2]} ${months[mIdx] || parts[1]}`;
    }
    return r.forecast_date;
  });

  const inflowData = rows.map(r => r.predicted_sales_inflow);
  const expenseData = rows.map(r => r.predicted_total_expense);
  const netData = rows.map(r => r.predicted_net_cashflow);

  // If Chart.js is loaded
  if (typeof Chart !== "undefined") {
    if (forecastChart) {
      try { forecastChart.destroy(); } catch (e) {}
    }

    try {
      const ctx = canvas.getContext("2d");
      forecastChart = new Chart(ctx, {
        type: "line",
        data: {
          labels,
          datasets: [
            {
              label: "Sales Inflow (Money In)",
              data: inflowData,
              borderColor: "#10b981",
              backgroundColor: "rgba(16, 185, 129, 0.12)",
              borderWidth: 2.5,
              pointRadius: rows.length <= 7 ? 4 : 2,
              tension: 0.3,
              fill: true,
            },
            {
              label: "Total Expenses (Money Out)",
              data: expenseData,
              borderColor: "#f59e0b",
              backgroundColor: "rgba(245, 158, 11, 0.08)",
              borderWidth: 2.5,
              pointRadius: rows.length <= 7 ? 4 : 2,
              tension: 0.3,
              fill: true,
            },
            {
              label: "Net Cash Surplus (Daily Profit)",
              data: netData,
              borderColor: "#00BAF2",
              backgroundColor: "rgba(0, 186, 242, 0.2)",
              borderWidth: 3,
              pointRadius: rows.length <= 7 ? 5 : 3,
              tension: 0.3,
              fill: false,
            }
          ]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          interaction: {
            mode: "index",
            intersect: false,
          },
          plugins: {
            legend: {
              position: "top",
              labels: {
                boxWidth: 14,
                font: { size: 13, weight: "bold" },
                padding: 16
              }
            },
            tooltip: {
              backgroundColor: "#002970",
              titleFont: { size: 14, weight: "bold" },
              bodyFont: { size: 13 },
              padding: 12,
              callbacks: {
                label: function(context) {
                  const label = context.dataset.label.split(" (")[0] || "";
                  const val = context.parsed.y !== null ? formatINR(context.parsed.y) : "₹0";
                  return ` ${label}: ${val}`;
                }
              }
            }
          },
          scales: {
            x: {
              grid: { display: false },
              ticks: { font: { size: 11 }, maxRotation: 45 }
            },
            y: {
              beginAtZero: false,
              grid: { color: "#f1f5f9" },
              title: { display: true, text: "Daily Amount (₹)", font: { weight: "bold" } },
              ticks: {
                callback: val => "₹" + Number(val).toLocaleString("en-IN")
              }
            }
          }
        }
      });
    } catch (chartErr) {
      console.warn("Chart.js failed to render, falling back to 2D canvas chart:", chartErr);
      drawCanvasFallback(canvas, labels, inflowData, expenseData, netData);
    }
  } else {
    // Pure Canvas High-Performance Fallback Renderer
    drawCanvasFallback(canvas, labels, inflowData, expenseData, netData);
  }
}

function drawCanvasFallback(canvas, labels, inflow, expense, net) {
  const ctx = canvas.getContext("2d");
  const w = canvas.width = canvas.parentElement.clientWidth || 800;
  const h = canvas.height = 360;

  ctx.clearRect(0, 0, w, h);
  const padL = 70, padR = 30, padT = 40, padB = 40;
  const plotW = w - padL - padR;
  const plotH = h - padT - padB;

  const allVals = [...inflow, ...expense, ...net];
  const minVal = Math.min(...allVals, 0);
  const maxVal = Math.max(...allVals) * 1.15 || 1000;

  const getY = v => padT + plotH - ((v - minVal) / (maxVal - minVal)) * plotH;
  const getX = i => padL + (i / Math.max(1, labels.length - 1)) * plotW;

  // Grid lines
  ctx.strokeStyle = "#e2e8f0";
  ctx.lineWidth = 1;
  for (let s = 0; s <= 4; s++) {
    const val = minVal + ((maxVal - minVal) * s) / 4;
    const y = getY(val);
    ctx.beginPath();
    ctx.moveTo(padL, y);
    ctx.lineTo(w - padR, y);
    ctx.stroke();

    ctx.fillStyle = "#64748b";
    ctx.font = "11px sans-serif";
    ctx.fillText("₹" + Math.round(val).toLocaleString("en-IN"), 10, y + 4);
  }

  // Draw lines
  const drawSeries = (data, color, width) => {
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.beginPath();
    data.forEach((val, i) => {
      const x = getX(i);
      const y = getY(val);
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();

    ctx.fillStyle = color;
    data.forEach((val, i) => {
      ctx.beginPath();
      ctx.arc(getX(i), getY(val), 3, 0, Math.PI * 2);
      ctx.fill();
    });
  };

  drawSeries(inflow, "#10b981", 2.5);
  drawSeries(expense, "#f59e0b", 2.5);
  drawSeries(net, "#00BAF2", 3);

  // X labels
  ctx.fillStyle = "#475569";
  ctx.font = "11px sans-serif";
  const step = Math.ceil(labels.length / 7);
  labels.forEach((lbl, i) => {
    if (i % step === 0 || i === labels.length - 1) {
      ctx.fillText(lbl, getX(i) - 15, h - 12);
    }
  });

  // Legend
  ctx.font = "bold 12px sans-serif";
  ctx.fillStyle = "#10b981"; ctx.fillText("■ Inflow", padL, 20);
  ctx.fillStyle = "#f59e0b"; ctx.fillText("■ Expense", padL + 90, 20);
  ctx.fillStyle = "#00BAF2"; ctx.fillText("■ Net Cashflow", padL + 185, 20);
}

function renderForecastDailyTable(fc) {
  const container = document.getElementById("forecast-daily-table-container");
  if (!container) return;

  const rows = fc.rows || [];
  if (rows.length === 0) {
    container.innerHTML = "";
    return;
  }

  container.innerHTML = `
    <div class="card" style="margin-top:1.5rem;">
      <div class="card-header">
        <span class="card-title">📅 Daily Forecast Breakdown (${rows.length} Days)</span>
        <span class="stat-subtext">Click any day to inspect exact values</span>
      </div>
      <div class="table-responsive" style="max-height:320px; overflow-y:auto;">
        <table class="data-table">
          <thead>
            <tr>
              <th>Day</th>
              <th>Date</th>
              <th>Sales Inflow (In)</th>
              <th>Total Expense (Out)</th>
              <th>Daily Net Flow (Surplus)</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            ${rows.map(r => {
              const isPositive = r.predicted_net_cashflow >= 0;
              return `
                <tr>
                  <td><strong>Day ${r.horizon_day}</strong></td>
                  <td>${r.forecast_date}</td>
                  <td style="color:#10b981; font-weight:600;">+${formatINR(r.predicted_sales_inflow)}</td>
                  <td style="color:#f59e0b; font-weight:600;">-${formatINR(r.predicted_total_expense)}</td>
                  <td style="color:${isPositive ? '#00BAF2' : '#ef4444'}; font-weight:700;">
                    ${isPositive ? '+' : ''}${formatINR(r.predicted_net_cashflow)}
                  </td>
                  <td>
                    <span class="badge ${isPositive ? 'badge-green' : 'badge-red'}">
                      ${isPositive ? 'Surplus' : 'Deficit'}
                    </span>
                  </td>
                </tr>
              `;
            }).join("")}
          </tbody>
        </table>
      </div>
    </div>
  `;
}
