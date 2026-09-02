from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from ..auth import login_required, role_required
from ..models import (
    PayrollParameter, IncomeTaxBracket, PayrollPeriod,
    Payroll, PayrollItem, PayrollAdjustment, Employee, AuditLog,
)
from ..extensions import db
from ..services.payroll_services import (
    calculate_full_payroll, get_param,
)

payroll_bp = Blueprint("payroll", __name__, url_prefix="/payroll")

MONTH_NAMES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]

VALID_STATUSES = ["BORRADOR", "CALCULADA", "APROBADA", "PAGADA", "ANULADA"]

ADJUSTMENT_TYPES = {
    "HORA_EXTRA": ("Horas Extra", True, True),
    "BONIFICACION": ("Bonificacion", True, True),
    "COMISION": ("Comision", True, True),
    "PRESTAMO": ("Prestamo", False, False),
    "ANTICIPO": ("Anticipo", False, False),
    "AUSENCIA": ("Ausencia", False, False),
    "OTRA_DEDUCCION": ("Otra Deduccion", False, False),
}


@payroll_bp.route("/")
@login_required
@role_required("payroll.manage")
def index():
    periods = PayrollPeriod.query.order_by(
        PayrollPeriod.year.desc(), PayrollPeriod.month.desc()
    ).limit(24).all()
    return render_template(
        "payroll/index.html",
        periods=periods,
        month_names=MONTH_NAMES,
        active_page="payroll.index",
    )


@payroll_bp.route("/period/create", methods=["GET", "POST"])
@login_required
@role_required("payroll.manage")
def create_period():
    if request.method == "GET":
        return render_template(
            "payroll/period_form.html",
            month_names=MONTH_NAMES,
                active_page="payroll.index",
        )

    try:
        month = int(request.form["month"])
        year = int(request.form["year"])
    except (ValueError, KeyError):
        flash("Periodo invalido.", "error")
        return redirect(url_for("payroll.create_period"))

    if month < 1 or month > 12:
        flash("Mes invalido.", "error")
        return redirect(url_for("payroll.create_period"))

    existing = PayrollPeriod.query.filter_by(month=month, year=year).first()
    if existing:
        flash("Este periodo ya existe.", "error")
        return redirect(url_for("payroll.create_period"))

    start_date = date(year, month, 1)
    if month == 12:
        end_date = date(year + 1, 1, 1)
    else:
        end_date = date(year, month + 1, 1)

    period = PayrollPeriod(
        month=month,
        year=year,
        start_date=start_date,
        end_date=end_date,
        status="ABIERTO",
    )
    db.session.add(period)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    flash(f"Periodo {MONTH_NAMES[month]} {year} creado.", "success")
    return redirect(url_for("payroll.index"))


@payroll_bp.route("/adjustments/<int:period_id>")
@login_required
@role_required("payroll.manage")
def adjustments(period_id):
    period = PayrollPeriod.query.get_or_404(period_id)
    employees = Employee.query.filter_by(status="ACTIVO").order_by(
        Employee.last_name, Employee.first_name
    ).all()

    existing_adjustments = PayrollAdjustment.query.filter_by(
        payroll_period_id=period_id
    ).order_by(PayrollAdjustment.created_at.desc()).all()

    return render_template(
        "payroll/adjustments.html",
        period=period,
        employees=employees,
        adjustments=existing_adjustments,
        adjustment_types=ADJUSTMENT_TYPES,
        month_names=MONTH_NAMES,
        active_page="payroll.index",
    )


@payroll_bp.route("/adjustment/create", methods=["POST"])
@login_required
@role_required("payroll.manage")
def create_adjustment():
    try:
        employee_id = int(request.form["employee_id"])
        period_id = int(request.form["period_id"])
        adjustment_type = request.form["adjustment_type"]
        amount = float(request.form["amount"])
    except (ValueError, KeyError):
        flash("Datos invalidos.", "error")
        return redirect(url_for("payroll.index"))

    if amount <= 0:
        flash("El monto debe ser mayor a cero.", "error")
        return redirect(url_for("payroll.adjustments", period_id=period_id))

    if adjustment_type not in ADJUSTMENT_TYPES:
        flash("Tipo de ajuste invalido.", "error")
        return redirect(url_for("payroll.adjustments", period_id=period_id))

    _, affects_tax, affects_ss = ADJUSTMENT_TYPES[adjustment_type]

    adjustment = PayrollAdjustment(
        employee_id=employee_id,
        payroll_period_id=period_id,
        adjustment_type=adjustment_type,
        description=request.form.get("description", "").strip(),
        amount=amount,
        affects_income_tax=affects_tax,
        affects_social_security=affects_ss,
    )
    db.session.add(adjustment)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    flash("Novedad registrada.", "success")
    return redirect(url_for("payroll.adjustments", period_id=period_id))


