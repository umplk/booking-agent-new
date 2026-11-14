"""登录失败限流。

账号维度：连续失败 LOGIN_MAX_FAILURES 次锁定 LOGIN_LOCK_MINUTES 分钟；
IP 维度：同一 IP 连续失败 LOGIN_IP_MAX_FAILURES 次锁定 LOGIN_IP_LOCK_MINUTES 分钟。
锁定期间不再累计失败、也不延长锁定，避免攻击者持续请求把账号永久锁死。
"""
import math

from app.config import settings
from app.utils import token_store

USER_FAIL_PREFIX = "login:fail:user:"
USER_LOCK_PREFIX = "login:lock:user:"
IP_FAIL_PREFIX = "login:fail:ip:"
IP_LOCK_PREFIX = "login:lock:ip:"


def _user_window() -> int:
    return max(int(settings.LOGIN_LOCK_MINUTES * 60), 1)


def _ip_window() -> int:
    return max(int(settings.LOGIN_IP_LOCK_MINUTES * 60), 1)


def remaining_lock(username: str, client_ip: str) -> int:
    """返回还需等待的秒数；0 表示未锁定。"""
    return max(
        token_store.ttl(USER_LOCK_PREFIX + username),
        token_store.ttl(IP_LOCK_PREFIX + client_ip),
    )


def record_failure(username: str, client_ip: str) -> None:
    user_count = token_store.incr(USER_FAIL_PREFIX + username, _user_window())
    if user_count >= settings.LOGIN_MAX_FAILURES:
        token_store.set_value(USER_LOCK_PREFIX + username, _user_window())
        token_store.delete(USER_FAIL_PREFIX + username)

    ip_count = token_store.incr(IP_FAIL_PREFIX + client_ip, _ip_window())
    if ip_count >= settings.LOGIN_IP_MAX_FAILURES:
        token_store.set_value(IP_LOCK_PREFIX + client_ip, _ip_window())
        token_store.delete(IP_FAIL_PREFIX + client_ip)


def clear_user_failures(username: str) -> None:
    """登录成功只清账号计数；IP 计数靠窗口自然过期，避免撞库者偶尔登对就洗白 IP。"""
    token_store.delete(USER_FAIL_PREFIX + username)


def format_wait(seconds: int) -> str:
    if seconds >= 60:
        return f"{math.ceil(seconds / 60)} 分钟"
    return f"{max(seconds, 1)} 秒"