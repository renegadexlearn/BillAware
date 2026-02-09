from flask import Blueprint, jsonify, g
from app.auth.decorators import require_jwt

bp = Blueprint("api", __name__)

@bp.get("/health")
def health():
    return jsonify({"status": "ok", "app": "billaware"})

@bp.get("/api/me")
@require_jwt
def me():
    c = g.jwt
    return jsonify({
        "sub": c.get("sub"),
        "email": c.get("email"),
        "name": c.get("name"),
        "roles": c.get("roles", []),
        "companies": c.get("companies", []),
        "iss": c.get("iss"),
        "aud": c.get("aud"),
        "exp": c.get("exp"),
    })
