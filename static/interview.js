/**
 * Interview Prep — front-end logic.
 * Talks to /api/interview/questions and /api/interview/review.
 */

// ---- State ----
const editors = {};        // qid -> CodeMirror instance (coding questions)
const questionData = {};    // qid -> question object (sent back to the reviewer)
let selectedLevel = '';     // '', 'junior', 'mid', 'senior'

// CodeMirror language -> mode mapping
const CM_MODES = {
    python: 'python',
    py: 'python',
    javascript: 'javascript',
    js: 'javascript',
    typescript: 'text/typescript',
    ts: 'text/typescript',
    node: 'javascript',
    java: 'text/x-java',
    c: 'text/x-csrc',
    'c++': 'text/x-c++src',
    cpp: 'text/x-c++src',
    'c#': 'text/x-csharp',
    csharp: 'text/x-csharp',
    go: 'text/x-go',
    sql: 'sql',
};

const LANG_OPTIONS = ['python', 'javascript', 'typescript', 'java', 'c++', 'c#', 'go', 'sql'];

// ---- CodeMirror lazy loader ----
// Loaded on demand and treated as a pure enhancement: if the CDN is slow or
// blocked, coding answers fall back to a plain <textarea>, and the page/buttons
// are never blocked waiting for it.
const CM_BASE = 'https://cdn.jsdelivr.net/npm/codemirror@5.65.16';
const CM_CSS = [`${CM_BASE}/lib/codemirror.min.css`, `${CM_BASE}/theme/material-darker.min.css`];
const CM_JS = [
    `${CM_BASE}/lib/codemirror.min.js`,
    `${CM_BASE}/mode/python/python.min.js`,
    `${CM_BASE}/mode/javascript/javascript.min.js`,
    `${CM_BASE}/mode/clike/clike.min.js`,
    `${CM_BASE}/mode/sql/sql.min.js`,
    `${CM_BASE}/addon/edit/closebrackets.min.js`,
];
let _cmPromise = null;
function ensureCodeMirror() {
    if (_cmPromise) return _cmPromise;
    _cmPromise = new Promise((resolve) => {
        if (window.CodeMirror) return resolve(true);
        CM_CSS.forEach(href => {
            const l = document.createElement('link');
            l.rel = 'stylesheet';
            l.href = href;
            document.head.appendChild(l);
        });
        let i = 0, settled = false;
        const done = () => { if (!settled) { settled = true; resolve(!!window.CodeMirror); } };
        setTimeout(done, 6000); // never wait forever for a blocked CDN
        const loadNext = () => {
            if (settled) return;
            if (i >= CM_JS.length) return done();
            const s = document.createElement('script');
            s.src = CM_JS[i++];
            s.async = false;      // preserve order: core must run before modes
            s.onload = loadNext;
            s.onerror = done;     // give up gracefully -> textarea fallback
            document.body.appendChild(s);
        };
        loadNext();
    });
    return _cmPromise;
}

// ---- Init ----
console.log('[interview.js v4] script loaded');

function wireButtons() {
    const gen = document.getElementById('generateBtn');
    if (gen) gen.addEventListener('click', generateQuestions);
    const hero = document.getElementById('heroGenerate');
    if (hero) hero.addEventListener('click', generateQuestions); // href still scrolls to #setup
    const demo = document.getElementById('demoBtn');
    if (demo) demo.addEventListener('click', loadDemoContext);
    console.log('[interview.js] buttons wired:', { gen: !!gen, hero: !!hero, demo: !!demo });
}

function init() {
    prefillContext();
    wireLevelSelector();
    wireCountRange();
    wireNavbarScroll();
    wireButtons();
    ensureCodeMirror(); // start fetching the editor in the background
}

// `defer` runs this before DOMContentLoaded, but guard for the already-loaded
// case too so the buttons always get wired.
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
} else {
    init();
}

function prefillContext() {
    const cv = sessionStorage.getItem('autocv_cv_latex');
    const job = sessionStorage.getItem('autocv_job_text');
    let filled = [];
    if (cv) { document.getElementById('cvInput').value = cv; filled.push('CV'); }
    if (job) { document.getElementById('jobInput').value = job; filled.push('job offer'); }
    if (filled.length) {
        const note = document.getElementById('contextNote');
        note.innerHTML = `<i class="bi bi-check-circle-fill"></i> Loaded your ${filled.join(' and ')} from the optimizer. Edit if you like, then generate.`;
        note.classList.remove('hidden');
    }
}

function wireLevelSelector() {
    document.querySelectorAll('#levelSeg .seg-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('#levelSeg .seg-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            selectedLevel = btn.dataset.level || '';
        });
    });
}

