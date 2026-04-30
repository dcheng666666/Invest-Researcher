import logging
import os

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from backend.api.routes import router
from backend.config import settings
from backend.repositories import user_repository
from backend.repositories.symbol_repository import initialize as initialize_symbol_store

_LOG_LEVEL_NAME = os.environ.get("LOG_LEVEL", "INFO").upper()
_LOG_LEVEL = getattr(logging, _LOG_LEVEL_NAME, None)
if not isinstance(_LOG_LEVEL, int):
    _LOG_LEVEL = logging.INFO
    _LOG_LEVEL_NAME = "INFO"

logging.basicConfig(
    level=_LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger().setLevel(_LOG_LEVEL)

initialize_symbol_store()
_session_override = settings.app_session_secret.strip()
_SESSION_SECRET = (
    _session_override
    if _session_override
    else user_repository.get_or_create_session_secret()
)

app = FastAPI(title="价值投资五步法分析", version="0.1.0")

app.add_middleware(
    SessionMiddleware,
    secret_key=_SESSION_SECRET,
    same_site="lax",
    max_age=60 * 60 * 24 * 7,
)

_origins = settings.cors_origin_list()
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.on_event("startup")
async def on_startup() -> None:
    initialize_symbol_store()


if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level=_LOG_LEVEL_NAME.lower(),
    )
