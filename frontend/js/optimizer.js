/**
 * Interactive Loan Optimizer & Simulator Module for LoanIQ.
 * Featuring:
 * 1. Old / Existing Loan Optimizer:
 *    - Optimizes strictly on the basis of Current EMI, Remaining Tenure, and Remaining Principal.
 *    - Contractual interest rate is LOCKED / IMMUTABLE and cannot be changed.
 *    - Dynamic Daily EMI Slider with RED VALUE MARKER when EMI exceeds forecast cashflow.
 *    - Dynamic Remaining Tenure Slider with real-time recalculation of reducing-balance EMI.
 *    - Real-time payoff acceleration, interest savings, and cashflow impact calculations.
 * 2. Prospective New Loan Simulator:
 *    - Simulates borrowing a new loan with Principal Amount, Tenure, Daily EMI, and APR sliders.
 *    - Visual Stacked Debt Commitment Meter (Existing Active EMIs + New Loan EMI vs Forecast Cap).
 *    - Detailed cost breakdown and alternative restructuring options.
 */

import { api } from "./api.js";
import { getCurrentMerchantId, formatINR } from "./auth.js";

let currentForecastNetDaily = 600.0;
let currentExistingDailyEmi = 358.17;
let activeLoansList = [];
let debounceTimer = null;

// Currently selected old loan for optimization ('all' or active loan object)
let selectedOldLoanState = null;

export function computeEmi(P, annualRate, tenureDays) {
  if (P <= 0 || tenureDays <= 0) return 0;
  if (annualRate <= 0) return P / tenureDays;
  const r = (annualRate / 100) / 365;
  const factor = Math.pow(1 + r, tenureDays);
  return Math.round((P * (r * factor) / (factor - 1)) * 100) / 100;
}

export async function loadOptimizer() {
  const merchantId = getCurrentMerchantId();
  if (!merchantId) return;

  try {
    // 1. Fetch Optimization Summary & Active Loans
    const opt = await api.merchants.getOptimization(merchantId);
    currentExistingDailyEmi = opt.total_current_daily_emi || 0.0;
    currentForecastNetDaily = opt.forecast_avg_daily_net_cashflow || 1000.0;
    activeLoansList = opt.active_loans || [];

    renderOptimizationSummary(opt);
    renderActiveLoansTable(activeLoansList);

    // 2. Setup Tab Switching
    initSubTabNavigation();

    // 3. Initialize Old Loan Optimizer
    initOldLoanOptimizer();

    // 4. Initialize New Loan Simulator
    initNewLoanSimulator();

    // 5. Run initial simulation for new loan
    runSimulationFromSliders();
  } catch (err) {
    console.error("Optimizer load error:", err);
  }
}

function renderOptimizationSummary(opt) {
  setText("opt-tot-debt", formatINR(opt.total_remaining_principal));
  setText("opt-daily-emi", formatINR(opt.total_current_daily_emi));
  setText("opt-cashflow-avg", formatINR(opt.forecast_avg_daily_net_cashflow) + "/day");
  setText("opt-free-cash", formatINR(opt.cash_available_after_emi) + "/day");

  const recomBox = document.getElementById("opt-consolidation-recom");
  if (recomBox) {
    recomBox.textContent = opt.refinance_or_consolidation_recommendation;
  }
}

function renderActiveLoansTable(loans) {
  const container = document.getElementById("active-loans-table-container");
  if (!container) return;

  if (loans.length === 0) {
    container.innerHTML = `<p class="stat-subtext">No active loan obligations on record.</p>`;
    return;
  }

  container.innerHTML = `
    <table class="data-table">
      <thead>
        <tr>
          <th>Account</th>
          <th>Product</th>
          <th>Remaining Debt</th>
          <th>Daily EMI</th>
          <th>Interest (Fixed)</th>
          <th>Remaining Days</th>
        </tr>
      </thead>
      <tbody>
        ${loans.map(l => `
          <tr>
            <td><strong>${l.loan_account_id}</strong></td>
            <td>${l.loan_id}</td>
            <td>${formatINR(l.remaining_principal)}</td>
            <td style="color:#002970; font-weight:700;">${formatINR(l.daily_emi)}</td>
            <td><span class="badge badge-blue">${l.annual_interest_rate}%</span></td>
            <td>${l.remaining_tenure_days} days</td>
          </tr>
        `).join("")}
      </tbody>
    </table>
  `;
}

