import jwt
from flask import current_app

def _load_public_key() -> str:
    path = current_app.config["JWT_PUBLIC_KEY_PATH"]
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def verify_bearer_token(token: str) -> dict:
    public_key = _load_public_key()
    payload = jwt.decode(
        token,
        public_key,
        algorithms=["RS256"],
        audience=current_app.config["JWT_AUDIENCE"],
        issuer=current_app.config["JWT_ISSUER"],
        options={"require": ["exp", "iat", "iss", "aud", "sub"]},
    )
    return payload
