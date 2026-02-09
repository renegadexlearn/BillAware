# app/utils/tokens.py
from itsdangerous import URLSafeTimedSerializer
from flask import current_app

def _get_serializer():
    secret = current_app.config["SECRET_KEY"]
    salt = current_app.config.get("SECURITY_PASSWORD_SALT")
    return URLSafeTimedSerializer(secret, salt=salt)

def generate_password_reset_token(email: str) -> str:
    s = _get_serializer()
    return s.dumps(email)

def verify_password_reset_token(token: str, max_age: int = None):
    s = _get_serializer()
    max_age = max_age or current_app.config.get("PASSWORD_RESET_TOKEN_EXPIRES", 3600)
    try:
        email = s.loads(token, max_age=max_age)
        return email
    except Exception:
        return None
