from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from ..auth import login_required, role_required
from ..models import Employee, SalaryHistory, Department, Position, AuditLog
from ..extensions import db
from sqlalchemy import or_

hr_bp = Blueprint("hr", __name__, url_prefix="/hr")

VALID_STATUSES = ["ACTIVO", "INACTIVO", "SUSPENDIDO"]
VALID_CONTRACT_TYPES = ["INDEFINIDO", "PLAZO_FIJO", "POR_OBRA", "PASANTE"]


@hr_bp.route("/")
@login_required
@role_required("hr.employees.view")
def list():
    search = request.args.get("search", "").strip()
    department_id = request.args.get("department_id", "").strip()
    status = request.args.get("status", "").strip()

    query = Employee.query

    if search:
        query = query.filter(
            or_(
                Employee.first_name.ilike(f"%{search}%"),
                Employee.last_name.ilike(f"%{search}%"),
                Employee.employee_code.ilike(f"%{search}%"),
                Employee.identity_number.ilike(f"%{search}%"),
            )
        )

    if department_id:
        query = query.filter(Employee.department_id == int(department_id))

    if status and status in VALID_STATUSES:
        query = query.filter(Employee.status == status)

    employees = query.order_by(Employee.last_name, Employee.first_name).all()
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()

    return render_template(
        "hr/list.html",
        employees=employees,
        search=search,
        selected_department=department_id,
        selected_status=status,
        departments=departments,
        valid_statuses=VALID_STATUSES,
        active_page="hr.list",
    )


