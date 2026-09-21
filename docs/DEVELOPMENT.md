# Development Guide

This guide explains how to run Auto-CV locally and where to make changes.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (manages the Python version + dependencies).
- Python 3.10+ (uv installs/pins it from `.python-version`).
- A LaTeX distribution with `pdflatex` if you need PDF rendering.
- Network access to either a local OpenAI-compatible server or OpenRouter if
  you want live AI rewriting and interview generation.

## Local Setup

From the project root:

```bash
uv sync   # creates .venv and installs the project + dev dependencies
uv run python -c "import nltk; nltk.download('punkt'); nltk.download('punkt_tab'); nltk.download('stopwords')"
cp .env.example .env
```

uv manages the virtual environment for you — there is no `activate` step; prefix
commands with `uv run`. (You can still `source .venv/bin/activate` if you prefer.)

## Run The App

Default development run:

```bash
uv run python -m autocv   # or: make run
```

That starts the app on:

```text
http://localhost:5000
```

If port `5000` is busy, use Flask directly:

```bash
uv run flask --app autocv run --host 0.0.0.0 --port 5001 --debug
```

## Environment Configuration

All LLM access goes through `src/autocv/llm_client.py`. It loads `.env` from the
project root and selects the provider, base URL, API key, timeout, and model
for each task.

Start from the tracked template:

```bash
cp .env.example .env
```

Then choose one provider:

```bash
# Local vLLM/Ollama/OpenAI-compatible server
SOURCE_LLM=local
LOCAL_LLM_URL=http://localhost:8000/v1
LOCAL_LLM_MODEL=your-local-model
```

or:

```bash
# OpenRouter serverless API
SOURCE_LLM=openrouter
OPENROUTER_API_KEY=your-key
OPENROUTER_MODEL=qwen/qwen3.6-plus
```

Important environment variables:

| Variable | Used by | Purpose |
| --- | --- | --- |
| `SOURCE_LLM` | `src/autocv/llm_client.py` | Selects `local` or `openrouter`. |
| `LOCAL_LLM_URL` | `src/autocv/llm_client.py` | Base URL for a local OpenAI-compatible server. |
| `LOCAL_LLM_MODEL` | `src/autocv/llm_client.py` | Default local model. |
| `LOCAL_LLM_API_KEY` | `src/autocv/llm_client.py` | Optional local bearer token. |
| `OPENROUTER_API_KEY` | `src/autocv/llm_client.py` | Required when `SOURCE_LLM=openrouter`. |
| `OPENROUTER_MODEL` | `src/autocv/llm_client.py` | Default OpenRouter model. |
| `OPENROUTER_MODEL_OCR` | `src/autocv/llm_client.py` | Vision-capable OpenRouter model for scanned/image OCR. |
| `OPENROUTER_BASE_URL` | `src/autocv/llm_client.py` | OpenRouter API base URL. Rarely changed. |
| `LLM_CONNECT_TIMEOUT` | `src/autocv/llm_client.py` | Connection timeout in seconds. |
| `LLM_TIMEOUT` | `src/autocv/llm_client.py` | Read timeout in seconds. |
| `LLM_MAX_WORKERS` | `section_rewriter.py` through `llm_client.py` | Max parallel section rewrite calls. |
| `LATEX_REPAIR_ATTEMPTS` | `src/autocv/latex_repair.py` | Max render-error correction iterations. |
| `LATEX_REPAIR_MAX_TOKENS` | `src/autocv/latex_repair.py` | Response-token budget for each render repair request. |

Per-task model overrides:

```text
LOCAL_MODEL_ANALYSIS=
LOCAL_MODEL_SECTION_REWRITE=
LOCAL_MODEL_PROPOSAL=
LOCAL_MODEL_INTERVIEW=
LOCAL_MODEL_SMART_CV=

OPENROUTER_MODEL_ANALYSIS=
OPENROUTER_MODEL_SECTION_REWRITE=
OPENROUTER_MODEL_PROPOSAL=
OPENROUTER_MODEL_INTERVIEW=
OPENROUTER_MODEL_SMART_CV=
OPENROUTER_MODEL_OCR=google/gemini-3.1-flash-lite
```

Legacy variables such as `VLLM_API_URL`, `VLLM_MODEL`,
`VLLM_CONNECT_TIMEOUT`, `VLLM_TIMEOUT`, and `VLLM_MAX_WORKERS` are still
accepted as fallbacks, but new development should use the variables in
`.env.example`.

