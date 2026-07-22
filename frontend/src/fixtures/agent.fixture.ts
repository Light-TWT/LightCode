import type { HistoryTaskDetail, HistoryTaskEntry, Session, Task, Workspace, WorkspaceEntry } from '@/types/agent'

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

export const workspaceEntriesFixture: WorkspaceEntry[] = [
  { id: 'workspace-login-service', name: 'login-service', rootPath: '~/workspace/login-service', status: 'waiting', tags: ['Python', 'FastAPI'], lastTask: '登录接口输入校验', timeAgo: '3 分钟前' },
  { id: 'workspace-dashboard', name: 'dashboard-ui', rootPath: '~/workspace/dashboard-ui', status: 'pass', tags: ['Vue 3', 'TypeScript', 'Vite'], lastTask: '重构数据面板组件', timeAgo: '1 小时前' },
  { id: 'workspace-api', name: 'api-gateway', rootPath: '~/workspace/api-gateway', status: 'fail', tags: ['Node.js', 'Express'], lastTask: '添加请求限流中间件', timeAgo: '昨天' },
  { id: 'workspace-docs', name: 'docs-generator', rootPath: '~/workspace/docs-generator', status: 'idle', tags: ['Python', 'Markdown'], lastTask: '从 README 生成 API 文档', timeAgo: '3 天前' },
  { id: 'workspace-data', name: 'data-pipeline', rootPath: '~/workspace/data-pipeline', status: 'pass', tags: ['Python', 'Airflow'], lastTask: '优化 ETL 调度逻辑', timeAgo: '2 天前' },
  { id: 'workspace-cli', name: 'cli-tools', rootPath: '~/workspace/cli-tools', status: 'idle', tags: ['Go'], lastTask: '添加 JSON 格式化子命令', timeAgo: '5 天前' },
  { id: 'workspace-mobile', name: 'mobile-app', rootPath: '~/workspace/mobile-app', status: 'idle', tags: ['React Native'], lastTask: '升级导航库版本', timeAgo: '1 周前' },
]

export const taskHistoryEntriesFixture: HistoryTaskEntry[] = [
  { id: 'history-task-1', status: 'waiting', title: '为 login.py 的登录接口增加输入校验，并运行相关测试', summary: '已读取 login.py，分析现有登录接口。当前实现缺少类型检查、长度校验和输入清洗。Diff 已生成，等待你审批后写入文件并运行测试。', time: '今天 14:32', duration: '3 分钟前', toolCount: 4, files: [{ name: 'login.py', additions: 6, deletions: 2 }], testResult: { badge: 'none', text: '未运行' } },
  { id: 'history-task-2', status: 'done', title: '重构 utils.py 中的日期格式化函数', summary: '将分散的日期格式化逻辑统一为 format_date() 工具函数，支持 ISO 和本地化两种模式。已更新 3 处调用方。', time: '今天 13:18', duration: '5 分钟', toolCount: 12, files: [{ name: 'utils.py', additions: 18, deletions: 32 }, { name: 'login.py', additions: 2, deletions: 4 }, { name: 'test_utils.py', additions: 14, deletions: 0 }], testResult: { badge: 'pass', text: '6 passed' } },
  { id: 'history-task-3', status: 'fail', title: '为 login.py 添加 rate limiting 中间件', summary: '尝试引入 slowapi 库实现请求限流，但 requirements.txt 中缺少依赖且 pip install 在沙箱中被拒绝。任务终止。', time: '今天 11:45', duration: '2 分钟', toolCount: 6, files: [{ name: 'login.py', additions: 8, deletions: 0 }], testResult: { badge: 'fail', text: '1 failed' } },
  { id: 'history-task-4', status: 'done', title: '修复用户列表分页偏移量计算 bug', summary: '分页参数 offset 在第一页时错误地设为 1 而非 0，导致跳过首条记录。已修复并补充边界测试。', time: '昨天 16:20', duration: '8 分钟', toolCount: 9, files: [{ name: 'login.py', additions: 1, deletions: 1 }, { name: 'test_login.py', additions: 8, deletions: 0 }], testResult: { badge: 'pass', text: '5 passed' } },
  { id: 'history-task-5', status: 'done', title: '添加结构化日志模块', summary: '引入 logging 配置，统一所有模块的日志输出格式为 JSON，包含 request_id、timestamp 和 level 字段。', time: '昨天 14:05', duration: '3 分钟', toolCount: 7, files: [{ name: 'logger.py', additions: 28, deletions: 0 }, { name: 'login.py', additions: 3, deletions: 0 }], testResult: { badge: 'pass', text: '3 passed' } },
  { id: 'history-task-6', status: 'fail', title: '生成数据库迁移脚本', summary: '尝试从 SQLAlchemy model 自动生成 Alembic migration，但检测到数据库连接配置缺失，无法完成。', time: '7 月 18 日', duration: '4 分钟', toolCount: 5, files: [{ name: 'migrations/001.py', additions: 0, deletions: 0 }], testResult: { badge: 'none', text: '未运行' } },
  { id: 'history-task-7', status: 'done', title: '初始化项目结构和 config.yaml', summary: '创建基础目录结构、配置文件和入口脚本。设置 FastAPI 应用骨架。', time: '7 月 17 日', duration: '2 分钟', toolCount: 5, files: [{ name: 'config.yaml', additions: 15, deletions: 0 }, { name: 'main.py', additions: 22, deletions: 0 }, { name: 'requirements.txt', additions: 6, deletions: 0 }], testResult: { badge: 'pass', text: '2 passed' } },
  { id: 'history-task-8', status: 'cancelled', title: '添加 OAuth2 第三方登录', summary: '用户主动取消。Agent 仅完成了需求分析，未进入实现阶段。', time: '7 月 17 日', duration: '1 分钟', toolCount: 2, files: [], testResult: { badge: 'none', text: '未运行' } },
]

