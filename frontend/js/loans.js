/**
 * Loan Recommendations & Comparison Module for LoanIQ.
 */

import { api } from "./api.js";
import { getCurrentMerchantId, formatINR } from "./auth.js";

let currentRecommendations = [];
let selectedLoanIds = new Set();

export async function loadRecommendations(prefill = {}) {
  const merchantId = getCurrentMerchantId();
  if (!merchantId) return;

  const amountInput = document.getElementById("rec-amount-input");
  const tenureInput = document.getElementById("rec-tenure-input");
  const emiInput = document.getElementById("rec-emi-input");

  if (prefill.amount) amountInput.value = prefill.amount;
  if (prefill.tenure) tenureInput.value = prefill.tenure;
  if (prefill.emi) emiInput.value = prefill.emi;

  const amount = parseFloat(amountInput.value) || 100000;
  const tenure = parseInt(tenureInput.value) || 365;
  const maxEmi = parseFloat(emiInput.value) || null;

  try {
    currentRecommendations = await api.merchants.getRecommendations(merchantId, amount, maxEmi, tenure);
    renderRecommendations();
  } catch (err) {
    console.error("Failed to load recommendations:", err);
  }
}

export function renderRecommendations() {
  const container = document.getElementById("recommendations-list");
  const showIneligible = document.getElementById("show-ineligible-toggle")?.checked;
  if (!container) return;

  const listToRender = showIneligible
    ? currentRecommendations
    : currentRecommendations.filter(r => r.is_eligible);

  if (listToRender.length === 0) {
    container.innerHTML = `<div class="card"><p class="stat-subtext">No products match the selected criteria. Toggle 'Show Ineligible Products' to review failed requirements.</p></div>`;
    return;
  }

  container.innerHTML = listToRender.map(r => {
    const isChecked = selectedLoanIds.has(r.loan_id);
    const eligBadge = r.is_eligible
      ? `<span class="badge badge-green">Eligible</span>`
      : `<span class="badge badge-red">Ineligible</span>`;

    return `
      <div class="rec-card ${r.is_eligible ? '' : 'ineligible'}">
        <div class="rec-card-top">
          <div>
            <span class="rec-lender">${r.lender_name} • ${r.loan_id}</span>
            <div class="rec-name">${r.product_name}</div>
          </div>
          <div style="display:flex; align-items:center; gap:0.5rem;">
            ${eligBadge}
            <span class="badge badge-blue">Est. Acceptance: ${r.probability_percentage}</span>
            <label style="display:flex; align-items:center; gap:0.35rem; font-size:0.8rem; cursor:pointer; margin-left:0.5rem;">
              <input type="checkbox" class="compare-checkbox" data-loan-id="${r.loan_id}" ${isChecked ? 'checked' : ''}>
              Compare
            </label>
          </div>
        </div>

        <div class="rec-metrics-grid">
          <div class="rec-metric-item">
            <span class="rec-metric-label">Daily EMI</span>
            <span class="rec-metric-val">${formatINR(r.estimated_daily_emi)}</span>
          </div>
          <div class="rec-metric-item">
            <span class="rec-metric-label">Interest Rate</span>
            <span class="rec-metric-val">${r.annual_interest_rate}% APR</span>
          </div>
          <div class="rec-metric-item">
            <span class="rec-metric-label">Total Interest</span>
            <span class="rec-metric-val">${formatINR(r.estimated_total_interest)}</span>
          </div>
          <div class="rec-metric-item">
            <span class="rec-metric-label">Processing Fee</span>
            <span class="rec-metric-val">${formatINR(r.estimated_processing_fee)} (${r.processing_fee_pct}%)</span>
          </div>
          <div class="rec-metric-item">
            <span class="rec-metric-label">Prepayment Fee</span>
            <span class="rec-metric-val">${r.prepayment_fee_pct}%</span>
          </div>
          <div class="rec-metric-item">
            <span class="rec-metric-label">Affordability</span>
            <span class="rec-metric-val" style="font-size:0.85rem; color:${r.affordability_status.includes('High') ? '#ef4444' : '#10b981'};">${r.affordability_status}</span>
          </div>
        </div>

        ${r.is_eligible
          ? `<div class="rec-reason"><strong>Why this product:</strong> ${r.recommendation_reason}</div>`
          : `<div class="rec-ineligible-reason"><strong>Eligibility requirements failed:</strong> ${r.failed_reasons.join(" • ")}</div>`
        }

        <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.75rem; color:var(--text-secondary);">
          <span>Allowed Range: ₹${r.min_amount.toLocaleString()} - ₹${r.max_amount.toLocaleString()} | Tenure: ${r.min_tenure_days}-${r.max_tenure_days} days</span>
          <span>${r.disclaimer}</span>
        </div>
      </div>
    `;
  }).join("");

  // Attach compare checkbox listeners
  container.querySelectorAll(".compare-checkbox").forEach(cb => {
    cb.addEventListener("change", (e) => {
      const lid = e.target.getAttribute("data-loan-id");
      if (e.target.checked) {
        selectedLoanIds.add(lid);
      } else {
        selectedLoanIds.delete(lid);
      }
      updateCompareBar();
    });
  });

  updateCompareBar();
}

