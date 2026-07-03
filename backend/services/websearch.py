"""Чтение веб-страниц (read_url) с защитой от SSRF.
Веб-поиск выполняется на стороне Anthropic (серверный инструмент web_search)."""
import ipaddress
import socket
from urllib.parse import urlparse


def _is_safe_url(url: str) -> tuple[bool, str]:
    """Разрешает только http/https на публичные адреса. Блокирует запросы
    к внутренним/приватным IP (loopback, private, link-local, метаданные облака)."""
    try:
        p = urlparse(url)
    except Exception:
        return False, "некорректная ссылка"
    if p.scheme not in ("http", "https"):
        return False, "разрешены только http и https"
    host = p.hostname
    if not host:
        return False, "не указан хост"
    try:
        infos = socket.getaddrinfo(host, None)
    except Exception:
        return False, "не удалось разрешить адрес хоста"
    for info in infos:
        ip = info[4][0]
        try:
            addr = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if (addr.is_private or addr.is_loopback or addr.is_link_local
                or addr.is_reserved or addr.is_multicast or addr.is_unspecified):
            return False, "доступ к внутренним адресам запрещён"
    return True, ""


_TIMEOUT = 10.0
_MAX_BYTES = 3_000_000
_MAX_HOPS = 3


class _UnsafeRedirect(Exception):
    pass


def _fetch_html(url: str) -> str:
    """Загружает HTML вручную, ревалидируя адрес на КАЖДОМ хопе редиректа
    (issue #8): trafilatura следовал редиректам без повторной проверки, что
    позволяло увести запрос на внутренний адрес. Плюс таймаут и лимит размера."""
    import httpx

    headers = {"User-Agent": "RemTechAI/1.0 (+internal)"}
    with httpx.Client(follow_redirects=False, timeout=_TIMEOUT, headers=headers) as client:
        for _ in range(_MAX_HOPS + 1):
            ok, reason = _is_safe_url(url)
            if not ok:
                raise _UnsafeRedirect(reason)
            with client.stream("GET", url) as r:
                if r.is_redirect:
                    loc = r.headers.get("location")
                    if not loc:
                        raise _UnsafeRedirect("редирект без адреса")
                    url = str(r.url.join(loc))
                    continue
                chunks, size = [], 0
                for chunk in r.iter_bytes():
                    size += len(chunk)
                    if size > _MAX_BYTES:
                        break
                    chunks.append(chunk)
                return b"".join(chunks).decode(r.encoding or "utf-8", errors="replace")
        raise _UnsafeRedirect("слишком много редиректов")


def read_url(url: str) -> str:
    ok, reason = _is_safe_url(url)
    if not ok:
        return f"Ссылка отклонена: {reason}."

    import trafilatura

    try:
        downloaded = _fetch_html(url)
    except _UnsafeRedirect as e:
        return f"Ссылка отклонена: {e}."
    except Exception:
        return "Не удалось загрузить страницу."
    text = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
    if not text:
        return "Не удалось извлечь текст со страницы."
    return text[:8000]
