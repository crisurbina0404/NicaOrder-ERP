from datetime import datetime, timezone
from ..extensions import db


class PayrollParameter(db.Model):
    __tablename__ = "parametros_nomina"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column("nombre", db.String(100), unique=True, nullable=False)
    value = db.Column("valor", db.Float, nullable=False)
    description = db.Column("descripcion", db.String(300), nullable=True)
    start_date = db.Column("fecha_inicio", db.Date, nullable=True)
    end_date = db.Column("fecha_fin", db.Date, nullable=True)
    is_active = db.Column("activo", db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        "fecha_creacion", db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def __repr__(self):
        return f"<PayrollParameter {self.name} = {self.value}>"


class IncomeTaxBracket(db.Model):
    __tablename__ = "tramos_ir"

    id = db.Column(db.Integer, primary_key=True)
    lower_limit = db.Column("limite_inferior", db.Float, nullable=False)
    upper_limit = db.Column("limite_superior", db.Float, nullable=True)
    base_tax = db.Column("impuesto_base", db.Float, nullable=False, default=0.0)
    excess_percentage = db.Column("porcentaje_exceso", db.Float, nullable=False, default=0.0)
    year = db.Column("anio", db.Integer, nullable=False)
    is_active = db.Column("activo", db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        "fecha_creacion", db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    def __repr__(self):
        return f"<IncomeTaxBracket {self.lower_limit} - {self.upper_limit}>"


class PayrollPeriod(db.Model):
    __tablename__ = "periodos_nomina"

    id = db.Column(db.Integer, primary_key=True)
    month = db.Column("mes", db.Integer, nullable=False)
    year = db.Column("anio", db.Integer, nullable=False)
    start_date = db.Column("fecha_inicio", db.Date, nullable=False)
    end_date = db.Column("fecha_fin", db.Date, nullable=False)
    status = db.Column("estado", db.String(20), nullable=False, default="ABIERTO")
    created_at = db.Column(
        "fecha_creacion", db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    __table_args__ = (
        db.UniqueConstraint("mes", "anio", name="uq_periodo_mes_anio"),
    )

    payrolls = db.relationship("Payroll", back_populates="period", lazy=True)

    def __repr__(self):
        return f"<PayrollPeriod {self.month}/{self.year} - {self.status}>"


class Payroll(db.Model):
    __tablename__ = "nominas"

    id = db.Column(db.Integer, primary_key=True)
    payroll_period_id = db.Column(
        "periodo_nomina_id", db.Integer, db.ForeignKey("periodos_nomina.id"), nullable=False
    )
    user_id = db.Column("usuario_id", db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    generated_at = db.Column("fecha_generacion", db.DateTime, nullable=False)
    total_income = db.Column("total_ingresos", db.Float, nullable=False, default=0.0)
    total_deductions = db.Column("total_deducciones", db.Float, nullable=False, default=0.0)
    total_net = db.Column("total_neto", db.Float, nullable=False, default=0.0)
    status = db.Column("estado", db.String(20), nullable=False, default="BORRADOR")
    created_at = db.Column(
        "fecha_creacion", db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
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
    __tablename__ = "detalle_nominas"

    id = db.Column(db.Integer, primary_key=True)
    payroll_id = db.Column("nomina_id", db.Integer, db.ForeignKey("nominas.id"), nullable=False)
    employee_id = db.Column(
        "empleado_id", db.Integer, db.ForeignKey("empleados.id"), nullable=False
    )
    base_salary = db.Column("salario_base", db.Float, nullable=False, default=0.0)
    overtime = db.Column("horas_extra", db.Float, nullable=False, default=0.0)
    bonuses = db.Column("bonificaciones", db.Float, nullable=False, default=0.0)
    commissions = db.Column("comisiones", db.Float, nullable=False, default=0.0)
    gross_salary = db.Column("salario_bruto", db.Float, nullable=False, default=0.0)
    employee_inss = db.Column("inss_empleado", db.Float, nullable=False, default=0.0)
    annual_taxable_income = db.Column("gravado_anual", db.Float, nullable=False, default=0.0)
    tax_bracket_id = db.Column(
        "tramo_ir_id", db.Integer, db.ForeignKey("tramos_ir.id"), nullable=True
    )
    annual_income_tax = db.Column("ir_anual", db.Float, nullable=False, default=0.0)
    monthly_income_tax = db.Column("ir_mensual", db.Float, nullable=False, default=0.0)
    other_deductions = db.Column("otras_deducciones", db.Float, nullable=False, default=0.0)
    net_salary = db.Column("salario_neto", db.Float, nullable=False, default=0.0)
    payment_status = db.Column("estado_pago", db.String(20), nullable=False, default="PENDIENTE")
    payment_date = db.Column("fecha_pago", db.Date, nullable=True)
    payment_method = db.Column("metodo_pago", db.String(30), nullable=True)

    payroll = db.relationship("Payroll", back_populates="items")
    employee = db.relationship("Employee")
    tax_bracket = db.relationship("IncomeTaxBracket")

    def __repr__(self):
        return f"<PayrollItem {self.employee_id} - {self.net_salary}>"


class PayrollAdjustment(db.Model):
    __tablename__ = "ajustes_nomina"

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(
        "empleado_id", db.Integer, db.ForeignKey("empleados.id"), nullable=False
    )
    payroll_period_id = db.Column(
        "periodo_nomina_id", db.Integer, db.ForeignKey("periodos_nomina.id"), nullable=False
    )
    adjustment_type = db.Column("tipo_ajuste", db.String(30), nullable=False)
    description = db.Column("descripcion", db.String(200), nullable=True)
    amount = db.Column("monto", db.Float, nullable=False, default=0.0)
    affects_income_tax = db.Column("afecta_ir", db.Boolean, default=True, nullable=False)
    affects_social_security = db.Column("afecta_inss", db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        "fecha_creacion", db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    employee = db.relationship("Employee")
    period = db.relationship("PayrollPeriod")

    def __repr__(self):
        return f"<PayrollAdjustment {self.adjustment_type} - {self.amount}>"
