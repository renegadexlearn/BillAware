from __future__ import annotations

from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import requests
from flask import current_app, url_for


class CommonAuthOAuthClient:
    _sync_token: str | None = None
    _sync_token_expires_at: datetime | None = None

    def __init__(self, *, redirect_uri_override: str | None = None):
        self.base_url = (current_app.config.get("COMMON_AUTH_BASE_URL") or "").rstrip("/")
        self.client_id = (current_app.config.get("COMMON_AUTH_CLIENT_ID") or "billaware").strip()
        self.client_secret = (current_app.config.get("COMMON_AUTH_CLIENT_SECRET") or "").strip()
        self.redirect_uri = (
            (redirect_uri_override or "").strip()
            or (current_app.config.get("COMMON_AUTH_REDIRECT_URI") or "").strip()
            or url_for("auth.common_auth_callback", _external=True)
        )
        self.timeout = float(current_app.config.get("COMMON_AUTH_TIMEOUT_SECONDS", 10))

        if not self.base_url or not self.client_secret or not self.redirect_uri:
            raise RuntimeError("common_auth_not_configured")

    @staticmethod
    def _naive_utc(value: datetime | None) -> datetime | None:
        if not value:
            return None
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value

    def authorize_url(self, *, state: str) -> str:
        query = urlencode(
            {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "state": state,
            }
        )
        return f"{self.base_url}/authorize?{query}"

    def exchange_code_for_token(self, *, code: str) -> str:
        response = requests.post(
            f"{self.base_url}/token",
            json={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": code,
                "redirect_uri": self.redirect_uri,
            },
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            raise RuntimeError(f"token_exchange_failed:{response.status_code}")

        payload = response.json()
        token = (payload.get("access_token") or "").strip()
        if not token:
            raise RuntimeError("missing_access_token")
        expires_in = int(payload.get("expires_in") or 0)
        if expires_in > 0:
            CommonAuthOAuthClient._sync_token = token
            CommonAuthOAuthClient._sync_token_expires_at = datetime.utcnow() + timedelta(seconds=max(expires_in - 60, 30))
        return token

    def get_sync_access_token(self) -> str:
        now = datetime.utcnow()
        token_expires_at = self._naive_utc(CommonAuthOAuthClient._sync_token_expires_at)
        if CommonAuthOAuthClient._sync_token and token_expires_at and now < token_expires_at:
            return CommonAuthOAuthClient._sync_token

        sync_email = (current_app.config.get("COMMON_AUTH_SYNC_EMAIL") or "").strip().lower()
        sync_password = (current_app.config.get("COMMON_AUTH_SYNC_PASSWORD") or "").strip()
        if not sync_email or not sync_password:
            raise RuntimeError("common_auth_sync_credentials_missing")

        auth_session = requests.Session()
        next_value = url_for("auth.login_common_auth", _external=False)
        login_url = f"{self.base_url}/auth/login"
        login_response = auth_session.post(
            login_url,
            data={"email": sync_email, "password": sync_password, "next": next_value},
            allow_redirects=False,
            timeout=self.timeout,
        )
        if login_response.status_code not in {302, 303}:
            raise RuntimeError(f"common_auth_sync_login_failed:{login_response.status_code}")
        location = (login_response.headers.get("Location") or "").lower()
        if "/auth/login" in location:
            raise RuntimeError("common_auth_sync_invalid_credentials")

        authorize_response = auth_session.get(
            self.authorize_url(state="billaware-sync"),
            allow_redirects=False,
            timeout=self.timeout,
        )
        if authorize_response.status_code not in {302, 303}:
            raise RuntimeError(f"common_auth_sync_authorize_failed:{authorize_response.status_code}")

        redirect_location = authorize_response.headers.get("Location") or ""
        if "code=" not in redirect_location:
            raise RuntimeError("common_auth_sync_code_missing")

        code = ""
        for part in redirect_location.split("?", 1)[-1].split("&"):
            if part.startswith("code="):
                code = part.split("=", 1)[1]
                break
        if not code:
            raise RuntimeError("common_auth_sync_code_missing")

        return self.exchange_code_for_token(code=code)
