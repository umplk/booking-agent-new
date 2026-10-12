# 自习室预约系统

小组协作项目：自习室座位在线预约系统。

- `backend/`：后端（Python + FastAPI + SQLAlchemy + JWT，端口 **8000**）
- `frontend/`：前端（开发中）

---



## 启动后端（完整步骤）

### 第 1 步：拿到源码

直接用仓库拉下来，或让后端同学把 `backend` 文件夹发给你。

### 第 2 步：准备数据库

后端连接的是你 **本机** 的 MySQL，需要先建一个库。二选一：

**方式 A（推荐，导 SQL 文件）**
1. 让后端同学用 Navicat 把 `study_room_db` 导出为 `.sql` 文件发给你；
2. 你打开 Navicat 连上自己的 MySQL（localhost）；
3. 右键 → **运行 SQL 文件** → 选择 `.sql` → 执行；
4. 完成后你的 MySQL 里就有 `study_room_db` 库了（含表和数据）。

**方式 B（手动建库）**
在 Navicat 里新建一个空库，或者命令行执行：

```sql
CREATE DATABASE study_room_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

> 表不用手动建，后端首次启动会自动创建表、默认管理员和初始数据。

### 第 3 步：配置 `.env`

进入 `backend` 目录，把 `.env.example` 复制一份改名为 `.env`（如果已经有人发给你 `.env` 就直接用）。

**重点**：`.env` 里有一行数据库连接，`root` 后面的密码必须改成 **你自己 MySQL 的密码**：

```env
DATABASE_URL=mysql+pymysql://root:改成你的密码@localhost:3306/study_room_db?charset=utf8mb4
```

其他配置（JWT、CORS、默认管理员）保持默认即可，不用动。

### 第 4 步：安装依赖

```bash
cd backend
pip install -r requirements.txt
```

> 如果下载太慢，可以加国内镜像：`pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

### 第 5 步：启动服务

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

看到类似 `Application startup complete` 就代表启动成功。

### 第 6 步：验证

浏览器打开以下地址：

| 地址 | 说明 |
|------|------|
| http://localhost:8000/docs | Swagger 接口文档（可在线调试） |
| http://localhost:8000/health | 返回 `"data": "ok"` 即正常 |
| http://localhost:8000/ | 接口欢迎页 |

### 第 7 步：前端对接

后端监听 `8000` 端口，CORS 已放开（允许任意来源跨域），前端直接请求 `http://localhost:8000/api/...` 即可。

默认管理员账号：**admin / admin123**

---
---

