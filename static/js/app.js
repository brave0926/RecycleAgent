// Page state, events and wiring. Drawing is in render.js, the server call in api.js.
import { fetchQuickAnswers, sendChat } from "./api.js";
import { addAnswer, addAssistantText, addBubble, addTyping, el, scrollToBottom } from "./render.js";

// All page text, in Korean and English.
const TEXT = {
  ko: {
    title: "AI 분리배출 가이드",
    subtitle: "분리배출 도우미 · 환경부 공식 지침 기반",
    howItWorks: "이용 방법",
    step1: "품목을 입력하거나 눌러 보세요",
    step2: "분리배출 방법을 확인하세요",
    step3: "출처를 확인하세요",
    quickQuestions: "자주 묻는 품목",
    today: "오늘",
    note: "AI는 실수할 수 있어요. 지역별 배출 규칙을 꼭 확인하세요.",
    placeholder: "버릴 물건을 물어보세요…",
    send: "보내기",
    cameraTitle: "준비 중",
    cameraLabel: "카메라 (준비 중)",
    thinking: "답변 작성 중",
    intro: "안녕하세요! 버리려는 물건을 알려 주시면 올바른 분리배출 방법을 안내해 드릴게요.",
    connectionError: "연결에 문제가 있어요. 다시 시도해 주세요.",
    source: "출처: ",
    languageLabel: "언어: ",
  },
  en: {
    title: "AI Recycling Guide",
    subtitle: "분리배출 도우미 · Official Korean guidelines",
    howItWorks: "How it works",
    step1: "Type or tap an item",
    step2: "Get sorting steps",
    step3: "Check the source",
    quickQuestions: "Quick questions",
    today: "Today",
    note: "AI can make mistakes — check local rules.",
    placeholder: "Ask about any item…",
    send: "Send",
    cameraTitle: "Coming soon",
    cameraLabel: "Camera (coming soon)",
    thinking: "Thinking",
    intro: "Hi! Tell me what you want to throw away, and I'll show you how to sort it the right way.",
    connectionError: "Connection problem — please try again.",
    source: "Source: ",
    languageLabel: "Language: ",
  },
};

// Header button order. "auto" answers in the language of the latest question.
const LANG_STATES = ["auto", "en", "ko"];
const LANG_LABELS = { auto: "Auto", en: "EN", ko: "KO" };

// A new key on purpose: the old "recycle-lang" could hold "ko" from the earlier toggle,
// which would now count as an explicit choice and force Korean answers.
const LANG_KEY = "recycle-lang-state";

const inputEl = document.getElementById("input");
const sendBtn = document.getElementById("send");
const langBtn = document.getElementById("lang");
const cameraBtn = document.getElementById("camera");
const isDesktop = window.matchMedia("(pointer: fine)").matches;

const messages = []; // Sent to the server with every request; the server keeps nothing.
let waiting = false;
let lang = loadLang();
let introBubble = null;
let quickChips = [];

// localStorage can throw in private browsing, so fall back to the default.
function loadLang() {
  try {
    const saved = localStorage.getItem(LANG_KEY);
    return LANG_STATES.includes(saved) ? saved : "auto";
  } catch (error) {
    return "auto";
  }
}

// Language of the page text and prepared answers. Auto follows the browser language.
function uiLanguage() {
  if (lang !== "auto") return lang;
  return (navigator.language || "").toLowerCase().startsWith("ko") ? "ko" : "en";
}

function saveLang() {
  try {
    localStorage.setItem(LANG_KEY, lang);
  } catch (error) {
    // Not saved: the page still works in the chosen language until reload.
  }
}

function setWaiting(value) {
  waiting = value;
  sendBtn.disabled = value;
  document.querySelectorAll(".chip").forEach((chip) => {
    chip.disabled = value;
  });
}

