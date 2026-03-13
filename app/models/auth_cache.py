from __future__ import annotations

from datetime import datetime

from flask import has_request_context, session
from flask_login import UserMixin

from app.extensions import db


class MainGroupCache(db.Model):
    __tablename__ = "auth_cache_main_groups"

    id = db.Column(db.BigInteger, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(64), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    source_updated_at = db.Column(db.DateTime, nullable=True)
    synced_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class CompanyCache(db.Model):
    __tablename__ = "auth_cache_companies"

    id = db.Column(db.BigInteger, primary_key=True)
    main_group_id = db.Column(db.BigInteger, nullable=True, index=True)
    name = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    source_updated_at = db.Column(db.DateTime, nullable=True)
    synced_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class BranchCache(db.Model):
    __tablename__ = "auth_cache_branches"

    id = db.Column(db.BigInteger, primary_key=True)
    company_id = db.Column(db.BigInteger, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    code = db.Column(db.String(64), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    source_updated_at = db.Column(db.DateTime, nullable=True)
    synced_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


def _normalize_id_list(values) -> list[int]:
    normalized: list[int] = []
    for value in values or []:
        try:
            normalized.append(int(value))
        except (TypeError, ValueError):
            continue
    return sorted(set(normalized))


class UserCache(db.Model, UserMixin):
    __tablename__ = "auth_cache_users"

    id = db.Column(db.BigInteger, primary_key=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    full_name = db.Column(db.String(255), nullable=True)
    main_group_id = db.Column(db.BigInteger, nullable=True, index=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    employee_id = db.Column(db.BigInteger, nullable=True, index=True)
    memberships = db.Column(db.JSON, nullable=False, default=list)
    source_updated_at = db.Column(db.DateTime, nullable=True)
    synced_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    @property
    def is_active(self) -> bool:
        return bool(self.active)

    @property
    def display_name(self) -> str:
        return (self.full_name or self.email or "").strip()

    @property
    def common_auth_roles(self) -> list[str]:
        if not has_request_context():
            return []
        return [str(item) for item in (session.get("common_auth_roles") or []) if item]

    @property
    def common_auth_permissions(self) -> list[str]:
        if not has_request_context():
            return []
        return [str(item) for item in (session.get("common_auth_permissions") or []) if item]

    def has_role(self, role_name: str) -> bool:
        return role_name in set(self.common_auth_roles)

    def has_permission(self, permission_name: str) -> bool:
        if self.has_role("system_admin"):
            return True
        permissions = set(self.common_auth_permissions)
        roles = set(self.common_auth_roles)
        return permission_name in permissions or permission_name in roles

    def snapshot(self) -> "CurrentUserSnapshot | None":
        return db.session.get(CurrentUserSnapshot, int(self.id))

    def effective_main_group_ids(self) -> list[int]:
        snapshot = self.snapshot()
        if not snapshot:
            return [value for value in [self.main_group_id] if value is not None]

        explicit = _normalize_id_list(snapshot.scope_main_group_ids)
        if explicit:
            return explicit
        return [value for value in [self.main_group_id] if value is not None]

    def effective_company_ids(self) -> list[int]:
        if self.has_role("system_admin"):
            rows = db.session.query(CompanyCache.id).filter(CompanyCache.active.is_(True)).all()
            return sorted({int(row[0]) for row in rows})

        snapshot = self.snapshot()
        explicit = _normalize_id_list(snapshot.scope_company_ids if snapshot else [])
        main_group_ids = self.effective_main_group_ids()
        derived: set[int] = set()
        if main_group_ids:
            rows = (
                db.session.query(CompanyCache.id)
                .filter(
                    CompanyCache.active.is_(True),
                    CompanyCache.main_group_id.in_(main_group_ids),
                )
                .all()
            )
            derived.update(int(row[0]) for row in rows)

        effective = sorted(set(explicit) | derived)
        return effective if effective else explicit

    def effective_branch_ids(self) -> list[int]:
        if self.has_role("system_admin"):
            rows = db.session.query(BranchCache.id).filter(BranchCache.active.is_(True)).all()
            return sorted({int(row[0]) for row in rows})

        snapshot = self.snapshot()
        explicit = _normalize_id_list(snapshot.scope_branch_ids if snapshot else [])
        company_ids = self.effective_company_ids()
        derived: set[int] = set()
        if company_ids:
            rows = (
                db.session.query(BranchCache.id)
                .filter(
                    BranchCache.active.is_(True),
                    BranchCache.company_id.in_(company_ids),
                )
                .all()
            )
            derived.update(int(row[0]) for row in rows)

        effective = sorted(set(explicit) | derived)
        return effective if effective else explicit

    def app_scope_payload(self) -> dict:
        main_group_ids = self.effective_main_group_ids()
        company_ids = self.effective_company_ids()
        branch_ids = self.effective_branch_ids()

        main_groups = []
        if main_group_ids:
            main_groups = [
                {
                    "id": item.id,
                    "name": item.name,
                    "code": item.code,
                    "active": item.active,
                }
                for item in MainGroupCache.query.filter(MainGroupCache.id.in_(main_group_ids)).order_by(MainGroupCache.name.asc()).all()
            ]

        companies = []
        if company_ids:
            companies = [
                {
                    "id": item.id,
                    "main_group_id": item.main_group_id,
                    "name": item.name,
                    "active": item.active,
                }
                for item in CompanyCache.query.filter(CompanyCache.id.in_(company_ids)).order_by(CompanyCache.name.asc()).all()
            ]

        branches = []
        if branch_ids:
            branches = [
                {
                    "id": item.id,
                    "company_id": item.company_id,
                    "name": item.name,
                    "code": item.code,
                    "active": item.active,
                }
                for item in BranchCache.query.filter(BranchCache.id.in_(branch_ids)).order_by(BranchCache.company_id.asc(), BranchCache.name.asc()).all()
            ]

        return {
            "roles": self.common_auth_roles,
            "main_group_ids": main_group_ids,
            "company_ids": company_ids,
            "branch_ids": branch_ids,
            "main_groups": main_groups,
            "companies": companies,
            "branches": branches,
        }


class EmployeeCache(db.Model):
    __tablename__ = "auth_cache_employees"

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(db.BigInteger, nullable=True, index=True)
    company_id = db.Column(db.BigInteger, nullable=False, index=True)
    branch_id = db.Column(db.BigInteger, nullable=True, index=True)
    main_group_id = db.Column(db.BigInteger, nullable=True, index=True)
    employee_code = db.Column(db.String(64), nullable=True)
    first_name = db.Column(db.String(255), nullable=True)
    last_name = db.Column(db.String(255), nullable=True)
    middle_name = db.Column(db.String(255), nullable=True)
    full_name = db.Column(db.String(255), nullable=True)
    job_title = db.Column(db.String(255), nullable=True)
    active = db.Column(db.Boolean, nullable=False, default=True)
    branch_ids = db.Column(db.JSON, nullable=False, default=list)
    user_profile = db.Column(db.JSON, nullable=True)
    company = db.Column(db.JSON, nullable=True)
    branch = db.Column(db.JSON, nullable=True)
    main_group = db.Column(db.JSON, nullable=True)
    source_updated_at = db.Column(db.DateTime, nullable=True)
    synced_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class CurrentUserSnapshot(db.Model):
    __tablename__ = "auth_current_user_snapshots"

    user_id = db.Column(db.BigInteger, primary_key=True)
    email = db.Column(db.String(255), nullable=False, index=True)
    full_name = db.Column(db.String(255), nullable=True)
    employee_id = db.Column(db.BigInteger, nullable=True, index=True)
    scope_main_group_ids = db.Column(db.JSON, nullable=False, default=list)
    scope_company_ids = db.Column(db.JSON, nullable=False, default=list)
    scope_branch_ids = db.Column(db.JSON, nullable=False, default=list)
    user_payload = db.Column(db.JSON, nullable=False, default=dict)
    employee_payload = db.Column(db.JSON, nullable=True)
    scope_payload = db.Column(db.JSON, nullable=False, default=dict)
    synced_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class ReferenceSyncState(db.Model):
    __tablename__ = "auth_reference_sync_state"

    collection = db.Column(db.String(64), primary_key=True)
    cursor_updated_at = db.Column(db.DateTime, nullable=True)
    last_synced_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    row_count = db.Column(db.Integer, nullable=False, default=0)
