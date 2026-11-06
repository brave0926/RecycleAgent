# Architecture

## 1. Overview

**Goal:** help people at an event in Korea sort and dispose of household waste correctly.

**Users:** event visitors, mostly on phones, who scan a QR code. No login or install. The app supports Korean and English. Answers follow the language of the latest question, or the language picked with the header button.

**Summary:** one FastAPI app serves a static HTML/CSS/JS page and one endpoint, `POST /api/chat`. The browser keeps the chat history and sends it with each request, so the server stores nothing. The server places the whole knowledge base in the system prompt, adds a short language instruction after the history, calls an OpenAI-compatible model in JSON mode, validates the answer and returns it. The page draws it as an answer card. Quick chips show prepared answers without calling the model. There is no database, no login and no RAG.

## 2. Architecture diagram

```
 Phone / Laptop
      │  scan QR, open page
      ▼
 Static frontend (static/)
      │  POST /api/chat  { messages, lang }
      ▼
 FastAPI route (app/api/routes/chat.py)
      │  language.py: button choice, or detect from the latest question
      ▼
 Rate limiter (app/services/rate_limiter.py) ──over limit──► friendly reply
      │  allowed
      ▼
 llm_service (app/services/llm_service.py)
      │  system prompt (knowledge base + rules) + last 8 messages + language instruction
      ▼
 OpenAI or Gemini (OpenAI-compatible API)
      │  JSON text
      ▼
 llm_service: repair and validate ──invalid──► retry once ──invalid again──► friendly reply
      │  ChatResponse
      ▼
 Answer card in the browser
```

## 3. Layers

| Layer | Folder | Responsibility | Depends on |
|---|---|---|---|
| App entry | `app/main.py` | Create the app, connect routers, mount static files, startup logging | routes, core |
| Routes | `app/api/routes/` | Receive requests and return responses; no business logic | deps, schemas, services, core (paths) |
| Dependencies | `app/api/deps.py` | Find the client IP | FastAPI |
| Services | `app/services/` | Prompt building, language choice, model call, parsing, error mapping, rate limit, prepared answers; no FastAPI imports | core, schemas, prompts |
| Prompts | `app/prompts/` | Fixed output rules text | nothing |
| Schemas | `app/schemas/` | Request and response shapes | Pydantic |
| Core | `app/core/` | Settings (the only place that reads env vars), logging setup | python-dotenv |
| Data | `data/` | Knowledge base and prepared chip answers | nothing |
| Frontend | `static/` | Page, styles, chat logic | `/api/chat` |
| Scripts | `scripts/` | Knowledge base check; QR generator (`make_qr.py`, still empty until Step 7) | `data/` |
| Tests | `tests/` | API tests with a mocked model call | app |

## 4. Request flow

