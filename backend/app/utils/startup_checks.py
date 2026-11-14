"""启动阶段的安全配置校验。

放在 lifespan 而不是 config 模块级，避免测试、脚本、CLI 被误伤；
只有真正启动服务时才校验，失败直接拒绝启动。
"""
import logging

from app.config import settings

logger = logging.getLogger("app")

WEAK_SECRET_KEYS = {
    "please-change-this-to-a-random-secret-key-in-production",
    "replace-with-a-random-secret-generated-by-secrets-token-urlsafe",
    "secret",
    "changeme",
}
ALLOWED_JWT_ALGORITHMS = {"HS256", "HS384", "HS512"}
MIN_SECRET_LENGTH = 32
WEAK_DEFAULT_PASSWORDS = {"admin123", "merchant123", "123456", "password", "admin", "merchant"}


def _secret_help() -> str:
    return 'python -c "import secrets; print(secrets.token_urlsafe(48))"'


def validate_jwt_config() -> None:
    """弱密钥或非法算法直接抛 RuntimeError，uvicorn 会因此启动失败。"""
    secret = (settings.JWT_SECRET_KEY or "").strip()
    if secret in WEAK_SECRET_KEYS:
        raise RuntimeError(
            "JWT_SECRET_KEY 仍为默认或示例值，拒绝启动。请生成强密钥：" + _secret_help()
        )
    if len(secret) < MIN_SECRET_LENGTH:
        raise RuntimeError(
            f"JWT_SECRET_KEY 长度不足 {MIN_SECRET_LENGTH} 位（当前 {len(secret)} 位），"
            "拒绝启动。请生成强密钥：" + _secret_help()
        )
    if settings.JWT_ALGORITHM not in ALLOWED_JWT_ALGORITHMS:
        raise RuntimeError(
            f"JWT_ALGORITHM={settings.JWT_ALGORITHM} 不在允许列表 "
            f"{sorted(ALLOWED_JWT_ALGORITHMS)} 中，拒绝启动。"
        )


def warn_default_credentials() -> None:
    """默认账号仍是弱口令时只告警，不阻断本地开发（第 4 期由登录限流兜底）。"""
    if settings.DEFAULT_ADMIN_PASSWORD.strip() in WEAK_DEFAULT_PASSWORDS:
        logger.warning(
            "默认管理员密码仍为弱口令，请尽快修改：%s", settings.DEFAULT_ADMIN_USERNAME
        )
    if settings.DEFAULT_MERCHANT_PASSWORD.strip() in WEAK_DEFAULT_PASSWORDS:
        logger.warning(
            "默认商家密码仍为弱口令，请尽快修改：%s", settings.DEFAULT_MERCHANT_USERNAME
        )