import sys
import unittest
from datetime import date, time, timedelta

from langchain_core.messages import HumanMessage
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.agent.classifier import detect_intent, resolve_relative_date
from app.config import settings as app_settings
from app.database import Base
from app.models.resource import Resource
from app.models.scenario import Scenario
from app.models.user import User
import app.agent.nodes as nodes
import app.agent.tools as tools

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class AgentFlowTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app_settings.DEEPSEEK_API_KEY = ""
        Base.metadata.create_all(bind=engine)
        tools.SessionLocal = TestingSession
        nodes.SessionLocal = TestingSession
        db = TestingSession()
        cls.s1 = Scenario(
            name="自习室", time_step_minutes=30, min_duration_minutes=30,
            max_duration_minutes=240, max_advance_days=30, allow_same_day=True,
            max_active_per_user=2,
        )
        cls.s2 = Scenario(
            name="会议室", time_step_minutes=30, min_duration_minutes=30,
            max_duration_minutes=120, max_advance_days=7, allow_same_day=False,
            max_active_per_user=1,
        )
        db.add_all([cls.s1, cls.s2])
        db.flush()
        cls.r1 = Resource(scenario_id=cls.s1.id, name="A1", code="1F-A1",
                          open_start=time(8, 0), open_end=time(22, 0))
        cls.r2 = Resource(scenario_id=cls.s1.id, name="B1", code="1F-B1",
                          open_start=time(8, 0), open_end=time(22, 0))
        cls.r3 = Resource(scenario_id=cls.s2.id, name="会议室A", code="M-A",
                          open_start=time(9, 0), open_end=time(17, 0))
        db.add_all([cls.r1, cls.r2, cls.r3])
        cls.u = User(username="u1", email="u1@test.com", password_hash="x", role="student")
        db.add(cls.u)
        db.commit()
        db.close()

    def setUp(self):
        from app.agent.graph import graph

        self.graph = graph
        db = TestingSession()
        self.uid = db.query(User).filter(User.username == "u1").first().id
        db.query(models.Reservation).delete()
        db.commit()
        db.close()
        self.config = {"configurable": {"thread_id": f"test_{id(self)}", "user_id": self.uid}}

    def _chat(self, text):
        out = self.graph.invoke({"messages": [HumanMessage(content=text)]}, config=self.config)
        content = ""
        for m in reversed(out.get("messages") or []):
            if getattr(m, "type", "") == "ai":
                content = str(m.content)
                break
        return content

    def _day(self, offset=2):
        return (date.today() + timedelta(days=offset)).isoformat()

    def test_intent_rules(self):
        self.assertEqual(detect_intent("帮我预约自习室"), "book")
        self.assertEqual(detect_intent("取消预约号 3"), "cancel")
        self.assertEqual(detect_intent("查一下自习室有没有位置"), "query")
        self.assertEqual(detect_intent("有哪些场景"), "list_scenarios")
        self.assertEqual(detect_intent("查一下我的预约"), "list_my")
        self.assertEqual(detect_intent("你好呀"), "chitchat")

    def test_relative_date(self):
        today = date(2026, 10, 19)
        self.assertEqual(resolve_relative_date("今天", today), "2026-10-19")
        self.assertEqual(resolve_relative_date("明天", today), "2026-10-20")
        self.assertEqual(resolve_relative_date("后天", today), "2026-10-21")
        self.assertEqual(resolve_relative_date("周三", today), "2026-10-21")
        self.assertEqual(resolve_relative_date("2026-11-01", today), "2026-11-01")

    def test_chitchat_flow(self):
        reply = self._chat("你好")
        self.assertIn("预约助手", reply)

    def test_book_missing_flow(self):
        day = self._day()
        reply = self._chat(f"帮我预约 {day} 下午自习室")
        self.assertIn("资源", reply)
        self.assertIn("开始时间", reply)
        reply = self._chat(f"{day} 自习室 A1 预约")
        self.assertIn("开始时间", reply)
        reply = self._chat(f"就自习室 A1，{day} 15:00-16:00")
        self.assertIn("预约成功", reply)

    def test_conflict_flow(self):
        day = self._day()
        self._chat(f"帮我约自习室 A1，{day} 15:00-16:00")
        reply = self._chat(f"再帮我约自习室 A1 {day} 15:00-15:30")
        self.assertIn("已被预约", reply)

    def test_query_flow(self):
        day = self._day()
        reply = self._chat(f"查一下自习室 {day} 下午的时段")
        self.assertIn("可约", reply)
        self.assertIn("1F-A1", reply)

    def test_list_my_flow(self):
        day = self._day(3)
        self._chat(f"帮我约自习室 A1，{day} 10:00-11:00")
        reply = self._chat("查一下我的预约")
        self.assertIn("预约号", reply)

    def test_cancel_flow(self):
        day = self._day(3)
        self._chat(f"帮我约自习室 B1，{day} 10:00-11:00")
        reply = self._chat("取消预约号 1")
        self.assertIn("成功取消", reply)
        reply = self._chat("取消预约号 1")
        self.assertIn("已取消", reply)

    def test_list_scenarios_flow(self):
        reply = self._chat("有哪些场景")
        self.assertIn("自习室", reply)
        self.assertIn("会议室", reply)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)