@payroll_bp.route("/adjustment/<int:adjustment_id>/delete", methods=["POST"])
@login_required
@role_required("payroll.manage")
def delete_adjustment(adjustment_id):
    adjustment = PayrollAdjustment.query.get_or_404(adjustment_id)
    period_id = adjustment.payroll_period_id

    audit = AuditLog(
        user_id=g.user.id,
        action="DELETE",
        module="PAYROLL",
        description=f"Ajuste de nomina eliminado: {adjustment.adjustment_type} - {adjustment.description} (Empleado #{adjustment.employee_id})",
    )
    db.session.add(audit)
    db.session.delete(adjustment)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    flash("Novedad eliminada.", "success")
    return redirect(url_for("payroll.adjustments", period_id=period_id))


@payroll_bp.route("/calculate", methods=["GET", "POST"])
@login_required
@role_required("payroll.manage")
def calculate():
    periods = PayrollPeriod.query.filter(
        PayrollPeriod.status.in_(["ABIERTO", "CALCULADA"])
    ).order_by(PayrollPeriod.year.desc(), PayrollPeriod.month.desc()).all()

    if request.method == "POST":
        try:
            period_id = int(request.form["period_id"])
        except (ValueError, KeyError):
            flash("Seleccione un periodo valido.", "error")
            return render_template(
                "payroll/calculate.html",
                periods=periods,
                month_names=MONTH_NAMES,
                active_page="payroll.index",
            )

        period = PayrollPeriod.query.get(period_id)
        if not period or period.status in ("APROBADA", "PAGADA", "ANULADA"):
            flash("No se puede calcular este periodo.", "error")
            return redirect(url_for("payroll.calculate"))

        payroll = calculate_full_payroll(period_id, g.user.id)
        if payroll:
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                raise
            flash(
                f"Nomina calculada: {len(payroll.items)} empleado(s), "
                f"Total neto: C$ {payroll.total_net:,.2f}",
                "success",
            )
            return redirect(url_for("payroll.detail", payroll_id=payroll.id))
        else:
            flash("Error al calcular la nomina.", "error")

    return render_template(
        "payroll/calculate.html",
        periods=periods,
        month_names=MONTH_NAMES,
        active_page="payroll.index",
    )


@payroll_bp.route("/<int:payroll_id>")
@login_required
@role_required("payroll.manage")
def detail(payroll_id):
    payroll = Payroll.query.get_or_404(payroll_id)
    period = payroll.period
    items = sorted(payroll.items, key=lambda i: (i.employee.last_name, i.employee.first_name))
    return render_template(
        "payroll/detail.html",
        payroll=payroll,
        period=period,
        items=items,
        month_names=MONTH_NAMES,
        active_page="payroll.index",
    )


@payroll_bp.route("/<int:payroll_id>/employee/<int:employee_id>")
@login_required
@role_required("payroll.manage")
def employee_detail(payroll_id, employee_id):
    payroll = Payroll.query.get_or_404(payroll_id)
    item = PayrollItem.query.filter_by(
        payroll_id=payroll_id, employee_id=employee_id
    ).first_or_404()
    employee = item.employee
    period = payroll.period

    adjustments = PayrollAdjustment.query.filter_by(
        employee_id=employee_id, payroll_period_id=period.id
    ).all()

    income_adjustments = [a for a in adjustments if a.adjustment_type in ("HORA_EXTRA", "BONIFICACION", "COMISION")]
    deduction_adjustments = [a for a in adjustments if a.adjustment_type in ("PRESTAMO", "ANTICIPO", "AUSENCIA", "OTRA_DEDUCCION")]

    return render_template(
        "payroll/employee_detail.html",
        payroll=payroll,
        item=item,
        employee=employee,
        period=period,
        income_adjustments=income_adjustments,
        deduction_adjustments=deduction_adjustments,
        month_names=MONTH_NAMES,
        active_page="payroll.index",
    )


