from __future__ import annotations

from flask import g
from flask_login import current_user


def _normalize_id_list(values) -> list[int]:
    normalized: list[int] = []
    for value in values or []:
        try:
            normalized.append(int(value))
        except (TypeError, ValueError):
            continue
    return sorted(set(normalized))


def raw_jwt_scope() -> dict:
    claims = getattr(g, "jwt", None) or {}
    return {
        "main_group_ids": _normalize_id_list(claims.get("main_groups")),
        "company_ids": _normalize_id_list(claims.get("companies")),
        "branch_ids": _normalize_id_list(claims.get("branches")),
        "roles": list(claims.get("roles") or []),
    }


def jwt_scope() -> dict:
    if current_user.is_authenticated:
        return current_user.app_scope_payload()
    return raw_jwt_scope()


def jwt_allows_company(company_id: int | None) -> bool:
    if company_id is None:
        return True
    scope = jwt_scope()
    return "system_admin" in scope["roles"] or int(company_id) in set(scope["company_ids"])


def jwt_allows_branch(branch_id: int | None) -> bool:
    if branch_id is None:
        return True
    scope = jwt_scope()
    return "system_admin" in scope["roles"] or int(branch_id) in set(scope["branch_ids"])


def filter_ids_to_jwt_scope(company_ids=None, branch_ids=None) -> tuple[list[int] | None, list[int] | None]:
    scope = jwt_scope()
    if "system_admin" in scope["roles"]:
        return (
            _normalize_id_list(company_ids) if company_ids is not None else None,
            _normalize_id_list(branch_ids) if branch_ids is not None else None,
        )

    effective_company_ids = (
        _normalize_id_list(company_ids)
        if company_ids is not None
        else scope["company_ids"]
    )
    effective_branch_ids = (
        _normalize_id_list(branch_ids)
        if branch_ids is not None
        else scope["branch_ids"]
    )

    return (
        sorted(set(effective_company_ids) & set(scope["company_ids"])),
        sorted(set(effective_branch_ids) & set(scope["branch_ids"])),
    )
