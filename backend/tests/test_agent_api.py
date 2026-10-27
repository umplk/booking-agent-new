import asyncio
import sys
import unittest
from datetime import date, time, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

try:
    _probe = asyncio.new_event_loop()
    _probe.close()
    _ASYNC_AVAILABLE = True
except OSError:
    _ASYNC_AVAILABLE = False

from app import models  # noqa: F401
from app.config import settings as app_settings
from app.database import Base
from app.models.resource import Resource
from app.models.scenario import Scenario
from app.models.user import User
from app.routers.agent import ChatRequest, chat
import app.agent.nodes as nodes
import app.agent.tools as tools

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class AgentApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app_settings.DEEPSEEK_API_KEY = ""
        Base.metadata.create_all(bind=engine)
        tools.SessionLocal = TestingSession
        nodes.SessionLocal = TestingSession
        db = TestingSession()
        s = Scenario(
            name="自习室", time_step_minutes=30, min_duration_minutes=30,
            max_duration_minutes=240, max_advance_days=30, allow_same_day=True,
            max_active_per_user=2,
        )
        db.add(s)
        db.flush()
        db.add(Resource(scenario_id=s.id, name="A1", code="1F-A1",
                        open_start=time(8, 0), open_end=time(22, 0)))
        db.add(User(username="u1", email="u1@test.com", password_hash="x", role="student"))
        db.commit()
        cls.user = db.query(User).filter(User.username == "u1").first()
        db.close()

    @classmethod
    def tearDownClass(cls):
        engine.dispose()

    def setUp(self):
        db = TestingSession()
        db.query(models.Reservation).delete()
        db.commit()
        db.close()

    @staticmethod
    async def _call(message, session_id=None):
        req = ChatRequest(message=message, session_id=session_id)
        resp = await chat(req, current_user=AgentApiTest.user)
        chunks = []
        async for piece in resp.body_iterator:
            chunks.append(piece)
        return "".join(chunks)

    def _chat(self, message, session_id=None):
        return asyncio.run(self._call(message, session_id))

    @unittest.skipUnless(_ASYNC_AVAILABLE, "当前环境无法创建 asyncio 事件循环（沙箱禁网），跳过端到端异步测试")
    def test_chat_sse_chitchat(self):
        text = self._chat("你好")
        self.assertIn("data:", text)
        self.assertIn("done", text)
        self.assertIn("预约助手", text)

    @unittest.skipUnless(_ASYNC_AVAILABLE, "当前环境无法创建 asyncio 事件循环（沙箱禁网），跳过端到端异步测试")
    def test_chat_session_book_flow(self):
        day = (date.today() + timedelta(days=2)).isoformat()
        text = self._chat(f"帮我预约 {day} 下午自习室", session_id="s1")
        self.assertIn("资源", text)
        self.assertIn("开始时间", text)
        text = self._chat(f"自习室 A1，{day} 15:00-16:00", session_id="s1")
        self.assertIn("确认", text)
        text = self._chat("确认", session_id="s1")
        self.assertIn("预约成功", text)
        text = self._chat("我的预约", session_id="s1")
        self.assertIn("预约号", text)


if __name__ == "__main__":
    suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)