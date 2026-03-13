import os
from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.models import (
    BranchCache,
    CommonAuthSyncRun,
    CompanyCache,
    CurrentUserSnapshot,
    EmployeeCache,
    MainGroupCache,
    ReferenceSyncState,
    UserCache,
)
from app.services.auth_sync import run_commonauth_sync
from app.utils.permissions import permission_required
from app.utils.ui_settings import DEFAULT_UI_SETTINGS, THEME_PRESETS, get_ui_settings, save_ui_settings


bp = Blueprint("web", __name__)


def _is_system_admin() -> bool:
    return current_user.has_role("system_admin")


def _require_system_admin() -> None:
    if not _is_system_admin():
        abort(403)


def _normalize_color(value: str, fallback: str) -> str:
    raw = (value or "").strip()
    if len(raw) == 7 and raw.startswith("#"):
        return raw.upper()
    return fallback


def _save_theme_logo(file) -> str | None:
    if not file or not getattr(file, "filename", ""):
        return None
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}:
        return None
    folder = os.path.join(current_app.static_folder or "", "uploads", "ui")
    os.makedirs(folder, exist_ok=True)
    safe_name = secure_filename(file.filename or "") or f"theme-logo{ext}"
    stored_name = f"{uuid4().hex[:12]}-{safe_name}"
    saved_path = os.path.join(folder, stored_name)
    file.save(saved_path)
    return f"uploads/ui/{stored_name}"


def _dashboard_context() -> dict:
    latest_run = CommonAuthSyncRun.query.order_by(CommonAuthSyncRun.id.desc()).first()
    snapshot = current_user.snapshot()
    active_branch_ids = set(current_user.effective_branch_ids())
    active_company_ids = set(current_user.effective_company_ids())
    active_main_group_ids = set(current_user.effective_main_group_ids())

    return {
        "latest_run": latest_run,
        "snapshot": snapshot,
        "sync_states": {
            row.collection: row
            for row in ReferenceSyncState.query.order_by(ReferenceSyncState.collection.asc()).all()
        },
        "counts": {
            "main_groups": MainGroupCache.query.filter(MainGroupCache.active.is_(True)).count(),
            "companies": CompanyCache.query.filter(CompanyCache.active.is_(True)).count(),
            "branches": BranchCache.query.filter(BranchCache.active.is_(True)).count(),
            "users": UserCache.query.filter(UserCache.active.is_(True)).count(),
            "employees": EmployeeCache.query.filter(EmployeeCache.active.is_(True)).count(),
        },
        "scope_counts": {
            "main_groups": len(active_main_group_ids),
            "companies": len(active_company_ids),
            "branches": len(active_branch_ids),
        },
        "system_admin": _is_system_admin(),
    }


def _render_cache_list(*, page_title: str, eyebrow: str, items, columns: list[dict]):
    return render_template(
        "dashboard/cache_list.html",
        page_title=page_title,
        eyebrow=eyebrow,
        items=items,
        columns=columns,
    )


def _render_auth_list(*, page_title: str, eyebrow: str, items: list[str], description: str):
    return render_template(
        "dashboard/auth_list.html",
        page_title=page_title,
        eyebrow=eyebrow,
        items=items,
        description=description,
    )


@bp.get("/")
@login_required
@permission_required("dashboard_view")
def dashboard():
    return render_template("dashboard/index.html", **_dashboard_context())


