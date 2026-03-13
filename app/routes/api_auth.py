from flask import Blueprint, current_app, g, jsonify, request
from flask_login import current_user

from app.auth.decorators import require_jwt
from app.auth.scope import jwt_scope, raw_jwt_scope
from app.extensions import db
from app.models import CurrentUserSnapshot
from app.services.auth_sync import CommonAuthSyncService, run_commonauth_sync
from app.services.common_auth_client import CommonAuthClientError


bp = Blueprint("api_auth", __name__)


def _snapshot_for_current_subject():
    subject = g.jwt.get("sub")
    if not str(subject or "").isdigit():
        return None
    return db.session.get(CurrentUserSnapshot, int(subject))


@bp.get("/api/auth/status")
@require_jwt
def auth_status():
    snapshot = _snapshot_for_current_subject()
    raw_scope = raw_jwt_scope()
    app_scope = current_user.app_scope_payload() if current_user.is_authenticated else jwt_scope()
    return jsonify(
        {
            "authenticated": True,
            "iss": g.jwt.get("iss"),
            "aud": g.jwt.get("aud"),
            "sub": g.jwt.get("sub"),
            "email": g.jwt.get("email"),
            "name": g.jwt.get("name"),
            "roles": g.jwt.get("roles", []),
            "main_groups": raw_scope["main_group_ids"],
            "companies": raw_scope["company_ids"],
            "branches": raw_scope["branch_ids"],
            "app_scope": app_scope,
            "exp": g.jwt.get("exp"),
            "cached": {
                "has_snapshot": snapshot is not None,
                "user": snapshot.user_payload if snapshot else None,
                "employee": snapshot.employee_payload if snapshot else None,
                "scope": snapshot.scope_payload if snapshot else None,
                "synced_at": snapshot.synced_at.isoformat() if snapshot else None,
            },
        }
    ), 200


@bp.post("/api/auth/bootstrap")
@require_jwt
def auth_bootstrap():
    service = CommonAuthSyncService()
    try:
        result = service.sync(g.access_token)
    except CommonAuthClientError as exc:
        db.session.rollback()
        status = exc.status_code or 502
        return jsonify(
            {
                "error": "common_auth_sync_failed",
                "details": str(exc),
                "upstream_status": exc.status_code,
                "upstream_payload": exc.payload,
            }
        ), status

    snapshot = db.session.get(CurrentUserSnapshot, result.user_id)
    return jsonify(
        {
            "authenticated": True,
            "user_id": result.user_id,
            "jwt_scope": raw_jwt_scope(),
            "app_scope": result.scope,
            "permissions": result.permissions,
            "synced": result.synced,
            "cache": {
                "user": snapshot.user_payload if snapshot else None,
                "employee": snapshot.employee_payload if snapshot else None,
                "scope": snapshot.scope_payload if snapshot else result.scope,
                "synced_at": snapshot.synced_at.isoformat() if snapshot else None,
            },
        }
    ), 200


@bp.post("/api/commonauth/sync")
def trigger_sync():
    expected_secret = (current_app.config.get("COMMON_AUTH_PUSH_SYNC_SECRET") or "").strip()
    if not expected_secret:
        return jsonify({"error": "sync_secret_not_configured"}), 503

    provided_secret = (request.headers.get("X-Secret-Key") or "").strip()
    if provided_secret != expected_secret:
        return jsonify({"error": "forbidden"}), 403

    payload = request.get_json(silent=True) or {}
    force_full = bool(payload.get("full", False))
    reason = (payload.get("reason") or "").strip() or None

    try:
        result = run_commonauth_sync(
            trigger="push",
            reason=reason,
            force_full=force_full,
        )
    except Exception as exc:
        current_app.logger.exception("BillAware commonAuth push sync failed reason=%s", reason)
        return jsonify({"ok": False, "error": str(exc)}), 500

    if result is None:
        return jsonify({"ok": True, "skipped": True, "reason": "sync_already_running"}), 200

    return jsonify(
        {
            "ok": True,
            "skipped": False,
            "full_sync": force_full,
            "main_groups_synced": result.synced.get("main_groups", 0),
            "companies_synced": result.synced.get("companies", 0),
            "branches_synced": result.synced.get("branches", 0),
            "users_synced": result.synced.get("users", 0),
            "employees_synced": result.synced.get("employees", 0),
            "reason": reason,
        }
    ), 200
