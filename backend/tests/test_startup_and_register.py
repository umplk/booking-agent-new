"""启动密钥校验与注册越权测试。

覆盖：弱密钥/短密钥/非法算法拒绝启动；学生注册正常；商家注册必须邀请码；
邀请码为空时关闭自助注册；admin 角色与弱密码被契约拦截。
测试直接调用路由函数，不依赖 TestClient 网络环境。
"""
import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["DEEPSEEK_API_KEY"] = "fake-key-for-testing"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import unittest

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import settings
from app.database import Base
from app.models.user import User
from app.routers import auth
from app.schemas.user import UserRegister
from app.utils.startup_checks import validate_jwt_config

engine = create_engine(
    "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class StartupConfigTest(unittest.TestCase):
    def setUp(self):
        self._secret = settings.JWT_SECRET_KEY
        self._algorithm = settings.JWT_ALGORITHM

    def tearDown(self):
        settings.JWT_SECRET_KEY = self._secret
        settings.JWT_ALGORITHM = self._algorithm

    def test_strong_secret_passes(self):
        settings.JWT_SECRET_KEY = "x" * 48
        settings.JWT_ALGORITHM = "HS256"
        validate_jwt_config()

    def test_default_secret_rejected(self):
        settings.JWT_SECRET_KEY = "please-change-this-to-a-random-secret-key-in-production"
        with self.assertRaises(RuntimeError):
            validate_jwt_config()

    def test_short_secret_rejected(self):
        settings.JWT_SECRET_KEY = "short-secret"
        with self.assertRaises(RuntimeError):
            validate_jwt_config()

    def test_algorithm_whitelist(self):
        settings.JWT_SECRET_KEY = "x" * 48
        settings.JWT_ALGORITHM = "none"
        with self.assertRaises(RuntimeError):
            validate_jwt_config()


class RegisterTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=engine)

    def setUp(self):
        self._invite = settings.MERCHANT_INVITE_CODE
        self.session = SessionLocal()
        self.session.query(User).delete()
        self.session.commit()

    def tearDown(self):
        settings.MERCHANT_INVITE_CODE = self._invite
        self.session.close()

    @staticmethod
    def _payload(role="student", invite_code=None, password="Pass1234", username="new_user"):
        return UserRegister(
            username=username,
            email=username + "@example.com",
            password=password,
            role=role,
            invite_code=invite_code,
        )

    def _register(self, **kwargs):
        payload = self._payload(**kwargs)
        try:
            auth.register(payload, db=self.session)
            return 200
        except HTTPException as exc:
            return exc.status_code

    def test_student_register_ok(self):
        self.assertEqual(self._register(username="student_ok"), 200)
        user = self.session.query(User).filter(User.username == "student_ok").first()
        self.assertEqual(user.role, "student")

    def test_merchant_without_invite_rejected(self):
        self.assertEqual(self._register(role="merchant", username="merchant_no_code"), 400)

    def test_merchant_wrong_invite_rejected(self):
        self.assertEqual(
            self._register(role="merchant", invite_code="wrong", username="merchant_bad"),
            400,
        )

    def test_merchant_correct_invite_ok(self):
        self.assertEqual(
            self._register(
                role="merchant",
                invite_code=settings.MERCHANT_INVITE_CODE,
                username="merchant_ok",
            ),
            200,
        )
        user = self.session.query(User).filter(User.username == "merchant_ok").first()
        self.assertEqual(user.role, "merchant")

    def test_merchant_disabled_when_code_empty(self):
        settings.MERCHANT_INVITE_CODE = ""
        self.assertEqual(
            self._register(role="merchant", invite_code="anything", username="merchant_off"),
            400,
        )

    def test_admin_role_rejected_by_schema(self):
        with self.assertRaises(ValidationError):
            self._payload(role="admin")

    def test_weak_password_rejected(self):
        with self.assertRaises(ValidationError):
            self._payload(password="pass123")
        with self.assertRaises(ValidationError):
            self._payload(password="passwordonly")
        with self.assertRaises(ValidationError):
            self._payload(password="12345678")

    def test_strong_password_accepted(self):
        payload = UserRegister(
            username="strong_user",
            email="strong_user@example.com",
            password="Pass1234",
        )
        self.assertEqual(payload.password, "Pass1234")


if __name__ == "__main__":
    unittest.main()