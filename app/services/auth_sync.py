from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from flask import current_app
from sqlalchemy import text

from app.extensions import db
from app.models import (
    BranchCache,
    CompanyCache,
    CommonAuthSyncRun,
    CurrentUserSnapshot,
    EmployeeCache,
    MainGroupCache,
    ReferenceSyncState,
    UserCache,
)
from app.services.common_auth import CommonAuthOAuthClient
from app.services.common_auth_client import CommonAuthClient


SYNC_DB_LOCK_NAME = "billaware_commonauth_sync_lock"


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)


def _cursor_value(state: ReferenceSyncState | None) -> str | None:
    if not state or not state.cursor_updated_at:
        return None
    return state.cursor_updated_at.isoformat() + "Z"


def _latest_timestamp(payloads: list[dict], *, fallback: datetime | None) -> datetime | None:
    timestamps = [_parse_dt(item.get("updated_at")) for item in payloads]
    timestamps = [item for item in timestamps if item is not None]
    if fallback is not None:
        timestamps.append(fallback)
    return max(timestamps) if timestamps else fallback


def _upsert(model, record_id: int):
    instance = db.session.get(model, int(record_id))
    if instance is None:
        instance = model(id=int(record_id))
        db.session.add(instance)
    return instance


def _now_utc() -> datetime:
    return datetime.utcnow()


def _begin_sync_run(*, trigger: str, reason: str | None, requested_by_user_id: int | None, force_full: bool) -> CommonAuthSyncRun:
    row = CommonAuthSyncRun(
        started_at=_now_utc(),
        status="running",
        trigger=trigger[:30],
        reason=(reason or None),
        requested_by_user_id=requested_by_user_id,
        force_full=force_full,
    )
    db.session.add(row)
    db.session.flush()
    return row


