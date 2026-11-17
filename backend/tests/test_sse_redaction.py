"""SSE 流式异常脱敏的 pytest 用例集（不依赖事件循环，可在禁 socket 环境执行）。"""
import json
import logging
from unittest.mock import AsyncMock, patch

import pytest
from langchain_core.messages import AIMessage

from app.models.user import User
from app.routers.agent import ChatRequest, chat
from app.utils import fallback_metrics

_SAFE_MESSAGE = "服务暂时不可用，请稍后重试"


def _drive(coro):
    try:
        return coro.send(None)
    except StopIteration as exc:
        return exc.value


def _first_event(agen):
    try:
        step = agen.__anext__()
    except StopAsyncIteration:
        return ""
    try:
        return step.send(None)
    except StopIteration as exc:
        return exc.value or ""


def _all_events(agen):
    events = []
    while True:
        try:
            step = agen.__anext__()
        except StopAsyncIteration:
            break
        try:
            value = step.send(None)
        except StopIteration as exc:
            value = exc.value
        except StopAsyncIteration:
            break
        if value is not None:
            events.append(value)
    return events


def _run_chat(message="你好", session_id=None):
    user = User(id=1, username="u1", email="u1@test.com", password_hash="x", role="student")
    response = _drive(chat(ChatRequest(message=message, session_id=session_id), current_user=user))
    return response, _first_event(response.body_iterator)


def _payload(event):
    assert event.startswith("data: ")
    return json.loads(event[len("data: "):].strip())


@pytest.fixture(autouse=True)
def clean_metrics():
    fallback_metrics.reset()
    yield
    fallback_metrics.reset()


@pytest.mark.parametrize(
    "secret",
    [
        "api_key=sk-secret-1234567890",
        "mysql://root:Passw0rd@10.0.0.8:3306/app",
        "C:\\Users\\admin\\.env",
        "Traceback (most recent call last)",
        "SecretAccessKey=AKIAIOSFODNN7EXAMPLE",
        "用户手机号 13800001111",
    ],
)
def test_sse_error_event_hides_sensitive_text(secret):
    boom = RuntimeError(f"upstream failed: {secret}")
    with patch("app.routers.agent.graph.ainvoke", new=AsyncMock(side_effect=boom)):
        _, event = _run_chat()
    payload = _payload(event)
    assert payload["error"] == _SAFE_MESSAGE
    assert "content" not in payload
    for fragment in ("sk-secret", "10.0.0.8", "Passw0rd", "C:\\Users", "Traceback", "AKIA", "13800001111"):
        assert fragment not in event


def test_sse_error_event_keeps_session_and_contract():
    boom = RuntimeError("api_key=sk-secret-123")
    with patch("app.routers.agent.graph.ainvoke", new=AsyncMock(side_effect=boom)):
        response, event = _run_chat(session_id="fixed-session")
    payload = _payload(event)
    assert payload["session_id"] == "fixed-session"
    assert set(payload) == {"session_id", "error"}
    assert response.media_type == "text/event-stream"
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"


def test_sse_error_keeps_original_exception_in_server_log(caplog):
    boom = RuntimeError("api_key=sk-secret-123 internal=10.0.0.8")
    with caplog.at_level(logging.ERROR, logger="app.routers.agent"):
        with patch("app.routers.agent.graph.ainvoke", new=AsyncMock(side_effect=boom)):
            _, event = _run_chat()
    assert "sk-secret-123" in caplog.text
    assert "10.0.0.8" in caplog.text
    assert "sk-secret-123" not in event


def test_sse_error_increments_fallback_metric_once():
    boom = RuntimeError("boom")
    with patch("app.routers.agent.graph.ainvoke", new=AsyncMock(side_effect=boom)):
        _run_chat()
    snapshot = fallback_metrics.snapshot()
    assert snapshot["by_stage"]["sse"] == 1
    assert snapshot["by_reason"]["unhandled_exception"] == 1
    assert snapshot["recent"][0]["detail"] is None


def test_sse_repeated_errors_accumulate_metric():
    boom = RuntimeError("boom")
    with patch("app.routers.agent.graph.ainvoke", new=AsyncMock(side_effect=boom)):
        _run_chat()
        _run_chat()
    assert fallback_metrics.snapshot()["by_stage"]["sse"] == 2


def test_sse_normal_reply_has_content_and_no_error():
    result = {"messages": [AIMessage(content="你好，我是预约助手")]}
    with patch("app.routers.agent.graph.ainvoke", new=AsyncMock(return_value=result)):
        _, event = _run_chat()
    payload = _payload(event)
    assert payload["content"] == "你好，我是预约助手"
    assert "error" not in payload
    assert fallback_metrics.snapshot()["total"] == 0


def test_sse_error_event_is_followed_by_done():
    boom = RuntimeError("api_key=sk-secret-123")
    user = User(id=1, username="u1", email="u1@test.com", password_hash="x", role="student")
    with patch("app.routers.agent.graph.ainvoke", new=AsyncMock(side_effect=boom)):
        response = _drive(chat(ChatRequest(message="你好"), current_user=user))
        events = _all_events(response.body_iterator)
    assert len(events) == 2
    first, second = (_payload(event) for event in events)
    assert first["error"] == _SAFE_MESSAGE
    assert second == {"session_id": first["session_id"], "done": True}


def test_sse_normal_reply_is_followed_by_done():
    result = {"messages": [AIMessage(content="你好")]}
    user = User(id=1, username="u1", email="u1@test.com", password_hash="x", role="student")
    with patch("app.routers.agent.graph.ainvoke", new=AsyncMock(return_value=result)):
        response = _drive(chat(ChatRequest(message="你好"), current_user=user))
        events = _all_events(response.body_iterator)
    assert [event.get("done") for event in map(_payload, events)] == [None, True]


def test_sse_generator_closes_cleanly_after_client_disconnect():
    boom = RuntimeError("api_key=sk-secret-123")
    user = User(id=1, username="u1", email="u1@test.com", password_hash="x", role="student")
    with patch("app.routers.agent.graph.ainvoke", new=AsyncMock(side_effect=boom)):
        response = _drive(chat(ChatRequest(message="你好"), current_user=user))
        _first_event(response.body_iterator)
        with pytest.raises(StopIteration):
            response.body_iterator.aclose().send(None)