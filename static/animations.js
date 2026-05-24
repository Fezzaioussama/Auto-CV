/**
 * Auto-CV - UI animation layer.
 * Pure presentation: scroll reveals, navbar state, button ripples,
 * count-up stats, the circular match gauge, and the live stepper.
 * It observes elements that script.js already updates, so no app
 * logic is duplicated or overridden here.
 */
(function () {
    'use strict';

    const RING_CIRCUMFERENCE = 2 * Math.PI * 56; // r=56 in the SVG gauge

    function init() {
        setupNavbar();
        setupReveal();
        setupRipple();
        watchMatchScore();
        watchWorkflowState();
        document.addEventListener('autocv:state-change', updateStepper);
        updateStepper();
    }

    /* ---------------- Navbar shrink on scroll ---------------- */
    function setupNavbar() {
        const nav = document.getElementById('navbar');
        if (!nav) return;
        const onScroll = () => nav.classList.toggle('scrolled', window.scrollY > 12);
        onScroll();
        window.addEventListener('scroll', onScroll, { passive: true });
    }

    /* ---------------- Scroll reveal ---------------- */
    function setupReveal() {
        const items = document.querySelectorAll('.reveal:not(.in)');
        if (!('IntersectionObserver' in window) || !items.length) {
            items.forEach((el) => el.classList.add('in'));
            return;
        }
        const io = new IntersectionObserver((entries) => {
            entries.forEach((entry) => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('in');
                    io.unobserve(entry.target);
                }
            });
        }, { threshold: 0.12, rootMargin: '0px 0px -8% 0px' });
        items.forEach((el) => io.observe(el));
    }

    /* ---------------- Button ripple ---------------- */
    function setupRipple() {
        document.addEventListener('click', (e) => {
            const btn = e.target.closest('.btn');
            if (!btn) return;
            const rect = btn.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height);
            const ripple = document.createElement('span');
            ripple.className = 'ripple';
            ripple.style.width = ripple.style.height = size + 'px';
            ripple.style.left = (e.clientX - rect.left - size / 2) + 'px';
            ripple.style.top = (e.clientY - rect.top - size / 2) + 'px';
            btn.appendChild(ripple);
            setTimeout(() => ripple.remove(), 600);
        });
    }

    /* ---------------- Count-up helper ---------------- */
    function countUp(el, duration) {
        if (!el) return;
        const raw = el.textContent;
        const match = raw.match(/-?\d+/);
        if (!match) return;

        const target = parseInt(match[0], 10);
        const prefix = raw.slice(0, match.index);
        const suffix = raw.slice(match.index + match[0].length);
        const start = performance.now();
        duration = duration || 950;

        function tick(now) {
            const p = Math.min(1, (now - start) / duration);
            const eased = 1 - Math.pow(1 - p, 3);
            el.textContent = prefix + Math.round(target * eased) + suffix;
            if (p < 1) {
                requestAnimationFrame(tick);
            } else {
                el.textContent = prefix + target + suffix;
            }
        }
        requestAnimationFrame(tick);
    }

    /* ---------------- Match score: ring + counters ---------------- *
     * script.js writes #matchProgressBar.style.width on every optimize.
     * We observe that one attribute (never its text), so re-running the
     * optimizer re-animates the gauge without any feedback loop.        */
    function watchMatchScore() {
        const bar = document.getElementById('matchProgressBar');
        const ring = document.getElementById('matchRing');
        const score = document.getElementById('matchScore');
        if (!bar) return;

        const render = () => {
            const pct = Math.max(0, Math.min(100, parseFloat(bar.style.width) || 0));
            if (ring) {
                ring.setAttribute('stroke-dashoffset', String(RING_CIRCUMFERENCE * (1 - pct / 100)));
                if (score) {
                    // Tint the gauge to match the score colour set by script.js.
                    const color = getComputedStyle(score).color;
                    if (color) ring.style.stroke = color;
                }
            }
            countUp(score, 1100);
            countUp(document.getElementById('skillsMatched'));
            countUp(document.getElementById('missingSkills'));
            updateStepper();
        };

        const mo = new MutationObserver(() => {
            // Defer so script.js finishes writing every related value first.
            clearTimeout(render._t);
            render._t = setTimeout(render, 40);
        });
        mo.observe(bar, { attributes: true, attributeFilter: ['style'] });
    }

    /* ---------------- Workflow counters + stepper ---------------- */
    function watchWorkflowState() {
        const panel = document.getElementById('jobAnalysis');
        if (!panel) return;
        let wasHidden = panel.classList.contains('hidden');

        const mo = new MutationObserver(() => {
            const hidden = panel.classList.contains('hidden');
            if (wasHidden && !hidden) {
                countUp(document.getElementById('jobSkillsCount'));
                countUp(document.getElementById('jobRequirementsCount'));
                countUp(document.getElementById('jobQualificationsCount'));
            }
            wasHidden = hidden;
            updateStepper();
        });
        ['jobAnalysis', 'cvSection', 'actionButtons', 'resultsSection'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) {
                mo.observe(el, { attributes: true, attributeFilter: ['class'] });
            }
        });
    }

    /* ---------------- Stepper progress ---------------- */
    function updateStepper() {
        const stepper = document.getElementById('stepper');
        if (!stepper) return;

        const visible = (id) => {
            const el = document.getElementById(id);
            return el && !el.classList.contains('hidden');
        };
        const resultsReady = visible('resultsSection');
        const optimizeReady = visible('actionButtons');
        const cvReady = visible('cvSection') || visible('jobAnalysis');

        let current; // the active step
        const done = []; // completed steps
        if (resultsReady) {
            current = 3; done.push(1, 2);
        } else if (optimizeReady) {
            current = 3; done.push(1, 2);
        } else if (cvReady) {
            current = 2; done.push(1);
        } else {
            current = 1;
        }

        stepper.querySelectorAll('.node').forEach((node) => {
            const step = parseInt(node.dataset.step, 10);
            node.classList.toggle('done', done.includes(step));
            node.classList.toggle('active', step === current);
        });
        stepper.querySelectorAll('.line').forEach((line) => {
            const idx = parseInt(line.dataset.line, 10);
            line.classList.toggle('done', current > idx);
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