function initSubTabNavigation() {
  window.switchOptimizerTab = switchOptimizerTab;
}

export function switchOptimizerTab(tabName) {
  const btnOld = document.getElementById("btn-subtab-old-loan");
  const btnNew = document.getElementById("btn-subtab-new-loan");
  const tabOld = document.getElementById("subtab-old-loan");
  const tabNew = document.getElementById("subtab-new-loan");

  if (tabName === "old") {
    btnOld?.classList.add("active");
    btnNew?.classList.remove("active");
    if (tabOld) tabOld.style.display = "block";
    if (tabNew) tabNew.style.display = "none";
  } else {
    btnNew?.classList.add("active");
    btnOld?.classList.remove("active");
    if (tabNew) tabNew.style.display = "block";
    if (tabOld) tabOld.style.display = "none";
  }
}

/* =========================================================================
 * 1. OLD / EXISTING LOAN OPTIMIZER LOGIC (FIXED CONTRACTUAL APR)
 * ========================================================================= */

function initOldLoanOptimizer() {
  const selectEl = document.getElementById("old-loan-select");
  if (!selectEl) return;

  // Populate dropdown options
  let optionsHtml = `<option value="all">Combined Active Debt Portfolio (${formatINR(activeLoansList.reduce((s, l) => s + l.remaining_principal, 0))} Total Debt)</option>`;
  activeLoansList.forEach(l => {
    optionsHtml += `<option value="${l.loan_account_id}">${l.loan_account_id} - ${l.loan_id} (${formatINR(l.remaining_principal)} @ ${l.annual_interest_rate}% APR)</option>`;
  });
  selectEl.innerHTML = optionsHtml;

  selectEl.addEventListener("change", () => {
    loadSelectedOldLoan(selectEl.value);
  });

  // Load default (combined or first loan)
  loadSelectedOldLoan("all");
  attachOldLoanSliderListeners();
}

