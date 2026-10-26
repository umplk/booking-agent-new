import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.database import Base, engine, SessionLocal
from app.models import User, Scenario, Resource, Reservation  # noqa: F401  确保模型被注册
from app.utils.security import get_password_hash
from app.routers import auth, users, scenarios, resources, reservations, agent
from app.seed import init_seed_data

logger = logging.getLogger("app")


def _ensure_schema_columns() -> None:
    """对已存在的 scenarios 表幂等补齐新增列（无 alembic 迁移系统的轻量自迁移）。"""
    insp = inspect(engine)
    if not insp.has_table("scenarios"):
        return
    existing = {c["name"] for c in insp.get_columns("scenarios")}
    additions = [
        ("min_advance_minutes", "INTEGER NOT NULL DEFAULT 0"),
        ("max_minutes_per_day", "INTEGER"),
        ("owner_id", "INTEGER"),
    ]
    with engine.begin() as conn:
        for name, ddl in additions:
            if name not in existing:
                conn.execute(text(f"ALTER TABLE scenarios ADD COLUMN {name} {ddl}"))


def _relax_user_role_constraint() -> None:
    """将 users.role 列放宽为 VARCHAR(20)，移除旧 Enum 带来的 CHECK 约束，以支持 merchant 角色。"""
    insp = inspect(engine)
    if not insp.has_table("users"):
        return

    if not settings.is_sqlite:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE users MODIFY COLUMN role VARCHAR(20) NOT NULL DEFAULT 'student'"))
        return

    ccs = insp.get_check_constraints("users")
    if not any("role" in (cc.get("sqltext") or "") for cc in ccs):
        return

    with engine.begin() as conn:
        conn.execute(text(
            "CREATE TABLE _users_new ("
            "id INTEGER NOT NULL PRIMARY KEY, "
            "username VARCHAR(50) NOT NULL, "
            "email VARCHAR(120) NOT NULL, "
            "password_hash VARCHAR(255) NOT NULL, "
            "student_id VARCHAR(50), "
            "name VARCHAR(50), "
            "role VARCHAR(20) NOT NULL DEFAULT 'student', "
            "created_at DATETIME NOT NULL, "
            "updated_at DATETIME NOT NULL)"
        ))
        conn.execute(text(
            "INSERT INTO _users_new (id, username, email, password_hash, student_id, name, role, created_at, updated_at) "
            "SELECT id, username, email, password_hash, student_id, name, role, created_at, updated_at FROM users"
        ))
        conn.execute(text("DROP TABLE users"))
        conn.execute(text("ALTER TABLE _users_new RENAME TO users"))
        conn.execute(text("CREATE UNIQUE INDEX ix_users_username ON users (username)"))
        conn.execute(text("CREATE UNIQUE INDEX ix_users_email ON users (email)"))
        conn.execute(text("CREATE INDEX ix_users_student_id ON users (student_id)"))
        conn.execute(text("CREATE INDEX ix_users_role ON users (role)"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _ensure_schema_columns()
    _relax_user_role_constraint()
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
        merchant = db.query(User).filter(User.username == settings.DEFAULT_MERCHANT_USERNAME).first()
        if not merchant:
            merchant = User(
                username=settings.DEFAULT_MERCHANT_USERNAME,
                email="merchant@example.com",
                password_hash=get_password_hash(settings.DEFAULT_MERCHANT_PASSWORD),
                name="默认商家",
                role="merchant",
            )
            db.add(merchant)
            db.commit()
            logger.info("默认商家已创建: %s", settings.DEFAULT_MERCHANT_USERNAME)
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
    title="可配置预约平台",
    description="基于 FastAPI + SQLAlchemy + JWT 的通用可配置预约平台",
    version="2.0.0",
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
app.include_router(scenarios.router)
app.include_router(resources.router)
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
    return {"code": 200, "message": "success", "data": "可配置预约平台 API，请访问 /docs 查看文档"}


@app.get("/health", tags=["默认"])
def health():
    return {"code": 200, "message": "success", "data": "ok"}
