# LightCode 设计原型

本目录保存已批准的独立 HTML 视觉原型。它们是 Vue 实现的视觉与交互参考，不得直接复制到 `frontend/src/`，也不代表运行时能力已经实现。

## 原型文件

- `agent-workspace.html`：智能体任务、计划、工具活动、差异审批与验证上下文工作区。
- `workspace-home.html`：最近项目与已注册工作区入口。
- `session-history.html`：任务历史时间线与页内只读详情抽屉。
- `settings.html`：两列配置中心。
- `settings-providers.html`：暖纸多供应商设置页（供应商列表 + 搜索 + 配置安全摘要 + 添加供应商弹层），设置分类当前仅含“模型与供应商”与“关于”。
- `PROTOTYPE_STATUS.md`：原型归档状态和跨文档交互裁决规则。

## 实现规则

1. 使用 Vue 组件、Vue Router、Pinia、类型化 fixture 和服务接口重建视图。
2. Mock、HTTP 与 SSE 实现必须位于服务边界之后；View 和 store 不直接访问 `fetch`、`EventSource`、SQLite、本地文件系统、Shell 或密钥。
3. Agent Workspace 保持固定左侧栏、居中执行流与可调整大小的右侧上下文抽屉。
4. 完整代码差异仅属于右侧审查抽屉；执行流只显示受影响文件和增删行摘要。
5. 待审批 ChangeSet 替换新任务输入为审查与拒绝操作。
6. Workspace Home 仅显示最近工作区；全部已注册工作区仅在可搜索的右侧抽屉中展示。
7. Session History 使用紧凑摘要；待审批任务返回审查，其他终态任务打开只读详情。
8. Settings 沿用主工作区已有的主侧边栏与 SVG 图标，不引入第二套主导航；设置分类暂只保留“模型与供应商”与“关于”。
9. Settings 的供应商列表与右侧详情展示安全视图：不显示 API Key、完整 Base URL、Authorization header 或上游原始响应；密钥只在提交瞬间存在于前端内存。

## 阶段对应关系

- **Phase 0.5**：原型通过确定性 Mock Runtime、REST 与 SQLite 事件回放获得数据；不得将原型内的读写文件、命令或模型交互视为真实执行。
- **Phase 1**：真实安全变更能力必须在服务端实现，并将状态、ChangeSet、审批和内建验证结果映射到既有视觉结构。完整规则见 `../phase1-safety-contract.md`。前端已连通全部 Phase 1 真实端点（2026-07-27）：`/real` 注册工作区列表、`/real/:id` 文件树/预览/搜索/建任务、`/real/:id/task/:taskId` 计划/差异/审批/SSE 事件；仅在 `VITE_LIGHTCODE_RUNTIME=api` 时启用真实数据，Mock 模式下这些页面使用 fixture。
- **Phase 3**：Electron 才可提供原生文件夹选择；在此之前浏览器不能提交任意本地路径。

当原型与架构文档不一致时，以 `../architecture/lightcode-local-first-agent-design.md` 决定行为和安全边界，以原型决定视觉语言。