function loadSelectedOldLoan(selectionId) {
  if (selectionId === "all" || activeLoansList.length === 0) {
    const totalP = activeLoansList.reduce((s, l) => s + l.remaining_principal, 0);
    const totalEmi = activeLoansList.reduce((s, l) => s + l.daily_emi, 0);
    // Weighted APR
    const weightedApr = totalP > 0
      ? activeLoansList.reduce((s, l) => s + (l.remaining_principal * l.annual_interest_rate), 0) / totalP
      : 17.5;
    const maxTenure = activeLoansList.length > 0 ? Math.max(...activeLoansList.map(l => l.remaining_tenure_days)) : 268;

    selectedOldLoanState = {
      id: "all",
      title: "Combined Active Debt Portfolio",
      principal: totalP,
      apr: Math.round(weightedApr * 10) / 10,
      currDailyEmi: totalEmi,
      currTenureDays: maxTenure,
      otherEmi: 0.0 // no other loans outside portfolio
    };
  } else {
    const loan = activeLoansList.find(l => l.loan_account_id === selectionId) || activeLoansList[0];
    const otherEmi = activeLoansList
      .filter(l => l.loan_account_id !== loan.loan_account_id)
      .reduce((s, l) => s + l.daily_emi, 0);

    selectedOldLoanState = {
      id: loan.loan_account_id,
      title: `${loan.loan_account_id} (${loan.loan_id})`,
      principal: loan.remaining_principal,
      apr: loan.annual_interest_rate,
      currDailyEmi: loan.daily_emi,
      currTenureDays: loan.remaining_tenure_days,
      otherEmi: otherEmi
    };
  }

  // Update Locked Contractual Term display
  setText("old-disp-account-title", `Selected: ${selectedOldLoanState.title}`);
  setText("old-disp-principal", formatINR(selectedOldLoanState.principal));
  setText("old-disp-apr", `${selectedOldLoanState.apr.toFixed(1)}% APR`);
  setText("old-disp-curr-emi", formatINR(selectedOldLoanState.currDailyEmi) + "/day");
  setText("old-disp-curr-tenure", `${selectedOldLoanState.currTenureDays} Days`);

  const markerRef = document.getElementById("old-emi-threshold-reference");
  if (markerRef) {
    markerRef.textContent = `Forecast Net Limit: ${formatINR(currentForecastNetDaily)}/day`;
  }

  // Update slider bounds & set baseline values
  const emiSlider = document.getElementById("slider-old-emi");
  const tenureSlider = document.getElementById("slider-old-tenure");

  if (emiSlider && tenureSlider) {
    const P = selectedOldLoanState.principal;
    const R = selectedOldLoanState.apr;
    const minOldTenure = 15;
    const maxOldTenure = 540;

    const minOldEmi = computeEmi(P, R, maxOldTenure);
    const maxOldEmi = computeEmi(P, R, minOldTenure);

    emiSlider.min = Math.floor(minOldEmi);
    emiSlider.max = Math.ceil(maxOldEmi);
    emiSlider.step = 1;
    emiSlider.value = Math.max(minOldEmi, Math.min(maxOldEmi, Math.round(selectedOldLoanState.currDailyEmi)));

    tenureSlider.min = minOldTenure;
    tenureSlider.max = maxOldTenure;
    tenureSlider.step = 5;
    tenureSlider.value = Math.max(minOldTenure, Math.min(maxOldTenure, selectedOldLoanState.currTenureDays));

    setText("old-emi-min-lbl", `Min ${formatINR(minOldEmi)} (${maxOldTenure}d)`);
    setText("old-emi-max-lbl", `Max ${formatINR(maxOldEmi)} (${minOldTenure}d)`);

    syncOldSlidersFromEmi();
  }

  updateOldLoanCapacityMeter();
}

function attachOldLoanSliderListeners() {
  const emiSlider = document.getElementById("slider-old-emi");
  const tenureSlider = document.getElementById("slider-old-tenure");

  emiSlider?.addEventListener("input", syncOldSlidersFromEmi);
  tenureSlider?.addEventListener("input", syncOldSlidersFromTenure);
}

// When merchant drags Adjusted Daily EMI slider for old loan
function syncOldSlidersFromEmi() {
  if (!selectedOldLoanState) return;
  const emiSlider = document.getElementById("slider-old-emi");
  const tenureSlider = document.getElementById("slider-old-tenure");
  const emiBadge = document.getElementById("badge-old-emi");
  const tenureBadge = document.getElementById("badge-old-tenure");

  let newEmi = parseFloat(emiSlider.value);
  const P = selectedOldLoanState.principal;
  const R = selectedOldLoanState.apr;
  const r = (R / 100) / 365;

  const minOldTenure = 15;
  const maxOldTenure = 540;
  const minOldEmi = computeEmi(P, R, maxOldTenure);
  const maxOldEmi = computeEmi(P, R, minOldTenure);

  let calculatedN = 365;
  // RULE: "do not increase the daily emi if the tenure becomes less than minimum loan tenure and vice versa"
  if (newEmi >= maxOldEmi) {
    newEmi = maxOldEmi;
    calculatedN = minOldTenure;
  } else if (newEmi <= minOldEmi) {
    newEmi = minOldEmi;
    calculatedN = maxOldTenure;
  } else {
    if (newEmi > P * r) {
      const factor = newEmi / (newEmi - (P * r));
      calculatedN = Math.round(Math.log(factor) / Math.log(1 + r));
    } else {
      calculatedN = maxOldTenure;
    }
    calculatedN = Math.max(minOldTenure, Math.min(maxOldTenure, calculatedN));
  }

  emiSlider.value = newEmi;
  tenureSlider.value = calculatedN;

  emiBadge.textContent = formatINR(newEmi) + "/day";
  tenureBadge.textContent = `${calculatedN} Days (${Math.round(calculatedN / 30)} mos)`;

  evaluateOldLoanImpact(newEmi, calculatedN);
}

