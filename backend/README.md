# LightCode 后端（Phase 0.5：本地运行时基础）

## 概述

`backend/` 是基于 FastAPI 与 SQLite 的**确定性 Mock Runtime**。它为前端提供工作区、会话、任务、历史、审批和有序事件的 REST/SSE 合约；所有数据由 `app/db/database.py` 的 `seed_database()` 确定性生成，仅用于界面演示、服务适配与合约验证。

当前后端不访问真实项目目录、不写源码、不执行命令、不调用模型、不接收或存储密钥。Phase 1 开始前，这些能力不得被模拟为已实现。

## 结构

```text
app/
  main.py                 FastAPI 入口、CORS 与 SQLite 生命周期
  api/routes.py           REST 与 SSE 路由
  db/database.py          SQLite schema、初始化与确定性种子
  schemas/contracts.py    camelCase Pydantic 请求/响应合约
  services/runtime.py     查询、审批状态迁移与事件读取
tests/                    pytest 用例；每个用例使用隔离临时数据库
pyproject.toml            Python 依赖与 pytest 配置
```

SSE 实现在 `app/api/routes.py`：它仅回放 SQLite 中已持久化且按 sequence 排序的事件，发送 `stream.end` 后关闭；它不是持续模型流。

## 依赖与启动

需要 Python 3.11 或更高版本。推荐使用隔离环境：

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
```

从 `backend/` 目录启动开发服务：

```bash
uvicorn app.main:app --reload --port 8000
```

`main.py` 会将本地 `backend/` 置于 Python 导入路径前部，避免系统环境中同名 `app` 包影响 `uvicorn app.main:app`。

前端 API 模式可通过 Vite `/api` 代理访问 `http://127.0.0.1:8000`，也可使用直接 API 基址 `http://127.0.0.1:8000/api/v1`。

## 临时数据库

运行时数据库包含审批后的 Mock 任务状态，不应进入源码历史。

- 默认路径：`<repo>/backend/data/lightcode.db`。
- 由 `backend/app/main.py` 基于自身位置解析为绝对路径。
- 可使用 `LIGHTCODE_DATABASE_PATH` 指向隔离的临时数据库。
- 相对的 `LIGHTCODE_DATABASE_PATH` 以 `backend/` 为基准解析，而不是当前工作目录。

```bash
# Unix / Git Bash
LIGHTCODE_DATABASE_PATH=/tmp/lightcode-demo.db uvicorn app.main:app --port 8000

# Windows PowerShell
$env:LIGHTCODE_DATABASE_PATH="C:\tmp\lightcode-demo.db"; uvicorn app.main:app --port 8000
```

测试 fixture 会把 `LIGHTCODE_DATABASE_PATH` 指向 `tmp_path`，避免用例互相污染。根 `.gitignore` 忽略 `backend/data/*.db` 和历史错误路径 `backend/backend/data/*.db` 及其 `-shm`/`-wal` 文件。

## Phase 0.5 合约与边界

当前 REST 路由：

```text
GET  /health
GET  /api/v1/workspaces/recent
GET  /api/v1/workspaces
GET  /api/v1/workspaces/{workspaceId}
GET  /api/v1/workspaces/{workspaceId}/sessions
GET  /api/v1/sessions/{sessionId}/tasks/current
POST /api/v1/tasks/{taskId}/changeset/approve
GET  /api/v1/workspaces/{workspaceId}/tasks/history
GET  /api/v1/tasks/{taskId}
GET  /api/v1/tasks/{taskId}/events
```

所有 JSON 使用 camelCase，并与 `frontend/src/types/agent.ts` 对齐。审批是当前唯一状态修改操作：它更新确定性 Mock 状态，并追加 `changeset.approved`、`verification.started`、`verification.completed` 事件；不会写入真实文件或执行真实验证。

明确禁止：

- 真实模型提供商与持续模型流；
- 真实工作区注册、读取或写入；
- Shell、`subprocess`、依赖安装、网络下载与 Git 写操作；
- API Key、密码、token 或其他密钥的接收、持久化、事件记录、前端传播、日志或截图；
- Electron。

## 验证

从 `backend/` 目录运行：

```bash
python -m pytest -q
```

当前基线为 16 个后端测试通过。全量验证还应从 `frontend/` 运行：

```bash
npm run test
npm run build
```

同一 SQLite 数据库重启后，审批后的 Mock 状态会保留；使用新的数据库启动则回到 `awaiting_approval` 等确定性种子状态。

## Phase 1 衔接

Phase 1 将以服务端静态注册的授权工作区、路径守卫、只读工具、确定性 ChangeSet、版本绑定审批、单文件原子写入与内建验证替换当前 Mock 审批行为。实施前必须遵守 `../docs/phase1-safety-contract.md` 与 `../docs/workspace-registration.md`；在这些约束实现并测试前，当前端点不得扩展为真实文件能力。