1. The visitor types a question or taps a chip.
2. `app.js` adds the question to `messages[]`, shows it and shows the typing indicator.
3. `api.js` sends `{ messages, lang }` to `POST /api/chat`.
4. FastAPI validates the body against `ChatRequest`. An invalid body gets a 422.
5. `get_client_ip` takes the first `X-Forwarded-For` entry, or the connection IP if there is none.
6. `resolve_language` uses the button choice, or detects the language of the latest user message when `lang` is `auto`.
7. `limiter.check(ip)` counts the request. Over the limit, the route returns a friendly reply and the model is not called.
8. `llm_service.ask` keeps the last 8 messages and cuts each user message to 500 characters. Stored assistant answers are not cut, so they stay valid JSON.
9. It calls the model with the system prompt, the history, a final language instruction, `temperature=0.2` and JSON mode.
10. It logs token usage (prompt, completion, and cached when reported).
11. It parses the first `{...}` block in the output, which also handles ```` ```json ```` fences and text around the JSON, then validates it. If that fails, it sends the same request once more. If the second answer is invalid too, it returns the friendly error reply. Raw model output is never shown to a visitor.
12. API errors become a friendly reply, and the real error goes to the log.
13. `render.js` draws the answer, and `app.js` stores it in `messages[]` as a JSON string.

**Quick chips** skip steps 3–12: `app.js` shows the prepared answer from `/api/quick-answers` and adds it to `messages[]`.

**Label format:** `<name in answer language> (<Korean term>)`, for example `Plastic (플라스틱)`. Korean answers use just the Korean term. The app name 내 손안의 분리배출 always stays in Korean letters.

**Language instruction:** it is sent as a final message with the `user` role, not `system`. On Gemini's OpenAI-compatible API a second system message replaces the first, which silently drops the knowledge base (measured: prompt tokens fell from about 25,500 to 79, and answers were invented). `tests/test_api.py` checks that there is exactly one system message.

## 5. API contract

| Method | Path | Purpose | Response |
|---|---|---|---|
| GET | `/` | Chat page | HTML |
| GET | `/static/...` | CSS and JS | File |
| GET | `/health` | Health check | `{"ok": true}` |
| POST | `/api/chat` | Ask a question | `ChatResponse` |
| GET | `/api/quick-answers` | Chip labels and prepared answers (`en`, `ko`) | `{"chips": [...]}` |
| GET | `/docs` | Swagger UI | HTML |

**Request:**

```json
{
  "messages": [
    { "role": "user", "content": "takeout coffee cup with a plastic lid" }
  ],
  "lang": "auto"
}
```

- `role` is `user` or `assistant`.
- `lang` is `auto`, `en` or `ko`, and defaults to `auto`. It sets the language of both the AI answer and the server's fixed replies.
- With `auto`, the latest user message decides: any Hangul → `ko`; anything else → `en`.

**Response:**

```json
{
  "reply": "Separate the cup and the lid.",
  "parts": [
    {
      "label": "Paper cup (종이컵)",
      "category": "papercup",
      "item": "Cup",
      "action": "Empty, rinse and put out with paper cups."
    },
    {
      "label": "Plastic (플라스틱)",
      "category": "plastic",
      "item": "Lid",
      "action": "Rinse and put in the plastic bin."
    }
  ],
  "tip": "Local rules differ — check the 구청 or the app 내 손안의 분리배출.",
  "source": "Part A – 바. 합성수지 용기·트레이류 (별표 1, 2026)"
}
```

**Error behavior:** everything except an invalid request returns HTTP 200 with the same JSON shape, with `parts: []`, `tip: ""` and `source: ""`.

| Situation | HTTP | `reply` (shown in English; sent in the resolved language) |
|---|---|---|
| Rate limit in this app | 200 | "You've asked a lot of questions — thank you! Please try again a little later." |
| Model API returns 429 | 200 | "Too many questions right now — please try again in a minute." |
| Any other API error | 200 | "Sorry, something went wrong. Please try again." |
| Model output is invalid twice | 200 | "Sorry, something went wrong. Please try again." |
| `messages` is empty, or `role` or `lang` is invalid | 422 | FastAPI validation error |

A message with empty `content` is accepted by the API. The page blocks blank input before sending.

## 6. Knowledge base

- **Source file:** `data/guidelines.md`, about 39,500 characters. It was supplied already cleaned and is stored unchanged.
- **Structure:**
  - Part 0: AI rules, sources and known differences from older editions
  - Part A: official item list (별표 1, in force 2026-01-01)
  - Part B: summary of the guideline text
  - Part C: older guideline, details by category
  - Part D: item dictionary
  - Part E: FAQ from the app 내 손안의 분리배출
  - Part F: fines (older source, must be verified)
- **Source priority:** Part A > Part B > Parts C–F. An item that isn't listed gets a material-based guess that is clearly marked.
- **Why no RAG:** the whole file fits in one prompt, so search would add a vector store and retrieval errors for no gain. The project also had about 2 hours to build.
- **Caching note:** the knowledge base comes first and the prompt never changes per request (the language instruction goes after the history), so providers that cache matching prompt starts can reuse it. Measured size is about 25,500 prompt tokens per question on Gemini, where the logs show `cached=n/a`. Check `cached` again when using OpenAI.

## 7. Frontend

**Files:**

| File | Role |
|---|---|
| `static/index.html` | Page structure |
| `static/css/style.css` | Styles and breakpoints |
| `static/js/api.js` | `sendChat(messages, lang)` and `fetchQuickAnswers()`; both throw on a network error or non-200 response |
| `static/js/render.js` | Bubbles, answer card, typing indicator, category check |
| `static/js/app.js` | State, page text, language button, chips, events, wiring |

**State:** `messages[]` holds the history in memory, so a reload starts a new chat. The intro message is local and is never sent. The language state is kept in `localStorage` under `recycle-lang-state`. The old `recycle-lang` key is ignored on purpose, because a saved `ko` would now force Korean answers.

**Language button:** cycles Auto → EN → KO and shows the current state. The default is Auto.

| Button | Answers typed by the visitor | Page text | Chips |
|---|---|---|---|
| Auto | Language of the question | Korean if `navigator.language` starts with `ko`, else English | Prepared answer in the page language |
| EN | English | English | Prepared English answer |
| KO | Korean | Korean | Prepared Korean answer |

**Rendering:** all user and AI text goes through `textContent`, never `innerHTML`. A failed request removes the question from `messages[]` so it can be sent again.

**Responsive breakpoints (CSS only):**

| Width | Layout |
|---|---|
| Under 600px | Full-screen chat |
| 600px and up | Centered card, up to 760px wide |
| 1100px and up | Side panel (280px) + chat, up to 1100px wide; the chips row is hidden |

**Category colors:**

| Category | Background | Text |
|---|---|---|
| `plastic` | `#DBEAFE` | `#1E40AF` |
| `paper` | `#E5E7EB` | `#374151` |
| `papercup` | `#FEF3C7` | `#92400E` |
| `glass` | `#CCFBF1` | `#115E59` |
| `can` | `#E0E7FF` | `#3730A3` |
| `vinyl` | `#F3E8FF` | `#6B21A8` |
| `styrofoam` | `#F1F5F9` | `#334155` |
| `food` | `#DCFCE7` | `#166534` |
| `general` | `#FEE2E2` | `#991B1B` |
| `special` | `#FFEDD5` | `#9A3412` |
| Any other value | `#F3F4F6` | `#374151` |

