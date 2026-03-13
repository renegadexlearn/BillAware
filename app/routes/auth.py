from __future__ import annotations

import secrets

from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for
from flask_login import current_user, login_required, login_user, logout_user

from app.extensions import db
from app.models import UserCache
from app.services.auth_sync import CommonAuthSyncService
from app.services.common_auth import CommonAuthOAuthClient


auth_bp = Blueprint("auth", __name__)


def _safe_next_url(value: str | None) -> str:
    if value and value.startswith("/") and not value.startswith("//"):
        return value
    return url_for("web.dashboard")


def _redirect_after_login(next_url: str | None = None):
    return redirect(_safe_next_url(next_url))


def _callback_redirect_uri() -> str:
    configured = (current_app.config.get("COMMON_AUTH_REDIRECT_URI") or "").strip()
    if configured:
        return configured
    return url_for("auth.common_auth_callback", _external=True)


@auth_bp.route("/index")
def index():
    if current_user.is_authenticated:
        return _redirect_after_login()
    return redirect(url_for("auth.login"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return _redirect_after_login(request.args.get("next"))

    if request.method == "POST":
        flash("Local username/password login is disabled. Use commonAuth.", "warning")
        return redirect(url_for("auth.login", next=request.args.get("next")))

    return render_template("auth/login.html")


@auth_bp.route("/login/common-auth")
def login_common_auth():
    callback_redirect_uri = _callback_redirect_uri()
    try:
        client = CommonAuthOAuthClient(redirect_uri_override=callback_redirect_uri)
    except RuntimeError:
        flash("Single sign-on is not configured.", "danger")
        return redirect(url_for("auth.login"))

    state = secrets.token_urlsafe(32)
    session["common_auth_oauth_state"] = state
    session["common_auth_oauth_redirect_uri"] = callback_redirect_uri
    session["common_auth_oauth_next"] = _safe_next_url(request.args.get("next"))
    return redirect(client.authorize_url(state=state))


@auth_bp.route("/auth/callback")
def common_auth_callback():
    expected_state = session.pop("common_auth_oauth_state", None)
    callback_redirect_uri = session.pop("common_auth_oauth_redirect_uri", None)
    state = (request.args.get("state") or "").strip()
    code = (request.args.get("code") or "").strip()
    next_url = session.pop("common_auth_oauth_next", url_for("web.dashboard"))

    if not expected_state or state != expected_state:
        flash("Invalid login state. Please try again.", "danger")
        return redirect(url_for("auth.login"))

    if not code:
        flash("Missing authorization code.", "danger")
        return redirect(url_for("auth.login"))

    try:
        client = CommonAuthOAuthClient(redirect_uri_override=callback_redirect_uri)
        access_token = client.exchange_code_for_token(code=code)
        result = CommonAuthSyncService().sync(access_token)
        local_user = db.session.get(UserCache, result.user_id)
        if not local_user or not local_user.active:
            raise RuntimeError("local_user_sync_failed")
    except Exception:
        current_app.logger.exception("commonAuth callback failed")
        db.session.rollback()
        flash("Single sign-on failed. Please try again.", "danger")
        return redirect(url_for("auth.login"))

    login_user(local_user)
    session["common_auth_access_token"] = access_token
    session["common_auth_roles"] = list(result.roles)
    session["common_auth_permissions"] = list(result.permissions)
    session["common_auth_scope"] = result.scope
    return _redirect_after_login(next_url)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.pop("common_auth_access_token", None)
    session.pop("common_auth_roles", None)
    session.pop("common_auth_permissions", None)
    session.pop("common_auth_scope", None)
    session.pop("common_auth_oauth_state", None)
    session.pop("common_auth_oauth_redirect_uri", None)
    session.pop("common_auth_oauth_next", None)
    return render_template(
        "auth/logout.html",
        common_auth_logout_url=f"{current_app.config.get('AUTH_LOGOUT_URL', '').rstrip('/')}?next={url_for('auth.login', _external=True)}",
    )
