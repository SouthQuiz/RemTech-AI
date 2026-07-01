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


def read_url(url: str) -> str:
    ok, reason = _is_safe_url(url)
    if not ok:
        return f"Ссылка отклонена: {reason}."

    import trafilatura

    downloaded = trafilatura.fetch_url(url)
    if not downloaded:
        return "Не удалось загрузить страницу."
    text = trafilatura.extract(downloaded, include_comments=False, include_tables=True)
    if not text:
        return "Не удалось извлечь текст со страницы."
    return text[:8000]
