# Auto-CV

Auto-CV is a Flask web application that helps candidates tailor a LaTeX CV to a
specific job offer, review the match, export a polished PDF, and prepare for the
interview with an AI coaching workflow.

The app combines job-offer parsing, CV analysis, LLM-assisted rewriting,
LaTeX/PDF rendering, saved workspace history, and interview preparation from the
same CV and job context.

## Key Features

- **Job offer analysis**: Extracts skills, requirements, qualifications, and
  company information from pasted or uploaded job descriptions.
- **CV matching**: Compares the candidate CV against the target role and
  highlights matched skills, missing skills, gaps, and recommendations.
- **LLM-assisted CV optimization**: Rewrites relevant LaTeX CV sections while
  keeping the candidate's facts intact.
- **Reviewable changes**: Shows before/after rewrite suggestions and optional
  additions so the user can accept, reject, or edit changes.
- **PDF rendering**: Compiles optimized LaTeX into a downloadable PDF, with
  automatic repair attempts for common LaTeX issues.
- **Workspace history**: Saves jobs and CV versions for reuse, comparison, and
  restoration.
- **AI interview coach**: Generates role-grounded interview sessions with
  coding, system design, technical, and behavioral questions.
- **Answer review and progression tracking**: Scores interview answers, surfaces
  weak points, role-fit risks, priority actions, and score evolution across the
  session.
- **Flexible LLM provider support**: Works with a local OpenAI-compatible server
  or OpenRouter through one central configuration layer.

## Tech Stack

- **Backend**: Flask, Flask-Login, Flask-WTF, Flask-SQLAlchemy, Flask-Limiter
- **Frontend**: HTML templates, Bootstrap, custom CSS, vanilla JavaScript
- **AI layer**: OpenAI-compatible chat-completions client with provider/task
  routing
- **Documents**: LaTeX generation, PDF rendering, OCR/file extraction support
- **Database**: SQLite by default, configurable via `DATABASE_URL`

## Project Structure

```text
auto-cv-app/
├── main.py                   # Backwards-compatible entry point (builds the app via create_app)
├── pyproject.toml            # Packaging, dependencies, and tooling config
├── uv.lock                   # Resolved dependency lockfile (uv — authoritative)
├── .python-version           # Python version pin used by uv
├── requirements.txt          # pip fallback (uv.lock is authoritative)
├── Makefile                  # Local run/stop/check/test helpers
├── src/
│   └── autocv/               # Application package
│       ├── app.py            # Flask application factory (create_app) + routes
│       ├── __main__.py       # `python -m autocv` entry point
│       ├── llm_client.py     # Central LLM provider configuration
│       ├── parser.py         # Job description parsing
│       ├── matcher.py        # CV/job matching and optimization orchestration
│       ├── section_rewriter.py  # Section-level LLM rewrite logic
│       ├── interview_agent.py   # Interview generation and answer review
│       ├── workspace.py      # Saved jobs and CV version history
│       └── latex_gen.py      # LaTeX helpers and sample CV generation
├── templates/                # Flask HTML + LaTeX templates
├── static/                   # Frontend JavaScript, CSS, and assets
├── tests/                    # pytest suite (+ fixtures/)
├── scripts/                  # Standalone smoke/dev scripts
├── docs/                     # Developer documentation
├── examples/                 # Example CV/job material
├── output/                   # Generated output placeholder
└── instance/                 # Local SQLite database, ignored in production
```

## Requirements

