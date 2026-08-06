"""Per-request / per-task user identity for multi-tenant path resolution."""
from __future__ import annotations

import os
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Iterator

LOCAL_USER_ID = "_local"

_current_user_id: ContextVar[str | None] = ContextVar("current_user_id", default=None)


def auth_disabled() -> bool:
    """When True, all requests use the `_local` user (no Google login).

    Explicit AUTH_DISABLED=1/0 wins. Otherwise, in FLASK_DEBUG mode with no
    Google OAuth client configured, auth is auto-disabled so local/dev keeps
    working without Google Cloud setup.
    """
    flag = os.environ.get("AUTH_DISABLED", "").strip().lower()
    if flag in ("1", "true", "yes"):
        return True
    if flag in ("0", "false", "no"):
        return False
    debug = os.environ.get("FLASK_DEBUG", "true").lower() in ("1", "true", "yes")
    has_google = bool(
        os.environ.get("GOOGLE_CLIENT_ID", "").strip()
        and os.environ.get("GOOGLE_CLIENT_SECRET", "").strip()
    )
    return debug and not has_google


def get_current_user_id() -> str:
    """Return the active user id for path/AI scoping.

    Order: contextvar (workers) → Flask g.user_id → AUTH_DISABLED/_local fallback.
    """
    uid = _current_user_id.get()
    if uid:
        return uid
    try:
        from flask import g, has_request_context
        if has_request_context():
            g_uid = getattr(g, "user_id", None)
            if g_uid:
                return str(g_uid)
    except Exception:
        pass
    if auth_disabled():
        return LOCAL_USER_ID
    # CLI / startup without a request: treat as local single-user
    return LOCAL_USER_ID


def set_current_user_id(user_id: str) -> Token:
    return _current_user_id.set(user_id)


def reset_current_user_id(token: Token) -> None:
    _current_user_id.reset(token)


@contextmanager
def user_context(user_id: str) -> Iterator[str]:
    token = set_current_user_id(user_id)
    try:
        yield user_id
    finally:
        reset_current_user_id(token)
