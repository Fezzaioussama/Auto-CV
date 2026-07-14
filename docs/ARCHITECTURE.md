# Architecture

Auto-CV has four main layers:

1. Flask routes in `src/autocv/app.py`.
2. Domain logic in `src/`.
3. Jinja templates in `templates/`.
4. Browser logic and styling in `static/`.

The app is mostly request/response based. The long-running operations are LLM
rewrites and PDF compilation.

## High-Level Request Flow

```text
Browser
  -> Flask route in src/autocv/app.py
    -> parser/matcher/rewriter/interview module
      -> src/autocv/llm_client.py
        -> optional local/OpenRouter chat completion API
      -> optional pdflatex process
    -> JSON or PDF response
  -> Browser updates page state
```

## Optimizer Workflow

The main optimizer lives at `/`.

1. User pastes or drops a job description.
2. Browser calls `POST /api/parse-job`.
3. `src/autocv/app.py` calls `parse_job_description` from `src/autocv/parser.py`.
4. Browser displays extracted skills, requirements, and qualifications.
5. User pastes or drops a LaTeX CV.
6. Browser calls `POST /api/optimize-cv`.
7. `src/autocv/app.py` calls `optimize_cv_for_job` from `src/autocv/matcher.py`.
8. `matcher.py` analyzes the CV/job match.
9. `matcher.py` starts these in parallel:
   - general modifications from `CVMatcher.generate_cv_modifications`
   - section rewrites from `src/autocv/section_rewriter.py`
   - optional proposal snippets from `src/autocv/section_rewriter.py`
10. Browser receives analysis, optimized LaTeX, rewritten section titles, and
    proposed additions.
11. Browser displays score, coverage, recommendations, editable LaTeX, and PDF
    preview controls.
12. Browser calls `POST /api/render-latex` when the user previews or downloads
    a PDF.

## Interview Workflow

The interview feature lives at `/interview`.

1. The optimizer stores the current CV and job text in `sessionStorage`.
2. `/interview` pre-fills those values when available.
3. User chooses level, domains, count, and optional instructions.
4. Browser calls `POST /api/interview/questions`.
5. `src/autocv/interview_agent.py` generates structured questions with the LLM.
6. If generation fails, deterministic fallback questions are returned with
   `fallback: true`.
7. User answers a question.
8. Browser calls `POST /api/interview/review`.
9. `src/autocv/interview_agent.py` returns a score, strengths, improvements,
   follow-up questions, and coding complexity when relevant.

## Backend Module Responsibilities

### `src/autocv/app.py`

- Creates the Flask app.
- Defines HTML and API routes.
- Handles request validation at the route boundary.
- Compiles LaTeX to PDF in a temporary directory.
- Normalizes some LaTeX dependencies before compilation.
- Imports `llm_client`, which loads `.env`, and exposes `/api/llm/health`.

### `src/autocv/llm_client.py`

- Loads `.env` from the project root.
- Selects the LLM provider with `SOURCE_LLM`.
- Supports `local` OpenAI-compatible servers and OpenRouter.
- Resolves a default model or per-task model for each LLM call type.
- Adds provider-specific authorization and optional OpenRouter attribution
  headers.
- Centralizes request timeouts and max worker configuration.
- Returns `None` on LLM failures so feature modules can use their existing
  fallbacks.

### `src/autocv/parser.py`

- Cleans job description text.
- Extracts skills using a curated common-skill set.
- Extracts requirements and qualifications with rule-based patterns.
- Extracts light company/location information.

### `src/autocv/matcher.py`

- Canonicalizes and matches skills.
- Calls the LLM client for CV/job analysis.
- Provides a rule-based fallback if the LLM is unavailable.
- Normalizes analysis output into the response shape expected by the frontend.
- Orchestrates CV optimization, section rewrite, and proposals.

### `src/autocv/section_rewriter.py`

- Splits a LaTeX document into `\section{...}` blocks.
- Classifies sections such as summary, skills, experience, projects, education,
  certifications, and languages.
- Sends each supported section through the LLM client independently.
- Rejects suspicious outputs, whole-document outputs, or outputs that introduce
  unclaimed missing skills.
