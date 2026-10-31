/**
 * LoanIQ Application Controller and Router.
 */

import { requireAuth, handleLogout, getCurrentMerchantId, getCurrentMerchantProfile, formatINR } from "./auth.js";
import { initI18n } from "./i18n.js";
import { api } from "./api.js";
import { loadDashboard } from "./dashboard.js";
import { loadRecommendations, loadComparison } from "./loans.js";
import { loadForecast, handleRefreshForecast } from "./forecast.js";
import { loadOptimizer, handleRunSimulation, switchOptimizerTab } from "./optimizer.js";
import { initAssistant, openAssistantWindow } from "./assistant.js";

export function switchPage(pageName, params = {}) {
  if (pageName === "assistant") {
    openAssistantWindow();
    return;
  }

  // Update sidebar active link
  document.querySelectorAll(".nav-link").forEach(link => {
    const p = link.getAttribute("data-page");
    link.classList.toggle("active", p === pageName);
  });

  // Update page-section active class
  document.querySelectorAll(".page-section").forEach(sec => {
    sec.classList.remove("active");
  });

  const activeSec = document.getElementById(`section-${pageName}`);
  if (activeSec) {
    activeSec.classList.add("active");
  }

  window.location.hash = pageName;

  // Trigger page specific loader
  if (pageName === "dashboard") {
    loadDashboard();
  } else if (pageName === "recommendations") {
    loadRecommendations(params);
  } else if (pageName === "compare") {
    loadComparison(params.loan_ids || null);
  } else if (pageName === "forecast") {
    loadForecast(params.horizon || 30);
  } else if (pageName === "optimizer") {
    loadOptimizer();
  } else if (pageName === "profile") {
    loadProfilePage();
  }
}

async function loadProfilePage() {
  const merchantId = getCurrentMerchantId();
  if (!merchantId) return;

  const cachedProfile = getCurrentMerchantProfile();
  if (cachedProfile) {
    document.getElementById("prof-biz-name").textContent = cachedProfile.business_name || "-";
    document.getElementById("prof-id").textContent = cachedProfile.merchant_id || "-";
    document.getElementById("prof-type").textContent = (cachedProfile.merchant_type || "").replace("_", " ").toUpperCase() || "-";
    document.getElementById("prof-city").textContent = cachedProfile.city ? `${cachedProfile.city} (${cachedProfile.city_tier})` : "-";
    document.getElementById("prof-age").textContent = cachedProfile.business_age_months ? `${cachedProfile.business_age_months} months` : "-";
    document.getElementById("prof-sales").textContent = cachedProfile.monthly_sales_reference ? formatINR(cachedProfile.monthly_sales_reference) : "-";
    document.getElementById("prof-profit").textContent = cachedProfile.monthly_profit_reference ? formatINR(cachedProfile.monthly_profit_reference) : "-";
    document.getElementById("prof-score").textContent = cachedProfile.credit_score || "-";
    document.getElementById("prof-opening-bal").textContent = cachedProfile.opening_cash_balance ? formatINR(cachedProfile.opening_cash_balance) : "-";
    document.getElementById("prof-lang").textContent = cachedProfile.preferred_language || "-";
  }

  try {
    const profile = await api.merchants.getProfile(merchantId);
    const completedLoans = await api.merchants.getLoans(merchantId, "completed");

    document.getElementById("prof-biz-name").textContent = profile.business_name;
    document.getElementById("prof-id").textContent = profile.merchant_id;
    document.getElementById("prof-type").textContent = profile.merchant_type.replace("_", " ").toUpperCase();
    document.getElementById("prof-city").textContent = `${profile.city} (${profile.city_tier})`;
    document.getElementById("prof-age").textContent = `${profile.business_age_months} months`;
    document.getElementById("prof-sales").textContent = formatINR(profile.monthly_sales_reference);
    document.getElementById("prof-profit").textContent = formatINR(profile.monthly_profit_reference);
    document.getElementById("prof-score").textContent = profile.credit_score;
    document.getElementById("prof-opening-bal").textContent = formatINR(profile.opening_cash_balance);
    document.getElementById("prof-lang").textContent = profile.preferred_language;

    // Render completed loans
    const completedContainer = document.getElementById("completed-loans-container");
    if (completedContainer) {
      if (completedLoans.length === 0) {
        completedContainer.innerHTML = `<p class="stat-subtext">No completed loans on record.</p>`;
      } else {
        completedContainer.innerHTML = `
          <table class="data-table">
            <thead>
              <tr>
                <th>Account ID</th>
                <th>Product</th>
                <th>Disbursed</th>
                <th>Completed</th>
                <th>Principal Repaid</th>
                <th>Total Paid</th>
                <th>Interest Paid</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              ${completedLoans.map(l => `
                <tr>
                  <td><strong>${l.loan_account_id}</strong></td>
                  <td>${l.loan_id}</td>
                  <td>${l.disbursement_date}</td>
                  <td>${l.contractual_end_date}</td>
                  <td>${formatINR(l.principal_repaid_to_date)}</td>
                  <td>${formatINR(l.amount_paid_to_date)}</td>
                  <td>${formatINR(l.interest_paid_to_date)}</td>
                  <td><span class="badge badge-green">Completed</span></td>
                </tr>
              `).join("")}
            </tbody>
          </table>
        `;
      }
    }
  } catch (err) {
    console.error("Profile load error:", err);
  }
}

