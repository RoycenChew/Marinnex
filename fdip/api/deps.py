"""Shared state and the two authentication paths.

The UI authenticates with an httpOnly session cookie; the API authenticates with
a bearer key. They are deliberately separate dependencies rather than one that
accepts either: a cookie is sent automatically by the browser and is therefore
vulnerable to CSRF, while a bearer key is not, and conflating them would extend
the cookie's exposure to the pipeline routes.

`Principal` is what every route gets: a project and how it was proved.
"""
from __future__ import annotations

import time
from collections.abc import Iterator
from dataclasses import dataclass, field

from fastapi import Depends, Query, Request
from sqlalchemy import Engine
from sqlalchemy.engine import Connection

from fdip.adapters import keys as key_tools
from fdip.adapters.db import create_db_engine
from fdip.adapters.repository import GlobalRepository, ProjectRepository
from fdip.adapters.storage import BlobStore
from fdip.api import problems
from fdip.config import Settings
from fdip.config import settings as load_settings


@dataclass
class AppState:
    settings: Settings
    engine: Engine
    blobs: BlobStore
    rate_limiter: RateLimiter = field(default_factory=lambda: RateLimiter())

    @staticmethod
    def build(settings: Settings | None = None) -> AppState:
        resolved = settings or load_settings()
        resolved.ensure_dirs()
        return AppState(
            settings=resolved,
            engine=create_db_engine(resolved.db_url),
            blobs=BlobStore(resolved.blob_dir),
        )


