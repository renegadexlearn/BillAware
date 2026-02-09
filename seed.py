from app import create_app
from app.extensions import db

from app.models.user import User
from app.models.role import Role
from app.models.permission import Permission
from app.models.external_app import ExternalApp, UserAppAccess

from app.models.company import Company
from app.models.branch import Branch          # NEW
from app.models.user_company import UserCompany

from app import models  # ensure all models are imported


# ============================================================
# HELPERS
# ============================================================

def get_or_create_role(name, description=None):
    role = Role.query.filter_by(name=name).first()
    if not role:
        role = Role(name=name, description=description)
        db.session.add(role)
        db.session.commit()
    return role


def get_or_create_permission(name, description=None):
    perm = Permission.query.filter_by(name=name).first()
    if not perm:
        perm = Permission(name=name, description=description)
        db.session.add(perm)
        db.session.commit()
    return perm


def get_or_create_user(email, full_name, simple_role):
    user = User.query.filter_by(email=email).first()
    if not user:
        user = User(
            email=email,
            full_name=full_name,
            role=simple_role,
            active=True,
        )
        user.set_password("aaa")
        db.session.add(user)
        db.session.commit()
    return user


def attach_permission_to_role(role, perm):
    if perm not in role.permissions:
        role.permissions.append(perm)
        db.session.commit()


def assign_role_to_user(user, role):
    if role not in user.roles:
        user.roles.append(role)
        db.session.commit()


def get_or_create_app(key, name, base_url=None, enabled=True):
    app = ExternalApp.query.filter_by(key=key).first()
    if not app:
        app = ExternalApp(
            key=key,
            name=name,
            base_url=base_url,
            enabled=enabled,
        )
        db.session.add(app)
        db.session.commit()
    return app


def grant_app_access(user, app, enabled=True, expires_at=None):
    access = UserAppAccess.query.filter_by(
        user_id=user.id,
        app_id=app.id,
    ).first()

    if not access:
        access = UserAppAccess(
            user=user,
            app=app,
            enabled=enabled,
            expires_at=expires_at,
        )
        db.session.add(access)
        db.session.commit()
    else:
        access.enabled = enabled
        access.expires_at = expires_at
        db.session.commit()

    return access


def get_or_create_company(name, active=True):
    company = Company.query.filter_by(name=name).first()
    if not company:
        company = Company(name=name, active=active)
        db.session.add(company)
        db.session.commit()
    return company


def get_company_by_name(name: str) -> Company:
    c = Company.query.filter_by(name=name).first()
    if not c:
        raise RuntimeError(f"Company not found: {name}")
    return c


def get_or_create_branch(company: Company, name: str, code: str, active=True) -> Branch:
    b = Branch.query.filter_by(company_id=company.id, code=code).first()
    if not b:
        b = Branch(company_id=company.id, name=name, code=code, active=active)
        db.session.add(b)
        db.session.commit()
    else:
        # keep idempotent
        b.name = name
        b.active = active
        db.session.commit()
    return b


def get_or_create_membership(user: User, company: Company, active=True) -> UserCompany:
    m = UserCompany.query.filter_by(user_id=user.id, company_id=company.id).first()
    if not m:
        m = UserCompany(user_id=user.id, company_id=company.id, active=active)
        db.session.add(m)
        db.session.commit()
    else:
        m.active = active
        db.session.commit()
    return m


def assign_role_to_membership(membership: UserCompany, role: Role):
    if role not in membership.roles:
        membership.roles.append(role)
        db.session.commit()


# ============================================================
# MAIN SEED
# ============================================================

