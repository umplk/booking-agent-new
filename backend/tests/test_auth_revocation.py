"""登出与改密撤销测试。

覆盖：登出撤销当前设备 access/refresh、不影响其他设备；改密作废旧 access/refresh、
踢掉全部设备、新登录可用；内存撤销记录到期清理。
使用 FastAPI TestClient + 内存 SQLite，通过 dependency_overrides 注入测试数据库。
"""
import os
import sys
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["DEEPSEEK_API_KEY"] = "fake-key-for-testing"

# 支持直接运行本文件（python tests/test_auth_revocation.py）时找到 backend/app
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import time
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.models.user import User
from app.utils import token_store
from app.utils.security import get_password_hash
import app.main

# 测试固定使用进程内撤销存储，避免污染 Memurai 中的真实数据
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


class RevocationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=test_engine)

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=test_engine)

    def setUp(self):
        token_store.reset()
        self.username = "revoke_" + self._testMethodName
        db = TestSessionLocal()
        try:
            user = User(
                username=self.username,
                email=self.username + "@example.com",
                password_hash=get_password_hash("pass123"),
                role="student",
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            self.user_id = user.id
        finally:
            db.close()

    @staticmethod
    def _auth(token):
        return {"Authorization": "Bearer " + token}

    def _login(self, password="pass123"):
        resp = client.post(
            "/api/auth/login",
            json={"username": self.username, "password": password},
        )
        self.assertEqual(resp.status_code, 200, resp.json())
        return resp.json()["data"]

    def _me_status(self, token):
        return client.get("/api/users/me", headers=self._auth(token)).status_code

    def _refresh_status(self, refresh_token):
        return client.post(
            "/api/auth/refresh", json={"refresh_token": refresh_token}
        ).status_code

    def _logout(self, data):
        return client.post(
            "/api/auth/logout",
            json={"refresh_token": data["refresh_token"]},
            headers=self._auth(data["access_token"]),
        )

    def _change_password(self, token, new_password="newpass123"):
        return client.put(
            "/api/users/me",
            json={"password": new_password},
            headers=self._auth(token),
        )

    # ===== 登出：只退当前设备 =====

    def test_logout_revokes_current_access(self):
        data = self._login()
        self.assertEqual(self._logout(data).status_code, 200)
        self.assertEqual(self._me_status(data["access_token"]), 401)

    def test_logout_revokes_current_refresh(self):
        data = self._login()
        self._logout(data)
        self.assertEqual(self._refresh_status(data["refresh_token"]), 401)

    def test_logout_does_not_affect_other_device(self):
        first = self._login()
        second = self._login()
        self._logout(first)
        self.assertEqual(self._me_status(second["access_token"]), 200)
        self.assertEqual(self._refresh_status(second["refresh_token"]), 200)

    # ===== 改密：踢掉全部设备 =====

    def test_password_change_revokes_old_access(self):
        data = self._login()
        time.sleep(1.1)
        self.assertEqual(self._change_password(data["access_token"]).status_code, 200)
        self.assertEqual(self._me_status(data["access_token"]), 401)

    def test_password_change_revokes_old_refresh(self):
        data = self._login()
        time.sleep(1.1)
        self._change_password(data["access_token"])
        self.assertEqual(self._refresh_status(data["refresh_token"]), 401)

    def test_password_change_kicks_all_devices(self):
        first = self._login()
        second = self._login()
        time.sleep(1.1)
        self.assertEqual(self._change_password(first["access_token"]).status_code, 200)
        self.assertEqual(self._me_status(first["access_token"]), 401)
        self.assertEqual(self._me_status(second["access_token"]), 401)
        self.assertEqual(self._refresh_status(second["refresh_token"]), 401)

    def test_new_login_after_password_change_works(self):
        data = self._login()
        time.sleep(1.1)
        self._change_password(data["access_token"])
        fresh = self._login("newpass123")
        self.assertEqual(self._me_status(fresh["access_token"]), 200)
        self.assertEqual(self._refresh_status(fresh["refresh_token"]), 200)

    def test_profile_update_without_password_keeps_session(self):
        data = self._login()
        resp = client.put(
            "/api/users/me",
            json={"name": "新名字"},
            headers=self._auth(data["access_token"]),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(self._me_status(data["access_token"]), 200)

    # ===== 进程内存储 TTL =====

    def test_memory_store_expires(self):
        token_store.revoke("unit-jti-for-ttl", 1)
        token_store.mark_password_changed(999, 1)
        self.assertTrue(token_store.is_revoked("unit-jti-for-ttl"))
        self.assertGreater(token_store.password_changed_at(999), 0)
        time.sleep(1.1)
        self.assertFalse(token_store.is_revoked("unit-jti-for-ttl"))
        self.assertEqual(token_store.password_changed_at(999), 0)


if __name__ == "__main__":
    unittest.main()