from datetime import datetime, timezone
from ..extensions import db


class PayrollParameter(db.Model):
    __tablename__ = "payroll_parameters"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Float, nullable=False)
    description = db.Column(db.String(300), nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    end_date = db.Column(db.Date, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def __repr__(self):
        return f"<PayrollParameter {self.name} = {self.value}>"


class IncomeTaxBracket(db.Model):
    __tablename__ = "income_tax_brackets"

    id = db.Column(db.Integer, primary_key=True)
    lower_limit = db.Column(db.Float, nullable=False)
    upper_limit = db.Column(db.Float, nullable=True)
    base_tax = db.Column(db.Float, nullable=False, default=0.0)
    excess_percentage = db.Column(db.Float, nullable=False, default=0.0)
    year = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def __repr__(self):
        return f"<IncomeTaxBracket {self.lower_limit} - {self.upper_limit}>"


class PayrollPeriod(db.Model):
    __tablename__ = "payroll_periods"

    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.Integer, nullable=False)
    year = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="ABIERTO")
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint("month", "year", name="uq_period_month_year"),
    )

    payrolls = db.relationship("Payroll", back_populates="period", lazy=True)

    def __repr__(self):
        return f"<PayrollPeriod {self.month}/{self.year} - {self.status}>"


class Payroll(db.Model):
    __tablename__ = "payrolls"

    id = db.Column(db.Integer, primary_key=True)
    payroll_period_id = db.Column(
        db.Integer, db.ForeignKey("payroll_periods.id"), nullable=False
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    generated_at = db.Column(db.DateTime, nullable=False)
    total_income = db.Column(db.Float, nullable=False, default=0.0)
    total_deductions = db.Column(db.Float, nullable=False, default=0.0)
    total_net = db.Column(db.Float, nullable=False, default=0.0)
    status = db.Column(db.String(20), nullable=False, default="BORRADOR")
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    period = db.relationship("PayrollPeriod", back_populates="payrolls")
    user = db.relationship("User", backref="payrolls")
    items = db.relationship(
        "PayrollItem", back_populates="payroll", lazy=True,
        cascade="all, delete-orphan"
    )

    def recalculate_totals(self):
        self.total_income = sum(item.gross_salary for item in self.items)
        self.total_deductions = sum(
            item.employee_inss + item.monthly_income_tax + item.other_deductions
            for item in self.items
        )
        self.total_net = sum(item.net_salary for item in self.items)

    def __repr__(self):
        return f"<Payroll {self.id} - {self.status}>"


class PayrollItem(db.Model):
    __tablename__ = "payroll_items"

    id = db.Column(db.Integer, primary_key=True)
    payroll_id = db.Column(db.Integer, db.ForeignKey("payrolls.id"), nullable=False)
    employee_id = db.Column(
        db.Integer, db.ForeignKey("employees.id"), nullable=False
    )
    base_salary = db.Column(db.Float, nullable=False, default=0.0)
    overtime = db.Column(db.Float, nullable=False, default=0.0)
    bonuses = db.Column(db.Float, nullable=False, default=0.0)
    commissions = db.Column(db.Float, nullable=False, default=0.0)
    gross_salary = db.Column(db.Float, nullable=False, default=0.0)
    employee_inss = db.Column(db.Float, nullable=False, default=0.0)
    annual_taxable_income = db.Column(db.Float, nullable=False, default=0.0)
    tax_bracket_id = db.Column(
        db.Integer, db.ForeignKey("income_tax_brackets.id"), nullable=True
    )
    annual_income_tax = db.Column(db.Float, nullable=False, default=0.0)
    monthly_income_tax = db.Column(db.Float, nullable=False, default=0.0)
    other_deductions = db.Column(db.Float, nullable=False, default=0.0)
    net_salary = db.Column(db.Float, nullable=False, default=0.0)
    payment_status = db.Column(db.String(20), nullable=False, default="PENDIENTE")
    payment_date = db.Column(db.Date, nullable=True)
    payment_method = db.Column(db.String(30), nullable=True)

    payroll = db.relationship("Payroll", back_populates="items")
    employee = db.relationship("Employee")
    tax_bracket = db.relationship("IncomeTaxBracket")

    def __repr__(self):
        return f"<PayrollItem {self.employee_id} - {self.net_salary}>"


class PayrollAdjustment(db.Model):
    __tablename__ = "payroll_adjustments"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        db.Integer, db.ForeignKey("employees.id"), nullable=False
    )
    payroll_period_id = db.Column(
        db.Integer, db.ForeignKey("payroll_periods.id"), nullable=False
    )
    adjustment_type = db.Column(db.String(30), nullable=False)
    description = db.Column(db.String(200), nullable=True)
    amount = db.Column(db.Float, nullable=False, default=0.0)
    affects_income_tax = db.Column(db.Boolean, default=True, nullable=False)
    affects_social_security = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    employee = db.relationship("Employee")
    period = db.relationship("PayrollPeriod")

    def __repr__(self):
        return f"<PayrollAdjustment {self.adjustment_type} - {self.amount}>"