// When merchant drags Adjusted Tenure slider for old loan
function syncOldSlidersFromTenure() {
  if (!selectedOldLoanState) return;
  const emiSlider = document.getElementById("slider-old-emi");
  const tenureSlider = document.getElementById("slider-old-tenure");
  const emiBadge = document.getElementById("badge-old-emi");
  const tenureBadge = document.getElementById("badge-old-tenure");

  let N = parseInt(tenureSlider.value);
  const P = selectedOldLoanState.principal;
  const R = selectedOldLoanState.apr;
  const minOldTenure = 15;
  const maxOldTenure = 540;

  if (N <= minOldTenure) {
    N = minOldTenure;
  } else if (N >= maxOldTenure) {
    N = maxOldTenure;
  }
  tenureSlider.value = N;

  const minOldEmi = computeEmi(P, R, maxOldTenure);
  const maxOldEmi = computeEmi(P, R, minOldTenure);

  let calculatedEmi = computeEmi(P, R, N);
  calculatedEmi = Math.max(minOldEmi, Math.min(maxOldEmi, calculatedEmi));

  emiSlider.value = calculatedEmi;

  emiBadge.textContent = formatINR(calculatedEmi) + "/day";
  tenureBadge.textContent = `${N} Days (${Math.round(N / 30)} mos)`;

  evaluateOldLoanImpact(calculatedEmi, N);
}

