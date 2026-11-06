// Everything that draws in the chat area. Text always goes through textContent,
// never innerHTML, so user or AI text cannot inject HTML into the page.

// Categories with their own color in css/style.css. Anything else keeps the default.
const KNOWN_CATEGORIES = new Set([
  "plastic", "paper", "papercup", "glass", "can",
  "vinyl", "styrofoam", "food", "general", "special",
]);

const messagesEl = document.getElementById("messages");

export function el(tag, className, text) {
  const node = document.createElement(tag);
  node.className = className;
  if (text) node.textContent = text;
  return node;
}

export function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

export function addBubble(node) {
  messagesEl.appendChild(node);
  scrollToBottom();
  return node;
}

export function addAssistantText(text) {
  return addBubble(el("div", "bubble assistant", text));
}

// With parts this is the answer card; without parts the same code gives a normal
// bubble (reply, plus tip and source if present).
export function addAnswer(data, sourcePrefix) {
  const bubble = el("div", "bubble assistant");
  bubble.appendChild(el("div", "reply", data.reply));

  const parts = Array.isArray(data.parts) ? data.parts : [];
  parts.forEach((part) => {
    const row = el("div", "part");
    const colorClass = KNOWN_CATEGORIES.has(part.category) ? " cat-" + part.category : "";
    row.appendChild(el("span", "part-label" + colorClass, part.label));
    row.appendChild(el("span", "part-text", part.item + " — " + part.action));
    bubble.appendChild(row);
  });

  if (data.tip) bubble.appendChild(el("div", "tip", data.tip));
  if (data.source) bubble.appendChild(el("div", "source", sourcePrefix + data.source));

  addBubble(bubble);
}

export function addTyping(label) {
  const bubble = el("div", "bubble assistant typing");
  bubble.setAttribute("aria-label", label);
  for (let i = 0; i < 3; i++) bubble.appendChild(document.createElement("span"));
  return addBubble(bubble);
}
