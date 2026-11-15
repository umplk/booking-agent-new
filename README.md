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

---

## 生产部署（Docker Compose）

生产环境统一用单机 Docker Compose 部署：nginx 托管前端静态文件并把 `/api` 反向代理到后端，MySQL 与 Redis 由容器提供，后端与前端都不直接对公网暴露端口。

```
浏览器 → nginx :80
           ├── /            → 前端构建产物
           └── /api/...     → backend:8000（uvicorn 单 worker）
backend → mysql:3306 + redis:6379
```

### 1. 服务器准备

- 配置 2C4G 起；2C2G 必须先加 2G swap，否则镜像构建容易 OOM
- Ubuntu 22.04 / 24.04 LTS，磁盘 40G 起
- 安全组只放行 22 / 80 / 443，不要暴露 3306、6379、8000

### 2. 安装 Docker

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && newgrp docker
docker compose version
```

### 3. 准备生产配置

```bash
cp .env.production.example .env.production
python3 -c "import secrets; print(secrets.token_urlsafe(48))"
```

把生成的随机串填进 `JWT_SECRET_KEY`（保留示例值会直接拒绝启动），同时修改 `MYSQL_*`、默认账号密码和 `DEEPSEEK_API_KEY`。`DATABASE_URL` 的主机名必须是 compose 服务名 `mysql`，密码含特殊字符时要做 URL 编码。

### 4. 启动

```bash
docker compose up -d --build
docker compose ps
docker compose logs -f backend
```

首次启动会自动建表、创建默认管理员与商家、写入种子数据。

### 5. 验收

```bash
curl http://127.0.0.1/health
curl -I http://127.0.0.1/user/bookings
```

- `/health` 返回 `"data": "ok"`
- 子路由返回 200（history 路由已由 nginx 回退到 `index.html`，刷新不会 404）
- 浏览器登录后与智能体连续对话一次，回复应逐字流式出现，而不是等待很久一次性出现

上线后立即用默认账号登录并修改管理员、商家密码。

### 6. 域名与 HTTPS

域名 A 记录指向服务器公网 IP 后签发证书：

```bash
sudo apt install -y certbot
sudo certbot certonly --standalone -d 你的域名
```

再把证书挂载给 nginx 容器并补 443 server 块，或在前端容器前加一层 Caddy 自动签发。大陆节点绑定域名走 80/443 需要先完成 ICP 备案。

### 部署注意事项

- 后端固定单 worker：多轮对话状态和令牌撤销的降级存储都在进程内存里，多 worker 会串会话；要扩容需先把这两处切到 Redis。
- nginx 关闭了 `/api` 的响应缓冲，否则 AI 流式回复会被积压到结束后一次性输出。
- 容器时区固定为 `Asia/Shanghai`，可预约时段判断依赖本地时间，不能留在默认 UTC。
- nginx 已开启 gzip、静态资源长缓存与日志大小轮转，避免磁盘被日志写满。
- 生产环境不要把 8000、3306、6379 映射到宿主机。
