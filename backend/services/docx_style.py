"""Issue #19 — единый фирменный стиль DOCX (цвета + OOXML-хелперы).

Убирает дублирование ``shade()`` и брендовых цветов, которые были скопированы
в docgen.py и reports.py (по 3-4 копии).
"""
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

# Фирменная гамма «Ремтехники»: жёлтый / чёрный / бледно-жёлтая полоса
YELLOW = "FFCB05"   # титульная плашка, акцент
DARK = "1A1A1A"     # шапки таблиц, текст
BAND = "FFF6D5"     # бледно-жёлтая полоса чередования строк

# Реквизиты компании — единый источник (issue #26). Проверены по документам БЗ.
COMPANY = {
    "name": "ООО «Ремтехника»",
    "inn": "2447007401",
    "kpp": "245401001",
    "ogrn": "1042401110454",
    "director": "Шеверев О.В.",
    "address": "662549, г. Лесосибирск, ул. Мичурина, 6",
    "phone": "",
    "email": "",
}


def requisites_lines() -> list[str]:
    """Строки реквизитов для подвала документов."""
    c = COMPANY
    lines = [c["name"], f"ИНН {c['inn']} · КПП {c['kpp']} · ОГРН {c['ogrn']}",
             f"Адрес: {c['address']}", f"Генеральный директор: {c['director']}"]
    if c.get("phone") or c.get("email"):
        lines.append(" · ".join(x for x in (c.get("phone"), c.get("email")) if x))
    return lines


def shade(cell, color: str) -> None:
    """Заливка ячейки таблицы Word фоновым цветом (OOXML ``w:shd``)."""
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), color)
    tc_pr.append(shd)
