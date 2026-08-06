"""Auth gate + Google OAuth plumbing (offline)."""
import pytest

import web
import job.paths
import job.profiles as profs
from job.user_context import LOCAL_USER_ID


@pytest.fixture
def auth_client(tmp_path, monkeypatch):
    monkeypatch.setattr(web, "BASE", tmp_path)
    monkeypatch.setattr(job.paths, "BASE", tmp_path)
    pdir = tmp_path / "profiles"
    pdir.mkdir()
    monkeypatch.setattr(profs, "PROFILES_DIR", pdir)
    monkeypatch.setattr(profs, "_update_symlinks", lambda d: None)
    web.app.config["TESTING"] = True
    web.app.config["SECRET_KEY"] = "test-secret"
    return web.app.test_client()


def test_auth_me_local_when_disabled(auth_client, monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "1")
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    r = auth_client.get("/auth/me")
    assert r.status_code == 200
    assert r.get_json()["id"] == LOCAL_USER_ID
    assert r.get_json()["auth_disabled"] is True


def test_api_requires_auth_when_enabled(auth_client, monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "0")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "csecret")
    monkeypatch.setenv("FLASK_DEBUG", "false")
    r = auth_client.get("/api/profiles")
    assert r.status_code == 401


def test_login_google_redirects_when_configured(auth_client, monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "0")
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "cid")
    monkeypatch.setenv("GOOGLE_CLIENT_SECRET", "csecret")
    monkeypatch.setenv("FLASK_DEBUG", "false")
    from job.auth import init_oauth, oauth
    init_oauth(web.app)

    class _FakeGoogle:
        def authorize_redirect(self, redirect_uri):
            from flask import redirect
            return redirect("https://accounts.google.com/o/oauth2/v2/auth?client_id=cid")

    monkeypatch.setattr(oauth, "google", _FakeGoogle(), raising=False)
    r = auth_client.get("/auth/login/google")
    assert r.status_code in (302, 303)
    assert "accounts.google.com" in r.headers["Location"]


def test_cross_user_profile_not_found(auth_client, monkeypatch):
    monkeypatch.setenv("AUTH_DISABLED", "1")
    other = profs.PROFILES_DIR / "google_other" / "secret-profile"
    other.mkdir(parents=True)
    (other / "profile.md").write_text("# Secret\n")
    r = auth_client.get("/api/profiles/secret-profile/profile-md")
    assert r.status_code == 404
