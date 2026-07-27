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
    verification_lines_json TEXT NOT NULL DEFAULT '[]',
    kind TEXT NOT NULL DEFAULT 'mock',
    target_file TEXT NOT NULL DEFAULT '',
    changeset_id TEXT NOT NULL DEFAULT '',
    verification_detail TEXT NOT NULL DEFAULT ''
);

-- Phase 1: server-generated, immutable, versioned ChangeSets.
CREATE TABLE IF NOT EXISTS changesets (
    id TEXT PRIMARY KEY,
    task_id TEXT NOT NULL,
    workspace_id TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    logical_relative_path TEXT NOT NULL,
    base_sha256 TEXT NOT NULL,
    proposed_sha256 TEXT NOT NULL,
    diff_hash TEXT NOT NULL,
    policy_version TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    additions INTEGER NOT NULL DEFAULT 0,
    deletions INTEGER NOT NULL DEFAULT 0,
    before_json TEXT NOT NULL DEFAULT '[]',
    after_json TEXT NOT NULL DEFAULT '[]',
    base_text TEXT NOT NULL DEFAULT '',
    proposed_text TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    expires_at TEXT NOT NULL DEFAULT ''
);

-- Phase 1: version-bound approval records with idempotency.
CREATE TABLE IF NOT EXISTS approvals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    changeset_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    revision INTEGER NOT NULL,
    diff_hash TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    outcome TEXT NOT NULL DEFAULT 'pending',
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT '',
    UNIQUE(idempotency_key)
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


def _column_names(connection: sqlite3.Connection, table: str) -> set[str]:
    rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
    return {row["name"] for row in rows}


def run_migrations(connection: sqlite3.Connection) -> None:
    """Idempotently upgrade a pre-existing Phase 0.5 database to the Phase 1 schema.

    Fresh databases already receive the new columns/tables from SCHEMA_SQL; this
    only backfills columns that older databases are missing. `ALTER TABLE ADD
    COLUMN` with a DEFAULT marks every existing (mock) task row as kind='mock',
    which satisfies the "Mock 隔离" safety invariant.
    """
    task_columns = _column_names(connection, "tasks")
    changeset_columns = _column_names(connection, "changesets")
    # (column_name, target_table, ddl) — keyed by the table that owns the column
    # so the existence check queries the correct table.
    migrations = {
        "kind": ("tasks", "ALTER TABLE tasks ADD COLUMN kind TEXT NOT NULL DEFAULT 'mock'"),
        "target_file": ("tasks", "ALTER TABLE tasks ADD COLUMN target_file TEXT NOT NULL DEFAULT ''"),
        "changeset_id": ("tasks", "ALTER TABLE tasks ADD COLUMN changeset_id TEXT NOT NULL DEFAULT ''"),
        "verification_detail": ("tasks", "ALTER TABLE tasks ADD COLUMN verification_detail TEXT NOT NULL DEFAULT ''"),
        "expires_at": ("changesets", "ALTER TABLE changesets ADD COLUMN expires_at TEXT NOT NULL DEFAULT ''"),
    }
    for column, (table, statement) in migrations.items():
        existing = task_columns if table == "tasks" else changeset_columns
        if column not in existing:
            connection.execute(statement)


