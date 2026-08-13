# LightCode Windows 桌面端 —— 发布检查清单（Release Checklist）

> 适用范围：`electron/` 打包出的 NSIS 安装器（unsigned 内部版）。公开发布前必须通过本清单，并单独制作签名与自动更新计划。

## 一、构建前门禁

- [ ] 后端全量测试通过：`cd backend; python -m pytest -q`
- [ ] 前端测试通过：`cd frontend; npm run test`
- [ ] 前端类型检查 + 构建通过：`cd frontend; npm run typecheck; npm run build -- --emptyOutDir false`
- [ ] Electron 单元测试通过：`cd electron; npm run test`
- [ ] 源码级扫描：无应用/源码日志、事件、DTO、截图夹具或安装器配置包含真实 API Key、完整 Provider URL 或绝对工作区路径。

## 二、构建产物

- [ ] sidecar 已构建：`powershell -ExecutionPolicy Bypass -File scripts/build-sidecar.ps1`
  - 产物：`electron/resources/sidecar/lightcode-sidecar.exe`（已 gitignore）
- [ ] NSIS 安装器已构建：`cd electron; npm run build:win`
  - 产物：`electron/release/LightCode Setup <version>.exe`（已 gitignore）
- [ ] 记录安装器哈希：`Get-FileHash "electron\release\LightCode Setup <version>.exe" -Algorithm SHA256`

## 三、干净机器安装验证（手动）

- [ ] 在**全新 Windows 账户**上运行安装器，完成安装。
- [ ] 应用启动后出现暖纸首页（居中 LightCode + 聊天框 + 工作区选择器）。
- [ ] 使用文件夹选择器注册一个真实项目文件夹，确认弹窗保留该文件夹、聊天框可用。
- [ ] 发送首条消息，确认创建会话并跳转进入。
- [ ] 关闭应用并重新启动：
  - 已注册工作区仍存在（SQLite 持久化）；
  - 历史会话仍存在。
- [ ] Provider 凭据已配置时，重启后凭据仍可用（Windows Credential Manager 持久化）。

## 四、升级验证（手动）

- [ ] 构建 v2 安装器，覆装到已有 v1。
- [ ] 确认应用资源被替换，而用户数据（会话/工作区/凭据）保留。
- [ ] 确认版本号已更新：`electron/package.json` version 与安装器文件名一致。

## 五、卸载验证（手动）

- [ ] 卸载移除应用资源。
- [ ] 卸载**不静默删除**用户数据（用户数据在 `app.getPath('userData')`，不在安装目录内）。

## 六、数据备份提醒（对用户）

- [ ] 用户数据位置：`%APPDATA%\LightCode`（SQLite、技能、凭据）。
- [ ] 升级前建议备份该目录。

## 七、公开发布门禁（发布前必须完成）

- [ ] 制定并落地**代码签名**计划（SmartScreen 未知发布者警告消除）。
- [ ] 制定**自动更新**计划（当前为手动覆装升级）。
- [ ] 最终扫描确认无密钥/路径泄露。

## 记录本

- 版本：`0.1.0`
- 后端测试通过数：303 passed / 2 skipped
- 前端测试通过数：141 passed（19 文件）
- Electron 测试通过数：10 passed（3 文件）
- sidecar 产物大小：约 180 MB
- 安装器产物大小：约 256 MB
- 安装器 SHA-256：`____________________`
- 干净安装证据：`____________`
- 重启持久化证据：`____________`
- 升级证据：`____________`