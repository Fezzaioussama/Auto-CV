# Maintenance Guide

Use this guide when changing or debugging Auto-CV.

## Before Changing Code

1. Identify the affected workflow:
   - optimizer
   - PDF rendering
   - interview generation
   - interview review
2. Read the related docs:
   - [ARCHITECTURE.md](ARCHITECTURE.md)
   - [API_REFERENCE.md](API_REFERENCE.md)
   - [FRONTEND.md](FRONTEND.md)
3. Run the app once with sample data to understand the current behavior.

## Change Checklist

For backend changes:

- Validate request inputs in `main.py`.
- Keep response keys compatible with the frontend.
- Preserve fallback behavior when the LLM is unavailable.
- Log enough detail for failures, but avoid dumping unnecessary private data.
- Update `docs/API_REFERENCE.md` if request or response shapes change.
- Keep `src/llm_client.py`, `.env.example`, and `docs/DEVELOPMENT.md`
  synchronized if provider/model configuration changes.

For frontend changes:

- Keep element IDs in sync with JavaScript selectors.
- Use `.hidden` for workflow visibility.
- Show useful loading and failure states.
- Escape dynamic text before inserting with `innerHTML`.
- Test on both the optimizer and interview page if shared CSS changed.

For LLM prompt changes:

- Keep strict output contracts.
- Keep JSON parsing or LaTeX validation in place.
- Test both successful LLM output and fallback behavior.
- Avoid changing output keys unless frontend code is updated too.

For LLM provider/configuration changes:

- Make the change in `src/llm_client.py`.
- Update `.env.example`.
- Update [DEVELOPMENT.md](DEVELOPMENT.md).
- Confirm `/api/llm/health` still returns a secret-free configuration string.
- Test both `SOURCE_LLM=local` and `SOURCE_LLM=openrouter` when possible.

For LaTeX changes:

- Test a minimal article document.
- Test a realistic CV document.
- Test missing package behavior.
- Test invalid LaTeX and confirm a useful error is returned.

## Current Verification Commands

Run the app:

```bash
python main.py
```

Check active LLM configuration:

```bash
curl http://localhost:5000/api/llm/health
```

Run available scripts:

```bash
python test_smart_cv.py
python test_vllm_cv.py
```

Manual smoke test:

1. Open `http://localhost:5000`.
2. Load sample job.
3. Load sample CV.
4. Optimize CV.
5. Render PDF.
6. Insert one proposed addition if available.
7. Render PDF again.
8. Open `/interview`.
9. Load demo context.
10. Generate questions.
11. Submit one answer for review.

## Common Failure Modes

| Symptom | Likely cause | Where to inspect |
| --- | --- | --- |
| Job parsing returns few skills | `common_skills` does not contain the role's vocabulary | `src/parser.py` |
| Match score seems wrong | Skill aliases or normalization are incomplete | `src/matcher.py` |
| Optimize takes a long time | LLM endpoint is slow or multiple section rewrites are running | `src/matcher.py`, `src/section_rewriter.py` |
| `/api/llm/health` reports the wrong provider | `.env` is missing or `SOURCE_LLM` is not set as expected | `.env`, `.env.example`, `src/llm_client.py` |
| OpenRouter calls are skipped | `SOURCE_LLM=openrouter` but `OPENROUTER_API_KEY` is empty | `.env`, `src/llm_client.py` |
| Rewritten sections is empty | LLM unavailable or outputs failed validation | `src/section_rewriter.py` |
| PDF preview fails | Invalid LaTeX, missing package, or missing `pdflatex` | `main.py`, terminal logs |
| Interview page shows fallback templates | LLM generation failed or returned invalid JSON | `src/interview_agent.py` |
| Buttons do nothing | Template ID changed or script failed to load | Browser console, `static/*.js` |
| Styling is stale | Browser cached old static assets | query versions in templates |

## Repository Hygiene

The project has a `.gitignore` that excludes:

- `.env` and local secret/config files.
- Python caches and virtual environments.
- test/type-check/cache outputs.
- generated CV artifacts under `output/`.
- LaTeX build artifacts such as `.aux`, `.log`, `.out`, and `.toc`.

Keep `output/.gitkeep` tracked so the folder exists, but do not commit
generated PDFs, `.tex`, or LaTeX logs. If a generated artifact is accidentally
tracked, remove it from git rather than changing `.gitignore` to allow it.

## Adding A New API Endpoint

1. Add the route in `main.py`.
2. Validate `request.get_json()` safely.
3. Return consistent JSON:

```json
{
  "success": true
}
```

or:

```json
{
  "error": "Human-readable error"
}
```

4. Add frontend code if the browser uses it.
5. Document the endpoint in `docs/API_REFERENCE.md`.
6. Add a test or manual smoke test step.

## Adding Or Changing An LLM Task

1. Add or reuse a task identifier in `llm_client.Task`.
2. Call `complete(...)` or `chat(...)` from `src/llm_client.py`.
3. Pass the task name so per-task model overrides work.
4. Add matching variables to `.env.example` if the task needs an override.
5. Keep the caller's fallback path intact when the LLM returns `None`.
6. Document the new task in [ARCHITECTURE.md](ARCHITECTURE.md) and
   [DEVELOPMENT.md](DEVELOPMENT.md).

## Adding A New CV Feature

Example features: diff view, template selector, cover letter generator, CV
version history, ATS score breakdown.

Recommended implementation path:

1. Define the user-visible workflow first.
2. Decide whether the feature is pure frontend, backend-only, or both.
3. Define the response shape before writing the frontend.
4. Add the backend logic.
5. Add the UI with loading/error/empty states.
6. Add sample data if needed.
7. Update documentation.

## Adding A New Skill Or Alias

Skills appear in two important places:

- `src/parser.py` for extracting skills from the job offer.
- `src/matcher.py` for canonicalizing aliases and checking CV coverage.

When adding a new skill:

1. Add it to `JobDescriptionParser._load_common_skills`.
2. Add aliases to `SKILL_ALIASES` if users commonly write it differently.
3. Test with a job description and a CV that uses an alias.

## LLM Response Validation

Do not trust model output directly.

Existing validation patterns:

- Strip `<think>...</think>` blocks.
- Strip markdown fences.
- Extract JSON from noisy responses.
- Reject suspicious LaTeX that contains whole-document commands when only a
  section body is expected.
- Reject rewrites that add missing skills the original section did not contain.

Preserve these checks when refactoring.

## Documentation Maintenance

Update docs in the same change when:

- A route changes.
- A request or response field changes.
- A new environment variable is added.
- A new source module is added.
- A developer workflow changes.
- A feature changes visible behavior.
- `.env.example`, `.gitignore`, or `ROADMAP.md` changes.

The docs should describe the current code, not the planned ideal version.