export const taskDetailFixture: HistoryTaskDetail = {
  id: 'history-task-1',
  status: 'waiting',
  title: '为 login.py 的登录接口增加输入校验，并运行相关测试',
  time: '今天 14:32',
  duration: '3 分钟前',
  toolCount: 4,
  summary: '已读取 login.py，分析现有登录接口。当前实现缺少类型检查、长度校验和输入清洗。Diff 已生成，等待你审批后写入文件并运行测试。',
  plan: [
    { label: '读取 login.py 源码', state: 'done' },
    { label: '分析现有登录接口', state: 'done' },
    { label: '生成输入校验 Diff', state: 'waiting' },
    { label: '写入文件', state: 'pending' },
    { label: '运行相关测试', state: 'pending' },
  ],
  toolCalls: [
    { icon: '📖', name: 'read_file', args: 'login.py', ok: true },
    { icon: '📖', name: 'read_file', args: 'test_login.py', ok: true },
    { icon: '🔍', name: 'search_files', args: 'test_login.py · 3 matches', ok: true },
    { icon: '📝', name: 'generate_diff', args: 'login.py', ok: true },
  ],
  files: [
    { name: 'login.py', additions: 6, deletions: 2, diff: '- def login(username, password):\n+ def login(username: str, password: str) -> dict:\n+     if not isinstance(username, str) or len(username) > 64:\n+         return {"error": "Invalid username"}\n+     username = username.strip().lower()' },
  ],
  approval: { status: 'none', text: '等待审批', time: '—' },
  test: { command: 'pytest test_login.py -v', result: 'none', detail: '等待批准修改后运行' },
}

