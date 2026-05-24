/**
 * Workspace page: list, restore, and delete saved jobs and CV versions.
 * All endpoints are per-user and login-protected; csrf.js handles the token
 * and bounces to /login on 401.
 */
(function () {
    function esc(v) {
        return String(v || '')
            .replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }
    function el(id) { return document.getElementById(id); }
    function fmtDate(iso) {
        if (!iso) return '';
        try { return new Date(iso).toLocaleString(); } catch (e) { return iso; }
    }

    function notify(type, title, message) {
        const region = el('toastRegion');
        if (!region) { console.log(title, message || ''); return; }
        const icon = { success: 'bi-check2-circle', warning: 'bi-exclamation-triangle', danger: 'bi-x-circle' }[type] || 'bi-info-circle';
        const toast = document.createElement('div');
        toast.className = `toast-card ${type || 'info'}`;
        toast.innerHTML = `<span class="toast-icon"><i class="bi ${icon}"></i></span>
            <span class="toast-copy"><strong>${esc(title)}</strong>${message ? `<span>${esc(message)}</span>` : ''}</span>`;
        region.appendChild(toast);
        setTimeout(() => toast.remove(), 4200);
    }

    async function renderAuthNav() {
        const slot = el('navAuth');
        if (!slot) return;
        try {
            const data = await (await fetch('/api/me')).json();
            if (data.authenticated) {
                const name = data.user.name || data.user.email;
                slot.innerHTML = `<span class="nav-user"><i class="bi bi-person-circle"></i> ${esc(name)}</span>` +
                    `<a class="btn btn-outline-secondary btn-sm" href="/logout">Logout</a>`;
            }
        } catch (e) { /* ignore */ }
    }

    // ---- Jobs -----------------------------------------------------------
    async function loadJobs() {
        const list = el('jobsList');
        try {
            const data = await (await fetch('/api/jobs')).json();
            const jobs = data.jobs || [];
            if (jobs.length === 0) {
                list.innerHTML = '<div class="ws-empty">No saved jobs yet. Optimize a CV and click “Save job + CV”.</div>';
                return;
            }
            list.innerHTML = '';
            jobs.forEach((job) => {
                const skills = (job.skills || []).slice(0, 8)
                    .map((s) => `<span class="skills-badge">${esc(s)}</span>`).join(' ');
                const item = document.createElement('div');
                item.className = 'ws-item';
                item.innerHTML = `
                    <div class="ws-item-head">
                        <div>
                            <strong>${esc(job.title || job.company || 'Saved job')}</strong>
                            <div class="ws-meta">${esc(job.company || '')} · ${fmtDate(job.created_at)} · ${esc(job.language || 'en')}</div>
                        </div>
                        <button class="btn btn-outline-danger btn-sm" data-del-job="${job.id}"><i class="bi bi-trash"></i></button>
                    </div>
                    <div class="mt-2">${skills || '<span class="text-muted">No skills extracted.</span>'}</div>`;
                item.querySelector('[data-del-job]').addEventListener('click', () => deleteJob(job.id));
                list.appendChild(item);
            });
        } catch (e) {
            list.innerHTML = '<div class="ws-empty">Could not load jobs.</div>';
        }
    }

    async function deleteJob(id) {
        if (!confirm('Delete this saved job?')) return;
        const r = await fetch('/api/jobs/' + id, { method: 'DELETE' });
        if (r.ok) { notify('success', 'Job deleted'); loadJobs(); }
        else notify('danger', 'Delete failed');
    }

    // ---- CVs + versions -------------------------------------------------
    async function loadCvs() {
        const list = el('cvList');
        try {
            const data = await (await fetch('/api/cv')).json();
            const docs = data.documents || [];
            if (docs.length === 0) {
                list.innerHTML = '<div class="ws-empty">No saved CVs yet.</div>';
                return;
            }
            list.innerHTML = '';
            for (const doc of docs) {
                // Fetch full doc to get its versions.
                const full = await (await fetch('/api/cv/' + doc.id)).json();
                const d = full.document || doc;
                const item = document.createElement('div');
                item.className = 'ws-item';
                const versions = (d.versions || []).map((v) => `
                    <div class="ws-version">
                        <span>${esc(v.label || 'Version')} · <span class="ws-meta">${fmtDate(v.created_at)}${v.score != null ? ' · ' + v.score + '%' : ''}</span></span>
                        <span class="d-flex gap-1">
                            <button class="btn btn-outline-primary btn-sm" data-view="${v.id}"><i class="bi bi-eye"></i></button>
                            <button class="btn btn-outline-success btn-sm" data-restore="${v.id}"><i class="bi bi-arrow-counterclockwise"></i></button>
                            <button class="btn btn-outline-danger btn-sm" data-del-ver="${v.id}"><i class="bi bi-trash"></i></button>
                        </span>
                    </div>`).join('');
                item.innerHTML = `
                    <div class="ws-item-head">
                        <div>
                            <strong>${esc(d.name)}</strong>
                            <div class="ws-meta">${esc(d.source_format || 'latex')} · ${d.version_count} version(s) · updated ${fmtDate(d.updated_at)}</div>
                        </div>
                        <button class="btn btn-outline-danger btn-sm" data-del-doc="${d.id}"><i class="bi bi-trash"></i></button>
                    </div>
                    <div class="ws-versions">${versions}</div>`;

                item.querySelector('[data-del-doc]').addEventListener('click', () => deleteDoc(d.id));
                item.querySelectorAll('[data-view]').forEach((b) => b.addEventListener('click', () => viewVersion(b.dataset.view)));
                item.querySelectorAll('[data-restore]').forEach((b) => b.addEventListener('click', () => restoreVersion(b.dataset.restore)));
                item.querySelectorAll('[data-del-ver]').forEach((b) => b.addEventListener('click', () => deleteVersion(b.dataset.delVer)));
                list.appendChild(item);
            }
        } catch (e) {
            list.innerHTML = '<div class="ws-empty">Could not load CVs.</div>';
        }
    }

    let modal = null;
    async function viewVersion(id) {
        const data = await (await fetch('/api/cv/versions/' + id)).json();
        const v = data.version || {};
        el('versionModalTitle').textContent = v.label || 'CV version';
        el('versionLatex').value = v.latex || '';
        if (!modal) modal = new bootstrap.Modal(el('versionModal'));
        modal.show();
    }

    async function restoreVersion(id) {
        const r = await fetch('/api/cv/versions/' + id + '/restore', { method: 'POST' });
        if (r.ok) { notify('success', 'Version restored', 'A fresh copy was added to the top.'); loadCvs(); }
        else notify('danger', 'Restore failed');
    }

    async function deleteVersion(id) {
        if (!confirm('Delete this version?')) return;
        const r = await fetch('/api/cv/versions/' + id, { method: 'DELETE' });
        if (r.ok) { notify('success', 'Version deleted'); loadCvs(); }
        else notify('danger', 'Delete failed');
    }

    async function deleteDoc(id) {
        if (!confirm('Delete this CV and all its versions?')) return;
        const r = await fetch('/api/cv/' + id, { method: 'DELETE' });
        if (r.ok) { notify('success', 'CV deleted'); loadCvs(); }
        else notify('danger', 'Delete failed');
    }

    document.addEventListener('DOMContentLoaded', function () {
        renderAuthNav();
        loadJobs();
        loadCvs();
        const copyBtn = el('versionCopyBtn');
        if (copyBtn) copyBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(el('versionLatex').value).then(() => notify('success', 'Copied'));
        });
    });
})();
