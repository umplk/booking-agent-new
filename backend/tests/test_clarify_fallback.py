"""降级澄清追问测试：规则兜底猜出高风险意图时先追问，不直接执行。"""
import sys
import unittest
from unittest.mock import patch

from langchain_core.messages import HumanMessage

from app.agent import nodes
from app.agent.classifier import detect_intent_safe
from app.agent.llm_guard import reset_guard
from app.config import settings as app_settings
from app.utils import fallback_metrics


def _human(text):
    return HumanMessage(content=text)


def _state(text, **extra):
    state = {
        "messages": [_human(text)],
        "pending_confirmation": False,
        "pending_clarification": False,
    }
    state.update(extra)
    return state


class ClarifyFallbackTest(unittest.TestCase):
    def setUp(self):
        fallback_metrics.reset()
        reset_guard()
        self._api_key = app_settings.DEEPSEEK_API_KEY
        app_settings.DEEPSEEK_API_KEY = "test-key"

    def tearDown(self):
        app_settings.DEEPSEEK_API_KEY = self._api_key
        reset_guard()
        fallback_metrics.reset()

    def _route(self, text, guessed_intent, degraded, **extra):
        with patch.object(
            nodes, "detect_intent_safe", return_value=(guessed_intent, degraded)
        ):
            return nodes.route_intent(_state(text, **extra))

    def test_degraded_high_risk_intent_asks_before_acting(self):
        with self.assertLogs("app.utils.fallback_metrics", level="WARNING"):
            out = self._route("帮我弄一下那个", "book", True)
        self.assertTrue(out["pending_clarification"])
        self.assertEqual(out["intent"], "book")
        self.assertIn("你是想", out["reply"])
        self.assertEqual(fallback_metrics.snapshot()["by_stage"]["clarify"], 1)

    def test_degraded_read_only_intent_does_not_ask(self):
        out = self._route("明天有空的吗", "query", True)
        self.assertFalse(out.get("pending_clarification"))
        self.assertEqual(out["intent"], "query")
        self.assertEqual(out["reply"], "")

    def test_degraded_chitchat_still_replies_normally(self):
        out = self._route("你好", "chitchat", True)
        self.assertEqual(out["intent"], "chitchat")
        self.assertFalse(out.get("pending_clarification"))
        self.assertTrue(out["reply"])

    def test_offline_rule_mode_does_not_ask(self):
        out = self._route("帮我预约自习室", "book", False)
        self.assertFalse(out.get("pending_clarification"))
        self.assertEqual(out["intent"], "book")

    def test_multiturn_slot_fill_is_not_treated_as_guess(self):
        out = self._route("A1", "chitchat", True, intent="book", missing=["start_time"])
        self.assertFalse(out.get("pending_clarification"))
        self.assertEqual(out["intent"], "book")

    def test_clarification_reply_selects_intent(self):
        cases = {
            "1": "book",
            "2": "query",
            "3": "cancel",
            "取消": "cancel",
            "我的预约": "list_my",
            "查看场景": "list_scenarios",
            "生成资源": "configure",
            "预约": "book",
        }
        for reply, expected in cases.items():
            out = nodes.route_intent(
                {
                    "messages": [_human(reply)],
                    "pending_confirmation": False,
                    "pending_clarification": True,
                    "intent": "book",
                }
            )
            self.assertEqual(out["intent"], expected, reply)
            self.assertFalse(out["pending_clarification"])
            self.assertEqual(out["reply"], "")

    def test_clarification_unknown_reply_does_not_act(self):
        out = nodes.route_intent(
            {
                "messages": [_human("哈哈")],
                "pending_confirmation": False,
                "pending_clarification": True,
            }
        )
        self.assertFalse(out["pending_clarification"])
        self.assertEqual(out["intent"], "chitchat")
        self.assertIn("请直接回复", out["reply"])

    def test_offline_detect_intent_safe_marks_not_degraded(self):
        app_settings.DEEPSEEK_API_KEY = ""
        intent, degraded = detect_intent_safe("帮我预约自习室")
        self.assertEqual(intent, "book")
        self.assertFalse(degraded)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)