@bp.route("/dashboard/theme", methods=["GET", "POST"])
@login_required
@permission_required("dashboard_view")
def theme_editor():
    _require_system_admin()

    if request.method == "POST":
        action = (request.form.get("action") or "save").strip().lower()
        current = get_ui_settings()

        if action == "preset":
            preset_key = (request.form.get("preset") or "").strip().lower()
            preset = THEME_PRESETS.get(preset_key)
            if not preset:
                flash("Invalid preset.", "danger")
                return redirect(url_for("web.theme_editor"))
            updated = dict(current)
            updated.update({key: value for key, value in preset.items() if key != "label"})
            save_ui_settings(updated)
            flash(f"Applied {preset['label']} preset.", "success")
            return redirect(url_for("web.theme_editor"))

        logo_action = (request.form.get("logo_action") or "").strip().lower()
        logo_upload = request.files.get("logo_file")
        logo_path = current.get("logo_path") or DEFAULT_UI_SETTINGS["logo_path"]
        if logo_action == "reset":
            logo_path = DEFAULT_UI_SETTINGS["logo_path"]
        elif logo_upload and getattr(logo_upload, "filename", ""):
            saved_logo_path = _save_theme_logo(logo_upload)
            if not saved_logo_path:
                flash("Logo must be a PNG, JPG, JPEG, GIF, SVG, or WEBP image.", "danger")
                return redirect(url_for("web.theme_editor"))
            logo_path = saved_logo_path

        updated = {
            "app_title": (request.form.get("app_title") or current.get("app_title") or DEFAULT_UI_SETTINGS["app_title"]).strip(),
            "logo_path": logo_path,
            "navbar_bg": _normalize_color(request.form.get("navbar_bg"), current["navbar_bg"]),
            "navbar_text": _normalize_color(request.form.get("navbar_text"), current["navbar_text"]),
            "primary_bg": _normalize_color(request.form.get("primary_bg"), current["primary_bg"]),
            "primary_hover": _normalize_color(request.form.get("primary_hover"), current["primary_hover"]),
            "primary_text": _normalize_color(request.form.get("primary_text"), current["primary_text"]),
            "accent_bg": _normalize_color(request.form.get("accent_bg"), current["accent_bg"]),
            "surface_tint": _normalize_color(request.form.get("surface_tint"), current["surface_tint"]),
        }
        save_ui_settings(updated)
        flash("Theme settings saved.", "success")
        return redirect(url_for("web.theme_editor"))

    return render_template("dashboard/theme_editor.html", settings=get_ui_settings(), presets=THEME_PRESETS)


@bp.post("/commonauth/sync")
@login_required
def manual_sync():
    force_full = request.form.get("full") == "1"
    try:
        result = run_commonauth_sync(
            trigger="manual",
            reason="dashboard_manual_sync",
            requested_by_user_id=int(current_user.id),
            force_full=force_full,
        )
    except Exception:
        flash("commonAuth sync failed. Check the logs for details.", "danger")
        return redirect(url_for("web.dashboard"))

    if result is None:
        flash("commonAuth sync skipped because another sync is already running.", "warning")
    else:
        flash(
            (
                "commonAuth sync complete. "
                f"Users: {result.synced.get('users', 0)}, "
                f"Employees: {result.synced.get('employees', 0)}, "
                f"Branches: {result.synced.get('branches', 0)}."
            ),
            "success",
        )
    return redirect(url_for("web.dashboard"))


@bp.get("/dashboard/sync-history")
@login_required
def sync_history():
    rows = CommonAuthSyncRun.query.order_by(CommonAuthSyncRun.id.desc()).limit(50).all()
    return render_template("dashboard/sync_history.html", rows=rows)


@bp.get("/dashboard/users")
@login_required
def users():
    items = UserCache.query.order_by(UserCache.full_name.asc(), UserCache.email.asc()).all()
    return _render_cache_list(
        page_title="Users",
        eyebrow="commonAuth mirror",
        items=items,
        columns=[
            {"label": "ID", "attr": "id"},
            {"label": "Name", "attr": "display_name"},
            {"label": "Email", "attr": "email"},
            {"label": "Main Group", "callable": lambda item: item.main_group_id or "-"},
            {"label": "Status", "callable": lambda item: "Active" if item.active else "Inactive"},
            {"label": "Synced", "callable": lambda item: item.synced_at},
        ],
    )


@bp.get("/dashboard/roles")
@login_required
@permission_required("dashboard_view")
def roles():
    items = sorted(set(current_user.common_auth_roles))
    return _render_auth_list(
        page_title="Roles",
        eyebrow="commonAuth session",
        items=items,
        description="Roles synced from commonAuth for your current BillAware session.",
    )


