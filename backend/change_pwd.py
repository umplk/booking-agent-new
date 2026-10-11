# -*- coding: utf-8 -*-
"""将 MySQL root 密码改为 123456（仅本地开发用）"""
from sqlalchemy import create_engine, text

OLD_PWD = "xin946068"
NEW_PWD = "123456"

engine = create_engine(
    f"mysql+pymysql://root:{OLD_PWD}@127.0.0.1:3306/?charset=utf8mb4",
    isolation_level="AUTOCOMMIT",
)

with engine.connect() as conn:
    rows = conn.execute(text("SELECT user, host FROM mysql.user WHERE user='root'")).fetchall()
    print("修改前 root 授权: ", rows)
    for _, host in rows:
        conn.execute(
            text(f"ALTER USER 'root'@'{host}' IDENTIFIED BY '{NEW_PWD}'")
        )
    print("ALTER USER 执行完成")

new_engine = create_engine(
    f"mysql+pymysql://root:{NEW_PWD}@127.0.0.1:3306/?charset=utf8mb4",
    isolation_level="AUTOCOMMIT",
)
with new_engine.connect() as conn:
    conn.execute(text("SELECT 1"))
    print("新密码 123456 连接验证: OK")