export const taskDetailFixture2: HistoryTaskDetail = {
  id: 'history-task-2',
  status: 'done',
  title: '重构 utils.py 中的日期格式化函数',
  time: '今天 13:18',
  duration: '5 分钟',
  toolCount: 12,
  summary: '将分散的日期格式化逻辑统一为 format_date() 工具函数，支持 ISO 和本地化两种模式。已更新 3 处调用方。',
  plan: [
    { label: '分析 utils.py 中所有日期格式化调用', state: 'done' },
    { label: '设计统一的 format_date() 接口', state: 'done' },
    { label: '重构并更新调用方', state: 'done' },
    { label: '编写并运行测试', state: 'done' },
  ],
  toolCalls: [
    { icon: '📖', name: 'read_file', args: 'utils.py', ok: true },
    { icon: '📖', name: 'read_file', args: 'login.py', ok: true },
    { icon: '📖', name: 'read_file', args: 'test_utils.py', ok: true },
    { icon: '🔍', name: 'search_files', args: 'date_format|strftime', ok: true },
    { icon: '📝', name: 'generate_diff', args: 'utils.py', ok: true },
    { icon: '📝', name: 'generate_diff', args: 'login.py', ok: true },
    { icon: '📝', name: 'generate_diff', args: 'test_utils.py', ok: true },
    { icon: '✍️', name: 'write_file', args: 'utils.py', ok: true },
    { icon: '✍️', name: 'write_file', args: 'login.py', ok: true },
    { icon: '✍️', name: 'write_file', args: 'test_utils.py', ok: true },
    { icon: '🧪', name: 'run_test', args: 'test_utils.py', ok: true },
    { icon: '📊', name: 'summarize', args: 'task complete', ok: true },
  ],
  files: [
    { name: 'utils.py', additions: 18, deletions: 32, diff: '- def parse_date(s):\n-     return datetime.strptime(s, "%Y-%m-%d")\n- def format_iso(dt):\n-     return dt.isoformat()\n+ def format_date(dt, mode="iso"):\n+     if mode == "iso":\n+         return dt.isoformat()\n+     return dt.strftime("%Y年%m月%d日")' },
    { name: 'login.py', additions: 2, deletions: 4, diff: '- from utils import parse_date, format_iso\n+ from utils import format_date' },
    { name: 'test_utils.py', additions: 14, deletions: 0, diff: '+ def test_format_date_iso():\n+     assert format_date(dt, "iso") == "2026-07-20T00:00:00"\n+ def test_format_date_local():\n+     assert format_date(dt, "local") == "2026年07月20日"' },
  ],
  approval: { status: 'approved', text: '已批准写入', time: '今天 13:16' },
  test: { command: 'pytest test_utils.py -v', result: 'pass', detail: '6 passed · 0 failed · 0.4s' },
}

export const taskDetailFixture3: HistoryTaskDetail = {
  id: 'history-task-3',
  status: 'fail',
  title: '为 login.py 添加 rate limiting 中间件',
  time: '今天 11:45',
  duration: '2 分钟',
  toolCount: 6,
  summary: '尝试引入 slowapi 库实现请求限流，但 requirements.txt 中缺少依赖且 pip install 在沙箱中被拒绝。任务终止。',
  failReason: '依赖缺失',
  failDetail: 'slowapi 未安装，沙箱安全策略禁止 pip install。Agent 未写入任何文件。',
  rejectedCmd: 'pip install slowapi',
  plan: [
    { label: '读取 login.py 和 requirements.txt', state: 'done' },
    { label: '搜索现有限流实现', state: 'done' },
    { label: '生成 rate limiting Diff', state: 'done' },
    { label: '安装 slowapi 依赖', state: 'fail' },
    { label: '运行测试验证', state: 'pending' },
  ],
  toolCalls: [
    { icon: '📖', name: 'read_file', args: 'login.py', ok: true },
    { icon: '📖', name: 'read_file', args: 'requirements.txt', ok: true },
    { icon: '🔍', name: 'search_files', args: 'rate.limit|throttle', ok: true },
    { icon: '📝', name: 'generate_diff', args: 'login.py', ok: true },
    { icon: '🧪', name: 'run_test', args: 'test_login.py', ok: false },
    { icon: '⚙️', name: 'exec', args: 'pip install slowapi', ok: false },
  ],
  files: [
    { name: 'login.py', additions: 8, deletions: 0, diff: '+ from slowapi import Limiter\n+ from slowapi.util import get_remote_address\n+ limiter = Limiter(key_func=get_remote_address)\n+ @app.route("/login", methods=["POST"])\n+ @limiter.limit("5/minute")' },
  ],
  approval: { status: 'none', text: '未进入审批', time: '—' },
  test: { command: 'pytest test_login.py -v', result: 'fail', detail: "ImportError: No module named 'slowapi'" },
}

