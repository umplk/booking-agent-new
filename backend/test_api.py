import sys
import unittest
from datetime import date, datetime, time, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException

from app import models  # noqa: F401
from app.database import Base
from app.models.resource import Resource
from app.models.scenario import Scenario
from app.models.user import User
from app.services.booking_service import (
    cancel_reservation,
    create_reservation,
    query_availability,
)

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def days(n):
    return (date.today() + timedelta(days=n)).isoformat()


def dt(days_from_now, hh, mm=0):
    return datetime.combine(date.today() + timedelta(days=days_from_now), time(hh, mm))


class BookingServiceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        cls.s1 = Scenario(
            name="自习室", time_step_minutes=30, min_duration_minutes=30,
            max_duration_minutes=240, max_advance_days=30, allow_same_day=True,
            max_active_per_user=2, cancel_before_minutes=None,
        )
        cls.s2 = Scenario(
            name="会议室", time_step_minutes=30, min_duration_minutes=30,
            max_duration_minutes=120, max_advance_days=7, allow_same_day=False,
            max_active_per_user=1, cancel_before_minutes=60,
        )
        db.add_all([cls.s1, cls.s2])
        db.flush()
        cls.r1 = Resource(scenario_id=cls.s1.id, name="A1", code="1F-A1",
                          open_start=time(8, 0), open_end=time(22, 0))
        cls.r2 = Resource(scenario_id=cls.s1.id, name="B1", code="1F-B1",
                          open_start=time(8, 0), open_end=time(18, 0))
        cls.r3 = Resource(scenario_id=cls.s2.id, name="会议室A", code="M-A",
                          open_start=time(9, 0), open_end=time(17, 0))
        db.add_all([cls.r1, cls.r2, cls.r3])
        cls.u = User(username="u1", email="u1@test.com", password_hash="x", role="student")
        cls.admin = User(username="admin", email="a@test.com", password_hash="x", role="admin")
        db.add_all([cls.u, cls.admin])
        db.commit()
        db.close()

    def setUp(self):
        self.db = SessionLocal()
        self.user = self.db.query(User).filter(User.username == "u1").first()
        self.admin = self.db.query(User).filter(User.username == "admin").first()
        self.s1 = self.db.query(Scenario).filter(Scenario.name == "自习室").first()
        self.s2 = self.db.query(Scenario).filter(Scenario.name == "会议室").first()
        self.r1 = self.db.query(Resource).filter(Resource.name == "A1").first()
        self.r2 = self.db.query(Resource).filter(Resource.name == "B1").first()
        self.r3 = self.db.query(Resource).filter(Resource.name == "会议室A").first()
        self.db.query(models.Reservation).delete()
        self.db.commit()

    def tearDown(self):
        self.db.close()

    def test_availability_slots(self):
        d = query_availability(self.db, self.s1.id, date.today() + timedelta(days=1))
        by_code = {r.code: r for r in d["resources"]}
        self.assertEqual(len(by_code["1F-A1"].free_slots), 28)
        self.assertEqual(len(by_code["1F-B1"].free_slots), 20)
        self.assertEqual(by_code["1F-A1"].free_slots[0].start, "08:00")
        self.assertEqual(by_code["1F-A1"].free_slots[-1].end, "22:00")

    def test_availability_range_filter(self):
        d = query_availability(
            self.db, self.s1.id, date.today() + timedelta(days=1),
            range_start=time(10, 0), range_end=time(12, 0),
        )
        by_code = {r.code: r for r in d["resources"]}
        self.assertEqual(len(by_code["1F-A1"].free_slots), 4)

    def test_create_reservation(self):
        r = create_reservation(
            self.db, self.user, self.s1.id, self.r1.id,
            dt(1, 9, 0), dt(1, 10, 0),
        )
        self.assertEqual(r.status, "confirmed")
        d = query_availability(self.db, self.s1.id, date.today() + timedelta(days=1))
        by_code = {r.code: r for r in d["resources"]}
        self.assertNotIn("09:00", [s.start for s in by_code["1F-A1"].free_slots])

    def test_conflict_detection(self):
        create_reservation(self.db, self.user, self.s1.id, self.r1.id, dt(1, 9, 0), dt(1, 10, 0))
        with self.assertRaises(HTTPException) as ctx:
            create_reservation(self.db, self.user, self.s1.id, self.r1.id, dt(1, 9, 30), dt(1, 10, 30))
        self.assertEqual(ctx.exception.status_code, 409)

    def test_granularity(self):
        with self.assertRaises(HTTPException) as ctx:
            create_reservation(self.db, self.user, self.s1.id, self.r1.id, dt(1, 9, 15), dt(1, 10, 0))
        self.assertIn("粒度", str(ctx.exception.detail))

    def test_duration_not_step(self):
        with self.assertRaises(HTTPException) as ctx:
            create_reservation(self.db, self.user, self.s1.id, self.r1.id, dt(1, 9, 0), dt(1, 10, 15))
        self.assertIn("整数倍", str(ctx.exception.detail))

    def test_past_time(self):
        with self.assertRaises(HTTPException) as ctx:
            create_reservation(self.db, self.user, self.s1.id, self.r1.id, dt(-1, 9, 0), dt(-1, 10, 0))
        self.assertIn("过去", str(ctx.exception.detail))

    def test_duration_too_long(self):
        with self.assertRaises(HTTPException) as ctx:
            create_reservation(self.db, self.user, self.s1.id, self.r1.id, dt(1, 9, 0), dt(1, 14, 0))
        self.assertIn("超过", str(ctx.exception.detail))

    def test_outside_open_window(self):
        with self.assertRaises(HTTPException) as ctx:
            create_reservation(self.db, self.user, self.s1.id, self.r1.id, dt(1, 7, 0), dt(1, 8, 30))
        self.assertIn("开放时间", str(ctx.exception.detail))
        with self.assertRaises(HTTPException):
            create_reservation(self.db, self.user, self.s1.id, self.r1.id, dt(1, 21, 30), dt(1, 23, 0))

    def test_same_day_disabled(self):
        with self.assertRaises(HTTPException) as ctx:
            create_reservation(self.db, self.user, self.s2.id, self.r3.id, dt(0, 10, 0), dt(0, 11, 0))
        self.assertIn("当日预约", str(ctx.exception.detail))

    def test_advance_days_limit(self):
        with self.assertRaises(HTTPException) as ctx:
            create_reservation(self.db, self.user, self.s2.id, self.r3.id, dt(8, 10, 0), dt(8, 11, 0))
        self.assertIn("提前", str(ctx.exception.detail))

    def test_max_active_per_user(self):
        create_reservation(self.db, self.user, self.s2.id, self.r3.id, dt(1, 10, 0), dt(1, 11, 0))
        with self.assertRaises(HTTPException) as ctx:
            create_reservation(self.db, self.user, self.s2.id, self.r3.id, dt(2, 10, 0), dt(2, 11, 0))
        self.assertIn("同时最多", str(ctx.exception.detail))

    def test_cancel_before_limit(self):
        r = create_reservation(self.db, self.user, self.s2.id, self.r3.id, dt(1, 10, 0), dt(1, 11, 0))
        r.start_time = datetime.now() + timedelta(minutes=30)
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            cancel_reservation(self.db, self.user, r.id)
        self.assertIn("不可取消", str(ctx.exception.detail))

    def test_cancel_and_cancel_again(self):
        r = create_reservation(self.db, self.user, self.s1.id, self.r1.id, dt(3, 9, 0), dt(3, 10, 0))
        canceled = cancel_reservation(self.db, self.user, r.id)
        self.assertEqual(canceled.status, "cancelled")
        with self.assertRaises(HTTPException) as ctx:
            cancel_reservation(self.db, self.user, r.id)
        self.assertIn("已取消", str(ctx.exception.detail))

    def test_user_permission(self):
        r = create_reservation(self.db, self.user, self.s1.id, self.r1.id, dt(3, 10, 0), dt(3, 11, 0))
        other = User(username="u2", email="u2@test.com", password_hash="x", role="student")
        self.db.add(other)
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            cancel_reservation(self.db, other, r.id)
        self.assertEqual(ctx.exception.status_code, 403)
        canceled = cancel_reservation(self.db, self.admin, r.id)
        self.assertEqual(canceled.status, "cancelled")

    def test_min_advance_minutes(self):
        self.s1.min_advance_minutes = 2000
        self.db.commit()
        try:
            with self.assertRaises(HTTPException) as ctx:
                create_reservation(self.db, self.user, self.s1.id, self.r1.id, dt(1, 9, 0), dt(1, 10, 0))
            self.assertIn("至少提前", str(ctx.exception.detail))
        finally:
            self.s1.min_advance_minutes = 0
            self.db.commit()

    def test_max_minutes_per_day(self):
        self.s1.max_minutes_per_day = 60
        self.db.commit()
        try:
            create_reservation(self.db, self.user, self.s1.id, self.r1.id, dt(1, 9, 0), dt(1, 10, 0))
            with self.assertRaises(HTTPException) as ctx:
                create_reservation(self.db, self.user, self.s1.id, self.r2.id, dt(1, 11, 0), dt(1, 11, 30))
            self.assertIn("每日预约总时长", str(ctx.exception.detail))
        finally:
            self.s1.max_minutes_per_day = None
            self.db.commit()


class AppAssemblyTest(unittest.TestCase):
    def test_routes_registered(self):
        from app.main import app
        paths = {route.path for route in app.routes}
        for expected in [
            "/api/auth/login",
            "/api/users/me",
            "/api/scenarios",
            "/api/scenarios/{scenario_id}/availability",
            "/api/scenarios/{scenario_id}/resources",
            "/api/reservations",
            "/api/reservations/{reservation_id}/cancel",
            "/api/agent/chat",
        ]:
            self.assertIn(expected, paths)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)