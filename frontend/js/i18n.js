/**
 * Multilingual UI Translation Service for LoanIQ.
 * Translates UI string keys only, preserving all identifiers, currency, numbers, and dates.
 */

import { api } from "./api.js";

const CURRENT_LANG_KEY = "loaniq_ui_lang";
let currentLanguage = localStorage.getItem(CURRENT_LANG_KEY) || "en";
const baseStringMap = {};

export function getCurrentLanguage() {
  return currentLanguage;
}

export function initI18n() {
  // Capture original English strings from all [data-i18n] elements
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (!baseStringMap[key]) {
      baseStringMap[key] = el.textContent.trim();
    }
  });

  const selector = document.getElementById("lang-select");
  if (selector) {
    selector.value = currentLanguage;
    selector.addEventListener("change", async (e) => {
      await changeLanguage(e.target.value);
    });
  }

  if (currentLanguage !== "en") {
    changeLanguage(currentLanguage);
  }
}

export async function changeLanguage(targetLang) {
  currentLanguage = targetLang;
  localStorage.setItem(CURRENT_LANG_KEY, targetLang);

  if (targetLang === "en") {
    // Revert to base English
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (baseStringMap[key]) {
        el.textContent = baseStringMap[key];
      }
    });
    return;
  }

  // Check local cache
  const cacheKey = `loaniq_i18n_${targetLang}`;
  let cached = {};
  try {
    cached = JSON.parse(localStorage.getItem(cacheKey) || "{}");
  } catch (e) {
    cached = {};
  }

  // Collect strings to translate
  const toTranslate = {};
  for (const [key, text] of Object.entries(baseStringMap)) {
    if (!cached[key]) {
      toTranslate[key] = text;
    }
  }

  if (Object.keys(toTranslate).length > 0) {
    try {
      const res = await api.translation.translate({
        source_lang: "en",
        target_lang: targetLang,
        strings: toTranslate,
      });

      if (res && res.translations) {
        Object.assign(cached, res.translations);
        localStorage.setItem(cacheKey, JSON.stringify(cached));
      }
    } catch (err) {
      console.warn("Language translation error; remaining in English:", err);
    }
  }

  // Apply translations to DOM
  document.querySelectorAll("[data-i18n]").forEach((el) => {
    const key = el.getAttribute("data-i18n");
    if (cached[key]) {
      el.textContent = cached[key];
    } else if (baseStringMap[key]) {
      el.textContent = baseStringMap[key];
    }
  });
}

