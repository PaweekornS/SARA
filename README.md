<div align="center">

# SARA

**Upload a meeting recording. Get a Thai summary, a to-do list, and answers to questions later.**

Built on AI4Thai Pathumma ASR and ThaiLLM.

[![Python](https://img.shields.io/badge/Python-3.11-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Next.js](https://img.shields.io/badge/Next.js-000000?logo=nextdotjs&logoColor=white)](https://nextjs.org/)
[![License](https://img.shields.io/badge/license-Apache%202.0-blue)](LICENSE)

</div>

## Features

- **Summaries:** upload audio or a document and get a summary, key points and action items.
- **Follow-up:** in the next meeting, SARA spots tasks that were reported done and asks you to confirm.
- **Ask:** question all meetings in a collection and get answers that quote the transcript.
- **Share:** export to `.docx` or email the summary.

## How it works

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/diagrams/architecture-dark.png">
  <img alt="SARA architecture: the browser uses the Next.js frontend, which forwards /api to FastAPI; FastAPI uses PostgreSQL, Redis and Qdrant and calls AI4Thai, Google and SMTP; the Celery worker transcribes and summarizes through AI4Thai." src="docs/diagrams/architecture.png">
</picture>

More detail, including the processing lifecycle: [docs/development.md](docs/development.md).

## Quick start

```bash
cp .env.example .env    # set APP_POSTGRES_PASSWORD, APP_SECRET_KEY, APP_AI4THAI_API_KEY
docker compose up --build -d
```

Open http://localhost:20130 and choose **Try with demo account**. API docs: http://localhost:20131/docs.

## Configuration

| Variable | Required | Purpose |
| --- | --- | --- |
| `APP_POSTGRES_PASSWORD` | yes | Database password |
| `APP_SECRET_KEY` | yes | Signs login sessions (32+ random characters) |
| `APP_AI4THAI_API_KEY` | yes | AI4Thai ASR and LLM |
| `GOOGLE_CLIENT_ID` | for Google login | OAuth client ID |
| `APP_SMTP_USER`, `APP_SMTP_PASSWORD` | for email | Without them, emails are only logged |

`APP_*` variables are secrets: keep them out of git. All other settings: [docs/development.md](docs/development.md#configuration).

## License

Apache License 2.0. See [LICENSE](LICENSE).
