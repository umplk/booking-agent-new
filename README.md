# 智能预约系统

基于 **AI Agent** 的预约系统：用户通过自然语言与智能体对话即可完成场景选择、资源查询、预约 / 取消等操作；商家可自助配置预约场景与规则，AI 自动生成匹配的资源。

## 技术栈

| 层 | 技术 |
|------|------|
| 后端 | Python + FastAPI + SQLAlchemy 2.x + JWT（端口 **8000**） |
| AI Agent | LangGraph + LangChain + DeepSeek |
| 前端 | Vue 3 + Vite + vue-router（目录 `fronted/`） |
| 数据库 | SQLite（默认，零配置）/ MySQL（可选） |

## 目录结构

```
booking-agent-mine/
├── backend/                # 后端服务
│   ├── app/
│   │   ├── main.py         # FastAPI 入口 + 启动自迁移
│   │   ├── config.py       # .env 配置读取
│   │   ├── database.py     # 数据库引擎与 Session
│   │   ├── models/         # ORM 模型（User/Scenario/Resource/Reservation）
│   │   ├── schemas/        # Pydantic 请求/响应模型
│   │   ├── routers/        # API 路由（auth/users/scenarios/resources/reservations/agent）
│   │   ├── services/       # 业务逻辑（booking_service / resource_generator）
│   │   ├── agent/          # LangGraph 智能体（classifier/graph/nodes/tools/state/llm）
│   │   ├── utils/          # JWT、密码、依赖注入、统一响应
│   │   └── seed.py         # 初始化种子数据
│   ├── requirements.txt
│   ├── .env.example
│   └── tests/              # pytest 测试
├── fronted/                # Vue 3 前端
│   ├── src/
│   │   ├── views/auth/     # 登录 / 注册
│   │   ├── views/user/     # 用户端（场景/预约/我的预约/个人中心）
│   │   ├── views/merchant/ # 商家端（场景/资源/规则/预约/个人中心）
│   │   ├── components/  layouts/  composables/  api/  router/
│   │   └── main.js
│   └── vite.config.js
└── README.md
```

## 核心能力

- **AI 对话预约**：自然语言意图识别（预约 / 查询 / 取消 / 列出 / 配置 / 闲聊），多轮对话自动追问缺失信息
- **可配置场景与规则**：以场景为粒度配置开放时间、时长步长、提前预约限制、每日上限、同日是否允许、最大活跃预约数、取消提前分钟数等
- **AI 生成资源**：根据场景规则自动生成资源（含开放时段与任意扩展属性）
- **统一业务校验**：REST 接口与 Agent 走同一套 `booking_service` 校验逻辑
- **角色权限**：student / merchant / admin，前端按 `role` 字段路由分流

---

## 启动后端

### 第 1 步：配置 `.env`

进入 `backend` 目录，将 `.env.example` 复制为 `.env`：

```bash
cd backend
cp .env.example .env
```

默认使用 **SQLite**，无需安装任何数据库服务。如需切换 MySQL，修改 `DATABASE_URL`：

```env
DATABASE_URL=mysql+pymysql://root:你的密码@localhost:3306/study_room_db?charset=utf8mb4
```

> 使用 MySQL 时需先建库：
> ```sql
> CREATE DATABASE study_room_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
> ```

还需配置 DeepSeek API Key：

```env
DEEPSEEK_API_KEY=sk-你的key
DEEPSEEK_MODEL=deepseek-chat
```

### 第 2 步：安装依赖

```bash
cd backend
pip install -r requirements.txt
```

> 下载慢可加国内镜像：`pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`

### 第 3 步：启动服务

```bash
cd backend
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

首次启动会自动建表、创建默认管理员并写入种子数据；新增字段通过 `_ensure_schema_columns` 幂等自迁移补列。

### 第 4 步：验证

| 地址 | 说明 |
|------|------|
| http://localhost:8000/docs | Swagger 接口文档（可在线调试） |
| http://localhost:8000/health | 返回 `"data": "ok"` 即正常 |
| http://localhost:8000/ | 接口欢迎页 |

默认管理员账号：**admin / admin123**

---

## 启动前端

```bash
cd fronted
npm install
npm run dev
```

默认开发端口 **5173**，前端通过 `http://localhost:8000/api/...` 请求后端（CORS 已放开）。

---

## 测试

```bash
cd backend
pytest
```