function evaluateOldLoanImpact(newEmi, newTenure) {
  if (!selectedOldLoanState) return;

  const P = selectedOldLoanState.principal;
  const currEmi = selectedOldLoanState.currDailyEmi;
  const currN = selectedOldLoanState.currTenureDays;
  const otherEmi = selectedOldLoanState.otherEmi || 0;

  // Baseline contractual remaining interest
  const baselineRemainingInterest = Math.max(0, (currEmi * currN) - P);
  // New total repayment and remaining interest
  const newTotalRepayment = newEmi * newTenure;
  const newRemainingInterest = Math.max(0, newTotalRepayment - P);
  const interestDifference = baselineRemainingInterest - newRemainingInterest;

  // Combined daily commitment (Optimized loan EMI + Other active loans)
  const totalDailyCommitment = newEmi + otherEmi;
  const remainingCashBuffer = currentForecastNetDaily - totalDailyCommitment;

  // 1. Check RED MARKER threshold
  const emiSlider = document.getElementById("slider-old-emi");
  const emiBadge = document.getElementById("badge-old-emi");
  const markerFlag = document.getElementById("old-emi-red-marker-flag");

  const exceedsForecast = totalDailyCommitment > currentForecastNetDaily || newEmi > currentForecastNetDaily;

  if (exceedsForecast) {
    emiSlider?.classList.add("danger");
    emiBadge?.classList.add("danger");
    if (markerFlag) {
      const deficit = totalDailyCommitment - currentForecastNetDaily;
      markerFlag.className = "red-marker-flag";
      markerFlag.innerHTML = `🚨 <strong>RED MARKER ALERT:</strong> Daily EMI (${formatINR(newEmi)}) + Other Debt (${formatINR(otherEmi)}) exceeds your forecast daily cashflow (${formatINR(currentForecastNetDaily)}/day) by ${formatINR(deficit)}/day! High risk of daily default.`;
    }
  } else {
    emiSlider?.classList.remove("danger");
    emiBadge?.classList.remove("danger");
    if (markerFlag) {
      markerFlag.className = "green-marker-flag";
      markerFlag.innerHTML = `✅ <strong>SAFE ZONE:</strong> Daily payment is comfortably covered by forecast cashflow. Safety buffer: ${formatINR(remainingCashBuffer)}/day.`;
    }
  }

  // 2. Update Impact Box Metrics
  const speedEl = document.getElementById("old-impact-speed");
  const diffEl = document.getElementById("old-impact-interest-diff");
  const badgeEl = document.getElementById("old-impact-interest-badge");
  const repayEl = document.getElementById("old-impact-total-repay");
  const bufferEl = document.getElementById("old-impact-buffer");
  const strategyTextEl = document.getElementById("old-impact-strategy-text");

  const daysSaved = currN - newTenure;

  if (speedEl) {
    if (daysSaved > 0) {
      speedEl.textContent = `⚡ ${daysSaved} Days Earlier`;
      speedEl.style.color = "#059669";
    } else if (daysSaved < 0) {
      speedEl.textContent = `⏳ ${Math.abs(daysSaved)} Days Extended`;
      speedEl.style.color = "#d97706";
    } else {
      speedEl.textContent = `Current Pace`;
      speedEl.style.color = "#002970";
    }
  }

  if (diffEl && badgeEl) {
    if (interestDifference > 50) {
      diffEl.textContent = `- ${formatINR(interestDifference)}`;
      diffEl.style.color = "#059669";
      badgeEl.className = "badge badge-green";
      badgeEl.textContent = `Save ${formatINR(interestDifference)} Interest`;
    } else if (interestDifference < -50) {
      diffEl.textContent = `+ ${formatINR(Math.abs(interestDifference))}`;
      diffEl.style.color = "#d97706";
      badgeEl.className = "badge badge-amber";
      badgeEl.textContent = `+ ${formatINR(Math.abs(interestDifference))} Interest Cost`;
    } else {
      diffEl.textContent = `₹0.00`;
      diffEl.style.color = "#64748b";
      badgeEl.className = "badge badge-blue";
      badgeEl.textContent = `Baseline Contract Terms`;
    }
  }

  if (repayEl) repayEl.textContent = formatINR(newTotalRepayment);
  if (bufferEl) {
    bufferEl.textContent = formatINR(remainingCashBuffer) + "/day";
    bufferEl.style.color = remainingCashBuffer < 0 ? "#ef4444" : (remainingCashBuffer < 100 ? "#d97706" : "#059669");
  }

  // Strategic rule-based summary note
  if (strategyTextEl) {
    if (daysSaved > 0 && !exceedsForecast) {
      const extraDaily = newEmi - currEmi;
      strategyTextEl.innerHTML = `<strong>Accelerated Repayment Strategy:</strong> Paying <strong>${formatINR(extraDaily)} more per day</strong> retires this obligation <strong>${daysSaved} days sooner</strong> and saves <strong>${formatINR(interestDifference)}</strong> in interest charges while maintaining a safe operating buffer of <strong>${formatINR(remainingCashBuffer)}/day</strong>.`;
    } else if (daysSaved < 0) {
      const dailyRelief = currEmi - newEmi;
      strategyTextEl.innerHTML = `<strong>Cashflow Relief Strategy:</strong> Reducing daily payments by <strong>${formatINR(dailyRelief)}/day</strong> frees up immediate working capital, boosting daily buffer to <strong>${formatINR(remainingCashBuffer)}/day</strong>. Remaining tenure extends by ${Math.abs(daysSaved)} days with ${formatINR(Math.abs(interestDifference))} added in total interest.`;
    } else if (exceedsForecast) {
      strategyTextEl.innerHTML = `<span style="color:#b91c1c;"><strong>Liquidity Stress Alert:</strong> This repayment pace exceeds your business cash generation capability. Lower the daily EMI to avoid operational cash crunches.</span>`;
    } else {
      strategyTextEl.innerHTML = `Operating under contractual schedule terms. Adjust sliders to explore payoff acceleration or cashflow relief scenarios.`;
    }
  }

  updateOldLoanCapacityMeter();
}

