# AI Recycling Guide (AI 분리배출 가이드)

Visitors scan a QR code at an event, a mobile page opens, and they chat with an AI in Korean or English about how to sort household waste under Korea's official guidelines.

## Run locally

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env             # Windows: copy .env.example .env
```

Add your API key to `.env`. To use Gemini instead of OpenAI, also set `OPENAI_MODEL` and `OPENAI_BASE_URL` (see `.env.example`). Then start the app:

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8080
```

- Chat page: http://127.0.0.1:8080
- API docs: http://127.0.0.1:8080/docs
- From a phone on the same Wi-Fi: `http://<your-computer-ip>:8080`

## Test

```bash
pytest                       # Mocked model: no API key needed, costs nothing
python scripts/check_kb.py   # Knowledge base size and headings
```

## Deploy on Render

The settings are in `render.yaml`. Your API key is entered on Render and never goes into the repo.

1. Push this project to GitHub.
2. In the [Render dashboard](https://dashboard.render.com), choose **New → Blueprint**.
3. Connect your GitHub account and select the repo. Render reads `render.yaml`.
4. Enter the values Render asks for:

   | Variable | OpenAI | Gemini |
   |---|---|---|
   | `OPENAI_API_KEY` | Your OpenAI key | Your Gemini key |
   | `OPENAI_MODEL` | `gpt-4o-mini` | `gemini-3.5-flash-lite` |
   | `OPENAI_BASE_URL` | Leave empty | `https://generativelanguage.googleapis.com/v1beta/openai/` |

5. Click **Apply** and wait for the deploy to finish.
6. Check the service:
   - `https://<your-service>.onrender.com/health` should show `{"ok":true}`.
   - Open the page and ask one question in Korean and one in English.

To change the rate limit, add `RATE_LIMIT` under the service's **Environment** tab. The default is 200 requests per IP per hour.

**Free plan:** the service goes to sleep when idle, and the first visitor after that waits while it wakes up. Restarts also reset the rate limit count. Open the page shortly before the event, and watch for this during quiet periods.

## ngrok fallback

If Render isn't working, run the app on a laptop and expose it through ngrok:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
ngrok http 8080
```

Use the `https://` address that ngrok prints. The laptop must stay on and connected. The address may change each time ngrok starts, and any QR code must point to the current one.

## QR code and poster

```bash
python scripts/make_qr.py https://recycleagent.onrender.com
```

This creates `qr.png`, `qr_poster.png` and `qr_poster.pdf` (A4) in the project folder. It needs a Korean font found by `fc-list`: Noto Sans CJK KR or NanumGothic. Print the poster at 100% scale, then scan the printed copy with a phone.

## Docs

- [ARCHITECTURE.md](ARCHITECTURE.md): how the app is built
- [PROGRESS.md](PROGRESS.md): status, decisions, known issues
