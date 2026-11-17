"""Pydantic 输出契约（值域校验）与脏 LLM 输出的 pytest 用例集。"""
import random
import string
from datetime import time

import pytest
from pydantic import ValidationError

from app.agent import classifier
from app.agent.classifier import (
    IntentResult,
    SlotExtraction,
    detect_intent,
    detect_intent_safe,
    extract_by_llm,
    extract_request,
)
from app.agent.llm_guard import CircuitOpenError, reset_guard
from app.config import settings as app_settings
from app.services import resource_generator
from app.services.resource_generator import (
    ResourceSpec,
    _to_time,
    parse_description,
)
from app.utils import fallback_metrics


try:
    IntentResult(intent="bad")
except ValidationError as _exc:
    _intent_validation_error = _exc
else:
    raise AssertionError("IntentResult 应当拒绝非法枚举")


class _FakeChain:
    def __init__(self, result=None, exc=None):
        self.result = result
        self.exc = exc

    def invoke(self, *args, **kwargs):
        if self.exc is not None:
            raise self.exc
        return self.result


def _patch_llm(monkeypatch, chain):
    fake_llm = type("FakeLLM", (), {})()
    fake_llm.with_structured_output = lambda *a, **k: chain
    monkeypatch.setattr(classifier, "llm", fake_llm)


@pytest.fixture(autouse=True)
def isolated_state(monkeypatch):
    fallback_metrics.reset()
    reset_guard()
    monkeypatch.setattr(app_settings, "DEEPSEEK_API_KEY", "test-key")
    yield
    reset_guard()
    fallback_metrics.reset()


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("09:00", "09:00"),
        ("9:05", "09:05"),
        ("9:5", "09:05"),
        (" 23:59 ", "23:59"),
        ("9点", "09:00"),
        ("9：30", "09:30"),
        ("24:00", None),
        ("12:60", None),
        ("930", None),
        ("晚上", None),
        ("", None),
    ],
)
def test_slot_time_is_normalized_to_hhmm(raw, expected):
    slots = SlotExtraction(start_time=raw)
    assert slots.start_time == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("预约号3", 3),
        ("预约号 #7", 7),
        ("#12", 12),
        (12, 12),
        ("3.5", 3),
        ("abc", None),
        ("   ", None),
        (None, None),
    ],
)
def test_reservation_id_is_coerced_from_dirty_text(raw, expected):
    assert SlotExtraction(reservation_id=raw).reservation_id == expected


@pytest.mark.parametrize(
    "field, raw, expected",
    [
        ("date", " 明天 ", "明天"),
        ("scenario_query", "  自习室 ", "自习室"),
        ("resource_query", "A1", "A1"),
        ("date", "   ", None),
        ("scenario_query", "", None),
    ],
)
def test_text_fields_are_stripped_and_blank_becomes_none(field, raw, expected):
    assert getattr(SlotExtraction(**{field: raw}), field) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        (999, 100),
        (100, 100),
        (101, 100),
        (0, 1),
        (-5, 1),
        ("999个", 100),
        ("0个", 1),
        ("abc", 1),
        (3.9, 3),
    ],
)
def test_resource_count_is_clamped_into_1_100(raw, expected):
    spec = ResourceSpec(count=raw, name_prefix="x", code_prefix="X")
    assert spec.count == expected


@pytest.mark.parametrize("raw", [None, [], {}])
def test_resource_count_rejects_non_numeric_values(raw):
    with pytest.raises(ValidationError):
        ResourceSpec(count=raw, name_prefix="x", code_prefix="X")


@pytest.mark.parametrize(
    "start, end, expected_start, expected_end",
    [
        ("9-22点", None, "09:00", "22:00"),
        ("9:30-17:45", None, "09:30", "17:45"),
        ("9点", None, "09:00", "22:00"),
        ("晚上", "9点", "08:00", "09:00"),
        ("25:99", None, "08:00", "22:00"),
        (None, None, "08:00", "22:00"),
        ("09:00", "18:00", "09:00", "18:00"),
    ],
)
def test_resource_open_time_is_normalized(start, end, expected_start, expected_end):
    spec = ResourceSpec(
        count=1, name_prefix="场地", code_prefix="COURT", open_start=start, open_end=end
    )
    assert (spec.open_start, spec.open_end) == (expected_start, expected_end)


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("room-a", "ROOMA"),
        ("badminton", "BADMINTON"),
        ("中文前缀", "RES"),
        ("  ", "RES"),
        ("abcdefghijklmnopqrstuvwxyz", "ABCDEFGHIJKLMNOPQRST"),
        ("A1_b2", "A1B2"),
    ],
)
def test_code_prefix_is_sanitized_and_truncated(raw, expected):
    spec = ResourceSpec(count=1, name_prefix="x", code_prefix=raw)
    assert spec.code_prefix == expected


@pytest.mark.parametrize("raw", ["oops", None, ["a"], 42])
def test_non_dict_attributes_are_reset_to_empty(raw):
    spec = ResourceSpec(count=1, name_prefix="x", code_prefix="X", attributes=raw)
    assert spec.attributes == {}


def test_resource_spec_rejects_missing_count():
    with pytest.raises(ValidationError):
        ResourceSpec(name_prefix="x", code_prefix="X")


@pytest.mark.parametrize(
    "payload, field, expected",
    [
        ({"count": 3, "code_prefix": "X"}, "name_prefix", "资源"),
        ({"count": 3, "name_prefix": "x"}, "code_prefix", "RES"),
    ],
)
def test_resource_spec_fills_optional_text_defaults(payload, field, expected):
    assert getattr(ResourceSpec(**payload), field) == expected