class RateLimiter:
    """A fixed-window counter per key, in process.

    In process because there is one API process in the MVP and a shared limiter
    needs Redis, which 8.1 says not to build yet. The consequence is honest and
    worth writing down: two API processes would each allow the full limit.
    """

    def __init__(self) -> None:
        self._windows: dict[str, tuple[int, int]] = {}

    def check(self, key: str, limit: int) -> int:
        """Returns the remaining allowance, or raises `Problem` at 429."""
        window = int(time.time() // 60)
        current_window, count = self._windows.get(key, (window, 0))
        if current_window != window:
            current_window, count = window, 0
        if count >= limit:
            raise problems.rate_limited(60 - int(time.time() % 60))
        self._windows[key] = (current_window, count + 1)
        return limit - count - 1


def client_ip(request: Request) -> str:
    """The caller's address, trusting one proxy hop.

    Behind Caddy every request arrives from the container network, so without
    `X-Forwarded-For` a per-IP limit would be one global limit. Only the first
    entry is read, and only the first: the rest are attacker-supplied.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return getattr(getattr(request, "client", None), "host", "") or "unknown"


def limit_by_ip(request: Request, state: AppState, bucket: str,
                limit: int) -> None:
    """Rate limit one route per calling address.

    Per IP rather than per account for login, because an attacker trying one
    password against a thousand accounts never trips a per-account limit.
    """
    state.rate_limiter.check("%s:%s" % (bucket, client_ip(request)), limit)


@dataclass(frozen=True)
class Principal:
    project_id: str
    actor: str
    """`usr_...` for a session, `key_...` for an API key. Goes in audit rows."""
    via: str
    user_id: str | None = None
    api_key_id: str | None = None
    api_key_mode: str | None = None
    allowed_schema_versions: tuple[tuple[str, int], ...] = ()

    def may_use(self, schema_id: str, version: int) -> bool:
        """A key with an empty allow-list may use any version of its project.

        The restriction is opt-in because the common case is one schema, and a
        key that silently cannot call anything is a support ticket.
        """
        if not self.allowed_schema_versions:
            return True
        return (schema_id, version) in self.allowed_schema_versions


def get_state(request: Request) -> AppState:
    state = getattr(request.app.state, "fdip", None)
    if state is None:  # pragma: no cover - the app always sets it on startup
        raise problems.Problem(500, "internal", "application state is missing")
    assert isinstance(state, AppState)
    return state


def get_settings(state: AppState = Depends(get_state)) -> Settings:
    return state.settings


def db_connection(state: AppState = Depends(get_state)) -> Iterator[Connection]:
    """One transaction per request, committed on a clean return.

    Per request rather than per operation so that a route which writes a document
    and its job cannot leave one without the other.

    Commit-as-you-go rather than a `begin()` block, so that a route which then
    does long-running work can release the write lock first. SQLite allows one
    writer: `POST /extract?wait=30` holds this connection, and the pipeline it
    runs opens its own, so without an early commit the request deadlocks against
    itself and the job fails with `database is locked`. `release_write_lock`
    below is how a route asks for that.
    """
    with state.engine.connect() as connection:
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def release_write_lock(connection: Connection) -> None:
    """Commit what the request has written so another connection may write.

    Called only by a route that is about to do something slow. It means the
    request is no longer atomic from that point on, which is the right trade for
    `POST /extract?wait=`: the document and job rows are what the client is
    promised, and they are already written.
    """
    connection.commit()


PROJECT_ID_QUERY = Query(
    None,
    description=(
        "Which project to act in. Defaults to the caller's first project. A "
        "project id that is not yours returns 404, not 403."
    ),
)


def session_principal(
    request: Request,
    project_id: str | None = PROJECT_ID_QUERY,
    state: AppState = Depends(get_state),
    connection: Connection = Depends(db_connection),
) -> Principal:
    """The UI path: cookie, then `?project_id=`, defaulting to the first project.

    `project_id` is a declared parameter rather than something read off the raw
    request, so it appears in `openapi.json` for every route that depends on this
    and the generated client will accept it. It used to be pulled from
    `request.query_params`, which worked but was invisible to the schema.
    """
    token = request.cookies.get(key_tools.SESSION_COOKIE)
    if not token:
        raise problems.unauthenticated("no session cookie; log in first")
    user_id = key_tools.read_session(state.settings.session_secret, token)
    if not user_id:
        raise problems.unauthenticated("the session has expired or is invalid")

    repo = GlobalRepository(connection)
    user = repo.user(user_id)
    if user is None or not user["is_active"]:
        raise problems.unauthenticated("the account no longer exists")
    owned = repo.projects_for(user_id)
    if not owned:
        raise problems.forbidden("this account has no project")

    requested = project_id
    if requested:
        match = next((p for p in owned if p["id"] == requested), None)
        if match is None:
            # 404, not 403: see `problems.not_found`.
            raise problems.not_found("project")
        project_id = str(match["id"])
    else:
        project_id = str(owned[0]["id"])
    return Principal(
        project_id=project_id, actor=str(user["id"]), via="session",
        user_id=str(user["id"]),
    )


def key_principal(
    request: Request,
    state: AppState = Depends(get_state),
    connection: Connection = Depends(db_connection),
) -> Principal:
    """The pipeline path: `Authorization: Bearer fdip_live_...` or `fdip_test_...`."""
    header = request.headers.get("authorization", "")
    scheme, _, presented = header.partition(" ")
    if scheme.lower() != "bearer" or not presented.strip():
        raise problems.unauthenticated("an Authorization: Bearer key is required")
    presented = presented.strip()
    if key_tools.key_mode(presented) is None:
        raise problems.unauthenticated("the key is not an FDIP key")

    repo = GlobalRepository(connection)
    row = repo.api_key_by_prefix(key_tools.key_prefix(presented))
    # One failure message for an unknown prefix, a wrong secret, a revoked key
    # and an expired key: which of the four it was is not the caller's business.
    if row is None or not key_tools.verify_key(
        presented, str(row["key_hash"]), state.settings.key_pepper
    ):
        raise problems.unauthenticated("the key is not valid")
    if row["revoked_at"] is not None:
        raise problems.unauthenticated("the key is not valid")
    if key_tools.is_expired(row["expires_at"]):
        raise problems.unauthenticated("the key is not valid")

    allowed = tuple(
        (str(entry["schema_id"]), int(entry["version"]))
        for entry in (row["schema_versions"] or [])
        if isinstance(entry, dict) and "schema_id" in entry
    )
    state.rate_limiter.check(
        "key:" + str(row["id"]), int(row["rate_limit_per_minute"] or 60)
    )
    return Principal(
        project_id=str(row["project_id"]), actor=str(row["id"]), via="api_key",
        api_key_id=str(row["id"]), api_key_mode=str(row["mode"]),
        allowed_schema_versions=allowed,
    )


def repository(
    principal: Principal = Depends(session_principal),
    connection: Connection = Depends(db_connection),
) -> ProjectRepository:
    return ProjectRepository(connection, principal.project_id)


def key_repository(
    principal: Principal = Depends(key_principal),
    connection: Connection = Depends(db_connection),
) -> ProjectRepository:
    return ProjectRepository(connection, principal.project_id)


def global_repository(
    connection: Connection = Depends(db_connection),
) -> GlobalRepository:
    return GlobalRepository(connection)


def effective_provider_mode(settings: Settings, principal: Principal) -> str:
    """A test key may never reach the live provider.

    That is the point of having two key schemes: a customer integrating against
    `fdip_test_` must be unable to spend money, whatever the server is configured
    for.
    """
    if principal.api_key_mode == "test" and settings.provider_mode == "live":
        return "mock"
    return settings.provider_mode


def any_principal(request: Request,
                  project_id: str | None = PROJECT_ID_QUERY,
                  state: AppState = Depends(get_state),
                  connection: Connection = Depends(db_connection)) -> Principal:
    """For `GET /extractions/{id}`, which 3.7 allows either way.

    The bearer key is tried first so that an API client with a stale cookie in
    the same browser still authenticates as itself.
    """
    if request.headers.get("authorization"):
        return key_principal(request, state=state, connection=connection)
    # Keyword arguments: this is a direct call, not a FastAPI resolution, and the
    # parameter order changed when project_id became a declared query parameter.
    return session_principal(
        request, project_id=project_id, state=state, connection=connection,
    )


__all__ = [
    "AppState",
    "Principal",
    "RateLimiter",
    "any_principal",
    "db_connection",
    "effective_provider_mode",
    "get_settings",
    "get_state",
    "global_repository",
    "key_principal",
    "key_repository",
    "release_write_lock",
    "repository",
    "session_principal",
]