@bp.get("/dashboard/permissions")
@login_required
@permission_required("dashboard_view")
def permissions():
    items = sorted(set(current_user.common_auth_permissions))
    return _render_auth_list(
        page_title="Permissions",
        eyebrow="commonAuth session",
        items=items,
        description="Permissions synced from commonAuth for your current BillAware session.",
    )


@bp.get("/dashboard/employees")
@login_required
def employees():
    items = EmployeeCache.query.order_by(EmployeeCache.full_name.asc(), EmployeeCache.id.asc()).all()
    return _render_cache_list(
        page_title="Employees",
        eyebrow="commonAuth mirror",
        items=items,
        columns=[
            {"label": "ID", "attr": "id"},
            {"label": "Name", "callable": lambda item: item.full_name or "-"},
            {"label": "Code", "callable": lambda item: item.employee_code or "-"},
            {"label": "Company", "callable": lambda item: (item.company or {}).get("name") or item.company_id or "-"},
            {"label": "Branch", "callable": lambda item: (item.branch or {}).get("name") or item.branch_id or "-"},
            {"label": "Role", "callable": lambda item: item.job_title or "-"},
            {"label": "Status", "callable": lambda item: "Active" if item.active else "Inactive"},
        ],
    )


@bp.get("/dashboard/main-groups")
@login_required
def main_groups():
    items = MainGroupCache.query.order_by(MainGroupCache.name.asc()).all()
    return _render_cache_list(
        page_title="Main Groups",
        eyebrow="Scope cache",
        items=items,
        columns=[
            {"label": "ID", "attr": "id"},
            {"label": "Name", "attr": "name"},
            {"label": "Code", "callable": lambda item: item.code or "-"},
            {"label": "Status", "callable": lambda item: "Active" if item.active else "Inactive"},
            {"label": "Synced", "callable": lambda item: item.synced_at},
        ],
    )


@bp.get("/dashboard/companies")
@login_required
def companies():
    items = CompanyCache.query.order_by(CompanyCache.name.asc()).all()
    return _render_cache_list(
        page_title="Companies",
        eyebrow="Scope cache",
        items=items,
        columns=[
            {"label": "ID", "attr": "id"},
            {"label": "Name", "attr": "name"},
            {"label": "Main Group", "callable": lambda item: item.main_group_id or "-"},
            {"label": "Status", "callable": lambda item: "Active" if item.active else "Inactive"},
            {"label": "Synced", "callable": lambda item: item.synced_at},
        ],
    )


@bp.get("/dashboard/branches")
@login_required
def branches():
    items = BranchCache.query.order_by(BranchCache.name.asc()).all()
    return _render_cache_list(
        page_title="Branches",
        eyebrow="Scope cache",
        items=items,
        columns=[
            {"label": "ID", "attr": "id"},
            {"label": "Name", "attr": "name"},
            {"label": "Code", "callable": lambda item: item.code or "-"},
            {"label": "Company", "callable": lambda item: item.company_id},
            {"label": "Status", "callable": lambda item: "Active" if item.active else "Inactive"},
            {"label": "Synced", "callable": lambda item: item.synced_at},
        ],
    )


@bp.get("/dashboard/scope")
@login_required
def scope_snapshot():
    snapshot = current_user.snapshot()
    return render_template(
        "dashboard/scope_snapshot.html",
        snapshot=snapshot,
        app_scope=current_user.app_scope_payload(),
    )


@bp.get("/bills/encode")
@login_required
@permission_required("encode_view")
def encode_bills():
    return redirect(url_for("billing.bill_create"))


@bp.get("/companies-workspace")
@login_required
def companies_workspace():
    return redirect(url_for("web.companies"))


@bp.get("/suppliers")
@login_required
def suppliers():
    return redirect(url_for("billing.supplier_list"))


@bp.get("/settings")
@login_required
def settings():
    return redirect(url_for("billing.product_list"))


@bp.get("/tags")
@login_required
def tags():
    return redirect(url_for("billing.tag_list"))
