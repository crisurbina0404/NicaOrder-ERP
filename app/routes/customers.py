from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from ..auth import login_required, role_required
from ..models import Customer, AuditLog
from ..extensions import db
from sqlalchemy import or_

customers_bp = Blueprint("customers", __name__, url_prefix="/customers")


@customers_bp.route("/")
@login_required
@role_required("customers.view")
def list():
    search = request.args.get("search", "").strip()

    query = Customer.query

    if search:
        query = query.filter(
            or_(
                Customer.name.ilike(f"%{search}%"),
                Customer.identity_number.ilike(f"%{search}%"),
            )
        )

    customers = query.order_by(Customer.name).all()

    return render_template(
        "customers/list.html",
        customers=customers,
        search=search,
        active_page="customers.list",
    )


@customers_bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required("customers.manage")
def create():
    if request.method == "POST":
        errors = _validate_customer_form(request.form, exclude_id=None)

        if errors:
            flash(errors[0], "error")
            return render_template(
                "customers/form.html",
                form_data=request.form,
                errors=errors,
                is_edit=False,
                active_page="customers.list",
            )

        customer = Customer(
            name=request.form["name"].strip(),
            identity_number=request.form["identity_number"].strip(),
            phone=request.form.get("phone", "").strip(),
            email=request.form.get("email", "").strip(),
            address=request.form.get("address", "").strip(),
            is_active=True,
        )

        db.session.add(customer)
        audit = AuditLog(
            user_id=g.user.id,
            action="CREATE",
            module="CUSTOMERS",
            description=f"Cliente creado: {customer.name}",
        )
        db.session.add(audit)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        flash("Cliente registrado correctamente.", "success")
        return redirect(url_for("customers.list"))

    return render_template(
        "customers/form.html",
        form_data={},
        errors={},
        is_edit=False,
        active_page="customers.list",
    )


@customers_bp.route("/<int:customer_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("customers.manage")
def edit(customer_id):
    customer = Customer.query.get_or_404(customer_id)

    if request.method == "POST":
        errors = _validate_customer_form(
            request.form, exclude_id=customer.identity_number
        )

        if errors:
            flash(errors[0], "error")
            return render_template(
                "customers/form.html",
                customer=customer,
                form_data=request.form,
                errors=errors,
                is_edit=True,
                active_page="customers.list",
            )

        customer.name = request.form["name"].strip()
        customer.identity_number = request.form["identity_number"].strip()
        customer.phone = request.form.get("phone", "").strip()
        customer.email = request.form.get("email", "").strip()
        customer.address = request.form.get("address", "").strip()

        audit = AuditLog(
            user_id=g.user.id,
            action="UPDATE",
            module="CUSTOMERS",
            description=f"Cliente actualizado: {customer.name}",
        )
        db.session.add(audit)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        flash("Cliente actualizado correctamente.", "success")
        return redirect(url_for("customers.list"))

    return render_template(
        "customers/form.html",
        customer=customer,
        form_data=customer,
        errors={},
        is_edit=True,
        active_page="customers.list",
    )


@customers_bp.route("/<int:customer_id>/toggle", methods=["POST"])
@login_required
@role_required("customers.manage")
def toggle(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    customer.is_active = not customer.is_active
    status = "activado" if customer.is_active else "desactivado"

    audit = AuditLog(
        user_id=g.user.id,
        action="TOGGLE",
        module="CUSTOMERS",
        description=f"Cliente {status}: {customer.name}",
    )
    db.session.add(audit)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    flash(f"Cliente {status} correctamente.", "success")
    return redirect(url_for("customers.list"))


def _validate_customer_form(form, exclude_id=None):
    errors = []

    name = form.get("name", "").strip()
    identity_number = form.get("identity_number", "").strip()

    if not name:
        errors.append("El nombre es obligatorio.")

    if not identity_number:
        errors.append("El numero de identificacion es obligatorio.")
    elif exclude_id is None or identity_number != exclude_id:
        existing = Customer.query.filter_by(identity_number=identity_number).first()
        if existing:
            errors.append(
                f"El numero de identificacion '{identity_number}' ya esta registrado."
            )

    return errors
