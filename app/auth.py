import re
from functools import wraps
from flask import session, redirect, url_for, request, g
from .models import User

# ===== VALIDADORES DE DATOS DE USUARIO =====

PHONE_RE = re.compile(r"^[578]\d{7}$")


def normalize_phone(raw):
    """Elimina espacios, guiones y parentesis de un telefono."""
    return re.sub(r"[\s\-()]", "", (raw or "")).strip()


def validate_phone(phone):
    """Telefono opcional: exactamente 8 digitos, inicia con 5, 7 u 8. None si es valido."""
    if not phone:
        return None
    if not PHONE_RE.match(phone):
        return "El telefono debe tener 8 digitos e iniciar con 5, 7 u 8."
    return None


def validate_full_name(full_name):
    if len(full_name) > 50:
        return "El nombre completo no debe exceder 50 caracteres."
    return None


def validate_username(username):
    if len(username) > 25:
        return "El nombre de usuario no debe exceder 25 caracteres."
    return None


def validate_email(email):
    if "@" not in email:
        return "Ingrese un correo electronico valido."
    local_part = email.split("@")[0]
    if len(local_part) > 64:
        return "La parte del correo antes del @ no debe exceder 64 caracteres."
    if len(email) > 120:
        return "El correo electronico no debe exceder 120 caracteres."
    return None


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
