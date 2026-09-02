from datetime import date
from ..extensions import db
from ..models import (
    Employee, SalaryHistory, PayrollParameter, IncomeTaxBracket,
    PayrollPeriod, Payroll, PayrollItem, PayrollAdjustment,
)


def get_param(name):
    param = PayrollParameter.query.filter_by(name=name, is_active=True).first()
    return param.value if param else 0.0


def get_salary_for_period(employee, period_year, period_month):
    salary_records = SalaryHistory.query.filter(
        SalaryHistory.employee_id == employee.id,
        SalaryHistory.start_date <= date(period_year, period_month, 28),
    ).order_by(SalaryHistory.start_date.desc()).all()

    for record in salary_records:
        if record.end_date is None or record.end_date >= date(period_year, period_month, 1):
            return record.salary

    return employee.base_salary


def calculate_gross_salary(base_salary, overtime=0.0, bonuses=0.0, commissions=0.0):
    return base_salary + overtime + bonuses + commissions


def calculate_employee_inss(gross_salary):
    rate = get_param("INSS_LABORAL") / 100
    return round(gross_salary * rate, 2)


def calculate_annual_taxable_income(monthly_gross, employee_inss):
    monthly_taxable = monthly_gross - employee_inss
    return round(monthly_taxable * 12, 2)


def get_tax_bracket(annual_income, year):
    brackets = IncomeTaxBracket.query.filter_by(year=year, is_active=True).order_by(
        IncomeTaxBracket.lower_limit
    ).all()

    for bracket in brackets:
        upper = bracket.upper_limit if bracket.upper_limit is not None else float('inf')
        if bracket.lower_limit <= annual_income <= upper:
            return bracket

    return brackets[-1] if brackets else None


def calculate_annual_income_tax(annual_taxable_income, bracket):
    if not bracket:
        return 0.0
    excess = annual_taxable_income - bracket.lower_limit
    tax = bracket.base_tax + (excess * bracket.excess_percentage / 100)
    return round(max(tax, 0.0), 2)


def calculate_monthly_income_tax(annual_tax):
    return round(annual_tax / 12, 2)


def calculate_net_salary(gross_salary, employee_inss, monthly_income_tax, other_deductions=0.0):
    return round(gross_salary - employee_inss - monthly_income_tax - other_deductions, 2)


def get_adjustments(employee_id, period_id):
    return PayrollAdjustment.query.filter_by(
        employee_id=employee_id,
        payroll_period_id=period_id,
    ).all()


def calculate_employee_payroll(employee, period):
    base = get_salary_for_period(employee, period.year, period.month)

    adjustments = get_adjustments(employee.id, period.id)
    overtime = sum(a.amount for a in adjustments if a.adjustment_type == "HORA_EXTRA")
    bonuses = sum(a.amount for a in adjustments if a.adjustment_type == "BONIFICACION")
    commissions = sum(a.amount for a in adjustments if a.adjustment_type == "COMISION")
    income_additions = sum(
        a.amount for a in adjustments
        if a.adjustment_type in ("HORA_EXTRA", "BONIFICACION", "COMISION") and a.affects_income_tax
    )
    ss_additions = sum(
        a.amount for a in adjustments
        if a.adjustment_type in ("HORA_EXTRA", "BONIFICACION", "COMISION") and a.affects_social_security
    )
    deduction_amounts = sum(
        a.amount for a in adjustments
        if a.adjustment_type in ("PRESTAMO", "ANTICIPO", "AUSENCIA", "OTRA_DEDUCCION")
    )

    gross_for_ss = base + ss_additions
    employee_inss = calculate_employee_inss(gross_for_ss)

    gross_for_tax = base + income_additions
    annual_taxable = calculate_annual_taxable_income(gross_for_tax, employee_inss)
    bracket = get_tax_bracket(annual_taxable, period.year)
    annual_tax = calculate_annual_income_tax(annual_taxable, bracket)
    monthly_tax = calculate_monthly_income_tax(annual_tax)

    gross_salary = base + overtime + bonuses + commissions
    net_salary = calculate_net_salary(gross_salary, employee_inss, monthly_tax, deduction_amounts)

    return {
        "base_salary": base,
        "overtime": overtime,
        "bonuses": bonuses,
        "commissions": commissions,
        "gross_salary": gross_salary,
        "employee_inss": employee_inss,
        "annual_taxable_income": annual_taxable,
        "tax_bracket_id": bracket.id if bracket else None,
        "annual_income_tax": annual_tax,
        "monthly_income_tax": monthly_tax,
        "other_deductions": deduction_amounts,
        "net_salary": net_salary,
    }


def calculate_full_payroll(period_id, user_id):
    period = PayrollPeriod.query.get(period_id)
    if not period:
        return None

    existing = Payroll.query.filter_by(payroll_period_id=period_id).first()
    if existing:
        if existing.status in ("APROBADA", "PAGADA"):
            return None
        PayrollItem.query.filter_by(payroll_id=existing.id).delete()
        payroll = existing
    else:
        payroll = Payroll(
            payroll_period_id=period_id,
            user_id=user_id,
            generated_at=date.today(),
            status="BORRADOR",
        )
        db.session.add(payroll)
        db.session.flush()

    employees = Employee.query.filter_by(status="ACTIVO").all()

    for emp in employees:
        result = calculate_employee_payroll(emp, period)
        item = PayrollItem(
            payroll_id=payroll.id,
            employee_id=emp.id,
            **result,
        )
        db.session.add(item)

    db.session.flush()
    payroll.recalculate_totals()
    payroll.status = "CALCULADA"

    return payroll
