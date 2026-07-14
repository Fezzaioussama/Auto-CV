/**
 * Before/after review with accept · reject · edit.
 *
 * For each section the optimizer rewrote, the user sees the original ("before")
 * next to the tailored version ("after") and decides what to keep. Their
 * choices recompose the LaTeX in the editor, so nothing is applied silently and
 * every change is reversible. Editing a section turns this into a lightweight
 * per-section editor too.
 */
(function () {
    const section = document.getElementById('reviewSection');
    const container = document.getElementById('reviewContainer');
    const acceptAllBtn = document.getElementById('acceptAllBtn');
    const rejectAllBtn = document.getElementById('rejectAllBtn');

    let diffs = [];
    let states = [];       // per-section: { choice: 'after'|'before', edited: string|null }
    let baseLatex = '';

    function esc(value) {
        return String(value || '')
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    // Apply the user's choices to the optimizer's LaTeX (which ships all "after"
    // bodies) by swapping back any rejected/edited section bodies.
    function recompose() {
        let latex = baseLatex;
        diffs.forEach((d, i) => {
            const st = states[i];
            const chosen = st.edited != null
                ? st.edited
                : (st.choice === 'before' ? d.before : d.after);
            if (chosen !== d.after && latex.indexOf(d.after) !== -1) {
                latex = latex.replace(d.after, chosen);
            }
        });
        if (typeof window.setOptimizedLatex === 'function') {
            window.setOptimizedLatex(latex);
        }
    }

    function stateLabel(i) {
        const st = states[i];
        if (st.edited != null) return '<i class="bi bi-pencil"></i> Edited';
        if (st.choice === 'before') return '<i class="bi bi-x-circle"></i> Reverted to original';
        return '<i class="bi bi-check2-circle"></i> Using tailored version';
    }

    function renderCard(d, i) {
        const card = document.createElement('div');
        card.className = 'review-card';
        card.dataset.index = i;
        card.innerHTML = `
            <div class="review-head">
                <div>
                    <strong>${esc(d.title)}</strong>
                    <span class="review-kind">${esc(d.kind || 'section')}</span>
                </div>
                <div class="review-actions btn-group btn-group-sm">
                    <button type="button" class="btn btn-outline-success" data-act="accept">Accept</button>
                    <button type="button" class="btn btn-outline-secondary" data-act="reject">Reject</button>
                    <button type="button" class="btn btn-outline-primary" data-act="edit">Edit</button>
                </div>
            </div>
            <div class="review-diff">
                <div class="diff-col before">
                    <h6>Before</h6><pre>${esc(d.before) || '<em>(empty)</em>'}</pre>
                </div>
                <div class="diff-col after">
                    <h6>After</h6><pre>${esc(d.after)}</pre>
                </div>
            </div>
            <textarea class="form-control review-edit hidden" rows="6" spellcheck="false"></textarea>
            <div class="review-state">${stateLabel(i)}</div>`;

        const editBox = card.querySelector('.review-edit');
        const stateEl = card.querySelector('.review-state');

        function refresh() {
            stateEl.innerHTML = stateLabel(i);
            card.classList.toggle('is-rejected', states[i].choice === 'before' && states[i].edited == null);
        }

        card.querySelectorAll('[data-act]').forEach((btn) => {
            btn.addEventListener('click', () => {
                const act = btn.dataset.act;
                if (act === 'accept') {
                    states[i] = { choice: 'after', edited: null };
                    editBox.classList.add('hidden');
                } else if (act === 'reject') {
                    states[i] = { choice: 'before', edited: null };
                    editBox.classList.add('hidden');
                } else if (act === 'edit') {
                    const current = states[i].edited != null
                        ? states[i].edited
                        : (states[i].choice === 'before' ? d.before : d.after);
                    editBox.value = current;
                    editBox.classList.toggle('hidden');
                }
                refresh();
                recompose();
            });
        });

        editBox.addEventListener('input', () => {
            states[i].edited = editBox.value;
            refresh();
            recompose();
        });

        return card;
    }

    function render(sectionDiffs, optimizedLatex) {
        diffs = Array.isArray(sectionDiffs) ? sectionDiffs : [];
        baseLatex = optimizedLatex || '';

        if (!section || !container) {
            return;
        }
        if (diffs.length === 0) {
            section.classList.add('hidden');
            return;
        }
        section.classList.remove('hidden');
        states = diffs.map(() => ({ choice: 'after', edited: null }));
        container.innerHTML = '';
        diffs.forEach((d, i) => container.appendChild(renderCard(d, i)));
    }

    if (acceptAllBtn) {
        acceptAllBtn.addEventListener('click', () => {
            render(diffs, baseLatex); // resets all cards to "after"
            recompose();
        });
    }
    if (rejectAllBtn) {
        rejectAllBtn.addEventListener('click', () => {
            states = diffs.map(() => ({ choice: 'before', edited: null }));
            container.querySelectorAll('.review-card').forEach((card) => {
                card.classList.add('is-rejected');
                card.querySelector('.review-state').innerHTML =
                    '<i class="bi bi-x-circle"></i> Reverted to original';
                card.querySelector('.review-edit').classList.add('hidden');
            });
            recompose();
        });
    }

    window.AutoCVReview = { render: render };
})();
