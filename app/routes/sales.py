from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, g, jsonify
from ..auth import login_required, role_required
from ..models import Sale, SaleItem, Customer, Product, Category, AuditLog, InventoryMovement, ProductBatch
from ..extensions import db
from .inventory import fefo_dispatch, _get_product_stock
from sqlalchemy import or_

sales_bp = Blueprint("sales", __name__, url_prefix="/sales")

VALID_STATUSES = ["BORRADOR", "CONFIRMADA", "CANCELADA"]
VALID_PAYMENT_METHODS = ["EFECTIVO", "TARJETA", "TRANSFERENCIA", "CREDITO"]


@sales_bp.route("/")
@login_required
@role_required("sales.view")
def list():
    search = request.args.get("search", "").strip()
    status = request.args.get("status", "").strip()

    query = Sale.query

    if search:
        query = query.join(Sale.customer).filter(
            or_(
                Customer.name.ilike(f"%{search}%"),
                Sale.id.ilike(f"%{search}%"),
            )
        )

    if status and status in VALID_STATUSES:
        query = query.filter(Sale.status == status)

    sales = query.order_by(Sale.created_at.desc()).all()

    return render_template(
        "sales/list.html",
        sales=sales,
        search=search,
        selected_status=status,
        valid_statuses=VALID_STATUSES,
        active_page="sales.list",
    )


@sales_bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required("sales.manage")
def create():
    customers = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    product_stock = {p.id: _get_product_stock(p.id) for p in products}

    if request.method == "POST":
        errors = _validate_sale_form(request.form)

        if errors:
            flash(errors[0], "error")
            return render_template(
                "sales/form.html",
                form_data=request.form,
                errors=errors,
                customers=customers,
                products=products,
                categories=categories,
                product_stock=product_stock,
                valid_payment_methods=VALID_PAYMENT_METHODS,
                is_edit=False,
                active_page="sales.list",
            )

        try:
            sale_date = datetime.strptime(request.form["sale_date"], "%Y-%m-%d")
        except (ValueError, TypeError):
            sale_date = datetime.now()

        sale = Sale(
            customer_id=int(request.form["customer_id"]),
            user_id=g.user.id,
            sale_date=sale_date,
            status="BORRADOR",
            payment_method=request.form.get("payment_method", "EFECTIVO"),
            discount=float(request.form.get("discount", 0) or 0),
            tax=float(request.form.get("tax", 0) or 0),
            notes=request.form.get("notes", "").strip(),
        )

        db.session.add(sale)
        db.session.flush()

        items = _parse_items(request.form)
        for item_data in items:
            item = SaleItem(
                sale_id=sale.id,
                product_id=item_data["product_id"],
                quantity=item_data["quantity"],
                unit_price=item_data["unit_price"],
                subtotal=item_data["quantity"] * item_data["unit_price"],
            )
            db.session.add(item)

        sale.recalculate_totals()

        audit = AuditLog(
            user_id=g.user.id,
            action="CREATE",
            module="SALES",
            description=f"Venta #{sale.id} creada con {len(items)} item(s)",
        )
        db.session.add(audit)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        flash(f"Venta #{sale.id} registrada correctamente.", "success")
        return redirect(url_for("sales.detail", sale_id=sale.id))

    return render_template(
        "sales/form.html",
        form_data={"sale_date": datetime.now().strftime("%Y-%m-%d")},
        errors={},
        customers=customers,
        products=products,
        categories=categories,
        product_stock=product_stock,
        valid_payment_methods=VALID_PAYMENT_METHODS,
        is_edit=False,
        active_page="sales.list",
    )


