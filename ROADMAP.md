# Auto-CV Roadmap

Planned features to make Auto-CV feel like a complete, professional product.
Items are grouped by priority and theme. See the **Recommended Build Order** at
the bottom for what to ship first.

## Status (implemented)

The following are now shipped (✅) or partially shipped (🟡):

- ✅ **Accounts + login** — email/password auth, per-user data isolation (`src/auth.py`, `src/models.py`).
- ✅ **Public-web hardening** — debug off by default, sanitized errors, security headers, CSRF, rate limiting, upload size cap (`src/config.py`, `main.py`).
- ✅ **PDF/DOCX upload** — extracted and converted to LaTeX (`src/file_extract.py`, `/api/extract-cv`).
- ✅ **Non-tech skill extraction** — LLM-based, any profession, with curated fallback (`src/parser.py`).
- ✅ **ATS score breakdown** — matched/missing keywords, requirement coverage, weak sections, priority fixes (`src/matcher.py`).
- ✅ **Cover letter + outreach** — cover letter, recruiter, LinkedIn, email (`src/cover_letter.py`, `/api/cover-letter`).
- ✅ **Template selector** — ATS-simple / modern / compact / academic (`src/cv_templates.py`).
- ✅ **Multilingual output** — EN/FR/ES through rewrite + proposals + cover letter.
- ✅ **Before/after diff** — section-by-section accept / reject / edit (`static/review.js`).
- ✅ **Workspace + version history** — saved jobs and CV versions, restore/compare (`src/workspace.py`, `/workspace`).
- 🟡 **Interactive section editor** — per-section editing is available within the review/diff panel; a standalone field-by-field editor for *all* sections is still open.

See `docs/DEVELOPMENT.md` → "Web App: Accounts, Database & Security" for setup.

---

## Top Priority

### 1. Before/After Diff View
Show exactly what the AI changed in the CV, section by section, with controls to:
- **Accept**
- **Reject**
- **Edit manually**

This is probably the most important professional feature.

### 2. Support PDF/DOCX CV Upload
The app is currently LaTeX-focused, but most users have PDF or Word CVs. Add a flow that can:
- Upload PDF/DOCX → extract content → optimize → export

### 3. ATS Score Breakdown
Replace the single match score with a detailed breakdown:
- Missing keywords
- Matched keywords
- Weak sections
- Role requirements covered
- Priority improvements

### 4. Template Selector
Let users choose a CV style:
- ATS simple
- Modern tech
- Academic
- Executive
- Compact one-page
- LaTeX professional

### 5. Cover Letter Generator
After optimizing the CV, generate:
- Cover letter
- Short recruiter message
- LinkedIn message
- Email application text

---

## Very Useful Features

### 6. Job Application Workspace
Let users save multiple job offers and CV versions:
- Job A → tailored CV
- Job B → tailored CV
- Job C → tailored CV

### 7. CV Version History
Keep previous optimized versions and allow restore/compare.

### 8. Smart Suggestions Instead of Auto-Adding
For missing skills, ask before adding. Example:
> "You did not mention Docker. Do you actually have Docker experience?"

Then let the user choose:
- **Yes, add it**
- **No, add as a learning/project goal**

### 9. Interactive CV Editor
Instead of only a raw LaTeX textarea, add editable sections:
- Summary
- Experience
- Skills
- Projects
- Education

### 10. Multilingual CV
Generate the CV in:
- English
- French
- Spanish

With professional tone adaptation per language.

---

## Modern AI Features

### 11. AI CV Chat
A chat panel for natural-language edits, e.g.:
- "Make my summary more senior"
- "Make this bullet more measurable"
- "Shorten to one page"
- "Adapt this CV for data engineer"

### 12. Bullet Point Improver
For each experience bullet, offer variants:
- Weak version
- Stronger version
- Impact-focused version
- ATS-friendly version

### 13. Honesty Checker
Detect when the AI proposes something not clearly present in the original CV
and ask the user to confirm before including it.

### 14. Interview Prep Upgrade
Build on the existing interview page with:
- Timed mock interview
- Voice answer practice
- Score per question
- Saved feedback
- Final interview readiness report

### 15. Skill Gap Roadmap
After analyzing a job, show:
- Skills you already have
- Skills missing
- Project ideas to prove missing skills
- Learning resources / categories

---

## Recommended Build Order

The five features that would make the app feel most complete and professional first:

1. Before/After diff with accept/reject
2. PDF/DOCX CV upload
3. ATS score breakdown
4. Template selector
5. Cover letter + recruiter message generator
