# app/utils/permissions.py

from functools import wraps
from flask import abort
from flask_login import current_user

def permission_required(permission_name):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                # let your login_required handle redirect; here we abort 401
                abort(401)
            if not current_user.has_permission(permission_name):
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator

def role_required(role_name):
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not current_user.has_role(role_name):
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator
