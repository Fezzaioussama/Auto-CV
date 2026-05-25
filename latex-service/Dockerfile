FROM debian:bookworm-slim

# TeX Live: a broad-but-not-full set covering the app's CV templates
# (fontawesome5, enumitem, CormorantGaramond and other fonts live in
# texlive-fonts-extra). If a template ever needs a package not included here,
# either add its texlive-* package or switch the first RUN to `texlive-full`.
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 python3-pip \
        texlive-latex-base \
        texlive-latex-recommended \
        texlive-latex-extra \
        texlive-fonts-recommended \
        texlive-fonts-extra \
        texlive-xetex \
        lmodern \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip3 install --no-cache-dir --break-system-packages -r requirements.txt
COPY server.py .

# Defense in depth: compile untrusted LaTeX as a non-root user.
RUN useradd -m -u 10001 texuser
USER texuser

ENV PORT=8080
EXPOSE 8080
# Few workers, generous per-request timeout (a big CV can take a few seconds).
CMD ["sh", "-c", "gunicorn -b 0.0.0.0:${PORT} -w 2 -t 120 server:app"]