def _finalize_sync_run(
    row: CommonAuthSyncRun,
    *,
    result: "AuthSyncResult | None" = None,
    status: str,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    row.finished_at = _now_utc()
    row.status = status[:20]
    if result:
        row.main_groups_synced = int(result.synced.get("main_groups") or 0)
        row.companies_synced = int(result.synced.get("companies") or 0)
        row.branches_synced = int(result.synced.get("branches") or 0)
        row.users_synced = int(result.synced.get("users") or 0)
        row.employees_synced = int(result.synced.get("employees") or 0)
    row.error_code = error_code
    row.error_message = error_message


def _try_acquire_db_lock(lock_name: str) -> bool:
    result = db.session.execute(text("SELECT GET_LOCK(:name, 0)"), {"name": lock_name}).scalar()
    return int(result or 0) == 1


def _release_db_lock(lock_name: str) -> None:
    try:
        db.session.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": lock_name})
    except Exception:
        pass


@dataclass
class AuthSyncResult:
    user_id: int
    scope: dict
    roles: list[str]
    permissions: list[str]
    synced: dict


class CommonAuthSyncService:
    def __init__(self, client: CommonAuthClient | None = None):
        self.client = client or CommonAuthClient.from_app()

    def sync(self, token: str, *, force_full: bool = False) -> AuthSyncResult:
        me_payload = self.client.get_me(token)
        scope_payload = self.client.get_scope(token)
        roles = [str(item) for item in (me_payload.get("roles") or []) if item]
        permissions = [str(item) for item in (me_payload.get("permissions") or []) if item]

        user_payload = me_payload.get("user") or {}
        employee_payload = me_payload.get("employee")
        self._sync_scope(scope_payload)
        self._sync_me(user_payload, employee_payload, scope_payload)

        users_state = None if force_full else db.session.get(ReferenceSyncState, "users")
        employees_state = None if force_full else db.session.get(ReferenceSyncState, "employees")

        users_payload = self.client.get_users(token, updated_after=_cursor_value(users_state))
        employees_payload = self.client.get_employees(token, updated_after=_cursor_value(employees_state))

        synced_users = self._sync_users(users_payload.get("users") or [], fallback_user=user_payload)
        synced_employees = self._sync_employees(
            employees_payload.get("employees") or [],
            fallback_employee=employee_payload,
        )

        db.session.commit()

        snapshot = db.session.get(CurrentUserSnapshot, int(user_payload["id"]))
        local_user = db.session.get(UserCache, int(user_payload["id"]))
        return AuthSyncResult(
            user_id=int(user_payload["id"]),
            scope=(local_user.app_scope_payload() if local_user else (snapshot.scope_payload if snapshot else scope_payload)),
            roles=roles,
            permissions=permissions,
            synced={
                "main_groups": len(scope_payload.get("main_groups") or []),
                "companies": len(scope_payload.get("companies") or []),
                "branches": len(scope_payload.get("branches") or []),
                "users": synced_users,
                "employees": synced_employees,
            },
        )

    def _sync_scope(self, scope_payload: dict) -> None:
        now = datetime.utcnow()
        for payload in scope_payload.get("main_groups") or []:
            item = _upsert(MainGroupCache, payload["id"])
            item.name = payload.get("name") or ""
            item.code = payload.get("code")
            item.active = bool(payload.get("active", True))
            item.source_updated_at = _parse_dt(payload.get("updated_at"))
            item.synced_at = now

        for payload in scope_payload.get("companies") or []:
            item = _upsert(CompanyCache, payload["id"])
            item.main_group_id = payload.get("main_group_id")
            item.name = payload.get("name") or ""
            item.active = bool(payload.get("active", True))
            item.source_updated_at = _parse_dt(payload.get("updated_at"))
            item.synced_at = now

        for payload in scope_payload.get("branches") or []:
            item = _upsert(BranchCache, payload["id"])
            item.company_id = int(payload["company_id"])
            item.name = payload.get("name") or ""
            item.code = payload.get("code")
            item.active = bool(payload.get("active", True))
            item.source_updated_at = _parse_dt(payload.get("updated_at"))
            item.synced_at = now

    def _sync_me(self, user_payload: dict, employee_payload: dict | None, scope_payload: dict) -> None:
        now = datetime.utcnow()
        user = _upsert(UserCache, user_payload["id"])
        user.email = user_payload.get("email") or ""
        user.full_name = user_payload.get("full_name")
        user.main_group_id = user_payload.get("main_group_id")
        user.active = bool(user_payload.get("active", True))
        user.employee_id = employee_payload.get("id") if employee_payload else None
        user.memberships = user.memberships or []
        user.source_updated_at = _parse_dt(user_payload.get("updated_at"))
        user.synced_at = now

        if employee_payload:
            self._sync_employee_payload(employee_payload, synced_at=now)

        snapshot = db.session.get(CurrentUserSnapshot, int(user_payload["id"]))
        if snapshot is None:
            snapshot = CurrentUserSnapshot(user_id=int(user_payload["id"]))
            db.session.add(snapshot)

        snapshot.email = user_payload.get("email") or ""
        snapshot.full_name = user_payload.get("full_name")
        snapshot.employee_id = employee_payload.get("id") if employee_payload else None
        snapshot.scope_main_group_ids = list(scope_payload.get("main_group_ids") or [])
        snapshot.scope_company_ids = list(scope_payload.get("company_ids") or [])
        snapshot.scope_branch_ids = list(scope_payload.get("branch_ids") or [])
        snapshot.user_payload = user_payload
        snapshot.employee_payload = employee_payload
        snapshot.scope_payload = scope_payload
        snapshot.synced_at = now

    def _sync_users(self, users: list[dict], *, fallback_user: dict) -> int:
        now = datetime.utcnow()
        all_users = list(users)
        if fallback_user and not any(int(item.get("id", 0)) == int(fallback_user["id"]) for item in all_users):
            all_users.append(fallback_user)

        for payload in all_users:
            item = _upsert(UserCache, payload["id"])
            if "email" in payload:
                item.email = payload.get("email") or ""
            if "full_name" in payload:
                item.full_name = payload.get("full_name")
            if "main_group_id" in payload:
                item.main_group_id = payload.get("main_group_id")
            if "active" in payload:
                item.active = bool(payload.get("active", True))
            if "employee" in payload:
                item.employee_id = (payload.get("employee") or {}).get("id")
            if "memberships" in payload:
                memberships = list(payload.get("memberships") or [])
                item.memberships = memberships
                for membership in memberships:
                    company = membership.get("company") or {}
                    company_id = company.get("id") or membership.get("company_id")
                    if company_id is None:
                        continue
                    cached_company = _upsert(CompanyCache, company_id)
                    cached_company.main_group_id = company.get("main_group_id")
                    cached_company.name = company.get("name") or cached_company.name or f"Company {company_id}"
                    cached_company.active = bool(company.get("active", membership.get("active", True)))
                    company_updated_at = _parse_dt(company.get("updated_at"))
                    if company_updated_at is not None:
                        cached_company.source_updated_at = company_updated_at
                    cached_company.synced_at = now
            updated_at = _parse_dt(payload.get("updated_at"))
            if updated_at is not None:
                item.source_updated_at = updated_at
            item.synced_at = now

        self._set_sync_state(
            "users",
            all_users,
            fallback=_parse_dt(fallback_user.get("updated_at")) if fallback_user else None,
        )
        return len(all_users)

    def _sync_employees(self, employees: list[dict], *, fallback_employee: dict | None) -> int:
        now = datetime.utcnow()
        all_employees = list(employees)
        if fallback_employee and not any(int(item.get("id", 0)) == int(fallback_employee["id"]) for item in all_employees):
            all_employees.append(fallback_employee)

        for payload in all_employees:
            self._sync_employee_payload(payload, synced_at=now)

        self._set_sync_state(
            "employees",
            all_employees,
            fallback=_parse_dt(fallback_employee.get("updated_at")) if fallback_employee else None,
        )
        return len(all_employees)

    def _sync_employee_payload(self, payload: dict, *, synced_at: datetime) -> None:
        item = _upsert(EmployeeCache, payload["id"])
        if "user_id" in payload or "user" in payload:
            item.user_id = payload.get("user_id") or (payload.get("user") or {}).get("id")
        if "company_id" in payload:
            item.company_id = int(payload["company_id"])
        if "branch_id" in payload:
            item.branch_id = payload.get("branch_id")
        if "main_group_id" in payload or "main_group" in payload:
            item.main_group_id = payload.get("main_group_id") or (payload.get("main_group") or {}).get("id")
        if "employee_code" in payload:
            item.employee_code = payload.get("employee_code")
        if "first_name" in payload:
            item.first_name = payload.get("first_name")
        if "last_name" in payload:
            item.last_name = payload.get("last_name")
        if "middle_name" in payload:
            item.middle_name = payload.get("middle_name")
        if "full_name" in payload:
            item.full_name = payload.get("full_name")
        if "job_title" in payload:
            item.job_title = payload.get("job_title")
        if "active" in payload:
            item.active = bool(payload.get("active", True))
        if "branch_ids" in payload:
            item.branch_ids = list(payload.get("branch_ids") or [])
        if "user" in payload:
            item.user_profile = payload.get("user")
        if "company" in payload:
            item.company = payload.get("company")
        if "branch" in payload:
            item.branch = payload.get("branch")
        if "main_group" in payload:
            item.main_group = payload.get("main_group")
        updated_at = _parse_dt(payload.get("updated_at"))
        if updated_at is not None:
            item.source_updated_at = updated_at
        item.synced_at = synced_at

    def _set_sync_state(self, collection: str, payloads: list[dict], *, fallback: datetime | None) -> None:
        state = db.session.get(ReferenceSyncState, collection)
        if state is None:
            state = ReferenceSyncState(collection=collection)
            db.session.add(state)

        state.cursor_updated_at = _latest_timestamp(payloads, fallback=fallback)
        state.last_synced_at = datetime.utcnow()
        state.row_count = len(payloads)


def run_commonauth_sync(
    *,
    trigger: str,
    reason: str | None = None,
    requested_by_user_id: int | None = None,
    force_full: bool = False,
) -> AuthSyncResult | None:
    if not _try_acquire_db_lock(SYNC_DB_LOCK_NAME):
        current_app.logger.info("commonAuth sync skipped: another sync run is active")
        return None

    try:
        history_row = _begin_sync_run(
            trigger=trigger,
            reason=reason,
            requested_by_user_id=requested_by_user_id,
            force_full=force_full,
        )
        token = CommonAuthOAuthClient().get_sync_access_token()
        result = CommonAuthSyncService().sync(token, force_full=force_full)
        _finalize_sync_run(history_row, result=result, status="success")
        db.session.commit()
        current_app.logger.info(
            "commonAuth sync complete trigger=%s full=%s users=%s employees=%s branches=%s",
            trigger,
            force_full,
            result.synced.get("users"),
            result.synced.get("employees"),
            result.synced.get("branches"),
        )
        return result
    except Exception as exc:
        db.session.rollback()
        with db.session.begin():
            failed_row = _begin_sync_run(
                trigger=trigger,
                reason=reason,
                requested_by_user_id=requested_by_user_id,
                force_full=force_full,
            )
            _finalize_sync_run(
                failed_row,
                status="failed",
                error_code=exc.__class__.__name__,
                error_message=str(exc)[:1000],
            )
        raise
    finally:
        _release_db_lock(SYNC_DB_LOCK_NAME)