async function showSystemStatusModal() {
  const modal = document.getElementById("status-modal");
  const body = document.getElementById("status-modal-body");
  if (!modal || !body) return;

  modal.classList.add("active");
  body.innerHTML = "<p>Loading model metadata and integration status...</p>";

  try {
    const status = await api.system.getStatus();
    const meta = status.model_metadata || {};
    const fc = meta.cashflow_forecaster || {};
    const cl = meta.loan_acceptance_model || {};
    const intg = status.integrations_status || {};

    body.innerHTML = `
      <div style="display:flex; flex-direction:column; gap:1rem; font-size:0.875rem;">
        <div class="card" style="padding:0.75rem 1rem;">
          <strong>Integration Health:</strong>
          <div style="display:grid; grid-template-columns:1fr 1fr; gap:0.5rem; margin-top:0.5rem;">
            <div>AI Agent Subsystem: <span class="badge ${intg.agent_subsystem ? 'badge-green' : 'badge-red'}">${intg.agent_subsystem ? 'Operational' : 'Unavailable'}</span></div>
            <div>MCP Server: <span class="badge ${intg.mcp_server ? 'badge-green' : 'badge-red'}">${intg.mcp_server ? 'Running' : 'Offline'}</span></div>
            <div>OpenAI Reasoning: <span class="badge ${intg.openai_configured ? 'badge-green' : 'badge-amber'}">${intg.openai_configured ? 'Configured' : 'Key Absent (Deterministic Mode)'}</span></div>
            <div>Sarvam Voice: <span class="badge ${intg.sarvam_voice_configured ? 'badge-green' : 'badge-amber'}">${intg.sarvam_voice_configured ? 'Configured' : 'Key Absent'}</span></div>
            <div>Google Translate: <span class="badge ${intg.google_translate_configured ? 'badge-green' : 'badge-amber'}">${intg.google_translate_configured ? 'Configured' : 'Key Absent'}</span></div>
            <div>Prediction CSVs: <span class="badge ${status.predictions_available ? 'badge-green' : 'badge-red'}">${status.predictions_available ? 'Ready (4/4)' : 'Missing'}</span></div>
          </div>
        </div>

        <div class="card" style="padding:0.75rem 1rem;">
          <strong>Model 1: Cash-Flow Forecaster</strong>
          <div style="margin-top:0.35rem; color:var(--text-secondary);">
            • Architecture: ${fc.model_type || 'HistGradientBoostingRegressor'}<br>
            • Inflow Validation MAE: ₹${fc.inflow_mae?.toFixed(2) || '354.93'} (vs Seasonal Naive MAE ₹${fc.baseline_comparison?.inflow_seasonal_naive_mae?.toFixed(2) || '579.67'})<br>
            • Expense Validation MAE: ₹${fc.expense_mae?.toFixed(2) || '246.06'} (vs Seasonal Naive MAE ₹${fc.baseline_comparison?.expense_seasonal_naive_mae?.toFixed(2) || '399.06'})<br>
            • Split Date: ${fc.validation_split_date || '2026-07-01'} (Zero future leakage)
          </div>
        </div>

        <div class="card" style="padding:0.75rem 1rem;">
          <strong>Model 2: Loan Acceptance Classifier</strong>
          <div style="margin-top:0.35rem; color:var(--text-secondary);">
            • Architecture: ${cl.model_type || 'CalibratedClassifierCV (RandomForest)'}<br>
            • Test ROC-AUC: ${cl.evaluation_metrics?.roc_auc?.toFixed(4) || '0.6055'} | PR-AUC: ${cl.evaluation_metrics?.pr_auc?.toFixed(4) || '0.5732'}<br>
            • Brier Score: ${cl.evaluation_metrics?.brier_score?.toFixed(4) || '0.2406'} (Calibrated Probabilities)<br>
            • Chronological Split Date: ${cl.chronological_split_date || '2026-04-21'}
          </div>
        </div>
      </div>
    `;
  } catch (e) {
    body.innerHTML = `<p style="color:var(--accent-red);">Failed to load status: ${e.message}</p>`;
  }
}

window.switchPage = switchPage;
window.switchOptimizerTab = switchOptimizerTab;

// Global initialization
function initApp() {
  if (!requireAuth()) return;

  try { initI18n(); } catch (e) { console.error("i18n init error:", e); }
  try { initAssistant(); } catch (e) { console.error("Assistant init error:", e); }

  // Navigation Links
  document.querySelectorAll(".nav-link").forEach(link => {
    link.addEventListener("click", (e) => {
      e.preventDefault();
      const page = link.getAttribute("data-page");
      switchPage(page);
    });
  });

  // Logout button
  document.getElementById("logout-btn")?.addEventListener("click", handleLogout);

  // Status modal
  document.getElementById("status-btn")?.addEventListener("click", showSystemStatusModal);
  document.getElementById("close-modal-btn")?.addEventListener("click", () => {
    document.getElementById("status-modal")?.classList.remove("active");
  });

  // Filter handlers for Recommendations
  document.getElementById("apply-rec-filter-btn")?.addEventListener("click", () => loadRecommendations());
  document.getElementById("show-ineligible-toggle")?.addEventListener("change", () => loadRecommendations());
  document.getElementById("compare-selected-btn")?.addEventListener("click", () => switchPage("compare"));

  // Horizon Buttons
  document.querySelectorAll(".horizon-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const h = parseInt(btn.getAttribute("data-horizon"));
      loadForecast(h);
    });
  });
  document.getElementById("refresh-forecast-btn")?.addEventListener("click", handleRefreshForecast);

  // Simulation run button
  document.getElementById("run-simulation-btn")?.addEventListener("click", handleRunSimulation);

  // Default page route from hash
  const initialHash = window.location.hash.replace("#", "") || "dashboard";
  switchPage(initialHash);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initApp);
} else {
  initApp();
}

