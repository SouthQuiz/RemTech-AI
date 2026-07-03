"""Issue #12/#15 — единый структурный логгер приложения.

Заменяет разрозненные print()/проглоченные исключения. Настраивается один раз;
формат с временем/уровнем/именем логгера, вывод в stdout (перехватывается Docker/ЛВС).
"""
import logging
import sys

_configured = False


def setup_logging(level: str = "INFO") -> None:
    global _configured
    if _configured:
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    ))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level.upper())
    # уменьшаем шум сторонних библиотек
    logging.getLogger("httpx").setLevel(logging.WARNING)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)
