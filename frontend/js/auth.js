/**
 * Authentication and Session Management for LoanIQ.
 */

import { api } from "./api.js";

const SESSION_KEY = "loaniq_merchant_id";
const PROFILE_KEY = "loaniq_merchant_profile";

export function getCurrentMerchantId() {
  return sessionStorage.getItem(SESSION_KEY);
}

export function getCurrentMerchantProfile() {
  const data = sessionStorage.getItem(PROFILE_KEY);
  return data ? JSON.parse(data) : null;
}

export function setCurrentMerchant(id, profile) {
  sessionStorage.setItem(SESSION_KEY, id);
  if (profile) {
    sessionStorage.setItem(PROFILE_KEY, JSON.stringify(profile));
  }
}

export function clearSession() {
  sessionStorage.removeItem(SESSION_KEY);
  sessionStorage.removeItem(PROFILE_KEY);
}

export function requireAuth() {
  const mId = getCurrentMerchantId();
  if (!mId) {
    window.location.href = "/login";
    return false;
  }
  return true;
}

export async function handleLogout() {
  try {
    await api.auth.logout();
  } catch (e) {
    console.warn("Logout error:", e);
  } finally {
    clearSession();
    window.location.href = "/login";
  }
}

export function formatINR(val) {
  if (val === null || val === undefined || isNaN(val)) return "₹0.00";
  const num = Number(val);
  return "₹" + num.toLocaleString("en-IN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

