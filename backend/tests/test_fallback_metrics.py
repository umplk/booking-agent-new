"""LLM 降级指标测试：计数、结构化日志、阈值告警、接口返回与隐私边界。"""
import sys
import unittest
from datetime import time
from unittest.mock import Mock, patch

from app.agent import classifier
from app.config import settings as app_settings
from app.routers import agent as agent_router
from app.services.resource_generator import _to_time
from app.utils import fallback_metrics


class FallbackMetricsTest(unittest.TestCase):
    def setUp(self):
        fallback_metrics.reset()
        self._api_key = app_settings.DEEPSEEK_API_KEY
        app_settings.DEEPSEEK_API_KEY = "test-key"

    def tearDown(self):
        app_settings.DEEPSEEK_API_KEY = self._api_key
        fallback_metrics.reset()

    def test_records_counts_and_structured_log(self):
        with self.assertLogs("app.utils.fallback_metrics", level="WARNING") as logs:
            fallback_metrics.record_fallback("intent", "AttributeError", {"input_len": 6})
            fallback_metrics.record_fallback("intent", "AttributeError")
            fallback_metrics.record_fallback("slot", "ValidationError")

        snap = fallback_metrics.snapshot()
        self.assertEqual(snap["total"], 3)
        self.assertEqual(snap["by_stage"]["intent"], 2)
        self.assertEqual(snap["by_stage"]["slot"], 1)
        self.assertEqual(snap["by_reason"]["AttributeError"], 2)
        self.assertIsNotNone(snap["last_at"])
        self.assertTrue(any("stage=intent" in line for line in logs.output))

    def test_alert_fires_once_after_threshold(self):
        with self.assertLogs("app.utils.fallback_metrics", level="ERROR") as logs:
            for _ in range(fallback_metrics.ALERT_THRESHOLD + 3):
                fallback_metrics.record_fallback("slot", "ValidationError")
        alerts = [line for line in logs.output if "fallback alert" in line]
        self.assertEqual(len(alerts), 1)

    def test_intent_fallback_records_length_not_raw_text(self):
        fake_llm = Mock()
        fake_chain = Mock()
        fake_chain.invoke.return_value = None
        fake_llm.with_structured_output.return_value = fake_chain

        text = "帮我预约 13800001111"
        with patch.object(classifier, "llm", fake_llm):
            self.assertEqual(classifier.detect_intent_llm(text), "book")

        snap = fallback_metrics.snapshot()
        self.assertEqual(snap["by_stage"]["intent"], 1)
        self.assertNotIn("13800001111", str(snap))
        self.assertEqual(snap["recent"][0]["detail"], {"input_len": len(text)})

    def test_resource_time_fallback_is_recorded(self):
        with self.assertLogs("app.utils.fallback_metrics", level="WARNING"):
            self.assertEqual(_to_time("9点", time(8, 0)), time(8, 0))

        snap = fallback_metrics.snapshot()
        self.assertEqual(snap["by_stage"]["resource_time"], 1)
        self.assertEqual(snap["recent"][0]["detail"], {"value": "9点"})

    def test_metrics_endpoint_returns_snapshot(self):
        fallback_metrics.record_fallback("resource_time", "invalid_value", {"value": "9点"})
        response = agent_router.fallback_metrics(_current_user=object())
        self.assertEqual(response["code"], 200)
        self.assertEqual(response["data"]["total"], 1)
        self.assertEqual(response["data"]["by_stage"]["resource_time"], 1)
        self.assertIn("persistent", response["data"])


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)