function updateOldLoanCapacityMeter() {
  const visualGauge = document.getElementById("affordability-gauge-bar");
  if (!visualGauge) return;

  const emiSlider = document.getElementById("slider-old-emi");
  const optimizedEmi = emiSlider ? parseFloat(emiSlider.value) : currentExistingDailyEmi;
  const otherEmi = selectedOldLoanState ? selectedOldLoanState.otherEmi : 0;
  const totalCommitment = optimizedEmi + otherEmi;

  const pctCommitment = Math.min(100, (totalCommitment / currentForecastNetDaily) * 100);
  const isOver = totalCommitment > currentForecastNetDaily;

  visualGauge.innerHTML = `
    <div style="display:flex; height:18px; border-radius:9px; overflow:hidden; background:#e2e8f0; margin-top:0.4rem;">
      <div style="width:${pctCommitment}%; background:${isOver ? '#ef4444' : '#002970'}; transition:width 0.2s;" title="Total Commitment: ${formatINR(totalCommitment)}"></div>
    </div>
    <div style="display:flex; justify-content:space-between; font-size:0.75rem; color:var(--text-secondary); margin-top:0.35rem;">
      <span>Active Obligation: ${formatINR(totalCommitment)}/day</span>
      <span style="font-weight:700; color:${isOver ? '#ef4444' : '#002970'};">${isOver ? 'DEFICIT ALERT' : 'COVERED BY CASHFLOW'}</span>
      <span>Forecast Cap: ${formatINR(currentForecastNetDaily)}/day</span>
    </div>
  `;
}


/* =========================================================================
 * 2. PROSPECTIVE NEW LOAN SIMULATOR LOGIC
 * ========================================================================= */

