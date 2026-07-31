export type TaskState = 'awaiting_approval' | 'completed'
export type ToolStatus = 'ok' | 'pending' | 'idle'
export type ChangeSetStatus = 'pending' | 'approved' | 'rejected'

export interface WorkspaceFile {
  id: string
  name: string
  kind: 'file' | 'directory'
}

export interface Workspace {
  id: string
  name: string
  rootPath: string
  files: WorkspaceFile[]
}

export interface Session {
  id: string
  title: string
  status: 'running' | 'awaiting_approval' | 'completed'
}

export interface PlanStep {
  id: string
  label: string
  status: 'completed' | 'current' | 'upcoming'
}

export interface ToolCall {
  id: string
  toolName: 'read_file' | 'search_files' | 'generate_diff' | 'run_test'
  target: string
  status: ToolStatus
  duration: string
  detail: string[]
  fileSummary?: { path: string; additions: number; deletions: number }
}

export interface ChangeSet {
  id: string
  status: ChangeSetStatus
  filePath: string
  additions: number
  deletions: number
  before: string[]
  after: string[]
}

export interface VerificationOutput {
  status: 'pending' | 'running' | 'passed' | 'failed'
  command: string
  lines: string[]
}

export interface Task {
  id: string
  sessionId: string
  title: string
  state: TaskState
  plan: PlanStep[]
  toolCalls: ToolCall[]
  modelOutput: string
  changeSet: ChangeSet
  verification: VerificationOutput
}

export type WorkspaceStatus = 'waiting' | 'pass' | 'fail' | 'idle'

export interface WorkspaceEntry {
  id: string
  name: string
  rootPath: string
  status: WorkspaceStatus
  tags: string[]
  lastTask: string
  timeAgo: string
}

export type HistoryTaskStatus = 'waiting' | 'done' | 'fail' | 'cancelled'
export type PlanStepResult = 'done' | 'fail' | 'waiting' | 'pending'

export interface HistoryFileSummary {
  name: string
  additions: number
  deletions: number
}

export interface HistoryTestSummary {
  badge: 'pass' | 'fail' | 'none'
  text: string
}

export interface HistoryTaskEntry {
  id: string
  status: HistoryTaskStatus
  title: string
  summary: string
  time: string
  duration: string
  toolCount: number
  files: HistoryFileSummary[]
  testResult: HistoryTestSummary
}

export interface HistoryPlanStep {
  label: string
  state: PlanStepResult
}

export interface HistoryToolCall {
  icon: string
  name: string
  args: string
  ok: boolean
}

export interface HistoryFileChange {
  name: string
  additions: number
  deletions: number
  diff: string
}

export interface HistoryApproval {
  status: 'approved' | 'rejected' | 'none'
  text: string
  time: string
}

export interface HistoryTestResult {
  command: string
  result: 'pass' | 'fail' | 'none'
  detail: string
}

export interface TaskEvent {
  sequence: number
  eventType: string
  payload: Record<string, unknown>
  createdAt: string
}

// ---------------------------------------------------------------------------
// Phase 1: 真实安全变更闭环（字段与 backend/app/schemas/contracts.py 一一对齐）
// ---------------------------------------------------------------------------

/** 真实任务状态机（backend/app/services/phase1.py 中 tasks.state 的取值） */
export type RealTaskState =
  | 'awaiting_approval'
  | 'applying_change'
  | 'completed'
  | 'failed'
  | 'cancelled'

/** 变更集状态（backend changesets.status: active -> applied/rejected/failed） */
export type RealChangeSetStatus = 'active' | 'applied' | 'rejected' | 'failed'

/** 审批决定（backend 仅识别 approve；其余值一律走拒绝路径） */
export type ApprovalDecision = 'approve' | 'reject'

/** GET /registered-workspaces —— 公共视图，绝不包含真实根路径 */
export interface RegisteredWorkspace {
  id: string
  displayName: string
  enabled: boolean
  capabilities: string[]
  policyVersion: string
}

