from functools import wraps
from flask import session, redirect, url_for, request, g
from .models import User


def load_user():
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
    else:
        user = User.query.get(user_id)
        if user is None or not user.is_active or user.account_status != "ACTIVA":
            session.clear()
            g.user = None
        else:
            g.user = user


def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def role_required(permission_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if g.user is None:
                return redirect(url_for("auth.login", next=request.url))
            if g.user.role is None:
                return redirect(url_for("auth.unauthorized"))
            if not g.user.has_permission(permission_name):
                return redirect(url_for("auth.unauthorized"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def permission_required(permission_name):
    return role_required(permission_name)
