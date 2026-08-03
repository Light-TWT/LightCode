import os
import sys
import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router as api_router
from app.config.model_provider import load_model_provider_config
from app.db.database import initialize_database
from app.schemas.errors import Phase1Error
from app.security.guard import WorkspaceGuard
from app.services.observability import (
    configure_logging,
    correlation_id_var,
    get_logger,
)
from app.services.phase1 import Phase1Service
from app.workspaces.registry import WorkspaceRegistry

log = get_logger("lightcode.lifespan")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # WP8: install the structured (JSON) logger exactly once at startup.
    configure_logging()

    # 默认数据库路径基于本文件位置解析为绝对路径（<repo>/backend/data/lightcode.db），
    # 不依赖启动命令当前所在目录，避免从 backend/ 启动时落到 backend/backend/data/。
    backend_dir = Path(__file__).resolve().parent.parent
    default_database_path = backend_dir / "data" / "lightcode.db"
    env_database_path = os.environ.get("LIGHTCODE_DATABASE_PATH")
    database_path = Path(env_database_path) if env_database_path else default_database_path
    if not database_path.is_absolute():
        database_path = (backend_dir / database_path).resolve()
    connection = initialize_database(database_path)
    app.state.db = connection

    # Phase 1: load the static workspace registry from server-side config only.
    # 默认配置路径基于 backend/ 目录，同样与启动目录无关。
    default_config_path = backend_dir / "workspaces.json"
    env_config_path = os.environ.get("LIGHTCODE_WORKSPACES_CONFIG")
    config_path = Path(env_config_path) if env_config_path else default_config_path
    if not config_path.is_absolute():
        config_path = (backend_dir / config_path).resolve()
    registry = WorkspaceRegistry.load(config_path)
    app.state.registry = registry
    app.state.guard = WorkspaceGuard(registry)

    # Phase 2 / WP5: snapshot the model provider config once at startup. It is
    # read from backend env vars only and is OFF unless explicitly enabled, so
    # a default deployment has no provider, no key and no outbound capability.
    # Only the status is ever logged — never the key or the base URL.
    model_provider = load_model_provider_config()
    app.state.model_provider = model_provider
    log.info("model provider status resolved", extra={"status": model_provider.status()})

    # Startup crash recovery: reconcile any real task left mid-apply by a
    # previously crashed process (contract §失败和恢复承诺).
    recovery = Phase1Service(connection, registry, app.state.guard).recover_incomplete_tasks()
    if any(v for v in recovery.values()):
        log.warning("startup recovery performed", extra={"recovery": recovery})

    yield
    connection.close()


app = FastAPI(title="LightCode Local Runtime", version="0.1.0", lifespan=lifespan)


@app.middleware("http")
async def correlation_middleware(request: Request, call_next):
    """Assign a per-request correlation id; sync routes re-bind it locally.

    FastAPI runs synchronous endpoints in a threadpool, where the ContextVar set
    here would not propagate, so the id is also stored on ``request.state`` and
    the instrumented sync routes re-apply it via :func:`correlation_id_var.set`.
    """
    cid = uuid.uuid4().hex
    correlation_id_var.set(cid)
    request.state.correlation_id = cid
    try:
        return await call_next(request)
    finally:
        correlation_id_var.set("-")


@app.exception_handler(Phase1Error)
async def phase1_error_handler(request: Request, exc: Phase1Error) -> JSONResponse:
    # 公共错误体只暴露稳定机器码与安全消息，绝不泄露真实根路径或内部堆栈。
    return JSONResponse(
        status_code=exc.http_status,
        content={"code": exc.code, "message": exc.message},
    )


app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "runtime": "mock"}
