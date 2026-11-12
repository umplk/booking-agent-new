"""令牌撤销列表。

access/refresh 均为无状态 JWT，只能靠 jti 黑名单让已签发的令牌提前失效：
- refresh 轮换：旧 refresh 用一次即撤销
- 后续登出、改密也会复用同一套接口

Redis 可用时写入 Redis；未配置或连接失败时降级为进程内 TTL 字典并输出告警，
降级模式下多进程部署的撤销状态不共享（单机开发/演示可接受）。
"""
import logging
import threading
import time

from app.config import settings

logger = logging.getLogger("app")

_KEY_PREFIX = "jwt:revoked:"

_memory: dict = {}
_lock = threading.Lock()
_redis_client = None
_backend = None


def _connect_redis():
    if not settings.REDIS_URL:
        return None
    try:
        import redis
    except ImportError:
        logger.warning("未安装 redis 包，令牌撤销列表降级为进程内存储")
        return None
    try:
        client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
        )
        client.ping()
        return client
    except Exception as exc:  # 连接失败、认证失败、服务未启动等
        logger.warning("Redis 不可用（%s），令牌撤销列表降级为进程内存储", exc)
        return None


def init_token_store() -> None:
    """应用启动时初始化一次，并明确告知当前使用的存储后端。"""
    global _redis_client, _backend
    if _backend is not None:
        return
    _redis_client = _connect_redis()
    _backend = "redis" if _redis_client is not None else "memory"
    if _backend == "memory":
        logger.warning("令牌撤销列表使用进程内存储：重启后撤销状态丢失，多进程不共享")
    else:
        logger.info("令牌撤销列表已连接 Redis：%s", settings.REDIS_URL)


def _ensure_backend() -> None:
    if _backend is None:
        init_token_store()


def _purge_expired(now: float) -> None:
    expired = [jti for jti, expire_at in _memory.items() if expire_at <= now]
    for jti in expired:
        _memory.pop(jti, None)


def revoke(jti: str, ttl_seconds: int) -> None:
    """将 jti 加入黑名单，ttl_seconds 取该令牌的剩余有效期。"""
    if not jti:
        return
    _ensure_backend()
    ttl = max(int(ttl_seconds), 1)
    if _redis_client is not None:
        try:
            _redis_client.setex(_KEY_PREFIX + jti, ttl, "1")
            return
        except Exception as exc:
            logger.warning("写入 Redis 失败（%s），本次撤销改存进程内", exc)
    now = time.time()
    with _lock:
        _purge_expired(now)
        _memory[jti] = now + ttl


def is_revoked(jti: str) -> bool:
    if not jti:
        return False
    _ensure_backend()
    if _redis_client is not None:
        try:
            return _redis_client.exists(_KEY_PREFIX + jti) == 1
        except Exception as exc:
            logger.warning("读取 Redis 失败（%s），本次改查进程内", exc)
    now = time.time()
    with _lock:
        expire_at = _memory.get(jti)
        if expire_at is None:
            return False
        if expire_at <= now:
            _memory.pop(jti, None)
            return False
        return True


def reset() -> None:
    """清空进程内撤销记录（测试用）。"""
    with _lock:
        _memory.clear()