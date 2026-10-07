"""The FastAPI application.

Everything lives under `/v1`, so a future `/v2` can exist beside it rather than
breaking the UI. CORS is restricted to `FDIP_CORS_ORIGINS` with credentials
allowed, which is required for the session cookie: a wildcard origin and
`allow_credentials=True` is rejected by browsers, so the origin list is not
optional.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from fdip import __version__
from fdip.adapters.db import create_all
from fdip.adapters.seed import seed
from fdip.api import problems
from fdip.api.deps import AppState
from fdip.api.routers import admin, auth, documents, extractions, pipeline, schemas
from fdip.config import Settings, load_settings
from fdip.config import settings as load_cached
from fdip.observability import configure_logging

API_PREFIX = "/v1"

logger = logging.getLogger("fdip")


def create_app(settings: Settings | None = None,
               create_schema: bool = True) -> FastAPI:
    configure_logging()
    # Resolved once here, because the CORS middleware needs the origin list at
    # construction time while everything else is built in the lifespan.
    resolved = settings or load_settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        state = AppState.build(resolved)
        if create_schema:
            # Convenient for a first local run and for tests. A deployment runs
            # `alembic upgrade head`; `tests/test_migration.py` proves the two
            # produce the same schema.
            create_all(state.engine)
        seed(state.engine, state.settings)
        application.state.fdip = state
        logger.info("started mode=%s model=%s thinking=%s",
                    state.settings.provider_mode, state.settings.model,
                    state.settings.extract_thinking)
        try:
            yield
        finally:
            state.engine.dispose()

    app = FastAPI(
        title="FDIP",
        version=__version__,
        description=(
            "Financial Document Intelligent Processing. Upload a document, poll "
            "until its status is terminal, read the extraction with evidence "
            "boxes. Errors are RFC 9457 problem details with a `code` field; "
            "branch on `code`, never on `detail`."
        ),
        lifespan=lifespan,
        openapi_url=API_PREFIX + "/openapi.json",
        docs_url=API_PREFIX + "/docs",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(resolved.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "Idempotency-Key"],
        expose_headers=["X-Page-Dpi"],
    )

    app.add_exception_handler(problems.Problem, problems.problem_handler)
    app.add_exception_handler(HTTPException, problems.problem_handler)

    root = APIRouter(prefix=API_PREFIX)
    for module in (auth, schemas, documents, extractions, pipeline, admin):
        root.include_router(module.router)
    app.include_router(root)
    return app


def openapi_document(app: FastAPI | None = None) -> dict[str, Any]:
    """The OpenAPI document, for `fdip/openapi.json` and the staleness test."""
    target = app or create_app(load_settings(env_file=None), create_schema=False)
    return dict(target.openapi())


def _default_app() -> FastAPI:
    """What `uvicorn fdip.api.app:app` serves."""
    return create_app(load_cached())


app = _default_app()

__all__ = ["API_PREFIX", "app", "create_app", "openapi_document"]
