"""Issue #37 (TASK-0802, EPIC-08) — уведомления о новых тендерах.

Периодически (Celery beat, см. app/tasks.tenders_poll_task) прогоняет сохранённые
критерии (tender_subscriptions), находит НОВЫЕ закупки (дедуп по реестровому номеру,
tender_seen) и доставляет ответственным в два канала: веб-лента (таблица
notifications) и Telegram (адаптер #31). Доставка инъектируется — тесты без сети.

Получатели адресуются по ролям подписки (recipient_roles); Telegram-адреса берём
реверсом из allow-list (config.telegram_allowmap), новых столбцов в users не заводим.
"""
from __future__ import annotations

import asyncio

from app import repositories as repo
from app.config import get_settings
from app.logging_config import get_logger
from services import tenders

log = get_logger("remtech.tender_notify")


def _format(sub_name: str, t: dict) -> tuple[str, str, str]:
    price = f"{t['price']:,.0f} ₽".replace(",", " ") if t.get("price") else "не указана"
    title = f"Новая закупка по подписке «{sub_name}»: {t.get('name', '')}".strip()
    body = (f"№{t.get('number', '—')} · Заказчик: {t.get('customer') or '—'} · "
            f"НМЦК: {price} · Срок подачи: {t.get('deadline') or '—'}")
    return title, body, t.get("link", "")


async def _telegram_send(usernames: list[str], text: str) -> None:
    """Реальная доставка в Telegram: username → tg_id (реверс allow-list) → sendMessage."""
    s = get_settings()
    if not s.telegram_bot_token or not usernames:
        return
    rev = {uname: tid for tid, uname in s.telegram_allowmap.items()}
    targets = [rev[u] for u in usernames if u in rev]
    if not targets:
        return
    from app.telegram_bot import TelegramTransport
    tx = TelegramTransport(s.telegram_bot_token)
    try:
        for chat_id in targets:
            try:
                await tx.call("sendMessage", {"chat_id": chat_id, "text": text})
            except Exception:
                log.exception("tg notify failed chat=%s", chat_id)
    finally:
        await tx.aclose()


async def poll_once(s, search=None, tg_sender=_telegram_send) -> int:
    """Один прогон всех активных подписок. Возвращает число НОВЫХ уведомлений.
    search(keywords, region, customer, budget_min, budget_max) -> list[dict];
    по умолчанию — реальный поиск ЕИС (блокирующий, уводим в поток)."""
    subs = await repo.list_subscriptions(s, only_active=True)
    tg_queue: list[tuple[list[str], str]] = []
    new_count = 0

    for sub in subs:
        try:
            if search is not None:
                rows = search(sub.keywords, sub.region or "", sub.customer or "",
                              sub.budget_min, sub.budget_max)
            else:
                rows = await asyncio.to_thread(
                    tenders.search_tenders, sub.keywords, sub.region or "",
                    sub.customer or "", sub.budget_min, sub.budget_max)
        except tenders.TenderSourceError as e:
            log.warning("подписка #%s: источник недоступен: %s", sub.id, e)
            continue

        roles = [r.strip() for r in (sub.recipient_roles or "").split(",") if r.strip()]
        for t in rows:
            reg = (t.get("number") or "").strip()
            if not reg:
                continue   # без реестрового номера дедуп невозможен — пропускаем
            if not await repo.mark_tender_seen(s, sub.id, reg):
                continue   # уже отправляли — не дублируем
            title, body, link = _format(sub.name, t)
            for role in roles:
                await repo.add_notification(s, role, title, body, link)
            usernames = await repo.usernames_by_roles(s, roles)
            if usernames:
                tg_queue.append((usernames, f"{title}\n{body}\n{link}".strip()))
            new_count += 1

    await s.commit()
    # доставка в Telegram — после фиксации БД (не держим транзакцию на время сети)
    for usernames, text in tg_queue:
        await tg_sender(usernames, text)
    return new_count
