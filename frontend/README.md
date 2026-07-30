# LightCode 前端

## 作用

`frontend/` 是 LightCode 的 Vue 3 用户界面。它实现工作区首页、智能体工作区、会话历史和设置页，并通过服务接口隔离运行时来源：默认使用类型化 Mock 数据；设置 `VITE_LIGHTCODE_RUNTIME=api` 时使用 FastAPI REST 与 EventSource SSE 适配器。

前端不访问本地文件系统、SQLite、Shell、模型提供商或密钥。所有需要本地能力的操作必须由后端 API 执行并受服务端策略约束。

## 技术栈

- Vue 3
- TypeScript
- Vite
- Vue Router
- Pinia
- Vitest 与 Vue Test Utils

包管理器为 **npm**。

## 结构

```text
src/
  config/       运行时 API 基址配置
  fixtures/     类型化 Mock 数据
  router/       路由声明
  services/     Mock、HTTP 与 EventSource 服务适配器
  stores/       Pinia 状态管理
  types/        前后端共享的 TypeScript 合约
  views/        Workspace Home、Agent Workspace、History、Settings 与 Phase 1 真实闭环（Real Workspace List/View、Real Task）页面
```

`docs/design/` 中的 HTML 是批准的视觉和交互参考，不得整体复制到 `src/`。完整 Diff 只应显示在 Agent Workspace 的右侧审查抽屉；中心执行流只显示文件和增删行摘要。

## 运行模式

### 默认 Mock 模式

不设置 `VITE_LIGHTCODE_RUNTIME` 时，服务层使用本地 fixture。Mock 仅用于界面与合约验证，不代表真实文件访问、写入、命令执行或模型调用。

```bash
npm run dev
```

### API 模式

先启动后端，再从 `frontend/` 目录启动：

```bash
VITE_LIGHTCODE_RUNTIME=api VITE_LIGHTCODE_API_BASE_URL=/api/v1 npm run dev
```

Windows PowerShell：

```powershell
$env:VITE_LIGHTCODE_RUNTIME = "api"
$env:VITE_LIGHTCODE_API_BASE_URL = "/api/v1"
npm run dev
```

Vite 将 `/api` 代理到 `http://127.0.0.1:8000`。如未设置 `VITE_LIGHTCODE_API_BASE_URL`，HTTP 服务默认直接访问 `http://127.0.0.1:8000/api/v1`。

## 验证

```bash
npm run test
npm run typecheck
npm run build
```

当前基线为 64 个前端测试通过（13 文件），`vue-tsc -b && vite build` 通过。修改服务合约、store 或视图后，应先运行对应聚焦测试，再运行完整测试和构建。

## Phase 1 前端边界（已完成 T8）

Phase 1 已扩展任务状态、ChangeSet 审查与安全错误展示，并新增真实工作区闭环（`RegisteredWorkspaceService`、`RealTaskService`）。浏览与读取改为不透明令牌导航（面包屑 token 栈，后端用 `browse_tokens` 签发/校验，前端不再持有自由路径），并新增运行时 DTO 校验（`contracts/real-task.schema.ts`：拒绝含 `rootPath` 的 workspace、未知 task state、畸形事件）。仍必须保留 `TaskService`、`WorkspaceService`、`RegisteredWorkspaceService`、`RealTaskService` 与 SSE 适配器边界：View 和 Pinia store 不直接调用 `fetch`、`EventSource`，不接收真实根路径、补丁正文或命令。详细规则见 `../docs/phase1-safety-contract.md`。
