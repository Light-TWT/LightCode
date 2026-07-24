import os
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router as api_router
from app.db.database import initialize_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
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
    yield
    connection.close()


app = FastAPI(title="LightCode Local Runtime", version="0.1.0", lifespan=lifespan)
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
