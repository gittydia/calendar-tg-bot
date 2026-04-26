# Calendar Commander

Personal Telegram bot for Google Calendar, built with FastAPI + python-telegram-bot in webhook mode.

## Features

- `/start` and `/help` onboarding commands
- `/today` for today's events (Asia/Manila timezone)
- `/events` for the next 10 upcoming events
- `/create_event` using natural language date parsing (default duration: 1 hour)
- `/delete_event` by selecting indexed upcoming events
- Fully async bot/webhook runtime

## Project Structure

```text
calendar-commander/
|
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── application.py
│   │   ├── handlers.py
│   │   └── commands.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── calendar_service.py
│   │   └── parser_service.py
│   └── utils/
│       ├── __init__.py
│       └── formatters.py
│
├── credentials.json
├── token.json
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Prerequisites

- Python 3.11+
- Telegram bot token from BotFather
- Google account and Google Cloud project

## Local Setup

1. Create virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. Copy env template and fill values:

   ```bash
   copy .env.example .env
   ```

3. Update `.env` with:

   - `BOT_TOKEN`
   - `WEBHOOK_URL` (public HTTPS URL)
   - Optional timezone override (`TIMEZONE`)

4. Add your real Google OAuth credentials to `credentials.json`.

## Google Cloud Setup

### 1. Enable Google Calendar API

1. Go to Google Cloud Console → APIs & Services → Library
2. Search "Google Calendar API"
3. Click Enable

### 2. Create OAuth Credentials (Web Application)

1. Go to APIs & Services → Credentials
2. Click Create Credentials → OAuth client ID
3. Select **Web application** (NOT Desktop app)
4. Add authorized redirect URIs:
   - `http://localhost:9999/`
5. Click Create
6. Download JSON and save as `credentials.json`

### 3. Configure OAuth Consent Screen

1. Go to APIs & Services → OAuth consent screen
2. If using "Testing" mode, add your email as a Test User
3. Or publish the app (requires Google verification for production)

## Local Run (With OAuth)

1. Run without webhook first to complete OAuth:

   ```bash
   $env:WEBHOOK_URL=""
   uvicorn app.main:app --host 127.0.0.1 --port 8080
   ```

2. Open `http://localhost:8080/` in browser
3. Complete OAuth flow in browser
4. `token.json` will be created automatically

## Run with Ngrok/Production

1. Start ngrok:

   ```bash
   ngrok http 8080
   ```

2. Update `.env` with your ngrok URL:

   ```
   WEBHOOK_URL=https://your-ngrok-url.ngrok-free.dev/
   ```

3. Run the app:

   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8080
   ```

## Render Deployment

1. Push repository to GitHub.
2. Create a new **Web Service** in Render.
3. Configure:
   - **Runtime:** Python
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add environment variables in Render:
   - `BOT_TOKEN`
   - `WEBHOOK_URL` (your Render service URL, e.g. `https://your-app.onrender.com`)
   - Optional `TIMEZONE`
5. Upload/provide `credentials.json` and `token.json` securely for runtime.

## Common Issues

### redirect_uri_mismatch
- The redirect URI in the OAuth request doesn't match your configured URIs
- Go to Google Cloud Console → APIs & Services → Credentials → Your OAuth Client
- Add the exact redirect URI (e.g., `http://localhost:9999/`) to "Authorized redirect URIs"

### access_denied
- OAuth consent screen not configured
- Go to APIs & Services → OAuth consent screen
- Add your email as Test User if in "Testing" mode

### accessNotConfigured
- Google Calendar API is disabled
- Go to APIs & Services → Library
- Enable Google Calendar API

## Notes for Production

- Never hardcode secrets.
- Keep `credentials.json`, `token.json`, and `.env` out of source control.
- The architecture is service-oriented and can be extended for multi-user token storage later (e.g., DB-backed user credential store).