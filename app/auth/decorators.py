from functools import wraps
from flask import request, jsonify, g
from .jwt import verify_bearer_token

def require_jwt(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return jsonify({"error": "missing_bearer_token"}), 401

        token = auth.split(" ", 1)[1].strip()
        try:
            g.jwt = verify_bearer_token(token)
        except Exception as e:
            return jsonify({"error": "invalid_token", "details": str(e)}), 401

        return fn(*args, **kwargs)
    return wrapper
