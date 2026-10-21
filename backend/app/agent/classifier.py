import re
from datetime import date, datetime, timedelta
from typing import Optional

from pydantic import BaseModel

from app.agent.llm import llm
from app.config import settings

_CANCEL = ("取消", "退掉", "不去了", "cancel")
_BOOK = ("约", "订", "book", "create")
_LIST_SCENARIOS = ("有什么", "有哪些", "列表", "list", "场景")
_LIST_MY = ("我的预约", "预约记录", "我的订", "订了", "都约了", "预约了哪些")
_QUERY = ("查", "有没有", "还有", "位置", "时段", "空位", "空闲", "能约吗", "available", "剩")
_CHITCHAT_GREET = ("你好", "hi", "hello", "在吗", "哈喽", "您好")
_CHITCHAT_THANK = ("谢谢", "感谢", "thx", "多谢", "3q")
_CHITCHAT_BYE = ("再见", "拜拜", "bye", "回见")

_WEEKDAY = {"一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6}

_RE_DATE = re.compile(
    r"今天|明天|后天|大后天|昨天|"
    r"\d{4}[-/.年]\d{1,2}[-/.月]\d{1,2}日?|"
    r"\d{1,2}月\d{1,2}日?|"
    r"周[一二三四五六日天]|星期[一二三四五六日天]|礼拜[一二三四五六日天]"
)
_RE_TIME_RANGE = re.compile(r"(\d{1,2})[:：](\d{2})\s*[-~至到]\s*(\d{1,2})[:：](\d{2})")
_RE_SINGLE_TIME = re.compile(r"(\d{1,2})[:：](\d{2})")
_RE_RESERVATION_ID = re.compile(r"预约号\s*[#号]?\s*(\d+)")
_RE_NUMBER = re.compile(r"\b(\d+)\b")


def detect_intent(text: str) -> str:
    t = text.strip().lower()
    if any(k in t for k in _CANCEL):
        return "cancel"
    if any(k in t for k in _LIST_MY):
        return "list_my"
    if any(k in t for k in _LIST_SCENARIOS):
        return "list_scenarios"
    if any(k in t for k in _QUERY):
        return "query"
    if any(k in t for k in _BOOK):
        return "book"
    return "chitchat"


def resolve_relative_date(expr: str, today: Optional[date] = None) -> Optional[str]:
    if not expr:
        return None
    today = today or date.today()
    expr = expr.strip()
    if expr in ("今天", "今日"):
        return today.isoformat()
    if expr in ("明天", "明日"):
        return (today + timedelta(days=1)).isoformat()
    if expr in ("后天", "后日"):
        return (today + timedelta(days=2)).isoformat()
    if expr == "大后天":
        return (today + timedelta(days=3)).isoformat()
    if expr == "昨天":
        return (today - timedelta(days=1)).isoformat()
    if expr[0] in ("周", "星期", "礼拜") and len(expr) >= 2:
        target = _WEEKDAY.get(expr[-1])
        if target is not None:
            delta = (target - today.weekday()) % 7
            return (today + timedelta(days=delta)).isoformat()
    m = re.match(r"^(\d{4})[-/.年](\d{1,2})[-/.月](\d{1,2})日?$", expr)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return None
    m = re.match(r"^(\d{1,2})月(\d{1,2})日?$", expr)
    if m:
        try:
            d = date(today.year, int(m.group(1)), int(m.group(2)))
        except ValueError:
            return None
        if d < today:
            try:
                d = date(today.year + 1, int(m.group(1)), int(m.group(2)))
            except ValueError:
                return None
        return d.isoformat()
    return None


class SlotExtraction(BaseModel):
    date: Optional[str] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    scenario_query: Optional[str] = None
    resource_query: Optional[str] = None
    reservation_id: Optional[int] = None


_EXTRACT_PROMPT = (
    "你是预约系统的参数提取器。从用户最近的发言中提取以下字段，严格遵守：\n"
    "- date: 期望的日期，可以是 '明天'、'周三'、'2026-10-21' 等，没提到就是 null\n"
    "- start_time / end_time: 时间段，格式 HH:MM，例如 '09:00'，没提到就是 null\n"
    "- scenario_query: 用户提到的预约场景名称关键词，例如 '自习室'、'会议室'，没提到就是 null\n"
    "- resource_query: 用户提到的具体资源名称，例如 'A1'、'会议室A'，没提到就是 null\n"
    "- reservation_id: 用户提到的预约号数字，仅当取消预约时填写，否则 null\n"
    "只从用户原话中提取，禁止猜测或编造。多轮对话中如果用户补充了新信息，提取最新信息并可以沿用此前已确认的信息。"
)


def extract_by_llm(history_text: str) -> dict:
    if not settings.DEEPSEEK_API_KEY:
        return {}
    try:
        chain = llm.with_structured_output(SlotExtraction)
        result = chain.invoke(_EXTRACT_PROMPT + "\n\n对话内容：\n" + history_text)
        data = result.model_dump()
        for key in ("start_time", "end_time"):
            if data.get(key):
                m = re.match(r"^(\d{1,2})[:：](\d{2})$", str(data[key]).strip())
                if m:
                    data[key] = f"{int(m.group(1)):02d}:{m.group(2)}"
        return data
    except Exception:
        return {}


def extract_by_regex(text: str) -> dict:
    data: dict = {}
    m = _RE_DATE.search(text)
    if m:
        data["date"] = m.group(0)
    m = _RE_TIME_RANGE.search(text)
    if m:
        data["start_time"] = f"{int(m.group(1)):02d}:{m.group(2)}"
        data["end_time"] = f"{int(m.group(3)):02d}:{m.group(4)}"
    else:
        m = _RE_SINGLE_TIME.search(text)
        if m:
            data["start_time"] = f"{int(m.group(1)):02d}:{m.group(2)}"
    m = _RE_RESERVATION_ID.search(text)
    if m:
        data["reservation_id"] = int(m.group(1))
    return data


def extract_request(intent: str, history_text: str) -> dict:
    data = extract_by_llm(history_text)
    regex_fallback = extract_by_regex(history_text)
    for key in ("date", "start_time", "end_time", "scenario_query", "resource_query", "reservation_id"):
        if not data.get(key) or str(data[key]).strip() == "":
            data[key] = regex_fallback.get(key)
        if key in ("date", "start_time", "end_time") and data.get(key):
            data[key] = str(data[key]).strip()
    if data.get("date") and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(data["date"])):
        resolved = resolve_relative_date(str(data["date"]))
        if resolved:
            data["date"] = resolved
    return data


def chitchat_reply(text: str) -> str:
    t = text.strip().lower()
    if any(k in t for k in _CHITCHAT_GREET):
        return "你好！我是预约助手，可以帮你预约自习室/会议室、查询可约时段、查看或取消预约。"
    if any(k in t for k in _CHITCHAT_THANK):
        return "不客气，还有其他需要帮忙的吗？"
    if any(k in t for k in _CHITCHAT_BYE):
        return "再见，有需要随时找我。"
    return "我是预约助手，支持：预约（book）、查询时段（query）、查看我的预约（list_my）、取消预约（cancel）。你可以直接告诉我需求，例如「明天自习室能约吗」或「帮我约明天 09:00-10:00 自习室 A1」。"