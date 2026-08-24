# SARA — Project Status

## Test coverage

**None.** There are no test files anywhere in the repository (backend or frontend), no test runner configured, and no test scripts beyond linting. This means there is currently no automated way to verify a code change hasn't broken existing functionality.

## CI/CD

**None.** There is no `.github/workflows` directory or any other CI configuration in the repo. Docker Compose and two Dockerfiles exist, but they define *local/manual* build-and-run steps only — there is no automated pipeline that runs tests, builds images, or deploys on every commit.

## Known bugs and limitations (unfixed, as of this writing)

- **Recipient discovery is hardcoded.** The endpoint meant to return real meeting participants' email addresses currently returns two fixed test addresses instead of real data pulled from a calendar or meeting platform.
- **Silent fallback on transcription failure.** If the speech-to-text API call fails (or the uploaded file is missing), the system substitutes a hardcoded placeholder transcript instead of surfacing a clear error to the user. This was an intentional shortcut to keep demos from crashing, but it means a real transcription failure could currently go unnoticed by the user.
- **No authentication enforced on the API.** A database table and validation function for API keys exist in the code, but no endpoint actually requires a key — any client that can reach the API can use every endpoint.
- **No database migrations.** The schema is created automatically at startup rather than through versioned migrations, so evolving the schema safely once real data exists is not yet supported.
- **Uploaded files are not durably stored.** Audio files are written to a temporary local folder rather than persistent/cloud storage, so they are not guaranteed to survive a restart or be available across multiple server instances.
- **Model naming inconsistency.** Configuration refers to the summarization model as `thaillm-8b`, while the README and some code comments call it "Qwen 3.5" — these do not obviously refer to the same thing, and it's unclear from the repo alone which is actually running in production.
- **Frontend is unbranded at the browser/document level.** The page title and meta description still say "Create Next App" (the default Next.js template value), even though the in-app UI is branded as SARA.
- **No dark/light mode toggle**, despite dark-mode CSS being present throughout — theming currently only follows the OS/browser preference.

## Deployment readiness

**Demo-only.** Specifically:
- Runs via Docker Compose on a single machine; no cloud deployment configuration exists.
- No authentication, no automated tests, no CI/CD, no database migrations, and no durable file storage — each of these is normally considered a baseline requirement before handling real user/customer data in production.
- Single-developer project with roughly 17 days of commit history (2026-07-23 to 2026-08-09) — this is early-stage/hackathon-stage code, not a system that has been hardened through iterative production use.

This assessment reflects the code as it exists today; it is not a judgment on the team's ability to close these gaps, several of which (auth, migrations, cloud storage) are well-understood, addressable engineering tasks rather than open research problems.
