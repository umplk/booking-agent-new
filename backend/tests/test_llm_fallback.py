"""LLM 输出异常时的兜底测试：脏输出不应抛异常，且必须降级到规则/正则路径。"""
import sys
import unittest
from unittest.mock import Mock, patch

from pydantic import ValidationError

from app.agent import classifier
from app.agent.classifier import (
    SlotExtraction,
    detect_intent,
    detect_intent_llm,
    extract_by_llm,
    extract_request,
)
from app.agent.llm_guard import reset_guard
from app.config import settings as app_settings
from app.services import resource_generator
from app.services.resource_generator import ResourceSpec, parse_description
from app.utils import fallback_metrics


class _FakeChain:
    """模拟 with_structured_output 返回的链，可以返回 None 或直接抛异常。"""

    def __init__(self, result=None, exc=None):
        self.result = result
        self.exc = exc

    def invoke(self, *args, **kwargs):
        if self.exc is not None:
            raise self.exc
        return self.result


def _validation_error(model, **data):
    try:
        model(**data)
    except ValidationError as exc:
        return exc
    raise AssertionError("预期触发 ValidationError")


class LlmFallbackTest(unittest.TestCase):
    def setUp(self):
        fallback_metrics.reset()
        reset_guard()
        self._api_key = app_settings.DEEPSEEK_API_KEY
        app_settings.DEEPSEEK_API_KEY = "test-key"

    def tearDown(self):
        app_settings.DEEPSEEK_API_KEY = self._api_key
        reset_guard()
        fallback_metrics.reset()

    def _patch_llm(self, chain):
        fake_llm = Mock()
        fake_llm.with_structured_output.return_value = chain
        return patch.object(classifier, "llm", fake_llm)

    def test_noise_output_falls_back_to_rule_intent(self):
        with self._patch_llm(_FakeChain(result=None)):
            with self.assertLogs("app.utils.fallback_metrics", level="WARNING") as logs:
                intent = detect_intent_llm("帮我预约自习室")
        self.assertEqual(intent, "book")
        self.assertEqual(intent, detect_intent("帮我预约自习室"))
        self.assertTrue(any("stage=intent" in line for line in logs.output))

    def test_illegal_enum_falls_back_to_rule_intent(self):
        exc = _validation_error(classifier.IntentResult, intent="unknown")
        with self._patch_llm(_FakeChain(exc=exc)):
            with self.assertLogs("app.utils.fallback_metrics", level="WARNING"):
                self.assertEqual(detect_intent_llm("取消预约号 3"), "cancel")

    def test_noise_output_falls_back_to_regex_slots(self):
        with self._patch_llm(_FakeChain(result=None)):
            with self.assertLogs("app.utils.fallback_metrics", level="WARNING") as logs:
                self.assertEqual(extract_by_llm("明天 15:00-16:00 自习室 A1"), {})
        self.assertTrue(any("stage=slot" in line for line in logs.output))
        self.assertGreaterEqual(fallback_metrics.snapshot()["by_stage"]["slot"], 1)

    def test_extract_request_merges_regex_when_llm_empty(self):
        with patch.object(classifier, "extract_by_llm", return_value={}):
            data = extract_request("book", "明天 15:00-16:00 自习室 A1")
        self.assertEqual(data["start_time"], "15:00")
        self.assertEqual(data["end_time"], "16:00")
        self.assertTrue(data["date"])

    def test_resource_spec_normalizes_dirty_values(self):
        spec = ResourceSpec(
            count="999个",
            name_prefix="  ",
            code_prefix="中文前缀",
            open_start="9-22点",
            open_end=None,
            attributes="oops",
        )
        self.assertEqual(spec.count, 100)
        self.assertEqual(spec.name_prefix, "资源")
        self.assertEqual(spec.code_prefix, "RES")
        self.assertEqual(spec.open_start, "09:00")
        self.assertEqual(spec.open_end, "22:00")
        self.assertEqual(spec.attributes, {})

        spec2 = ResourceSpec(
            count=3,
            name_prefix="会议室",
            code_prefix="room-a",
            open_start="晚上",
            open_end="9点",
        )
        self.assertEqual(spec2.open_start, "08:00")
        self.assertEqual(spec2.open_end, "09:00")
        self.assertEqual(spec2.code_prefix, "ROOMA")

    def test_missing_required_field_is_rejected(self):
        exc = _validation_error(ResourceSpec, name_prefix="x", code_prefix="X")
        self.assertIn("count", str(exc))

    def test_slot_extraction_dirty_values(self):
        slots = SlotExtraction(
            date=" 明天 ",
            start_time="9点",
            end_time="25:99",
            scenario_query="",
            reservation_id="预约号3",
        )
        self.assertEqual(slots.date, "明天")
        self.assertEqual(slots.start_time, "09:00")
        self.assertIsNone(slots.end_time)
        self.assertIsNone(slots.scenario_query)
        self.assertEqual(slots.reservation_id, 3)

    def test_resource_generation_falls_back_to_regex(self):
        with patch.object(resource_generator, "_parse_by_llm", return_value=None):
            spec = parse_description("生成 5 个羽毛球场地，9-22点开放")
        self.assertEqual(spec.count, 5)
        self.assertEqual(spec.open_start, "09:00")
        self.assertEqual(spec.open_end, "22:00")


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)