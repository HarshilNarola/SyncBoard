# SyncBoard

SyncBoard is a real-time collaborative Kanban board built with FastAPI, SQLite, SQLAlchemy, JWT authentication, WebSockets, Tailwind CSS, and Alpine.js.

## Run locally

1. Create and activate a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

2. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

3. Start the server:

   ```powershell
   python -m uvicorn app.main:app --reload
   ```

Open http://127.0.0.1:8000. The SQLite database is created automatically as `syncboard.db`.

## Configuration

Set `SECRET_KEY` to a long random value for production. Set `DATABASE_URL` to use another SQLAlchemy-compatible database URL. The default token lifetime is 60 minutes.

### Password reset email

The app supports authenticated password changes and email-based password resets. Configure these environment variables before using forgot-password in production:

```text
FRONTEND_URL=https://your-domain.example
SMTP_HOST=smtp.example.com
SMTP_PORT=587
SMTP_USERNAME=your-smtp-username
SMTP_PASSWORD=your-smtp-password
SMTP_FROM_EMAIL=no-reply@your-domain.example
SMTP_USE_TLS=true
```

Reset links expire after 30 minutes and can only be used once. If SMTP is not configured, the forgot-password endpoint returns a configuration error rather than exposing reset tokens.

## API

Interactive API documentation is available at `/docs`. Register two users, create a board, and invite the second user by email. Board task events are broadcast to every authorized WebSocket client connected to that board.
