from functools import wraps
from flask import request, redirect, current_app
from app.auth.jwt import verify_bearer_token

def require_commonauth(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        auth = request.headers.get("Authorization", "")

        # Frontend pages usually don't send Authorization headers,
        # so we also allow token via cookie or JS injection later if needed.
        if not auth.startswith("Bearer "):
            return redirect_to_auth()

        token = auth.split(" ", 1)[1].strip()
        try:
            verify_bearer_token(token)
        except Exception:
            return redirect_to_auth()

        return fn(*args, **kwargs)

    return wrapper


def redirect_to_auth():
    login_url = current_app.config.get(
        "AUTH_LOGIN_URL",
        "https://auth.ianeer.com/auth"
    )
    return redirect(login_url)
