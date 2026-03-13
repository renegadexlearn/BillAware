from __future__ import annotations

from flask import Flask, jsonify

from app.auth.scope import filter_ids_to_jwt_scope
from app.extensions import db, login_manager
from app.models import BranchCache, CompanyCache, CurrentUserSnapshot, EmployeeCache, ReferenceSyncState, UserCache
from app.routes.api_auth import bp as api_auth_bp
from app.services.auth_sync import AuthSyncResult, CommonAuthSyncService


class FakeClient:
    def __init__(self):
        self.user_calls = []
        self.employee_calls = []

    def get_me(self, token: str) -> dict:
        assert token == "token-123"
        return {
            "user": {
                "id": 7,
                "email": "user@example.com",
                "full_name": "User Example",
                "main_group_id": 11,
                "active": True,
                "updated_at": "2026-03-04T00:00:00Z",
            },
            "employee": {
                "id": 8,
                "user_id": 7,
                "company_id": 21,
                "branch_id": 31,
                "branch_ids": [31],
                "employee_code": "EMP-001",
                "full_name": "User Example",
                "job_title": "Clerk",
                "active": True,
                "updated_at": "2026-03-04T00:00:00Z",
                "company": {"id": 21, "name": "Northwind", "main_group_id": 11, "active": True},
                "branch": {"id": 31, "company_id": 21, "name": "HQ", "active": True},
                "main_group": {"id": 11, "name": "Retail", "active": True},
            },
        }

    def get_scope(self, token: str) -> dict:
        assert token == "token-123"
        return {
            "main_group_ids": [11],
            "company_ids": [21],
            "branch_ids": [31],
            "main_groups": [
                {"id": 11, "name": "Retail", "code": "RET", "active": True, "updated_at": "2026-03-04T00:00:00Z"}
            ],
            "companies": [
                {"id": 21, "main_group_id": 11, "name": "Northwind", "active": True, "updated_at": "2026-03-04T00:00:00Z"}
            ],
            "branches": [
                {"id": 31, "company_id": 21, "name": "HQ", "code": "HQ", "active": True, "updated_at": "2026-03-04T00:00:00Z"}
            ],
        }

    def get_users(self, token: str, *, updated_after: str | None = None) -> dict:
        self.user_calls.append(updated_after)
        return {
            "users": [
                {
                    "id": 7,
                    "email": "user@example.com",
                    "full_name": "User Example",
                    "main_group_id": 11,
                    "active": True,
                    "updated_at": "2026-03-04T00:00:00Z",
                    "memberships": [
                        {
                            "id": 101,
                            "company_id": 21,
                            "active": True,
                            "branch_ids": [31],
                            "company": {"id": 21, "name": "Northwind", "main_group_id": 11, "active": True},
                        }
                    ],
                    "employee": {"id": 8},
                }
            ]
        }

    def get_employees(self, token: str, *, updated_after: str | None = None) -> dict:
        self.employee_calls.append(updated_after)
        return {
            "employees": [
                {
                    "id": 8,
                    "user_id": 7,
                    "company_id": 21,
                    "branch_id": 31,
                    "branch_ids": [31],
                    "employee_code": "EMP-001",
                    "first_name": "User",
                    "last_name": "Example",
                    "full_name": "User Example",
                    "job_title": "Clerk",
                    "active": True,
                    "updated_at": "2026-03-04T00:00:00Z",
                    "company": {"id": 21, "name": "Northwind", "main_group_id": 11, "active": True},
                    "branch": {"id": 31, "company_id": 21, "name": "HQ", "active": True},
                    "main_group": {"id": 11, "name": "Retail", "active": True},
                    "user": {"id": 7, "email": "user@example.com", "full_name": "User Example", "active": True},
                }
            ]
        }


def make_app() -> Flask:
    app = Flask(__name__)
    app.config.update(
        TESTING=True,
        SECRET_KEY="test",
        SQLALCHEMY_DATABASE_URI="sqlite://",
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
    )
    db.init_app(app)
    login_manager.init_app(app)
    app.register_blueprint(api_auth_bp)

    @app.get("/scope-probe")
    def scope_probe():
        companies, branches = filter_ids_to_jwt_scope([21, 22], [31, 32])
        return jsonify({"companies": companies, "branches": branches})

    with app.app_context():
        import app.models  # noqa: F401

        @login_manager.user_loader
        def load_user(user_id: str):
            if not str(user_id or "").isdigit():
                return None
            return db.session.get(UserCache, int(user_id))

        db.create_all()

    return app


