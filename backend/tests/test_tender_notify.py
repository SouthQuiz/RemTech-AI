"""Issue #37 (TASK-0802) — уведомления о новых тендерах: дедуп + доставка в 2 канала."""
from app import repositories as repo
from services import tender_notify, tenders

ROWS = [
    {"number": "111", "name": "Экскаватор A", "customer": "ГБУ",
     "price": 5_000_000, "deadline": "20.07.2026", "link": "http://eis/111"},
    {"number": "222", "name": "Экскаватор B", "customer": "МКУ",
     "price": 8_000_000, "deadline": "21.07.2026", "link": "http://eis/222"},
]


async def _setup(session):
    # пользователь роли «закупки» — адресат уведомлений
    await repo.create_user(session, "buyer", "h$1", role="закупки")
    sub = await repo.create_subscription(session, "Экскаваторы", "экскаватор",
                                         recipient_roles="закупки")
    await session.commit()
    return sub


async def test_new_tenders_notify_both_channels_once(session):
    await _setup(session)
    tg = []

    async def fake_tg(usernames, text):
        tg.append((usernames, text))

    n = await tender_notify.poll_once(session, search=lambda *a: ROWS, tg_sender=fake_tg)
    assert n == 2                                            # две новые закупки
    web = await repo.list_notifications(session, "закупки")
    assert len(web) == 2                                     # веб-лента: два уведомления
    assert len(tg) == 2 and tg[0][0] == ["buyer"]           # Telegram: доставка адресату роли
    assert "№111" in tg[0][1] or "№111" in tg[1][1]


async def test_repeat_run_no_duplicates(session):
    await _setup(session)

    async def noop(u, t):
        pass

    await tender_notify.poll_once(session, search=lambda *a: ROWS, tg_sender=noop)
    tg = []

    async def fake_tg(u, t):
        tg.append((u, t))

    n2 = await tender_notify.poll_once(session, search=lambda *a: ROWS, tg_sender=fake_tg)
    assert n2 == 0                                           # дедуп по реестровому номеру
    assert len(await repo.list_notifications(session, "закупки")) == 2   # не выросло
    assert tg == []                                          # повторной доставки нет


async def test_only_new_tender_notified(session):
    await _setup(session)

    async def noop(u, t):
        pass

    await tender_notify.poll_once(session, search=lambda *a: ROWS, tg_sender=noop)
    rows2 = ROWS + [{"number": "333", "name": "Экскаватор C", "customer": "ООО",
                     "price": 3_000_000, "deadline": "", "link": "http://eis/333"}]
    n3 = await tender_notify.poll_once(session, search=lambda *a: rows2, tg_sender=noop)
    assert n3 == 1                                           # только новая №333
    assert len(await repo.list_notifications(session, "закупки")) == 3


async def test_source_unavailable_skips_subscription(session):
    await _setup(session)

    def boom(*a):
        raise tenders.TenderSourceError("источник недоступен")

    async def noop(u, t):
        pass

    n = await tender_notify.poll_once(session, search=boom, tg_sender=noop)
    assert n == 0                                            # без падения всего опроса
    assert await repo.list_notifications(session, "закупки") == []


async def test_tender_without_number_skipped(session):
    await _setup(session)
    rows = [{"number": "", "name": "Без номера", "price": None, "link": "http://eis/x"}]

    async def noop(u, t):
        pass

    n = await tender_notify.poll_once(session, search=lambda *a: rows, tg_sender=noop)
    assert n == 0                                            # без реестрового номера дедуп невозможен
