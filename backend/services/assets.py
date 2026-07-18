"""Поиск реальных фото техники/объектов для слайдов презентаций.

Гибридная схема иллюстраций: реальные фото приоритетны (точность для КП клиенту),
AI-генерация (FLUX) — запасной путь для обложки/разделов/концепций. Здесь только
локальный поиск фото по ключу в папке presentation_assets_dir.

Файлы кладутся в папку с говорящими именами, напр.:
    data/assets/equipment/xcmg-xe215.jpg
    data/assets/equipment/liugong_856h.png
Имя файла (без расширения) — набор ключевых слов; поиск по совпадению токенов.
"""
from __future__ import annotations

import os
import re

from app.config import get_settings

_IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def _norm(s: str) -> list[str]:
    """Разбивает строку на нормализованные токены (латиница/кириллица/цифры)."""
    return [t for t in re.split(r"[^0-9a-zA-Zа-яёА-ЯЁ]+", (s or "").lower()) if t]


def _dir() -> str:
    return (get_settings().presentation_assets_dir or "").strip()


def list_assets() -> list[str]:
    """Список имён файлов-фото в папке ассетов (пусто, если папки нет)."""
    d = _dir()
    if not d or not os.path.isdir(d):
        return []
    return sorted(f for f in os.listdir(d)
                  if os.path.splitext(f)[1].lower() in _IMAGE_EXT)


def find_photo(query: str) -> bytes | None:
    """Находит фото, лучше всего подходящее под query (напр. «XCMG XE215»).

    Оценка = число общих токенов имени файла и запроса; при равенстве — больше
    доля покрытия запроса. Нет папки/совпадений (нет ни одного общего токена) → None.
    """
    d = _dir()
    if not d or not os.path.isdir(d):
        return None
    q = set(_norm(query))
    if not q:
        return None
    best, best_score = None, 0.0
    for name in list_assets():
        toks = set(_norm(os.path.splitext(name)[0]))
        if not toks:
            continue
        common = len(q & toks)
        if common == 0:
            continue
        # приоритет: больше общих токенов, затем выше доля покрытия запроса
        score = common + (common / len(q)) * 0.5
        if score > best_score:
            best, best_score = name, score
    if not best:
        return None
    try:
        with open(os.path.join(d, best), "rb") as fh:
            return fh.read()
    except OSError:
        return None
