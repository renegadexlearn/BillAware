from functools import wraps
from flask import g, jsonify, request, session
from .jwt import verify_bearer_token

def require_jwt(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        token = ""
        if auth.startswith("Bearer "):
            token = auth.split(" ", 1)[1].strip()
        else:
            token = (session.get("common_auth_access_token") or "").strip()

        if not token:
            return jsonify({"error": "missing_bearer_token"}), 401

        try:
            g.jwt = verify_bearer_token(token)
            g.access_token = token
        except Exception as e:
            return jsonify({"error": "invalid_token", "details": str(e)}), 401

        return fn(*args, **kwargs)
    return wrapper