def seed():
    app = create_app()

    with app.app_context():
        print("⚠️ Dropping ALL tables...")
        db.drop_all()
        db.create_all()
        print("✅ All tables recreated.")

        # ----------------------------------------------------
        # Companies
        # ----------------------------------------------------
        print("Seeding companies...")

        company_names = [
            "Anahaw Island View Resort",
            "Color Master Photo",
            "Anahaw Island Cafe",
            "Cakes by Leen",
            "Network Embassy Enterprises",
        ]

        companies = []
        for name in company_names:
            c = get_or_create_company(name)
            companies.append(c)
            print(f"  - {c.name} (id={c.id})")

        print("✅ Companies seeded.\n")

        # ----------------------------------------------------
        # Branches
        # ----------------------------------------------------
        print("Seeding branches...")

        color_master = get_company_by_name("Color Master Photo")
        cakes_by_leen = get_company_by_name("Cakes by Leen")

        # Color Master Photo branches
        color_master_branches = [
            ("Calapan", "CAL"),
            ("Network Embassy", "NEE"),
            ("Pinamalayan", "PIN"),
            ("Roxas Mindoro", "RXM"),
            ("San Jose 1", "SJ1"),
            ("San Jose 2", "SJ2"),
            ("Sablayan", "SAB"),
            ("Batangas", "BAT"),
            ("Lemery", "LEM"),
            ("Nasugbu", "NAS"),
            ("Odiongan", "ODI"),
        ]

        for name, code in color_master_branches:
            b = get_or_create_branch(color_master, name=name, code=code)
            print(f"  - Color Master Photo: {b.name} ({b.code}) id={b.id}")

        # Cakes By Leen branches
        cakes_by_leen_branches = [
            ("MMIX Calapan", "MMIX"),
            ("CBL Calapan Unitop", "CAL-UNI"),
            ("CBL Victoria", "VIC"),
            ("CBL Nuciti", "CAL-NUCT"),
            ("CBL Pinamalayan", "PIN"),
            ("CBK Roxas Mindoro", "RXM"),
            ("CBL Baco", "BACO"),
            ("CBL Barcenaga", "BARCE"),
        ]

        for name, code in cakes_by_leen_branches:
            b = get_or_create_branch(cakes_by_leen, name=name, code=code)
            print(f"  - Cakes by Leen: {b.name} ({b.code}) id={b.id}")

        # Optional: “Anahaw Group of Companies” branches (these are companies already)
        # If you want them also as branches under a single parent company later,
        # we can model a parent-company grouping. For now, they are separate companies.
        print("✅ Branches seeded.\n")

        # ----------------------------------------------------
        # Roles, permissions, users
        # ----------------------------------------------------
        print("Seeding roles, permissions, and users.")

        # --- commonAuth Roles ---
        sys_role = get_or_create_role("system_admin", "Full system access")
        owner_role = get_or_create_role("owner", "Business owner")

        # --- commonAuth Permissions ---
        users_manage = get_or_create_permission("users_manage", "Manage user accounts")
        permissions_manage = get_or_create_permission("permissions_manage", "Manage permissions")
        roles_manage = get_or_create_permission("roles_manage", "Manage roles")

        # --- BillAware Roles (assigned per company membership) ---
        billaware_encoder_role = get_or_create_role("billaware_encoder", "Can encode/capture receipts")
        billaware_auditor_role = get_or_create_role("billaware_auditor", "Can allocate/verify receipts")
        billaware_admin_role = get_or_create_role("billaware_admin", "Full BillAware control")

        # --- BillAware Permissions ---
        ba_capture = get_or_create_permission("billaware.receipt.capture", "Capture receipt + line items")
        ba_allocate = get_or_create_permission("billaware.receipt.allocate", "Allocate line items to companies")
        ba_lock = get_or_create_permission("billaware.receipt.lock", "Lock receipt after allocation")
        ba_view = get_or_create_permission("billaware.receipt.view", "View receipts")

        # role → permissions mapping
        for perm in [ba_capture, ba_view]:
            attach_permission_to_role(billaware_encoder_role, perm)

        for perm in [ba_allocate, ba_view]:
            attach_permission_to_role(billaware_auditor_role, perm)

        for perm in [ba_capture, ba_allocate, ba_lock, ba_view]:
            attach_permission_to_role(billaware_admin_role, perm)

        # System admin gets everything (commonAuth-level)
        all_perms = [users_manage, permissions_manage, roles_manage]
        for perm in all_perms:
            attach_permission_to_role(sys_role, perm)

        # Owner gets everything EXCEPT permissions_manage (commonAuth-level)
        owner_perms = [p for p in all_perms if p.name != "permissions_manage"]
        for perm in owner_perms:
            attach_permission_to_role(owner_role, perm)

        # --- Users ---
        sys_user = get_or_create_user("a@a.com", "System Admin", "sys")
        owner_user = get_or_create_user("b@b.com", "Owner Account", "owner")

        # --- External App: BillAware ---
        billaware_app = get_or_create_app(
            key="billaware",
            name="BillAware",
            base_url="https://billaware.ianeer.com",
            enabled=True,
        )

        # --- User ↔ App Access ---
        grant_app_access(sys_user, billaware_app, enabled=True)
        grant_app_access(owner_user, billaware_app, enabled=True)

        # --- Assign GLOBAL roles (commonAuth admin stuff) ---
        assign_role_to_user(sys_user, sys_role)
        assign_role_to_user(owner_user, owner_role)

        # ----------------------------------------------------
        # Company Memberships + Company-scoped BillAware roles
        # ----------------------------------------------------

        # System admin: member of ALL companies + BillAware admin everywhere
        for c in companies:
            m = get_or_create_membership(sys_user, c, active=True)
            assign_role_to_membership(m, billaware_admin_role)

        # Owner: you can tweak these; right now owner is in Cakes by Leen only
        owner_company_names = [
            "Cakes by Leen",
        ]
        for name in owner_company_names:
            c = get_company_by_name(name)
            m = get_or_create_membership(owner_user, c, active=True)
            assign_role_to_membership(m, billaware_encoder_role)

        print("\n✅ Seeding complete!")
        print("Users created:")
        print(" - a@a.com / aaa (system admin)")
        print(" - b@b.com / aaa (owner)")


if __name__ == "__main__":
    seed()
