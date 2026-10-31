/**
 * LoanIQ Dashboard Module.
 */

import { api } from "./api.js";
import { getCurrentMerchantId, formatINR } from "./auth.js";
import { openLoanDetailModal } from "./loans.js";

export async function loadDashboard() {
  const merchantId = getCurrentMerchantId();
  if (!merchantId) return;

  try {
    // 1. Fetch Profile
    const profile = await api.merchants.getProfile(merchantId);
    renderProfileHeader(profile);

    // 2. Fetch Optimization (Active loans summary)
    const opt = await api.merchants.getOptimization(merchantId);
    renderDebtSummary(opt);

    // 3. Fetch Top Recommendations Preview
    const recs = await api.merchants.getRecommendations(merchantId, 100000, null, 365);
    renderTopRecommendations(recs);

    // 4. Fetch Forecast Preview
    const forecast = await api.merchants.getForecast(merchantId, 30);
    renderForecastPreview(forecast);
  } catch (err) {
    console.error("Dashboard load failed:", err);
  }
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}

function renderProfileHeader(p) {
  setText("merchant-name-display", p.business_name);
  setText("merchant-id-badge", p.merchant_id);
  setText("dash-city-tier", `${p.city} (${p.city_tier})`);
  setText("dash-type", (p.merchant_type || "").replace("_", " ").toUpperCase());
  setText("dash-sales", formatINR(p.monthly_sales_reference));
  setText("dash-profit", formatINR(p.monthly_profit_reference));
  setText("dash-score", p.credit_score);
}

function renderDebtSummary(opt) {
  setText("dash-active-count", opt.active_loans_count);
  setText("dash-debt-total", formatINR(opt.total_remaining_principal));
  setText("dash-daily-emi", formatINR(opt.total_current_daily_emi));
  setText("dash-repaid-total", formatINR(opt.total_repaid_principal));

  const alertContainer = document.getElementById("dash-warnings-container");
  if (alertContainer) {
    if (opt.warnings && opt.warnings.length > 0) {
      alertContainer.innerHTML = opt.warnings.map(w => `
        <div class="disclaimer-banner" style="background:#fef2f2; border-color:#fecaca; color:#991b1b; margin-bottom:0.75rem;">
          ⚠️ <strong>Cashflow Warning:</strong> ${w}
        </div>
      `).join("");
      alertContainer.style.display = "block";
    } else {
      alertContainer.style.display = "none";
    }
  }
}

function renderTopRecommendations(recs) {
  const container = document.getElementById("dash-top-recs");
  if (!container) return;

  const list = Array.isArray(recs) ? recs : [];
  const eligible = list.filter(r => r.is_eligible).slice(0, 3);
  if (eligible.length === 0) {
    container.innerHTML = `<p class="stat-subtext">No eligible loan offers matching baseline criteria. Check recommendations tab for full product list.</p>`;
    return;
  }

  container.innerHTML = eligible.map(r => `
    <div class="rec-card" data-loan-id="${r.loan_id}" style="margin-bottom:0.75rem; padding:1rem; cursor:pointer;" title="Click for details, cost pie chart & sliders">
      <div class="rec-card-top">
        <div>
          <span class="rec-lender">${r.lender_name}</span>
          <div class="rec-name" style="font-size:1.05rem;">${r.product_name} <span style="font-size:0.75rem; color:var(--primary-blue); font-weight:normal;">🔍</span></div>
        </div>
        <span class="badge badge-green">Probability: ${r.probability_percentage}</span>
      </div>
      <div class="rec-metrics-grid" style="padding:0.5rem 0.75rem;">
        <div class="rec-metric-item">
          <span class="rec-metric-label">Daily EMI</span>
          <span class="rec-metric-val">${formatINR(r.estimated_daily_emi)}</span>
        </div>
        <div class="rec-metric-item">
          <span class="rec-metric-label">Rate (APR)</span>
          <span class="rec-metric-val">${r.annual_interest_rate}%</span>
        </div>
        <div class="rec-metric-item">
          <span class="rec-metric-label">Total Interest</span>
          <span class="rec-metric-val">${formatINR(r.estimated_total_interest)}</span>
        </div>
      </div>
      <div class="rec-reason">${r.recommendation_reason}</div>
    </div>
  `).join("");

  container.querySelectorAll(".rec-card").forEach(card => {
    card.addEventListener("click", () => {
      const lid = card.getAttribute("data-loan-id");
      const prod = eligible.find(p => p.loan_id === lid);
      if (prod) openLoanDetailModal(prod);
    });
  });
}

function renderForecastPreview(fc) {
  const elInflow = document.getElementById("dash-fc-inflow");
  const elExpense = document.getElementById("dash-fc-expense");
  const elNet = document.getElementById("dash-fc-net");
  const elAvgDaily = document.getElementById("dash-fc-avg-daily");

  if (elInflow) elInflow.textContent = formatINR(fc.summary_inflow);
  if (elExpense) elExpense.textContent = formatINR(fc.summary_expense);
  if (elNet) elNet.textContent = formatINR(fc.summary_net_cashflow);
  if (elAvgDaily) elAvgDaily.textContent = formatINR(fc.avg_daily_net_cashflow) + "/day";

  const badge = document.getElementById("dash-fc-status-badge");
  if (badge) {
    if (fc.avg_daily_net_cashflow < 0) {
      badge.className = "badge badge-red";
      badge.textContent = "Caution: Net Deficit";
    } else {
      badge.className = "badge badge-green";
      badge.textContent = "Healthy Cashflow";
    }
  }
}

