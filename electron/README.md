# Electron 桌面端（Phase 3）

`electron/` 是 LightCode 的 **Windows 桌面端交付**。Electron 只作为原生外壳与信任代理：窗口生命周期、sidecar 启动、原生文件夹选择与受限 IPC。它**没有**任何直接工作区写权限，也不把文件系统暴露给渲染进程。

安全边界（与 `../docs/phase1-safety-contract.md`、`../docs/workspace-registration.md` 一致）：

- 渲染进程（Vue）保持沙箱化：`contextIsolation: true`、`sandbox: true`、`nodeIntegration: false`、`webSecurity: true`。
- 唯一桥接是 preload 暴露的 `lightcode.workspace.selectFolder()`，返回安全 DTO；**不从 preload 暴露** `ipcRenderer`、Node 全局、路径字符串、shell、文件系统、环境变量或 process 方法。
- 用户在原生对话框选择的文件夹，由**主进程**通过可信 loopback 通道发给 sidecar 的注册端点（带 per-launch 令牌），前端永远拿不到根路径。

## 目录

```text
electron/
  src/main.ts     窗口 + sidecar 生命周期 + 原生文件夹选择 + 受限 IPC
  src/preload.ts  窄类型上下文桥（仅 selectFolder）
  src/sidecar.ts  spawn/健康探测/优雅关闭/脱敏错误
  src/ipc.ts      IPC 通道常量与运行时校验
  tests/          主进程/preload/sidecar 单元测试
```

## 开发模式

```powershell
# 1) 启动后端（可选，开发期也可让 Electron 自行拉起打包的 sidecar）
cd backend
uvicorn app.main:app --reload --port 8000

# 2) 启动前端 dev server
cd frontend
npm run dev

# 3) 以 Electron 加载 Vite dev server
cd electron
$env:VITE_DEV_SERVER="http://localhost:5173"
npm run dev
```

## 构建与打包

```powershell
# 1) 构建 Vue 渲染产物
cd frontend
npm run build -- --emptyOutDir false

# 2) 构建 FastAPI sidecar（PyInstaller，产物写入 electron/resources/sidecar/）
cd ..
powershell -ExecutionPolicy Bypass -File scripts/build-sidecar.ps1

# 3) 打包 Windows NSIS 安装器（会自动复制前端产物并编译 Electron）
cd electron
npm run build:win
# 产物：electron/release/LightCode Setup <version>.exe
```

`build:win` 内部按顺序执行 `compile`（tsc）→ `copy:frontend`（复制 `frontend/dist` 到 `electron/frontend-dist`）→ `electron-builder --win`。

## 数据位置

- **不可变应用资源**（Vue、sidecar.exe、Electron）位于安装目录，由安装器升级替换。
- **可变用户数据**（SQLite、技能、工作区注册）位于 `app.getPath('userData')`，**不在**安装目录内；卸载不会静默删除用户数据。Provider API Key 单独存于 Windows Credential Manager。

## 验证

```powershell
npm run test    # Electron 主进程/preload/sidecar 单元测试（当前基线 12 passed）
```

发布前完整验证清单见 `../docs/release-checklist-phase3-desktop.md`。