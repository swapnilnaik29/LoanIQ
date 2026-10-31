/**
 * Loan Recommendations & Comparison Module for LoanIQ.
 * Features:
 * - Real-time filtering against merchant inputs (amount, tenure, max EMI).
 * - Strict criteria compliance: products with out-of-criteria tenure/EMI/amount are excluded.
 * - Interactive Loan Detail & Optimization Modal with Donut/Pie Chart.
 * - 3-slider dynamic optimization in the pop-up modal (Amount, Tenure, Daily EMI) with RED MARKER alert.
 */

import { api } from "./api.js";
import { getCurrentMerchantId, formatINR } from "./auth.js";
import { switchPage } from "./app.js";

let currentRecommendations = [];
let selectedLoanIds = new Set();
let modalPieChart = null;

export async function loadRecommendations(prefill = {}) {
  const merchantId = getCurrentMerchantId();
  if (!merchantId) return;

  const amountInput = document.getElementById("rec-amount-input");
  const tenureInput = document.getElementById("rec-tenure-input");
  const emiInput = document.getElementById("rec-emi-input");

  if (prefill.amount && amountInput) amountInput.value = prefill.amount;
  if (prefill.tenure && tenureInput) tenureInput.value = prefill.tenure;
  if (prefill.emi && emiInput) emiInput.value = prefill.emi;

  const amount = parseFloat(amountInput?.value) || 100000;
  const tenure = parseInt(tenureInput?.value) || 365;
  const maxEmi = parseFloat(emiInput?.value) || null;

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

  const amountInput = document.getElementById("rec-amount-input");
  const tenureInput = document.getElementById("rec-tenure-input");
  const emiInput = document.getElementById("rec-emi-input");

  const requestedAmount = parseFloat(amountInput?.value) || 100000;
  const requestedTenure = parseInt(tenureInput?.value) || 365;
  const maxEmi = parseFloat(emiInput?.value) || null;

  // Criteria validation: If calculated tenure / EMI / amount is out of criteria, do NOT show the loan
  const listToRender = currentRecommendations.filter(r => {
    if (showIneligible) return true;
    if (!r.is_eligible) return false;
    // Check product amount bounds
    if (requestedAmount < r.min_amount || requestedAmount > r.max_amount) return false;
    // Check product tenure bounds
    if (requestedTenure < r.min_tenure_days || requestedTenure > r.max_tenure_days) return false;
    // Check requested max daily EMI limit
    if (maxEmi && r.estimated_daily_emi > maxEmi) return false;
    return true;
  });

  if (listToRender.length === 0) {
    container.innerHTML = `
      <div class="card" style="padding:2rem; text-align:center;">
        <p style="font-weight:700; color:var(--dark-navy); font-size:1.1rem; margin-bottom:0.5rem;">
          No Loan Products Match Your Specified Criteria
        </p>
        <p class="stat-subtext" style="max-width:600px; margin:0 auto;">
          The requested amount (${formatINR(requestedAmount)}), tenure (${requestedTenure} days), or daily EMI limit (${maxEmi ? formatINR(maxEmi) + '/day' : 'None'}) falls outside the allowed limits of available products. Adjust your filters above or check 'Show Ineligible Products'.
        </p>
      </div>
    `;
    return;
  }

  container.innerHTML = listToRender.map(r => {
    const isChecked = selectedLoanIds.has(r.loan_id);
    const eligBadge = r.is_eligible
      ? `<span class="badge badge-green">Eligible</span>`
      : `<span class="badge badge-red">Ineligible</span>`;

    return `
      <div class="rec-card ${r.is_eligible ? '' : 'ineligible'}" data-loan-id="${r.loan_id}" style="cursor:pointer;" title="Click to view details, cost pie chart, and interactive sliders">
        <div class="rec-card-top">
          <div>
            <span class="rec-lender">${r.lender_name} • ${r.loan_id}</span>
            <div class="rec-name" style="display:flex; align-items:center; gap:0.5rem;">
              <span>${r.product_name}</span>
              <span style="font-size:0.75rem; color:var(--primary-blue); font-weight:600;">🔍 Click for Interactive Modal</span>
            </div>
          </div>
          <div style="display:flex; align-items:center; gap:0.5rem;">
            ${eligBadge}
            <span class="badge badge-blue">Est. Acceptance: ${r.probability_percentage}</span>
            <label style="display:flex; align-items:center; gap:0.35rem; font-size:0.8rem; cursor:pointer; margin-left:0.5rem;" onclick="event.stopPropagation();">
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

        <div style="display:flex; justify-content:space-between; align-items:center; font-size:0.75rem; color:var(--text-secondary); margin-top:0.5rem;">
          <span>Allowed Range: ₹${r.min_amount.toLocaleString()} - ₹${r.max_amount.toLocaleString()} | Tenure: ${r.min_tenure_days}-${r.max_tenure_days} days</span>
          <span style="color:var(--primary-blue); font-weight:600;">👆 Click to Open Details, Pie Chart & Sliders</span>
        </div>
      </div>
    `;
  }).join("");

  // Attach card click handlers to open interactive detail modal
  container.querySelectorAll(".rec-card").forEach(card => {
    card.addEventListener("click", (e) => {
      if (e.target.closest(".compare-checkbox") || e.target.closest("label")) {
        return;
      }
      const loanId = card.getAttribute("data-loan-id");
      const product = currentRecommendations.find(r => r.loan_id === loanId);
      if (product) {
        openLoanDetailModal(product, requestedAmount, requestedTenure);
      }
    });
  });

  // Attach compare checkbox listeners
  container.querySelectorAll(".compare-checkbox").forEach(cb => {
    cb.addEventListener("change", (e) => {
      e.stopPropagation();
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

/* =========================================================================
 * INTERACTIVE LOAN DETAIL & 3-SLIDER OPTIMIZATION MODAL WITH PIE CHART
 * ========================================================================= */

export async function openLoanDetailModal(loanProduct, initialAmount = 100000, initialTenure = 365) {
  const modal = document.getElementById("loan-detail-modal");
  if (!modal) return;

  const merchantId = getCurrentMerchantId();
  let forecastNetDaily = 600.0;
  let activeDebtEmi = 358.17;

  if (merchantId) {
    try {
      const opt = await api.merchants.getOptimization(merchantId);
      activeDebtEmi = opt.total_current_daily_emi || 0.0;
      forecastNetDaily = opt.forecast_avg_daily_net_cashflow || 600.0;
    } catch (e) {
      console.warn("Could not fetch optimization context for modal:", e);
    }
  }

  // Populate header & information
  setText("modal-loan-title", `${loanProduct.lender_name} • ${loanProduct.product_name}`);
  setText("modal-loan-subtitle", `${loanProduct.lender_name} | Product ID: ${loanProduct.loan_id}`);
  setText("modal-loan-id-badge", loanProduct.loan_id);
  setText("modal-loan-prob-badge", `Est. Acceptance: ${loanProduct.probability_percentage || 'High'}`);

  const termsMeta = document.getElementById("modal-loan-terms-meta");
  if (termsMeta) {
    termsMeta.innerHTML = `
      • Rate: <strong>${loanProduct.annual_interest_rate}% APR</strong> | Processing Fee: <strong>${loanProduct.processing_fee_pct}%</strong> | Prepayment: <strong>${loanProduct.prepayment_fee_pct}%</strong><br>
      • Product Allowed Amount: <strong>${formatINR(loanProduct.min_amount)} - ${formatINR(loanProduct.max_amount)}</strong> | Allowed Tenure: <strong>${loanProduct.min_tenure_days} - ${loanProduct.max_tenure_days} Days</strong>
    `;
  }

  const reasonBox = document.getElementById("modal-loan-reason-box");
  if (reasonBox) {
    reasonBox.innerHTML = `<strong>Product Highlights:</strong> ${loanProduct.recommendation_reason || 'Matches your business profile and borrowing requirement.'}`;
  }

  // Sliders and Badges
  const amountSlider = document.getElementById("modal-slider-amount");
  const tenureSlider = document.getElementById("modal-slider-tenure");
  const emiSlider = document.getElementById("modal-slider-emi");

  const minAmt = loanProduct.min_amount || 10000;
  const maxAmt = loanProduct.max_amount || 300000;
  const minTen = loanProduct.min_tenure_days || 30;
  const maxTen = loanProduct.max_tenure_days || 540;

  setText("modal-amount-min-lbl", `Min ${formatINR(minAmt)}`);
  setText("modal-amount-max-lbl", `Max ${formatINR(maxAmt)}`);
  setText("modal-tenure-min-lbl", `Min ${minTen} Days`);
  setText("modal-tenure-max-lbl", `Max ${maxTen} Days`);
  setText("modal-emi-limit-lbl", `Forecast Net Cap: ${formatINR(forecastNetDaily)}/day`);

  if (amountSlider) {
    amountSlider.min = minAmt;
    amountSlider.max = maxAmt;
    amountSlider.step = minAmt >= 50000 ? 5000 : 2500;
    amountSlider.value = Math.max(minAmt, Math.min(maxAmt, initialAmount));
  }

  if (tenureSlider) {
    tenureSlider.min = minTen;
    tenureSlider.max = maxTen;
    tenureSlider.step = 5;
    tenureSlider.value = Math.max(minTen, Math.min(maxTen, initialTenure));
  }

  function computeEmi(P, annualRate, N) {
    if (P <= 0 || N <= 0) return 0;
    if (annualRate <= 0) return P / N;
    const r = (annualRate / 100) / 365;
    const factor = Math.pow(1 + r, N);
    return Math.round((P * (r * factor) / (factor - 1)) * 100) / 100;
  }

  function updateModalCalculations(fromSource = "amount_tenure") {
    let P = parseFloat(amountSlider?.value) || minAmt;
    P = Math.max(minAmt, Math.min(maxAmt, P));
    let N = parseInt(tenureSlider?.value) || minTen;
    const R = loanProduct.annual_interest_rate;
    const r = (R / 100) / 365;

    // Strict tenure-bounded Daily EMI limits:
    // Min allowed EMI occurs at maximum allowed tenure (maxTen)
    // Max allowed EMI occurs at minimum allowed tenure (minTen)
    const minAllowedEmi = computeEmi(P, R, maxTen);
    const maxAllowedEmi = computeEmi(P, R, minTen);

    // Dynamically constrain the Daily EMI slider track to these bounds
    if (emiSlider) {
      emiSlider.min = Math.floor(minAllowedEmi);
      emiSlider.max = Math.ceil(maxAllowedEmi);
      emiSlider.step = 1;
    }
    setText("modal-emi-min-lbl", `Min ${formatINR(minAllowedEmi)} (${maxTen}d)`);
    setText("modal-emi-max-lbl", `Max ${formatINR(maxAllowedEmi)} (${minTen}d)`);

    let emi = 0;
    if (fromSource === "emi") {
      emi = parseFloat(emiSlider?.value) || minAllowedEmi;

      // RULE: Do not increase daily EMI if tenure becomes less than minimum tenure, and vice versa
      if (emi >= maxAllowedEmi) {
        emi = maxAllowedEmi;
        N = minTen;
      } else if (emi <= minAllowedEmi) {
        emi = minAllowedEmi;
        N = maxTen;
      } else {
        if (emi > P * r) {
          const factor = emi / (emi - (P * r));
          N = Math.round(Math.log(factor) / Math.log(1 + r));
        } else {
          N = maxTen;
        }
        N = Math.max(minTen, Math.min(maxTen, N));
      }
      if (emiSlider) emiSlider.value = emi;
      if (tenureSlider) tenureSlider.value = N;
    } else {
      // fromSource is 'amount_tenure'
      if (N <= minTen) {
        N = minTen;
      } else if (N >= maxTen) {
        N = maxTen;
      }
      if (tenureSlider) tenureSlider.value = N;

      emi = computeEmi(P, R, N);
      // Clamp strictly within [minAllowedEmi, maxAllowedEmi]
      emi = Math.max(minAllowedEmi, Math.min(maxAllowedEmi, emi));
      if (emiSlider) emiSlider.value = emi;
    }

    // Calculations
    const totalRepay = Math.round(emi * N * 100) / 100;
    const totalInterest = Math.max(0, Math.round((totalRepay - P) * 100) / 100);
    const feePct = loanProduct.processing_fee_pct || 1.0;
    const feeAmt = Math.round(P * (feePct / 100) * 100) / 100;

    // Badges & Labels
    setText("modal-badge-amount", formatINR(P));
    setText("modal-badge-tenure", `${N} Days (${Math.round(N / 30)} mos)`);
    setText("modal-badge-emi", formatINR(emi) + "/day");
    setText("modal-pie-emi-badge", `Daily EMI: ${formatINR(emi)}/day`);

    setText("modal-kpi-principal", formatINR(P));
    setText("modal-kpi-emi", formatINR(emi) + "/day");
    setText("modal-kpi-interest", formatINR(totalInterest));
    setText("modal-kpi-repayment", formatINR(totalRepay));

    setText("modal-leg-principal", formatINR(P));
    setText("modal-leg-interest", formatINR(totalInterest));
    setText("modal-leg-fee", formatINR(feeAmt));

    // Dynamic Red Marker Evaluation
    const totalDailyCommitment = emi + activeDebtEmi;
    const exceedsForecast = emi > forecastNetDaily || totalDailyCommitment > forecastNetDaily;
    const flagEl = document.getElementById("modal-emi-red-marker-flag");
    const emiBadge = document.getElementById("modal-badge-emi");

    if (exceedsForecast) {
      emiSlider?.classList.add("danger");
      emiBadge?.classList.add("danger");
      if (flagEl) {
        const deficit = totalDailyCommitment - forecastNetDaily;
        flagEl.className = "red-marker-flag";
        flagEl.innerHTML = `🚨 <strong>RED MARKER ALERT:</strong> Daily EMI (${formatINR(emi)}) + Active Debt (${formatINR(activeDebtEmi)}) exceeds forecast daily cashflow (${formatINR(forecastNetDaily)}/day) by ${formatINR(deficit)}/day! High default risk.`;
      }
    } else {
      emiSlider?.classList.remove("danger");
      emiBadge?.classList.remove("danger");
      if (flagEl) {
        const surplus = forecastNetDaily - totalDailyCommitment;
        flagEl.className = "green-marker-flag";
        flagEl.innerHTML = `✅ <strong>SAFE ZONE:</strong> Daily payment is comfortably covered by forecast cashflow. Remaining safety buffer: ${formatINR(surplus)}/day.`;
      }
    }

    // Redraw Pie Chart
    renderModalPieChart(P, totalInterest, feeAmt, emi);
  }

  // Attach slider input listeners
  amountSlider.oninput = () => updateModalCalculations("amount_tenure");
  tenureSlider.oninput = () => updateModalCalculations("amount_tenure");
  emiSlider.oninput = () => updateModalCalculations("emi");

  // Initial Calculation
  updateModalCalculations("amount_tenure");

  // Send to Loan Optimizer button
  const applyBtn = document.getElementById("modal-apply-optimizer-btn");
  if (applyBtn) {
    applyBtn.onclick = () => {
      const selectedAmt = amountSlider.value;
      const selectedTen = tenureSlider.value;
      closeLoanModal();
      switchPage("optimizer");
      setTimeout(() => {
        const pSlider = document.getElementById("slider-amount");
        const tSlider = document.getElementById("slider-tenure");
        const rSlider = document.getElementById("slider-rate");
        if (pSlider) pSlider.value = selectedAmt;
        if (tSlider) tSlider.value = selectedTen;
        if (rSlider) rSlider.value = loanProduct.annual_interest_rate;
        pSlider?.dispatchEvent(new Event("input"));
        if (typeof window.switchOptimizerTab === "function") {
          window.switchOptimizerTab("new");
        }
      }, 150);
    };
  }

  // Close listeners
  document.getElementById("close-loan-modal-btn")?.addEventListener("click", closeLoanModal);
  document.getElementById("modal-cancel-btn")?.addEventListener("click", closeLoanModal);
  modal.onclick = (e) => {
    if (e.target === modal) closeLoanModal();
  };

  modal.classList.add("active");
}

function closeLoanModal() {
  const modal = document.getElementById("loan-detail-modal");
  if (modal) modal.classList.remove("active");
  if (modalPieChart) {
    try { modalPieChart.destroy(); } catch (e) {}
    modalPieChart = null;
  }
}

function renderModalPieChart(principal, totalInterest, processingFee, dailyEmi) {
  const canvas = document.getElementById("loanModalPieChart");
  if (!canvas) return;

  if (typeof Chart !== "undefined") {
    if (modalPieChart) {
      try { modalPieChart.destroy(); } catch (e) {}
    }
    try {
      const ctx = canvas.getContext("2d");
      modalPieChart = new Chart(ctx, {
        type: "doughnut",
        data: {
          labels: ["Principal Loan Amount", "Total Interest", "Processing Fee"],
          datasets: [{
            data: [principal, totalInterest, processingFee],
            backgroundColor: ["#002970", "#00BAF2", "#f59e0b"],
            borderWidth: 2,
            borderColor: "#ffffff",
            hoverOffset: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => {
                  const val = ctx.parsed || 0;
                  const total = principal + totalInterest + processingFee;
                  const pct = total > 0 ? Math.round((val / total) * 100) : 0;
                  return ` ${ctx.label}: ${formatINR(val)} (${pct}%)`;
                }
              }
            }
          },
          cutout: "60%"
        }
      });
    } catch (err) {
      drawCanvasDonutFallback(canvas, principal, totalInterest, processingFee);
    }
  } else {
    drawCanvasDonutFallback(canvas, principal, totalInterest, processingFee);
  }
}

function drawCanvasDonutFallback(canvas, principal, totalInterest, processingFee) {
  const ctx = canvas.getContext("2d");
  const w = canvas.width = 240;
  const h = canvas.height = 200;
  ctx.clearRect(0, 0, w, h);

  const total = principal + totalInterest + processingFee;
  if (total <= 0) return;

  const data = [
    { label: "Principal", val: principal, color: "#002970" },
    { label: "Interest", val: totalInterest, color: "#00BAF2" },
    { label: "Fee", val: processingFee, color: "#f59e0b" }
  ];

  const cx = w / 2;
  const cy = h / 2;
  const r = 70;
  const innerR = 42;

  let startAngle = -0.5 * Math.PI;
  for (const seg of data) {
    const sliceAngle = (seg.val / total) * 2 * Math.PI;
    ctx.beginPath();
    ctx.arc(cx, cy, r, startAngle, startAngle + sliceAngle);
    ctx.arc(cx, cy, innerR, startAngle + sliceAngle, startAngle, true);
    ctx.closePath();
    ctx.fillStyle = seg.color;
    ctx.fill();
    startAngle += sliceAngle;
  }
}

/* =========================================================================
 * PRODUCT COMPARISON TABLE
 * ========================================================================= */

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

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}
