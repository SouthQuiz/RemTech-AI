"""Issue #8 — редирект на внутренний адрес отклоняется (ревалидация каждого хопа)."""
import httpx

from services import websearch


class _FakeResp:
    def __init__(self, redirect_to=None, body=""):
        self._redir = redirect_to
        self._body = body
        self.encoding = "utf-8"
        self.url = httpx.URL("http://public.example/")

    @property
    def is_redirect(self):
        return self._redir is not None

    @property
    def headers(self):
        return {"location": self._redir} if self._redir else {}

    def iter_bytes(self):
        yield self._body.encode()

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _FakeClient:
    def __init__(self, resp, **_):
        self._resp = resp

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def stream(self, method, url, **_):   # принимаем headers/extensions
        return self._resp


def test_redirect_to_internal_is_blocked(monkeypatch):
    # публичный IP-литерал (проходит стартовую проверку), затем редирект на loopback
    resp = _FakeResp(redirect_to="http://127.0.0.1/admin")
    monkeypatch.setattr(httpx, "Client", lambda **k: _FakeClient(resp))
    out = websearch.read_url("http://8.8.8.8/")
    assert "отклонена" in out.lower()


def test_direct_internal_is_blocked():
    out = websearch.read_url("http://169.254.169.254/latest/meta-data/")
    assert "отклонена" in out.lower()


def test_pinning_rejects_host_resolving_internal(monkeypatch):
    # #8 — DNS-rebinding: хост резолвится во внутренний IP → отказ до подключения
    import socket

    def fake_getaddrinfo(host, port, *a, **kw):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", port or 80))]

    # _is_safe_url пройдёт? нет — он тоже резолвит; подменяем на публичный там,
    # а пиннинг внутри _fetch_html поймает внутренний адрес
    monkeypatch.setattr(websearch.socket, "getaddrinfo", fake_getaddrinfo)
    import pytest
    with pytest.raises(websearch._UnsafeRedirect):
        websearch._resolve_pinned_ip("evil.example", 80)