## 8. Configuration

Read once by `app/core/config.py`. An empty value uses the default.

| Variable | Default | Meaning |
|---|---|---|
| `OPENAI_API_KEY` | none | API key. Without it the app starts, but `/api/chat` returns the error reply |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model name |
| `OPENAI_BASE_URL` | OpenAI | API address. For Gemini: `https://generativelanguage.googleapis.com/v1beta/openai/` |
| `OPENAI_TIMEOUT` | `30` | Seconds before one model request gives up. SDK retries are off (`max_retries=0`), and API errors aren't retried. Only an invalid answer triggers a second request, so the worst case is about twice this |
| `RATE_LIMIT` | `200` | Requests allowed per IP per window |
| `RATE_WINDOW` | `3600` | Window length in seconds |
| `MAX_HISTORY` | `8` | Most recent messages kept from each request |
| `MAX_MSG_CHARS` | `500` | Characters kept from each user message; assistant messages are not cut |

## 9. Security and limits

- **API key:** stays on the server in `.env`, which is in `.gitignore`. It never reaches the browser.
- **Client input:** clients can only send `user` and `assistant` roles, so they can't add their own system message. They can still write fake assistant messages, and off-topic refusal relies on the model following its rules. Assistant messages have no length limit, so a client could send very long ones to raise token costs.
- **Output:** the page renders text only, so model output can't inject HTML.
- **Rate limit:** 200 requests per IP per hour by default, with these known weaknesses:
  - **Shared Wi-Fi:** visitors on one public IP share one limit, which is why the default is 200. A busy venue could still reach it, so raise `RATE_LIMIT` if needed.
  - **Spoofable header:** a client can fake `X-Forwarded-For` to get around the limit.
  - **In-memory, single worker:** the count resets on restart and isn't shared between workers, so run one worker.
- **Spending cap:** the rate limit doesn't protect the budget against abuse, so set a spending cap in the provider account. Each model question costs about 25,500 prompt tokens, so one IP at the limit can use about 5 million prompt tokens per hour.
- **Out of credit:** this also returns 429, so visitors see "Too many questions". The log shows the real reason.

## 10. Deployment

**Render (main plan):** defined in `render.yaml`. See `README.md` for the steps.

- Plan: free web service, Python 3.12.3
- Build command: `pip install -r requirements.txt`
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check path: `/health`
- `OPENAI_API_KEY`, `OPENAI_MODEL` and `OPENAI_BASE_URL` are set in Render (`sync: false`), never in the repo.
- The free plan sleeps when idle, so open the page before the event. A restart also resets the rate limit count.

**ngrok (fallback):** run the app on a laptop and expose it:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
ngrok http 8080
```

The laptop must stay on and connected. The QR code must point to the ngrok address, which may change between runs, so make the final QR code only after choosing the address.

## 11. Future work

- RAG with pgvector, if the knowledge base grows too large for one prompt
- Camera and image input (the button is already there, disabled)
- More languages
- Feedback logging
- Analytics
