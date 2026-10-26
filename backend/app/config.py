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
        os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
    )

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
