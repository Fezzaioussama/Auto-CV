# Auto-CV LaTeX compile service

A tiny stateless microservice that compiles LaTeX to PDF with `pdflatex` inside
a TeX Live container. The main Auto-CV app runs on Vercel, which can't run a TeX
toolchain, so it offloads PDF rendering here.

```
Browser ──▶ Auto-CV (Vercel) ──POST /compile──▶ this service (Docker + TeX Live)
                  ▲                                      │
                  └──────────────  PDF  ◀────────────────┘
```

## Endpoints

- `POST /compile` — body `{"latex": "<full document>"}`, returns
  `{"success": bool, "pdf_base64": str|null, "log": str, "returncode": int, "timed_out": bool}`.
  Requires header `Authorization: Bearer <COMPILE_TOKEN>` on every request; compilation is disabled if the token is missing or shorter than 32 characters.
- `GET /health` — `{"ok": true, "pdflatex": true}` when TeX is available.

## Configuration (service env vars)

| Var | Purpose | Default |
|-----|---------|---------|
| `COMPILE_TOKEN` | Shared secret the app must send, at least 32 characters. **Set this in production.** | _(empty or short → disabled)_ |
| `COMPILE_TIMEOUT` | Max seconds per compile | `60` |
| `MAX_LATEX_BYTES` | Reject larger documents | `2097152` (2 MB) |
| `PORT` | Port to listen on (most hosts set this) | `8080` |

## Deploy

Generate a token first and keep it — you'll paste it both here and in Vercel:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

### Render (Docker) — easiest

1. Render → **New** → **Web Service** → connect this repo.
2. **Root Directory:** `latex-service`. Render auto-detects the `Dockerfile`.
3. Add env var `COMPILE_TOKEN` = the token you generated.
4. Create. The first build is slow (TeX Live is large); afterwards it's cached.
5. Note the public URL, e.g. `https://your-latex-service.onrender.com`.
6. Verify: `curl https://<your-url>/health` → `{"ok": true, "pdflatex": true}`.

> Render's free tier sleeps when idle, so the first PDF after a pause waits for a
> cold start (~30–60 s). A paid instance stays warm.

### Railway / Fly.io

- **Railway:** New Project → Deploy from repo → set root to `latex-service` →
  add `COMPILE_TOKEN`. Railway builds the Dockerfile and assigns a URL.
- **Fly.io:** from `latex-service/`, `fly launch --dockerfile Dockerfile`
  (Fly creates a `fly.toml`), then
  `fly secrets set COMPILE_TOKEN=<token>` and `fly deploy`.

## Wire it into the Vercel app

In the Auto-CV Vercel project → **Settings → Environment Variables**, add:

| Var | Value |
|-----|-------|
| `LATEX_COMPILE_URL` | `https://<your-service-url>/compile` |
| `LATEX_COMPILE_TOKEN` | the same `COMPILE_TOKEN` |

Redeploy the Vercel app. `/api/render-latex` will now compile through this
service. With these unset, the app falls back to local `pdflatex` (dev) — so
local development is unchanged.

## Local test

```bash
cd latex-service
docker build -t autocv-latex .
export COMPILE_TOKEN="$(python3 -c 'import secrets;print(secrets.token_hex(32))')"
docker run -d -p 8080:8080 -e COMPILE_TOKEN autocv-latex
curl -s localhost:8080/compile -H "Authorization: Bearer $COMPILE_TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"latex":"\\documentclass{article}\\begin{document}Hello\\end{document}"}' \
  | python3 -c "import sys,json,base64; d=json.load(sys.stdin); open('out.pdf','wb').write(base64.b64decode(d['pdf_base64'])); print('wrote out.pdf', d['returncode'])"
```