function wireCountRange() {
    const range = document.getElementById('countRange');
    const out = document.getElementById('countValue');
    range.addEventListener('input', () => { out.textContent = range.value; });
}

function wireNavbarScroll() {
    const nav = document.getElementById('navbar');
    if (!nav) return;
    window.addEventListener('scroll', () => {
        nav.classList.toggle('scrolled', window.scrollY > 10);
    });
}

function getSelectedDomains() {
    return Array.from(document.querySelectorAll('#domainChips input:checked')).map(c => c.value);
}

function showLoading(title) {
    document.getElementById('loadingTitle').textContent = title;
    document.getElementById('loadingIndicator').classList.add('show');
}
function hideLoading() {
    document.getElementById('loadingIndicator').classList.remove('show');
}

function escapeHtml(str) {
    return String(str == null ? '' : str)
        .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;').replace(/'/g, '&#39;');
}

// ---- Generate questions ----
async function generateQuestions() {
    console.log('[interview] generateQuestions() called');
    const cv = document.getElementById('cvInput').value.trim();
    const job = document.getElementById('jobInput').value.trim();
    const domains = getSelectedDomains();
    const count = parseInt(document.getElementById('countRange').value, 10);

    if (!cv && !job) {
        alert('Add your CV and/or the job offer first.');
        return;
    }
    if (!domains.length) {
        alert('Pick at least one question domain.');
        return;
    }

    const extra = (document.getElementById('extraInstructions')?.value || '').trim();

    showLoading('Designing your interview…');
    try {
        const res = await fetch('/api/interview/questions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                cv_latex: cv,
                job_description: job,
                level: selectedLevel,
                domains,
                count,
                extra_instructions: extra,
            }),
        });
        const data = await res.json();
        if (!res.ok || data.error) throw new Error(data.error || 'Request failed');
        renderSession(data);
    } catch (err) {
        alert('Could not generate questions: ' + err.message);
    } finally {
        hideLoading();
    }
}

