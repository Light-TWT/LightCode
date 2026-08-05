# Phase 1 安全变更 MVP 契约

## 目的

Phase 1 的目标不是开放任意本地编码能力，而是建立一个最小、可审查、可审计且对失败有确定行为的真实文件变更闭环：

```text
已注册工作区
  -> 受控只读工具
  -> 服务端生成并持久化 ChangeSet
  -> 用户审批指定版本
  -> 写前基线校验
  -> 单文件原子替换
  -> 内建完整性验证
  -> 持久化事件与历史
```

本文件是 Phase 1 的实现前置条件。若实现、原型或后续计划与本文件冲突，以本文件的安全边界为准；产品层面的总体行为仍以 `architecture/lightcode-local-first-agent-design.md` 为准。

> **核心 Agent 更新（阶段 A）**：Phase 1 的审批写入协议、原子替换、基线校验与内建验证
> 保持不变，并被聊天流程的编辑任务复用（`kind='model'` 任务仍走本契约的版本绑定审批）。
> 阶段 A 新增的是「运行期 Provider 设置 + 聊天闭环」，其边界见
> `phase2-model-provider-design.md` §6；Mock Runtime 与 mock-only 数据已移除。
> 阶段 B 之前的完整文件操作（删除/新建/重命名/移动/多文件事务）仍被本契约禁止。

## 已冻结范围

### 允许

- 单用户、单机、本地 FastAPI 服务，可管理多个由服务端静态配置注册的工作区。
- 浏览器只提交 `workspaceId`、会话标识、用户消息文本、任务标识、审批决定、ChangeSet 标识、版本、哈希和幂等键。
- 服务端受控只读工具：`list_files`、`read_file`、`search_files`（`search_files` 亦对模型开放，经严格 query 文本约束与命中上限）。
- 服务端受控任务模板生成确定性 ChangeSet；模型提议经服务端独立校验生成不可变 ChangeSet。
- 单个**既有、普通、UTF-8 文本文件**的审批后原子替换。
- SQLite 持久化任务、聊天会话与消息、工具结果、ChangeSet、审批、写入尝试、验证和有序事件。
- 不启动外部进程的内建验证：UTF-8 校验、基线/目标 SHA-256、写入后内容哈希和 diff 摘要核对。
- 运行期 Provider 设置：凭据仅进后端进程内存（`InMemoryProviderCredentialStore`），经最小化连接测试后方可保存。

### 不允许

- 浏览器提交任意 `rootPath`、`filePath`、补丁正文、文件内容、Shell 命令、API Key 或工作区配置。
- Shell、`subprocess`、PowerShell、cmd、bash、外部测试命令、依赖安装、网络下载、Git 写操作或进程控制。
- 删除、新建、重命名、移动文件或目录；多文件事务编辑；二进制、非 UTF-8 或超限文件修改。
- Electron、本地文件夹选择、远程工作区、云同步、多用户、自动合并外部改动、前端密钥持久化。
- 模型直接写文件、执行命令、决定审批、或接收根路径/自由文件路径（模型只能经 fileToken 读取，且只能读取受控检索命中的文件）。

## 安全不变量

1. **根路径仅在服务端**：真实工作区根路径只来自启动静态注册表，公共 API 和日志不得返回完整根路径。
2. **统一路径守卫**：每个文件访问都必须经服务端 `WorkspaceGuard` 解析，业务模块不得直接使用客户端输入调用文件 API。
3. **路径拒绝**：拒绝绝对路径、`..`、UNC 路径、驱动器路径、设备路径、父目录或目标的符号链接、junction 与 reparse point。
4. **文件拒绝**：拒绝目录、特殊文件、二进制、非 UTF-8、超限文件和策略禁止的文件。
5. **默认敏感文件拒绝**：拒绝 `.env`、`.git/**`、`*.pem`、`*.key`、`id_rsa*`、`credentials*`、`secrets*` 的读取和写入。扩展名、大小和 diff 行数上限由实现时的策略常量和测试固定。
6. **不可变 ChangeSet**：ChangeSet 必须由服务端生成、持久化、版本化，绑定 `changeSetId`、`revision`、`diffHash`、逻辑相对路径、`baseSha256`、`proposedSha256` 和策略版本。
7. **审批绑定版本**：用户审批的对象是指定 `changeSetId + revision + diffHash`，不是泛化的“继续执行”。旧版本、过期版本或哈希不匹配的审批一律无效。
8. **写前重检**：实际写入前必须再次校验路径策略、文件身份和当前 SHA-256。基线变化必须返回 `STALE_BASE`，不得覆盖外部改动。
9. **持久化优先**：状态迁移、工具结果、审批和事件必须在 SQLite 事务中提交成功后才可被 SSE 或 UI 观察到。
10. **Mock 隔离**：Phase 0.5 的种子任务标记为 legacy/mock，只允许读取和演示，不得经兼容端点触发真实文件写入。