/** GET /registered-workspaces/{id}/files 的目录条目 */
export interface RegisteredFileEntry {
  name: string
  kind: 'file' | 'dir' | 'link' | 'secret'
  /** 服务端签发的短期浏览令牌；前端仅回传此令牌，绝不自行构造 relativePath */
  token: string
  /** 仅用于展示的服务器下发相对路径；前端绝不将其作为自由路径回传 */
  relativePath?: string
}

/** GET /registered-workspaces/{id}/file 的响应 */
export interface RegisteredFileContent {
  /** 仅用于展示；服务端不回显可写路径 */
  relativePath?: string
  content: string
}

/** GET /registered-workspaces/{id}/search 的命中条目 */
export interface WorkspaceSearchHit {
  name: string
  /** 服务端签发的短期浏览令牌；前端仅回传此令牌打开文件 */
  token: string
  /** 仅用于展示 */
  relativePath?: string
}

/** RealChangeSetResponse 对应结构 */
export interface RealChangeSet {
  changeSetId: string
  revision: number
  diffHash: string
  baseSha256: string
  proposedSha256: string
  logicalRelativePath: string
  status: RealChangeSetStatus
  policyVersion: string
  additions: number
  deletions: number
  before: string[]
  after: string[]
  expiresAt?: string | null
}

/** POST /real-tasks 请求体（CreateRealTaskRequest） */
export interface CreateRealTaskInput {
  workspaceId: string
  title: string
  templateId?: string
}

/** POST /real-tasks/{id}/approval 请求体（ApprovalRequest，extra=forbid） */
export interface ApprovalInput {
  decision: ApprovalDecision
  changeSetId: string
  revision: number
  diffHash: string
  idempotencyKey: string
}

/** RealTaskResponse 对应结构 */
export interface RealTask {
  id: string
  workspaceId: string
  sessionId: string
  kind: string
  state: RealTaskState
  title: string
  targetFile?: string | null
  changeSet?: RealChangeSet | null
  plan: PlanStep[]
  toolCalls: ToolCall[]
  verification: VerificationOutput
  createdAt: string
}

// --- Phase 2 / WP6：模型任务（仅提交 workspaceId + title；模型只"提议" ---
/** POST /api/v1/model-tasks 请求体（ModelTaskCreateRequest，extra=forbid） */
export interface CreateModelTaskInput {
  workspaceId: string
  title: string
}

/** POST/GET /api/v1/model-tasks 响应（ModelTaskResponse，extra=forbid） */
export interface ModelTaskResponse {
  id: string
  workspaceId: string
  state: string
  changeSetId: string | null
  detail: string
}

export interface HistoryTaskDetail {
  id: string
  status: HistoryTaskStatus
  title: string
  time: string
  duration: string
  toolCount: number
  summary: string
  plan: HistoryPlanStep[]
  toolCalls: HistoryToolCall[]
  files: HistoryFileChange[]
  approval: HistoryApproval
  test: HistoryTestResult
  failReason?: string
  failDetail?: string
  rejectedCmd?: string
  cancelInfo?: { stage: string; detail: string }
}

// --- Phase 2 / WP5：Provider 健康状态（仅展示，绝不含 key/baseUrl） ---

/** `GET /api/v1/provider/health` 的状态枚举 */
export type ProviderStatus = 'disabled' | 'unconfigured' | 'ready' | 'degraded'

/** 模型被允许的能力与预算（只读，服务端校验后下发） */
export interface ProviderCapabilities {
  tools: string[]
  canWriteFiles: boolean
  canRunCommands: boolean
  maxToolRounds: number
  maxRequestsPerTask: number
  maxInputBytes: number
  maxOutputTokens: number
  maxConcurrentTasks: number
}

/** 模型安全事实（布尔/枚举，绝不暴露凭据或完整 URL） */
export interface ProviderSecurity {
  apiKeyConfigured: boolean
  transport: 'https' | 'http' | 'none'
  originAllowlisted: boolean
  followRedirects: boolean
  trustEnvProxies: boolean
}

/** `GET /api/v1/provider/health` 响应（config 派生，计算时不发网络请求） */
export interface ProviderHealth {
  status: ProviderStatus
  provider: string
  modelId: string
  detail: string
  capabilities: ProviderCapabilities
  security: ProviderSecurity
}
