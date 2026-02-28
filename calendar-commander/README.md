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
│
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

4. Add your real Google OAuth desktop credentials to `credentials.json`.

## Google OAuth Setup (Desktop App Flow)

1. Open Google Cloud Console.
2. Create/select project.
3. Enable **Google Calendar API**.
4. Go to **APIs & Services > Credentials**.
5. Create **OAuth client ID** with type **Desktop app**.
6. Download credentials JSON and save as `credentials.json` in project root.
7. Run app locally once and trigger a calendar command (`/today` or `/events`).
8. Browser auth flow opens; once approved, `token.json` is generated and reused.

## Run Locally

Use the same startup command as Render:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Expose your local server publicly for Telegram webhook testing (for example, using ngrok) and set `WEBHOOK_URL` accordingly.

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

## Notes for Production

- Never hardcode secrets.
- Keep `credentials.json`, `token.json`, and `.env` out of source control.
- The architecture is service-oriented and can be extended for multi-user token storage later (e.g., DB-backed user credential store).
