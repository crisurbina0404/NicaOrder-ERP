from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from ..auth import login_required, role_required
from ..models import Supplier, AuditLog
from ..extensions import db
from sqlalchemy import or_

suppliers_bp = Blueprint("suppliers", __name__, url_prefix="/suppliers")


@suppliers_bp.route("/")
@login_required
@role_required("suppliers.view")
def list():
    search = request.args.get("search", "").strip()

    query = Supplier.query

    if search:
        query = query.filter(
            or_(
                Supplier.name.ilike(f"%{search}%"),
                Supplier.tax_id.ilike(f"%{search}%"),
                Supplier.contact_person.ilike(f"%{search}%"),
            )
        )

    suppliers = query.order_by(Supplier.name).all()

    return render_template(
        "suppliers/list.html",
        suppliers=suppliers,
        search=search,
        active_page="suppliers.list",
    )


@suppliers_bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required("suppliers.manage")
def create():
    if request.method == "POST":
        errors = _validate_supplier_form(request.form, exclude_tax_id=None)

        if errors:
            flash(errors[0], "error")
            return render_template(
                "suppliers/form.html",
                form_data=request.form,
                errors=errors,
                is_edit=False,
                active_page="suppliers.list",
            )

        supplier = Supplier(
            name=request.form["name"].strip(),
            tax_id=request.form["tax_id"].strip(),
            phone=request.form.get("phone", "").strip(),
            email=request.form.get("email", "").strip(),
            address=request.form.get("address", "").strip(),
            contact_person=request.form.get("contact_person", "").strip(),
            is_active=True,
        )

        db.session.add(supplier)
        audit = AuditLog(
            user_id=g.user.id,
            action="CREATE",
            module="SUPPLIERS",
            description=f"Proveedor creado: {supplier.name}",
        )
        db.session.add(audit)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Error al guardar el proveedor.", "error")
            return render_template(
                "suppliers/form.html",
                form_data=request.form,
                errors=[],
                is_edit=False,
                active_page="suppliers.list",
            )

        flash("Proveedor registrado correctamente.", "success")
        return redirect(url_for("suppliers.list"))

    return render_template(
        "suppliers/form.html",
        form_data={},
        errors={},
        is_edit=False,
        active_page="suppliers.list",
    )


@suppliers_bp.route("/<int:supplier_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("suppliers.manage")
def edit(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)

    if request.method == "POST":
        errors = _validate_supplier_form(request.form, exclude_tax_id=supplier.tax_id)

        if errors:
            flash(errors[0], "error")
            return render_template(
                "suppliers/form.html",
                supplier=supplier,
                form_data=request.form,
                errors=errors,
                is_edit=True,
                active_page="suppliers.list",
            )

        supplier.name = request.form["name"].strip()
        supplier.tax_id = request.form["tax_id"].strip()
        supplier.phone = request.form.get("phone", "").strip()
        supplier.email = request.form.get("email", "").strip()
        supplier.address = request.form.get("address", "").strip()
        supplier.contact_person = request.form.get("contact_person", "").strip()

        audit = AuditLog(
            user_id=g.user.id,
            action="UPDATE",
            module="SUPPLIERS",
            description=f"Proveedor actualizado: {supplier.name}",
        )
        db.session.add(audit)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Error al actualizar el proveedor.", "error")
            return render_template(
                "suppliers/form.html",
                supplier=supplier,
                form_data=request.form,
                errors=[],
                is_edit=True,
                active_page="suppliers.list",
            )

        flash("Proveedor actualizado correctamente.", "success")
        return redirect(url_for("suppliers.list"))

    return render_template(
        "suppliers/form.html",
        supplier=supplier,
        form_data=supplier,
        errors={},
        is_edit=True,
        active_page="suppliers.list",
    )


@suppliers_bp.route("/<int:supplier_id>/toggle", methods=["POST"])
@login_required
@role_required("suppliers.manage")
def toggle(supplier_id):
    supplier = Supplier.query.get_or_404(supplier_id)
    supplier.is_active = not supplier.is_active
    status = "activado" if supplier.is_active else "desactivado"

    audit = AuditLog(
        user_id=g.user.id,
        action="TOGGLE",
        module="SUPPLIERS",
        description=f"Proveedor {status}: {supplier.name}",
    )
    db.session.add(audit)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Error al cambiar estado del proveedor.", "error")
        return redirect(url_for("suppliers.list"))

    flash(f"Proveedor {status} correctamente.", "success")
    return redirect(url_for("suppliers.list"))


def _validate_supplier_form(form, exclude_tax_id=None):
    errors = []

    name = form.get("name", "").strip()
    tax_id = form.get("tax_id", "").strip()

    if not name:
        errors.append("El nombre es obligatorio.")
    elif len(name) > 150:
        errors.append("El nombre no puede exceder 150 caracteres.")
    elif exclude_tax_id is None or name != form.get("original_name", ""):
        existing_name = Supplier.query.filter_by(name=name).first()
        if existing_name:
            errors.append(f"El nombre '{name}' ya esta registrado.")

    if not tax_id:
        errors.append("El NIT/RUC es obligatorio.")
    elif len(tax_id) > 50:
        errors.append("El NIT/RUC no puede exceder 50 caracteres.")
    elif exclude_tax_id is None or tax_id != exclude_tax_id:
        existing = Supplier.query.filter_by(tax_id=tax_id).first()
        if existing:
            errors.append(f"El NIT/RUC '{tax_id}' ya esta registrado.")

    return errors
