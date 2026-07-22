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
  status: 'pending' | 'passed'
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