- [uv](https://docs.astral.sh/uv/) (manages the Python version and dependencies)
- Python 3.10+ (uv installs/pins it from `.python-version`)
- A LaTeX distribution with `pdflatex` for PDF rendering
- Optional: Tesseract OCR for image/scanned CV extraction
- Optional: a local OpenAI-compatible LLM server, or an OpenRouter API key

## Quick Start

1. Install dependencies (creates `.venv` and installs the project + dev tools):

```bash
uv sync          # or: make install
```

2. Create your local environment file:

```bash
cp .env.example .env
```

3. Edit `.env` for your LLM provider.

For a local OpenAI-compatible server:

```env
SOURCE_LLM=local
LOCAL_LLM_URL=http://localhost:8000/v1
LOCAL_LLM_MODEL=your-model-name
```

For OpenRouter:

```env
SOURCE_LLM=openrouter
OPENROUTER_API_KEY=your-api-key
OPENROUTER_MODEL=openai/gpt-oss-120b
```

4. Run the app:

```bash
make start          # or: uv run python -m autocv
```

Open:

```text
http://127.0.0.1:5000
```

The interview coach is available at:

```text
http://127.0.0.1:5000/interview
```

## Make Commands

```bash
make run       # Run the app in the foreground
make start     # Start the app in the background on port 5000
make stop      # Stop the app and anything listening on port 5000
make restart   # Stop and start the app
make status    # Show the process using port 5000
make logs      # Follow the app log
make check     # Run Python compile checks and JS syntax checks
make clean     # Remove local runtime files and Python caches
```

The default port is `5000`. You can override it for Makefile-managed commands:

```bash
make start PORT=5001
make stop PORT=5001
```

### Running with uv

The app is packaged (`pyproject.toml`) as the `autocv` package under `src/`.
`uv sync` installs it (editable) into `.venv`, so the standard entry points work
through `uv run`:

```bash
uv sync                              # create/refresh .venv from pyproject + uv.lock
uv run flask --app autocv run        # dev server (add --debug for auto-reload)
uv run python -m autocv              # dev server
uv run auto-cv                       # console script (same as python -m autocv)
```

For a production WSGI server, install the `prod` extra (adds gunicorn):

```bash
uv sync --extra prod
uv run gunicorn "autocv:create_app()"
```

Common dependency tasks:

```bash
uv add <package>                     # add a runtime dependency (updates pyproject + uv.lock)
uv add --dev <package>               # add a dev/test dependency
uv lock --upgrade                    # re-resolve to the latest allowed versions
```

`python main.py` and `gunicorn main:app` still work if you prefer a plain
virtualenv without uv.

## Main Workflows

### CV Optimization

1. Paste or upload a job offer.
2. Parse the offer to extract requirements and skills.
3. Upload or paste a CV in LaTeX, PDF, Word, image, or plain text form.
4. Analyze the match between the CV and the role.
5. Generate an optimized LaTeX CV.
6. Review proposed changes before applying them.
7. Render and download the final PDF.
8. Save the job and CV version in the workspace.

### Interview Preparation

1. Reuse the CV and job context from the optimizer, or paste new context.
2. Choose seniority, domains, session focus, and question count.
3. Generate a role-grounded coaching session.
4. Answer coding, system design, technical, and behavioral questions.
5. Request AI review for each answer.
6. Track score evolution, weak areas, negative points, role-fit risks, and next
   practice actions from the AI coach dashboard.

## Important Routes

| Route | Purpose |
| --- | --- |
| `/` | Main CV optimizer workspace |
| `/interview` | AI interview coach |
| `/workspace` | Saved jobs and CV versions |
| `/how-it-works` | Product workflow overview |
| `/api/parse-job` | Parse raw job text |
| `/api/analyze-cv` | Analyze CV against a job |
| `/api/optimize-cv` | Rewrite and optimize CV LaTeX |
| `/api/render-latex` | Compile LaTeX to PDF |
| `/api/interview/questions` | Generate interview session questions |
| `/api/interview/review` | Review one interview answer |
| `/api/llm/health` | Show active LLM provider configuration |

## Configuration

The app reads configuration from `.env`. Use `.env.example` as the template.

Important settings:

- `SOURCE_LLM`: `local` or `openrouter`
- `LOCAL_LLM_URL`, `LOCAL_LLM_MODEL`, `LOCAL_LLM_API_KEY`
- `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`
- `SECRET_KEY`: required for production
- `DATABASE_URL`: defaults to SQLite under `instance/`
- `LATEX_REPAIR_ATTEMPTS`: number of automatic LaTeX repair attempts
- `MAX_CONTENT_LENGTH_MB`: upload/request size limit
- `RATELIMIT_*`: rate-limit settings

Do not commit `.env`; it is intentionally ignored.

## Verification

Run the local checks before pushing changes:

```bash
make check
```

This currently runs:

```bash
uv run python -m compileall main.py src scripts
node --check static/interview.js
```

Run the automated test suite with:

```bash
make test   # or: uv run pytest
```

For manual verification:

1. Start the app with `make start`.
2. Open `/`.
3. Parse a job offer.
4. Upload or paste a CV.
5. Optimize the CV and render the PDF.
6. Open `/interview`.
7. Generate a coaching session and review at least one answer.

## Documentation

Developer documentation lives in [docs/](docs/):

- [Quick Start](docs/QUICKSTART.md)
- [Installation Guide](docs/INSTALLATION.md)
- [Development Guide](docs/DEVELOPMENT.md)
- [Architecture](docs/ARCHITECTURE.md)
- [API Reference](docs/API_REFERENCE.md)
- [Frontend Guide](docs/FRONTEND.md)
- [Maintenance Guide](docs/MAINTENANCE.md)
- [Product Roadmap](docs/ROADMAP.md)

## Deployment Notes

- Set `SECRET_KEY` in every non-local environment.
- Keep `FLASK_DEBUG=0` outside local development.
- Use a production WSGI server instead of Flask's development server.
- Use PostgreSQL or another managed database by setting `DATABASE_URL`.
- Use Redis-backed rate limiting if running multiple workers.
- Keep API keys and secrets in environment variables, never in source control.

## License

No license file is currently included in this repository. Add one before public
distribution if the project will be shared externally.
