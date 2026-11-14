"""AI 辅助批量生成资源：将自然语言描述解析为结构化规格并批量创建资源。"""
import re
from datetime import time
from typing import List

from pydantic import BaseModel, Field, model_validator
from sqlalchemy.orm import Session

from app.agent.llm import llm
from app.config import settings
from app.models.resource import Resource
from app.models.scenario import Scenario
from app.utils.fallback_metrics import record_fallback

_RE_HHMM = re.compile(r"^(\d{1,2})[:：](\d{1,2})$")
_RE_HH_CN = re.compile(r"^(\d{1,2})\s*[点时時]$")
_RE_TIME_RANGE = re.compile(r"(\d{1,2})(?::(\d{2}))?\s*[-~至到]\s*(\d{1,2})(?::(\d{2}))?")


def _to_hhmm(value) -> str | None:
    """把 LLM 返回的时间值归一化为 HH:MM，无法识别时返回 None。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    m = _RE_HHMM.match(text)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
        return None
    m = _RE_HH_CN.match(text)
    if m:
        hour = int(m.group(1))
        if 0 <= hour <= 23:
            return f"{hour:02d}:00"
    return None


class ResourceSpec(BaseModel):
    """从描述解析出的批量资源生成规格。"""

    count: int = Field(..., ge=1, le=100, description="资源数量")
    name_prefix: str = Field(..., description="资源名称前缀，如「羽毛球场地」")
    code_prefix: str = Field(..., description="资源编号前缀，大写英文，如「BADMINTON」")
    open_start: str = Field("08:00", description="开放起始 HH:MM")
    open_end: str = Field("22:00", description="开放结束 HH:MM")
    attributes: dict = Field(default_factory=dict, description="每个资源附加的属性")

    @model_validator(mode="before")
    @classmethod
    def _normalize_fields(cls, data):
        if not isinstance(data, dict):
            return data
        data = dict(data)

        count = data.get("count")
        if isinstance(count, str):
            m = re.search(r"\d+", count)
            count = int(m.group(0)) if m else 1
        if isinstance(count, (int, float)) and not isinstance(count, bool):
            data["count"] = max(1, min(100, int(count)))

        start = _to_hhmm(data.get("open_start"))
        end = _to_hhmm(data.get("open_end"))
        if start is None:
            m = _RE_TIME_RANGE.search(str(data.get("open_start") or ""))
            if m:
                start = _to_hhmm(f"{m.group(1)}:{m.group(2) or '00'}")
                if end is None:
                    end = _to_hhmm(f"{m.group(3)}:{m.group(4) or '00'}")
        data["open_start"] = start or "08:00"
        data["open_end"] = end or "22:00"

        name = str(data.get("name_prefix") or "").strip()
        data["name_prefix"] = name or "资源"
        code = re.sub(r"[^A-Za-z0-9]", "", str(data.get("code_prefix") or "")).upper()
        data["code_prefix"] = code[:20] or "RES"
        if not isinstance(data.get("attributes"), dict):
            data["attributes"] = {}
        return data


_PARSE_PROMPT = (
    "你是预约资源生成器。从用户的自然语言描述中提取批量生成资源的规格，严格遵守：\n"
    "- count: 要生成的资源数量（如「5个」→5）\n"
    "- name_prefix: 资源名称前缀，如「羽毛球场地」「会议室」\n"
    "- code_prefix: 资源编号前缀，使用大写英文/拼音首字母，如「BADMINTON」「MEETING」\n"
    "- open_start / open_end: 开放时间 HH:MM，如「9-22点」→ 09:00 / 22:00，未提及默认 08:00 / 22:00\n"
    "- attributes: 资源附加属性字典，如 {\"type\": \"badminton\"}，无则空对象\n"
    "只从用户原话提取，禁止编造。"
)


def _parse_by_llm(description: str) -> ResourceSpec | None:
    if not settings.DEEPSEEK_API_KEY:
        return None
    try:
        chain = llm.with_structured_output(ResourceSpec)
        result = chain.invoke(_PARSE_PROMPT + "\n\n用户描述：" + description)
        return result
    except Exception as exc:
        record_fallback(
            "resource_spec", type(exc).__name__, {"description_len": len(description)}
        )
        return None


def _parse_by_regex(description: str) -> ResourceSpec:
    """无 LLM 时的降级解析：提取数量与名称前缀。"""
    m = re.search(r"(\d+)\s*个?", description)
    count = int(m.group(1)) if m else 1
    if count < 1:
        count = 1
    if count > 100:
        count = 100

    name = re.sub(r"\d+\s*个?", "", description).strip()
    name = re.sub(r"[，,。.、的生成创建添加帮我需要请]+", "", name).strip()
    if not name:
        name = "资源"
    name_prefix = name

    ascii_upper = re.sub(r"[^A-Za-z]", "", name).upper()
    code_prefix = ascii_upper[:8] if ascii_upper else "RES"

    m = re.search(r"(\d{1,2})\s*[-~至到]\s*(\d{1,2})\s*点", description)
    open_start = "08:00"
    open_end = "22:00"
    if m:
        start_hour, end_hour = int(m.group(1)), int(m.group(2))
        if 0 <= start_hour <= 23:
            open_start = f"{start_hour:02d}:00"
        if 0 <= end_hour <= 23:
            open_end = f"{end_hour:02d}:00"

    return ResourceSpec(
        count=count,
        name_prefix=name_prefix,
        code_prefix=code_prefix,
        open_start=open_start,
        open_end=open_end,
        attributes={},
    )


def parse_description(description: str) -> ResourceSpec:
    spec = _parse_by_llm(description)
    if spec is None:
        spec = _parse_by_regex(description)
    return spec


def _to_time(hhmm: str, default: time) -> time:
    try:
        parts = str(hhmm).split(":")
        return time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)
    except (TypeError, ValueError):
        record_fallback("resource_time", "invalid_value", {"value": str(hhmm)[:20]})
        return default


def generate_resources(db: Session, scenario: Scenario, description: str) -> List[Resource]:
    """根据描述在指定场景下批量创建资源，返回已创建列表。已存在的编号会跳过。"""
    spec = parse_description(description)
    open_start = _to_time(spec.open_start, time(8, 0))
    open_end = _to_time(spec.open_end, time(22, 0))
    if open_start >= open_end:
        open_end = time(22, 0)

    created: List[Resource] = []
    for i in range(1, spec.count + 1):
        code = f"{spec.code_prefix}-{i}"
        exists = (
            db.query(Resource)
            .filter(Resource.scenario_id == scenario.id, Resource.code == code)
            .first()
        )
        if exists:
            continue
        resource = Resource(
            scenario_id=scenario.id,
            name=f"{spec.name_prefix} {i}",
            code=code,
            open_start=open_start,
            open_end=open_end,
            attributes=dict(spec.attributes),
            is_active=True,
        )
        db.add(resource)
        created.append(resource)

    if created:
        db.commit()
        for r in created:
            db.refresh(r)
    return created
