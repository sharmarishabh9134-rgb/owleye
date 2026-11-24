# OwlEye 🦉 — See through fake internships.

Paste an internship offer (email, WhatsApp, offer letter). OwlEye gives a **risk score with reasons** before you apply or pay, helps you **report scams**, and points you to **genuine internship platforms**.

Team **Night Coders** · Bapuji Institute of Engineering and Technology · wHACKiest 2026

## Features
| Feature | What it does |
|---|---|
| Offer checker | Heuristic signals (fees, personal-mail "HR", urgency, shared-account payments, bad links, domain age, TLS) combined into a 0–100 score: LOW / MEDIUM / HIGH |
| AI assistant | Chat widget for victims and doubters. Uses Claude when `ANTHROPIC_API_KEY` is set, otherwise a basic rule-based helper |
| Report a scam | Builds a paste-ready complaint for **cybercrime.gov.in** / helpline **1930**, with Copy, Open portal, Call, Email and Download buttons |
| Genuine platforms | Curated official and well-known portals (PM Internship Scheme, AICTE, NCS, Internshala, LinkedIn, Unstop, ...) plus keyword search links |

**Honest limits:** OwlEye cannot file on the government portal for you (it needs your own login and OTP, and there is no public API). It prepares everything and hands off. Platform list is curated links, not a live feed. Scores are estimates, not proof.

## Run on Windows
1. Install Python 3.10+ from python.org (tick "Add to PATH").
2. Double-click `run_windows.bat`, or in a terminal:
```
py -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python -m uvicorn backend.app.main:app --port 8000
```
3. Open http://localhost:8000

## Run on Mac / Linux
```
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn backend.app.main:app --port 8000
```

## Settings (environment variables)
- `ANTHROPIC_API_KEY` — turn on the AI chat (optional)
- `OWLEYE_MODEL` — model for chat (default `claude-haiku-5-5`)
- `OWLEYE_REPORT_EMAIL` — address for the "Email it" button (e.g. your college cyber cell)
- `OWLEYE_OFFLINE=1` — skip live domain/TLS lookups

Windows example: `set ANTHROPIC_API_KEY=your-key` then run the bat file.

## Tests
```
pip install -r requirements-dev.txt
pytest -q
```

## API
`POST /api/analyze` · `POST /api/chat` · `POST /api/complaint` · `GET /api/platforms` · `GET /api/health` (docs at `/docs`)

Chat is rate-limited to 20 messages/min per IP (behind a proxy, configure forwarded IPs). Nothing is stored.

Pitch deck: `docs/NightCoders_OwlEye_Pitch.pptx` · License: MIT
