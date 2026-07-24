# LightCode 后端（阶段 0.5：本地运行时基础）

## 概述

基于 FastAPI + SQLite 的**确定性 Mock Runtime**。此阶段不接入真实模型提供商、真实文件系统、
Shell 执行、密钥存储或网络下载。所有数据由 `app/db/database.py` 中的 `seed_database()` 确定性生成，
仅用于前端演示与验证。

## 目录结构

- `app/main.py` — FastAPI 入口与 lifespan（初始化 SQLite 连接，绑定到 `app.state.db`）
- `app/db/database.py` — 建表、种子数据、连接管理
- `app/api/routes.py` — REST 路由（camelCase JSON，与前端合约一致）
- `app/api/sse.py` — SSE 事件回放（仅回放 SQLite 中已持久化的有序事件）
- `tests/` — pytest 用例（通过 `conftest.py` 用 `tmp_path` 隔离数据库）

## 启动方式

### 依赖

需要 Python >= 3.11。推荐在隔离环境中安装：

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

### 运行（开发）

从 `backend/` 目录启动（`app` 包的发现依赖此目录在 `sys.path` 上）；
**数据库路径本身不依赖当前工作目录**：

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

> 注意：`main.py` 顶部 `sys.path.insert(0, ...)` 确保本地 `backend/` 优先于 site-packages 中
> 同名的 `app` 包解析，避免 `ModuleNotFoundError: No module named 'app.module_one'`。

前端通过 Vite 代理 `/api` → `http://127.0.0.1:8000` 访问后端。

## 临时数据库（LIGHTCODE_DATABASE_PATH）

运行时数据库属于**运行状态**，包含审批后的任务状态，不应进入源码历史。
默认路径为 `<repo>/backend/data/lightcode.db`，由 `backend/app/main.py` 基于自身文件位置解析为绝对路径。

可用环境变量覆盖，指向临时数据库以隔离演示或验证：

```bash
# Unix / Git Bash
LIGHTCODE_DATABASE_PATH=/tmp/lightcode-demo.db uvicorn app.main:app --port 8000

# Windows PowerShell
$env:LIGHTCODE_DATABASE_PATH="C:\tmp\lightcode-demo.db"; uvicorn app.main:app --port 8000
```

- 相对路径会解析到 `backend/` 目录下，而非当前工作目录。
- 测试套件在 `conftest.py` 中自动将 `LIGHTCODE_DATABASE_PATH` 指向 `tmp_path`，因此各测试用例互不污染。
- `backend/data/*.db` 与 `backend/backend/data/*.db`（含 `-shm`/`-wal`）已在根 `.gitignore` 中忽略。

## Mock Runtime 边界（阶段 0.5）

后端仅暴露确定性 Mock 数据与审批状态迁移。明确**不**做以下事项：

- 不接入真实模型提供商，也不模拟持续模型流（SSE 仅回放已持久化事件）。
- 不访问真实项目文件、不执行源码写入、不执行终端命令。
- 不接收、存储或记录任何 API Key / 密钥 / token（不进入 SQLite、事件、前端状态、日志或截图）。
- 不实现 Electron、Git 写操作、网络下载或依赖安装能力。

## 验证

```bash
# 后端测试（使用隔离的临时数据库）
python -m pytest -q

# 前端测试与构建
npm run test
npm run build
```

验证通过后：审批状态在同一数据库刷新后持久化；使用**新数据库**启动时回到 `awaiting_approval` 等初始种子状态。
