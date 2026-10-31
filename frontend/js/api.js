/**
 * Central API Client for LoanIQ Frontend.
 */

const API_BASE = "/api";

async function request(endpoint, options = {}) {
  const url = `${API_BASE}${endpoint}`;
  const headers = options.headers || {};

  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const config = {
    ...options,
    headers,
  };

  try {
    const response = await fetch(url, config);
    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      const msg = errData.detail || errData.message || `HTTP error ${response.status}`;
      throw new Error(msg);
    }
    return await response.json();
  } catch (err) {
    console.error(`API Error [${endpoint}]:`, err);
    throw err;
  }
}

export const api = {
  auth: {
    getAvailableMerchants: () => request("/auth/merchants"),
    login: (merchant_id) => request("/auth/login", {
      method: "POST",
      body: JSON.stringify({ merchant_id }),
    }),
    logout: () => request("/auth/logout", { method: "POST" }),
  },
  merchants: {
    getProfile: (id) => request(`/merchants/${id}/profile`),
    getLoans: (id, status = "all") => request(`/merchants/${id}/loans?status=${status}`),
    getForecast: (id, horizon = 30) => request(`/merchants/${id}/forecast?horizon=${horizon}`),
    refreshForecast: (id) => request(`/merchants/${id}/forecast/refresh`, { method: "POST" }),
    getOptimization: (id) => request(`/merchants/${id}/optimization`),
    getRecommendations: (id, amount = 100000, emi = null, tenure = 365) => {
      let q = `/merchants/${id}/recommendations?requested_amount=${amount}&tenure_days=${tenure}`;
      if (emi) q += `&max_daily_emi=${emi}`;
      return request(q);
    },
  },
  loans: {
    getProducts: () => request("/loans/products"),
    checkEligibility: (data) => request("/loans/eligibility", {
      method: "POST",
      body: JSON.stringify(data),
    }),
    getAcceptanceProbability: (data) => request("/loans/acceptance-probability", {
      method: "POST",
      body: JSON.stringify(data),
    }),
    compare: (data) => request("/loans/compare", {
      method: "POST",
      body: JSON.stringify(data),
    }),
    simulate: (data) => request("/loans/simulate", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  },
  assistant: {
    chat: (data) => request("/assistant/chat", {
      method: "POST",
      body: JSON.stringify(data),
    }),
    stt: (formData) => request("/assistant/stt", {
      method: "POST",
      body: formData,
    }),
    tts: (data) => request("/assistant/tts", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  },
  translation: {
    getLanguages: () => request("/translation/languages"),
    translate: (data) => request("/translation/translate", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  },
  system: {
    getStatus: () => request("/model/status"),
    getHealth: () => request("/health"),
  },
};

