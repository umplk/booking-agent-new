import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import Base, engine, SessionLocal
from app.models import User, Room, Seat, Reservation  # noqa: F401  确保模型被注册
from app.utils.security import get_password_hash
from app.routers import auth, users, rooms, seats, reservations, agent
from app.seed import init_seed_data

logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.username == settings.DEFAULT_ADMIN_USERNAME).first()
        if not admin:
            admin = User(
                username=settings.DEFAULT_ADMIN_USERNAME,
                email="admin@example.com",
                password_hash=get_password_hash(settings.DEFAULT_ADMIN_PASSWORD),
                name="系统管理员",
                role="admin",
            )
            db.add(admin)
            db.commit()
            logger.info("默认管理员已创建: %s", settings.DEFAULT_ADMIN_USERNAME)
    finally:
        db.close()

    db = SessionLocal()
    try:
        init_seed_data(db)
        logger.info("种子数据初始化完成")
    finally:
        db.close()
    yield


app = FastAPI(
    title="自习室预约系统",
    description="基于 FastAPI + SQLAlchemy + JWT 的自习室座位预约系统",
    version="1.0.0",
    lifespan=lifespan,
)

_origins = ["*"] if settings.CORS_ORIGINS.strip() == "*" else [
    o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(rooms.router)
app.include_router(seats.router)
app.include_router(reservations.router)
app.include_router(agent.router)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "message": exc.detail, "data": None},
    )


@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    return JSONResponse(
        status_code=409,
        content={"code": 409, "message": "数据冲突，请检查输入的唯一字段", "data": None},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.exception("未处理的异常: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"code": 500, "message": "服务器内部错误", "data": None},
    )


@app.get("/", tags=["默认"])
def root():
    return {"code": 200, "message": "success", "data": "自习室预约系统 API，请访问 /docs 查看文档"}


@app.get("/health", tags=["默认"])
def health():
    return {"code": 200, "message": "success", "data": "ok"}
