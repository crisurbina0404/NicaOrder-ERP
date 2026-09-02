from datetime import datetime, timezone
from werkzeug.security import generate_password_hash
from ..extensions import db


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(200), nullable=True)

    users = db.relationship("User", back_populates="role", foreign_keys="[User.role_id]", lazy=True)
    permissions = db.relationship(
        "Permission", secondary="role_permissions", back_populates="roles", lazy=True
    )

    def has_permission(self, perm_name):
        return any(p.name == perm_name for p in self.permissions)

    def __repr__(self):
        return f"<Role {self.name}>"


class Permission(db.Model):
    __tablename__ = "permissions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(200), nullable=True)
    module = db.Column(db.String(50), nullable=True)

    roles = db.relationship(
        "Role", secondary="role_permissions", back_populates="permissions", lazy=True
    )

    def __repr__(self):
        return f"<Permission {self.name}>"


class RolePermission(db.Model):
    __tablename__ = "role_permissions"

    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), primary_key=True)
    permission_id = db.Column(
        db.Integer, db.ForeignKey("permissions.id"), primary_key=True
    )


class User(db.Model):
    __tablename__ = "users"

    VALID_STATUSES = ("PENDIENTE", "ACTIVA", "RECHAZADA", "BLOQUEADA", "INACTIVA")

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    account_status = db.Column(db.String(20), default="ACTIVA", nullable=False)
    requested_role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    approved_at = db.Column(db.DateTime, nullable=True)
    rejection_reason = db.Column(db.String(500), nullable=True)
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    role = db.relationship("Role", foreign_keys=[role_id], back_populates="users")
    requested_role = db.relationship("Role", foreign_keys=[requested_role_id])
    approver = db.relationship("User", foreign_keys=[approved_by])
    audit_logs = db.relationship(
        "AuditLog", backref="user", foreign_keys="[AuditLog.user_id]", lazy=True, cascade="save-update, merge"
    )

    def set_password(self, password):
        if len(password) < 8:
            raise ValueError("La contrasena debe tener al menos 8 caracteres.")
        self.password_hash = generate_password_hash(password)

    def has_permission(self, perm_name):
        if self.role is None:
            return False
        return self.role.has_permission(perm_name)

    @property
    def is_approved(self):
        return self.account_status == "ACTIVA" and self.is_active

    def __repr__(self):
        return f"<User {self.username}>"


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<Department {self.name}>"


class Position(db.Model):
    __tablename__ = "positions"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.String(200), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    def __repr__(self):
        return f"<Position {self.name}>"


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    target_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(50), nullable=False)
    module = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(500), nullable=True)
    previous_role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=True)
    new_role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=True)
    previous_status = db.Column(db.String(20), nullable=True)
    new_status = db.Column(db.String(20), nullable=True)
    reason = db.Column(db.String(500), nullable=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    target_user = db.relationship("User", foreign_keys=[target_user_id])
    previous_role = db.relationship("Role", foreign_keys=[previous_role_id])
    new_role = db.relationship("Role", foreign_keys=[new_role_id])

    def __repr__(self):
        return f"<AuditLog {self.action} by user {self.user_id}>"
