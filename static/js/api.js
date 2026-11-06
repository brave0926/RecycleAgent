// Talks to the server. Both functions throw on a network error or any non-200 response.

// lang is "auto" or a language code picked with the header button.
export async function sendChat(messages, lang) {
  const response = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages, lang }),
  });
  if (!response.ok) throw new Error("HTTP " + response.status);
  return response.json();
}

export async function fetchQuickAnswers() {
  const response = await fetch("/api/quick-answers");
  if (!response.ok) throw new Error("HTTP " + response.status);
  const data = await response.json();
  return data.chips;
}
