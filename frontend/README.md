# LightCode 前端

## 作用

`frontend/` 是 LightCode 的 Vue 3 用户界面：暖纸首页、工作区聊天式 Agent 主界面、任务/审批视图、多供应商设置层与技能管理视图。产品运行时只通过 HTTP 与 SSE 连接后端 FastAPI；`src/fixtures/` 中的类型化夹具**仅用于测试**，不作为产品运行时数据源。

前端不访问本地文件系统、SQLite、Shell、模型 Provider 或密钥。所有本地能力由后端 API 执行并受服务端策略约束。

## 技术栈

- Vue 3 / TypeScript / Vite / Vue Router / Pinia
- Vitest 与 Vue Test Utils
- 包管理器：npm

## 结构

```text
src/
  config/    运行时 API 基址解析（优先读 Electron 桥，其次环境变量，最后开发默认值）
  contracts/ 运行时 DTO 校验（拒绝 rootPath/filePath/patch/command 等字段）
  fixtures/  测试用类型化夹具（非产品数据源）
  router/    路由声明
  services/  HTTP 与 EventSource 服务适配器
  stores/    Pinia 状态管理
  types/     与后端对齐的 TypeScript 合约
  views/     首页（WorkspaceHomeView）、工作区（WorkspaceView）、任务（RealTaskView）、技能（SkillsView）
```

`docs/design/` 中的 HTML 是已批准的视觉参考，不得整体复制到 `src/`。完整 Diff 只显示在审查抽屉；执行流只显示受影响的文件和增删行摘要。

## 开发

先启动后端，再启动前端：

```bash
# 终端 1：backend/
cd backend
uvicorn app.main:app --reload --port 8000

# 终端 2：frontend/
cd frontend
npm install
npm run dev
```

Vite 将 `/api` 代理到 `http://127.0.0.1:8000`。如未设置 `VITE_LIGHTCODE_API_BASE_URL`，HTTP 服务默认直接访问 `http://127.0.0.1:8000/api/v1`。

在 Electron 桌面模式下，`config/runtime.ts` 优先读取 preload 桥暴露的 `window.lightcode.apiBaseUrl`（每次启动随机的 loopback 端口），无需环境变量。

## 验证

```bash
npm run test
npm run typecheck   # vue-tsc -b
npm run build
```

当前基线：141 个测试通过（20 文件），`vue-tsc -b && vite build` 通过。修改服务合约、store 或视图后，先运行对应聚焦测试，再运行全量测试与构建。

## 安全边界

- 服务层契约经 `contracts/*.schema.ts` 运行时校验，任何响应携带 `rootPath`/`filePath`/`patch`/`command` 都会抛 `ContractValidationError`。
- View 与 Pinia store 不直接调用 `fetch`、`EventSource`、SQLite 或本地文件系统。
- Provider 设置仅提交 `name`/`provider`/`baseUrl`/`apiKey`/`modelId` 等字段，key 不持久化到前端（localStorage/sessionStorage/Pinia）。
- 聊天与任务请求只提交 `workspaceId`、会话标识、用户消息与审批决定，不含任何本地路径。
