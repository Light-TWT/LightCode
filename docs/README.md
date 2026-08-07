# LightCode 文档索引

本目录收录 LightCode 的架构决策、安全契约、阶段计划与设计原型。**实时状态与验证基线以根目录 [`AGENTS.md`](../AGENTS.md) 的「状态追踪」为准**——本索引只做导航，不重复事实。

## 权威规范（行为 / 安全边界）

改动行为或安全边界前必读：

- [`architecture/lightcode-local-first-agent-design.md`](architecture/lightcode-local-first-agent-design.md) — 产品架构与决策，含 Phase 1/2 实现状态（M4–M6）。
- [`phase1-safety-contract.md`](phase1-safety-contract.md) — Phase 1 真实文件能力的不变量、状态机、审批写入协议与错误码。
- [`phase2-model-provider-design.md`](phase2-model-provider-design.md) — Phase 2 模型 Provider 与可观测性 / 发布门禁的权威设计（WP5–WP8）。
- [`workspace-registration.md`](workspace-registration.md) — 服务端静态工作区注册与启动校验规则。

## 阶段计划（历史记录）

- [`2026-07-23-phase-0-5-runtime-foundation.md`](2026-07-23-phase-0-5-runtime-foundation.md) — Phase 0.5 Mock Runtime 的任务分解与实现记录。
- [`2026-07-30-phase-2-model-and-dx-plan.md`](2026-07-30-phase-2-model-and-dx-plan.md) — Phase 2 实施计划（WP1–WP8）；WP5–WP8 已实现，状态见文件顶部与 `AGENTS.md`。
- [`superpowers/specs/2026-08-07-multi-provider-settings-design.md`](superpowers/specs/2026-08-07-multi-provider-settings-design.md) — 多供应商设置页设计（2026-08-07，阶段 A/B 已实现）。
- [`superpowers/plans/2026-08-07-settings-provider-refactor.md`](superpowers/plans/2026-08-07-settings-provider-refactor.md) — 多供应商设置页重构实施计划（阶段 A/B）。

## 设计原型

- [`design/README.md`](design/README.md) — HTML 视觉原型说明与实现规则。
- [`design/PROTOTYPE_STATUS.md`](design/PROTOTYPE_STATUS.md) — 原型归档状态与跨文档交互裁决。
- `design/*.html` — 已批准视觉基线（agent-workspace / workspace-home / session-history / settings / settings-providers），仅作视觉参考，不是运行时代码。

## 推荐阅读顺序

1. [`AGENTS.md`（根）](../AGENTS.md) — 当前阶段与红线。
2. `architecture/lightcode-local-first-agent-design.md` — 产品形态与阶段结论。
3. 涉及真实文件变更 → `phase1-safety-contract.md` + `workspace-registration.md`。
4. 涉及模型 Provider / 可观测性 → `phase2-model-provider-design.md`。
