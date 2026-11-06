# Progress

## Checklist

| Step | Task | Status | Notes |
|---|---|---|---|
| 1 | Setup | ✅ done | Project skeleton, requirements, `.env.example`, `.gitignore` |
| 2 | Knowledge base | ✅ done | `data/guidelines.md`, byte-identical to the supplied file; PDF extraction removed |
| 3 | Backend | ✅ done | `/api/chat`, `/health`, rate limit, JSON validation, usage logging |
| 4 | Frontend | ✅ done | Clean Chat design; language button updated in 4d. Tested in headless Chromium only; real phones are Step 5 |
| 4c | Restructure | ✅ done | Layered `app/`, split JS, tests and docs. System prompt identical to before |
| 4d | Answer language fix | ✅ done | Auto-detect plus button (Auto/EN/KO), language instruction, prepared chip answers in `data/quick_answers.json`. Russian and Uzbek were built, then removed on request |
| 4e | Answer cleanup | ✅ done | Assistant messages no longer cut, `max_retries=0`, app name stays in Korean, one label format |
| 4f | Invalid output and pinned versions | ✅ done | Repair, one retry, then friendly error; never raw JSON. `requirements.txt` pinned to `.venv` versions |
| 4g | Final fixes | ✅ done | `item` optional, category rule in the prompt, final event-day checklist |
| 5 | Testing on phones | ⬜ todo | iPhone and Android: keyboard, Korean typing, safe area, fonts |
| 6 | Deploy | ✅ done | Live at https://recycleagent.onrender.com. `/health`, the page, chips, and one English and one Korean chat question all work |
| 7 | QR + poster | ✅ done | `scripts/make_qr.py` makes `qr.png`, `qr_poster.png` and `qr_poster.pdf`. All three decode to the live URL by software; not yet scanned from a real print |
| 8 | Event-day checklist | ⬜ todo | See the checklist below |

## Event-day checklist (Step 8)

- [ ] UptimeRobot pings /health every 5 min
- [ ] Gemini billing linked (or OpenAI set) + budget alert
- [ ] Open the site 10 min before start
- [ ] Phone test on mobile data: chip, English, Korean question
- [ ] Check aistudio.google.com/usage during the day
- [ ] No git push during busy hours

## Decisions log

| Date | Decision | Reason |
|---|---|---|
| 2026-11-06 | No RAG; whole knowledge base in the system prompt | It fits in one prompt, and the build time was about 2 hours |
| 2026-11-06 | Knowledge base first, rules after, nothing per-request | Lets providers cache the matching start of the prompt |
| 2026-11-06 | Gemini for development, OpenAI for the event | Both use the same code; only `.env` changes |
| 2026-11-06 | `AsyncOpenAI` client | Slow replies don't block other visitors |
| 2026-11-06 | 30-second timeout | Visitors shouldn't wait minutes |
| 2026-11-06 | Lenient `category` (any text) | One unexpected value shouldn't discard a good answer and show raw JSON |
| 2026-11-06 | Default language state is Auto, replacing Korean-first | Answers must match the language of the latest question |
| 2026-11-06 | `lang` on `/api/chat`: `auto` (default), `en`, `ko`; button choice wins over detection | Lets visitors force a language; the system prompt stays fixed |
| 2026-11-06 | Language instruction sent as a final `user` message, not `system` | On Gemini a second system message drops the knowledge base (prompt tokens fell from about 25,500 to 79) |
| 2026-11-06 | Korean and English only; other languages fall back to English | Requested: two languages are enough |
| 2026-11-06 | Prepared chip answers in English and Korean | Instant answers with no token cost |
| 2026-11-06 | Only user messages are cut to 500 characters; last 8 messages kept | Cutting stored answers broke their JSON in follow-ups |
| 2026-11-06 | `max_retries=0` | A failed request reaches the visitor within 30 seconds instead of about 90 |
| 2026-11-06 | Labels are `<name> (<Korean term>)`; Korean answers use only the Korean term; app name stays in Korean | Requested: no repeated terms, and visitors can search for the app |
| 2026-11-06 | `RATE_LIMIT` default raised to 200 per IP per hour | Event visitors share the venue Wi-Fi IP |
| 2026-11-06 | Render free web service, defined in `render.yaml`, with secrets entered on Render | Simple deploy; the API key never enters the repo |
| 2026-11-06 | Invalid model output: repair, retry once, then friendly error | Visitors must never see raw JSON; repairs cost nothing, and a retry costs tokens only when needed |
| 2026-11-06 | `requirements.txt` pinned to exact `.venv` versions, including indirect packages | Render installs what was tested |
| 2026-11-06 | QR uses level H; on the poster the black pattern is about 800 px, plus its white border | Scans from further away and survives damage to the print |
| 2026-11-06 | `item` is optional (default empty) | The model often left it out, which caused needless errors for visitors |
| 2026-11-06 | Category must match the bin where the item goes | Eggshells were labeled food waste while the text said not to put them there |
| 2026-11-06 | Poster says "AI Recycling Guide Lab" (the event booth name); the app name stays as it is | Booth name is for the poster only |
| 2026-11-06 | New `localStorage` key for the language state | An old saved `ko` would otherwise force Korean answers |
| 2026-11-06 | Layered `app/` structure | Requested in Step 4c; no behavior change |

## Known issues / risks

- **Model availability:** `gemini-2.5-flash-lite` returned 404 even though it is listed for the key, so `.env` now uses `gemini-3.5-flash-lite`. Test the event model the same way before the event.
- **Advice accuracy is unchecked:** real answers were checked for format and language only, not against the guideline.
- **Switch to OpenAI is untested:** the event plan uses OpenAI, but real tests so far used Gemini.
- **No length limit on assistant messages:** a client could send very long fake ones to raise token costs. A spending cap is the backstop.
- **No retries:** a brief API hiccup now shows the error reply straight away, and the visitor has to send again.
- **Shared Wi-Fi:** visitors on one public IP share the 200-per-hour limit. One IP at the limit can use about 5 million prompt tokens per hour, so set a spending cap.
- **Render free plan:** the service sleeps when idle, so the first visitor after a quiet period waits. Restarts reset the rate limit count.
- **Pinned versions on Windows:** the pinned install was tested on Linux only.
- **Rate limit weaknesses:** `X-Forwarded-For` can be faked; the count is in memory and for a single worker. Set a spending cap.
- **Out of credit looks like "too many questions":** check the balance before the event.
- **Cost:** about 25,500 prompt tokens per question; caching isn't confirmed.
- **Gemini 429 under load:** after about 10 real questions in under a minute, Gemini returned 429 on the current key. Each question sends about 25,500 tokens, so a busy booth could hit this. The likely cause is a token-per-minute quota, but the log doesn't show the reason. Link billing and check the quota before the event.
- **Gemini 503:** one request in about 20 failed with 503. With retries off, the visitor sees the error reply.
- **Label format relies on the model:** the instruction sets it, but nothing on the server enforces it.
- **Translations unreviewed:** Korean page text and Korean prepared answers need a native speaker's check.
- **Prepared answers unreviewed:** written by Claude from the knowledge base, so check them against the guideline before the event. Don't edit them without keeping `en` and `ko` in step.
- **Mixed-language questions:** any Hangul means Korean, so `How do I throw away 종량제봉투?` gets a Korean answer in Auto.
- **Instruction role on OpenAI:** the final `user` message is tested on Gemini only.
- **Not tested on real phones:** keyboard behavior and real Korean typing are unverified.

## Next action

Test on real phones (Step 5), including scanning a printed poster.