function renderSession(data) {
    // Reset state
    Object.keys(editors).forEach(k => delete editors[k]);
    Object.keys(questionData).forEach(k => delete questionData[k]);

    const summary = document.getElementById('sessionSummary');
    const role = escapeHtml(data.role_title || 'Target role');
    const level = escapeHtml((data.detected_level || 'mid'));
    const fallbackPill = data.fallback ? '<span class="ss-pill"><i class="bi bi-wifi-off"></i> offline templates</span>' : '';
    summary.innerHTML = `
        <span class="ss-title"><i class="bi bi-clipboard-check"></i> ${role}</span>
        <span class="ss-pill">Level: ${level}</span>
        <span class="ss-pill">${data.questions.length} questions</span>
        ${fallbackPill}
        <button type="button" class="btn btn-light btn-sm ss-regen" id="regenBtn">
            <i class="bi bi-arrow-repeat"></i> Regenerate
        </button>`;
    summary.classList.remove('hidden');
    document.getElementById('regenBtn').addEventListener('click', generateQuestions);

    // If the model couldn't be used, say so plainly so the output isn't mistaken
    // for real, CV-grounded questions.
    const container = document.getElementById('questionsContainer');
    container.innerHTML = '';
    if (data.fallback) {
        const warn = document.createElement('div');
        warn.className = 'fallback-flag';
        warn.innerHTML = `<i class="bi bi-exclamation-triangle"></i> These are generic offline templates — the AI model couldn't be reached`
            + (data.error ? ` (${escapeHtml(data.error)})` : '')
            + `. Check the server/model, then click <b>Regenerate</b>.`;
        container.appendChild(warn);
    }
    data.questions.forEach(q => container.appendChild(buildQuestionCard(q)));

    // Upgrade coding answers to a CodeMirror editor once it's available. Until
    // then (or if the CDN is unreachable) the plain textarea with starter code
    // is fully usable, so the feature never depends on the editor loading.
    if (data.questions.some(q => q.domain === 'coding')) {
        ensureCodeMirror().then(() => {
            data.questions.forEach(q => { if (q.domain === 'coding') initEditor(q); });
        });
    }

    summary.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function buildQuestionCard(q) {
    questionData[q.id] = q;
    const card = document.createElement('div');
    card.className = 'q-card reveal in';
    card.id = `qcard-${q.id}`;

    const criteria = (q.evaluation_criteria || [])
        .map(c => `<span class="crit">${escapeHtml(c)}</span>`).join('');

    let answerArea;
    if (q.domain === 'coding') {
        const langOpts = LANG_OPTIONS.map(l =>
            `<option value="${l}" ${l === (q.language || 'python') ? 'selected' : ''}>${l}</option>`).join('');
        answerArea = `
            <div class="answer-wrap">
                <div class="answer-toolbar">
                    <span class="answer-label"><i class="bi bi-terminal"></i> Your code</span>
                    <select class="form-select form-select-sm lang-select" id="lang-${q.id}" onchange="onLangChange(${q.id})">${langOpts}</select>
                </div>
                <textarea id="code-${q.id}">${escapeHtml(q.starter_code || '')}</textarea>
            </div>`;
    } else {
        answerArea = `
            <div class="answer-wrap">
                <span class="answer-label"><i class="bi bi-pencil"></i> Your answer</span>
                <textarea class="answer-text" id="ans-${q.id}" placeholder="Type your answer here…"></textarea>
            </div>`;
    }

    card.innerHTML = `
        <div class="q-head">
            <span class="q-index">${q.id}</span>
            <span class="q-domain ${q.domain}">${escapeHtml(q.domain_label || q.domain)}</span>
            <span class="q-level">${escapeHtml(q.level || '')}</span>
            <span class="q-title">${escapeHtml(q.title || '')}</span>
        </div>
        <div class="q-body">${escapeHtml(q.question)}</div>
        ${q.rationale ? `<div class="q-rationale"><i class="bi bi-info-circle"></i> ${escapeHtml(q.rationale)}</div>` : ''}
        ${criteria ? `<div class="q-criteria">${criteria}</div>` : ''}
        ${answerArea}
        <div class="mt-3">
            <button class="btn btn-primary btn-sm" id="reviewBtn-${q.id}" onclick="requestReview(${q.id})">
                <i class="bi bi-robot"></i> Get AI review
            </button>
        </div>
        <div class="review hidden" id="review-${q.id}"></div>`;
    return card;
}

function cmModeFor(lang) {
    return CM_MODES[(lang || '').toLowerCase()] || 'text/plain';
}

function initEditor(q) {
    const ta = document.getElementById(`code-${q.id}`);
    if (!ta || typeof CodeMirror === 'undefined') return; // graceful fallback to textarea
    const editor = CodeMirror.fromTextArea(ta, {
        mode: cmModeFor(q.language || 'python'),
        theme: 'material-darker',
        lineNumbers: true,
        indentUnit: 4,
        autoCloseBrackets: true,
        viewportMargin: Infinity,
    });
    editors[q.id] = editor;
}

function onLangChange(qid) {
    const lang = document.getElementById(`lang-${qid}`).value;
    if (editors[qid]) editors[qid].setOption('mode', cmModeFor(lang));
}

function getAnswer(q) {
    if (q.domain === 'coding') {
        if (editors[q.id]) return editors[q.id].getValue();
        const ta = document.getElementById(`code-${q.id}`);
        return ta ? ta.value : '';
    }
    const ta = document.getElementById(`ans-${q.id}`);
    return ta ? ta.value : '';
}

// ---- Review ----
async function requestReview(qid) {
    const q = questionData[qid];
    const answer = getAnswer(q).trim();
    if (!answer) { alert('Write an answer or some code first.'); return; }

    const lang = q.domain === 'coding'
        ? (document.getElementById(`lang-${qid}`)?.value || q.language || '')
        : '';
    const btn = document.getElementById(`reviewBtn-${qid}`);
    const original = btn.innerHTML;
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Reviewing…';

    const job = document.getElementById('jobInput').value.trim();
    try {
        const res = await fetch('/api/interview/review', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question: q, answer, language: lang, job_description: job }),
        });
        const data = await res.json();
        if (!res.ok || data.error) throw new Error(data.error || 'Request failed');
        renderReview(qid, data.review);
    } catch (err) {
        alert('Review failed: ' + err.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-arrow-repeat"></i> Re-review';
    }
}

function scoreClass(s) { return s >= 70 ? 'good' : s >= 45 ? 'mid' : 'low'; }

