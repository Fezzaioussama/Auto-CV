/**
 * Feature glue for the optimizer page:
 *   - auth-aware navigation (Sign in / account + Logout)
 *   - template picker population
 *   - ATS breakdown rendering
 *   - cover letter / outreach generation
 *   - "save job + CV" to the user's workspace
 *
 * Exposes window.AutoCVFeatures.onOptimized(data), called by script.js after a
 * successful optimization.
 */
(function () {
    function esc(v) {
        return String(v || '')
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
    function el(id) { return document.getElementById(id); }

    // ---- Auth nav -------------------------------------------------------
    async function renderAuthNav() {
        const slot = el('navAuth');
        if (!slot) return;
        try {
            const data = await (await fetch('/api/me')).json();
            if (data.authenticated) {
                const name = data.user.name || data.user.email;
                slot.innerHTML =
                    `<span class="nav-user" title="${esc(data.user.email)}"><i class="bi bi-person-circle"></i> ${esc(name)}</span>` +
                    `<a class="btn btn-outline-secondary btn-sm" href="/logout">Logout</a>`;
            } else {
                slot.innerHTML =
                    `<a class="navlink" href="/login">Sign in</a>` +
                    `<a class="btn btn-primary btn-sm" href="/register">Sign up</a>`;
            }
        } catch (e) {
            slot.innerHTML = `<a class="navlink" href="/login">Sign in</a>`;
        }
    }

    // ---- Templates ------------------------------------------------------
    async function populateTemplates() {
        const select = el('cvTemplate');
        if (!select) return;
        try {
            const data = await (await fetch('/api/templates')).json();
            (data.templates || []).forEach((t) => {
                const opt = document.createElement('option');
                opt.value = t.id;
                opt.textContent = t.name;
                opt.title = t.description || '';
                select.appendChild(opt);
            });
        } catch (e) { /* picker stays empty; backend uses a default */ }
    }

    // ---- ATS breakdown --------------------------------------------------
    function renderAts(analysis) {
        const ats = analysis && analysis.ats;
        const sectionEl = el('atsSection');
        if (!ats || !sectionEl) {
            if (sectionEl) sectionEl.classList.add('hidden');
            return;
        }
        sectionEl.classList.remove('hidden');

        const matched = (ats.matched_keywords || []).length;
        const missing = (ats.missing_keywords || []).length;
        const covered = ats.requirements_covered_count || 0;
        const total = ats.requirements_total || 0;
        el('atsStats').innerHTML = `
            <div class="stat-card"><h4>Keywords matched</h4><div class="value text-success">${matched}</div></div>
            <div class="stat-card"><h4>Keywords missing</h4><div class="value text-danger">${missing}</div></div>
            <div class="stat-card"><h4>Requirements covered</h4><div class="value">${covered}/${total}</div></div>`;

        const reqs = ats.requirements_covered || [];
        el('atsRequirements').innerHTML = reqs.length
            ? reqs.map((r) => `
                <li class="${r.covered ? 'covered' : 'uncovered'}">
                    <i class="bi ${r.covered ? 'bi-check-circle-fill' : 'bi-circle'}"></i>
                    <span>${esc(r.requirement)}</span>
                </li>`).join('')
            : '<li class="text-muted">No explicit requirements detected.</li>';

        const prios = ats.priority_improvements || [];
        el('atsPriorities').innerHTML = prios.length
            ? prios.map((p) => `<li><i class="bi bi-arrow-right-short"></i> ${esc(p)}</li>`).join('')
            : '<li class="text-muted">Looking strong — no high-priority gaps.</li>';

        const weak = ats.weak_sections || [];
        el('atsWeakSections').innerHTML = weak.length
            ? `<div class="ats-weak"><strong>Missing standard sections:</strong> ` +
              weak.map((w) => `<span class="skills-badge missing">${esc(w)}</span>`).join(' ') + `</div>`
            : '';
    }

    // ---- Cover letter / outreach ---------------------------------------
    const KIND_LABELS = {
        cover_letter: 'Cover letter',
        recruiter_message: 'Recruiter message',
        linkedin_message: 'LinkedIn note',
        email: 'Application email'
    };

    async function generateCover() {
        const checked = Array.from(document.querySelectorAll('#coverKinds input:checked'))
            .map((c) => c.value);
        if (checked.length === 0) {
            window.notify && window.notify('warning', 'Pick at least one', 'Choose what to generate.');
            return;
        }
        const out = el('coverLetterResults');
        const btn = el('generateCoverBtn');
        btn.disabled = true;
        out.innerHTML = '<p class="text-muted"><i class="bi bi-hourglass-split"></i> Generating…</p>';
        try {
            const response = await fetch('/api/cover-letter', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    cv_latex: (window.getOptimizedLatex && window.getOptimizedLatex()) || window.currentCvLatex || '',
                    job_description: window.currentJobAnalysis || {},
                    kinds: checked,
                    language: window.currentLanguage || 'en'
                })
            });
            const data = await response.json();
            if (!response.ok) {
                out.innerHTML = '';
                window.notify && window.notify('danger', 'Generation failed', data.error || 'Try again.');
                return;
            }
            out.innerHTML = '';
            checked.forEach((kind) => {
                const content = (data.results || {})[kind] || '';
                const card = document.createElement('div');
                card.className = 'cover-card';
                card.innerHTML = `
                    <div class="cover-card-head">
                        <strong>${esc(KIND_LABELS[kind] || kind)}</strong>
                        <button type="button" class="btn btn-outline-secondary btn-sm cover-copy">
                            <i class="bi bi-clipboard"></i> Copy
                        </button>
                    </div>
                    <textarea class="form-control" rows="${kind === 'linkedin_message' ? 3 : 8}">${esc(content)}</textarea>`;
                card.querySelector('.cover-copy').addEventListener('click', () => {
                    const ta = card.querySelector('textarea');
                    navigator.clipboard.writeText(ta.value).then(() => {
                        window.notify && window.notify('success', 'Copied', KIND_LABELS[kind] + ' copied.');
                    });
                });
                out.appendChild(card);
            });
        } catch (e) {
            out.innerHTML = '';
            window.notify && window.notify('danger', 'Generation failed', 'An error occurred.');
        } finally {
            btn.disabled = false;
        }
    }

    // ---- Save to workspace ---------------------------------------------
    async function saveToWorkspace() {
        const btn = el('saveWorkspaceBtn');
        const status = el('saveStatus');
        const job = window.currentJobAnalysis || {};
        const jobText = (el('jobDescription') && el('jobDescription').value.trim()) || job.text || '';
        const latex = (window.getOptimizedLatex && window.getOptimizedLatex()) || '';
        if (!jobText || !latex) {
            window.notify && window.notify('warning', 'Nothing to save', 'Optimize a CV first.');
            return;
        }
        btn.disabled = true;
        status.textContent = 'Saving…';
        try {
            // 1) Save the job.
            const jobResp = await fetch('/api/jobs', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    raw_text: jobText,
                    company: (job.company_info && job.company_info.company_name) || null,
                    parsed: job,
                    language: window.currentLanguage || 'en'
                })
            });
            const jobData = await jobResp.json();
            if (!jobResp.ok) throw new Error(jobData.error || 'Could not save job');
            const jobId = jobData.job.id;

            // 2) Save the CV as a first version tied to that job.
            const name = (el('saveCvName') && el('saveCvName').value.trim())
                || ('CV — ' + (jobData.job.company || 'job') );
            const cvResp = await fetch('/api/cv', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    latex: latex,
                    name: name,
                    source_format: 'latex',
                    job_id: jobId,
                    analysis: (window.currentOptimization || {}).analysis || null,
                    language: window.currentLanguage || 'en',
                    label: 'Tailored for this offer'
                })
            });
            const cvData = await cvResp.json();
            if (!cvResp.ok) throw new Error(cvData.error || 'Could not save CV');

            status.innerHTML = `Saved! <a href="/workspace">Open workspace</a>`;
            window.notify && window.notify('success', 'Saved to workspace', 'Job and tailored CV stored.');
        } catch (e) {
            status.textContent = '';
            window.notify && window.notify('danger', 'Save failed', e.message || 'Try again.');
        } finally {
            btn.disabled = false;
        }
    }

    function onOptimized(data) {
        renderAts(data.analysis);
    }

    document.addEventListener('DOMContentLoaded', function () {
        renderAuthNav();
        populateTemplates();
        const gen = el('generateCoverBtn');
        if (gen) gen.addEventListener('click', generateCover);
        const save = el('saveWorkspaceBtn');
        if (save) save.addEventListener('click', saveToWorkspace);
    });

    window.AutoCVFeatures = { onOptimized: onOptimized };
})();