export const taskDetailFixture4: HistoryTaskDetail = {
  id: 'history-task-4',
  status: 'done',
  title: '修复用户列表分页偏移量计算 bug',
  time: '昨天 16:20',
  duration: '8 分钟',
  toolCount: 9,
  summary: '分页参数 offset 在第一页时错误地设为 1 而非 0，导致跳过首条记录。已修复并补充边界测试。',
  plan: [
    { label: '读取用户列表分页逻辑', state: 'done' },
    { label: '定位 offset 计算 bug', state: 'done' },
    { label: '修复并补充边界测试', state: 'done' },
  ],
  toolCalls: [
    { icon: '📖', name: 'read_file', args: 'login.py', ok: true },
    { icon: '📖', name: 'read_file', args: 'test_login.py', ok: true },
    { icon: '🔍', name: 'search_files', args: 'offset|pagination', ok: true },
    { icon: '📝', name: 'generate_diff', args: 'login.py', ok: true },
    { icon: '📝', name: 'generate_diff', args: 'test_login.py', ok: true },
    { icon: '✍️', name: 'write_file', args: 'login.py', ok: true },
    { icon: '✍️', name: 'write_file', args: 'test_login.py', ok: true },
    { icon: '🧪', name: 'run_test', args: 'test_login.py', ok: true },
    { icon: '📊', name: 'summarize', args: 'task complete', ok: true },
  ],
  files: [
    { name: 'login.py', additions: 1, deletions: 1, diff: '- offset = page\n+ offset = (page - 1) * per_page' },
    { name: 'test_login.py', additions: 8, deletions: 0, diff: '+ def test_pagination_first_page():\n+     resp = client.get("/users?page=1&per_page=10")\n+     assert len(resp.json()["items"]) == 10\n+ def test_pagination_empty():\n+     resp = client.get("/users?page=999")\n+     assert resp.json()["items"] == []' },
  ],
  approval: { status: 'approved', text: '已批准写入', time: '昨天 16:18' },
  test: { command: 'pytest test_login.py -v', result: 'pass', detail: '5 passed · 0 failed · 0.3s' },
}

export const taskDetailFixture5: HistoryTaskDetail = {
  id: 'history-task-5',
  status: 'done',
  title: '添加结构化日志模块',
  time: '昨天 14:05',
  duration: '3 分钟',
  toolCount: 7,
  summary: '引入 logging 配置，统一所有模块的日志输出格式为 JSON，包含 request_id、timestamp 和 level 字段。',
  plan: [
    { label: '设计 JSON 日志格式', state: 'done' },
    { label: '创建 logger.py 模块', state: 'done' },
    { label: '集成到 login.py 并测试', state: 'done' },
  ],
  toolCalls: [
    { icon: '📖', name: 'read_file', args: 'login.py', ok: true },
    { icon: '📖', name: 'read_file', args: 'config.yaml', ok: true },
    { icon: '📝', name: 'generate_diff', args: 'logger.py', ok: true },
    { icon: '📝', name: 'generate_diff', args: 'login.py', ok: true },
    { icon: '✍️', name: 'write_file', args: 'logger.py', ok: true },
    { icon: '✍️', name: 'write_file', args: 'login.py', ok: true },
    { icon: '🧪', name: 'run_test', args: 'test_logger.py', ok: true },
  ],
  files: [
    { name: 'logger.py', additions: 28, deletions: 0, diff: '+ import logging, json, uuid\n+ class JSONFormatter(logging.Formatter):\n+     def format(self, record):\n+         return json.dumps({"timestamp": self.formatTime(record), "level": record.levelname, "request_id": getattr(record, "request_id", "-"), "message": record.getMessage()})' },
    { name: 'login.py', additions: 3, deletions: 0, diff: '+ from logger import get_logger\n+ logger = get_logger(__name__)' },
  ],
  approval: { status: 'approved', text: '已批准写入', time: '昨天 14:03' },
  test: { command: 'pytest test_logger.py -v', result: 'pass', detail: '3 passed · 0 failed · 0.2s' },
}

export const taskDetailFixture6: HistoryTaskDetail = {
  id: 'history-task-6',
  status: 'fail',
  title: '生成数据库迁移脚本',
  time: '7 月 18 日',
  duration: '4 分钟',
  toolCount: 5,
  summary: '尝试从 SQLAlchemy model 自动生成 Alembic migration，但检测到数据库连接配置缺失，无法完成。',
  failReason: '连接缺失',
  failDetail: 'DATABASE_URL 环境变量未配置，Alembic 无法连接数据库。Agent 未写入任何迁移文件。',
  rejectedCmd: 'alembic revision --autogenerate -m "init"',
  plan: [
    { label: '读取 SQLAlchemy model 定义', state: 'done' },
    { label: '检查 Alembic 配置', state: 'done' },
    { label: '读取数据库连接配置', state: 'fail' },
    { label: '生成 migration 文件', state: 'pending' },
  ],
  toolCalls: [
    { icon: '📖', name: 'read_file', args: 'models.py', ok: true },
    { icon: '📖', name: 'read_file', args: 'alembic.ini', ok: true },
    { icon: '🔍', name: 'search_files', args: 'DATABASE_URL|sqlalchemy', ok: true },
    { icon: '⚙️', name: 'exec', args: 'alembic revision --autogenerate', ok: false },
    { icon: '⚙️', name: 'exec', args: 'echo $DATABASE_URL', ok: false },
  ],
  files: [
    { name: 'migrations/001.py', additions: 0, deletions: 0, diff: '# 未生成 — 迁移失败' },
  ],
  approval: { status: 'none', text: '未进入审批', time: '—' },
  test: { command: 'pytest', result: 'none', detail: '迁移未生成，跳过测试' },
}

