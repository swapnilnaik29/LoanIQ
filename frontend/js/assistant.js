/**
 * Conversational AI Assistant & Voice Interface for LoanIQ.
 * Orchestrates natural-language loan actions, comparison explanations, bounded finance Q&A,
 * and automated UI form prefill / navigation.
 * Embedded as a persistent floating assistant in the bottom-left corner.
 */

import { api } from "./api.js";
import { getCurrentMerchantId } from "./auth.js";
import { switchPage } from "./app.js";

let mediaRecorder = null;
let audioChunks = [];
let isRecording = false;

export function toggleAssistantWindow() {
  const win = document.getElementById("floating-chat-window");
  if (win) {
    win.classList.toggle("open");
    if (win.classList.contains("open")) {
      document.getElementById("chat-input")?.focus();
    }
  }
}

export function openAssistantWindow() {
  const win = document.getElementById("floating-chat-window");
  if (win) {
    win.classList.add("open");
    document.getElementById("chat-input")?.focus();
  }
}

export function closeAssistantWindow() {
  const win = document.getElementById("floating-chat-window");
  if (win) {
    win.classList.remove("open");
  }
}

export function initAssistant() {
  const sendBtn = document.getElementById("chat-send-btn");
  const input = document.getElementById("chat-input");
  const micBtn = document.getElementById("chat-mic-btn");
  const floatingBtn = document.getElementById("floating-assistant-btn");
  const closeBtn = document.getElementById("close-chat-window-btn");
  const minBtn = document.getElementById("minimize-chat-window-btn");

  if (floatingBtn) {
    floatingBtn.addEventListener("click", toggleAssistantWindow);
  }
  if (closeBtn) {
    closeBtn.addEventListener("click", closeAssistantWindow);
  }
  if (minBtn) {
    minBtn.addEventListener("click", closeAssistantWindow);
  }

  if (sendBtn && input) {
    sendBtn.addEventListener("click", () => handleSendMessage());
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") handleSendMessage();
    });
  }

  if (micBtn) {
    micBtn.addEventListener("click", toggleVoiceRecording);
  }

  // Quick prompt pills
  document.querySelectorAll(".prompt-pill").forEach(pill => {
    pill.addEventListener("click", () => {
      const promptText = pill.getAttribute("data-prompt") || pill.textContent.trim();
      if (input) input.value = promptText;
      handleSendMessage();
    });
  });
}

export async function handleSendMessage() {
  const input = document.getElementById("chat-input");
  const message = input.value.trim();
  if (!message) return;

  const merchantId = getCurrentMerchantId();
  if (!merchantId) return;

  input.value = "";
  appendChatMessage("user", message);

  // Show typing placeholder
  const placeholderId = appendChatMessage("assistant", "Thinking...");

  try {
    const res = await api.assistant.chat({
      merchant_id: merchantId,
      message,
      session_id: "demo_session",
      page_context: {
        current_page: window.location.hash.replace("#", "") || "dashboard",
      }
    });

    updateChatMessage(placeholderId, res.reply_text, res.workflow_type, res.llm_used, res.tool_calls);

    // If UI Action was returned, execute it after brief delay
    if (res.ui_action && res.ui_action.action_type === "NAVIGATE" && res.ui_action.target_page) {
      setTimeout(() => {
        switchPage(res.ui_action.target_page, res.ui_action.parameters);
      }, 1000);
    }
  } catch (err) {
    updateChatMessage(placeholderId, `Error communicating with Assistant: ${err.message}`, "ERROR", false);
  }
}

function appendChatMessage(role, text) {
  const container = document.getElementById("chat-messages-container");
  if (!container) return null;

  const msgId = `msg-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`;
  const div = document.createElement("div");
  div.id = msgId;
  div.className = `chat-msg ${role}`;
  div.innerHTML = formatMarkdownLike(text);

  container.appendChild(div);
  container.scrollTop = container.scrollHeight;
  return msgId;
}

function updateChatMessage(msgId, text, workflowType, llmUsed, toolCalls = []) {
  const el = document.getElementById(msgId);
  if (!el) return;

  let toolHtml = "";
  if (toolCalls && toolCalls.length > 0) {
    toolHtml = toolCalls.map(t => `
      <div class="chat-tool-pill">
        ⚙️ <strong>${t.tool_name}</strong>: ${t.result_preview}
      </div>
    `).join("");
  }

  const modeBadge = llmUsed
    ? `<span style="font-size:0.7rem; color:#0284c7; display:block; margin-bottom:0.25rem;">✨ OpenAI Reasoning Active</span>`
    : `<span style="font-size:0.7rem; color:#64748b; display:block; margin-bottom:0.25rem;">⚡ Deterministic Agent Workflow (${workflowType})</span>`;

  // TTS speak button
  const ttsBtn = `<button class="btn btn-outline btn-sm tts-speak-btn" style="margin-top:0.5rem; font-size:0.7rem; padding:0.2rem 0.5rem;" data-text="${encodeURIComponent(text.slice(0, 300))}">🔊 Speak</button>`;

  el.innerHTML = `
    ${modeBadge}
    <div>${formatMarkdownLike(text)}</div>
    ${toolHtml}
    ${ttsBtn}
  `;

  // Attach TTS handler
  const btn = el.querySelector(".tts-speak-btn");
  if (btn) {
    btn.addEventListener("click", () => {
      handlePlayTTS(decodeURIComponent(btn.getAttribute("data-text")));
    });
  }

  const container = document.getElementById("chat-messages-container");
  if (container) container.scrollTop = container.scrollHeight;
}

async function handlePlayTTS(text) {
  try {
    const res = await api.assistant.tts({ text, language_code: "hi-IN" });
    if (res && res.audio_base64) {
      const audio = new Audio("data:audio/wav;base64," + res.audio_base64);
      audio.play();
    } else {
      alert(res.message || "Voice playback requires SARVAM_API_KEY.");
    }
  } catch (e) {
    console.warn("TTS playback error:", e);
  }
}

async function toggleVoiceRecording() {
  const micBtn = document.getElementById("chat-mic-btn");

  if (!isRecording) {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      audioChunks = [];
      mediaRecorder = new MediaRecorder(stream);
      mediaRecorder.ondataavailable = e => audioChunks.push(e.data);
      mediaRecorder.onstop = async () => {
        const audioBlob = new Blob(audioChunks, { type: "audio/wav" });
        const formData = new FormData();
        formData.append("file", audioBlob, "recording.wav");
        formData.append("language_code", "hi-IN");

        try {
          const res = await api.assistant.stt(formData);
          if (res && res.text) {
            document.getElementById("chat-input").value = res.text;
            handleSendMessage();
          } else {
            alert(res.message || "STT requires SARVAM_API_KEY.");
          }
        } catch (err) {
          alert("STT recording upload failed: " + err.message);
        }
      };

      mediaRecorder.start();
      isRecording = true;
      micBtn.classList.add("recording");
      micBtn.innerHTML = "⏹️";
    } catch (err) {
      alert("Microphone permission denied or device not found.");
    }
  } else {
    if (mediaRecorder && mediaRecorder.state !== "inactive") {
      mediaRecorder.stop();
    }
    isRecording = false;
    micBtn.classList.remove("recording");
    micBtn.innerHTML = "🎙️";
  }
}

function formatMarkdownLike(str) {
  if (!str) return "";
  return str
    .replace(/\n\n/g, "<br><br>")
    .replace(/\n/g, "<br>")
    .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.*?)\*/g, "<em>$1</em>")
    .replace(/•/g, "&bull;");
}
