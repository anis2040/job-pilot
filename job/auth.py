"""Google OAuth (Authlib) + Flask session helpers."""
from __future__ import annotations

import os
from functools import wraps

from authlib.integrations.flask_client import OAuth
from flask import Flask, g, jsonify, redirect, request, session, url_for

from .profiles import ensure_user_dir, validate_user_id
from .user_context import LOCAL_USER_ID, auth_disabled

oauth = OAuth()


def init_oauth(app: Flask) -> None:
    oauth.init_app(app)
    client_id = os.environ.get("GOOGLE_CLIENT_ID", "")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET", "")
    if client_id and client_secret:
        oauth.register(
            name="google",
            client_id=client_id,
            client_secret=client_secret,
            server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
            client_kwargs={"scope": "openid email profile"},
        )


def google_configured() -> bool:
    return bool(os.environ.get("GOOGLE_CLIENT_ID") and os.environ.get("GOOGLE_CLIENT_SECRET"))


def user_id_from_google(userinfo: dict) -> str:
    sub = str(userinfo.get("sub") or "").strip()
    if not sub:
        raise ValueError("Google userinfo missing sub")
    uid = f"google_{sub}"
    if not validate_user_id(uid):
        raise ValueError("Invalid Google subject")
    return uid


def login_user(userinfo: dict) -> str:
    uid = user_id_from_google(userinfo)
    ensure_user_dir(uid)
    session["user_id"] = uid
    session["email"] = userinfo.get("email") or ""
    session["name"] = userinfo.get("name") or ""
    session["picture"] = userinfo.get("picture") or ""
    session.permanent = True
    return uid


def logout_user() -> None:
    session.clear()


def current_session_user() -> dict | None:
    uid = session.get("user_id")
    if not uid:
        return None
    return {
        "id": uid,
        "email": session.get("email") or "",
        "name": session.get("name") or "",
        "picture": session.get("picture") or "",
    }


def resolve_request_user() -> str | None:
    """Set g.user_id from session or AUTH_DISABLED. Returns user_id or None."""
    if auth_disabled():
        g.user_id = LOCAL_USER_ID
        ensure_user_dir(LOCAL_USER_ID)
        return LOCAL_USER_ID
    uid = session.get("user_id")
    if uid and validate_user_id(uid):
        g.user_id = uid
        return uid
    g.user_id = None
    return None


def _is_public_path(path: str) -> bool:
    if path.startswith("/auth/"):
        return True
    if path.startswith("/assets/") or path.startswith("/spa-assets/"):
        return True
    # Login / SPA shell (index is /app or /login; Vite assets under /assets)
    if path in ("/app", "/login", "/favicon.svg", "/favicon.ico"):
        return True
    if path.startswith("/app/"):
        return True
    return False


def register_auth_routes(app: Flask) -> None:
    @app.before_request
    def _auth_gate():
        path = request.path or "/"
        if _is_public_path(path):
            resolve_request_user()  # optional identity for public pages
            return None

        uid = resolve_request_user()
        if uid:
            return None

        if path.startswith("/api/") or path.startswith("/pdf/"):
            return jsonify({"error": "unauthorized"}), 401

        # HTML / legacy pages → login
        return redirect("/login")

    @app.get("/auth/me")
    def auth_me():
        if auth_disabled():
            return jsonify({
                "id": LOCAL_USER_ID,
                "email": "",
                "name": "Local",
                "picture": "",
                "auth_disabled": True,
            })
        user = current_session_user()
        if not user:
            return jsonify({"error": "unauthorized"}), 401
        return jsonify(user)

    @app.get("/auth/login/google")
    def auth_login_google():
        if auth_disabled():
            return redirect("/")
        if not google_configured():
            return jsonify({
                "error": "Google OAuth not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.",
            }), 503
        redirect_uri = os.environ.get("OAUTH_REDIRECT_URI") or url_for(
            "auth_callback_google", _external=True
        )
        return oauth.google.authorize_redirect(redirect_uri)

    @app.get("/auth/callback/google")
    def auth_callback_google():
        if not google_configured():
            return jsonify({"error": "Google OAuth not configured"}), 503
        token = oauth.google.authorize_access_token()
        userinfo = token.get("userinfo")
        if not userinfo:
            userinfo = oauth.google.userinfo()
        login_user(dict(userinfo))
        # Prefer SPA; fall back to root
        return redirect("/app")

    @app.post("/auth/logout")
    def auth_logout():
        logout_user()
        return jsonify({"ok": True})

    @app.get("/auth/status")
    def auth_status():
        return jsonify({
            "google_configured": google_configured(),
            "auth_disabled": auth_disabled(),
            "authenticated": bool(resolve_request_user()),
        })
