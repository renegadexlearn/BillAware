from functools import wraps
from flask import request, jsonify, g

def require_company(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        jwt_claims = getattr(g, "jwt", None) or {}
        roles = jwt_claims.get("roles") or []
        companies = jwt_claims.get("companies") or []

        # system_admin bypass: company header optional
        if "system_admin" in roles:
            raw = request.headers.get("X-Company-ID", "").strip()
            if raw:
                try:
                    g.company_id = int(raw)
                except ValueError:
                    return jsonify({"error": "company_invalid"}), 400
            else:
                g.company_id = None
            return fn(*args, **kwargs)

        # everyone else MUST provide company
        raw = request.headers.get("X-Company-ID", "").strip()
        if not raw:
            return jsonify({"error": "company_required"}), 400

        try:
            company_id = int(raw)
        except ValueError:
            return jsonify({"error": "company_invalid"}), 400

        # must be allowed by token
        allowed_ids = set(int(x) for x in companies)
        if company_id not in allowed_ids:
            return jsonify({"error": "company_forbidden"}), 403

        g.company_id = company_id
        return fn(*args, **kwargs)

    return wrapper
