"""商家登录与权限控制测试。

覆盖：登录成功/失败、未登录访问、普通用户越权、跨商家数据访问、正常商家操作。
使用 FastAPI TestClient + 内存 SQLite，通过 dependency_overrides 注入测试数据库。
"""
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["DEEPSEEK_API_KEY"] = "fake-key-for-testing"

import unittest
from datetime import date, datetime, time, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.models.user import User
from app.models.scenario import Scenario
from app.models.resource import Resource
from app.utils.security import get_password_hash
import app.main

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


def _scenario_payload(name="测试场景"):
    return {
        "name": name,
        "time_step_minutes": 30,
        "min_duration_minutes": 30,
        "max_duration_minutes": 120,
        "max_advance_days": 30,
        "min_advance_minutes": 0,
        "allow_same_day": True,
        "max_active_per_user": 3,
    }


def _resource_payload(name="资源1", code="R1"):
    return {"name": name, "code": code, "open_start": "08:00", "open_end": "22:00"}


def _future_slot(day_offset=2, hour=9):
    start = datetime.combine(date.today() + timedelta(days=day_offset), time(hour, 0))
    end = datetime.combine(date.today() + timedelta(days=day_offset), time(hour + 1, 0))
    return start.isoformat(), end.isoformat()


class AuthPermissionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=test_engine)
        db = TestSessionLocal()
        try:
            ma = User(username="merchant_a", email="ma@test.com",
                      password_hash=get_password_hash("pass123"), name="商家A", role="merchant")
            mb = User(username="merchant_b", email="mb@test.com",
                      password_hash=get_password_hash("pass123"), name="商家B", role="merchant")
            st = User(username="student1", email="s1@test.com",
                      password_hash=get_password_hash("pass123"), name="学生", role="student")
            ad = User(username="admin", email="admin@test.com",
                      password_hash=get_password_hash("pass123"), name="管理员", role="admin")
            db.add_all([ma, mb, st, ad])
            db.commit()
            cls.merchant_a_id = ma.id
            cls.merchant_b_id = mb.id
            cls.student_id = st.id
            cls.admin_id = ad.id

            sa = Scenario(name="场景A", owner_id=ma.id, time_step_minutes=30,
                          min_duration_minutes=30, max_duration_minutes=120, max_advance_days=30,
                          allow_same_day=True, max_active_per_user=3, is_active=True)
            sb = Scenario(name="场景B", owner_id=mb.id, time_step_minutes=30,
                          min_duration_minutes=30, max_duration_minutes=120, max_advance_days=30,
                          allow_same_day=True, max_active_per_user=3, is_active=True)
            db.add_all([sa, sb])
            db.commit()
            cls.scenario_a_id = sa.id
            cls.scenario_b_id = sb.id

            ra = Resource(scenario_id=sa.id, name="资源A1", code="A1",
                          open_start=time(8, 0), open_end=time(22, 0), is_active=True)
            rb = Resource(scenario_id=sb.id, name="资源B1", code="B1",
                          open_start=time(8, 0), open_end=time(22, 0), is_active=True)
            db.add_all([ra, rb])
            db.commit()
            cls.resource_a_id = ra.id
            cls.resource_b_id = rb.id
        finally:
            db.close()

        cls.token_a = cls._login("merchant_a", "pass123")
        cls.token_b = cls._login("merchant_b", "pass123")
        cls.token_student = cls._login("student1", "pass123")
        cls.token_admin = cls._login("admin", "pass123")

    @classmethod
    def tearDownClass(cls):
        Base.metadata.drop_all(bind=test_engine)

    @staticmethod
    def _login(username, password):
        resp = client.post("/api/auth/login", json={"username": username, "password": password})
        assert resp.status_code == 200, f"预置登录失败: {resp.json()}"
        return resp.json()["data"]["access_token"]

    @staticmethod
    def _auth(token):
        return {"Authorization": f"Bearer {token}"}

    # ===== 登录成功与失败 =====

    def test_login_success_merchant(self):
        resp = client.post("/api/auth/login", json={"username": "merchant_a", "password": "pass123"})
        self.assertEqual(resp.status_code, 200)
        self.assertIn("access_token", resp.json()["data"])

    def test_login_success_admin(self):
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "pass123"})
        self.assertEqual(resp.status_code, 200)

    def test_login_wrong_password(self):
        resp = client.post("/api/auth/login", json={"username": "merchant_a", "password": "wrong"})
        self.assertEqual(resp.status_code, 401)

    def test_login_nonexistent_user(self):
        resp = client.post("/api/auth/login", json={"username": "nobody", "password": "pass123"})
        self.assertEqual(resp.status_code, 401)

    # ===== 未登录访问 =====

    def test_unauthenticated_create_scenario(self):
        resp = client.post("/api/scenarios", json=_scenario_payload())
        self.assertEqual(resp.status_code, 401)

    def test_unauthenticated_create_resource(self):
        resp = client.post(f"/api/scenarios/{self.scenario_a_id}/resources", json=_resource_payload())
        self.assertEqual(resp.status_code, 401)

    def test_unauthenticated_admin_reservations(self):
        resp = client.get("/api/reservations/admin")
        self.assertEqual(resp.status_code, 401)

    def test_unauthenticated_cancel_reservation(self):
        resp = client.put("/api/reservations/1/cancel")
        self.assertEqual(resp.status_code, 401)

    # ===== 普通用户越权 =====

    def test_student_cannot_create_scenario(self):
        resp = client.post("/api/scenarios", json=_scenario_payload(), headers=self._auth(self.token_student))
        self.assertEqual(resp.status_code, 403)

    def test_student_cannot_create_resource(self):
        resp = client.post(
            f"/api/scenarios/{self.scenario_a_id}/resources",
            json=_resource_payload(), headers=self._auth(self.token_student),
        )
        self.assertEqual(resp.status_code, 403)

    def test_student_cannot_update_scenario(self):
        resp = client.put(
            f"/api/scenarios/{self.scenario_a_id}",
            json={"name": "hack"}, headers=self._auth(self.token_student),
        )
        self.assertEqual(resp.status_code, 403)

    def test_student_cannot_delete_scenario(self):
        resp = client.delete(f"/api/scenarios/{self.scenario_a_id}", headers=self._auth(self.token_student))
        self.assertEqual(resp.status_code, 403)

    def test_student_cannot_access_admin_reservations(self):
        resp = client.get("/api/reservations/admin", headers=self._auth(self.token_student))
        self.assertEqual(resp.status_code, 403)

    # ===== 跨商家数据访问 =====

    def test_cross_merchant_update_scenario(self):
        resp = client.put(
            f"/api/scenarios/{self.scenario_a_id}",
            json={"name": "stolen"}, headers=self._auth(self.token_b),
        )
        self.assertEqual(resp.status_code, 403)

    def test_cross_merchant_delete_scenario(self):
        resp = client.delete(f"/api/scenarios/{self.scenario_a_id}", headers=self._auth(self.token_b))
        self.assertEqual(resp.status_code, 403)

    def test_cross_merchant_create_resource(self):
        resp = client.post(
            f"/api/scenarios/{self.scenario_a_id}/resources",
            json=_resource_payload("hack", "H1"), headers=self._auth(self.token_b),
        )
        self.assertEqual(resp.status_code, 403)

    def test_cross_merchant_update_resource(self):
        resp = client.put(
            f"/api/scenarios/{self.scenario_a_id}/resources/{self.resource_a_id}",
            json={"name": "stolen"}, headers=self._auth(self.token_b),
        )
        self.assertEqual(resp.status_code, 403)

    def test_cross_merchant_delete_resource(self):
        resp = client.delete(
            f"/api/scenarios/{self.scenario_a_id}/resources/{self.resource_a_id}",
            headers=self._auth(self.token_b),
        )
        self.assertEqual(resp.status_code, 403)

    def test_cross_merchant_cancel_reservation(self):
        start, end = _future_slot(3, 9)
        resp = client.post("/api/reservations", json={
            "scenario_id": self.scenario_a_id,
            "resource_id": self.resource_a_id,
            "start_time": start, "end_time": end,
        }, headers=self._auth(self.token_student))
        self.assertEqual(resp.status_code, 200)
        rid = resp.json()["data"]["id"]

        resp = client.put(f"/api/reservations/{rid}/cancel", headers=self._auth(self.token_b))
        self.assertEqual(resp.status_code, 403)

    # ===== 正常商家操作 =====

    def test_merchant_can_create_scenario(self):
        resp = client.post(
            "/api/scenarios", json=_scenario_payload("我的新场景"), headers=self._auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["data"]["owner_id"], self.merchant_a_id)

    def test_merchant_can_update_own_scenario(self):
        resp = client.put(
            f"/api/scenarios/{self.scenario_a_id}",
            json={"description": "更新描述"}, headers=self._auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 200)

    def test_merchant_can_create_resource(self):
        resp = client.post(
            f"/api/scenarios/{self.scenario_a_id}/resources",
            json=_resource_payload("新资源", "NEW1"), headers=self._auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 200)

    def test_merchant_can_update_own_resource(self):
        resp = client.put(
            f"/api/scenarios/{self.scenario_a_id}/resources/{self.resource_a_id}",
            json={"name": "改名"}, headers=self._auth(self.token_a),
        )
        self.assertEqual(resp.status_code, 200)

    def test_mine_filter_returns_only_own(self):
        resp = client.get("/api/scenarios?mine=true", headers=self._auth(self.token_a))
        self.assertEqual(resp.status_code, 200)
        items = resp.json()["data"]["items"]
        self.assertTrue(all(item["owner_id"] == self.merchant_a_id for item in items))
        self.assertTrue(any(item["id"] == self.scenario_a_id for item in items))
        self.assertFalse(any(item["id"] == self.scenario_b_id for item in items))

    def test_merchant_admin_reservations_filtered(self):
        resp = client.get("/api/reservations/admin", headers=self._auth(self.token_a))
        self.assertEqual(resp.status_code, 200)
        for item in resp.json()["data"]:
            self.assertEqual(item["scenario_id"], self.scenario_a_id)

    def test_merchant_can_cancel_own_scenario_reservation(self):
        start, end = _future_slot(2, 9)
        resp = client.post("/api/reservations", json={
            "scenario_id": self.scenario_a_id,
            "resource_id": self.resource_a_id,
            "start_time": start, "end_time": end,
        }, headers=self._auth(self.token_student))
        self.assertEqual(resp.status_code, 200)
        rid = resp.json()["data"]["id"]

        resp = client.put(f"/api/reservations/{rid}/cancel", headers=self._auth(self.token_a))
        self.assertEqual(resp.status_code, 200)

    def test_admin_can_access_admin_reservations(self):
        resp = client.get("/api/reservations/admin", headers=self._auth(self.token_admin))
        self.assertEqual(resp.status_code, 200)

    def test_admin_can_manage_any_scenario(self):
        resp = client.put(
            f"/api/scenarios/{self.scenario_a_id}",
            json={"description": "admin改的"}, headers=self._auth(self.token_admin),
        )
        self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