@payroll_bp.route("/<int:payroll_id>/payslip/<int:employee_id>")
@login_required
@role_required("payroll.manage")
def payslip(payroll_id, employee_id):
    payroll = Payroll.query.get_or_404(payroll_id)
    item = PayrollItem.query.filter_by(
        payroll_id=payroll_id, employee_id=employee_id
    ).first_or_404()
    employee = item.employee
    period = payroll.period

    adjustments = PayrollAdjustment.query.filter_by(
        employee_id=employee_id, payroll_period_id=period.id
    ).all()

    income_adjustments = [a for a in adjustments if a.adjustment_type in ("HORA_EXTRA", "BONIFICACION", "COMISION")]
    deduction_adjustments = [a for a in adjustments if a.adjustment_type in ("PRESTAMO", "ANTICIPO", "AUSENCIA", "OTRA_DEDUCCION")]

    payment_methods = {
        "EFECTIVO": "Efectivo",
        "TARJETA": "Tarjeta",
        "TRANSFERENCIA": "Transferencia",
        "CHEQUE": "Cheque",
    }

    return render_template(
        "payroll/payslip.html",
        payroll=payroll,
        item=item,
        employee=employee,
        period=period,
        income_adjustments=income_adjustments,
        deduction_adjustments=deduction_adjustments,
        payment_methods=payment_methods,
        month_names=MONTH_NAMES,
    )


@payroll_bp.route("/<int:payroll_id>/status", methods=["POST"])
@login_required
@role_required("payroll.manage")
def update_status(payroll_id):
    payroll = Payroll.query.get_or_404(payroll_id)
    new_status = request.form.get("status", "").strip()

    if payroll.status in ("PAGADA", "ANULADA"):
        flash("No se puede modificar una nomina pagada o anulada.", "error")
        return redirect(url_for("payroll.detail", payroll_id=payroll.id))

    if new_status not in VALID_STATUSES:
        flash("Estado invalido.", "error")
        return redirect(url_for("payroll.detail", payroll_id=payroll.id))

    allowed_transitions = {
        "BORRADOR": ["CALCULADA"],
        "CALCULADA": ["APROBADA", "ANULADA"],
        "APROBADA": ["PAGADA", "ANULADA"],
    }

    if new_status not in allowed_transitions.get(payroll.status, []):
        flash(f"No se puede cambiar de {payroll.status} a {new_status}.", "error")
        return redirect(url_for("payroll.detail", payroll_id=payroll.id))

    payroll.status = new_status

    if new_status == "PAGADA":
        for item in payroll.items:
            item.payment_status = "PAGADO"
            item.payment_date = date.today()

    audit = AuditLog(
        user_id=g.user.id,
        action="STATUS_CHANGE",
        module="PAYROLL",
        description=f"Nomina #{payroll.id} cambia a {new_status}",
    )
    db.session.add(audit)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    flash(f"Nomina #{payroll.id} actualizada a {new_status}.", "success")
    return redirect(url_for("payroll.detail", payroll_id=payroll.id))


@payroll_bp.route("/history")
@login_required
@role_required("payroll.manage")
def history():
    payrolls = Payroll.query.order_by(Payroll.created_at.desc()).limit(50).all()
    return render_template(
        "payroll/history.html",
        payrolls=payrolls,
        month_names=MONTH_NAMES,
        active_page="payroll.index",
    )


@payroll_bp.route("/parameters")
@login_required
@role_required("payroll.manage")
def parameters():
    all_params = PayrollParameter.query.order_by(PayrollParameter.name).all()
    brackets = IncomeTaxBracket.query.filter_by(is_active=True).order_by(
        IncomeTaxBracket.year, IncomeTaxBracket.lower_limit
    ).all()
    return render_template(
        "payroll/parameters.html",
        parameters=all_params,
        brackets=brackets,
        active_page="payroll.index",
    )
