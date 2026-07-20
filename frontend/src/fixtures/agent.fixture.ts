import type { Session, Task, Workspace } from '@/types/agent'

export const workspaceFixture: Workspace = {
  id: 'workspace-login-service',
  name: 'login-service',
  rootPath: '~/workspace/login-service',
  files: [
    { id: 'login', name: 'login.py', kind: 'file' },
    { id: 'test-login', name: 'test_login.py', kind: 'file' },
    { id: 'utils', name: 'utils/', kind: 'directory' },
    { id: 'config', name: 'config.yaml', kind: 'file' },
    { id: 'requirements', name: 'requirements.txt', kind: 'file' },
  ],
}

export const sessionsFixture: Session[] = [
  { id: 'session-login-validation', title: '登录接口校验', status: 'awaiting_approval' },
  { id: 'session-utils', title: '重构 utils.py', status: 'running' },
  { id: 'session-pagination', title: '修复分页 bug', status: 'completed' },
  { id: 'session-logging', title: '添加日志模块', status: 'completed' },
  { id: 'session-migration', title: '数据库迁移脚本', status: 'completed' },
]

export const taskFixture: Task = {
  id: 'task-login-validation',
  sessionId: 'session-login-validation',
  title: '为 login.py 的登录接口增加输入校验，并运行相关测试',
  state: 'awaiting_approval',
  plan: [
    { id: 'read', label: '读取 login.py 源码', status: 'completed' },
    { id: 'analyse', label: '分析现有登录接口', status: 'completed' },
    { id: 'diff', label: '生成输入校验 Diff', status: 'current' },
    { id: 'apply', label: '写入文件', status: 'upcoming' },
    { id: 'test', label: '运行相关测试', status: 'upcoming' },
  ],
  toolCalls: [
    {
      id: 'tool-read-login',
      toolName: 'read_file',
      target: 'login.py',
      status: 'ok',
      duration: '42ms',
      detail: [
        '1  def login(username, password):',
        '2      if not username or not password:',
        '3          return {"error": "Missing credentials"}',
        '4      user = db.query(username)',
        '5      return {"token": generate_token(user)}',
      ],
    },
    {
      id: 'tool-search-tests',
      toolName: 'search_files',
      target: 'test_login.py · 3 matches',
      status: 'ok',
      duration: '38ms',
      detail: ['test_login_empty_credentials (L12)', 'test_login_valid_user (L20)', 'test_login_wrong_password (L28)'],
    },
    {
      id: 'tool-generate-diff',
      toolName: 'generate_diff',
      target: 'login.py · +6 -2 · 等待审批',
      status: 'pending',
      duration: '~120ms',
      fileSummary: { path: 'login.py', additions: 6, deletions: 2 },
      detail: [
        '- def login(username, password):',
        '+ def login(username: str, password: str) -> dict:',
        '+     if not isinstance(username, str) or len(username) > 64:',
        '+         return {"error": "Invalid username"}',
        '+     username = username.strip().lower()',
      ],
    },
    {
      id: 'tool-run-tests',
      toolName: 'run_test',
      target: 'test_login.py · 等待写入后执行',
      status: 'idle',
      duration: '—',
      detail: ['等待批准修改后运行', '$ pytest test_login.py -v'],
    },
  ],
  modelOutput: '已读取 login.py 并分析登录接口。当前实现缺少类型检查、长度校验和输入清洗。Diff 已生成，等待你审批后写入文件并运行测试。',
  changeSet: {
    id: 'changeset-login-validation',
    status: 'pending',
    filePath: 'login.py',
    additions: 6,
    deletions: 2,
    before: [
      'def login(username, password):',
      '    if not username or not password:',
      '        return {"error": "Missing credentials"}',
      '    user = db.query(username)',
      '    return {"token": generate_token(user)}',
    ],
    after: [
      'def login(username: str, password: str) -> dict:',
      '    if not isinstance(username, str) or len(username) > 64:',
      '        return {"error": "Invalid username"}',
      '    if not isinstance(password, str) or len(password) < 8:',
      '        return {"error": "Password too short"}',
      '    username = username.strip().lower()',
      '    user = db.query(username)',
      '    return {"token": generate_token(user)}',
    ],
  },
  verification: {
    status: 'pending',
    command: '$ pytest test_login.py -v',
    lines: ['等待批准修改后运行'],
  },
}
