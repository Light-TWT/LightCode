import type {
  RealTask,
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
    { name: 'src', kind: 'dir', relativePath: 'src' },
    { name: 'NOTES.md', kind: 'file', relativePath: 'NOTES.md' },
    { name: '.env', kind: 'secret', relativePath: '.env' },
  ],
  src: [
    { name: 'main.py', kind: 'file', relativePath: 'main.py' },
  ],
}

export const registeredFileContentFixture: RegisteredFileContent = {
  relativePath: 'NOTES.md',
  content: '# Notes\n\ndemo content line\n',
}

export const searchHitsFixture: WorkspaceSearchHit[] = [
  { name: 'NOTES.md', relativePath: 'NOTES.md' },
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
