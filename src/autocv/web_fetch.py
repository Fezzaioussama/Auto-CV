"""Fetch a job description from a URL — safely.

Users usually have a link (LinkedIn, Indeed, a careers page) rather than the
pasted text. Fetching arbitrary user-supplied URLs server-side is a classic SSRF
risk: a crafted URL could point at internal services, cloud metadata endpoints
(169.254.169.254), or localhost. This module hardens against that by:

* allowing only ``http`` / ``https`` schemes,
* resolving the host and rejecting any private / loopback / link-local /
  reserved / multicast IP (including IPv6 and IPv4-mapped forms),
* re-validating the target on every redirect hop (so a public URL can't bounce
  to an internal one),
* re-checking the IP of the socket actually connected (so DNS rebinding — a
  host that resolves public for the check, then private for the connection —
  is blocked too), and ignoring proxy env vars that would bypass that check,
* capping the response size and time.

It returns readable plain text extracted from the page, ready to feed the parser.
"""

from __future__ import annotations

import ipaddress
import socket
from html.parser import HTMLParser
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.connection import HTTPConnection, HTTPSConnection
from urllib3.connectionpool import HTTPConnectionPool, HTTPSConnectionPool


class FetchError(Exception):
    """Raised when a URL is unsafe, unreachable, or yields no usable text."""


MAX_BYTES = 2_000_000          # stop reading after ~2 MB
MAX_REDIRECTS = 4
TIMEOUT = (5, 10)              # (connect, read) seconds
_UA = "Mozilla/5.0 (compatible; Auto-CV/1.0; +https://auto-cv.local)"


def _ip_is_public(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return not (
        ip.is_private or ip.is_loopback or ip.is_link_local
        or ip.is_reserved or ip.is_multicast or ip.is_unspecified
    )


def _assert_safe_url(url: str) -> None:
    """Raise FetchError unless ``url`` is http(s) and resolves to public IPs."""
    parts = urlparse(url)
    if parts.scheme not in ("http", "https"):
        raise FetchError("Only http(s) URLs are supported.")
    host = parts.hostname
    if not host:
        raise FetchError("That doesn't look like a valid URL.")

    try:
        infos = socket.getaddrinfo(host, parts.port or (443 if parts.scheme == "https" else 80))
    except socket.gaierror as exc:
        raise FetchError("Could not resolve that host.") from exc

    resolved = {info[4][0] for info in infos}
    if not resolved:
        raise FetchError("Could not resolve that host.")
    for ip in resolved:
        if not _ip_is_public(ip):
            raise FetchError("That URL points to a non-public address and was blocked.")


class _PublicPeerMixin:
    """Refuse the connection unless the connected peer is a public address.

    ``_assert_safe_url`` validates the hostname's DNS answer, but the HTTP
    client resolves it again when connecting. Checking the socket's real peer
    closes that time-of-check/time-of-use gap (DNS rebinding).
    """

    def _new_conn(self):
        sock = super()._new_conn()
        if not _ip_is_public(sock.getpeername()[0]):
            sock.close()
            raise FetchError("That URL points to a non-public address and was blocked.")
        return sock


class _PublicHTTPConnection(_PublicPeerMixin, HTTPConnection):
    pass


class _PublicHTTPSConnection(_PublicPeerMixin, HTTPSConnection):
    pass


class _PublicHTTPPool(HTTPConnectionPool):
    ConnectionCls = _PublicHTTPConnection


class _PublicHTTPSPool(HTTPSConnectionPool):
    ConnectionCls = _PublicHTTPSConnection


class _PublicOnlyAdapter(HTTPAdapter):
    def init_poolmanager(self, *args, **kwargs):
        super().init_poolmanager(*args, **kwargs)
        self.poolmanager.pool_classes_by_scheme = {
            "http": _PublicHTTPPool,
            "https": _PublicHTTPSPool,
        }


def _session() -> requests.Session:
    session = requests.Session()
    # Proxy env vars would make the proxy the socket peer, hiding the target.
    session.trust_env = False
    adapter = _PublicOnlyAdapter()
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


class _TextExtractor(HTMLParser):
    """Collect visible text, skipping script/style/noscript content."""

    _SKIP = {"script", "style", "noscript", "head", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_depth = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP:
            self._skip_depth += 1

    def handle_endtag(self, tag):
        if tag in self._SKIP and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data):
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self.parts.append(text)


def _html_to_text(html: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:  # noqa: BLE001 - malformed HTML shouldn't crash the request
        pass
    # Join, then collapse runs of blank lines.
    lines = [ln.strip() for ln in "\n".join(parser.parts).splitlines()]
    out, blank = [], False
    for ln in lines:
        if ln:
            out.append(ln)
            blank = False
        elif not blank:
            out.append("")
            blank = True
    return "\n".join(out).strip()


def fetch_url_text(url: str) -> str:
    """Fetch ``url`` safely and return extracted plain text.

    Follows up to :data:`MAX_REDIRECTS` redirects, re-validating each hop.
    Raises :class:`FetchError` on any unsafe target, network error, or empty
    result.
    """
    url = (url or "").strip()
    if not url:
        raise FetchError("No URL provided.")
    if not urlparse(url).scheme:
        url = "https://" + url  # be forgiving about a missing scheme

    with _session() as session:
        return _fetch(session, url)


def _fetch(session: requests.Session, url: str) -> str:
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        _assert_safe_url(current)
        try:
            resp = session.get(
                current,
                headers={"User-Agent": _UA, "Accept": "text/html,application/xhtml+xml"},
                timeout=TIMEOUT,
                allow_redirects=False,
                stream=True,
            )
        except requests.RequestException as exc:
            raise FetchError("Could not fetch that URL.") from exc

        # Manually follow redirects so we can re-validate each destination.
        if resp.is_redirect or resp.is_permanent_redirect:
            location = resp.headers.get("Location")
            resp.close()
            if not location:
                raise FetchError("The URL redirected without a destination.")
            current = requests.compat.urljoin(current, location)
            continue

        if resp.status_code != 200:
            resp.close()
            raise FetchError(f"The page returned HTTP {resp.status_code}.")

        ctype = resp.headers.get("Content-Type", "")
        if "html" not in ctype and "text" not in ctype:
            resp.close()
            raise FetchError("That URL is not an HTML/text page.")

        chunks, total = [], 0
        for chunk in resp.iter_content(chunk_size=16384, decode_unicode=False):
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total >= MAX_BYTES:
                break
        resp.close()

        html = b"".join(chunks).decode(resp.encoding or "utf-8", errors="replace")
        text = _html_to_text(html)
        if len(text) < 40:
            raise FetchError("Couldn't extract a readable job description from that page.")
        return text

    raise FetchError("Too many redirects.")
