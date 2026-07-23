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
