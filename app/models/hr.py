from datetime import datetime, timezone, date
from ..extensions import db


class Employee(db.Model):
    __tablename__ = "employees"

    id = db.Column(db.Integer, primary_key=True)
    employee_code = db.Column(db.String(30), unique=True, nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    identity_number = db.Column(db.String(50), unique=True, nullable=False)
    birth_date = db.Column(db.Date, nullable=True)
    phone = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.String(300), nullable=True)
    department_id = db.Column(
        db.Integer, db.ForeignKey("departments.id"), nullable=False
    )
    position_id = db.Column(
        db.Integer, db.ForeignKey("positions.id"), nullable=False
    )
    hire_date = db.Column(db.Date, nullable=False)
    contract_type = db.Column(db.String(30), nullable=False, default="INDEFINIDO")
    base_salary = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(20), nullable=False, default="ACTIVO")
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
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
    __tablename__ = "salary_history"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer, db.ForeignKey("employees.id"), nullable=False
    )
    salary = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=True)
    reason = db.Column(db.String(200), nullable=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    employee = db.relationship("Employee", back_populates="salary_history")

    def __repr__(self):
        return f"<SalaryHistory {self.employee_id} - {self.salary}>"
