from app.extensions import db
from app.models.user import User
from app.models.user_company import UserCompany


def get_user_by_id(user_id: int) -> User | None:
    return db.session.get(User, user_id)


def get_global_roles_for_user(user_id: int) -> list[str]:
    """
    Global/system-wide roles, from user.roles (many-to-many).
    """
    user = get_user_by_id(user_id)
    if not user:
        return []

    try:
        return [r.name for r in user.roles.all()]
    except Exception:
        # fallback if lazy isn't dynamic in some contexts
        return [r.name for r in user.roles]


def get_company_ids_for_user(user_id: int) -> list[int]:
    """
    Active company memberships for the user.
    """
    rows = (
        db.session.query(UserCompany.company_id)
        .filter(UserCompany.user_id == user_id, UserCompany.active.is_(True))
        .all()
    )
    return [r[0] for r in rows]
