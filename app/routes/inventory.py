from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from ..auth import login_required, role_required
from ..models import (
    Product,
    ProductBatch,
    InventoryMovement,
    AuditLog,
)
from ..extensions import db
from sqlalchemy import or_, func

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")


@inventory_bp.route("/stock")
@login_required
@role_required("inventory.view")
def stock():
    search = request.args.get("search", "").strip()

    query = db.session.query(
        Product.id,
        Product.code,
        Product.name,
        Product.unit,
        Product.minimum_stock,
        func.coalesce(
            db.session.query(func.sum(ProductBatch.quantity - db.func.coalesce(
                db.session.query(func.sum(InventoryMovement.quantity))
                .filter(
                    InventoryMovement.batch_id == ProductBatch.id,
                    InventoryMovement.movement_type == "SALIDA",
                )
                .correlate(ProductBatch)
                .scalar_subquery(),
                0,
            )))
            .filter(ProductBatch.product_id == Product.id, ProductBatch.is_active == True)
            .correlate(Product)
            .scalar_subquery(),
            0,
        ).label("current_stock"),
    )

    if search:
        query = query.filter(
            or_(Product.code.ilike(f"%{search}%"), Product.name.ilike(f"%{search}%"))
        )

    products = query.filter(Product.is_active == True).order_by(Product.name).all()

    stock_data = []
    for p in products:
        total = _get_product_stock(p.id)
        stock_data.append({
            "id": p.id,
            "code": p.code,
            "name": p.name,
            "unit": p.unit,
            "minimum_stock": p.minimum_stock,
            "current_stock": total,
            "is_low": total <= p.minimum_stock,
        })

    return render_template(
        "inventory/stock.html",
        stock_data=stock_data,
        search=search,
        active_page="inventory.stock",
    )


@inventory_bp.route("/batches")
@login_required
@role_required("inventory.view")
def batches():
    search = request.args.get("search", "").strip()
    filter_type = request.args.get("filter", "").strip()

    query = ProductBatch.query.filter(ProductBatch.is_active == True)

    if search:
        query = query.join(Product).filter(
            or_(
                Product.code.ilike(f"%{search}%"),
                Product.name.ilike(f"%{search}%"),
                ProductBatch.batch_number.ilike(f"%{search}%"),
            )
        )

    if filter_type == "low":
        all_batches = query.all()
        batch_ids = []
        for b in all_batches:
            if b.current_quantity <= b.product.minimum_stock and b.current_quantity > 0:
                batch_ids.append(b.id)
        query = query.filter(ProductBatch.id.in_(batch_ids)) if batch_ids else query.filter(ProductBatch.id == -1)
    elif filter_type == "expired":
        query = query.filter(ProductBatch.expiration_date < datetime.now().date())
    elif filter_type == "expiring":
        threshold = datetime.now().date() + timedelta(days=90)
        query = query.filter(
            ProductBatch.expiration_date <= threshold,
            ProductBatch.expiration_date >= datetime.now().date(),
        )

    batch_list = query.order_by(ProductBatch.expiration_date).all()

    return render_template(
        "inventory/batches.html",
        batches=batch_list,
        search=search,
        filter_type=filter_type,
        active_page="inventory.stock",
    )


@inventory_bp.route("/movements")
@login_required
@role_required("inventory.view")
def movements():
    product_id = request.args.get("product_id", "", type=str)
    movement_type = request.args.get("movement_type", "").strip()

    query = InventoryMovement.query

    if product_id:
        query = query.filter(InventoryMovement.product_id == int(product_id))

    if movement_type and movement_type in ("ENTRADA", "SALIDA", "AJUSTE"):
        query = query.filter(InventoryMovement.movement_type == movement_type)

    movement_list = query.order_by(InventoryMovement.created_at.desc()).limit(200).all()
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()

    return render_template(
        "inventory/movements.html",
        movements=movement_list,
        products=products,
        selected_product=product_id,
        selected_type=movement_type,
        active_page="inventory.stock",
    )


@inventory_bp.route("/expiring")
@login_required
@role_required("inventory.view")
def expiring():
    days = request.args.get("days", "90", type=str)
    try:
        days_int = int(days)
    except ValueError:
        days_int = 90

    threshold = datetime.now().date() + timedelta(days=days_int)
    today = datetime.now().date()

    expired = ProductBatch.query.filter(
        ProductBatch.is_active == True,
        ProductBatch.expiration_date < today,
    ).order_by(ProductBatch.expiration_date).all()

    expiring_soon = ProductBatch.query.filter(
        ProductBatch.is_active == True,
        ProductBatch.expiration_date >= today,
        ProductBatch.expiration_date <= threshold,
    ).order_by(ProductBatch.expiration_date).all()

    return render_template(
        "inventory/expiring.html",
        expired=expired,
        expiring_soon=expiring_soon,
        days=days_int,
        now_date=today,
        active_page="inventory.stock",
    )


