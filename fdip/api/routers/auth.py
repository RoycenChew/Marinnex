"""Register, log in, log out, who am I.

The session is a signed cookie rather than a server-side table. It costs a
database round trip per request to look up a session row, and the only thing that
buys in the MVP is instant revocation, which the MVP does not offer. The
trade-off is written down so that adding revocation later is a decision rather
than a surprise: it needs a table.

`SameSite=Lax` plus httpOnly is the CSRF and XSS posture (B4). `Secure` is set
only when the request arrived over HTTPS, because a `Secure` cookie on
`http://localhost` is silently dropped and the UI agent would see a login that
appears to succeed and then forgets them.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.engine import Connection

from fdip.adapters import keys as key_tools
from fdip.adapters.keys import MIN_PASSWORD_LENGTH
from fdip.adapters.repository import GlobalRepository, ProjectRepository
from fdip.api import problems
from fdip.api.deps import (
    AppState,
    Principal,
    db_connection,
    get_state,
    limit_by_ip,
    session_principal,
)

router = APIRouter(tags=["auth"])

DEFAULT_PROJECT_NAME = "Default"


class Credentials(BaseModel):
    """Registration. The format rules belong here and only here."""

    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=200)


class LoginRequest(BaseModel):
    """Login, deliberately without the registration rules.

    Two reasons, both learned the hard way. `dev@fdip.local` is a reserved TLD
    that `EmailStr` refuses, so the seeded account could never log in. And more
    generally, tightening the registration policy must never lock out an account
    that already exists: a login is authenticated by lookup, not by format.
    """

    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=200)


class SessionUser(BaseModel):
    id: str
    email: str


class ProjectRef(BaseModel):
    id: str
    name: str


class MeResponse(BaseModel):
    user: SessionUser
    projects: list[ProjectRef]


def _set_cookie(response: Response, request: Request, state: AppState,
                user_id: str) -> None:
    response.set_cookie(
        key_tools.SESSION_COOKIE,
        key_tools.session_token(state.settings.session_secret, user_id),
        max_age=key_tools.SESSION_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )


@router.post("/auth/register", response_model=MeResponse, status_code=201)
def register(payload: Credentials, request: Request, response: Response,
             state: AppState = Depends(get_state),
             connection: Connection = Depends(db_connection)) -> MeResponse:
    """Create an account and its first project, then log in.

    A new account gets a project immediately because every other route needs
    one, and an account with no project is a dead end the UI cannot escape.
    """
    if not state.settings.allow_registration:
        # 403 with a reason, not a 404 pretending the route is absent: someone
        # who finds the sign-up page should be told it is closed, not left
        # guessing whether they typed the address wrong.
        raise problems.Problem(
            403, "registration_closed",
            "New accounts are invite only at the moment. Ask the team for an "
            "invitation and you will be sent a sign-in.",
        )
    limit_by_ip(request, state, "register", state.settings.login_attempts_per_minute)
    repo = GlobalRepository(connection)
    email = str(payload.email).strip().lower()
    if repo.user_by_email(email) is not None:
        raise problems.conflict("email_taken", "that email is already registered")
    user_id = repo.create_user(
        email=email, password_hash=key_tools.hash_password(payload.password),
        is_active=True,
    )
    project_id = repo.create_project(
        owner_id=user_id, name=DEFAULT_PROJECT_NAME,
        allowed_providers=["deepseek", "mock"], monthly_page_quota=10000,
    )
    _set_cookie(response, request, state, user_id)
    return MeResponse(
        user=SessionUser(id=user_id, email=email),
        projects=[ProjectRef(id=project_id, name=DEFAULT_PROJECT_NAME)],
    )


@router.post("/auth/login", response_model=MeResponse)
def login(payload: LoginRequest, request: Request, response: Response,
          state: AppState = Depends(get_state),
          connection: Connection = Depends(db_connection)) -> MeResponse:
    # Before the password is checked, so a guessing run is cut off whether or
    # not the accounts it names exist.
    limit_by_ip(request, state, "login", state.settings.login_attempts_per_minute)
    repo = GlobalRepository(connection)
    user = repo.user_by_email(str(payload.email))
    # One message whether the email is unknown or the password is wrong: the
    # difference is an account-enumeration oracle.
    if user is None or not key_tools.verify_password(
        payload.password, str(user["password_hash"])
    ):
        raise problems.unauthenticated("the email or password is incorrect")
    if not user["is_active"]:
        raise problems.unauthenticated("the email or password is incorrect")
    user_id = str(user["id"])
    _set_cookie(response, request, state, user_id)
    projects = repo.projects_for(user_id)
    return MeResponse(
        user=SessionUser(id=user_id, email=str(user["email"])),
        projects=[
            ProjectRef(id=str(row["id"]), name=str(row["name"])) for row in projects
        ],
    )


@router.post("/auth/logout", status_code=204)
def logout(response: Response) -> Response:
    """Clears the cookie. The token itself stays valid until it expires.

    Stated rather than hidden: without a session table there is nothing to
    invalidate, so a token already copied elsewhere survives a logout.
    """
    response.delete_cookie(key_tools.SESSION_COOKIE, path="/")
    response.status_code = 204
    return response


class PasswordChange(BaseModel):
    """The current password is required even though the session proves identity.

    A session can be borrowed — a shared screen, a stolen cookie. Requiring the
    current password means taking the account permanently needs more than
    sitting down at someone's desk.
    """

    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=200)


@router.post("/auth/password", status_code=204)
def change_password(
    payload: PasswordChange,
    request: Request,
    response: Response,
    principal: Annotated[Principal, Depends(session_principal)],
    state: AppState = Depends(get_state),
    connection: Connection = Depends(db_connection),
) -> Response:
    """Change your own password, without anyone touching the server.

    There is no forgotten-password flow: that needs email, token storage and
    expiry. The product says so where a user can read it rather than implying a
    reset link exists. Until then a lockout is recovered by the owner running
    `deploy/scripts/reset-password.sh`.
    """
    from sqlalchemy import update

    from fdip.adapters import tables

    # The same per-address bound as login: guessing the current password here
    # is as good as guessing it at the sign-in form.
    limit_by_ip(request, state, "password", state.settings.login_attempts_per_minute)

    # `user_id` is optional on a Principal because an API key has none. This
    # route is session-only, so it is always set here — checked rather than
    # asserted, since a wrong answer would be an authentication bypass.
    if principal.user_id is None:
        raise problems.unauthenticated("sign in again")
    user = GlobalRepository(connection).user(principal.user_id)
    if user is None:  # pragma: no cover - a live session implies a user
        raise problems.unauthenticated("sign in again")

    if not key_tools.verify_password(payload.current_password,
                                     str(user["password_hash"])):
        raise problems.Problem(
            403, "password_incorrect", "that is not your current password",
        )

    connection.execute(
        update(tables.users)
        .where(tables.users.c.id == user["id"])
        .values(password_hash=key_tools.hash_password(payload.new_password))
    )
    # Neither password reaches the detail, which is the whole point of
    # recording this: that it happened, and when.
    ProjectRepository(connection, principal.project_id).audit(
        principal.actor, "password_changed", "user", str(user["id"]), {},
    )
    response.status_code = 204
    return response


@router.get("/auth/me", response_model=MeResponse)
def me(principal: Annotated[Principal, Depends(session_principal)],
       connection: Connection = Depends(db_connection)) -> MeResponse:
    repo = GlobalRepository(connection)
    user = repo.user(str(principal.user_id))
    if user is None:  # pragma: no cover - the dependency already checked
        raise problems.unauthenticated("the account no longer exists")
    return MeResponse(
        user=SessionUser(id=str(user["id"]), email=str(user["email"])),
        projects=[
            ProjectRef(id=str(row["id"]), name=str(row["name"]))
            for row in repo.projects_for(str(user["id"]))
        ],
    )


__all__ = ["router"]
