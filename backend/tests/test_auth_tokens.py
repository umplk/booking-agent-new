"""双 Token 与 refresh 轮换测试。

覆盖：登录返回双 Token、access/refresh 类型隔离、refresh 轮换、旧 refresh 复用拒绝。
使用 FastAPI TestClient + 内存 SQLite，通过 dependency_overrides 注入测试数据库。
"""
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["DEEPSEEK_API_KEY"] = "fake-key-for-testing"

import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.models.user import User
from app.utils import token_store
from app.utils.security import (
    ACCESS_TOKEN_TYPE,
    REFRESH_TOKEN_TYPE,
    decode_token,
    get_password_hash,
)
import app.main

# 测试固定使用进程内撤销存储，避免连接或污染真实 Redis
token_store._backend = "memory"
token_store._redis_client = None

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

app.main.engine = test_engine
app.main.SessionLocal = TestSessionLocal


def _get_test_db():
    db = TestSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.main.app.dependency_overrides[get_db] = _get_test_db

client = TestClient(app.main.app)


class TokenLifecycleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=test_engine)
        db = TestSessionLocal()
        try:
            db.add(User(
                username="token_user",
                email="token_user@example.com",
                password_hash=get_password_hash("pass123"),
                role="student",
            ))
            db.commit()
        finally:
            db.close()

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=test_engine)

    @staticmethod
    def _login():
        resp = client.post("/api/auth/login", json={"username": "token_user", "password": "pass123"})
        assert resp.status_code == 200, f"登录失败: {resp.json()}"
        return resp.json()["data"]

    def test_login_returns_dual_tokens(self):
        data = self._login()
        self.assertIn("access_token", data)
        self.assertIn("refresh_token", data)
        self.assertEqual(data["token_type"], "bearer")
        self.assertGreater(data["expires_in"], 0)

    def test_token_claims_contain_jti_type_iss_aud(self):
        data = self._login()
        payload = decode_token(data["access_token"], expected_type=ACCESS_TOKEN_TYPE)
        self.assertIsNotNone(payload)
        for claim in ("jti", "iat", "exp", "iss", "aud", "type", "sub"):
            self.assertIn(claim, payload)
        self.assertEqual(payload["type"], ACCESS_TOKEN_TYPE)

        refresh_payload = decode_token(data["refresh_token"], expected_type=REFRESH_TOKEN_TYPE)
        self.assertIsNotNone(refresh_payload)
        self.assertEqual(refresh_payload["type"], REFRESH_TOKEN_TYPE)

    def test_refresh_rotates_and_issues_working_access(self):
        data = self._login()
        resp = client.post("/api/auth/refresh", json={"refresh_token": data["refresh_token"]})
        self.assertEqual(resp.status_code, 200)
        new_data = resp.json()["data"]
        self.assertNotEqual(new_data["refresh_token"], data["refresh_token"])

        me = client.get(
            "/api/users/me",
            headers={"Authorization": "Bearer " + new_data["access_token"]},
        )
        self.assertEqual(me.status_code, 200)
        self.assertEqual(me.json()["data"]["username"], "token_user")

    def test_old_refresh_cannot_be_reused(self):
        data = self._login()
        first = client.post("/api/auth/refresh", json={"refresh_token": data["refresh_token"]})
        self.assertEqual(first.status_code, 200)

        second = client.post("/api/auth/refresh", json={"refresh_token": data["refresh_token"]})
        self.assertEqual(second.status_code, 401)

    def test_access_token_rejected_as_refresh(self):
        data = self._login()
        resp = client.post("/api/auth/refresh", json={"refresh_token": data["access_token"]})
        self.assertEqual(resp.status_code, 401)

    def test_refresh_token_rejected_as_access(self):
        data = self._login()
        resp = client.get(
            "/api/users/me",
            headers={"Authorization": "Bearer " + data["refresh_token"]},
        )
        self.assertEqual(resp.status_code, 401)

    def test_invalid_refresh_rejected(self):
        resp = client.post("/api/auth/refresh", json={"refresh_token": "not-a-token"})
        self.assertEqual(resp.status_code, 401)

    def test_oauth2_token_endpoint_returns_dual_tokens(self):
        resp = client.post(
            "/api/auth/token",
            data={"username": "token_user", "password": "pass123"},
        )
        self.assertEqual(resp.status_code, 200)
        body = resp.json()
        self.assertIn("access_token", body)
        self.assertIn("refresh_token", body)
        self.assertEqual(body["token_type"], "bearer")


if __name__ == "__main__":
    unittest.main()