@hr_bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required("hr.employees.manage")
def create():
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    positions = Position.query.filter_by(is_active=True).order_by(Position.name).all()

    if request.method == "POST":
        errors = _validate_employee_form(request.form, exclude_code=None, exclude_identity=None)

        if errors:
            flash(errors[0], "error")
            return render_template(
                "hr/form.html",
                form_data=request.form,
                errors=errors,
                departments=departments,
                positions=positions,
                valid_statuses=VALID_STATUSES,
                valid_contract_types=VALID_CONTRACT_TYPES,
                is_edit=False,
                active_page="hr.list",
            )

        try:
            birth_date = datetime.strptime(request.form["birth_date"], "%Y-%m-%d").date() if request.form.get("birth_date") else None
        except (ValueError, TypeError):
            birth_date = None

        try:
            hire_date = datetime.strptime(request.form["hire_date"], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            hire_date = date.today()

        try:
            base_salary = float(request.form.get("base_salary", 0) or 0)
        except (ValueError, TypeError):
            base_salary = 0.0

        employee = Employee(
            employee_code=request.form["employee_code"].strip(),
            first_name=request.form["first_name"].strip(),
            last_name=request.form["last_name"].strip(),
            identity_number=request.form["identity_number"].strip(),
            birth_date=birth_date,
            phone=request.form.get("phone", "").strip(),
            email=request.form.get("email", "").strip(),
            address=request.form.get("address", "").strip(),
            department_id=int(request.form["department_id"]),
            position_id=int(request.form["position_id"]),
            hire_date=hire_date,
            contract_type=request.form.get("contract_type", "INDEFINIDO"),
            base_salary=base_salary,
            status=request.form.get("status", "ACTIVO"),
        )

        db.session.add(employee)
        db.session.flush()

        salary_record = SalaryHistory(
            employee_id=employee.id,
            salary=base_salary,
            start_date=hire_date,
            end_date=None,
            reason="Salario inicial",
        )
        db.session.add(salary_record)

        audit = AuditLog(
            user_id=g.user.id,
            action="CREATE",
            module="HR",
            description=f"Empleado registrado: {employee.employee_code} - {employee.full_name}",
        )
        db.session.add(audit)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        flash(f"Empleado {employee.employee_code} registrado correctamente.", "success")
        return redirect(url_for("hr.detail", employee_id=employee.id))

    return render_template(
        "hr/form.html",
        form_data={"hire_date": date.today().strftime("%Y-%m-%d"), "contract_type": "INDEFINIDO", "status": "ACTIVO"},
        errors={},
        departments=departments,
        positions=positions,
        valid_statuses=VALID_STATUSES,
        valid_contract_types=VALID_CONTRACT_TYPES,
        is_edit=False,
        active_page="hr.list",
    )


@hr_bp.route("/<int:employee_id>")
@login_required
@role_required("hr.employees.view")
def detail(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    salary_history = employee.salary_history
    return render_template(
        "hr/detail.html",
        employee=employee,
        salary_history=salary_history,
        active_page="hr.list",
    )


@hr_bp.route("/<int:employee_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("hr.employees.manage")
def edit(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    departments = Department.query.filter_by(is_active=True).order_by(Department.name).all()
    positions = Position.query.filter_by(is_active=True).order_by(Position.name).all()

    if request.method == "POST":
        errors = _validate_employee_form(
            request.form,
            exclude_code=employee.employee_code,
            exclude_identity=employee.identity_number,
        )

        if errors:
            flash(errors[0], "error")
            return render_template(
                "hr/form.html",
                employee=employee,
                form_data=request.form,
                errors=errors,
                departments=departments,
                positions=positions,
                valid_statuses=VALID_STATUSES,
                valid_contract_types=VALID_CONTRACT_TYPES,
                is_edit=True,
                active_page="hr.list",
            )

        try:
            birth_date = datetime.strptime(request.form["birth_date"], "%Y-%m-%d").date() if request.form.get("birth_date") else None
        except (ValueError, TypeError):
            birth_date = None

        try:
            hire_date = datetime.strptime(request.form["hire_date"], "%Y-%m-%d").date()
        except (ValueError, TypeError):
            hire_date = employee.hire_date

        try:
            new_salary = float(request.form.get("base_salary", 0) or 0)
        except (ValueError, TypeError):
            new_salary = 0.0

        salary_changed = new_salary != employee.base_salary
        salary_reason = request.form.get("salary_reason", "").strip()

        employee.employee_code = request.form["employee_code"].strip()
        employee.first_name = request.form["first_name"].strip()
        employee.last_name = request.form["last_name"].strip()
        employee.identity_number = request.form["identity_number"].strip()
        employee.birth_date = birth_date
        employee.phone = request.form.get("phone", "").strip()
        employee.email = request.form.get("email", "").strip()
        employee.address = request.form.get("address", "").strip()
        employee.department_id = int(request.form["department_id"])
        employee.position_id = int(request.form["position_id"])
        employee.hire_date = hire_date
        employee.contract_type = request.form.get("contract_type", "INDEFINIDO")
        employee.base_salary = new_salary
        employee.status = request.form.get("status", "ACTIVO")

        if salary_changed:
            today = date.today()
            for record in employee.salary_history:
                if record.end_date is None:
                    record.end_date = today

            new_record = SalaryHistory(
                employee_id=employee.id,
                salary=new_salary,
                start_date=today,
                end_date=None,
                reason=salary_reason or "Ajuste salarial",
            )
            db.session.add(new_record)

        audit = AuditLog(
            user_id=g.user.id,
            action="UPDATE",
            module="HR",
            description=f"Empleado actualizado: {employee.employee_code} - {employee.full_name}",
        )
        db.session.add(audit)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        flash(f"Empleado {employee.employee_code} actualizado correctamente.", "success")
        return redirect(url_for("hr.detail", employee_id=employee.id))

    return render_template(
        "hr/form.html",
        employee=employee,
        form_data=employee,
        errors={},
        departments=departments,
        positions=positions,
        valid_statuses=VALID_STATUSES,
        valid_contract_types=VALID_CONTRACT_TYPES,
        is_edit=True,
        active_page="hr.list",
    )


@hr_bp.route("/<int:employee_id>/toggle", methods=["POST"])
@login_required
@role_required("hr.employees.manage")
def toggle(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    if employee.status == "ACTIVO":
        employee.status = "INACTIVO"
        new_status = "desactivado"
    else:
        employee.status = "ACTIVO"
        new_status = "activado"

    audit = AuditLog(
        user_id=g.user.id,
        action="TOGGLE",
        module="HR",
        description=f"Empleado {new_status}: {employee.employee_code} - {employee.full_name}",
    )
    db.session.add(audit)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    flash(f"Empleado {new_status} correctamente.", "success")
    return redirect(url_for("hr.list"))


@hr_bp.route("/<int:employee_id>/salary-history")
@login_required
@role_required("hr.salary.view")
def salary_history(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    history = employee.salary_history
    return render_template(
        "hr/salary_history.html",
        employee=employee,
        salary_history=history,
        active_page="hr.list",
    )


def _validate_employee_form(form, exclude_code=None, exclude_identity=None):
    errors = []

    code = form.get("employee_code", "").strip()
    first_name = form.get("first_name", "").strip()
    last_name = form.get("last_name", "").strip()
    identity = form.get("identity_number", "").strip()
    department_id = form.get("department_id", "").strip()
    position_id = form.get("position_id", "").strip()
    hire_date = form.get("hire_date", "").strip()
    base_salary = form.get("base_salary", "").strip()

    if not code:
        errors.append("El codigo de empleado es obligatorio.")
    elif exclude_code is None or code != exclude_code:
        existing = Employee.query.filter_by(employee_code=code).first()
        if existing:
            errors.append(f"El codigo '{code}' ya esta registrado.")

    if not first_name:
        errors.append("El nombre es obligatorio.")

    if not last_name:
        errors.append("El apellido es obligatorio.")

    if not identity:
        errors.append("El numero de identificacion es obligatorio.")
    elif exclude_identity is None or identity != exclude_identity:
        existing = Employee.query.filter_by(identity_number=identity).first()
        if existing:
            errors.append(f"El numero de identificacion '{identity}' ya esta registrado.")

    if not department_id:
        errors.append("Seleccione un departamento.")

    if not position_id:
        errors.append("Seleccione un cargo.")

    if not hire_date:
        errors.append("La fecha de ingreso es obligatoria.")

    try:
        salary_val = float(base_salary or 0)
        if salary_val < 0:
            errors.append("El salario no puede ser negativo.")
    except (ValueError, TypeError):
        errors.append("El salario no es valido.")

    return errors
