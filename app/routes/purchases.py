from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify
from ..auth import login_required, role_required
from ..models import Purchase, PurchaseItem, Supplier, Product, AuditLog
from ..extensions import db
from sqlalchemy import or_
from ..services.purchase_reception_service import (
    receive_purchase, validate_invoice_uniqueness,
    ReceptionError, DuplicateInvoiceError, QuantityExceededError, InvalidStateError,
)

purchases_bp = Blueprint("purchases", __name__, url_prefix="/purchases")

VALID_STATUSES = ["BORRADOR", "RECIBIDA", "CANCELADA", "PAGADA"]


@purchases_bp.route("/")
@login_required
@role_required("purchases.view")
def list():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()

    query = Purchase.query

    if search:
        query = query.join(Purchase.supplier).filter(
            or_(
                Supplier.name.ilike(f"%{search}%"),
                Purchase.id.ilike(f"%{search}%"),
            )
        )

    if status and status in VALID_STATUSES:
        query = query.filter(Purchase.status == status)

    purchases = query.order_by(Purchase.created_at.desc()).all()

    return render_template(
        "purchases/list.html",
        purchases=purchases,
        search=search,
        selected_status=status,
        valid_statuses=VALID_STATUSES,
        active_page="purchases.list",
    )


@purchases_bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required("purchases.manage")
def create():
    suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()

    if request.method == "POST":
        errors = _validate_purchase_form(request.form)

        if errors:
            flash(errors[0], "error")
            return render_template(
                "purchases/form.html",
                form_data=request.form,
                errors=errors,
                suppliers=suppliers,
                products=products,
                is_edit=False,
                active_page="purchases.list",
            )

        try:
            purchase_date = datetime.strptime(
                request.form["purchase_date"], "%Y-%m-%d"
            )
        except (ValueError, TypeError):
            purchase_date = datetime.now()

        purchase = Purchase(
            supplier_id=int(request.form["supplier_id"]),
            user_id=g.user.id,
            purchase_date=purchase_date,
            invoice_number=request.form["invoice_number"].strip(),
            invoice_type=request.form.get("invoice_type", "FACTURA").strip(),
            status="BORRADOR",
            discount=float(request.form.get("discount", 0) or 0),
            tax=float(request.form.get("tax", 0) or 0),
            notes=request.form.get("notes", "").strip(),
        )

        db.session.add(purchase)
        db.session.flush()

        items = _parse_items(request.form)
        for item_data in items:
            item = PurchaseItem(
                purchase_id=purchase.id,
                product_id=item_data["product_id"],
                quantity=item_data["quantity"],
                unit_cost=item_data["unit_cost"],
                subtotal=item_data["quantity"] * item_data["unit_cost"],
            )
            db.session.add(item)

        purchase.recalculate_totals()

        audit = AuditLog(
            user_id=g.user.id,
            action="CREATE",
            module="PURCHASES",
            description=f"Compra #{purchase.id} creada con {len(items)} item(s)",
        )
        db.session.add(audit)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        flash(f"Compra #{purchase.id} registrada correctamente.", "success")
        return redirect(url_for("purchases.detail", purchase_id=purchase.id))

    return render_template(
        "purchases/form.html",
        form_data={
            "purchase_date": datetime.now().strftime("%Y-%m-%d"),
            "invoice_number": "",
            "invoice_type": "FACTURA",
        },
        errors={},
        suppliers=suppliers,
        products=products,
        is_edit=False,
        active_page="purchases.list",
    )


@purchases_bp.route("/<int:purchase_id>")
@login_required
@role_required("purchases.view")
def detail(purchase_id):
    purchase = Purchase.query.get_or_404(purchase_id)
    return render_template(
        "purchases/detail.html",
        purchase=purchase,
        active_page="purchases.list",
    )


