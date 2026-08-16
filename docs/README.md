# LightCode 文档索引

本目录收录 LightCode 的架构决策、安全契约、桌面设计与设计原型。**实时状态与验证基线以根目录 [`AGENTS.md`](../AGENTS.md) 的「状态追踪」为准**——本索引只做导航，不重复事实。

## 权威规范（行为 / 安全边界）

改动行为或安全边界前必读：

- [`architecture/lightcode-local-first-agent-design.md`](architecture/lightcode-local-first-agent-design.md) — 产品架构与决策，含阶段 A/B/3 实现状态。
- [`phase1-safety-contract.md`](phase1-safety-contract.md) — 真实文件能力的不变量、状态机、审批写入协议与错误码。
- [`phase2-model-provider-design.md`](phase2-model-provider-design.md) — 模型 Provider、凭据存储、聊天闭环与可观测性设计。
- [`workspace-registration.md`](workspace-registration.md) — 静态工作区注册与桌面动态注册规范。

## 桌面端设计与发布

- [`superpowers/specs/2026-08-13-phase-3-windows-desktop-design.md`](superpowers/specs/2026-08-13-phase-3-windows-desktop-design.md) — Windows 桌面端设计（Electron 安全外壳、sidecar、Credential Manager、NSIS）。
- [`superpowers/specs/2026-08-12-skill-management-design.md`](superpowers/specs/2026-08-12-skill-management-design.md) — 技能管理设计（ZIP 校验、Agent 门禁）。
- [`release-checklist-phase3-desktop.md`](release-checklist-phase3-desktop.md) — 桌面端发布检查清单（内部发布流程）。

## 设计原型

- [`design/README.md`](design/README.md) — HTML 视觉原型说明与实现规则。
- [`design/PROTOTYPE_STATUS.md`](design/PROTOTYPE_STATUS.md) — 原型归档状态与跨文档交互裁决。
- `design/*.html` — 已批准视觉基线（agent-workspace / workspace-home / session-history / settings-providers），仅作视觉参考，不是运行时代码。

## 推荐阅读顺序

1. [`AGENTS.md`（根）](../AGENTS.md) — 当前阶段与红线（内部规则）。
2. `architecture/lightcode-local-first-agent-design.md` — 产品形态与阶段结论。
3. 涉及真实文件变更 → `phase1-safety-contract.md` + `workspace-registration.md`。
4. 涉及模型 Provider / 可观测性 → `phase2-model-provider-design.md`。