@sales_bp.route("/<int:sale_id>")
@login_required
@role_required("sales.view")
def detail(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    return render_template(
        "sales/detail.html",
        sale=sale,
        active_page="sales.list",
    )


@sales_bp.route("/<int:sale_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("sales.manage")
def edit(sale_id):
    sale = Sale.query.get_or_404(sale_id)

    if sale.status != "BORRADOR":
        flash("Solo se pueden editar ventas en estado BORRADOR.", "error")
        return redirect(url_for("sales.detail", sale_id=sale.id))

    customers = Customer.query.filter_by(is_active=True).order_by(Customer.name).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()
    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    product_stock = {p.id: _get_product_stock(p.id) for p in products}

    if request.method == "POST":
        errors = _validate_sale_form(request.form)

        if errors:
            flash(errors[0], "error")
            return render_template(
                "sales/form.html",
                sale=sale,
                form_data=request.form,
                errors=errors,
                customers=customers,
                products=products,
                categories=categories,
                product_stock=product_stock,
                valid_payment_methods=VALID_PAYMENT_METHODS,
                is_edit=True,
                active_page="sales.list",
            )

        try:
            sale_date = datetime.strptime(request.form["sale_date"], "%Y-%m-%d")
        except (ValueError, TypeError):
            sale_date = sale.sale_date

        sale.customer_id = int(request.form["customer_id"])
        sale.sale_date = sale_date
        sale.payment_method = request.form.get("payment_method", "EFECTIVO")
        sale.discount = float(request.form.get("discount", 0) or 0)
        sale.tax = float(request.form.get("tax", 0) or 0)
        sale.notes = request.form.get("notes", "").strip()

        SaleItem.query.filter_by(sale_id=sale.id).delete()

        items = _parse_items(request.form)
        for item_data in items:
            item = SaleItem(
                sale_id=sale.id,
                product_id=item_data["product_id"],
                quantity=item_data["quantity"],
                unit_price=item_data["unit_price"],
                subtotal=item_data["quantity"] * item_data["unit_price"],
            )
            db.session.add(item)

        sale.recalculate_totals()

        audit = AuditLog(
            user_id=g.user.id,
            action="UPDATE",
            module="SALES",
            description=f"Venta #{sale.id} actualizada con {len(items)} item(s)",
        )
        db.session.add(audit)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        flash(f"Venta #{sale.id} actualizada correctamente.", "success")
        return redirect(url_for("sales.detail", sale_id=sale.id))

    return render_template(
        "sales/form.html",
        sale=sale,
        form_data=sale,
        errors={},
        customers=customers,
        products=products,
        categories=categories,
        product_stock=product_stock,
        valid_payment_methods=VALID_PAYMENT_METHODS,
        is_edit=True,
        active_page="sales.list",
    )


@sales_bp.route("/<int:sale_id>/confirm", methods=["POST"])
@login_required
@role_required("sales.manage")
def confirm(sale_id):
    sale = Sale.query.get_or_404(sale_id)

    if sale.status != "BORRADOR":
        flash("Solo se pueden confirmar ventas en estado BORRADOR.", "error")
        return redirect(url_for("sales.detail", sale_id=sale.id))

    for item in sale.items:
        stock = _get_product_stock(item.product_id)
        if stock < item.quantity:
            flash(
                f"Stock insuficiente para {item.product.name}. Disponible: {stock}.",
                "error",
            )
            return redirect(url_for("sales.detail", sale_id=sale.id))

    for item in sale.items:
        dispatched, remaining = fefo_dispatch(
            product_id=item.product_id,
            quantity_needed=item.quantity,
            user_id=g.user.id,
            reference_type="VENTA",
            reference_id=sale.id,
            description=f"Salida por venta #{sale.id}",
        )

        if dispatched:
            item.batch_id = dispatched[0]["batch_id"]

    sale.status = "CONFIRMADA"

    audit = AuditLog(
        user_id=g.user.id,
        action="CONFIRM",
        module="SALES",
        description=f"Venta #{sale.id} confirmada - {sale.payment_method}",
    )
    db.session.add(audit)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    flash(f"Venta #{sale.id} confirmada correctamente.", "success")
    return redirect(url_for("sales.detail", sale_id=sale.id))


@sales_bp.route("/<int:sale_id>/cancel", methods=["POST"])
@login_required
@role_required("sales.cancel")
def cancel(sale_id):
    sale = Sale.query.get_or_404(sale_id)

    if sale.status == "CANCELADA":
        flash("La venta ya esta cancelada.", "error")
        return redirect(url_for("sales.detail", sale_id=sale.id))

    if sale.status == "CONFIRMADA":
        for item in sale.items:
            if item.batch_id:
                movement = InventoryMovement(
                    product_id=item.product_id,
                    batch_id=item.batch_id,
                    movement_type="ENTRADA",
                    quantity=item.quantity,
                    reference_type="SALE_CANCEL",
                    reference_id=sale.id,
                    description=f"Devolucion por cancelacion de venta #{sale.id}",
                    user_id=g.user.id,
                )
                db.session.add(movement)

    sale.status = "CANCELADA"

    audit = AuditLog(
        user_id=g.user.id,
        action="CANCEL",
        module="SALES",
        description=f"Venta #{sale.id} cancelada",
    )
    db.session.add(audit)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    flash(f"Venta #{sale.id} cancelada.", "success")
    return redirect(url_for("sales.detail", sale_id=sale.id))


@sales_bp.route("/<int:sale_id>/return", methods=["GET", "POST"])
@login_required
@role_required("sales.manage")
def return_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)

    if sale.status != "CONFIRMADA":
        flash("Solo se pueden devolver ventas confirmadas.", "error")
        return redirect(url_for("sales.detail", sale_id=sale.id))

    if request.method == "POST":
        return_items = request.form.getlist("return_item_id[]")
        return_qtys = request.form.getlist("return_quantity[]")
        reason = request.form.get("reason", "").strip()

        if not return_items:
            flash("Seleccione al menos un producto para devolver.", "error")
            return redirect(url_for("sales.return_sale", sale_id=sale.id))

        returned_count = 0
        for i, item_id in enumerate(return_items):
            try:
                item_id = int(item_id)
                qty = int(return_qtys[i])
            except (ValueError, IndexError):
                continue

            sale_item = SaleItem.query.get(item_id)
            if not sale_item or sale_item.sale_id != sale.id:
                continue

            max_return = sale_item.quantity - (sale_item.quantity_returned or 0)
            if qty <= 0 or qty > max_return:
                continue

            sale_item.quantity_returned = (sale_item.quantity_returned or 0) + qty

            if sale_item.batch_id:
                movement = InventoryMovement(
                    product_id=sale_item.product_id,
                    batch_id=sale_item.batch_id,
                    movement_type="ENTRADA",
                    quantity=qty,
                    reference_type="SALE_RETURN",
                    reference_id=sale.id,
                    description=f"Devolucion venta #{sale.id}: {sale_item.product.name} x{qty}. {reason}",
                    user_id=g.user.id,
                )
                db.session.add(movement)
            else:
                batch = ProductBatch.query.filter_by(
                    product_id=sale_item.product_id, is_active=True
                ).order_by(ProductBatch.created_at.desc()).first()
                if batch:
                    movement = InventoryMovement(
                        product_id=sale_item.product_id,
                        batch_id=batch.id,
                        movement_type="ENTRADA",
                        quantity=qty,
                        reference_type="SALE_RETURN",
                        reference_id=sale.id,
                        description=f"Devolucion venta #{sale.id}: {sale_item.product.name} x{qty}. {reason}",
                        user_id=g.user.id,
                    )
                    db.session.add(movement)

            returned_count += qty

        if returned_count > 0:
            audit = AuditLog(
                user_id=g.user.id,
                action="RETURN",
                module="SALES",
                description=f"Devolucion en venta #{sale.id}: {returned_count} unidades",
            )
            db.session.add(audit)
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
                raise
            flash(f"Devolucion procesada: {returned_count} unidad(es) devueltas.", "success")
        else:
            flash("No se pudo procesar la devolucion.", "error")

        return redirect(url_for("sales.detail", sale_id=sale.id))

    return render_template(
        "sales/return.html",
        sale=sale,
        active_page="sales.list",
    )


@sales_bp.route("/<int:sale_id>/receipt")
@login_required
@role_required("sales.view")
def receipt(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    return render_template("sales/receipt.html", sale=sale)


@sales_bp.route("/api/stock/<int:product_id>")
@login_required
@role_required("inventory.view")
def api_stock(product_id):
    stock = _get_product_stock(product_id)
    return jsonify({"product_id": product_id, "stock": stock})


def _parse_items(form):
    items = []
    product_ids = form.getlist("item_product_id[]")
    quantities = form.getlist("item_quantity[]")
    unit_prices = form.getlist("item_unit_price[]")

    for i in range(len(product_ids)):
        if not product_ids[i]:
            continue

        try:
            qty = int(quantities[i])
            price = float(unit_prices[i])
        except (ValueError, IndexError):
            continue

        if qty <= 0 or price < 0:
            continue

        items.append(
            {
                "product_id": int(product_ids[i]),
                "quantity": qty,
                "unit_price": price,
            }
        )

    return items


def _validate_sale_form(form):
    errors = []

    customer_id = form.get("customer_id", "").strip()
    sale_date = form.get("sale_date", "").strip()
    payment_method = form.get("payment_method", "").strip()

    if not customer_id:
        errors.append("Seleccione un cliente.")

    if not sale_date:
        errors.append("La fecha de venta es obligatoria.")

    if not payment_method or payment_method not in VALID_PAYMENT_METHODS:
        errors.append("Seleccione una forma de pago valida.")

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
        errors.append("Debe agregar al menos un producto a la venta.")

    for item in items:
        if item["quantity"] <= 0:
            errors.append("La cantidad debe ser mayor a cero.")
            break
        if item["unit_price"] < 0:
            errors.append("El precio no puede ser negativo.")
            break

    return errors
