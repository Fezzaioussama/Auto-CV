"""SSRF protection for the job-URL fetcher (security-critical)."""

import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "src"))

from autocv import web_fetch as wf  # noqa: E402

import http.server  # noqa: E402
import threading  # noqa: E402

import pytest  # noqa: E402

from conftest import register  # noqa: E402


def test_private_and_metadata_ips_classified_non_public():
    for ip in ["127.0.0.1", "10.0.0.1", "192.168.1.1", "169.254.169.254", "::1",
               "fe80::1", "::ffff:127.0.0.1"]:
        assert wf._ip_is_public(ip) is False, ip
    for ip in ["8.8.8.8", "1.1.1.1"]:
        assert wf._ip_is_public(ip) is True, ip


def test_assert_safe_url_blocks_internal_and_bad_schemes():
    for url in ["http://127.0.0.1/", "http://169.254.169.254/latest/meta-data/",
                "http://10.1.2.3/", "http://[::1]/", "ftp://example.com/",
                "file:///etc/passwd"]:
        try:
            wf._assert_safe_url(url)
            assert False, f"expected block for {url}"
        except wf.FetchError:
            pass


def test_fetch_endpoint_blocks_internal_url(client):
    register(client, "ssrf@example.com")
    r = client.post("/api/fetch-job-url", json={"url": "http://169.254.169.254/latest/meta-data/"})
    assert r.status_code == 422
    assert "blocked" in r.get_json()["error"].lower()


def test_fetch_endpoint_requires_login(client):
    assert client.post("/api/fetch-job-url", json={"url": "https://example.com"}).status_code == 401


def test_connection_to_private_peer_blocked_even_if_dns_check_passes(monkeypatch):
    """DNS rebinding: the pre-check passes but the real connection is private."""

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # pragma: no cover - must never be reached
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(b"<p>" + b"internal secret " * 10 + b"</p>")

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        monkeypatch.setattr(wf, "_assert_safe_url", lambda url: None)
        with pytest.raises(wf.FetchError, match="blocked"):
            wf.fetch_url_text(f"http://127.0.0.1:{server.server_port}/")
    finally:
        server.shutdown()
