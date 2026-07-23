# LightCode 开发规则

## 项目目标

LightCode 是一个独立实现的、本地优先的可视化编码智能体，面向有基础编程经验的开发者。它不是 MiniCode-Python 或其他编码智能体项目的分支、重写或源码延续。

## 当前阶段

项目处于阶段 0.5：本地运行时基础。

- 允许实现 FastAPI、SQLite、确定性 Mock Runtime、REST API、SSE 事件回放，以及前端 HTTP/EventSource 服务适配器。
- 后端 API 必须保持 camelCase JSON，并与前端 TypeScript 合约一致。
- SQLite 只保存确定性 Mock 工作区、会话、任务、事件、审批、工具调用和变更集状态。
- 保留前端服务边界，使 Mock 服务可被 REST 和 SSE 适配器替换，而无需更改视图或 store 合约。
- 此阶段不得实现真实模型提供商、真实本地文件系统桥接、Shell 命令执行、工作区路径选择、密钥输入或存储、Electron、Git 写操作、网络下载或依赖安装能力。

## 必读文件

在设计或实现工作之前，请阅读：

- `docs/architecture/lightcode-local-first-agent-design.md`
- `docs/superpowers/plans/2026-07-23-phase-0-5-runtime-foundation.md`
- `docs/design/README.md`
- `docs/design/` 下相关的 HTML 原型文件

## 源码独立性

- 不得复制 MiniCode-Python 或其他编码智能体项目的源代码、测试、名称或文档。
- 根据 LightCode 自身记录的需求来设计和实现。
- 将架构决策和实现证据保留在此仓库中。

## 目录结构

```text
frontend/       Vue 应用和 Mock/HTTP/SSE 服务适配器
backend/        阶段 0.5 的 FastAPI 和 SQLite Mock Runtime
electron/       为后续桌面 shell 保留
docs/architecture/ 产品架构与决策
docs/design/       已批准的 HTML 视觉原型与 UI 备注
scripts/        开发与验证脚本
```

## 前端规则

- 使用 Vue 组件、Vue Router、Pinia 存储、类型化夹具和服务接口。不得将视觉原型整体粘贴到应用视图中。
- 将 `docs/design/` 中的 HTML 文件视为视觉和交互参考，而非运行时代码。
- 完整差异仅保留在右侧审查抽屉中。执行流只显示紧凑的差异摘要。
- 当变更集等待审批时，底部栏显示审查和拒绝操作，而非新任务输入框。

## 运行时规则

- 按 `docs/superpowers/plans/2026-07-23-phase-0-5-runtime-foundation.md` 的任务顺序实现，并遵循先写失败测试、再写最小实现、再运行聚焦验证的节奏。
- FastAPI 仅暴露确定性 Mock 数据和审批状态迁移；不得宣称或模拟真实项目文件访问、源码写入、终端执行或模型调用。
- SSE 只回放 SQLite 中已持久化的有序事件；不得伪造持续模型流。
- 提供商 API Key 不得进入 SQLite、事件、前端状态、日志或截图。

## 验证

- 每个任务完成后运行对应的后端或前端聚焦测试；所有任务结束后运行后端全量测试、前端全量测试和前端构建。
- 没有当前的测试/构建证据，不得声称页面或运行时功能已完成。
- 不得为了通过验证而引入 `skip`、假成功状态、禁用失败的检查或绕过手段。

## 安全

未来的运行时必须强制执行工作区隔离、显式差异审批、命令策略和密钥脱敏。在阶段 0.5 中不得伪造文件系统访问或安全声明。
