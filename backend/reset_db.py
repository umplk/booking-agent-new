from app.database import Base, engine, SessionLocal
from app import models  # noqa: F401
from app.models.user import User
from app.seed import init_seed_data
from app.utils.security import get_password_hash


def reset():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        admin = User(
            username="admin",
            email="admin@example.com",
            password_hash=get_password_hash("admin123"),
            name="系统管理员",
            role="admin",
        )
        db.add(admin)
        init_seed_data(db)
        db.commit()
    finally:
        db.close()


if __name__ == "__main__":
    reset()
    print("数据库已重置")