function renderReview(qid, r) {
    const el = document.getElementById(`review-${qid}`);
    const sClass = scoreClass(r.score);

    const list = (arr) => (arr && arr.length)
        ? `<ul>${arr.map(x => `<li>${escapeHtml(x)}</li>`).join('')}</ul>`
        : '<p class="text-muted mb-0">—</p>';

    const correctness = (r.correctness && r.correctness !== 'n/a')
        ? `<span class="review-correctness ${escapeHtml(r.correctness)}">${escapeHtml(r.correctness.replace('_', ' '))}</span>`
        : '';

    let codingBlock = '';
    if (r.is_coding) {
        const cx = r.complexity || {};
        codingBlock += `
            <div class="complexity-row">
                <span class="cx-pill"><b>Time</b> · ${escapeHtml(cx.time || 'n/a')}</span>
                <span class="cx-pill"><b>Space</b> · ${escapeHtml(cx.space || 'n/a')}</span>
            </div>`;
        if (r.optimized_code && r.optimized_code.trim()) {
            const codeId = `opt-${qid}`;
            codingBlock += `
                <div class="opt-block">
                    <h6><i class="bi bi-lightning-charge-fill" style="color:var(--brand-600)"></i> Optimized version
                        <button class="btn btn-outline-secondary btn-sm copy-btn ms-auto" onclick="copyCode('${codeId}', this)"><i class="bi bi-clipboard"></i> Copy</button>
                    </h6>
                    <pre id="${codeId}"><code>${escapeHtml(r.optimized_code)}</code></pre>
                    ${r.optimized_notes ? `<p class="opt-notes">${escapeHtml(r.optimized_notes)}</p>` : ''}
                </div>`;
        }
    }

    const modelBlock = r.model_answer && r.model_answer.trim()
        ? `<div class="model-block">
               <h6><i class="bi bi-stars" style="color:var(--violet-600)"></i> What a strong answer looks like</h6>
               <p>${escapeHtml(r.model_answer)}</p>
           </div>`
        : '';

    const followUps = (r.follow_up_questions && r.follow_up_questions.length)
        ? `<div class="follow-ups">
               <h6><i class="bi bi-arrow-return-right"></i> Likely follow-up questions</h6>
               ${list(r.follow_up_questions)}
           </div>`
        : '';

    const fallbackFlag = r.fallback
        ? '<div class="fallback-flag"><i class="bi bi-exclamation-triangle"></i> The AI reviewer was unreachable — this is a heuristic estimate. Try again shortly.</div>'
        : '';

    el.innerHTML = `
        ${fallbackFlag}
        <div class="review-head">
            <div class="score-badge ${sClass}"><span>${r.score}</span><small>/ 100</small></div>
            <div>
                <div class="review-verdict">${escapeHtml(r.verdict || 'Reviewed')} ${correctness}</div>
            </div>
        </div>
        ${r.summary ? `<p class="review-summary">${escapeHtml(r.summary)}</p>` : ''}
        ${codingBlock}
        <div class="review-grid">
            <div class="review-col strengths">
                <h6><i class="bi bi-hand-thumbs-up"></i> Strengths</h6>
                ${list(r.strengths)}
            </div>
            <div class="review-col improvements">
                <h6><i class="bi bi-wrench-adjustable"></i> To improve</h6>
                ${list(r.improvements)}
            </div>
        </div>
        ${modelBlock}
        ${followUps}`;
    el.classList.remove('hidden');
    el.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function copyCode(codeId, btn) {
    const text = document.getElementById(codeId).innerText;
    navigator.clipboard.writeText(text).then(() => {
        const original = btn.innerHTML;
        btn.innerHTML = '<i class="bi bi-check2"></i> Copied';
        setTimeout(() => { btn.innerHTML = original; }, 1500);
    });
}

// ---- Demo content ----
function loadDemoContext() {
    document.getElementById('cvInput').value = `John Carter — Backend Software Engineer

Experience:
- Software Engineer at DataFlow (3 years): built REST APIs in Python/Django, scaled a PostgreSQL-backed service to 2M daily requests, introduced Redis caching cutting p95 latency by 40%.
- Junior Developer at WebStart (1.5 years): React front-ends, Node.js services, AWS (EC2, S3, Lambda).

Skills: Python, Django, PostgreSQL, Redis, Docker, AWS, REST APIs, JavaScript, React, CI/CD, Git.

Education: B.Sc. Computer Science.`;

    document.getElementById('jobInput').value = `Senior Backend Engineer — FinTech Co.

We need an experienced backend engineer to design and scale our payments platform.

Requirements:
- 5+ years with Python and a web framework (Django/FastAPI)
- Strong with relational databases (PostgreSQL), query optimization
- Experience designing distributed systems handling high throughput
- AWS, Docker, Kubernetes
- Familiarity with message queues (Kafka/RabbitMQ)

Nice to have: experience with payment systems, observability (Prometheus/Grafana).`;

    const note = document.getElementById('contextNote');
    note.innerHTML = '<i class="bi bi-shuffle"></i> Demo CV and offer loaded — hit "Generate interview questions".';
    note.classList.remove('hidden');
}
