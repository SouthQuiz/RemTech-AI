"""Issue #20 — WebSocket: отклонение неавторизованного подключения."""
import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app

# TestClient без контекст-менеджера не запускает startup (не трогаем боевую БД):
# невалидный токен отвергается ещё до обращения к БД (auth.verify → None).
_client = TestClient(app)


def test_ws_rejects_missing_token():
    with pytest.raises(WebSocketDisconnect):
        with _client.websocket_connect("/ws"):
            pass


def test_ws_rejects_bad_ticket():
    # #4 — авторизация по тикету; неизвестный тикет отвергается
    with pytest.raises(WebSocketDisconnect):
        with _client.websocket_connect("/ws?ticket=garbage-ticket"):
            pass
