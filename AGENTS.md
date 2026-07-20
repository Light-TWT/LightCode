# LightCode 开发规则

## 项目目标

LightCode 是一个独立实现的、本地优先的可视化编码智能体，面向有基础编程经验的开发者。它不是 MiniCode-Python 或其他编码智能体项目的分支、重写或源码延续。

## 当前阶段

项目处于阶段 0：前端优先的视觉原型。

- 仅实现 Vue 3 + TypeScript + Vite。
- 对所有工作区、会话、任务、事件、变更集、审批和测试输出使用类型化本地 Mock 夹具。
- 在此阶段不得创建 FastAPI、SQLite、Electron、真实模型提供商、真实本地文件系统桥接或 shell 命令执行。
- 保留前端服务边界，使 Mock 服务未来可被 REST 和 SSE 适配器替换，而无需更改视图或 store 合约。

## 必读文件

在设计或实现工作之前，请阅读：

- `docs/architecture/lightcode-local-first-agent-design.md`
- `docs/design/README.md`
- `docs/design/` 下相关的 HTML 原型文件

## 源码独立性

- 不得复制 MiniCode-Python 或其他编码智能体项目的源代码、测试、名称或文档。
- 根据 LightCode 自身记录的需求来设计和实现。
- 将架构决策和实现证据保留在此仓库中。

## 目录结构

```text
frontend/       阶段 0 的 Vue 应用
backend/        为后续 FastAPI 运行时保留
electron/       为后续桌面 shell 保留
docs/
  architecture/ 产品架构与决策
  design/       已批准的 HTML 视觉原型与 UI 备注
scripts/        开发与验证脚本
```

## 前端规则

- 使用 Vue 组件、Vue Router、Pinia 存储、类型化夹具和服务接口。不得将视觉原型整体粘贴到应用视图中。
- 将 `docs/design/` 中的 HTML 文件视为视觉和交互参考，而非运行时代码。
- 首先实现 Agent Workspace。完成其桌面端和窄屏布局后再实现其余视图。
- 完整差异仅保留在右侧审查抽屉中。执行流只显示紧凑的差异摘要。
- 当变更集等待审批时，底部栏显示审查和拒绝操作，而非新任务输入框。

## 验证

- 每个页面实现后运行聚焦的前端测试和构建。
- 没有当前的测试/构建证据，不得声称页面已完成。
- 不得为了通过验证而引入 `skip`、假成功状态、禁用失败的检查或绕过手段。

## 安全

未来的运行时必须强制执行工作区隔离、显式差异审批、命令策略和密钥脱敏。在阶段 0 中不得伪造文件系统访问或安全声明。
