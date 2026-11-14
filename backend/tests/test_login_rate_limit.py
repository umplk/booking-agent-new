"""登录限流测试。

覆盖：账号达到阈值锁定、锁定期间正确密码也拒绝、Retry-After 与中文提示、
OAuth2 表单入口同样受限、不存在用户名累计、成功登录清零、IP 维度锁定、
账号锁定不影响同 IP 其他用户、锁定到期自动解锁。
测试直接调用路由函数，不依赖 TestClient 网络环境。
"""
import os
import sys
import time
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["DEEPSEEK_API_KEY"] = "fake-key-for-testing"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import unittest

from fastapi import HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from starlette.requests import Request

from app.config import settings
from app.database import Base
from app.models.user import User
from app.routers import auth
from app.schemas.user import UserLogin
from app.utils import token_store
from app.utils.security import get_password_hash

engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def make_request(ip="127.0.0.1"):
    scope = {
        "type": "http",
        "method": "POST",
        "path": "/api/auth/login",
        "headers": [],
        "client": (ip, 1234),
        "server": ("testserver", 80),
        "scheme": "http",
        "query_string": b"",
    }
    return Request(scope)


class LoginRateLimitTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)

    def setUp(self):
        token_store._backend = "memory"
        token_store._redis_client = None
        token_store.reset()

        self._config = {
            "LOGIN_MAX_FAILURES": settings.LOGIN_MAX_FAILURES,
            "LOGIN_LOCK_MINUTES": settings.LOGIN_LOCK_MINUTES,
            "LOGIN_IP_MAX_FAILURES": settings.LOGIN_IP_MAX_FAILURES,
            "LOGIN_IP_LOCK_MINUTES": settings.LOGIN_IP_LOCK_MINUTES,
        }
        settings.LOGIN_MAX_FAILURES = 2
        settings.LOGIN_LOCK_MINUTES = 15
        settings.LOGIN_IP_MAX_FAILURES = 3
        settings.LOGIN_IP_LOCK_MINUTES = 15

        self.session = SessionLocal()
        self.session.query(User).delete()
        self.session.commit()
        for name in ("limit_user", "other_user"):
            self.session.add(User(
                username=name,
                email=name + "@example.com",
                password_hash=get_password_hash("Pass1234"),
                role="student",
            ))
        self.session.commit()

    def tearDown(self):
        for key, value in self._config.items():
            setattr(settings, key, value)
        self.session.close()

    def _login(self, username="limit_user", password="wrong", ip="127.0.0.1"):
        try:
            auth.login(UserLogin(username=username, password=password), make_request(ip), self.session)
            return 200, None
        except HTTPException as exc:
            return exc.status_code, exc

    def _form_login(self, username="limit_user", password="wrong", ip="127.0.0.1"):
        form = OAuth2PasswordRequestForm(username=username, password=password)
        try:
            auth.login_form(make_request(ip), form, self.session)
            return 200, None
        except HTTPException as exc:
            return exc.status_code, exc

    def _lock_user(self, username="limit_user", ip="127.0.0.1"):
        self._login(username=username, password="wrong", ip=ip)
        self._login(username=username, password="wrong", ip=ip)

    def test_locks_after_max_failures(self):
        self.assertEqual(self._login(password="wrong")[0], 401)
        self.assertEqual(self._login(password="wrong")[0], 401)
        status, _ = self._login(password="wrong")
        self.assertEqual(status, 429)

    def test_locked_rejects_correct_password(self):
        self._lock_user()
        status, _ = self._login(password="Pass1234")
        self.assertEqual(status, 429)

    def test_retry_after_and_message(self):
        self._lock_user()
        _, exc = self._login(password="wrong")
        self.assertIn("分钟", exc.detail)
        self.assertGreater(int(exc.headers["Retry-After"]), 0)

    def test_form_endpoint_also_limited(self):
        self.assertEqual(self._form_login(password="wrong")[0], 401)
        self.assertEqual(self._form_login(password="wrong")[0], 401)
        status, _ = self._form_login(password="Pass1234")
        self.assertEqual(status, 429)

    def test_unknown_username_counts(self):
        self._login(username="nobody", password="wrong")
        self._login(username="nobody", password="wrong")
        status, _ = self._login(username="nobody", password="wrong")
        self.assertEqual(status, 429)

    def test_success_clears_user_counter(self):
        self._login(password="wrong")
        self.assertEqual(self._login(password="Pass1234")[0], 200)

        self._login(password="wrong")
        self.assertEqual(self._login(password="Pass1234")[0], 200)

    def test_ip_dimension_locks_shared_ip(self):
        for name in ("u1", "u2", "u3"):
            self._login(username=name, password="wrong", ip="10.0.0.9")
        status, _ = self._login(password="Pass1234", ip="10.0.0.9")
        self.assertEqual(status, 429)

    def test_account_lock_does_not_block_other_user_same_ip(self):
        self._lock_user()
        status, _ = self._login(username="other_user", password="Pass1234")
        self.assertEqual(status, 200)

    def test_lock_expires(self):
        settings.LOGIN_LOCK_MINUTES = 0.02
        self._lock_user()
        self.assertEqual(self._login(password="Pass1234")[0], 429)

        time.sleep(1.2)
        status, _ = self._login(password="Pass1234")
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()