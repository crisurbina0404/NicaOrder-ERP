from flask import Blueprint, render_template, request, redirect, url_for, flash, g
from ..auth import login_required, role_required
from ..models import Product, Category, Brand, AuditLog
from ..extensions import db
from sqlalchemy import or_

products_bp = Blueprint("products", __name__, url_prefix="/products")


@products_bp.route("/")
@login_required
@role_required("products.view")
def list():
    search = request.args.get("search", "").strip()
    category_id = request.args.get("category_id", "", type=str)

    query = Product.query

    if search:
        query = query.filter(
            or_(
                Product.code.ilike(f"%{search}%"),
                Product.name.ilike(f"%{search}%"),
            )
        )

    if category_id:
        try:
            query = query.filter(Product.category_id == int(category_id))
        except (ValueError, TypeError):
            pass

    products = query.order_by(Product.name).all()
    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()

    return render_template(
        "products/list.html",
        products=products,
        categories=categories,
        search=search,
        selected_category=category_id,
        active_page="products.list",
    )


@products_bp.route("/create", methods=["GET", "POST"])
@login_required
@role_required("products.manage")
def create():
    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    brands = Brand.query.filter_by(is_active=True).order_by(Brand.name).all()

    if request.method == "POST":
        errors = _validate_form(request.form, exclude_code=None)

        if errors:
            flash(errors[0], "error")
            return render_template(
                "products/form.html",
                form_data=request.form,
                errors=errors,
                categories=categories,
                brands=brands,
                is_edit=False,
                active_page="products.list",
            )

        product = Product(
            code=request.form["code"].strip(),
            name=request.form["name"].strip(),
            description=request.form.get("description", "").strip(),
            category_id=int(request.form["category_id"]),
            brand_id=int(request.form["brand_id"]),
            presentation=request.form.get("presentation", "").strip(),
            unit=request.form["unit"].strip(),
            purchase_price=float(request.form["purchase_price"]),
            sale_price=float(request.form["sale_price"]),
            minimum_stock=int(request.form.get("minimum_stock", 0)),
            sanitary_registration=request.form.get("sanitary_registration", "").strip(),
            is_active=True,
        )

        db.session.add(product)
        audit = AuditLog(
            user_id=g.user.id,
            action="CREATE",
            module="PRODUCTS",
            description=f"Producto creado: {product.code} - {product.name}",
        )
        db.session.add(audit)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Error al guardar el producto.", "error")
            return render_template(
                "products/form.html",
                form_data=request.form,
                errors=[],
                categories=categories,
                brands=brands,
                is_edit=False,
                active_page="products.list",
            )

        flash("Producto registrado correctamente.", "success")
        return redirect(url_for("products.list"))

    return render_template(
        "products/form.html",
        form_data={},
        errors={},
        categories=categories,
        brands=brands,
        is_edit=False,
        active_page="products.list",
    )


@products_bp.route("/<int:product_id>/edit", methods=["GET", "POST"])
@login_required
@role_required("products.manage")
def edit(product_id):
    product = Product.query.get_or_404(product_id)
    categories = Category.query.filter_by(is_active=True).order_by(Category.name).all()
    brands = Brand.query.filter_by(is_active=True).order_by(Brand.name).all()

    if request.method == "POST":
        errors = _validate_form(request.form, exclude_code=product.code)

        if errors:
            flash(errors[0], "error")
            return render_template(
                "products/form.html",
                product=product,
                form_data=request.form,
                errors=errors,
                categories=categories,
                brands=brands,
                is_edit=True,
                active_page="products.list",
            )

        product.code = request.form["code"].strip()
        product.name = request.form["name"].strip()
        product.description = request.form.get("description", "").strip()
        product.category_id = int(request.form["category_id"])
        product.brand_id = int(request.form["brand_id"])
        product.presentation = request.form.get("presentation", "").strip()
        product.unit = request.form["unit"].strip()
        product.purchase_price = float(request.form["purchase_price"])
        product.sale_price = float(request.form["sale_price"])
        product.minimum_stock = int(request.form.get("minimum_stock", 0))
        product.sanitary_registration = request.form.get(
            "sanitary_registration", ""
        ).strip()

        audit = AuditLog(
            user_id=g.user.id,
            action="UPDATE",
            module="PRODUCTS",
            description=f"Producto actualizado: {product.code} - {product.name}",
        )
        db.session.add(audit)
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            flash("Error al actualizar el producto.", "error")
            return render_template(
                "products/form.html",
                product=product,
                form_data=request.form,
                errors=[],
                categories=categories,
                brands=brands,
                is_edit=True,
                active_page="products.list",
            )

        flash("Producto actualizado correctamente.", "success")
        return redirect(url_for("products.list"))

    return render_template(
        "products/form.html",
        product=product,
        form_data=product,
        errors={},
        categories=categories,
        brands=brands,
        is_edit=True,
        active_page="products.list",
    )


@products_bp.route("/<int:product_id>/toggle", methods=["POST"])
@login_required
@role_required("products.manage")
def toggle(product_id):
    product = Product.query.get_or_404(product_id)
    product.is_active = not product.is_active
    status = "activado" if product.is_active else "desactivado"

    audit = AuditLog(
        user_id=g.user.id,
        action="TOGGLE",
        module="PRODUCTS",
        description=f"Producto {status}: {product.code} - {product.name}",
    )
    db.session.add(audit)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("Error al cambiar estado del producto.", "error")
        return redirect(url_for("products.list"))

    flash(f"Producto {status} correctamente.", "success")
    return redirect(url_for("products.list"))


def _validate_form(form, exclude_code=None):
    errors = []

    code = form.get("code", "").strip()
    name = form.get("name", "").strip()
    category_id = form.get("category_id", "").strip()
    brand_id = form.get("brand_id", "").strip()
    unit = form.get("unit", "").strip()
    purchase_price = form.get("purchase_price", "").strip()
    sale_price = form.get("sale_price", "").strip()
    minimum_stock = form.get("minimum_stock", "0").strip()

    if not code:
        errors.append("El codigo es obligatorio.")
    elif exclude_code is None or code != exclude_code:
        existing = Product.query.filter_by(code=code).first()
        if existing:
            errors.append(f"El codigo '{code}' ya esta registrado.")

    if not name:
        errors.append("El nombre es obligatorio.")

    if not category_id:
        errors.append("Seleccione una categoria.")

    if not brand_id:
        errors.append("Seleccione una marca.")

    if not unit:
        errors.append("La unidad es obligatoria.")

    try:
        pp = float(purchase_price)
        if pp < 0:
            errors.append("El precio de compra no puede ser negativo.")
    except (ValueError, TypeError):
        errors.append("El precio de compra no es valido.")

    try:
        sp = float(sale_price)
        if sp < 0:
            errors.append("El precio de venta no puede ser negativo.")
    except (ValueError, TypeError):
        errors.append("El precio de venta no es valido.")

    try:
        ms = int(minimum_stock)
        if ms < 0:
            errors.append("El stock minimo no puede ser negativo.")
    except (ValueError, TypeError):
        errors.append("El stock minimo no es valido.")

    return errors
