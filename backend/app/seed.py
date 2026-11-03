from datetime import time

from sqlalchemy.orm import Session

from app.config import settings
from app.models.resource import Resource
from app.models.scenario import Scenario
from app.models.user import User

FLOORS = [
    {
        "name": "1F 文学阅览区",
        "location": "A栋 1楼",
        "all_power": False,
    },
    {
        "name": "2F 理工科阅览区",
        "location": "A栋 2楼",
        "all_power": True,
    },
    {
        "name": "3F 外文阅览区",
        "location": "A栋 3楼",
        "all_power": False,
    },
    {
        "name": "4F 人文社会学科图书阅览区",
        "location": "A栋 4楼",
        "all_power": False,
    },
    {
        "name": "5F 电子文献阅览区",
        "location": "A栋 5楼",
        "all_power": True,
    },
]

ROWS = ["A", "B", "C", "D", "E"]
COLS = 10

STUDY_ROOM_NAME = "自习室座位预约"

DEFAULT_RULES = {
    "time_step_minutes": 30,
    "min_duration_minutes": 30,
    "max_duration_minutes": 240,
    "max_advance_days": 30,
    "min_advance_minutes": 0,
    "max_minutes_per_day": None,
    "allow_same_day": True,
    "max_active_per_user": 5,
    "cancel_before_minutes": None,
}

CATALOG_SCENARIOS = [
    {
        "name": "会议室预约",
        "category": "meeting_room",
        "icon": "💼",
        "location": "B栋 3楼",
        "tags": "投影仪,白板,视频会议",
        "is_featured": True,
        "sort_order": 20,
        "description": "3 间不同容量的会议室，配备投影、白板与视频会议设备",
        "booking_notice": "请提前 10 分钟到场，会后请恢复桌椅并关闭设备。",
        "rules": {**DEFAULT_RULES, "max_duration_minutes": 180, "max_active_per_user": 2,
                  "max_minutes_per_day": 240, "cancel_before_minutes": 60},
        "resources": [
            {"name": "A301 小型会议室", "code": "MR-A301",
             "attributes": {"capacity": 8, "projector": True, "whiteboard": True, "video": True}},
            {"name": "A302 中型会议室", "code": "MR-A302",
             "attributes": {"capacity": 12, "projector": True, "whiteboard": True, "video": True}},
            {"name": "A303 大型会议室", "code": "MR-A303",
             "attributes": {"capacity": 20, "projector": True, "whiteboard": True, "video": False}},
        ],
    },
    {
        "name": "羽毛球场地预约",
        "category": "sports",
        "icon": "🏸",
        "location": "体育馆 1楼",
        "tags": "室内,灯光,木地板",
        "is_featured": True,
        "sort_order": 30,
        "description": "4 片标准室内羽毛球场地，晚间灯光开放",
        "booking_notice": "请自备球拍并穿运动鞋入场，结束后请带走个人物品。",
        "rules": {**DEFAULT_RULES, "time_step_minutes": 60, "min_duration_minutes": 60,
                  "max_duration_minutes": 120, "max_advance_days": 7,
                  "max_active_per_user": 2, "max_minutes_per_day": 180,
                  "cancel_before_minutes": 120},
        "resources": [
            {"name": f"{i} 号羽毛球场", "code": f"BD-{i:02d}",
             "attributes": {"court": i, "indoor": True, "floor": "木地板"},
             "open": ("09:00", "22:00")}
            for i in range(1, 5)
        ],
    },
    {
        "name": "健身房器械预约",
        "category": "fitness",
        "icon": "💪",
        "location": "体育馆 2楼",
        "tags": "器械,空调,免费",
        "is_featured": False,
        "sort_order": 40,
        "description": "跑步机、椭圆机与力量器械分时段预约，避免高峰拥挤",
        "booking_notice": "请先热身并使用毛巾，器械使用后请擦拭归位。",
        "rules": {**DEFAULT_RULES, "max_duration_minutes": 90, "max_advance_days": 3,
                  "max_active_per_user": 1, "max_minutes_per_day": 90,
                  "cancel_before_minutes": 30},
        "resources": [
            {"name": f"跑步机 T{i}", "code": f"GY-T{i}", "attributes": {"type": "cardio", "equipment": "treadmill"},
             "open": ("07:00", "23:00")} for i in range(1, 5)
        ] + [
            {"name": f"椭圆机 E{i}", "code": f"GY-E{i}", "attributes": {"type": "cardio", "equipment": "elliptical"},
             "open": ("07:00", "23:00")} for i in range(1, 3)
        ] + [
            {"name": f"力量器械 S{i}", "code": f"GY-S{i}", "attributes": {"type": "strength", "equipment": "machine"},
             "open": ("07:00", "23:00")} for i in range(1, 3)
        ],
    },
    {
        "name": "共享工位预约",
        "category": "workspace",
        "icon": "💻",
        "location": "C栋 2楼",
        "tags": "工位,独立空间,高速网络",
        "is_featured": False,
        "sort_order": 50,
        "description": "开放式与安静区共享工位，按小时预约",
        "booking_notice": "离开超过 30 分钟请办理暂离，贵重物品请随身携带。",
        "rules": {**DEFAULT_RULES, "time_step_minutes": 60, "min_duration_minutes": 60,
                  "max_duration_minutes": 480, "max_advance_days": 14,
                  "max_active_per_user": 1, "max_minutes_per_day": 480,
                  "cancel_before_minutes": 60},
        "resources": [
            {"name": f"工位 W{i:02d}", "code": f"WS-{i:02d}",
             "attributes": {"zone": "安静区" if i <= 5 else "开放区", "monitor": i % 2 == 0,
                            "power": True, "window": i in (1, 5, 6, 10)},
             "open": ("08:00", "22:00")} for i in range(1, 11)
        ],
    },
]


