from flask import Blueprint, g, jsonify
from flask_login import current_user

from app.auth.decorators import require_jwt
from app.auth.scope import jwt_scope, raw_jwt_scope
from app.extensions import db
from app.models import CurrentUserSnapshot

bp = Blueprint("api", __name__)

@bp.get("/health")
def health():
    return jsonify({"status": "ok", "app": "billaware"})

@bp.get("/api/me")
@require_jwt
def me():
    c = g.jwt
    raw_scope = raw_jwt_scope()
    snapshot = db.session.get(CurrentUserSnapshot, int(c.get("sub"))) if str(c.get("sub", "")).isdigit() else None
    app_scope = current_user.app_scope_payload() if current_user.is_authenticated else raw_scope
    return jsonify({
        "sub": c.get("sub"),
        "email": c.get("email"),
        "name": c.get("name"),
        "roles": c.get("roles", []),
        "main_groups": c.get("main_groups", []),
        "companies": c.get("companies", []),
        "branches": c.get("branches", []),
        "iss": c.get("iss"),
        "aud": c.get("aud"),
        "exp": c.get("exp"),
        "jwt_scope": raw_scope,
        "scope": app_scope,
        "cached_profile": snapshot.user_payload if snapshot else None,
        "cached_scope": snapshot.scope_payload if snapshot else None,
    })