To inspect the active provider without exposing secrets:

```bash
curl http://localhost:5000/api/llm/health
```

## Web App: Accounts, Database & Security

Auto-CV runs as a multi-user web app with accounts. The relevant pieces:

| File | Responsibility |
| --- | --- |
| `src/autocv/config.py` | Env-driven config: debug, `SECRET_KEY`, DB URL, cookies, limits. |
| `src/autocv/extensions.py` | Unbound `db`, `login_manager`, `csrf`, `limiter` instances. |
| `src/autocv/models.py` | `User`, `Job`, `CVDocument`, `CVVersion`, `CoverLetter`. |
| `src/autocv/auth.py` | Register / login / logout blueprint (`templates/login.html`, `register.html`). |
| `src/autocv/workspace.py` | Per-user saved jobs + CV version history API. |
| `src/autocv/features.py` | File extraction, templates, cover-letter endpoints. |

Key environment variables (see `.env.example` for the full list):

| Variable | Purpose |
| --- | --- |
| `FLASK_ENV` | `development` relaxes safety defaults; anything else is production. |
| `FLASK_DEBUG` | Werkzeug debugger. **Must be `0` in production** (RCE if exposed). |
| `SECRET_KEY` | **Required in production.** Signs sessions. |
| `DATABASE_URL` | Defaults to SQLite under `instance/`; set Postgres for production. |
| `WTF_CSRF_ENABLED` | CSRF protection for browser requests (keep on). |
| `MAX_CONTENT_LENGTH_MB` | Upload / body size cap. |
| `RATELIMIT_*` | Request budgets (default, LLM, auth). |

The database tables are created automatically on first start (`db.create_all()`).
The SQLite file and uploads live in `instance/`, which is git-ignored.

CSRF: server-rendered forms include a hidden token; the JSON API reads the token
from the `<meta name="csrf-token">` tag and `static/csrf.js` attaches it to every
mutating `fetch` (and redirects to `/login` on a 401). New pages that call the
API must include the meta tag and `csrf.js`.

Quick local check (no LLM/pdflatex needed):

```bash
FLASK_ENV=development SECRET_KEY=dev python -c "import main; print('routes:', len(list(main.app.url_map.iter_rules())))"
```

## Daily Development Workflow

1. Start the Flask app.
2. Open `/` for the CV optimizer or `/interview` for interview prep.
3. Use "Load Sample Job" and "Load Sample CV" to avoid manual input.
4. Watch the terminal logs for backend and LLM failures.
5. Check browser DevTools for frontend errors.
6. Run the relevant test script or manual workflow before committing.

## Where To Change Common Features

| Change | Files to inspect first |
| --- | --- |
| Add a new optimizer step | `templates/index.html`, `static/script.js`, `src/autocv/app.py` |
| Change LLM provider/model behavior | `src/autocv/llm_client.py`, `.env.example` |
| Change job parsing | `src/autocv/parser.py`, `src/autocv/matcher.py` |
| Change match scoring | `src/autocv/matcher.py` |
| Change CV rewrite behavior | `src/autocv/section_rewriter.py`, `src/autocv/matcher.py` |
| Change PDF rendering | `src/autocv/app.py`, `src/autocv/latex_gen.py` |
| Change interview generation | `src/autocv/interview_agent.py`, `static/interview.js` |
| Change standalone smart CV generation | `src/autocv/smart_cv_generator.py`, `src/autocv/llm_client.py` |
| Change page styling | `static/style.css`, `static/interview.css` |

## Browser Cache Busting

Templates currently load static files with manual query versions, for example:

```html
<script src="/static/script.js?v=6"></script>
```

When changing CSS or JS and the browser keeps old assets, increment the query
version in the template or clear the browser cache.

## Current Test Commands

The automated test suite lives in `tests/` and runs with pytest:

```bash
make test          # or: uv run pytest
```

There are also two standalone smoke scripts (not part of the pytest suite):

```bash
uv run python scripts/test_smart_cv.py
uv run python scripts/test_vllm_cv.py
```

`scripts/test_vllm_cv.py` is a legacy local-vLLM smoke script with an explicit endpoint
and model in the file. If that endpoint is offline, expect the connection part
to fail. Update the script before using it to test another provider.

Recommended manual smoke test:

1. Start the app.
2. Open `/`.
3. Load sample job.
4. Load sample CV.
5. Optimize CV.
6. Render PDF preview.
7. Open `/interview`.
8. Load demo context.
9. Generate questions.
10. Review one answer.
