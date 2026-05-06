# Calendar Commander

Multi-user Telegram bot for Google Calendar, built with FastAPI + python-telegram-bot in webhook mode. Supports unlimited users connecting their own Google accounts via OAuth.

## Features

- Multi-user Google Calendar support via per-user SQLite token storage
- `/connect` — Link your Google Calendar with one click
- `/disconnect` — Unlink your Google Calendar
- `/today` — Show today's events (configurable timezone)
- `/events` — Show next 10 upcoming events
- `/create_event` — Create events using natural language parsing
- `/delete_event` — Delete events by index
- Web-based OAuth flow with automatic Telegram notification on success
- Automatic webhook retry and health check support for cloud deployment

## Project Structure

```text
calendar-commander/
|
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI entrypoint, OAuth routes, webhook
│   ├── config.py            # Environment variable configuration
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── application.py   # Telegram app factory
│   │   ├── handlers.py      # Per-user command handlers
│   │   └── commands.py      # Bot command definitions
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py  # Per-user Google OAuth
│   │   ├── calendar_service.py  # Google Calendar operations
│   │   ├── parser_service.py    # Natural language date parsing
│   │   └── token_store.py       # SQLite token persistence
│   └── utils/
│       ├── __init__.py
│       └── formatters.py
│
├── credentials.json           # Google OAuth client config (never commit)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── .gitignore
└── README.md
```

## Prerequisites

- Python 3.11+
- Telegram bot token from BotFather
- Google Cloud project with Google Calendar API enabled

## Google Cloud Setup

### 1. Enable Google Calendar API
1. Go to Google Cloud Console → APIs & Services → Library
2. Search "Google Calendar API" → Click Enable

### 2. Create OAuth Credentials (Web Application)
1. Go to APIs & Services → Credentials → Create Credentials → OAuth client ID
2. Select **Web application** (NOT Desktop app)
3. Add authorized redirect URIs:
   - `http://localhost:9999/` (for local testing)
   - `https://your-domain.com/oauth/callback` (for production)
4. Download JSON and save as `credentials.json`

### 3. Configure OAuth Consent Screen
1. Go to APIs & Services → OAuth consent screen
2. If "Testing" mode, add your email as a Test User
3. Publish for production (requires Google verification if external users)

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

3. Update `.env`:

   | Variable | Description |
   |---|---|
   | `BOT_TOKEN` | Telegram bot token from BotFather |
   | `WEBHOOK_URL` | Public HTTPS URL (e.g., ngrok or production URL) |
   | `BASE_URL` | Same as `WEBHOOK_URL` (used for OAuth redirects) |
   | `GOOGLE_CREDENTIALS_JSON` | Paste entire `credentials.json` content here (optional) |
   | `GOOGLE_CREDENTIALS_FILE` | Path to `credentials.json` (default: `credentials.json`) |
   | `TIMEZONE` | User timezone (default: `Asia/Manila`) |
   | `DB_PATH` | SQLite database path (default: `tokens.db`) |

4. Run locally:

   ```bash
   uvicorn app.main:app --host 127.0.0.1 --port 8080
   ```

   Users can connect by sending `/connect` in Telegram, clicking the web link, and completing Google OAuth.

## Docker Deployment

```bash
docker compose up --build -d
```

Required environment variables in `.env`:
- `BOT_TOKEN`
- `WEBHOOK_URL`
- `BASE_URL`
- `GOOGLE_CREDENTIALS_JSON` (paste full JSON) or mount `credentials.json` via Docker Compose

## Render Deployment (Free Tier)

### 1. Push to GitHub
Ensure `credentials.json`, `.env`, and `tokens.db` are in `.gitignore`.

### 2. Create Web Service on Render
- Connect GitHub repo
- Select **Docker** runtime
- Set **Root Directory** to `calendar-commander` (if Dockerfile is in subfolder)

### 3. Environment Variables

| Key | Value |
|---|---|
| `BOT_TOKEN` | Your Telegram bot token |
| `WEBHOOK_URL` | `https://your-app.onrender.com` |
| `BASE_URL` | `https://your-app.onrender.com` |
| `GOOGLE_CREDENTIALS_JSON` | Full JSON content of `credentials.json` |
| `DB_PATH` | `/data/tokens.db` |
| `TIMEZONE` | `Asia/Manila` |

### 4. Add Render Redirect URI
In Google Cloud Console, add `https://your-app.onrender.com/oauth/callback` to **Authorized redirect URIs**.

### 5. Deploy
Render auto-deploys on push. The bot sets the Telegram webhook on startup. First message after inactivity may take ~50 seconds (free tier spin-down).

## How Multi-User Works

1. User sends `/connect` in Telegram
2. Bot replies with a unique link: `https://your-domain.com/connect?uid=USER_ID`
3. User clicks → sees "Connect with Google" button
4. After Google OAuth, tokens are stored in `tokens.db` (SQLite) mapped to their Telegram user ID
5. Bot sends a confirmation message in Telegram
6. All future commands (`/today`, `/events`, etc.) use that user's specific credentials
7. Token refresh is automatic; users can `/disconnect` to unlink

## Common Issues

### redirect_uri_mismatch
- Add the exact callback URL to Google Cloud Console → OAuth Client → Authorized redirect URIs
- Production: `https://your-domain.com/oauth/callback`

### access_denied
- OAuth consent screen not configured or user not in test users list

### accessNotConfigured
- Google Calendar API not enabled in Google Cloud Console

### Bot not responding
- Check Render logs for startup errors
- Verify `WEBHOOK_URL` and `BASE_URL` match your actual domain
- Run `/force_webhook` endpoint: `https://your-domain.com/force_webhook`

## Notes for Production

- Never commit `credentials.json`, `tokens.db`, or `.env`
- `GOOGLE_CREDENTIALS_JSON` env var is preferred over file mounting in cloud environments
- SQLite (`tokens.db`) stores per-user OAuth tokens with automatic refresh
- Free-tier hosts sleep after inactivity; first request may be slow
