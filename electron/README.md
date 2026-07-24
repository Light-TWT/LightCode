# Electron 预留

`electron/` 为 **Phase 3：桌面端交付** 预留。当前项目已处于 Phase 0.5，本目录仍不得新增 Electron 代码、原生文件夹选择、FastAPI sidecar 或打包逻辑。

Phase 1 的授权工作区由本地 FastAPI 启动时读取服务端静态配置注册；浏览器不能提交任意本地路径。Electron 后续才负责原生文件夹选择、受控工作区注册体验、FastAPI sidecar 生命周期和本地打包。

相关架构与约束见：

- `../docs/architecture/lightcode-local-first-agent-design.md`
- `../docs/workspace-registration.md`
- `../docs/phase1-safety-contract.md`