def test_common_auth_sync_upserts_and_advances_cursor():
    app = make_app()
    client = FakeClient()

    with app.app_context():
        service = CommonAuthSyncService(client=client)
        result = service.sync("token-123")

        assert result.user_id == 7
        assert result.synced["users"] == 1
        assert result.synced["employees"] == 1

        user = db.session.get(UserCache, 7)
        employee = db.session.get(EmployeeCache, 8)
        snapshot = db.session.get(CurrentUserSnapshot, 7)
        user_state = db.session.get(ReferenceSyncState, "users")
        employee_state = db.session.get(ReferenceSyncState, "employees")

        assert user.email == "user@example.com"
        assert user.memberships[0]["company_id"] == 21
        assert employee.company_id == 21
        assert snapshot.scope_company_ids == [21]
        assert user_state.cursor_updated_at.isoformat() == "2026-03-04T00:00:00"
        assert employee_state.cursor_updated_at.isoformat() == "2026-03-04T00:00:00"

        service.sync("token-123")

        assert client.user_calls == [None, "2026-03-04T00:00:00Z"]
        assert client.employee_calls == [None, "2026-03-04T00:00:00Z"]


def test_scope_filtering_comes_from_jwt_claims(monkeypatch):
    app = make_app()

    from app.auth import decorators as auth_decorators

    monkeypatch.setattr(
        auth_decorators,
        "verify_bearer_token",
        lambda token: {
            "sub": "7",
            "roles": [],
            "companies": [21],
            "branches": [31],
            "main_groups": [11],
        },
    )

    @app.get("/protected-scope")
    @auth_decorators.require_jwt
    def protected_scope():
        companies, branches = filter_ids_to_jwt_scope([21, 22], [31, 32])
        return jsonify({"companies": companies, "branches": branches})

    response = app.test_client().get(
        "/protected-scope",
        headers={"Authorization": "Bearer token-123"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"companies": [21], "branches": [31]}


def test_auth_bootstrap_returns_cached_snapshot(monkeypatch):
    app = make_app()

    from app.auth import decorators as auth_decorators
    import app.routes.api_auth as api_auth_module

    monkeypatch.setattr(
        auth_decorators,
        "verify_bearer_token",
        lambda token: {
            "sub": "7",
            "email": "user@example.com",
            "name": "User Example",
            "roles": [],
            "companies": [21],
            "branches": [31],
            "main_groups": [11],
            "iss": "https://auth.ianeer.com",
            "aud": "billaware",
            "exp": 9999999999,
        },
    )

    class FakeSyncService:
        def sync(self, token: str) -> AuthSyncResult:
            assert token == "token-123"
            with app.app_context():
                snapshot = CurrentUserSnapshot(
                    user_id=7,
                    email="user@example.com",
                    full_name="User Example",
                    employee_id=8,
                    scope_main_group_ids=[11],
                    scope_company_ids=[21],
                    scope_branch_ids=[31],
                    user_payload={"id": 7, "email": "user@example.com"},
                    employee_payload={"id": 8},
                    scope_payload={"company_ids": [21], "branch_ids": [31], "main_group_ids": [11]},
                )
                db.session.merge(snapshot)
                db.session.commit()
            return AuthSyncResult(
                user_id=7,
                scope={"company_ids": [21], "branch_ids": [31], "main_group_ids": [11], "roles": []},
                roles=[],
                synced={"users": 1, "employees": 1},
            )

    monkeypatch.setattr(api_auth_module, "CommonAuthSyncService", FakeSyncService)

    response = app.test_client().post(
        "/api/auth/bootstrap",
        headers={"Authorization": "Bearer token-123"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["jwt_scope"]["company_ids"] == [21]
    assert payload["cache"]["scope"]["company_ids"] == [21]
    assert payload["synced"]["users"] == 1


def test_scope_expands_branches_from_cached_main_group():
    app = make_app()

    with app.app_context():
        db.session.add_all(
            [
                UserCache(id=7, email="user@example.com", full_name="User Example", main_group_id=11, active=True),
                CurrentUserSnapshot(
                    user_id=7,
                    email="user@example.com",
                    full_name="User Example",
                    scope_main_group_ids=[11],
                    scope_company_ids=[21],
                    scope_branch_ids=[31],
                    user_payload={"id": 7, "email": "user@example.com"},
                    scope_payload={"main_group_ids": [11], "company_ids": [21], "branch_ids": [31]},
                ),
                CompanyCache(id=21, main_group_id=11, name="Northwind", active=True),
                CompanyCache(id=22, main_group_id=11, name="Southwind", active=True),
                BranchCache(id=31, company_id=21, name="HQ", active=True),
                BranchCache(id=32, company_id=22, name="Warehouse", active=True),
            ]
        )
        db.session.commit()

        with app.test_request_context("/"):
            from flask_login import login_user

            login_user(db.session.get(UserCache, 7))
            assert filter_ids_to_jwt_scope(None, None) == ([21, 22], [31, 32])