def _parse_time(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def _seed_study_room(db: Session, admin_id: int | None) -> None:
    study_scenario = db.query(Scenario).filter(Scenario.name == STUDY_ROOM_NAME).first()
    if study_scenario:
        if study_scenario.location is None:
            study_scenario.location = "A栋图书馆"
        if study_scenario.tags is None:
            study_scenario.tags = "安静,插座,靠窗"
        if not study_scenario.sort_order:
            study_scenario.sort_order = 10
            study_scenario.is_featured = True
            study_scenario.icon = "📚"
        study_scenario.category = study_scenario.category or "study_room"
        if not study_scenario.booking_notice:
            study_scenario.booking_notice = "请保持安静，离座超过 30 分钟请办理暂离。"
        return

    study_scenario = Scenario(
        name=STUDY_ROOM_NAME,
        description="校园图书馆自习室座位预约，示例场景",
        category="study_room",
        icon="📚",
        location="A栋图书馆",
        tags="安静,插座,靠窗",
        is_featured=True,
        sort_order=10,
        booking_notice="请保持安静，离座超过 30 分钟请办理暂离。",
        time_step_minutes=30,
        min_duration_minutes=30,
        max_duration_minutes=240,
        max_advance_days=30,
        min_advance_minutes=30,
        max_minutes_per_day=480,
        allow_same_day=True,
        max_active_per_user=3,
        cancel_before_minutes=30,
        is_active=True,
        owner_id=admin_id,
    )
    db.add(study_scenario)
    db.flush()

    for floor in FLOORS:
        floor_flag = floor["name"].split()[0]
        for ri, r in enumerate(ROWS):
            for c in range(1, COLS + 1):
                seat_number = f"{r}{c}"
                db.add(
                    Resource(
                        scenario_id=study_scenario.id,
                        name=f"{floor['name']} {seat_number} 座位",
                        code=f"{floor_flag}-{seat_number}",
                        open_start=time(8, 0),
                        open_end=time(22, 0),
                        attributes={
                            "location": floor["location"],
                            "row": r,
                            "col": c,
                            "window": ri == 0,
                            "power": floor["all_power"] or c % 2 == 0,
                            "quiet": ri <= 1,
                            "group": ri == len(ROWS) - 1,
                            "corner": c == 1 or c == COLS,
                        },
                        is_active=True,
                    )
                )


def _seed_catalog_scenario(db: Session, config: dict, admin_id: int | None) -> None:
    scenario = Scenario(
        name=config["name"],
        description=config["description"],
        category=config["category"],
        icon=config["icon"],
        location=config["location"],
        tags=config["tags"],
        is_featured=config["is_featured"],
        sort_order=config["sort_order"],
        booking_notice=config["booking_notice"],
        is_active=True,
        owner_id=admin_id,
        **config["rules"],
    )
    db.add(scenario)
    db.flush()

    for resource in config["resources"]:
        open_start, open_end = resource.get("open", ("08:00", "22:00"))
        db.add(
            Resource(
                scenario_id=scenario.id,
                name=resource["name"],
                code=resource["code"],
                open_start=_parse_time(open_start),
                open_end=_parse_time(open_end),
                attributes=resource.get("attributes", {}),
                is_active=True,
            )
        )


def init_seed_data(db: Session) -> None:
    admin = db.query(User).filter(User.username == settings.DEFAULT_ADMIN_USERNAME).first()
    admin_id = admin.id if admin else None

    _seed_study_room(db, admin_id)

    for config in CATALOG_SCENARIOS:
        exists = db.query(Scenario).filter(Scenario.name == config["name"]).first()
        if exists:
            continue
        _seed_catalog_scenario(db, config, admin_id)

    db.commit()