"""Cutover Стадия 3b — тесты чистых функций оркестратора (без вызова модели)."""
from app.orchestrator import _safe_content, _sanitize_history


def test_safe_content_keeps_text_and_tooluse():
    class T:
        type = "text"; text = "привет"
    class TU:
        type = "tool_use"; id = "1"; name = "create_docx"; input = {"filename": "x"}
    class Junk:
        type = "server_tool_use"
    out = _safe_content([T(), TU(), Junk()])
    assert out == [
        {"type": "text", "text": "привет"},
        {"type": "tool_use", "id": "1", "name": "create_docx", "input": {"filename": "x"}},
    ]


def test_sanitize_collapses_tool_exchanges():
    history = [
        {"role": "user", "content": "сделай кп"},
        {"role": "assistant", "content": [{"type": "tool_use", "id": "1", "name": "create_docx", "input": {}}]},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "1", "content": "ок"}]},
        {"role": "assistant", "content": [{"type": "text", "text": "готово"}]},
    ]
    clean = _sanitize_history(history)
    # осиротевших tool_use/tool_result не остаётся
    for m in clean:
        c = m.get("content")
        if isinstance(c, list):
            for b in c:
                assert b.get("type") not in ("tool_use", "tool_result")
    assert clean[0]["role"] == "user"
    assert any("готово" in (m["content"] if isinstance(m["content"], str) else "") for m in clean)


def test_sanitize_drops_leading_non_user():
    history = [
        {"role": "assistant", "content": "привет"},
        {"role": "user", "content": "вопрос"},
    ]
    clean = _sanitize_history(history)
    assert clean[0]["role"] == "user"
