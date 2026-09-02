from urllib.parse import urlparse
from flask import Blueprint, render_template, request, redirect, url_for, session, flash, g
from werkzeug.security import check_password_hash
from ..models import User, Role, AuditLog
from ..extensions import db

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")

VALID_REGISTRATION_ROLES = ("Bodeguero", "Vendedor", "RRHH")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user is not None:
        return redirect(url_for("main.dashboard"))

    if request.method == "POST":
        username = request.form.get("username", "").strip().lower()
        password = request.form.get("password", "")

        if not username or not password:
            flash("Ingrese usuario y contrasena.", "error")
            return render_template("auth/login.html")

        user = User.query.filter_by(username=username).first()

        if user is None or not check_password_hash(user.password_hash, password):
            flash("Usuario o contrasena incorrectos.", "error")
            return render_template("auth/login.html")

        if user.account_status == "PENDIENTE":
            flash("Su cuenta esta pendiente de aprobacion. Espere la aprobacion de un administrador.", "warning")
            return render_template("auth/login.html")

        if user.account_status == "RECHAZADA":
            flash("Su cuenta no fue aprobada. Contacte al administrador.", "error")
            return render_template("auth/login.html")

        if user.account_status == "BLOQUEADA":
            flash("Su cuenta ha sido bloqueada. Contacte al administrador.", "error")
            return render_template("auth/login.html")

        if user.account_status == "INACTIVA":
            flash("Su cuenta esta inactiva. Contacte al administrador.", "error")
            return render_template("auth/login.html")

        if not user.is_active:
            flash("Su cuenta esta desactivada. Contacte al administrador.", "error")
            return render_template("auth/login.html")

        from datetime import datetime, timezone
        user.last_login = datetime.now(timezone.utc)

        session.regenerate = True
        session["user_id"] = user.id

        audit = AuditLog(
            user_id=user.id,
            action="LOGIN",
            module="AUTH",
            description=f"Inicio de sesion: {user.username}",
        )
        db.session.add(audit)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

        next_page = request.args.get("next")
        if next_page:
            parsed = urlparse(next_page)
            if parsed.netloc or not next_page.startswith("/"):
                next_page = None

        if next_page:
            return redirect(next_page)

        role_name = user.role.name if user.role else ""
        ROLE_DASHBOARDS = {
            "Bodeguero": "inventory.stock",
            "Vendedor": "sales.list",
            "RRHH": "hr.list",
            "Administrador": "main.dashboard",
        }
        default_endpoint = ROLE_DASHBOARDS.get(role_name, "main.dashboard")
        return redirect(url_for(default_endpoint))

    return render_template("auth/login.html")


@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user is not None:
        return redirect(url_for("main.dashboard"))

    roles = Role.query.filter(Role.name.in_(VALID_REGISTRATION_ROLES)).order_by(Role.name).all()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        username = request.form.get("username", "").strip().lower()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        confirm_password = request.form.get("confirm_password", "")
        requested_role_name = request.form.get("requested_role", "").strip()

        errors = []

        if not full_name:
            errors.append("El nombre completo es obligatorio.")

        if not username:
            errors.append("El nombre de usuario es obligatorio.")
        elif User.query.filter_by(username=username).first():
            errors.append(f"El usuario '{username}' ya esta registrado.")

        if not email:
            errors.append("El correo electronico es obligatorio.")
        elif User.query.filter_by(email=email).first():
            errors.append(f"El correo '{email}' ya esta registrado.")

        if not password:
            errors.append("La contrasena es obligatoria.")
        elif len(password) < 8:
            errors.append("La contrasena debe tener al menos 8 caracteres.")

        if password != confirm_password:
            errors.append("Las contrasenas no coinciden.")

        if requested_role_name == "Administrador":
            errors.append("No es posible registrarse como administrador.")

        if not requested_role_name or requested_role_name not in VALID_REGISTRATION_ROLES:
            if requested_role_name != "Administrador":
                errors.append("Seleccione un rol valido.")

        if errors:
            flash(errors[0], "error")
            return render_template(
                "auth/register.html",
                form_data=request.form,
                roles=roles,
            )

        role = Role.query.filter_by(name=requested_role_name).first()
        if not role:
            flash("El rol seleccionado no existe.", "error")
            return render_template("auth/register.html", form_data=request.form, roles=roles)

        user = User(
            username=username,
            full_name=full_name,
            email=email,
            phone=phone,
            role_id=role.id,
            is_active=False,
            account_status="PENDIENTE",
            requested_role_id=role.id,
        )
        user.set_password(password)

        db.session.add(user)

        audit = AuditLog(
            user_id=0,
            target_user_id=user.id,
            action="REGISTER",
            module="AUTH",
            description=f"Registro publico: {username} solicita rol {requested_role_name}",
            new_role_id=role.id,
            new_status="PENDIENTE",
        )
        db.session.add(audit)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Error al registrar la cuenta.", "error")
            return render_template("auth/register.html", form_data=request.form, roles=roles)

        flash("Registro exitoso. Su cuenta esta pendiente de aprobacion por un administrador.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html", form_data={}, roles=roles)


@auth_bp.route("/logout", methods=["POST"])
def logout():
    user_id = session.get("user_id")
    if user_id:
        audit = AuditLog(
            user_id=user_id,
            action="LOGOUT",
            module="AUTH",
            description="Cierre de sesion",
        )
        db.session.add(audit)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()

    session.clear()
    flash("Sesion cerrada correctamente.", "success")
    return redirect(url_for("auth.login"))


@auth_bp.route("/unauthorized")
def unauthorized():
    return render_template("auth/unauthorized.html"), 403