function updateCompareBar() {
  const btn = document.getElementById("compare-selected-btn");
  const countSpan = document.getElementById("selected-compare-count");
  if (btn && countSpan) {
    countSpan.textContent = selectedLoanIds.size;
    btn.disabled = selectedLoanIds.size === 0;
  }
}

export async function loadComparison(preselectedIds = null) {
  const merchantId = getCurrentMerchantId();
  if (!merchantId) return;

  const ids = preselectedIds || Array.from(selectedLoanIds);
  const amountInput = document.getElementById("rec-amount-input");
  const tenureInput = document.getElementById("rec-tenure-input");

  const amount = parseFloat(amountInput?.value) || 100000;
  const tenure = parseInt(tenureInput?.value) || 365;

  try {
    const summary = await api.loans.compare({
      merchant_id: merchantId,
      loan_ids: ids,
      requested_amount: amount,
      tenure_days: tenure
    });
    renderComparisonTable(summary);
  } catch (err) {
    console.error("Comparison load error:", err);
  }
}

function renderComparisonTable(summary) {
  const prods = summary.products || [];
  const container = document.getElementById("comparison-table-container");
  if (!container) return;

  if (prods.length === 0) {
    container.innerHTML = `<p class="stat-subtext">No products to compare. Please select products from the Recommendations page.</p>`;
    return;
  }

  // Highlights bar
  document.getElementById("best-overall-badge").textContent = summary.best_overall_loan_id || "N/A";
  document.getElementById("lowest-interest-badge").textContent = summary.lowest_interest_loan_id || "N/A";
  document.getElementById("highest-prob-badge").textContent = summary.highest_probability_loan_id || "N/A";

  const rows = [
    { label: "Product & Lender", format: p => `<strong>${p.product_name}</strong><br><small>${p.lender_name} (${p.loan_id})</small>` },
    { label: "Eligibility", format: p => p.is_eligible ? `<span class="badge badge-green">Eligible</span>` : `<span class="badge badge-red">Ineligible</span>` },
    { label: "Acceptance Probability", format: p => `<span class="badge badge-blue">${p.probability_percentage}</span>` },
    { label: "Interest Rate (APR)", format: p => `<strong>${p.annual_interest_rate}%</strong>` },
    { label: "Estimated Daily EMI", format: p => `<strong>${formatINR(p.estimated_daily_emi)}</strong>` },
    { label: "Total Interest Cost", format: p => formatINR(p.estimated_total_interest) },
    { label: "Processing Fee", format: p => `${formatINR(p.estimated_processing_fee)} (${p.processing_fee_pct}%)` },
    { label: "Prepayment Penalty", format: p => `${p.prepayment_fee_pct}%` },
    { label: "Total Borrowing Cost", format: p => `<strong>${formatINR(p.estimated_total_cost)}</strong>` },
    { label: "Allowed Tenure", format: p => `${p.min_tenure_days} - ${p.max_tenure_days} days` },
    { label: "Affordability Status", format: p => `<span class="badge ${p.affordability_status.includes('High') ? 'badge-red' : 'badge-green'}">${p.affordability_status}</span>` },
    { label: "Recommendation Fit", format: p => `<small>${p.recommendation_reason}</small>` },
  ];

  let tableHtml = `<table class="data-table"><thead><tr><th>Attribute</th>`;
  for (const p of prods) {
    const isBest = p.loan_id === summary.best_overall_loan_id;
    tableHtml += `<th style="${isBest ? 'background:#e0f2fe; border-top:3px solid var(--primary-blue);' : ''}">${p.product_name} ${isBest ? '⭐' : ''}</th>`;
  }
  tableHtml += `</tr></thead><tbody>`;

  for (const r of rows) {
    tableHtml += `<tr><td style="font-weight:600; background:#f8fafc;">${r.label}</td>`;
    for (const p of prods) {
      const isBest = p.loan_id === summary.best_overall_loan_id;
      tableHtml += `<td style="${isBest ? 'background:#f0f9ff;' : ''}">${r.format(p)}</td>`;
    }
    tableHtml += `</tr>`;
  }
  tableHtml += `</tbody></table>`;
  container.innerHTML = tableHtml;
}

