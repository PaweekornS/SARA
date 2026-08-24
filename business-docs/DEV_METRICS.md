# SARA — Development Metrics

All figures below are pulled directly from `git log` and the repository's tracked files (not estimated).

## Commit & contributor summary

| Metric | Value |
|---|---|
| Total commits | 22 |
| Contributors | 1 (Paweekorn S.) |
| First commit | 2026-07-23 |
| Latest commit | 2026-08-09 |
| Development span | ~17 days |

The project used a branch/PR workflow (`feat/user-qa`, `feat/frontend`, `fix/backend` merged via 3 pull requests) even with a single developer.

## Codebase size (lines of code, tracked files only)

| Area | Lines |
|---|---|
| Backend (Python) | 912 |
| Frontend (TypeScript/TSX, excluding `package-lock.json`) | 1,285 |
| Other (README, LICENSE, `.env.example`, Docker/Compose config) | 485 |
| **Total** | **~2,682** |

Notable concentration: the entire frontend application logic lives in a single file, `frontend/app/page.tsx` (944 lines) — there is no component decomposition yet.

**Interpretation:** this is a small, young, single-author codebase consistent with an early hackathon-stage build rather than a mature product with a development team and history. ไม่มีข้อมูลเพียงพอ to project future development velocity or team-scaling needs from this history alone.

## Key dependencies and licenses

Licenses below are based on each package's well-known, publicly documented license; direct dependencies only (not the full transitive dependency tree, which was not audited here).

### Backend (Python, `backend/requirements.txt`)

| Package | License | Commercial flag |
|---|---|---|
| fastapi | MIT | — |
| uvicorn | BSD-3-Clause | — |
| pydantic / pydantic-settings | MIT | — |
| sqlalchemy | MIT | — |
| asyncpg | Apache-2.0 | — |
| **psycopg2-binary** | **LGPL** (with a linking exception) | ⚠️ **Flag** — the only copyleft-family license among direct dependencies. The package's own linking exception is designed to permit commercial/proprietary use without triggering LGPL's reciprocal-source obligations, but this should be confirmed by counsel before commercial distribution of the backend as a packaged product. |
| celery | BSD-3-Clause | — |
| redis (client) | MIT | — |
| openai (SDK) | Apache-2.0 | — |
| mcp (SDK) | MIT | — |
| fastmcp | Apache-2.0 | — |
| jinja2 | BSD-3-Clause | — |
| python-multipart | Apache-2.0 | — |
| requests | Apache-2.0 | — |

### Frontend (`frontend/package.json`)

| Package | License | Commercial flag |
|---|---|---|
| next, react, react-dom | MIT | — |
| lucide-react | ISC | — |
| typescript | Apache-2.0 | — |
| eslint, eslint-config-next, tailwindcss | MIT | — |

**No GPL or AGPL dependencies were found among direct dependencies** in either backend or frontend. `psycopg2-binary` (LGPL) is the only license worth flagging for commercial review. Transitive dependencies (pulled in automatically by the packages above, listed in full in `frontend/package-lock.json`) were not individually audited — a formal license-scanning tool (e.g., `pip-licenses`, `license-checker`, or `syft`) should be run before any commercial release to certify the complete dependency tree.

## Project's own license

The repository itself is published under the **Apache License 2.0** (`LICENSE` file, root of repo). Note: the license file's copyright-holder line still contains the unfilled template placeholder rather than a specific name/entity — this should be completed before any formal distribution.
