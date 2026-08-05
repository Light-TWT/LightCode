export type ToolStatus = 'ok' | 'pending' | 'idle'

export interface PlanStep {
  id: string
  label: string
  status: 'completed' | 'current' | 'upcoming'
}

export interface ToolCall {
  id: string
  toolName: string
  target: string
  status: ToolStatus
  duration: string
  detail: string[]
  fileSummary?: { path: string; additions: number; deletions: number }
}

export interface VerificationOutput {
  status: 'pending' | 'running' | 'passed' | 'failed'
  command: string
  lines: string[]
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

// --- Phase 2 / WP7：模型任务 SSE 生命周期（前端状态机） ---
/** 模型任务的稳定生命周期阶段（与后端 emit 的事件类型一一对应） */
export type ModelLifecycleStage =
  | 'created'
  | 'planning'
  | 'reading'
  | 'generating'
  | 'awaiting'
  | 'failed'

/** 单个生命周期阶段在 UI 时间线中的渲染态 */
export interface ModelLifecycleStep {
  stage: ModelLifecycleStage
  label: string
  status: 'completed' | 'current' | 'upcoming' | 'failed'
}

/** SSE 连接状态机（断点续传与降级可观测性） */
export type EventConnection = 'idle' | 'connecting' | 'open' | 'reconnecting' | 'closed'

/** 后端为模型任务 emit 的事件类型白名单（WP6 编排器决定） */
export const MODEL_TASK_EVENT_TYPES = [
  'task.created',
  'task.planning',
  'task.reading_workspace',
  'task.generating_diff',
  'task.awaiting_approval',
  'task.failed',
] as const

// --- Phase 2 / WP5：Provider 健康状态（仅展示，绝不含 key/baseUrl） ---

/** `GET /api/v1/provider/health` 的状态枚举 */
export type ProviderStatus = 'disabled' | 'unconfigured' | 'ready' | 'degraded'

/** 传输层枚举（ProviderSettingsResponse.transport） */
export type ProviderTransport = 'https' | 'http' | 'none'

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

// --- 核心 Agent 更新（阶段 A）：Provider 运行期设置 ---

/** POST /api/v1/provider/settings 请求体（ProviderSettingsRequest，extra=forbid） */
export interface ProviderSettingsInput {
  provider: string
  baseUrl: string
  apiKey: string
  modelId: string
}

/** GET/POST/DELETE /api/v1/provider/settings 响应（安全视图：无 key、无完整 baseUrl） */
export interface ProviderSettingsResponse {
  configured: boolean
  status: ProviderStatus
  provider: string
  modelId: string
  detail: string
  originAllowlisted: boolean
  transport: ProviderTransport
}

/** POST /api/v1/provider/settings/test 响应（连接测试：只有 ok 布尔与稳定错误码） */
export interface ProviderTestResponse {
  ok: boolean
  code: string
  detail: string
}

// --- 核心 Agent 更新（阶段 A）：聊天会话与消息 ---

/** 会话状态（backend chat_sessions.status，当前恒为 active） */
export type ChatSessionStatus = 'active'

/** 消息角色 */
export type ChatRole = 'user' | 'assistant'

/** 消息类型：普通回答 / 待审批编辑摘要 / 固定错误文案 */
export type ChatMessageKind = 'message' | 'edit_summary' | 'error'

/** ChatSessionResponse 对应结构 */
export interface ChatSession {
  id: string
  workspaceId: string
  title: string
  status: string
  createdAt: string
  updatedAt: string
}

/** ChatMessageResponse 对应结构 */
export interface ChatMessage {
  id: string
  sessionId: string
  sequence: number
  role: ChatRole
  content: string
  kind: ChatMessageKind
  taskId: string
  createdAt: string
}

/** ChatSubmitResponse：提交消息后的同步结果（已持久化的 assistant 消息 + 关联任务） */
export interface ChatSubmitResponse {
  message: ChatMessage
  taskId: string
}
