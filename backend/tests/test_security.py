"""Безопасность — тесты SSRF-фильтра read_url (_is_safe_url)."""
import pytest

from services.websearch import _is_safe_url


@pytest.mark.parametrize("url", [
    "http://127.0.0.1:8000/x",              # loopback
    "http://169.254.169.254/latest/meta",   # облачные метаданные
    "http://10.0.0.5/",                      # private A
    "http://192.168.1.10/",                  # private C
    "http://[::1]/",                          # loopback IPv6
    "ftp://example.com/file",                # запрещённая схема
    "file:///etc/passwd",                    # запрещённая схема
    "http:///nohost",                        # нет хоста
])
def test_blocked_urls(url):
    ok, _ = _is_safe_url(url)
    assert ok is False


@pytest.mark.parametrize("url", [
    "http://8.8.8.8/",       # публичный IP-литерал (без DNS)
    "https://1.1.1.1/path",
])
def test_allowed_public(url):
    ok, reason = _is_safe_url(url)
    assert ok is True and reason == ""
