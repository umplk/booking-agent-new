"""AI 辅助批量生成资源：将自然语言描述解析为结构化规格并批量创建资源。"""
import re
from datetime import time
from typing import List

from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agent.llm import llm
from app.config import settings
from app.models.resource import Resource
from app.models.scenario import Scenario


class ResourceSpec(BaseModel):
    """从描述解析出的批量资源生成规格。"""

    count: int = Field(..., ge=1, le=100, description="资源数量")
    name_prefix: str = Field(..., description="资源名称前缀，如「羽毛球场地」")
    code_prefix: str = Field(..., description="资源编号前缀，大写英文，如「BADMINTON」")
    open_start: str = Field("08:00", description="开放起始 HH:MM")
    open_end: str = Field("22:00", description="开放结束 HH:MM")
    attributes: dict = Field(default_factory=dict, description="每个资源附加的属性")


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
    except Exception:
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
        open_start = f"{int(m.group(1)):02d}:00"
        open_end = f"{int(m.group(2)):02d}:00"

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


def _to_time(hhmm: str) -> time:
    parts = hhmm.split(":")
    return time(int(parts[0]), int(parts[1]) if len(parts) > 1 else 0)


def generate_resources(db: Session, scenario: Scenario, description: str) -> List[Resource]:
    """根据描述在指定场景下批量创建资源，返回已创建列表。已存在的编号会跳过。"""
    spec = parse_description(description)
    open_start = _to_time(spec.open_start)
    open_end = _to_time(spec.open_end)
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
