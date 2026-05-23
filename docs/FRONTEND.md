# Frontend Guide

The frontend is plain HTML, CSS, and JavaScript. There is no build step.

## Files

| File | Purpose |
| --- | --- |
| `templates/index.html` | Markup for the main optimizer workflow. |
| `templates/interview.html` | Markup for interview prep. |
| `static/style.css` | Shared design tokens, layout, cards, buttons, forms, loading overlay. |
| `static/animations.js` | Presentation-only behavior for the optimizer page. |
| `static/script.js` | Optimizer workflow logic. |
| `static/interview.css` | Interview-specific components. |
| `static/interview.js` | Interview workflow logic. |

## Main Optimizer Page

The optimizer workflow is controlled by `static/script.js`.

Important elements:

| ID | Meaning |
| --- | --- |
| `jobDescription` | Job text input. |
| `jobAnalysis` | Parsed job result panel. |
| `cvSection` | CV input panel, hidden until a job is parsed. |
| `cvLatex` | Raw LaTeX CV input. |
| `actionButtons` | Optimize action area. |
| `resultsSection` | Analysis and optimized CV result area. |
| `optimizedLatexEditor` | Editable optimized LaTeX. |
| `latexPreview` | Highlighted LaTeX preview. |
| `pdfPreviewFrame` | Inline PDF preview iframe. |
| `pdfPreviewStatus` | PDF render status text. |

### Optimizer State Flow

```text
Initial page
  -> parseJobDescription()
    -> show #jobAnalysis and #cvSection
  -> uploadCV()
    -> show #actionButtons
  -> optimizeCV()
    -> show #resultsSection
    -> renderPDFPreview()
```

### Important Globals

`static/script.js` uses a few global values:

- `window.currentJobAnalysis` - parsed job data used by optimize.
- `window.currentProposals` - current optional proposal snippets.
- `currentPdfUrl` - browser object URL for the latest PDF preview.

When adding new frontend state, prefer keeping it local unless multiple
functions need to access it.

## Interview Page

The interview workflow is controlled by `static/interview.js`.

Important elements:

| ID | Meaning |
| --- | --- |
| `cvInput` | CV text/LaTeX context. |
| `jobInput` | Job offer context. |
| `levelSeg` | Seniority segmented control. |
| `domainChips` | Domain checkboxes. |
| `countRange` | Question count slider. |
| `extraInstructions` | User guidance for generation. |
| `sessionSummary` | Generated session summary. |
| `questionsContainer` | Generated question cards. |

### Interview State Flow

```text
Load page
  -> prefillContext() from sessionStorage
  -> generateQuestions()
    -> renderSession()
      -> buildQuestionCard()
      -> optional CodeMirror upgrade
  -> requestReview(questionId)
    -> renderReview()
```

## Styling Conventions

The app uses a shared token system in `:root` inside `static/style.css`.

Use existing variables before adding new colors:

- `--brand-500`, `--brand-600`, `--brand-700`
- `--ink`, `--ink-soft`, `--muted`
- `--line`, `--bg`, `--card`
- `--success`, `--warning`, `--danger`
- `--radius`, `--radius-sm`, `--radius-lg`

Common classes:

- `.hidden` - hides an element.
- `.loading.show` - shows the full-screen loading overlay.
- `.form-section` - grouped form/result panel.
- `.stat-card` - metric card.
- `.skills-badge` - skill pill.
- `.recommendation` - recommendation callout.
- `.proposal-card` - optional addition card.

## Dynamic HTML Safety

When rendering model or user-controlled text, escape it first.

Existing helper functions:

- `escapeHtml(value)` in `static/script.js`
- `escapeHtml(str)` in `static/interview.js`

Prefer `textContent` for simple text nodes. Use `innerHTML` only when markup is
needed, and escape all dynamic values inside the string.

## Adding A New Optimizer Action

1. Add the button or panel in `templates/index.html`.
2. Give it a stable `id`.
3. Add behavior in `static/script.js`.
4. Add loading and error states.
5. If it calls the backend, add or update the route in `main.py`.
6. Document the API change in `docs/API_REFERENCE.md`.

## Adding A New Interview Feature

1. Add controls or containers in `templates/interview.html`.
2. Wire events in `static/interview.js`.
3. Update `src/interview_agent.py` if the feature changes generation/review
   behavior.
4. Keep fallback behavior working.
5. Document the new request/response fields.

## PDF Preview Lifecycle

The optimizer stores the current preview URL in `currentPdfUrl`.

When a new PDF is rendered:

1. `renderLatexToPdfBlob()` calls `/api/render-latex`.
2. The returned PDF blob becomes an object URL.
3. The iframe `src` is set to that object URL.
4. The previous object URL is revoked to avoid leaking browser memory.

If the LaTeX editor changes, the preview is marked stale by changing
`pdfPreviewStatus`.

## External Frontend Dependencies

Loaded from CDNs:

- Bootstrap CSS and JS.
- Bootstrap Icons.
- Google Fonts.
- CodeMirror on the interview page, loaded lazily from `static/interview.js`.

CodeMirror is a progressive enhancement. If it fails to load, coding answers
fall back to a normal textarea.

