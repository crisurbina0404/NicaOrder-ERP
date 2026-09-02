from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from ..auth import login_required, role_required
from ..models import User, Role, Permission, AuditLog
from ..extensions import db
from sqlalchemy import or_

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/users/")
@login_required
@role_required("users.manage")
def users():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()
    role_filter = request.args.get("role", "").strip()

    query = User.query

    if search:
        query = query.filter(
            or_(
                User.username.ilike(f"%{search}%"),
                User.full_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
            )
        )

    if status and status in User.VALID_STATUSES:
        query = query.filter(User.account_status == status)

    if role_filter:
        query = query.join(Role).filter(Role.name == role_filter)

    user_list = query.order_by(User.username).all()
    roles = Role.query.order_by(Role.name).all()

    return render_template(
        "admin/users/list.html",
        users=user_list,
        roles=roles,
        search=search,
        selected_status=status,
        selected_role=role_filter,
        valid_statuses=User.VALID_STATUSES,
    )


@admin_bp.route("/users/pending/")
@login_required
@role_required("users.manage")
def pending_users():
    user_list = User.query.filter_by(account_status="PENDIENTE").order_by(User.created_at).all()
    return render_template(
        "admin/users/pending.html",
        users=user_list,
    )


@admin_bp.route("/users/create", methods=["GET", "POST"])
@login_required
@role_required("users.manage")
def user_create():
    roles = Role.query.order_by(Role.name).all()

    if request.method == "POST":
        errors = _validate_user_form(request.form)

        if errors:
            flash(errors[0], "error")
            return render_template(
                "admin/users/form.html",
                form_data=request.form,
                errors=errors,
                roles=roles,
                is_edit=False,
            )

        username = request.form["username"].strip().lower()
        password = request.form["password"]

        user = User(
            username=username,
            full_name=request.form["full_name"].strip(),
            email=request.form["email"].strip(),
            phone=request.form.get("phone", "").strip(),
            role_id=int(request.form["role_id"]),
            is_active=True,
            account_status="ACTIVA",
        )
        user.set_password(password)

        db.session.add(user)
        db.session.flush()

        audit = AuditLog(
            user_id=g.user.id,
            target_user_id=user.id,
            action="CREATE",
            module="ADMIN",
            description=f"Usuario creado por administrador: {username}",
            new_role_id=user.role_id,
            new_status="ACTIVA",
        )
        db.session.add(audit)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        flash(f"Usuario {username} creado correctamente.", "success")
        return redirect(url_for("admin.users"))

    return render_template(
        "admin/users/form.html",
        form_data={},
        errors={},
        roles=roles,
        is_edit=False,
    )


