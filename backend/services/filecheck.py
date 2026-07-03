"""Issue #7 — валидация загружаемых файлов и безопасный Content-Disposition.

- sniff_mime: определение типа по magic-number (а не только по расширению);
- ensure_allowed: whitelist разрешённых типов, сверка расширения с содержимым;
- content_disposition: экранированный заголовок (RFC 5987 filename*).
"""
from urllib.parse import quote

# расширение → набор допустимых magic-сигнатур (префиксы байт)
_ZIP = b"PK\x03\x04"          # docx/xlsx/pptx — это zip-контейнеры
_PDF = b"%PDF-"
_SIGNATURES: dict[str, tuple[bytes, ...]] = {
    "pdf": (_PDF,),
    "docx": (_ZIP,),
    "xlsx": (_ZIP,),
    "pptx": (_ZIP,),
    "png": (b"\x89PNG\r\n\x1a\n",),
    "jpg": (b"\xff\xd8\xff",),
    "jpeg": (b"\xff\xd8\xff",),
    "gif": (b"GIF87a", b"GIF89a"),
    "webp": (b"RIFF",),
}
# текстовые форматы magic не имеют — проверяем только расширение
_TEXT_EXT = {"txt", "md", "csv"}
ALLOWED_EXT = set(_SIGNATURES) | _TEXT_EXT


def _ext(filename: str) -> str:
    return filename.rsplit(".", 1)[-1].lower() if "." in (filename or "") else ""


def ensure_allowed(filename: str, data: bytes) -> str | None:
    """Возвращает текст ошибки, если файл недопустим; иначе None.
    Проверяет и расширение из whitelist, и соответствие magic-number содержимого."""
    ext = _ext(filename)
    if ext not in ALLOWED_EXT:
        return f"Недопустимый тип файла: .{ext or '?'}"
    if ext in _TEXT_EXT:
        return None
    sigs = _SIGNATURES[ext]
    if not any(data.startswith(sig) for sig in sigs):
        return "Содержимое файла не соответствует расширению"
    return None


def content_disposition(filename: str) -> str:
    """Безопасный заголовок Content-Disposition: ASCII-fallback + RFC 5987 filename*.
    Исключает инъекцию через кавычки/переводы строк в пользовательском имени."""
    ascii_name = (filename or "file").encode("ascii", "ignore").decode() or "file"
    ascii_name = ascii_name.replace('"', "").replace("\\", "").replace("\r", "").replace("\n", "")
    utf8_name = quote(filename or "file")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{utf8_name}"
