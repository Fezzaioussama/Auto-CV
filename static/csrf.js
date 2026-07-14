/**
 * CSRF + auth helper.
 *
 * The backend protects state-changing requests with Flask-WTF CSRF and requires
 * a logged-in session for the heavy endpoints. Rather than touch every existing
 * fetch() call, we wrap window.fetch once to:
 *   1. attach the X-CSRFToken header (read from the <meta> tag) to same-origin
 *      mutating requests, and
 *   2. bounce the user to /login when the server says the session is gone (401).
 */
(function () {
    function csrfToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.getAttribute('content') : null;
    }

    const MUTATING = ['POST', 'PUT', 'PATCH', 'DELETE'];
    const originalFetch = window.fetch.bind(window);

    window.fetch = function (input, init) {
        init = init || {};
        const method = (
            init.method ||
            (typeof input === 'object' && input && input.method) ||
            'GET'
        ).toUpperCase();
        const url = typeof input === 'string' ? input : (input && input.url) || '';
        const sameOrigin = url.startsWith('/') || url.startsWith(window.location.origin);

        if (sameOrigin && MUTATING.includes(method)) {
            const headers = new Headers(
                init.headers ||
                (typeof input === 'object' && input && input.headers) ||
                {}
            );
            const token = csrfToken();
            if (token && !headers.has('X-CSRFToken')) {
                headers.set('X-CSRFToken', token);
            }
            init.headers = headers;
            if (!init.credentials) init.credentials = 'same-origin';
        }

        return originalFetch(input, init).then(function (response) {
            if (response.status === 401 && sameOrigin) {
                const next = encodeURIComponent(
                    window.location.pathname + window.location.search
                );
                window.location.href = '/login?next=' + next;
            }
            return response;
        });
    };

    window.AutoCV = window.AutoCV || {};
    window.AutoCV.csrfToken = csrfToken;
})();
