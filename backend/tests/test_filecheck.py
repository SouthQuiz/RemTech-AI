"""Issue #7 — тесты валидации файлов и безопасного Content-Disposition."""
from services.filecheck import content_disposition, ensure_allowed

_PDF = b"%PDF-1.7\n..."
_PNG = b"\x89PNG\r\n\x1a\n....."


def test_allows_valid_pdf():
    assert ensure_allowed("doc.pdf", _PDF) is None


def test_allows_text_by_extension():
    assert ensure_allowed("notes.txt", b"anything") is None


def test_rejects_unknown_extension():
    err = ensure_allowed("evil.exe", b"MZ....")
    assert err and "тип" in err.lower()


def test_rejects_magic_mismatch():
    # .pdf по имени, но содержимое не PDF (magic не совпал)
    err = ensure_allowed("fake.pdf", _PNG)
    assert err and "содержим" in err.lower()


def test_rejects_no_extension():
    assert ensure_allowed("noext", _PDF) is not None


def test_content_disposition_escapes_injection():
    # попытка инъекции через кавычки/переводы строк в имени
    header = content_disposition('a"; rm -rf\r\nX="b.pdf')
    assert "\r" not in header and "\n" not in header
    assert header.count('"') == 2          # только обрамляющие кавычки ascii-части
    assert "filename*=UTF-8''" in header   # RFC 5987 для не-ASCII


def test_content_disposition_unicode_name():
    header = content_disposition("КП Ремтехника.pdf")
    assert "filename*=UTF-8''" in header