export const taskDetailFixture7: HistoryTaskDetail = {
  id: 'history-task-7',
  status: 'done',
  title: '初始化项目结构和 config.yaml',
  time: '7 月 17 日',
  duration: '2 分钟',
  toolCount: 5,
  summary: '创建基础目录结构、配置文件和入口脚本。设置 FastAPI 应用骨架。',
  plan: [
    { label: '创建目录结构', state: 'done' },
    { label: '编写 config.yaml', state: 'done' },
    { label: '创建 main.py 入口', state: 'done' },
  ],
  toolCalls: [
    { icon: '✍️', name: 'write_file', args: 'config.yaml', ok: true },
    { icon: '✍️', name: 'write_file', args: 'main.py', ok: true },
    { icon: '✍️', name: 'write_file', args: 'requirements.txt', ok: true },
    { icon: '⚙️', name: 'exec', args: 'mkdir -p app tests', ok: true },
    { icon: '🧪', name: 'run_test', args: 'test_main.py', ok: true },
  ],
  files: [
    { name: 'config.yaml', additions: 15, deletions: 0, diff: '+ app:\n+   name: login-service\n+   port: 8000\n+   debug: true' },
    { name: 'main.py', additions: 22, deletions: 0, diff: '+ from fastapi import FastAPI\n+ app = FastAPI()\n+ @app.get("/health")\n+ async def health():\n+     return {"status": "ok"}' },
    { name: 'requirements.txt', additions: 6, deletions: 0, diff: '+ fastapi\n+ uvicorn\n+ pydantic\n+ sqlalchemy\n+ alembic\n+ pytest' },
  ],
  approval: { status: 'approved', text: '首次创建，无需审批', time: '7 月 17 日' },
  test: { command: 'pytest test_main.py -v', result: 'pass', detail: '2 passed · 0 failed · 0.1s' },
}

export const taskDetailFixture8: HistoryTaskDetail = {
  id: 'history-task-8',
  status: 'cancelled',
  title: '添加 OAuth2 第三方登录',
  time: '7 月 17 日',
  duration: '1 分钟',
  toolCount: 2,
  summary: '用户主动取消。Agent 仅完成了需求分析，未进入实现阶段。',
  cancelInfo: { stage: '需求分析完成后', detail: 'Agent 刚完成 OAuth2 provider 调研，正准备生成 Diff 时被用户终止。' },
  plan: [
    { label: '调研 OAuth2 provider 集成方式', state: 'done' },
    { label: '读取现有登录接口', state: 'done' },
    { label: '设计 OAuth2 回调流程', state: 'pending' },
    { label: '生成 Diff', state: 'pending' },
  ],
  toolCalls: [
    { icon: '🔍', name: 'search_files', args: 'oauth|authlib', ok: true },
    { icon: '📖', name: 'read_file', args: 'login.py', ok: true },
  ],
  files: [],
  approval: { status: 'none', text: '未进入审批', time: '—' },
  test: { command: '—', result: 'none', detail: '任务已取消' },
}

export const taskDetailFixtures: Record<string, HistoryTaskDetail> = {
  'history-task-1': taskDetailFixture,
  'history-task-2': taskDetailFixture2,
  'history-task-3': taskDetailFixture3,
  'history-task-4': taskDetailFixture4,
  'history-task-5': taskDetailFixture5,
  'history-task-6': taskDetailFixture6,
  'history-task-7': taskDetailFixture7,
  'history-task-8': taskDetailFixture8,
}

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
