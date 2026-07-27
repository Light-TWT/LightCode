# LightCode 后端（Phase 0.5 Mock Runtime + Phase 1 安全变更 MVP）

## 概述

`backend/` 是基于 FastAPI 与 SQLite 的本地运行时，当前承载两条隔离的闭环：

- **Phase 0.5 Mock Runtime**：由 `app/db/database.py` 的 `seed_database()` 确定性生成工作区、会话、任务、历史和审批状态，仅用于界面演示、服务适配与合约验证。不访问真实项目目录、不写源码、不执行命令、不调用模型、不接收或存储密钥。
- **Phase 1 安全变更 MVP（后端）**：服务端静态注册授权工作区，提供受控只读工具（`list_files`/`read_file`/`search_files`）、服务端生成的确定性 ChangeSet、版本绑定审批，以及对单个既有 UTF-8 文本文件的原子替换与内建完整性验证。安全不变量以 `../docs/phase1-safety-contract.md` 与 `../docs/workspace-registration.md` 为准。

两条闭环共享同一 SQLite 与 SSE 基础设施，但数据严格隔离：Phase 0.5 种子任务标记为 `kind='mock'`，Phase 1 真实任务标记为 `kind='real'`，互不可跨端点触发对方行为。

## 结构

```text
app/
  main.py                  FastAPI 入口、CORS、SQLite 与 WorkspaceRegistry 生命周期
  api/routes.py            REST 与 SSE 路由（Mock + Phase 1 真实端点）
  db/database.py           SQLite schema、迁移、初始化与确定性种子
  schemas/
    contracts.py           camelCase Pydantic 请求/响应合约（extra="forbid"）
    errors.py              稳定错误码（Phase1Error）
  security/
    fs.py                  文件系统分类与规范化
    guard.py               WorkspaceGuard 统一路径守卫
  services/
    runtime.py             Mock 查询、审批状态迁移与事件读取
    changeset.py           确定性 append-marker ChangeSet 生成
    atomic_write.py        临时文件 + os.replace 原子替换 + 内建 UTF-8/哈希验证 + 每文件锁
    phase1.py              真实任务生命周期与 6 步审批写入协议
  workspaces/
    registry.py            服务端静态工作区注册表（启动加载）
tests/                    pytest 用例；每个用例使用隔离临时数据库
pyproject.toml            Python 依赖与 pytest 配置
```

SSE 实现在 `app/api/routes.py`：它仅回放 SQLite 中已持久化且按 `sequence` 排序的事件，不是持续模型流。每帧携带 `id:`（即 `sequence`），支持 `?after_sequence=<n>` 显式续传与浏览器自动重连的 `Last-Event-ID`；`?tail=true` 时回放后保持连接轮询新事件（默认 30s 窗口），否则发送 `stream.end` 后关闭。Phase 1 真实任务事件复用既有的 `task_events` 表，并有独立端点 `GET /api/v1/real-tasks/{taskId}/events`。

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

前端 API 模式可通过 Vite `/api` 代理访问 `http://127.0.0.1:8000`，也可使用直接 API 基址 `http://127.0.0.1:8000/api/v1`。以 API 模式启动前端（连通 Phase 1 真实端点与 `/real` 页面）：

```bash
# 从 frontend/ 目录
VITE_LIGHTCODE_RUNTIME=api npm run dev
```

不设置该变量时前端使用内置 Mock 服务，不访问后端。

## 配置与数据

### 运行时数据库

运行时数据库包含审批后的 Mock 任务状态与 Phase 1 真实任务/ChangeSet/审批记录，不应进入源码历史。

- 默认路径：`<repo>/backend/data/lightcode.db`。
- 由 `backend/app/main.py` 基于自身位置解析为绝对路径。
- 可使用 `LIGHTCODE_DATABASE_PATH` 指向隔离的临时数据库；相对路径以 `backend/` 为基准解析，而不是当前工作目录。
- 根 `.gitignore` 忽略 `backend/data/*.db` 及其 `-shm`/`-wal` 文件。

### 工作区注册配置（Phase 1）

Phase 1 真实工作区只来自服务端启动静态配置，浏览器不得提交本地路径：

- 默认配置文件：`backend/workspaces.json`（含 `rootPath` + `targetFile` 等，含机器特定绝对路径）。
- 也可用环境变量 `LIGHTCODE_WORKSPACES_CONFIG` 指向任意 JSON 配置文件。
- 该配置文件**已 gitignore，绝不提交**（防止泄露本机目录结构）。
- 配置文件缺失时服务正常启动，但真实工作区数量为零（仅 Mock 能力可用）。
- 仓库内置 `backend/workspaces.example.json` 模板：复制为 `backend/workspaces.json` 后，将每条 `rootPath` 改为本机真实绝对路径即可（其余字段按需调整；`rootPath` 不得是符号链接/联结且必须真实存在）。
- 配置形态与启动校验规则见 `../docs/workspace-registration.md`。

```bash
# 用隔离配置启动（示例）
LIGHTCODE_WORKSPACES_CONFIG=/tmp/lightcode-workspaces.json uvicorn app.main:app --port 8000
```

## REST 路由

### Phase 0.5 Mock 端点

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

所有 JSON 使用 camelCase，并与 `frontend/src/types/agent.ts` 对齐。 Mock 审批是当前唯一状态修改操作：它更新确定性 Mock 状态并追加 `changeset.approved`、`verification.started`、`verification.completed` 事件；不会写入真实文件或执行真实验证。

### Phase 1 真实端点

```text
GET  /api/v1/registered-workspaces
GET  /api/v1/registered-workspaces/{workspaceId}/files
GET  /api/v1/registered-workspaces/{workspaceId}/file?path=<logicalRelative>
GET  /api/v1/registered-workspaces/{workspaceId}/search?query=<text>
POST /api/v1/real-tasks
GET  /api/v1/real-tasks/{taskId}
POST /api/v1/real-tasks/{taskId}/approval
GET  /api/v1/real-tasks/{taskId}/events
```

真实任务 SSE 端点支持 `?after_sequence=`、`Last-Event-ID` 续传与 `?tail=true` 轮询。公共 DTO、SSE、日志与错误信息均不含真实根路径；审批请求仅接受 `decision`/`changeSetId`/`revision`/`diffHash`/`idempotencyKey`，且 Pydantic `extra="forbid"` 拒绝任何 `rootPath`/`filePath`/patch/command。稳定错误码见 `app/schemas/errors.py`。

## 禁止清单（全局）

- 真实模型提供商与持续模型流；
- Phase 1 之外的任意真实文件系统修改：新建/删除/重命名/移动、多文件事务、二进制/非 UTF-8/超限文件；
- Shell、`subprocess`、依赖安装、网络下载与 Git 写操作；
- API Key、密码、token 或其他密钥的接收、持久化、事件记录、前端传播、日志或截图；
- Electron。

Phase 1 允许的受控真实读取与单文件原子写入，必须在 `../docs/phase1-safety-contract.md` 的全部不变量下执行。

## 验证

从 `backend/` 目录运行：

```bash
python -m pytest -q
```

当前基线为 **94 个后端测试通过 + 2 个跳过**（跳过项为沙箱环境 `os.symlink` 静默降级导致不可检测，对应逻辑已由 monkeypatch 测试覆盖）。全量验证还应从 `frontend/` 运行：

```bash
npm run test
npm run build
```

同一 SQLite 数据库重启后，审批后的 Mock 状态与 Phase 1 真实任务/ChangeSet/审批记录会保留；使用新的数据库启动则回到确定性种子或 `awaiting_approval` 状态。