@admin_bp.route("/users/<int:user_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("users.manage")
def user_edit(user_id):
    user = User.query.get_or_404(user_id)
    roles = Role.query.order_by(Role.name).all()

    if request.method == "POST":
        errors = _validate_user_form(request.form, exclude_username=user.username, exclude_email=user.email)

        if errors:
            flash(errors[0], "error")
            return render_template(
                "admin/users/form.html",
                user=user,
                form_data=request.form,
                errors=errors,
                roles=roles,
                is_edit=True,
            )

        old_role_id = user.role_id
        user.username = request.form["username"].strip().lower()
        user.full_name = request.form["full_name"].strip()
        user.email = request.form["email"].strip()
        user.phone = request.form.get("phone", "").strip()
        user.role_id = int(request.form["role_id"])

        new_password = request.form.get("password", "").strip()
        if new_password:
            user.set_password(new_password)

        audit = AuditLog(
            user_id=g.user.id,
            target_user_id=user.id,
            action="UPDATE",
            module="ADMIN",
            description=f"Usuario actualizado: {user.username}",
            previous_role_id=old_role_id,
            new_role_id=user.role_id,
        )
        db.session.add(audit)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        flash(f"Usuario {user.username} actualizado correctamente.", "success")
        return redirect(url_for("admin.users"))

    return render_template(
        "admin/users/form.html",
        user=user,
        form_data={
            "username": user.username,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone or "",
            "role_id": user.role_id,
        },
        errors={},
        roles=roles,
        is_edit=True,
    )


@admin_bp.route("/users/<int:user_id>/approve", methods=["POST"])
@login_required
@role_required("users.manage")
def user_approve(user_id):
    user = User.query.get_or_404(user_id)

    if user.account_status != "PENDIENTE":
        flash("Esta cuenta no esta pendiente de aprobacion.", "error")
        return redirect(url_for("admin.pending_users"))

    new_role_id = int(request.form.get("role_id", user.requested_role_id or user.role_id))
    new_role = Role.query.get(new_role_id)
    if not new_role:
        flash("Rol invalido.", "error")
        return redirect(url_for("admin.pending_users"))

    old_role_id = user.role_id
    user.role_id = new_role_id
    user.account_status = "ACTIVA"
    user.is_active = True
    user.approved_by = g.user.id
    user.approved_at = datetime.utcnow()
    user.requested_role_id = None

    audit = AuditLog(
        user_id=g.user.id,
        target_user_id=user.id,
        action="APPROVE",
        module="ADMIN",
        description=f"Cuenta aprobada: {user.username} - Rol: {new_role.name}",
        previous_role_id=old_role_id,
        new_role_id=new_role_id,
        previous_status="PENDIENTE",
        new_status="ACTIVA",
    )
    db.session.add(audit)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    flash(f"Cuenta de {user.username} aprobada. Rol asignado: {new_role.name}.", "success")
    return redirect(url_for("admin.pending_users"))


@admin_bp.route("/users/<int:user_id>/reject", methods=["POST"])
@login_required
@role_required("users.manage")
def user_reject(user_id):
    user = User.query.get_or_404(user_id)

    if user.account_status != "PENDIENTE":
        flash("Esta cuenta no esta pendiente de aprobacion.", "error")
        return redirect(url_for("admin.pending_users"))

    reason = request.form.get("reason", "").strip()
    old_status = user.account_status
    user.account_status = "RECHAZADA"
    user.is_active = False
    user.rejection_reason = reason

    audit = AuditLog(
        user_id=g.user.id,
        target_user_id=user.id,
        action="REJECT",
        module="ADMIN",
        description=f"Cuenta rechazada: {user.username}",
        previous_status=old_status,
        new_status="RECHAZADA",
        reason=reason,
    )
    db.session.add(audit)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    flash(f"Cuenta de {user.username} rechazada.", "success")
    return redirect(url_for("admin.pending_users"))


@admin_bp.route("/users/<int:user_id>/block", methods=["POST"])
@login_required
@role_required("users.manage")
def user_block(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == g.user.id:
        flash("No puede bloquear su propio usuario.", "error")
        return redirect(url_for("admin.users"))

    old_status = user.account_status
    user.account_status = "BLOQUEADA"
    user.is_active = False

    audit = AuditLog(
        user_id=g.user.id,
        target_user_id=user.id,
        action="BLOCK",
        module="ADMIN",
        description=f"Usuario bloqueado: {user.username}",
        previous_status=old_status,
        new_status="BLOQUEADA",
    )
    db.session.add(audit)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    flash(f"Usuario {user.username} bloqueado.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/toggle", methods=["POST"])
@login_required
@role_required("users.manage")
def user_toggle(user_id):
    user = User.query.get_or_404(user_id)

    if user.id == g.user.id:
        flash("No puede desactivar su propio usuario.", "error")
        return redirect(url_for("admin.users"))

    old_status = user.account_status
    if user.account_status == "ACTIVA":
        user.account_status = "INACTIVA"
        user.is_active = False
        new_status_label = "desactivado"
    else:
        user.account_status = "ACTIVA"
        user.is_active = True
        new_status_label = "activado"

    audit = AuditLog(
        user_id=g.user.id,
        target_user_id=user.id,
        action="TOGGLE",
        module="ADMIN",
        description=f"Usuario {new_status_label}: {user.username}",
        previous_status=old_status,
        new_status=user.account_status,
    )
    db.session.add(audit)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    flash(f"Usuario {new_status_label} correctamente.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@login_required
@role_required("users.manage")
def user_reset_password(user_id):
    user = User.query.get_or_404(user_id)
    new_password = request.form.get("new_password", "").strip()

    if not new_password or len(new_password) < 8:
        flash("La contrasena debe tener al menos 8 caracteres.", "error")
        return redirect(url_for("admin.users"))

    user.set_password(new_password)

    audit = AuditLog(
        user_id=g.user.id,
        target_user_id=user.id,
        action="UPDATE",
        module="ADMIN",
        description=f"Contrasena reiniciada para: {user.username}",
    )
    db.session.add(audit)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    flash(f"Contrasena de {user.username} reiniciada correctamente.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.route("/roles/")
@login_required
@role_required("roles.manage")
def roles():
    role_list = Role.query.order_by(Role.name).all()
    return render_template(
        "admin/roles/list.html",
        roles=role_list,
    )


@admin_bp.route("/roles/create", methods=["GET", "POST"])
@login_required
@role_required("roles.manage")
def role_create():
    permissions = Permission.query.order_by(Permission.name).all()

    if request.method == "POST":
        errors = _validate_role_form(request.form)

        if errors:
            flash(errors[0], "error")
            return render_template(
                "admin/roles/form.html",
                form_data=request.form,
                errors=errors,
                permissions=permissions,
                is_edit=False,
            )

        role = Role(
            name=request.form["name"].strip(),
            description=request.form.get("description", "").strip(),
        )
        db.session.add(role)
        db.session.flush()

        selected_perms = request.form.getlist("permissions")
        role.permissions = [
            Permission.query.get(int(pid)) for pid in selected_perms
        ]

        audit = AuditLog(
            user_id=g.user.id,
            action="CREATE",
            module="ADMIN",
            description=f"Rol creado: {role.name}",
        )
        db.session.add(audit)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        flash(f"Rol {role.name} creado correctamente.", "success")
        return redirect(url_for("admin.roles"))

    return render_template(
        "admin/roles/form.html",
        form_data={},
        errors={},
        permissions=permissions,
        is_edit=False,
    )


@admin_bp.route("/roles/<int:role_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("roles.manage")
def role_edit(role_id):
    role = Role.query.get_or_404(role_id)
    permissions = Permission.query.order_by(Permission.name).all()

    if request.method == "POST":
        errors = _validate_role_form(request.form, exclude_name=role.name)

        if errors:
            flash(errors[0], "error")
            return render_template(
                "admin/roles/form.html",
                role=role,
                form_data=request.form,
                errors=errors,
                permissions=permissions,
                is_edit=True,
            )

        role.name = request.form["name"].strip()
        role.description = request.form.get("description", "").strip()

        selected_perms = request.form.getlist("permissions")
        role.permissions = [
            Permission.query.get(int(pid)) for pid in selected_perms
        ]

        audit = AuditLog(
            user_id=g.user.id,
            action="UPDATE",
            module="ADMIN",
            description=f"Rol actualizado: {role.name}",
        )
        db.session.add(audit)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        flash(f"Rol {role.name} actualizado correctamente.", "success")
        return redirect(url_for("admin.roles"))

    return render_template(
        "admin/roles/form.html",
        role=role,
        form_data=role,
        errors={},
        permissions=permissions,
        is_edit=True,
    )


@admin_bp.route("/audit/")
@login_required
@role_required("audit.view")
def audit_log():
    page = request.args.get("page", 1, type=int)
    per_page = 50
    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    return render_template(
        "admin/audit/list.html",
        logs=logs,
    )


def _validate_user_form(form, exclude_username=None, exclude_email=None):
    errors = []

    username = form.get("username", "").strip()
    full_name = form.get("full_name", "").strip()
    email = form.get("email", "").strip()
    role_id = form.get("role_id", "").strip()

    if not username:
        errors.append("El nombre de usuario es obligatorio.")
    elif exclude_username is None or username != exclude_username:
        existing = User.query.filter_by(username=username).first()
        if existing:
            errors.append(f"El usuario '{username}' ya esta registrado.")

    if not full_name:
        errors.append("El nombre completo es obligatorio.")

    if not email:
        errors.append("El email es obligatorio.")
    elif exclude_email is None or email != exclude_email:
        existing = User.query.filter_by(email=email).first()
        if existing:
            errors.append(f"El email '{email}' ya esta registrado.")

    if not role_id:
        errors.append("Seleccione un rol.")

    if not exclude_username:
        password = form.get("password", "").strip()
        if not password:
            errors.append("La contrasena es obligatoria.")
        elif len(password) < 8:
            errors.append("La contrasena debe tener al menos 8 caracteres.")

    return errors


def _validate_role_form(form, exclude_name=None):
    errors = []

    name = form.get("name", "").strip()

    if not name:
        errors.append("El nombre del rol es obligatorio.")
    elif exclude_name is None or name != exclude_name:
        existing = Role.query.filter_by(name=name).first()
        if existing:
            errors.append(f"El rol '{name}' ya esta registrado.")

    return errors
