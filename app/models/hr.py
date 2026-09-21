from datetime import datetime, timezone, date
from ..extensions import db


class Employee(db.Model):
    __tablename__ = "empleados"

    id = db.Column(db.Integer, primary_key=True)
    employee_code = db.Column("codigo_empleado", db.String(30), unique=True, nullable=False)
    first_name = db.Column("primer_nombre", db.String(100), nullable=False)
    last_name = db.Column("primer_apellido", db.String(100), nullable=False)
    identity_number = db.Column("cedula", db.String(50), unique=True, nullable=False)
    birth_date = db.Column("fecha_nacimiento", db.Date, nullable=True)
    phone = db.Column("telefono", db.String(30), nullable=True)
    email = db.Column("correo", db.String(120), nullable=True)
    address = db.Column("direccion", db.String(300), nullable=True)
    department_id = db.Column(
        "departamento_id", db.Integer, db.ForeignKey("departamentos.id"), nullable=False
    )
    position_id = db.Column(
        "cargo_id", db.Integer, db.ForeignKey("cargos.id"), nullable=False
    )
    hire_date = db.Column("fecha_contratacion", db.Date, nullable=False)
    contract_type = db.Column("tipo_contrato", db.String(30), nullable=False, default="INDEFINIDO")
    base_salary = db.Column("salario_base", db.Float, nullable=False, default=0.0)
    status = db.Column("estado", db.String(20), nullable=False, default="ACTIVO")
    created_at = db.Column(
        "fecha_creacion", db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    department = db.relationship("Department", backref="employees")
    position = db.relationship("Position", backref="employees")
    salary_history = db.relationship(
        "SalaryHistory", back_populates="employee", lazy=True,
        order_by="SalaryHistory.start_date.desc()"
    )

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    @property
    def age(self):
        if self.birth_date:
            today = date.today()
            return today.year - self.birth_date.year - (
                (today.month, today.day) < (self.birth_date.month, self.birth_date.day)
            )
        return None

    @property
    def current_salary(self):
        today = date.today()
        for record in self.salary_history:
            if record.end_date is None or record.end_date >= today:
                return record.salary
        return self.base_salary

    @property
    def years_of_service(self):
        today = date.today()
        return today.year - self.hire_date.year - (
            (today.month, today.day) < (self.hire_date.month, self.hire_date.day)
        )

    def __repr__(self):
        return f"<Employee {self.employee_code} - {self.full_name}>"


class SalaryHistory(db.Model):
    __tablename__ = "historial_salarios"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        "empleado_id", db.Integer, db.ForeignKey("empleados.id"), nullable=False
    )
    salary = db.Column("salario", db.Float, nullable=False)
    start_date = db.Column("fecha_inicio", db.Date, nullable=False)
    end_date = db.Column("fecha_fin", db.Date, nullable=True)
    reason = db.Column("motivo", db.String(200), nullable=True)
    created_at = db.Column(
        "fecha_creacion", db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    employee = db.relationship("Employee", back_populates="salary_history")

    def __repr__(self):
        return f"<SalaryHistory {self.employee_id} - {self.salary}>"
