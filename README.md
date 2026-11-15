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
   uvicorn app.main:app --reload
   ```

Open http://127.0.0.1:8000. The SQLite database is created automatically as `syncboard.db`.

## Configuration

Set `SECRET_KEY` to a long random value for production. Set `DATABASE_URL` to use another SQLAlchemy-compatible database URL. The default token lifetime is 60 minutes.

## API

Interactive API documentation is available at `/docs`. Register two users, create a board, and invite the second user by email. Board task events are broadcast to every authorized WebSocket client connected to that board.
