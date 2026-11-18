<div align="center">

# 🗓️ Booking Agent · 智能预约平台

**用自然语言完成预约：一个可配置、可降级、可部署的 AI Agent 预约系统**

![Python](https://img.shields.io/badge/Python-3.13-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1.2-1C3C3C)
![Vue](https://img.shields.io/badge/Vue-3-4FC08D?logo=vuedotjs&logoColor=white)
![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?logo=mysql&logoColor=white)
![Redis](https://img.shields.io/badge/Redis-7-DC382D?logo=redis&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

</div>

---

## 📖 项目简介

Booking Agent 是一个**通用的可配置预约平台**，在传统「场景 → 资源 → 预约」业务之上接入了基于 **LangGraph** 的对话式智能体：

- **用户**可以直接说「帮我约明天 9:00–10:00 的自习室 A1」，智能体会完成意图识别、参数补全、二次确认与下单；
- **商家**可以自助配置预约场景与规则，并用一句「生成 5 个羽毛球场地，9–22 点开放」批量创建资源；
- **REST 接口与 Agent 共用同一套业务校验层**，AI 只负责「理解」，规则校验与数据写入始终由确定性代码完成。

项目内置自习室、会议室、羽毛球场、健身房、共享工位五类示例场景，开箱即可体验；同一套模型与规则引擎可扩展到任意「时间段 + 资源」类预约业务。

---

## ✨ 核心特性

| | 特性 | 说明 |
|---|---|---|
| 🤖 | **对话式预约** | 支持预约 / 查询空闲 / 取消 / 查看我的预约 / 列出场景 / 批量生成资源 / 闲聊 7 类意图，缺失信息自动多轮追问 |
| 🧭 | **确定性状态机编排** | LangGraph 显式定义 6 个节点与条件边，LLM 仅承担意图分类与槽位抽取，**不直接决定调用哪个工具** |
| 🛡️ | **写操作二次确认** | 预约、取消必须经用户明确确认后才落库，防止误识别造成的副作用 |
| ⚙️ | **可配置规则引擎** | 以场景为粒度配置时间步长、时长上下限、提前预约窗口、每日上限、同日预约、活跃预约数、取消截止时间等 9 项规则 |
| 🔒 | **并发安全** | 对资源行加 `SELECT … FOR UPDATE` 悲观锁，冲突检测与写入串行化，杜绝同一时段重复预约 |
| 🧯 | **LLM 容灾降级** | 并发上限 + 熔断器 + 规则/正则兜底；降级时不"猜着执行"，而是向用户发起澄清追问 |
| 🔑 | **完整认证体系** | 双 Token（access/refresh）、refresh 单次轮换、jti 黑名单、改密全端失效、账号 + IP 双维度登录限流 |
| 📊 | **可观测与评测** | 降级指标接口 + 210 条意图评测集（dev/test 划分）+ 14 个测试模块 |
| 🚀 | **一键部署** | Docker Compose 编排 Nginx + FastAPI + MySQL + Redis，含健康检查、日志轮转与时区处理 |

---

## 🏗️ 系统架构

```mermaid
flowchart LR
    U["🧑 用户 / 商家<br/>Vue 3 SPA"] -->|HTTP| N["Nginx :80<br/>静态托管 + 反向代理"]
    N -->|"/api/*"| API["FastAPI<br/>routers"]
    API --> SVC["services<br/>booking_service<br/>resource_generator"]
    API --> AG["LangGraph Agent<br/>6 节点状态机"]
    AG -->|"调用同一套校验"| SVC
    AG -->|"结构化输出"| LLM["DeepSeek<br/>LLM Guard 保护"]
    SVC --> DB[("MySQL / SQLite")]
    API --> R[("Redis<br/>令牌黑名单 · 限流计数 · 降级指标")]
```

**分层职责**

| 层 | 目录 | 职责 |
|---|---|---|
| 接口层 | `routers/` | 参数校验、鉴权依赖、统一响应格式 `{code, message, data}` |
| 业务层 | `services/` | 预约规则校验、空闲时段计算、AI 资源生成，**REST 与 Agent 共用** |
| 智能体层 | `agent/` | 状态机编排、意图/槽位抽取、工具封装、LLM 调用保护 |
| 数据层 | `models/` `database.py` | SQLAlchemy 2.x ORM，SQLite / MySQL 一行配置切换 |
| 基础设施 | `utils/` | JWT、令牌存储、登录限流、降级指标、启动安全检查 |

---

## 🧠 Agent 设计

### 工作流

```mermaid
flowchart TD
    S(["用户消息"]) --> RI["route_intent<br/>意图识别 / 确认 / 澄清分流"]
    RI -->|"闲聊 · 取消确认 · 澄清追问<br/>已生成回复"| E1(["结束"])
    RI -->|"业务意图"| ES["extract_slots<br/>槽位抽取 + 实体解析"]
    ES -->|"缺少必填槽位"| AM["ask_missing<br/>列出可选项并追问"]
    ES -->|"预约 / 取消，尚未确认"| CF["confirm<br/>展示摘要，等待确认"]
    ES -->|"查询 / 列表 / 生成资源<br/>或已确认"| CT["call_tool<br/>调用业务服务"]
    CT --> RP["respond"]
    AM --> E2(["结束，下一轮继续"])
    CF --> E3(["结束，下一轮继续"])
    RP --> E4(["结束"])
```

多轮状态（意图、已填槽位、待确认标记等）由 LangGraph `checkpointer` 按 `session_id` 保存，用户可以分多句话补全信息，例如先说「约自习室」，再补「明天下午三点」。

### 关键设计决策

<details open>
<summary><b>1. LLM 只做「理解」，不做「决策」</b></summary>

LLM 通过 `with_structured_output` 输出受 Pydantic 校验的 `IntentResult` 与 `SlotExtraction`；字段值（时间格式、预约号等）经过 validator 归一化。具体调用哪个业务函数由图的条件边决定，而不是让模型自由选择工具，行为可预测、可测试。

</details>

<details open>
<summary><b>2. 权限不依赖模型输出</b></summary>

工具执行时的 `user_id` 来自已通过 JWT 鉴权的请求上下文（`config["configurable"]`），而不是对话内容或模型输出。取消预约、生成资源等操作在服务层再次校验归属与角色，Agent 无法越权。

</details>

<details open>
<summary><b>3. 实体解析：从自然语言到数据库主键</b></summary>

抽取出的「自习室」「A1」等文本，会在 `extract_slots` 中解析为真实的 `scenario_id` / `resource_id`（支持数字 ID、名称/编号模糊匹配，以及按对话历史反查），并限定在启用状态与所属场景内。相对日期（今天 / 周三 / 10月21日）由 `resolve_relative_date` 换算为 `YYYY-MM-DD`。

</details>

<details open>
<summary><b>4. 写操作必须二次确认</b></summary>

预约与取消在槽位齐全后先进入 `confirm` 节点，展示场景、资源、日期、时段摘要，用户回复「确认」才执行。确认词判定对「取消」等否定语义做了冲突处理，避免「确认取消」被误判为放弃。

</details>

<details open>
<summary><b>5. 降级不"猜着执行"</b></summary>

LLM 不可用时，系统退回关键词规则识别意图；若此时识别出的是会产生副作用的意图（预约 / 取消 / 配置），**不会直接执行**，而是返回编号菜单让用户选择（`1 预约 / 2 查询空闲 / 3 取消 …`）。降级事件同时写入指标，供运维观察。

</details>

### LLM 调用保护（`llm_guard.py`）

所有 LLM 调用统一经过 `guarded_invoke`：

```text
请求 ──► 熔断器 ──► 并发信号量(默认 5) ──► DeepSeek（超时 15s，SDK 重试 1 次）
          │                │
          │ open: 直接拒绝   │ 排队超 10s: 直接降级
          ▼                ▼
        规则 / 正则兜底 + 记录降级指标
```

- **熔断**：连续失败 3 次打开 60 秒；冷却后进入半开状态，仅放行一个探测请求，成功才恢复
- **并发上限**：避免 LLM 慢响应占满线程池
- **可观测**：`GET /api/agent/metrics/fallback`（管理员）按环节（意图 / 槽位 / 资源解析 / 会话…）统计降级次数，5 分钟内同一环节达到阈值自动告警；指标不记录用户原话，避免隐私扩散

---

## ⚙️ 预约规则引擎

`booking_service.create_reservation` 按顺序执行以下校验，REST 接口与 Agent 复用同一函数：

| 类别 | 校验项 |
|---|---|
| 基础合法性 | 场景存在且启用 · 资源属于该场景且可用 · 开始早于结束 · 不能预约过去 |
| 时间窗口 | 是否允许当日预约 · 最少提前 N 分钟 · 最多提前 N 天 |
| 时长与粒度 | 最短 / 最长时长 · 开始时间按步长对齐 · 时长为步长整数倍 |
| 资源可用性 | 落在资源开放时段内 · 与已有预约无时间重叠 |
| 用户配额 | 同场景最大活跃预约数 · 每日累计时长上限 |

取消预约另校验：操作者身份（本人 / 管理员 / 场景所属商家）、预约状态、以及**开始前 N 分钟不可取消**。

**并发控制**：创建预约时先对目标资源行加 `FOR UPDATE` 行锁，使"冲突检测 → 写入"在同一资源上串行执行；锁等待失败时转换为 `503` 并提示稍后重试。空闲时段查询按场景步长对资源开放时间切片，扣除已有预约后合并为连续区间返回。

---

## 🔐 安全设计

| 能力 | 实现 |
|---|---|
| 双 Token | access 默认 15 分钟，refresh 默认 7 天；前端在过期前 60 秒主动续期，并发请求共享同一次刷新（single-flight） |
| refresh 轮换 | refresh 单次使用，换新后旧令牌立即作废 |
| 令牌撤销 | 登出、轮换、改密均通过 jti 黑名单失效；改密后该用户此前签发的全部令牌一并失效 |
| 登录限流 | 账号维度 5 次 / 15 分钟，IP 维度 20 次 / 15 分钟；锁定期间不再累计，防止攻击者把账号永久锁死 |
| 启动自检 | 弱 / 默认 / 过短（<32 位）的 `JWT_SECRET_KEY` 或非法算法直接**拒绝启动**；默认账号仍为弱口令时告警 |
| 角色权限 | `student` / `merchant` / `admin` 三级；商家可管理平台预置场景与自己创建的场景，且只能查看自有场景下的预约；管理员拥有全部权限 |
| 商家注册 | 开放自助注册，任何人注册后可创建并管理自己的预约场景 |
| 错误处理 | 统一异常处理，对外不暴露内部异常原文；Agent 异常返回通用提示 |
| 部署加固 | 后端容器以非 root 用户运行；数据库、Redis、后端均不对宿主机暴露端口，仅 Nginx 对外；Nginx 设置安全响应头 |

---

## 🧰 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.13 · FastAPI · SQLAlchemy 2.x · Pydantic v2 · python-jose (JWT) · passlib/bcrypt |
| AI | LangGraph · LangChain · DeepSeek（`langchain-deepseek`） |
| 前端 | Vue 3 (`<script setup>` + Composables) · Vue Router 4 · Vite · 自研样式，无 UI 框架依赖 |
| 存储 | MySQL 8（生产）/ SQLite（本地零配置）· Redis 7 |
| 部署 | Docker 多阶段构建 · Docker Compose · Nginx |
| 测试 | pytest |

---

## 📁 目录结构

```text
booking-agent/
├── backend/
│   ├── app/
│   │   ├── main.py                 # 应用入口、生命周期、轻量自迁移、默认账号与种子数据
│   │   ├── config.py               # 环境变量配置
│   │   ├── models/                 # User / Scenario / Resource / Reservation
│   │   ├── schemas/                # Pydantic 请求/响应模型
│   │   ├── routers/                # auth · users · scenarios · resources · reservations · agent
│   │   ├── services/
│   │   │   ├── booking_service.py  # 预约规则引擎（REST 与 Agent 共用）
│   │   │   └── resource_generator.py  # 自然语言 → 批量资源
│   │   ├── agent/
│   │   │   ├── graph.py            # LangGraph 状态图定义
│   │   │   ├── nodes.py            # 节点：路由 / 槽位 / 追问 / 确认 / 调用 / 回复
│   │   │   ├── classifier.py       # 意图 + 槽位抽取（LLM 优先，规则兜底）
│   │   │   ├── tools.py            # 业务工具封装
│   │   │   ├── llm_guard.py        # 并发限制 + 熔断
│   │   │   └── state.py
│   │   ├── utils/                  # security · token_store · rate_limit · fallback_metrics · startup_checks
│   │   └── seed.py                 # 示例场景与资源
│   ├── tests/                      # pytest 测试（14 个模块）
│   ├── eval_intent.py              # 意图识别评测脚本
│   ├── Dockerfile
│   └── requirements.txt
├── fronted/                        # Vue 3 前端
│   ├── src/
│   │   ├── views/{auth,user,merchant}/   # 登录注册 · 用户端 · 商家端
│   │   ├── components/             # AgentDrawer（AI 助手抽屉）等
│   │   ├── composables/            # useAgent · useAuth · ...
│   │   ├── api/request.js          # 请求封装、双 Token 自动续期
│   │   └── router/                 # 路由与角色守卫
│   ├── nginx.conf
│   └── Dockerfile
├── eval/cases.csv                  # 意图评测数据集
├── docker-compose.yml
└── .env.production.example
```

---

## 🚀 快速开始

### 方式一：Docker Compose（推荐）

```bash
# 1. 准备生产配置
cp .env.production.example .env.production

# 2. 生成 JWT 密钥，并填入 JWT_SECRET_KEY
python3 -c "import secrets; print(secrets.token_urlsafe(48))"

# 3. 按需修改 MYSQL_*、默认账号密码、DEEPSEEK_API_KEY 后启动
docker compose up -d --build
docker compose ps
```

启动后访问 `http://<服务器地址>/`。首次启动会自动建表、创建默认管理员 / 商家并写入示例数据。

验收：

```bash
curl http://127.0.0.1/health        # 返回 "data": "ok"
```

### 方式二：本地开发

**后端**（Python 3.13）

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# 编辑 .env：必须把 JWT_SECRET_KEY 换成随机密钥，否则服务会拒绝启动
#   python -c "import secrets; print(secrets.token_urlsafe(48))"
# 可选：填入 DEEPSEEK_API_KEY；留空时 Agent 自动使用规则引擎

uvicorn app.main:app --reload --port 8000
```

| 地址 | 说明 |
|---|---|
| http://localhost:8000/docs | Swagger 在线接口文档 |
| http://localhost:8000/health | 健康检查 |

**前端**（Node.js 22）

```bash
cd fronted
npm install
npm run dev          # http://localhost:5173，开发环境默认请求 http://127.0.0.1:8000
```

> 本地默认使用 SQLite，无需安装数据库；`REDIS_URL` 不可用时，令牌撤销与限流计数自动降级为进程内存储。

### 默认账号

| 角色 | 用户名 | 默认密码 | 说明 |
|---|---|---|---|
| 管理员 | `admin` | `admin123` | 仅限本地体验，生产环境请在 `.env.production` 中修改 |
| 商家 | `merchant` | `merchant123` | 同上 |

---

## 🔧 配置说明

<details>
<summary><b>核心环境变量（点击展开）</b></summary>

| 变量 | 默认值 | 说明 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./study_room.db` | MySQL 示例：`mysql+pymysql://user:pwd@mysql:3306/booking?charset=utf8mb4` |
| `JWT_SECRET_KEY` | — | **必填**，≥32 位随机串，示例值会被拒绝 |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `15` | access 有效期（分钟） |
| `JWT_REFRESH_TOKEN_EXPIRE_DAYS` | `7` | refresh 有效期（天） |
| `REDIS_URL` | 空 | 为空或不可用时降级为进程内存储 |
| `LOGIN_MAX_FAILURES` / `LOGIN_LOCK_MINUTES` | `5` / `15` | 账号维度登录限流 |
| `LOGIN_IP_MAX_FAILURES` / `LOGIN_IP_LOCK_MINUTES` | `20` / `15` | IP 维度登录限流 |
| `CORS_ORIGINS` | `*` | 逗号分隔；生产环境同源部署无需跨域 |
| `DEEPSEEK_API_KEY` / `DEEPSEEK_MODEL` | 空 / `deepseek-chat` | 为空时 Agent 使用规则引擎 |
| `LLM_TIMEOUT_SECONDS` | `15` | 单次 LLM 请求超时 |
| `LLM_MAX_RETRIES` | `1` | SDK 重试次数 |
| `LLM_MAX_CONCURRENCY` | `5` | 同时请求上游的并发上限 |
| `LLM_QUEUE_WAIT_SECONDS` | `10` | 排队等待上限，超时直接降级 |
| `LLM_CIRCUIT_FAILURE_THRESHOLD` | `3` | 触发熔断的连续失败次数 |
| `LLM_CIRCUIT_COOLDOWN_SECONDS` | `60` | 熔断冷却时间 |

完整配置见 `backend/.env.example` 与 `.env.production.example`。

</details>

---

## 📡 API 概览

所有接口统一返回 `{ "code": 200, "message": "success", "data": ... }`，完整文档见 `/docs`。

| 模块 | 方法 · 路径 | 说明 | 权限 |
|---|---|---|---|
| **认证** | `POST /api/auth/register` | 注册（学生 / 商家均可自助注册） | 公开 |
| | `POST /api/auth/login` | 登录，返回 access + refresh | 公开 |
| | `POST /api/auth/refresh` | 刷新令牌（refresh 单次使用） | 公开 |
| | `POST /api/auth/logout` | 登出当前设备 | 登录 |
| **用户** | `GET` `PUT /api/users/me` | 查看 / 更新个人信息 | 登录 |
| **场景** | `GET /api/scenarios` · `GET /api/scenarios/{id}` | 场景列表 / 详情 | 公开 |
| | `GET /api/scenarios/{id}/availability` | 某日各资源空闲时段 | 公开 |
| | `POST` `PUT` `DELETE /api/scenarios[/{id}]` | 创建 / 更新规则 / 删除场景 | 商家 · 管理员 |
| **资源** | `GET /api/scenarios/{id}/resources` | 资源列表 | 公开 |
| | `POST` `PUT` `DELETE …/resources[/{rid}]` | 资源增删改 | 商家 · 管理员 |
| | `POST /api/scenarios/{id}/resources/generate` | 自然语言批量生成资源 | 商家 · 管理员 |
| **预约** | `POST /api/reservations` | 创建预约 | 登录 |
| | `GET /api/reservations` · `GET /api/reservations/{id}` | 我的预约 / 详情 | 登录 |
| | `PUT /api/reservations/{id}/cancel` | 取消预约 | 本人 · 商家 · 管理员 |
| | `GET /api/reservations/admin` | 全部预约（商家仅限自有场景） | 商家 · 管理员 |
| **Agent** | `POST /api/agent/chat` | 智能体对话（SSE，按 `session_id` 多轮记忆） | 登录 |
| | `GET /api/agent/metrics/fallback` | LLM 降级指标 | 管理员 |

---

## 🧪 测试与评测

### 单元 / 集成测试

```bash
cd backend
pytest
```

测试覆盖：认证与权限矩阵、令牌轮换与撤销、登录限流、启动安全校验、Agent 对话流程与二次确认、LLM 输出契约、LLM 降级与澄清追问、熔断器、降级指标、SSE 异常脱敏等。

### 意图识别评测

`eval/cases.csv` 共 **210 条**样本，覆盖 7 类意图（各 30 条），并按 `dev` / `test`（147 / 63）固定划分：调参只看 dev，最终对外只报 test，避免过拟合。样本按难度类型标注，包括口语化、含干扰词（如句中出现「场景」「预约」但并非对应意图）、错别字、省略句与多轮补充。

```bash
cd backend
python eval_intent.py --split test             # LLM 引擎，仅测试集
python eval_intent.py --split all              # dev / test 分别报告
python eval_intent.py --engine rule            # 纯规则基线，用于对比
python eval_intent.py --show-error 0           # 打印全部错例
```

脚本输出整体准确率、每类 Precision / Recall / F1 以及错例清单；多轮样本复用线上同一套 `apply_prev_intent` 逻辑，保证评测与线上行为一致。

---

## 🚢 部署说明

```text
浏览器 ─► Nginx :80 ─┬─ /      → 前端静态资源（history 路由回退 index.html）
                     └─ /api/* → backend:8000（关闭响应缓冲，兼容 SSE）
backend ─► mysql:3306 + redis:6379（仅容器内网可达）
```

- **服务器建议**：2C4G 起；2C2G 构建镜像前请先配置 swap；安全组只放行 22 / 80 / 443
- **时区**：容器统一为 `Asia/Shanghai`，可预约时段按本地时间判断，不能使用默认 UTC
- **HTTPS**：域名解析后可通过 certbot 签发证书并为 Nginx 补充 443 配置，或在前端容器前加 Caddy 自动签发；大陆节点使用 80/443 绑定域名需先完成 ICP 备案
- **上线后**：立即登录并修改默认管理员与商家密码

---

## ⚠️ 设计取舍与已知限制

| 现状 | 原因 | 扩展方向 |
|---|---|---|
| 后端固定**单 worker** | Agent 多轮状态使用 `InMemorySaver`，Redis 不可用时的令牌撤销降级存储也在进程内 | 将 LangGraph checkpointer 与令牌存储统一切到 Redis 后即可水平扩展 |
| 行级锁在 **SQLite 下不生效** | SQLite 不支持 `FOR UPDATE`；并发安全保证以 MySQL (InnoDB) 为准 | 本地开发用 SQLite，压测与生产使用 MySQL |
| 无 Alembic，使用**轻量自迁移** | 项目早期以幂等补列方式（`_ensure_schema_columns`）演进表结构 | 表结构稳定后引入 Alembic 做版本化迁移 |
| Agent 回复以**单条 SSE 事件**返回 | 当前图以 `ainvoke` 执行完毕后一次性输出最终回复 | 改用 `astream` 即可输出逐 token 流式 |

---

## 📄 License

本项目为个人学习与作品展示用途。
