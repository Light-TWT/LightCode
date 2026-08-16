# Phase 1 工作区注册规范

## 目标

真实工作区只能由本地 FastAPI 服务端注册。存在两种受控来源：**服务端启动静态配置**（`workspaces.json`）与 **桌面动态注册**（Phase 3，Electron 原生文件夹选择 → sidecar → 注册端点）。浏览器只负责选择已存在的 `workspaceId`，不能提交任意本地路径，也不能通过普通 API 创建或修改工作区根目录。

本规范与 `phase1-safety-contract.md` 配套使用。

## 注册模型

采用**服务端受控注册**：部署者维护一个不由浏览器写入的静态配置文件（`backend/workspaces.json`，见 `backend/README.md`），FastAPI 在启动阶段读取并验证；桌面模式另经带令牌的注册端点写入 SQLite `desktop_workspaces`。SQLite 仅保存注册状态、策略版本和审计镜像；服务端私有实体才是根路径的权威来源。

配置形状示例：

```json
{
  "workspaces": [
    {
      "id": "demo-workspace",
      "displayName": "Demo Workspace",
      "rootPath": "C:\\LightCodeWorkspaces\\demo",
      "enabled": true,
      "policy": "phase1-single-text-file"
    }
  ]
}
```

示例仅展示结构，不定义配置文件最终路径、环境变量名称或动态加载机制。实现时应将该位置记录在启动说明中，并确保配置文件不进入前端资源、事件、截图、日志或源码提交。

## 启动时校验

每个注册工作区在 FastAPI 启动时必须执行：

1. 验证 `id` 唯一、稳定且为服务端配置值。
2. 解析 `rootPath` 为 canonical path，确认目标存在且是目录。
3. 拒绝根目录自身为符号链接、junction 或其他 reparse point 的情形。
4. 记录启用状态、策略版本和校验结果；校验失败的工作区不可进入真实执行流程。
5. 将 canonical root 仅保留在服务端私有实体或内存注册表中。

桌面动态注册（Phase 3）在同一安全边界内运行：绝对路径只经 Electron 主进程与 sidecar 的可信 loopback 通道传递（携带每次启动生成的一次性令牌），渲染进程不持有根路径；注册请求经 `WorkspaceGuard` canonical/reparse 校验后写入 `desktop_workspaces`，同一 canonical root 幂等返回既有工作区。

工作区列表 API 至多返回：

```text
id
displayName
enabled
capabilities
policyVersion
```

不得返回 `rootPath`、canonical path、卷标、用户主目录或其他可推断本机目录结构的信息。

## 请求边界

允许浏览器提交：

```text
workspaceId
taskId
changeSetId
revision
diffHash
decision
idempotencyKey
```

禁止浏览器提交或影响：

```text
rootPath
filePath
relativePath
patch
fileContent
command
workingDirectory
workspace configuration
```

文件逻辑相对路径只能由服务端已持久化的 ChangeSet 产生。审批 API 不得接收或重建该路径。

## 生命周期

- **Phase 1**：静态注册、启动校验、只读列举与受控单文件变更。
- **Phase 2**：可在不放开任意路径的前提下增加受控策略与恢复能力。
- **Phase 3**：Electron 可通过原生文件夹选择创建或更新服务端注册信息；浏览器仍不获得任意文件系统能力。

### 桌面注册（Phase 3）

桌面注册是**服务端受控的动态注册**，与静态 `workspaces.json` 并存，但遵循同一安全边界：

1. 原生目录选择由 Electron 主进程触发，绝对路径只经主进程与 sidecar 之间的可信通道传递；渲染进程只提交 `workspaceId` 或安全摘要，绝不提交根路径。
2. 桌面注册请求需每次启动生成的一次性 sidecar 令牌校验；无令牌或令牌不符 fail-closed 拒绝。
3. 桌面注册不要求静态配置 `targetFile`。新目录经 `WorkspaceGuard` canonical/reparse 校验后进入系统；模型后续通过 `search_files`/`read_file` 决定指向哪个既有 UTF-8 文本文件的候选编辑，仍走显式审批与原子写入。
4. 桌面注册持久化到 SQLite（`desktop_workspaces` 表），存储服务端私有 canonical root 与安全元数据；公共 DTO、SSE、日志与错误不得返回真实根路径。
5. 同一 canonical root 唯一；重复或非法目录注册被拒绝。
6. 首期不删除或注销工作区；删除/注销留待后续阶段并需新入仓安全契约。

## 实现验收

1. 未注册或禁用的 `workspaceId` 无法执行只读或写入流程。
2. 请求中夹带 `rootPath`、`filePath`、`patch` 或 `command` 被 schema 拒绝或忽略，且不能影响服务端行为。
3. API 响应、SSE、日志和错误信息均不泄漏真实根路径。
4. 工作区根目录、父目录或目标文件涉及符号链接/junction/reparse point 时，访问被路径守卫拒绝。
5. Phase 1 测试只使用隔离 fixture 工作区，不能以开发者日常目录作为自动化测试目标。
6. 桌面注册路径必须来自受信任的 sidecar 通道并通过令牌校验，不能由浏览器直接提交。