@inventory_bp.route("/adjust", methods=["GET", "POST"])
@login_required
@role_required("inventory.adjust")
def adjust():
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()

    if request.method == "POST":
        product_id = request.form.get("product_id", "").strip()
        batch_number = request.form.get("batch_number", "").strip()
        expiration_date = request.form.get("expiration_date", "").strip()
        quantity_str = request.form.get("quantity", "").strip()
        description = request.form.get("description", "").strip()
        direction = request.form.get("direction", "").strip()

        if not product_id:
            flash("Seleccione un producto.", "error")
            return render_template(
                "inventory/adjust.html",
                products=products,
                form_data=request.form,
                active_page="inventory.stock",
            )

        if direction not in ("ENTRADA", "SALIDA"):
            flash("Direccion no valida.", "error")
            return render_template(
                "inventory/adjust.html",
                products=products,
                form_data=request.form,
                active_page="inventory.stock",
            )

        try:
            qty = int(quantity_str)
        except (ValueError, TypeError):
            flash("La cantidad no es valida.", "error")
            return render_template(
                "inventory/adjust.html",
                products=products,
                form_data=request.form,
                active_page="inventory.stock",
            )

        if qty <= 0:
            flash("La cantidad debe ser mayor a cero.", "error")
            return render_template(
                "inventory/adjust.html",
                products=products,
                form_data=request.form,
                active_page="inventory.stock",
            )

        if direction == "SALIDA":
            product = Product.query.get(int(product_id))
            current = _get_product_stock(int(product_id))
            if qty > current:
                flash(
                    f"Stock insuficiente. Disponible: {current} {product.unit}.",
                    "error",
                )
                return render_template(
                    "inventory/adjust.html",
                    products=products,
                    form_data=request.form,
                                active_page="inventory.stock",
                )

        if not batch_number:
            batch_number = f"AJT-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        if not expiration_date:
            expiration_date = (datetime.now() + timedelta(days=365)).strftime(
                "%Y-%m-%d"
            )

        try:
            exp_date = datetime.strptime(expiration_date, "%Y-%m-%d").date()
        except ValueError:
            exp_date = (datetime.now() + timedelta(days=365)).date()

        batch = ProductBatch(
            product_id=int(product_id),
            batch_number=batch_number,
            expiration_date=exp_date,
            quantity=0,
            purchase_price=0,
            is_active=True,
        )
        db.session.add(batch)
        db.session.flush()

        movement = InventoryMovement(
            product_id=int(product_id),
            batch_id=batch.id,
            movement_type=direction,
            quantity=qty,
            reference_type="AJUSTE",
            description=description or f"Ajuste manual: {direction}",
            user_id=g.user.id,
        )
        db.session.add(movement)

        audit = AuditLog(
            user_id=g.user.id,
            action="ADJUST",
            module="INVENTORY",
            description=f"Ajuste {direction}: {qty} unidades del producto #{product_id}",
        )
        db.session.add(audit)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        flash(f"Ajuste registrado: {direction} de {qty} unidades.", "success")
        return redirect(url_for("inventory.movements"))

    return render_template(
        "inventory/adjust.html",
        products=products,
        form_data={},
        active_page="inventory.stock",
    )


@inventory_bp.route("/product/<int:product_id>/batches")
@login_required
@role_required("inventory.view")
def product_batches(product_id):
    product = Product.query.get_or_404(product_id)
    batches = (
        ProductBatch.query.filter_by(product_id=product_id, is_active=True)
        .order_by(ProductBatch.expiration_date)
        .all()
    )
    total_stock = _get_product_stock(product_id)

    return render_template(
        "inventory/product_batches.html",
        product=product,
        batches=batches,
        total_stock=total_stock,
        active_page="inventory.stock",
    )


def create_batches_from_purchase(purchase):
    for item in purchase.items:
        batch_number = f"CMP-{purchase.id}-{item.product_id}"
        batch = ProductBatch(
            product_id=item.product_id,
            purchase_id=purchase.id,
            batch_number=batch_number,
            expiration_date=datetime.now().date() + timedelta(days=365),
            quantity=item.quantity,
            purchase_price=item.unit_cost,
            is_active=True,
        )
        db.session.add(batch)
        db.session.flush()

        movement = InventoryMovement(
            product_id=item.product_id,
            batch_id=batch.id,
            movement_type="ENTRADA",
            quantity=item.quantity,
            reference_type="COMPRA",
            reference_id=purchase.id,
            description=f"Entrada por compra #{purchase.id}",
            user_id=purchase.user_id,
        )
        db.session.add(movement)


def fefo_dispatch(product_id, quantity_needed, user_id, reference_type=None, reference_id=None, description=None):
    batches = (
        ProductBatch.query.filter_by(product_id=product_id, is_active=True)
        .filter(ProductBatch.quantity > 0)
        .order_by(ProductBatch.expiration_date)
        .all()
    )

    remaining = quantity_needed
    dispatched = []

    for batch in batches:
        if remaining <= 0:
            break

        available = batch.quantity
        to_dispatch = min(remaining, available)

        batch.quantity -= to_dispatch
        remaining -= to_dispatch

        movement = InventoryMovement(
            product_id=product_id,
            batch_id=batch.id,
            movement_type="SALIDA",
            quantity=to_dispatch,
            reference_type=reference_type,
            reference_id=reference_id,
            description=description or f"Salida FEFO - Lote {batch.batch_number}",
            user_id=user_id,
        )
        db.session.add(movement)
        dispatched.append({"batch_id": batch.id, "quantity": to_dispatch})

    return dispatched, remaining


def _get_product_stock(product_id):
    batches = ProductBatch.query.filter_by(
        product_id=product_id, is_active=True
    ).all()

    total = 0
    for batch in batches:
        incoming = sum(
            m.quantity for m in batch.movements if m.movement_type == "ENTRADA"
        )
        outgoing = sum(
            m.quantity for m in batch.movements if m.movement_type == "SALIDA"
        )
        total += incoming - outgoing

    return total
