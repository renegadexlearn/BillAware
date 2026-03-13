from __future__ import annotations

import json
from urllib import error, parse, request

from flask import current_app


class CommonAuthClientError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, payload=None):
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


class CommonAuthClient:
    def __init__(self, base_url: str, timeout: float = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    @classmethod
    def from_app(cls) -> "CommonAuthClient":
        return cls(
            base_url=current_app.config["COMMONAUTH_API_BASE_URL"],
            timeout=current_app.config["COMMONAUTH_TIMEOUT_SECONDS"],
        )

    def get_me(self, token: str) -> dict:
        return self._get_json("/me", token=token)

    def get_scope(self, token: str) -> dict:
        return self._get_json("/scope", token=token)

    def get_users(self, token: str, *, updated_after: str | None = None) -> dict:
        params = {"updated_after": updated_after} if updated_after else None
        return self._get_json("/users", token=token, params=params)

    def get_employees(self, token: str, *, updated_after: str | None = None) -> dict:
        params = {"updated_after": updated_after} if updated_after else None
        return self._get_json("/employees", token=token, params=params)

    def _get_json(self, path: str, *, token: str, params: dict | None = None) -> dict:
        url = f"{self.base_url}{path}"
        if params:
            query = parse.urlencode({key: value for key, value in params.items() if value not in (None, "")})
            if query:
                url = f"{url}?{query}"

        req = request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
            },
            method="GET",
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                return json.loads(body) if body else {}
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8")
            payload = None
            if body:
                try:
                    payload = json.loads(body)
                except json.JSONDecodeError:
                    payload = body
            message = payload.get("error") if isinstance(payload, dict) else exc.reason
            raise CommonAuthClientError(str(message or "common_auth_http_error"), exc.code, payload) from exc
        except error.URLError as exc:
            raise CommonAuthClientError(f"common_auth_unreachable: {exc.reason}") from exc