@purchases_bp.route("/<int:purchase_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("purchases.manage")
def edit(purchase_id):
    purchase = Purchase.query.get_or_404(purchase_id)

    if purchase.status != "BORRADOR":
        flash("Solo se pueden editar compras en estado BORRADOR.", "error")
        return redirect(url_for("purchases.detail", purchase_id=purchase.id))

    suppliers = Supplier.query.filter_by(is_active=True).order_by(Supplier.name).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()

    if request.method == "POST":
        errors = _validate_purchase_form(request.form)

        if errors:
            flash(errors[0], "error")
            return render_template(
                "purchases/form.html",
                purchase=purchase,
                form_data=request.form,
                errors=errors,
                suppliers=suppliers,
                products=products,
                is_edit=True,
                active_page="purchases.list",
            )

        try:
            purchase_date = datetime.strptime(
                request.form["purchase_date"], "%Y-%m-%d"
            )
        except (ValueError, TypeError):
            purchase_date = purchase.purchase_date

        purchase.supplier_id = int(request.form["supplier_id"])
        purchase.purchase_date = purchase_date
        purchase.invoice_number = request.form["invoice_number"].strip()
        purchase.invoice_type = request.form.get("invoice_type", "FACTURA").strip()
        purchase.discount = float(request.form.get("discount", 0) or 0)
        purchase.tax = float(request.form.get("tax", 0) or 0)
        purchase.notes = request.form.get("notes", "").strip()

        PurchaseItem.query.filter_by(purchase_id=purchase.id).delete()

        items = _parse_items(request.form)
        for item_data in items:
            item = PurchaseItem(
                purchase_id=purchase.id,
                product_id=item_data["product_id"],
                quantity=item_data["quantity"],
                unit_cost=item_data["unit_cost"],
                subtotal=item_data["quantity"] * item_data["unit_cost"],
            )
            db.session.add(item)

        purchase.recalculate_totals()

        audit = AuditLog(
            user_id=g.user.id,
            action="UPDATE",
            module="PURCHASES",
            description=f"Compra #{purchase.id} actualizada con {len(items)} item(s)",
        )
        db.session.add(audit)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        flash(f"Compra #{purchase.id} actualizada correctamente.", "success")
        return redirect(url_for("purchases.detail", purchase_id=purchase.id))

    return render_template(
        "purchases/form.html",
        purchase=purchase,
        form_data=purchase,
        errors={},
        suppliers=suppliers,
        products=products,
        is_edit=True,
        active_page="purchases.list",
    )


@purchases_bp.route("/<int:purchase_id>/status", methods=["POST"])
@login_required
@role_required("purchases.manage")
def update_status(purchase_id):
    purchase = Purchase.query.get_or_404(purchase_id)
    new_status = request.form.get("status", "").strip()

    if new_status not in VALID_STATUSES:
        flash("Estado no valido.", "error")
        return redirect(url_for("purchases.detail", purchase_id=purchase.id))

    old_status = purchase.status

    if new_status == "RECIBIDA" and old_status != "RECIBIDA":
        try:
            received_items = [
                {"purchase_item_id": item.id, "quantity_received": item.quantity}
                for item in purchase.items
            ]
            receive_purchase(
                purchase_id=purchase.id,
                user_id=g.user.id,
                received_items=received_items,
            )
            flash(f"Compra #{purchase.id} recibida. Lotes creados en CUARENTENA.", "success")
            return redirect(url_for("purchases.detail", purchase_id=purchase.id))
        except (ReceptionError, DuplicateInvoiceError, QuantityExceededError) as e:
            db.session.rollback()
            flash(str(e), "error")
            return redirect(url_for("purchases.detail", purchase_id=purchase.id))

    purchase.status = new_status

    audit = AuditLog(
        user_id=g.user.id,
        action="STATUS_CHANGE",
        module="PURCHASES",
        description=f"Compra #{purchase.id}: {old_status} -> {new_status}",
    )
    db.session.add(audit)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    flash(f"Compra #{purchase.id} cambiada a estado {new_status}.", "success")
    return redirect(url_for("purchases.detail", purchase_id=purchase.id))


@purchases_bp.route("/api/products")
@login_required
@role_required("purchases.view")
def api_products():
    search = request.args.get("q", "").strip()
    query = Product.query.filter_by(is_active=True)

    if search:
        query = query.filter(
            or_(
                Product.code.ilike(f"%{search}%"),
                Product.name.ilike(f"%{search}%"),
            )
        )

    products = query.order_by(Product.name).limit(20).all()

    return jsonify(
        [
            {
                "id": p.id,
                "code": p.code,
                "name": p.name,
                "unit": p.unit,
                "purchase_price": p.purchase_price,
            }
            for p in products
        ]
    )


def _parse_items(form):
    items = []
    product_ids = form.getlist("item_product_id[]")
    quantities = form.getlist("item_quantity[]")
    unit_costs = form.getlist("item_unit_cost[]")

    for i in range(len(product_ids)):
        if not product_ids[i]:
            continue

        try:
            qty = int(quantities[i])
            cost = float(unit_costs[i])
        except (ValueError, IndexError):
            continue

        if qty <= 0 or cost < 0:
            continue

        items.append(
            {
                "product_id": int(product_ids[i]),
                "quantity": qty,
                "unit_cost": cost,
            }
        )

    return items


def _validate_purchase_form(form):
    errors = []

    supplier_id = form.get("supplier_id", "").strip()
    purchase_date = form.get("purchase_date", "").strip()
    invoice_number = form.get("invoice_number", "").strip()

    if not supplier_id:
        errors.append("Seleccione un proveedor.")

    if not purchase_date:
        errors.append("La fecha de compra es obligatoria.")

    if not invoice_number:
        errors.append("El numero de factura es obligatorio.")

    try:
        discount = float(form.get("discount", 0) or 0)
        if discount < 0:
            errors.append("El descuento no puede ser negativo.")
    except (ValueError, TypeError):
        errors.append("El descuento no es valido.")

    try:
        tax = float(form.get("tax", 0) or 0)
        if tax < 0:
            errors.append("El impuesto no puede ser negativo.")
    except (ValueError, TypeError):
        errors.append("El impuesto no es valido.")

    items = _parse_items(form)
    if not items:
        errors.append("Debe agregar al menos un producto a la compra.")

    for item in items:
        if item["quantity"] <= 0:
            errors.append("La cantidad debe ser mayor a cero.")
            break
        if item["unit_cost"] < 0:
            errors.append("El costo unitario no puede ser negativo.")
            break

    return errors
