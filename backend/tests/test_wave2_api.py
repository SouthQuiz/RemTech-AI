"""Волна 2 — интеграционные проверки: деактивация действует сразу (#4),
проверка типа файла при загрузке (#7)."""


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _register_admin(client):
    r = await client.post("/api/register",
                          json={"username": "director", "password": "pass1234", "full_name": "Директор"})
    assert r.status_code == 200, r.text
    return r.json()["token"]


async def test_deactivated_token_rejected_immediately(client):
    admin = await _register_admin(client)
    await client.post("/api/admin/users",
                      json={"username": "anna", "password": "pass1234", "role": "user"},
                      headers=_auth(admin))
    anna = (await client.post("/api/login",
                              json={"username": "anna", "password": "pass1234"})).json()["token"]
    # токен валиден до деактивации
    assert (await client.get("/api/me", headers=_auth(anna))).status_code == 200

    uid = next(u["id"] for u in (await client.get("/api/admin/users", headers=_auth(admin))).json()
               if u["username"] == "anna")
    await client.post(f"/api/admin/users/{uid}/active?active=false", headers=_auth(admin))

    # тот же (не истёкший) токen больше не действует — #4
    assert (await client.get("/api/me", headers=_auth(anna))).status_code == 401


async def test_upload_rejects_bad_magic(client):
    admin = await _register_admin(client)
    # .pdf по имени, но содержимое не PDF → 400
    files = {"file": ("fake.pdf", b"\x89PNG\r\n\x1a\n not a pdf", "application/pdf")}
    r = await client.post("/api/upload", files=files, headers=_auth(admin))
    assert r.status_code == 400

    # валидный текстовый файл проходит
    files = {"file": ("notes.txt", b"hello", "text/plain")}
    r = await client.post("/api/upload", files=files, headers=_auth(admin))
    assert r.status_code == 200, r.text


async def test_password_reset_enforces_policy(client):
    admin = await _register_admin(client)
    await client.post("/api/admin/users",
                      json={"username": "bob", "password": "pass1234", "role": "user"},
                      headers=_auth(admin))
    uid = next(u["id"] for u in (await client.get("/api/admin/users", headers=_auth(admin))).json()
               if u["username"] == "bob")
    # слабый пароль отклоняется (#10 в сбросе)
    r = await client.post(f"/api/admin/users/{uid}/password",
                          json={"password": "123"}, headers=_auth(admin))
    assert r.status_code == 400