## 状态机

Phase 1 真实执行任务采用：

```text
created
  -> planning
  -> reading_workspace
  -> generating_diff
  -> awaiting_approval
  -> applying_change
  -> running_verification
  -> completed | failed | cancelled
```

- 在 `awaiting_approval` 前仅允许只读工具。
- 只有有效审批才能从 `awaiting_approval` 进入 `applying_change`。
- 用户拒绝进入 `cancelled`，记录 `USER_REJECTED` 和可选的受限反馈。
- 基线冲突、策略拒绝、原子替换失败、验证失败或恢复不确定进入 `failed`，并记录稳定机器码。
- `awaiting_command_approval` 和真实命令白名单保留给未来允许受控进程执行的阶段；Phase 1 不进入该状态。

## 审批与写入协议

审批请求只能包含以下信息：

```json
{
  "decision": "approve",
  "changeSetId": "cs_123",
  "revision": 3,
  "diffHash": "sha256:...",
  "idempotencyKey": "client-generated-uuid"
}
```

服务端顺序：

1. 校验任务状态、ChangeSet 状态、版本、哈希、有效期和幂等键。
2. 在事务中写入审批记录，将任务设为 `applying_change`，并写入有序事件。
3. 获取目标文件锁，再次执行路径和基线哈希检查。
4. 在同一目录写入临时文件，再使用原子替换更新目标文件。
5. 执行内建 UTF-8 与目标哈希验证。
6. 在事务中写入应用尝试、验证结果、终态和事件。

同一审批请求的网络重试只允许产生一次应用尝试。两个任务竞争同一文件时，最多一个可以成功；另一个必须因锁或基线变化失败，不得静默覆盖。

## 失败和恢复承诺

- 临时写入或原子替换前失败：原文件必须保持基线内容。
- 写入后内建验证失败且进程仍存活：服务可以在同一受控调用中尝试恢复原内容。
- 进程崩溃、磁盘故障或外部程序在写入后继续修改：不能承诺自动恢复。服务重启后根据当前文件哈希判定为基线、目标或未知。
- 结果未知时记录 `APPLY_OUTCOME_UNKNOWN`，阻止对该任务自动继续写入，并要求人工检查。

## API、事件与错误码

- 保持 `/api/v1` 和 camelCase JSON。
- 公共 DTO 不包含真实根路径、内部堆栈、密钥或策略实现细节。
- 每个任务事件使用单调递增的 sequence；SSE 仅传递已经持久化的事实事件。
- 推荐稳定错误码：

```text
WORKSPACE_NOT_REGISTERED
WORKSPACE_DISABLED
CHANGESET_NOT_ACTIVE
CHANGESET_EXPIRED
CHANGESET_REVISION_MISMATCH
APPROVAL_ALREADY_PROCESSED
INVALID_STATE_TRANSITION
STALE_BASE
PATH_POLICY_DENIED
SECRET_FILE_DENIED
SYMLINK_DENIED
FILE_TYPE_DENIED
FILE_SIZE_DENIED
APPLY_OUTCOME_UNKNOWN
USER_REJECTED
```

## 必须验证的负向场景

- 伪造 workspaceId、rootPath、filePath、patch 或 command 不得导致文件访问。
- 路径穿越、符号链接/junction、秘密文件、目录、二进制、非 UTF-8 和超限输入必须被拒绝。
- 错误的 ChangeSet ID、revision、diffHash、过期审批和重复审批不得写入文件。
- 外部改动后的旧 ChangeSet 必须以 `STALE_BASE` 失败。
- 任何 Phase 1 代码路径都不得启动 shell、包管理、网络请求、Git 写操作或读取密钥。