async function send(text) {
  const question = text.trim();
  if (!question || waiting) return false;

  addBubble(el("div", "bubble user", question));
  messages.push({ role: "user", content: question });

  setWaiting(true);
  const typing = addTyping(TEXT[uiLanguage()].thinking);

  try {
    const data = await sendChat(messages, lang);
    typing.remove();
    addAnswer(data, TEXT[uiLanguage()].source);
    messages.push({ role: "assistant", content: JSON.stringify(data) });
  } catch (error) {
    console.error(error);
    typing.remove();
    addAssistantText(TEXT[uiLanguage()].connectionError);
    messages.pop(); // Forget the failed question so it can be sent again.
  }

  setWaiting(false);
  if (isDesktop) inputEl.focus();
  return true;
}

// Shows the prepared answer without calling the model.
function tapChip(chip) {
  if (waiting) return;
  const ui = uiLanguage();
  const label = chip.label[ui];
  const answer = chip.answer[ui];
  addBubble(el("div", "bubble user", label));
  addAnswer(answer, TEXT[ui].source);
  messages.push({ role: "user", content: label });
  messages.push({ role: "assistant", content: JSON.stringify(answer) });
  if (isDesktop) inputEl.focus();
}

function renderChips() {
  const ui = uiLanguage();
  document.querySelectorAll("[data-chips]").forEach((container) => {
    container.textContent = "";
    quickChips.forEach((chip) => {
      const button = el("button", "chip", chip.label[ui]);
      button.type = "button";
      button.disabled = waiting;
      button.addEventListener("click", () => tapChip(chip));
      container.appendChild(button);
    });
  });
}

function resizeInput() {
  inputEl.style.height = "auto";
  // scrollHeight leaves out the border, so add it back (1px top + 1px bottom).
  const wanted = inputEl.scrollHeight + 2;
  const maxHeight = parseInt(getComputedStyle(inputEl).maxHeight, 10);
  inputEl.style.height = Math.min(wanted, maxHeight) + "px";
  inputEl.style.overflowY = wanted > maxHeight ? "auto" : "hidden";
}

function sendFromInput() {
  if (waiting || !inputEl.value.trim()) return;
  send(inputEl.value);
  inputEl.value = "";
  resizeInput();
}

// Applies the current language to all page text. Past messages stay as they are,
// except the intro, which has not been part of the conversation.
function applyLanguage() {
  const ui = uiLanguage();
  const text = TEXT[ui];
  document.documentElement.lang = ui;
  document.title = text.title;

  document.querySelectorAll("[data-i18n]").forEach((node) => {
    node.textContent = text[node.dataset.i18n];
  });

  inputEl.placeholder = text.placeholder;
  inputEl.setAttribute("aria-label", text.placeholder);
  sendBtn.setAttribute("aria-label", text.send);
  cameraBtn.title = text.cameraTitle;
  cameraBtn.setAttribute("aria-label", text.cameraLabel);
  langBtn.textContent = LANG_LABELS[lang];
  langBtn.setAttribute("aria-label", text.languageLabel + LANG_LABELS[lang]);
  renderChips();

  if (introBubble) introBubble.textContent = text.intro;
}

// --- Events ---
sendBtn.addEventListener("click", sendFromInput);
langBtn.addEventListener("click", () => {
  lang = LANG_STATES[(LANG_STATES.indexOf(lang) + 1) % LANG_STATES.length];
  saveLang();
  applyLanguage();
});
inputEl.addEventListener("input", resizeInput);

inputEl.addEventListener("keydown", (event) => {
  // While a Korean IME is composing, Enter only finishes the syllable, so it must
  // not send. Without this check the last character gets sent a second time.
  if (event.isComposing || event.keyCode === 229) return;
  if (event.key === "Enter" && !event.shiftKey) {
    event.preventDefault();
    sendFromInput();
  }
});

// Phone keyboard opening or closing: keep the latest message visible.
if (window.visualViewport) {
  window.visualViewport.addEventListener("resize", scrollToBottom);
}

// --- Start ---
introBubble = addAssistantText(TEXT[uiLanguage()].intro); // Local only: never added to messages.
applyLanguage();

fetchQuickAnswers()
  .then((chips) => {
    quickChips = chips;
    renderChips();
  })
  .catch((error) => console.error(error)); // The chat still works without chips.

if (isDesktop) inputEl.focus();
