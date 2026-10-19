from datetime import time

from sqlalchemy.orm import Session

from app.models.resource import Resource
from app.models.reservation import Reservation
from app.models.scenario import Scenario

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


def init_seed_data(db: Session) -> None:
    if db.query(Scenario).first():
        return

    study_scenario = Scenario(
        name="自习室座位预约",
        description="校园图书馆自习室座位预约，示例场景",
        time_step_minutes=30,
        min_duration_minutes=30,
        max_duration_minutes=240,
        max_advance_days=30,
        allow_same_day=True,
        max_active_per_user=3,
        cancel_before_minutes=30,
        is_active=True,
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

    db.commit()