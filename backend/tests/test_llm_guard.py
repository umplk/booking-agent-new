"""LLM 超时、并发上限与熔断测试。"""
import sys
import threading
import time
import unittest
from unittest.mock import Mock, patch

from app.agent import classifier
from app.agent.llm import llm as chat_llm
from app.agent.llm_guard import (
    CircuitOpenError,
    ConcurrencyLimitError,
    LLMGuard,
    guard_state,
    reset_guard,
)
from app.config import settings as app_settings
from app.utils import fallback_metrics


class _Chain:
    def __init__(self, fail=False, delay=0.0):
        self.fail = fail
        self.delay = delay
        self.calls = 0

    def invoke(self, prompt):
        self.calls += 1
        if self.delay:
            time.sleep(self.delay)
        if self.fail:
            raise TimeoutError("upstream timeout")
        return "ok"


class LLMGuardTest(unittest.TestCase):
    def setUp(self):
        fallback_metrics.reset()
        reset_guard()
        self._api_key = app_settings.DEEPSEEK_API_KEY
        app_settings.DEEPSEEK_API_KEY = "test-key"

    def tearDown(self):
        app_settings.DEEPSEEK_API_KEY = self._api_key
        reset_guard()
        fallback_metrics.reset()

    def test_client_has_timeout_and_retry(self):
        self.assertEqual(int(chat_llm.request_timeout), app_settings.LLM_TIMEOUT_SECONDS)
        self.assertEqual(chat_llm.max_retries, app_settings.LLM_MAX_RETRIES)

    def test_concurrency_is_limited(self):
        guard = LLMGuard(
            max_concurrency=2, queue_wait_seconds=5, failure_threshold=99, cooldown_seconds=0
        )
        state = {"active": 0, "peak": 0}
        lock = threading.Lock()
        errors = []

        class CountingChain:
            def invoke(self, prompt):
                with lock:
                    state["active"] += 1
                    state["peak"] = max(state["peak"], state["active"])
                time.sleep(0.15)
                with lock:
                    state["active"] -= 1
                return "ok"

        def call():
            try:
                guard.invoke(CountingChain(), "x")
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=call) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])
        self.assertEqual(state["peak"], 2)

    def test_queue_wait_times_out_instead_of_blocking(self):
        guard = LLMGuard(
            max_concurrency=1, queue_wait_seconds=0.05, failure_threshold=99, cooldown_seconds=0
        )
        started = threading.Event()
        release = threading.Event()

        class BlockingChain:
            def invoke(self, prompt):
                started.set()
                release.wait(2)
                return "ok"

        holder = threading.Thread(target=lambda: guard.invoke(BlockingChain(), "x"))
        holder.start()
        self.assertTrue(started.wait(1))
        try:
            with self.assertRaises(ConcurrencyLimitError):
                guard.invoke(BlockingChain(), "y")
        finally:
            release.set()
            holder.join()

    def test_circuit_opens_and_rejects_until_cooldown(self):
        guard = LLMGuard(
            max_concurrency=5,
            queue_wait_seconds=1,
            failure_threshold=3,
            cooldown_seconds=60,
        )
        fail_chain = _Chain(fail=True)

        for _ in range(3):
            with self.assertRaises(TimeoutError):
                guard.invoke(fail_chain, "x")
        self.assertEqual(guard.state, "open")

        with self.assertRaises(CircuitOpenError):
            guard.invoke(fail_chain, "x")
        self.assertEqual(fail_chain.calls, 3)

    def test_half_open_success_closes_circuit(self):
        guard = LLMGuard(
            max_concurrency=5,
            queue_wait_seconds=1,
            failure_threshold=1,
            cooldown_seconds=60,
        )
        fail_chain = _Chain(fail=True)
        ok_chain = _Chain()

        with self.assertRaises(TimeoutError):
            guard.invoke(fail_chain, "x")
        self.assertEqual(guard.state, "open")

        guard._opened_at -= 61
        self.assertEqual(guard.invoke(ok_chain, "x"), "ok")
        self.assertEqual(guard.state, "closed")

    def test_half_open_probe_failure_reopens(self):
        guard = LLMGuard(
            max_concurrency=5,
            queue_wait_seconds=1,
            failure_threshold=1,
            cooldown_seconds=60,
        )
        fail_chain = _Chain(fail=True)

        with self.assertRaises(TimeoutError):
            guard.invoke(fail_chain, "x")
        self.assertEqual(guard.state, "open")

        guard._opened_at -= 61
        with self.assertRaises(TimeoutError):
            guard.invoke(fail_chain, "x")
        self.assertEqual(guard.state, "open")

    def test_detect_intent_degrades_when_circuit_opens(self):
        threshold = app_settings.LLM_CIRCUIT_FAILURE_THRESHOLD
        fake_llm = Mock()
        fake_chain = Mock()
        fake_chain.invoke.side_effect = TimeoutError("upstream timeout")
        fake_llm.with_structured_output.return_value = fake_chain

        with patch.object(classifier, "llm", fake_llm):
            for _ in range(threshold + 1):
                self.assertEqual(classifier.detect_intent_llm("帮我预约自习室"), "book")

        self.assertEqual(guard_state(), "open")
        self.assertEqual(fake_chain.invoke.call_count, threshold)
        snap = fallback_metrics.snapshot()
        self.assertEqual(snap["by_stage"]["circuit"], 1)
        self.assertGreaterEqual(snap["by_stage"]["intent"], threshold + 1)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)