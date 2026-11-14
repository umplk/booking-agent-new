import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./study_room.db")

    JWT_SECRET_KEY: str = os.getenv(
        "JWT_SECRET_KEY", "please-change-this-to-a-random-secret-key-in-production"
    )
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15")
    )
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = int(
        os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")
    )
    JWT_ISSUER: str = os.getenv("JWT_ISSUER", "booking-platform")
    JWT_AUDIENCE: str = os.getenv("JWT_AUDIENCE", "booking-web")

    # 令牌撤销列表（refresh 轮换、登出、改密）使用的 Redis；留空则降级为进程内存储
    REDIS_URL: str = os.getenv("REDIS_URL", "")

    # 商家自助注册邀请码；留空则关闭商家自助注册（只能由管理员创建）
    MERCHANT_INVITE_CODE: str = os.getenv("MERCHANT_INVITE_CODE", "")

    # 登录限流：账号维度 5 次/15 分钟，IP 维度 20 次/15 分钟
    LOGIN_MAX_FAILURES: int = int(os.getenv("LOGIN_MAX_FAILURES", "5"))
    LOGIN_LOCK_MINUTES: int = int(os.getenv("LOGIN_LOCK_MINUTES", "15"))
    LOGIN_IP_MAX_FAILURES: int = int(os.getenv("LOGIN_IP_MAX_FAILURES", "20"))
    LOGIN_IP_LOCK_MINUTES: int = int(os.getenv("LOGIN_IP_LOCK_MINUTES", "15"))

    CORS_ORIGINS: str = os.getenv("CORS_ORIGINS", "*")

    DEFAULT_ADMIN_USERNAME: str = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
    DEFAULT_ADMIN_PASSWORD: str = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")

    DEFAULT_MERCHANT_USERNAME: str = os.getenv("DEFAULT_MERCHANT_USERNAME", "merchant")
    DEFAULT_MERCHANT_PASSWORD: str = os.getenv("DEFAULT_MERCHANT_PASSWORD", "merchant123")

    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL: str = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")

    @property
    def is_sqlite(self) -> bool:
        return self.DATABASE_URL.startswith("sqlite")


settings = Settings()