@pytest.mark.parametrize(
    "intent",
    ["unknown", "BOOK", "book ", "", None, "reserve"],
)
def test_intent_enum_rejects_illegal_values(intent):
    with pytest.raises(ValidationError):
        IntentResult(intent=intent)


def test_whitespace_only_name_falls_back_to_default():
    spec = ResourceSpec(count=2, name_prefix="   ", code_prefix="X")
    assert spec.name_prefix == "资源"


@pytest.mark.parametrize(
    "result, exc, message, expected",
    [
        (None, None, "帮我预约自习室", "book"),
        (None, TimeoutError("upstream timeout"), "取消预约号 3", "cancel"),
        (None, ValueError("bad json"), "明天有什么空的会议室", "list_scenarios"),
        (object(), None, "你好", "chitchat"),
    ],
)
def test_dirty_intent_output_falls_back_to_rules(result, exc, message, expected, monkeypatch):
    _patch_llm(monkeypatch, _FakeChain(result=result, exc=exc))
    intent, degraded = detect_intent_safe(message)
    assert intent == expected
    assert degraded is True
    assert intent == detect_intent(message)
    assert fallback_metrics.snapshot()["by_stage"]["intent"] == 1


@pytest.mark.parametrize(
    "exc",
    [
        TimeoutError("timeout"),
        CircuitOpenError("circuit open"),
        pytest.param(_intent_validation_error, id="validation-error"),
    ],
)
def test_dirty_slot_output_falls_back_to_empty_result(exc, monkeypatch):
    _patch_llm(monkeypatch, _FakeChain(exc=exc))
    assert extract_by_llm("明天 15:00-16:00 自习室 A1") == {}
    snapshot = fallback_metrics.snapshot()
    assert snapshot["by_stage"]["slot"] == 1
    assert snapshot["recent"][0]["detail"] == {"input_len": len("明天 15:00-16:00 自习室 A1")}


@pytest.mark.parametrize(
    "message, expected",
    [
        ("明天 15:00-16:00 自习室 A1", {"start_time": "15:00", "end_time": "16:00"}),
        ("预约号 8 我想取消", {"reservation_id": 8}),
    ],
)
def test_extract_request_merges_regex_when_llm_is_empty(message, expected, monkeypatch):
    _patch_llm(monkeypatch, _FakeChain(result=None))
    data = extract_request("book", message)
    for key, value in expected.items():
        assert data[key] == value


def test_extract_request_turns_relative_date_into_absolute(monkeypatch):
    _patch_llm(monkeypatch, _FakeChain(result=None))
    data = extract_request("book", "后天 15:00-16:00 自习室 A1")
    assert data["date"] is not None
    assert len(data["date"]) == 10
    assert data["date"].count("-") == 2


@pytest.mark.parametrize(
    "description, count, start, end",
    [
        ("生成 5 个羽毛球场地，9-22点开放", 5, "09:00", "22:00"),
        ("生成 999 个会议室", 100, "08:00", "22:00"),
        ("生成 0 个会议室", 1, "08:00", "22:00"),
        ("帮我生成会议室", 1, "08:00", "22:00"),
        ("创建 8 个场地，10-18点可用", 8, "10:00", "18:00"),
    ],
)
def test_resource_description_falls_back_to_regex(
    description, count, start, end, monkeypatch
):
    monkeypatch.setattr(resource_generator, "_parse_by_llm", lambda _: None)
    spec = parse_description(description)
    assert (spec.count, spec.open_start, spec.open_end) == (count, start, end)


@pytest.mark.parametrize("raw", ["9点", "25:99", None, "", "abc"])
def test_invalid_open_time_falls_back_and_is_recorded(raw):
    assert _to_time(raw, time(8, 0)) == time(8, 0)
    assert fallback_metrics.snapshot()["by_stage"]["resource_time"] == 1


def test_random_dirty_slot_values_never_raise():
    rng = random.Random(20261116)
    alphabet = string.ascii_letters + string.digits + "：:-点预约号 #中文~至到／\\n\\t"
    for _ in range(200):
        payload = {
            "date": "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 12))),
            "start_time": "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 8))),
            "end_time": "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 8))),
            "reservation_id": "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 6))),
        }
        slots = SlotExtraction(**payload)
        assert slots.date is None or isinstance(slots.date, str)
        assert slots.start_time is None or 0 <= int(slots.start_time[:2]) <= 23
        assert slots.reservation_id is None or slots.reservation_id >= 0


def test_random_dirty_resource_specs_never_escape_domain():
    rng = random.Random(20261116)
    alphabet = string.ascii_letters + string.digits + "：:-点中文/\\n\\t"
    accepted = 0
    rejected = 0
    for _ in range(200):
        payload = {
            "count": rng.choice(
                [
                    rng.randint(-50, 500),
                    "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 6))),
                    None,
                ]
            ),
            "name_prefix": "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 8))),
            "code_prefix": "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 30))),
            "open_start": "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 8))),
            "open_end": "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 8))),
            "attributes": rng.choice([{}, None, "oops", ["a", "b"]]),
        }
        try:
            spec = ResourceSpec(**payload)
        except ValidationError:
            rejected += 1
            continue
        accepted += 1
        assert 1 <= spec.count <= 100
        assert 0 <= int(spec.open_start[:2]) <= 23
        assert 0 <= int(spec.open_end[:2]) <= 23
        assert isinstance(spec.attributes, dict)
        assert 1 <= len(spec.code_prefix) <= 20
    assert accepted + rejected == 200
    assert accepted >= 120