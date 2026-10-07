<div align="center">

# SARA

**Upload a meeting recording, get a Thai summary, a to-do list, and a place to ask questions later.**

Built on AI4Thai Pathumma ASR and ThaiLLM.

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

</div>

## What it does

1. **Upload** an audio file (`.mp3 .m4a .wav ...`) or a document (`.txt .docx .pdf .md`).
2. **SARA transcribes and summarizes it** using the template you pick: general, marketing, finance or tech standup.
3. **You get** a summary, key points, and action items (who does what, by when).
4. **Next meeting in the same collection?** SARA checks whether any open action items were reported as done and suggests ticking them off. You confirm.
5. **Ask questions** across all meetings in a collection ("How much budget did we approve?") and get answers with quotes from the transcript.
6. **Export** to `.docx` or **email** the summary to attendees.

You can also try it without signing in: the public summarizer returns a one-off summary and saves nothing.

## How it works

```
Browser ── Next.js frontend
              │
              ▼
           FastAPI ──── PostgreSQL   users, collections, meetings, action items
              │    ├─── Redis        job queue + rate limits
              │    └─── Qdrant       vector index for Q&A
              ▼
        Celery worker
          upload → transcribe → summarize → index → check open tasks → ready
              │
              ▼
        AI4Thai ASR + ThaiLLM
```

- **Accounts:** Google Sign-In. Every user only sees their own data.
- **Q&A:** hybrid search. Qdrant finds passages with similar meaning, and keyword search catches names and numbers. If Qdrant is down, keyword search still answers.
- **Embeddings:** multilingual MiniLM, runs on CPU and is baked into the backend image.

## Quick start (Docker)

```bash
cp .env.example .env
# fill in at least: APP_POSTGRES_PASSWORD, APP_SECRET_KEY, APP_AI4THAI_API_KEY
docker compose up --build -d
```

| | URL |
| --- | --- |
| Web app | http://localhost:20130 |
| API docs | http://localhost:20131/docs |

In dev mode (`ENV=dev`) a demo account with sample meetings is created automatically. Sign in with `POST /auth/demo` in the API docs.

```bash
docker compose logs -f api worker   # follow logs
docker compose down                 # stop
```

## Configuration

Copy `.env.example` to `.env`. Variables starting with `APP_` are secrets, so never commit them.

| Variable | Needed | What it is |
| --- | --- | --- |
| `APP_POSTGRES_PASSWORD` | yes | Database password |
| `APP_SECRET_KEY` | yes | Signs login sessions. Generate one with `python -c "import secrets; print(secrets.token_urlsafe(48))"` |
| `APP_AI4THAI_API_KEY` | yes | AI4Thai key for ASR and LLM |
| `GOOGLE_CLIENT_ID` | for Google login | OAuth client ID (Web application) from Google Cloud Console |
| `APP_SMTP_USER` / `APP_SMTP_PASSWORD` | for email | SMTP login. If empty, emails are only written to the log |
| `ENV` | | `dev` enables demo login and `/docs`. `prod` turns them off and refuses to start without a strong secret key and a Google client ID |
| `SESSION_COOKIE_SECURE` | | `true` when served over HTTPS |
| `ROOT_PATH` | | Path prefix if a reverse proxy serves the API under a sub-path (e.g. `/api`). Leave empty locally |
| `CORS_ORIGINS` | | Allowed frontend origins, comma-separated |
| `DATABASE_URL` | | Only for running the backend outside Docker |

Tuning knobs (optional, see `backend/app/core/config.py`): `PUBLIC_SUMMARIZE_PER_HOUR`, `EMAIL_RECIPIENTS_PER_DAY`, `MEETING_TIME_LIMIT_MINUTES`, `VECTOR_MIN_SCORE`, `EMBEDDING_MODEL`.

## Developing without Docker

You need Python 3.11+, Node 20+, FFmpeg, and running PostgreSQL, Redis and Qdrant.

```bash
# backend
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
alembic upgrade head && python -m app.seed
uvicorn app.main:app --reload --port 8000

# worker (second terminal)
celery -A app.workers.tasks.celery_app worker -B --loglevel=info

# frontend (third terminal)
cd frontend && npm install && npm run dev
```

## Tests

```bash
# backend: needs a throwaway PostgreSQL (Qdrant and the embedding model are faked in tests)
docker run -d --name sara_test_db -e POSTGRES_PASSWORD=postgrespassword \
  -e POSTGRES_DB=sara_test -p 55432:5432 postgres:15-alpine
cd backend && python -m unittest discover -s tests -t . -v

# frontend
cd frontend && npm run build
```

## Project layout

```
backend/
  app/
    api/        routes: auth, collections, meetings, action-items, public
    services/   ASR, LLM summarize, Q&A, Qdrant, docx export, email, rate limits
    workers/    Celery pipeline
    db/         SQLAlchemy models
  alembic/      database migrations
  tests/
frontend/       Next.js app
docker-compose.yml
```

## License

Apache License 2.0. See [LICENSE](LICENSE).
