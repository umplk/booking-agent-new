from datetime import time
from sqlalchemy.orm import Session

from app.models.room import Room
from app.models.seat import Seat

ROWS = ["A", "B", "C", "D", "E"]
COLS = 10

FLOORS = [
    {
        "name": "1F 文学阅览区",
        "location": "A栋 1楼",
        "desc": "中外文学名著 · 散文诗歌 · 适合静心阅读",
        "occupied": ["A1", "A5", "B3", "B8", "C2", "C7", "D4", "D9", "E3", "E6"],
        "all_power": False,
    },
    {
        "name": "2F 理工科阅览区",
        "location": "A栋 2楼",
        "desc": "数理化 · 工程技术 · 计算机科学文献",
        "occupied": ["A2", "A6", "B1", "B7", "C4", "C9", "D2", "D8", "E5", "E9"],
        "all_power": True,
    },
    {
        "name": "3F 外文阅览区",
        "location": "A栋 3楼",
        "desc": "英日韩文原版书 · 进口期刊 · 语言学习专区",
        "occupied": ["A3", "A8", "B4", "B9", "C1", "C6", "D3", "D7", "E2", "E8"],
        "all_power": False,
    },
    {
        "name": "4F 人文社会学科图书阅览区",
        "location": "A栋 4楼",
        "desc": "历史哲学 · 政治经济 · 社会学法学",
        "occupied": ["A4", "A9", "B2", "B6", "C5", "C8", "D5", "D1", "E1", "E7"],
        "all_power": False,
    },
    {
        "name": "5F 电子文献阅览区",
        "location": "A栋 5楼",
        "desc": "电子数据库 · 在线检索 · 每座配备电源与网口",
        "occupied": ["A1", "A7", "B5", "C3", "C8", "D6", "E4"],
        "all_power": True,
    },
]


def init_seed_data(db: Session) -> None:
    if db.query(Room).first():
        return

    for floor in FLOORS:
        occ = set(floor["occupied"])
        room = Room(
            name=floor["name"],
            location=floor["location"],
            open_time=time(8, 0),
            close_time=time(22, 0),
            capacity=ROWS.__len__() * COLS,
            is_active=True,
        )
        db.add(room)
        db.flush()

        for ri, r in enumerate(ROWS):
            for c in range(1, COLS + 1):
                seat_number = f"{r}{c}"
                db.add(Seat(
                    room_id=room.id,
                    seat_number=seat_number,
                    is_available=seat_number not in occ,
                    window=(ri == 0),
                    power=(floor["all_power"] or c % 2 == 0),
                    quiet=(ri <= 1),
                    is_group=(ri == len(ROWS) - 1),
                    corner=(c == 1 or c == COLS),
                ))

    db.commit()
