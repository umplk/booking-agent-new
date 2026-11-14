"""LLM 调用的超时、并发与熔断保护。

单请求超时与 SDK 重试在客户端侧配置；本模块负责两件 SDK 不管的事：
1. 并发上限：同时打到 DeepSeek 的请求不超过阈值，排队超时直接降级，避免把线程池占满。
2. 熔断：连续失败达到阈值后打开 60 秒，期间不再调用上游、直接抛 CircuitOpenError，
   由调用方走规则/正则降级；冷却后只放一个探测请求，成功才恢复。

熔断与并发限制只包住 LLM 调用本身，不改变业务降级路径。
"""
import logging
import threading
import time
from app.config import settings
from app.utils.fallback_metrics import record_fallback

logger = logging.getLogger(__name__)


class CircuitOpenError(RuntimeError):
    """熔断打开期间拒绝调用上游。"""


class ConcurrencyLimitError(RuntimeError):
    """排队等待并发槽位超时。"""


class LLMGuard:
    def __init__(
        self,
        max_concurrency: int,
        queue_wait_seconds: float,
        failure_threshold: int,
        cooldown_seconds: float,
    ):
        self._semaphore = threading.BoundedSemaphore(max(1, int(max_concurrency)))
        self._queue_wait_seconds = max(0.0, float(queue_wait_seconds))
        self._failure_threshold = max(1, int(failure_threshold))
        self._cooldown_seconds = max(0.0, float(cooldown_seconds))

        self._lock = threading.Lock()
        self._state = "closed"
        self._failures = 0
        self._opened_at = 0.0
        self._half_open_inflight = False

    @property
    def state(self) -> str:
        with self._lock:
            return self._state

    def invoke(self, chain, prompt: str):
        self._acquire_slot()
        try:
            result = chain.invoke(prompt)
        except Exception:
            self._record_failure()
            raise
        else:
            self._record_success()
            return result
        finally:
            self._semaphore.release()

    def _acquire_slot(self) -> None:
        with self._lock:
            now = time.time()
            if self._state == "open":
                if now - self._opened_at < self._cooldown_seconds:
                    raise CircuitOpenError(
                        f"LLM 熔断中，{self._cooldown_seconds:.0f} 秒后重试"
                    )
                self._state = "half_open"
            if self._state == "half_open":
                if self._half_open_inflight:
                    raise CircuitOpenError("LLM 熔断半开探测进行中")
                self._half_open_inflight = True

        acquired = self._semaphore.acquire(timeout=self._queue_wait_seconds)
        if not acquired:
            with self._lock:
                if self._state == "half_open":
                    self._half_open_inflight = False
            raise ConcurrencyLimitError(
                f"LLM 排队超过 {self._queue_wait_seconds:.0f} 秒，直接降级"
            )

    def _record_success(self) -> None:
        with self._lock:
            self._failures = 0
            self._state = "closed"
            self._half_open_inflight = False

    def _record_failure(self) -> None:
        opened = False
        with self._lock:
            if self._state == "half_open":
                self._state = "open"
                self._opened_at = time.time()
                self._half_open_inflight = False
                self._failures = self._failure_threshold
                opened = True
            else:
                self._failures += 1
                if self._failures >= self._failure_threshold:
                    self._state = "open"
                    self._opened_at = time.time()
                    opened = True

        if opened:
            logger.error(
                "LLM 熔断打开：连续失败 %s 次，%s 秒内直接走降级",
                self._failures,
                self._cooldown_seconds,
            )
            record_fallback(
                "circuit",
                "opened",
                {"failures": self._failures, "cooldown_s": round(self._cooldown_seconds, 1)},
            )

    def reset(self) -> None:
        with self._lock:
            self._state = "closed"
            self._failures = 0
            self._opened_at = 0.0
            self._half_open_inflight = False


_guard = LLMGuard(
    max_concurrency=settings.LLM_MAX_CONCURRENCY,
    queue_wait_seconds=settings.LLM_QUEUE_WAIT_SECONDS,
    failure_threshold=settings.LLM_CIRCUIT_FAILURE_THRESHOLD,
    cooldown_seconds=settings.LLM_CIRCUIT_COOLDOWN_SECONDS,
)


def guarded_invoke(chain, prompt: str):
    """所有 LLM 调用统一走这里：并发上限 + 熔断，失败由调用方降级。"""
    return _guard.invoke(chain, prompt)


def guard_state() -> str:
    return _guard.state


def reset_guard() -> None:
    """重置熔断状态（测试与运维手动恢复用）。"""
    _guard.reset()