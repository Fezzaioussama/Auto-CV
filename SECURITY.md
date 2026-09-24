# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Instead, report
them privately through GitHub's
[private vulnerability reporting](https://github.com/Fezzaioussama/Auto-CV/security/advisories/new)
("Security" tab → "Report a vulnerability"). Include steps to reproduce and the
affected version or commit. You should get a response within a few days.

## Deploying safely

Auto-CV handles CVs, which contain personal data. If you host it publicly:

- Keep `FLASK_ENV` unset (production) and `FLASK_DEBUG=0`.
- Set a random `SECRET_KEY` of at least 32 characters and a Postgres `DATABASE_URL`.
- Never commit `.env`; rotate any key that was ever exposed.
- Protect the LaTeX compile service with a strong `COMPILE_TOKEN`.
- Use a shared `RATELIMIT_STORAGE_URI` (e.g. Redis) when running several workers.
- Serve over HTTPS and set `PROXY_FIX_HOPS` to match your proxy setup.

See `.env.example` for every security-related setting.
