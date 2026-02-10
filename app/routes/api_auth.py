# app/routes/api_auth.py (example)
from flask import Blueprint, g, jsonify
from app.auth.decorators import require_jwt

bp = Blueprint("api_auth", __name__)

@bp.get("/api/auth/status")
@require_jwt
def auth_status():
    # If we reached here, token is valid (CommonAuth authenticated)
    return jsonify({
        "authenticated": True,
        "iss": g.jwt.get("iss"),
        "aud": g.jwt.get("aud"),
        "sub": g.jwt.get("sub"),
        "email": g.jwt.get("email"),
        "name": g.jwt.get("name"),
        "roles": g.jwt.get("roles", []),
        "companies": g.jwt.get("companies", []),
        "exp": g.jwt.get("exp"),
    }), 200