- Proposes optional new section snippets.

### `src/autocv/interview_agent.py`

- Converts LaTeX CV content into plain text for prompting.
- Normalizes job descriptions.
- Generates structured interview questions.
- Reviews written or coding answers.
- Falls back to deterministic offline questions/reviews when the LLM fails.

### `src/autocv/smart_cv_generator.py`

- Provides the standalone smart CV generation API used by the legacy scripts.
- Uses `llm_client.Task.SMART_CV` for LLM-backed job analysis and CV content
  generation.
- Still accepts explicit `api_url` and `model` constructor overrides for older
  scripts, while defaulting to environment-resolved provider configuration.

### `src/autocv/latex_gen.py`

- Builds sample CV data.
- Contains helpers for creating LaTeX content.
- Contains older or standalone PDF compilation helpers used by the smart CV
  generator path.

## Frontend Module Responsibilities

### `templates/index.html`

Defines the optimizer page layout, including:

- hero and navigation
- job description upload area
- job analysis results
- CV upload area
- optimization action
- match score, recommendations, LaTeX editor, PDF preview, and proposals

### `static/script.js`

Owns the optimizer page behavior:

- drag/drop handlers
- API calls
- visible/hidden workflow state
- rendering skills, recommendations, proposal cards, and PDF preview
- copying and downloading optimized LaTeX/PDF

### `static/animations.js`

Presentation-only enhancements:

- navbar scroll state
- reveal animations
- button ripple
- match gauge animation
- stepper state

### `templates/interview.html`

Defines the interview setup form and generated question container.

### `static/interview.js`

Owns the interview page behavior:

- context prefill from `sessionStorage`
- question generation API call
- optional lazy CodeMirror loading
- answer review API call
- rendering review panels

## LLM Integration

All LLM calls use `src/autocv/llm_client.py`. The rest of the app should not call
`requests.post(.../chat/completions)` directly.

The client supports two providers:

| Provider | `SOURCE_LLM` | Required configuration |
| --- | --- | --- |
| Local OpenAI-compatible server | `local` | `LOCAL_LLM_URL`, `LOCAL_LLM_MODEL`, optional `LOCAL_LLM_API_KEY` |
| OpenRouter | `openrouter` | `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` |

Both providers use the OpenAI chat-completions contract:

```text
POST {base_url}/chat/completions
```

The active configuration is visible at:

```text
GET /api/llm/health
```

The response intentionally reports only secret-free details. It is a
configuration diagnostic, not a network connectivity test.

### LLM Tasks

`llm_client.Task` defines logical call types:

- `ANALYSIS`
- `SECTION_REWRITE`
- `PROPOSAL`
- `INTERVIEW`
- `SMART_CV`
- `DEFAULT`

Each task can use a different model through the per-task variables documented
in `.env.example`.

Most prompts ask for strict JSON or strict LaTeX-only output. The code still
validates and cleans responses because model output can be noisy.

## Fallback Strategy

The app is designed to keep working when the LLM is unavailable:

- CV analysis falls back to rule-based skill matching.
- CV rewriting falls back to rule-based LaTeX adaptation.
- Interview questions fall back to deterministic templates.
- Interview reviews fall back to a simple heuristic review.

When changing LLM prompts, preserve those fallbacks.

## LaTeX Rendering

`POST /api/render-latex` writes the submitted LaTeX to a temporary `cv.tex`,
runs `pdflatex`, reads the produced `cv.pdf`, and returns it as
`application/pdf`.

Before compilation, `ensure_latex_dependencies` tries to remove or add packages
for common local compiler compatibility issues.

## Important Couplings

- `script.js` expects specific element IDs from `templates/index.html`.
- `animations.js` observes `#matchProgressBar` to animate the gauge.
- `interview.js` expects specific element IDs from `templates/interview.html`.
- `matcher.py` response keys must stay compatible with `static/script.js`.
- `interview_agent.py` question and review shapes must stay compatible with
  `static/interview.js`.
- `llm_client.py` environment variable names must stay in sync with
  `.env.example`, `docs/DEVELOPMENT.md`, and startup/health diagnostics.