function initNewLoanSimulator() {
  const amountSlider = document.getElementById("slider-amount");
  const tenureSlider = document.getElementById("slider-tenure");
  const emiSlider = document.getElementById("slider-emi");
  const rateSlider = document.getElementById("slider-rate");

  if (!amountSlider || !tenureSlider || !emiSlider || !rateSlider) return;

  const amountBadge = document.getElementById("badge-amount");
  const tenureBadge = document.getElementById("badge-tenure");
  const emiBadge = document.getElementById("badge-emi");
  const rateBadge = document.getElementById("badge-rate");

  const markerLabel = document.getElementById("emi-threshold-reference");
  if (markerLabel) {
    markerLabel.textContent = `Forecast Net Limit: ${formatINR(currentForecastNetDaily)}/day`;
  }

  const minNewTenure = 30;
  const maxNewTenure = 540;

  function syncNewLoanSliders() {
    const P = parseFloat(amountSlider.value);
    let N = parseInt(tenureSlider.value);
    const R = parseFloat(rateSlider.value);

    if (N <= minNewTenure) N = minNewTenure;
    if (N >= maxNewTenure) N = maxNewTenure;
    tenureSlider.value = N;

    // Strict tenure-bounded Daily EMI limits for prospective new loan
    const minNewEmi = computeEmi(P, R, maxNewTenure);
    const maxNewEmi = computeEmi(P, R, minNewTenure);

    emiSlider.min = Math.floor(minNewEmi);
    emiSlider.max = Math.ceil(maxNewEmi);
    emiSlider.step = 1;

    let calculatedEmi = computeEmi(P, R, N);
    calculatedEmi = Math.max(minNewEmi, Math.min(maxNewEmi, calculatedEmi));
    emiSlider.value = calculatedEmi;

    amountBadge.textContent = formatINR(P);
    tenureBadge.textContent = `${N} Days (${Math.round(N / 30)} mos)`;
    rateBadge.textContent = `${R.toFixed(1)}% APR`;
    emiBadge.textContent = formatINR(calculatedEmi) + "/day";

    setText("new-emi-min-lbl", `Min ${formatINR(minNewEmi)} (${maxNewTenure}d)`);
    setText("new-emi-max-lbl", `Max ${formatINR(maxNewEmi)} (${minNewTenure}d)`);

    checkNewLoanEmiThreshold(calculatedEmi);
    triggerDebouncedSimulation();
  }

  function syncFromNewLoanEmiSlider() {
    let emi = parseFloat(emiSlider.value);
    const P = parseFloat(amountSlider.value);
    const R = parseFloat(rateSlider.value);
    const r = (R / 100) / 365;

    const minNewEmi = computeEmi(P, R, maxNewTenure);
    const maxNewEmi = computeEmi(P, R, minNewTenure);

    let N = 180;
    // RULE: "do not increase the daily emi if the tenure becomes less than minimum loan tenure and vice versa"
    if (emi >= maxNewEmi) {
      emi = maxNewEmi;
      N = minNewTenure;
    } else if (emi <= minNewEmi) {
      emi = minNewEmi;
      N = maxNewTenure;
    } else {
      if (emi > P * r) {
        const factor = emi / (emi - (P * r));
        N = Math.round(Math.log(factor) / Math.log(1 + r));
      } else {
        N = maxNewTenure;
      }
      N = Math.max(minNewTenure, Math.min(maxNewTenure, N));
    }

    emiSlider.value = emi;
    tenureSlider.value = N;

    amountBadge.textContent = formatINR(P);
    tenureBadge.textContent = `${N} Days (${Math.round(N / 30)} mos)`;
    rateBadge.textContent = `${R.toFixed(1)}% APR`;
    emiBadge.textContent = formatINR(emi) + "/day";

    checkNewLoanEmiThreshold(emi);
    triggerDebouncedSimulation();
  }

  function checkNewLoanEmiThreshold(newLoanEmi) {
    const totalDailyCommitment = currentExistingDailyEmi + newLoanEmi;
    const markerFlag = document.getElementById("emi-red-marker-flag");

    setText("new-disp-existing-emi", formatINR(currentExistingDailyEmi) + "/day");
    setText("new-disp-simulated-emi", formatINR(newLoanEmi) + "/day");
    setText("new-disp-total-commitment", formatINR(totalDailyCommitment) + "/day");
    setText("new-disp-forecast-limit", formatINR(currentForecastNetDaily) + "/day");

    const exceedsForecast = newLoanEmi > currentForecastNetDaily || totalDailyCommitment > currentForecastNetDaily;

    if (exceedsForecast) {
      emiSlider.classList.add("danger");
      emiBadge.classList.add("danger");
      if (markerFlag) {
        const deficit = totalDailyCommitment - currentForecastNetDaily;
        markerFlag.className = "red-marker-flag";
        markerFlag.innerHTML = `🚨 <strong>RED MARKER ALERT:</strong> New Loan EMI (${formatINR(newLoanEmi)}) + Active Debt (${formatINR(currentExistingDailyEmi)}) exceeds forecast cashflow (${formatINR(currentForecastNetDaily)}/day) by ${formatINR(deficit)}/day!`;
      }
    } else {
      emiSlider.classList.remove("danger");
      emiBadge.classList.remove("danger");
      if (markerFlag) {
        const surplus = currentForecastNetDaily - totalDailyCommitment;
        markerFlag.className = "green-marker-flag";
        markerFlag.innerHTML = `✅ <strong>SAFE ZONE:</strong> Combined payments covered by forecast cashflow. Remaining safety buffer: ${formatINR(surplus)}/day.`;
      }
    }

    // Render stacked capacity meter
    const visualGauge = document.getElementById("new-loan-gauge-bar");
    if (visualGauge) {
      const pctExisting = Math.min(100, (currentExistingDailyEmi / currentForecastNetDaily) * 100);
      const pctNew = Math.min(100 - pctExisting, (newLoanEmi / currentForecastNetDaily) * 100);
      const isOver = totalDailyCommitment > currentForecastNetDaily;

      visualGauge.innerHTML = `
        <div style="display:flex; height:18px; border-radius:9px; overflow:hidden; background:#e2e8f0; margin-top:0.4rem;">
          <div style="width:${pctExisting}%; background:#002970;" title="Existing Debt EMI: ${formatINR(currentExistingDailyEmi)}"></div>
          <div style="width:${pctNew}%; background:${isOver ? '#ef4444' : '#00BAF2'};" title="Simulated New EMI: ${formatINR(newLoanEmi)}"></div>
        </div>
        <div style="display:flex; justify-content:space-between; font-size:0.75rem; color:var(--text-secondary); margin-top:0.35rem;">
          <span>Active: ${formatINR(currentExistingDailyEmi)}</span>
          <span style="font-weight:700; color:${isOver ? '#ef4444' : '#002970'};">Combined: ${formatINR(totalDailyCommitment)}/day</span>
          <span>Forecast Cap: ${formatINR(currentForecastNetDaily)}/day</span>
        </div>
      `;
    }
  }

  // Event Listeners
  amountSlider.addEventListener("input", syncNewLoanSliders);
  tenureSlider.addEventListener("input", syncNewLoanSliders);
  rateSlider.addEventListener("input", syncNewLoanSliders);
  emiSlider.addEventListener("input", syncFromNewLoanEmiSlider);

  // Initial sync
  syncNewLoanSliders();
}

