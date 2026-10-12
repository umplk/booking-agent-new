# 自习室预约系统

小组协作项目：自习室座位在线预约系统。

- `backend/`：后端（Python + FastAPI + SQLAlchemy + JWT，端口 **8000**）
- `frontend/`：前端（开发中）

> 本文档面向队友，重点说明 **如何在你自己电脑上把后端跑起来**。有问题先看"常见问题"。

---

## 一、需要准备的东西

| 软件 | 说明 |
|------|------|
| Python 3.10+ | 必装，安装时勾选 "Add to PATH" |
| MySQL | 必装，版本 5.7+ / 8.x 均可 |
| Navicat（可选） | 方便导入数据库文件，用命令行也行 |

> 只开发前端、不碰数据库的队友，最好也把后端跑起来，前端才调得通接口。

---

## 二、启动后端（完整步骤）

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

## 三、常见问题

**Q1：启动报错 `Can't connect to MySQL server on 'localhost'`**
→ MySQL 服务没开，先在"服务"里启动 MySQL，或启动 Navicat 连接一次确认能连上。

**Q2：启动报错 `Access denied for user 'root'`**
→ `.env` 里的数据库密码和你 MySQL 的 root 密码不一致，认真检查第 3 步。

**Q3：启动报错 `Unknown database 'study_room_db'`**
→ 库没建，回到"第 2 步"完成建库。

**Q4：启动报错 `pip 不是内部或外部命令`**
→ Python 没装好或没勾选 "Add to PATH"，重装 Python 并勾选。

**Q5：占用了 8000 端口**
→ 换一个端口启动（前端联调时同步改请求地址）：
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8001
```

**Q6：改了 `.env` 没生效？**
→ 重启后端，`.env` 只在启动时读取。

---

## 四、API 说明（简要）

全部接口前缀 `/api`：
- `POST /api/auth/register`、`POST /api/auth/login`：注册 / 登录
- `GET /api/rooms`、`GET /api/rooms/{id}/availability`：自习室列表 / 座位的可用情况
- `POST /api/reservations`、`GET /api/reservations`：创建 / 查看预约

详细接口列表见 `backend/README.md`，或在 `http://localhost:8000/docs` 在线查看。