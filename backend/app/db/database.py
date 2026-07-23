import json
import sqlite3
from pathlib import Path
from typing import Optional

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS workspaces (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    root_path TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'idle',
    tags_json TEXT NOT NULL DEFAULT '[]',
    last_task TEXT NOT NULL DEFAULT '',
    time_ago TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running'
);

CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    title TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'created',
    plan_json TEXT NOT NULL DEFAULT '[]',
    tool_calls_json TEXT NOT NULL DEFAULT '[]',
    model_output TEXT NOT NULL DEFAULT '',
    changeset_status TEXT NOT NULL DEFAULT 'pending',
    verification_status TEXT NOT NULL DEFAULT 'pending',
    verification_command TEXT NOT NULL DEFAULT '',
    verification_lines_json TEXT NOT NULL DEFAULT '[]'
);

CREATE TABLE IF NOT EXISTS task_history (
    id TEXT PRIMARY KEY,
    workspace_id TEXT NOT NULL,
    status TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    time TEXT NOT NULL DEFAULT '',
    duration TEXT NOT NULL DEFAULT '',
    tool_count INTEGER NOT NULL DEFAULT 0,
    files_json TEXT NOT NULL DEFAULT '[]',
    test_result_json TEXT NOT NULL DEFAULT '{}',
    detail_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS task_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    event_type TEXT NOT NULL,
    payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT '',
    UNIQUE(task_id, sequence)
);
"""


def initialize_database(database_path: Optional[Path] = None) -> sqlite3.Connection:
    if database_path is None:
        database_path = Path("backend/data/lightcode.db")
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(database_path), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA_SQL)
    seed_database(connection)
    connection.commit()
    return connection


def seed_database(connection: sqlite3.Connection) -> None:
    workspaces_seed = [
        ("workspace-login-service", "login-service", "~/workspace/login-service", "waiting", json.dumps(["Python", "FastAPI"]), "登录接口输入校验", "3 分钟前"),
        ("workspace-dashboard", "dashboard-ui", "~/workspace/dashboard-ui", "pass", json.dumps(["Vue 3", "TypeScript", "Vite"]), "重构数据面板组件", "1 小时前"),
        ("workspace-api", "api-gateway", "~/workspace/api-gateway", "fail", json.dumps(["Node.js", "Express"]), "添加请求限流中间件", "昨天"),
        ("workspace-docs", "docs-generator", "~/workspace/docs-generator", "idle", json.dumps(["Python", "Markdown"]), "从 README 生成 API 文档", "3 天前"),
        ("workspace-data", "data-pipeline", "~/workspace/data-pipeline", "pass", json.dumps(["Python", "Airflow"]), "优化 ETL 调度逻辑", "2 天前"),
        ("workspace-cli", "cli-tools", "~/workspace/cli-tools", "idle", json.dumps(["Go"]), "添加 JSON 格式化子命令", "5 天前"),
        ("workspace-mobile", "mobile-app", "~/workspace/mobile-app", "idle", json.dumps(["React Native"]), "升级导航库版本", "1 周前"),
    ]
    connection.executemany(
        "INSERT OR IGNORE INTO workspaces (id, name, root_path, status, tags_json, last_task, time_ago) VALUES (?, ?, ?, ?, ?, ?, ?)",
        workspaces_seed,
    )

    sessions_seed = [
        ("session-login-validation", "workspace-login-service", "登录接口校验", "awaiting_approval"),
        ("session-utils", "workspace-login-service", "重构 utils.py", "running"),
        ("session-pagination", "workspace-login-service", "修复分页 bug", "completed"),
        ("session-logging", "workspace-login-service", "添加日志模块", "completed"),
        ("session-migration", "workspace-login-service", "数据库迁移脚本", "completed"),
    ]
    connection.executemany(
        "INSERT OR IGNORE INTO sessions (id, workspace_id, title, status) VALUES (?, ?, ?, ?)",
        sessions_seed,
    )

    plan_json = json.dumps([
        {"id": "read", "label": "读取 login.py 源码", "status": "completed"},
        {"id": "analyse", "label": "分析现有登录接口", "status": "completed"},
        {"id": "diff", "label": "生成输入校验 Diff", "status": "current"},
        {"id": "apply", "label": "写入文件", "status": "upcoming"},
        {"id": "test", "label": "运行相关测试", "status": "upcoming"},
    ])
    tool_calls_json = json.dumps([
        {"id": "tool-read-login", "toolName": "read_file", "target": "login.py", "status": "ok", "duration": "42ms", "detail": ["1  def login(username, password):", "2      if not username or not password:", "3          return {\"error\": \"Missing credentials\"}", "4      user = db.query(username)", "5      return {\"token\": generate_token(user)}"]},
        {"id": "tool-search-tests", "toolName": "search_files", "target": "test_login.py · 3 matches", "status": "ok", "duration": "38ms", "detail": ["test_login_empty_credentials (L12)", "test_login_valid_user (L20)", "test_login_wrong_password (L28)"]},
        {"id": "tool-generate-diff", "toolName": "generate_diff", "target": "login.py · +6 -2 · 等待审批", "status": "pending", "duration": "~120ms", "detail": ["- def login(username, password):", "+ def login(username: str, password: str) -> dict:", "+     if not isinstance(username, str) or len(username) > 64:", "+         return {\"error\": \"Invalid username\"}", "+     username = username.strip().lower()"]},
        {"id": "tool-run-tests", "toolName": "run_test", "target": "test_login.py · 等待写入后执行", "status": "idle", "duration": "—", "detail": ["等待批准修改后运行", "$ pytest test_login.py -v"]},
    ])
    changeset_status = "pending"
    verification_lines_json = json.dumps(["等待批准修改后运行"])
    connection.execute(
        """INSERT OR IGNORE INTO tasks (id, session_id, workspace_id, title, state, plan_json, tool_calls_json, model_output, changeset_status, verification_status, verification_command, verification_lines_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("task-login-validation", "session-login-validation", "workspace-login-service", "为 login.py 的登录接口增加输入校验，并运行相关测试", "awaiting_approval", plan_json, tool_calls_json, "已读取 login.py 并分析登录接口。当前实现缺少类型检查、长度校验和输入清洗。Diff 已生成，等待你审批后写入文件并运行测试。", changeset_status, "pending", "$ pytest test_login.py -v", verification_lines_json),
    )

    history_seed_tasks = [
        ("history-task-1", "workspace-login-service", "waiting", "为 login.py 的登录接口增加输入校验，并运行相关测试", "已读取 login.py，分析现有登录接口。当前实现缺少类型检查、长度校验和输入清洗。Diff 已生成，等待你审批后写入文件并运行测试。", "今天 14:32", "3 分钟前", 4),
        ("history-task-2", "workspace-login-service", "done", "重构 utils.py 中的日期格式化函数", "将分散的日期格式化逻辑统一为 format_date() 工具函数，支持 ISO 和本地化两种模式。已更新 3 处调用方。", "今天 13:18", "5 分钟", 12),
        ("history-task-3", "workspace-login-service", "fail", "为 login.py 添加 rate limiting 中间件", "尝试引入 slowapi 库实现请求限流，但 requirements.txt 中缺少依赖且 pip install 在沙箱中被拒绝。任务终止。", "今天 11:45", "2 分钟", 6),
        ("history-task-4", "workspace-login-service", "done", "修复用户列表分页偏移量计算 bug", "分页参数 offset 在第一页时错误地设为 1 而非 0，导致跳过首条记录。已修复并补充边界测试。", "昨天 16:20", "8 分钟", 9),
        ("history-task-5", "workspace-login-service", "done", "添加结构化日志模块", "引入 logging 配置，统一所有模块的日志输出格式为 JSON，包含 request_id、timestamp 和 level 字段。", "昨天 14:05", "3 分钟", 7),
        ("history-task-6", "workspace-login-service", "fail", "生成数据库迁移脚本", "尝试从 SQLAlchemy model 自动生成 Alembic migration，但检测到数据库连接配置缺失，无法完成。", "7 月 18 日", "4 分钟", 5),
        ("history-task-7", "workspace-login-service", "done", "初始化项目结构和 config.yaml", "创建基础目录结构、配置文件和入口脚本。设置 FastAPI 应用骨架。", "7 月 17 日", "2 分钟", 5),
        ("history-task-8", "workspace-login-service", "cancelled", "添加 OAuth2 第三方登录", "用户主动取消。Agent 仅完成了需求分析，未进入实现阶段。", "7 月 17 日", "1 分钟", 2),
    ]
    for task in history_seed_tasks:
        files_json = "[]"
        test_result_json = json.dumps({"badge": "none", "text": "未运行"})
        detail_json = "{}"
        connection.execute(
            "INSERT OR IGNORE INTO task_history (id, workspace_id, status, title, summary, time, duration, tool_count, files_json, test_result_json, detail_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (*task, files_json, test_result_json, detail_json),
        )

    events_seed = [
        ("task-login-validation", 1, "task.created", json.dumps({"taskId": "task-login-validation"}), "2026-07-23T09:00:00"),
        ("task-login-validation", 2, "task.planning", json.dumps({"plan": ["read login.py", "analyze interface"]}), "2026-07-23T09:00:05"),
        ("task-login-validation", 3, "task.reading", json.dumps({"files": ["login.py", "test_login.py"]}), "2026-07-23T09:00:08"),
        ("task-login-validation", 4, "task.generating_diff", json.dumps({"target": "login.py", "additions": 6, "deletions": 2}), "2026-07-23T09:00:15"),
        ("task-login-validation", 5, "task.awaiting_approval", json.dumps({"message": "等待审批"}), "2026-07-23T09:00:20"),
    ]
    connection.executemany(
        "INSERT OR IGNORE INTO task_events (task_id, sequence, event_type, payload_json, created_at) VALUES (?, ?, ?, ?, ?)",
        events_seed,
    )