function triggerDebouncedSimulation() {
  if (debounceTimer) clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => {
    runSimulationFromSliders();
  }, 200);
}

export async function runSimulationFromSliders() {
  const merchantId = getCurrentMerchantId();
  if (!merchantId) return;

  const amountSlider = document.getElementById("slider-amount");
  const tenureSlider = document.getElementById("slider-tenure");
  const rateSlider = document.getElementById("slider-rate");

  if (!amountSlider || !tenureSlider || !rateSlider) return;

  const amount = parseFloat(amountSlider.value) || 50000;
  const tenure = parseInt(tenureSlider.value) || 180;
  const rate = parseFloat(rateSlider.value) || 15.0;

  try {
    const result = await api.loans.simulate({
      merchant_id: merchantId,
      loan_amount: amount,
      tenure_days: tenure,
      annual_interest_rate: rate,
      processing_fee_pct: 1.0,
      prepayment_fee_pct: 0.0,
      safety_buffer: 5000.0,
    });
    renderSimulationResult(result);
  } catch (err) {
    console.error("Simulation error:", err);
  }
}

export const handleRunSimulation = runSimulationFromSliders;

function renderSimulationResult(sim) {
  const container = document.getElementById("sim-result-container");
  if (!container) return;

  container.style.display = "block";
  setText("sim-out-emi", formatINR(sim.daily_emi));
  setText("sim-out-interest", formatINR(sim.total_interest));
  setText("sim-out-fee", formatINR(sim.processing_fee));
  setText("sim-out-cost", formatINR(sim.total_cost));
  setText("sim-out-repay", formatINR(sim.total_repayment));

  const alertBox = document.getElementById("sim-status-banner");
  if (alertBox) {
    if (sim.is_affordable) {
      alertBox.className = "disclaimer-banner";
      alertBox.style.background = "#ecfdf5";
      alertBox.style.borderColor = "#a7f3d0";
      alertBox.style.color = "#065f46";
      alertBox.innerHTML = `✅ <strong>Affordable Borrowing:</strong> Daily EMI of ${formatINR(sim.daily_emi)} fits safely within your operational cashflow.`;
    } else {
      alertBox.className = "disclaimer-banner";
      alertBox.style.background = "#fef2f2";
      alertBox.style.borderColor = "#fecaca";
      alertBox.style.color = "#991b1b";
      alertBox.innerHTML = `⚠️ <strong>High Liquidity Stress:</strong> ${sim.affordability_notes}`;
    }
  }

  const altContainer = document.getElementById("sim-alternatives-container");
  if (altContainer && sim.suggested_alternatives) {
    altContainer.innerHTML = sim.suggested_alternatives.map(alt => `
      <div class="card" style="padding:0.75rem 1rem; margin-top:0.5rem; background:#f8fafc; border-left:3px solid var(--primary-blue);">
        <div style="display:flex; justify-content:space-between; align-items:center;">
          <strong>${alt.scenario}</strong>
          <span class="badge badge-blue">Adjusted EMI: ${formatINR(alt.daily_emi)}/day</span>
        </div>
        <p style="font-size:0.8rem; color:var(--text-secondary); margin-top:0.25rem;">${alt.rationale}</p>
      </div>
    `).join("");
  }
}

function setText(id, text) {
  const el = document.getElementById(id);
  if (el) el.textContent = text;
}
