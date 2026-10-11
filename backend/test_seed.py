from app.database import SessionLocal
from app.models import Room, Seat, User
from app.seed import init_seed_data

db = SessionLocal()
init_seed_data(db)
rooms = db.query(Room).all()
print("Room count:", len(rooms))
for r in rooms:
    seats = db.query(Seat).filter(Seat.room_id == r.id).all()
    s0 = seats[0]
    print(f"  {r.name}: {len(seats)} seats, first={s0.seat_number} win={s0.window} power={s0.power} quiet={s0.quiet} group={s0.is_group} corner={s0.corner} avail={s0.is_available}")
db.close()
print("DONE")