def initialize_database(database_path: Optional[Path] = None) -> sqlite3.Connection:
    if database_path is None:
        # 回退路径同样基于本文件位置解析为绝对路径，避免依赖启动目录。
        database_path = Path(__file__).resolve().parent.parent.parent / "data" / "lightcode.db"
    database_path.parent.mkdir(parents=True, exist_ok=True)

    connection = sqlite3.connect(str(database_path), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    # WAL 提升并发读吞吐并降低写锁等待；busy_timeout 避免多连接短竞态下抛
    # "database is locked"。两者均为对既有 schema/迁移语义透明的引擎级调优。
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=5000")
    connection.executescript(SCHEMA_SQL)
    run_migrations(connection)
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

    history_detail_1 = json.dumps({
        "plan": [{"label": "读取 login.py 源码", "state": "done"}, {"label": "分析现有登录接口", "state": "done"}, {"label": "生成输入校验 Diff", "state": "waiting"}, {"label": "写入文件", "state": "pending"}, {"label": "运行相关测试", "state": "pending"}],
        "toolCalls": [{"icon": "📖", "name": "read_file", "args": "login.py", "ok": True}, {"icon": "📖", "name": "read_file", "args": "test_login.py", "ok": True}, {"icon": "🔍", "name": "search_files", "args": "test_login.py · 3 matches", "ok": True}, {"icon": "📝", "name": "generate_diff", "args": "login.py", "ok": True}],
        "files": [{"name": "login.py", "additions": 6, "deletions": 2, "diff": "- def login(username, password):\n+ def login(username: str, password: str) -> dict:\n+     if not isinstance(username, str) or len(username) > 64:\n+         return {\"error\": \"Invalid username\"}\n+     username = username.strip().lower()"}],
        "approval": {"status": "none", "text": "等待审批", "time": "—"},
        "test": {"command": "pytest test_login.py -v", "result": "none", "detail": "等待批准修改后运行"},
    })
    history_detail_2 = json.dumps({
        "plan": [{"label": "分析 utils.py 中所有日期格式化调用", "state": "done"}, {"label": "设计统一的 format_date() 接口", "state": "done"}, {"label": "重构并更新调用方", "state": "done"}, {"label": "编写并运行测试", "state": "done"}],
        "toolCalls": [{"icon": "📖", "name": "read_file", "args": "utils.py", "ok": True}, {"icon": "📖", "name": "read_file", "args": "login.py", "ok": True}, {"icon": "📖", "name": "read_file", "args": "test_utils.py", "ok": True}, {"icon": "🔍", "name": "search_files", "args": "date_format|strftime", "ok": True}, {"icon": "📝", "name": "generate_diff", "args": "utils.py", "ok": True}, {"icon": "📝", "name": "generate_diff", "args": "login.py", "ok": True}, {"icon": "📝", "name": "generate_diff", "args": "test_utils.py", "ok": True}, {"icon": "✍️", "name": "write_file", "args": "utils.py", "ok": True}, {"icon": "✍️", "name": "write_file", "args": "login.py", "ok": True}, {"icon": "✍️", "name": "write_file", "args": "test_utils.py", "ok": True}, {"icon": "🧪", "name": "run_test", "args": "test_utils.py", "ok": True}, {"icon": "📊", "name": "summarize", "args": "task complete", "ok": True}],
        "files": [{"name": "utils.py", "additions": 18, "deletions": 32, "diff": "- def parse_date(s):\n-     return datetime.strptime(s, \"%Y-%m-%d\")\n- def format_iso(dt):\n-     return dt.isoformat()\n+ def format_date(dt, mode=\"iso\"):\n+     if mode == \"iso\":\n+         return dt.isoformat()\n+     return dt.strftime(\"%Y年%m月%d日\")"}, {"name": "login.py", "additions": 2, "deletions": 4, "diff": "- from utils import parse_date, format_iso\n+ from utils import format_date"}, {"name": "test_utils.py", "additions": 14, "deletions": 0, "diff": "+ def test_format_date_iso():\n+     assert format_date(dt, \"iso\") == \"2026-07-20T00:00:00\"\n+ def test_format_date_local():\n+     assert format_date(dt, \"local\") == \"2026年07月20日\""}],
        "approval": {"status": "approved", "text": "已批准写入", "time": "今天 13:16"},
        "test": {"command": "pytest test_utils.py -v", "result": "pass", "detail": "6 passed · 0 failed · 0.4s"},
    })
    history_detail_3 = json.dumps({
        "plan": [{"label": "读取 login.py 和 requirements.txt", "state": "done"}, {"label": "搜索现有限流实现", "state": "done"}, {"label": "生成 rate limiting Diff", "state": "done"}, {"label": "安装 slowapi 依赖", "state": "fail"}, {"label": "运行测试验证", "state": "pending"}],
        "toolCalls": [{"icon": "📖", "name": "read_file", "args": "login.py", "ok": True}, {"icon": "📖", "name": "read_file", "args": "requirements.txt", "ok": True}, {"icon": "🔍", "name": "search_files", "args": "rate.limit|throttle", "ok": True}, {"icon": "📝", "name": "generate_diff", "args": "login.py", "ok": True}, {"icon": "🧪", "name": "run_test", "args": "test_login.py", "ok": False}, {"icon": "⚙️", "name": "exec", "args": "pip install slowapi", "ok": False}],
        "files": [{"name": "login.py", "additions": 8, "deletions": 0, "diff": "+ from slowapi import Limiter\n+ from slowapi.util import get_remote_address\n+ limiter = Limiter(key_func=get_remote_address)\n+ @app.route(\"/login\", methods=[\"POST\"])\n+ @limiter.limit(\"5/minute\")"}],
        "approval": {"status": "none", "text": "未进入审批", "time": "—"},
        "test": {"command": "pytest test_login.py -v", "result": "fail", "detail": "ImportError: No module named 'slowapi'"},
        "failReason": "依赖缺失",
        "failDetail": "slowapi 未安装，沙箱安全策略禁止 pip install。Agent 未写入任何文件。",
        "rejectedCmd": "pip install slowapi",
    })
    history_detail_4 = json.dumps({
        "plan": [{"label": "读取用户列表分页逻辑", "state": "done"}, {"label": "定位 offset 计算 bug", "state": "done"}, {"label": "修复并补充边界测试", "state": "done"}],
        "toolCalls": [{"icon": "📖", "name": "read_file", "args": "login.py", "ok": True}, {"icon": "📖", "name": "read_file", "args": "test_login.py", "ok": True}, {"icon": "🔍", "name": "search_files", "args": "offset|pagination", "ok": True}, {"icon": "📝", "name": "generate_diff", "args": "login.py", "ok": True}, {"icon": "📝", "name": "generate_diff", "args": "test_login.py", "ok": True}, {"icon": "✍️", "name": "write_file", "args": "login.py", "ok": True}, {"icon": "✍️", "name": "write_file", "args": "test_login.py", "ok": True}, {"icon": "🧪", "name": "run_test", "args": "test_login.py", "ok": True}, {"icon": "📊", "name": "summarize", "args": "task complete", "ok": True}],
        "files": [{"name": "login.py", "additions": 1, "deletions": 1, "diff": "- offset = page\n+ offset = (page - 1) * per_page"}, {"name": "test_login.py", "additions": 8, "deletions": 0, "diff": "+ def test_pagination_first_page():\n+     resp = client.get(\"/users?page=1&per_page=10\")\n+     assert len(resp.json()[\"items\"]) == 10\n+ def test_pagination_empty():\n+     resp = client.get(\"/users?page=999\")\n+     assert resp.json()[\"items\"] == []"}],
        "approval": {"status": "approved", "text": "已批准写入", "time": "昨天 16:18"},
        "test": {"command": "pytest test_login.py -v", "result": "pass", "detail": "5 passed · 0 failed · 0.3s"},
    })
    history_detail_5 = json.dumps({
        "plan": [{"label": "设计 JSON 日志格式", "state": "done"}, {"label": "创建 logger.py 模块", "state": "done"}, {"label": "集成到 login.py 并测试", "state": "done"}],
        "toolCalls": [{"icon": "📖", "name": "read_file", "args": "login.py", "ok": True}, {"icon": "📖", "name": "read_file", "args": "config.yaml", "ok": True}, {"icon": "📝", "name": "generate_diff", "args": "logger.py", "ok": True}, {"icon": "📝", "name": "generate_diff", "args": "login.py", "ok": True}, {"icon": "✍️", "name": "write_file", "args": "logger.py", "ok": True}, {"icon": "✍️", "name": "write_file", "args": "login.py", "ok": True}, {"icon": "🧪", "name": "run_test", "args": "test_logger.py", "ok": True}],
        "files": [{"name": "logger.py", "additions": 28, "deletions": 0, "diff": "+ import logging, json, uuid\n+ class JSONFormatter(logging.Formatter):\n+     def format(self, record):\n+         return json.dumps({\"timestamp\": self.formatTime(record), \"level\": record.levelname, \"request_id\": getattr(record, \"request_id\", \"-\"), \"message\": record.getMessage()})"}, {"name": "login.py", "additions": 3, "deletions": 0, "diff": "+ from logger import get_logger\n+ logger = get_logger(__name__)"}],
        "approval": {"status": "approved", "text": "已批准写入", "time": "昨天 14:03"},
        "test": {"command": "pytest test_logger.py -v", "result": "pass", "detail": "3 passed · 0 failed · 0.2s"},
    })
    history_detail_6 = json.dumps({
        "plan": [{"label": "读取 SQLAlchemy model 定义", "state": "done"}, {"label": "检查 Alembic 配置", "state": "done"}, {"label": "读取数据库连接配置", "state": "fail"}, {"label": "生成 migration 文件", "state": "pending"}],
        "toolCalls": [{"icon": "📖", "name": "read_file", "args": "models.py", "ok": True}, {"icon": "📖", "name": "read_file", "args": "alembic.ini", "ok": True}, {"icon": "🔍", "name": "search_files", "args": "DATABASE_URL|sqlalchemy", "ok": True}, {"icon": "⚙️", "name": "exec", "args": "alembic revision --autogenerate", "ok": False}, {"icon": "⚙️", "name": "exec", "args": "echo $DATABASE_URL", "ok": False}],
        "files": [{"name": "migrations/001.py", "additions": 0, "deletions": 0, "diff": "# 未生成 — 迁移失败"}],
        "approval": {"status": "none", "text": "未进入审批", "time": "—"},
        "test": {"command": "pytest", "result": "none", "detail": "迁移未生成，跳过测试"},
        "failReason": "连接缺失",
        "failDetail": "DATABASE_URL 环境变量未配置，Alembic 无法连接数据库。Agent 未写入任何迁移文件。",
        "rejectedCmd": "alembic revision --autogenerate -m \"init\"",
    })
    history_detail_7 = json.dumps({
        "plan": [{"label": "创建目录结构", "state": "done"}, {"label": "编写 config.yaml", "state": "done"}, {"label": "创建 main.py 入口", "state": "done"}],
        "toolCalls": [{"icon": "✍️", "name": "write_file", "args": "config.yaml", "ok": True}, {"icon": "✍️", "name": "write_file", "args": "main.py", "ok": True}, {"icon": "✍️", "name": "write_file", "args": "requirements.txt", "ok": True}, {"icon": "⚙️", "name": "exec", "args": "mkdir -p app tests", "ok": True}, {"icon": "🧪", "name": "run_test", "args": "test_main.py", "ok": True}],
        "files": [{"name": "config.yaml", "additions": 15, "deletions": 0, "diff": "+ app:\n+   name: login-service\n+   port: 8000\n+   debug: true"}, {"name": "main.py", "additions": 22, "deletions": 0, "diff": "+ from fastapi import FastAPI\n+ app = FastAPI()\n+ @app.get(\"/health\")\n+ async def health():\n+     return {\"status\": \"ok\"}"}, {"name": "requirements.txt", "additions": 6, "deletions": 0, "diff": "+ fastapi\n+ uvicorn\n+ pydantic\n+ sqlalchemy\n+ alembic\n+ pytest"}],
        "approval": {"status": "approved", "text": "首次创建，无需审批", "time": "7 月 17 日"},
        "test": {"command": "pytest test_main.py -v", "result": "pass", "detail": "2 passed · 0 failed · 0.1s"},
    })
    history_detail_8 = json.dumps({
        "plan": [{"label": "调研 OAuth2 provider 集成方式", "state": "done"}, {"label": "读取现有登录接口", "state": "done"}, {"label": "设计 OAuth2 回调流程", "state": "pending"}, {"label": "生成 Diff", "state": "pending"}],
        "toolCalls": [{"icon": "🔍", "name": "search_files", "args": "oauth|authlib", "ok": True}, {"icon": "📖", "name": "read_file", "args": "login.py", "ok": True}],
        "files": [],
        "approval": {"status": "none", "text": "未进入审批", "time": "—"},
        "test": {"command": "—", "result": "none", "detail": "任务已取消"},
        "cancelInfo": {"stage": "需求分析完成后", "detail": "Agent 刚完成 OAuth2 provider 调研，正准备生成 Diff 时被用户终止。"},
    })

    history_details = [
        history_detail_1, history_detail_2, history_detail_3, history_detail_4,
        history_detail_5, history_detail_6, history_detail_7, history_detail_8,
    ]
    history_files = [
        json.dumps([{"name": "login.py", "additions": 6, "deletions": 2}]),
        json.dumps([{"name": "utils.py", "additions": 18, "deletions": 32}, {"name": "login.py", "additions": 2, "deletions": 4}, {"name": "test_utils.py", "additions": 14, "deletions": 0}]),
        json.dumps([{"name": "login.py", "additions": 8, "deletions": 0}]),
        json.dumps([{"name": "login.py", "additions": 1, "deletions": 1}, {"name": "test_login.py", "additions": 8, "deletions": 0}]),
        json.dumps([{"name": "logger.py", "additions": 28, "deletions": 0}, {"name": "login.py", "additions": 3, "deletions": 0}]),
        json.dumps([{"name": "migrations/001.py", "additions": 0, "deletions": 0}]),
        json.dumps([{"name": "config.yaml", "additions": 15, "deletions": 0}, {"name": "main.py", "additions": 22, "deletions": 0}, {"name": "requirements.txt", "additions": 6, "deletions": 0}]),
        json.dumps([]),
    ]
    history_test_results = [
        json.dumps({"badge": "none", "text": "未运行"}),
        json.dumps({"badge": "pass", "text": "6 passed"}),
        json.dumps({"badge": "fail", "text": "1 failed"}),
        json.dumps({"badge": "pass", "text": "5 passed"}),
        json.dumps({"badge": "pass", "text": "3 passed"}),
        json.dumps({"badge": "none", "text": "未运行"}),
        json.dumps({"badge": "pass", "text": "2 passed"}),
        json.dumps({"badge": "none", "text": "未运行"}),
    ]
    history_base_rows = [
        ("history-task-1", "workspace-login-service", "waiting", "为 login.py 的登录接口增加输入校验，并运行相关测试", "已读取 login.py，分析现有登录接口。当前实现缺少类型检查、长度校验和输入清洗。Diff 已生成，等待你审批后写入文件并运行测试。", "今天 14:32", "3 分钟前", 4),
        ("history-task-2", "workspace-login-service", "done", "重构 utils.py 中的日期格式化函数", "将分散的日期格式化逻辑统一为 format_date() 工具函数，支持 ISO 和本地化两种模式。已更新 3 处调用方。", "今天 13:18", "5 分钟", 12),
        ("history-task-3", "workspace-login-service", "fail", "为 login.py 添加 rate limiting 中间件", "尝试引入 slowapi 库实现请求限流，但 requirements.txt 中缺少依赖且 pip install 在沙箱中被拒绝。任务终止。", "今天 11:45", "2 分钟", 6),
        ("history-task-4", "workspace-login-service", "done", "修复用户列表分页偏移量计算 bug", "分页参数 offset 在第一页时错误地设为 1 而非 0，导致跳过首条记录。已修复并补充边界测试。", "昨天 16:20", "8 分钟", 9),
        ("history-task-5", "workspace-login-service", "done", "添加结构化日志模块", "引入 logging 配置，统一所有模块的日志输出格式为 JSON，包含 request_id、timestamp 和 level 字段。", "昨天 14:05", "3 分钟", 7),
        ("history-task-6", "workspace-login-service", "fail", "生成数据库迁移脚本", "尝试从 SQLAlchemy model 自动生成 Alembic migration，但检测到数据库连接配置缺失，无法完成。", "7 月 18 日", "4 分钟", 5),
        ("history-task-7", "workspace-login-service", "done", "初始化项目结构和 config.yaml", "创建基础目录结构、配置文件和入口脚本。设置 FastAPI 应用骨架。", "7 月 17 日", "2 分钟", 5),
        ("history-task-8", "workspace-login-service", "cancelled", "添加 OAuth2 第三方登录", "用户主动取消。Agent 仅完成了需求分析，未进入实现阶段。", "7 月 17 日", "1 分钟", 2),
    ]
    for i, task in enumerate(history_base_rows):
        connection.execute(
            "INSERT OR IGNORE INTO task_history (id, workspace_id, status, title, summary, time, duration, tool_count, files_json, test_result_json, detail_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (*task, history_files[i], history_test_results[i], history_details[i]),
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
