# Auto-CV Developer Documentation

This folder is the onboarding entry point for developers who need to build,
debug, or maintain Auto-CV.

Auto-CV is a Flask web application that takes a job offer and a candidate CV,
matches the CV against the offer, rewrites relevant LaTeX CV sections with an
LLM, renders the result to PDF, and can also generate interview-preparation
questions from the same CV and job context.

## Recommended Reading Order

| Document | Purpose |
| --- | --- |
| [DEVELOPMENT.md](DEVELOPMENT.md) | Local setup, configuration, run commands, and daily workflow. |
| [ARCHITECTURE.md](ARCHITECTURE.md) | How the backend, frontend, LLM calls, and LaTeX rendering fit together. |
| [API_REFERENCE.md](API_REFERENCE.md) | Flask routes, request payloads, and response shapes. |
| [FRONTEND.md](FRONTEND.md) | Template/static file structure and browser-side state flow. |
| [MAINTENANCE.md](MAINTENANCE.md) | Testing, debugging, release checks, and common failure modes. |
| [INSTALLATION.md](INSTALLATION.md) | Existing installation guide for basic environment setup. |
| [../ROADMAP.md](../ROADMAP.md) | Product feature roadmap and recommended build order. |

## Main Application Surfaces

- `/` - CV optimizer workflow.
- `/interview` - interview question generator and answer reviewer.
- `/api/parse-job` - parses a pasted job description.
- `/api/optimize-cv` - analyzes and rewrites CV content for a parsed job.
- `/api/render-latex` - compiles LaTeX into a PDF.
- `/api/llm/health` - reports the active LLM provider/model configuration
  without exposing secrets.
- `/api/interview/questions` - generates CV/job-grounded interview questions.
- `/api/interview/review` - reviews one interview answer or code solution.

## Important Project Paths

| Path | Responsibility |
| --- | --- |
| `main.py` | Flask app, route definitions, PDF rendering endpoint. |
| `src/llm_client.py` | Central LLM provider, model, timeout, and API-key configuration. |
| `src/parser.py` | Rule-based job description parsing and skill extraction. |
| `src/matcher.py` | CV/job match analysis and optimization orchestration. |
| `src/section_rewriter.py` | Section-level LLM rewrite and optional addition proposals. |
| `src/interview_agent.py` | Interview question generation and answer/code review. |
| `src/smart_cv_generator.py` | Standalone smart CV generation path and legacy test-script workflow. |
| `src/latex_gen.py` | Sample CV and LaTeX generation helpers. |
| `templates/index.html` | Main optimizer page. |
| `templates/interview.html` | Interview preparation page. |
| `static/script.js` | Optimizer page browser logic. |
| `static/interview.js` | Interview page browser logic. |
| `static/style.css` | Shared UI design system. |
| `static/interview.css` | Interview page-specific styling. |
| `.env.example` | Template for local/provider LLM configuration. |
| `.gitignore` | Keeps secrets, caches, and generated output out of version control. |
| `ROADMAP.md` | Planned product functionality and feature priority. |

## Key Concepts

- **Job analysis**: The parsed job description returned by `parse_job_description`.
- **CV analysis**: The match result returned by `analyze_cv`, including scores,
  matched skills, missing skills, and recommendations.
- **Optimized LaTeX**: The rewritten CV document returned by `/api/optimize-cv`.
- **Rewritten sections**: CV section titles that were successfully rewritten by
  the LLM. Empty means the app used fallback rewriting.
- **Proposed additions**: Optional new LaTeX snippets that the user may insert
  manually, usually for missing projects, skills, summaries, or certifications.
- **Fallback mode**: Rule-based behavior used when the LLM is unavailable or its
  output fails validation.
- **LLM provider**: Selected by `SOURCE_LLM` through `src/llm_client.py`.
  Supported values are `local` and `openrouter`.
- **Per-task model**: Optional model override for a specific LLM task such as
  analysis, section rewrite, proposal, interview, or smart CV generation.

## Developer Rule Of Thumb

When adding or changing a feature, update all four layers together:

1. Backend route or source module.
2. Browser-side workflow in `static/`.
3. Template markup in `templates/`.
4. Documentation and at least one manual or automated verification step.
