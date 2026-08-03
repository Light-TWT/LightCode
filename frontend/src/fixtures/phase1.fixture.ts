import type {
  RealTask,
  TaskEvent,
  RegisteredFileContent,
  RegisteredFileEntry,
  RegisteredWorkspace,
  WorkspaceSearchHit,
} from '@/types/agent'

// Phase 1 Mock 演示数据：仅用于 Mock 模式下的 UI 演示与测试，
// 字段结构与后端 contracts.py 保持一致，不代表任何真实文件系统。

export const registeredWorkspacesFixture: RegisteredWorkspace[] = [
  {
    id: 'demo-real-workspace',
    displayName: 'Demo Real Workspace',
    enabled: true,
    capabilities: ['read', 'search', 'changeset'],
    policyVersion: 'policy-v1',
  },
  {
    id: 'disabled-workspace',
    displayName: 'Disabled Workspace',
    enabled: false,
    capabilities: [],
    policyVersion: 'policy-v1',
  },
]

export const registeredFilesFixture: Record<string, RegisteredFileEntry[]> = {
  '': [
    { name: 'src', kind: 'dir', token: 'src', relativePath: 'src' },
    { name: 'NOTES.md', kind: 'file', token: 'NOTES.md', relativePath: 'NOTES.md' },
    { name: '.env', kind: 'secret', token: '', relativePath: '.env' },
  ],
  src: [
    { name: 'main.py', kind: 'file', token: 'src/main.py', relativePath: 'src/main.py' },
  ],
}

export const registeredFileContentFixture: RegisteredFileContent = {
  relativePath: 'NOTES.md',
  content: '# Notes\n\ndemo content line\n',
}

export const searchHitsFixture: WorkspaceSearchHit[] = [
  { name: 'NOTES.md', token: 'NOTES.md', relativePath: 'NOTES.md' },
]

export const realTaskFixture: RealTask = {
  id: 'real-task-demo0001',
  workspaceId: 'demo-real-workspace',
  sessionId: 'real-session-real-task-demo0001',
  kind: 'real',
  state: 'awaiting_approval',
  title: '在 NOTES.md 末尾追加标记',
  targetFile: 'NOTES.md',
  changeSet: {
    changeSetId: 'cs-demo00000001',
    revision: 1,
    diffHash: 'demo-diff-hash',
    baseSha256: 'demo-base-sha256',
    proposedSha256: 'demo-proposed-sha256',
    logicalRelativePath: 'NOTES.md',
    status: 'active',
    policyVersion: 'policy-v1',
    additions: 1,
    deletions: 0,
    before: ['# Notes', '', 'demo content line'],
    after: ['# Notes', '', 'demo content line', '<!-- lightcode: appended marker -->'],
    expiresAt: null,
  },
  plan: [
    { id: 'step-read', label: '读取目标文件', status: 'completed' },
    { id: 'step-diff', label: '生成变更集', status: 'completed' },
    { id: 'step-approve', label: '等待审批', status: 'current' },
    { id: 'step-apply', label: '原子写入并验证', status: 'upcoming' },
  ],
  toolCalls: [],
  verification: { status: 'pending', command: '内建完整性验证', lines: [] },
  createdAt: '2026-07-27T00:00:00+00:00',
}

/** WP7：模型任务夹具（kind='model'，awaiting_approval，复用 Phase 1 审批闭环）。 */
export const modelTaskFixture: RealTask = {
  id: 'model-task-mock1',
  workspaceId: 'demo-real-workspace',
  sessionId: 'model-session-model-task-mock1',
  kind: 'model',
  state: 'awaiting_approval',
  title: '让模型在 NOTES.md 末尾追加标记',
  targetFile: 'NOTES.md',
  changeSet: {
    changeSetId: 'cs-model00000001',
    revision: 1,
    diffHash: 'model-diff-hash',
    baseSha256: 'model-base-sha256',
    proposedSha256: 'model-proposed-sha256',
    logicalRelativePath: 'NOTES.md',
    status: 'active',
    policyVersion: 'policy-v1',
    additions: 1,
    deletions: 0,
    before: ['# Notes', '', 'demo content line'],
    after: ['# Notes', '', 'demo content line', '<!-- lightcode: appended marker -->'],
    expiresAt: null,
  },
  plan: [
    { id: 'plan', label: '规划变更', status: 'completed' },
    { id: 'read', label: '读取 NOTES.md', status: 'completed' },
    { id: 'diff', label: '生成候选变更集', status: 'completed' },
    { id: 'approve', label: '等待审批', status: 'current' },
    { id: 'apply', label: '原子写入', status: 'upcoming' },
    { id: 'verify', label: '内建验证', status: 'upcoming' },
  ],
  toolCalls: [
    {
      id: 'model-task-mock1-read',
      toolName: 'read_file',
      target: 'NOTES.md',
      status: 'ok',
      duration: '—',
      detail: ['# Notes'],
    },
    {
      id: 'model-task-mock1-diff',
      toolName: 'generate_diff',
      target: 'NOTES.md · +1 -0 · 等待审批',
      status: 'pending',
      duration: '—',
      detail: ['marker'],
    },
  ],
  verification: { status: 'pending', command: '内建完整性验证', lines: [] },
  createdAt: '2026-07-31T00:00:00+00:00',
}

/** WP7：模型任务 SSE 事件流（与后端编排器 emit 顺序一致），驱动前端生命周期时间线。 */
export const modelTaskEventsFixture: TaskEvent[] = [
  {
    sequence: 1,
    eventType: 'task.created',
    payload: { taskId: 'model-task-mock1', kind: 'model' },
    createdAt: '2026-07-31T00:00:00+00:00',
  },
  {
    sequence: 2,
    eventType: 'task.planning',
    payload: {},
    createdAt: '2026-07-31T00:00:00.100+00:00',
  },
  {
    sequence: 3,
    eventType: 'task.reading_workspace',
    payload: { target: 'NOTES.md' },
    createdAt: '2026-07-31T00:00:00.200+00:00',
  },
  {
    sequence: 4,
    eventType: 'task.generating_diff',
    payload: { changeSetId: 'cs-model00000001', additions: 1, deletions: 0 },
    createdAt: '2026-07-31T00:00:00.300+00:00',
  },
  {
    sequence: 5,
    eventType: 'task.awaiting_approval',
    payload: { changeSetId: 'cs-model00000001', revision: 1 },
    createdAt: '2026-07-31T00:00:00.400+00:00',
  },
]
