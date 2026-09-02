from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, g
from sqlalchemy import func, extract
from ..auth import login_required, role_required
from ..extensions import db
from ..models import (
    Product, Category, Brand,
    Supplier, Purchase, PurchaseItem,
    Customer, Sale, SaleItem,
    ProductBatch, InventoryMovement,
    Employee, Department,
    PayrollPeriod, Payroll, PayrollItem,
)

reports_bp = Blueprint("reports", __name__, url_prefix="/reports")

MONTH_NAMES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


def _parse_date(date_str):
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        return None


def _get_date_range():
    today = date.today()
    start = today.replace(day=1)
    return start, today


@reports_bp.route("/")
@login_required
@role_required("reports.view")
def index():
    return render_template(
        "reports/index.html",
                active_page="reports.index",
    )


@reports_bp.route("/compras/periodo")
@login_required
@role_required("reports.view")
def compras_periodo():
    start_str = request.args.get("start", "")
    end_str = request.args.get("end", "")
    status = request.args.get("status", "")

    start = _parse_date(start_str)
    end = _parse_date(end_str)

    if not start or not end:
        default_start, default_end = _get_date_range()
        start = start or default_start
        end = end or default_end

    query = Purchase.query.filter(
        func.date(Purchase.purchase_date) >= start,
        func.date(Purchase.purchase_date) <= end,
    )

    if status:
        query = query.filter(Purchase.status == status)

    purchases = query.order_by(Purchase.purchase_date.desc()).all()
    total = sum(p.total for p in purchases if p.status != "CANCELADA")

    return render_template(
        "reports/compras_periodo.html",
        purchases=purchases,
        total=total,
        start=start,
        end=end,
        status=status,
        month_names=MONTH_NAMES,
                active_page="reports.index",
    )


@reports_bp.route("/compras/proveedor")
@login_required
@role_required("reports.view")
def compras_proveedor():
    start_str = request.args.get("start", "")
    end_str = request.args.get("end", "")

    start = _parse_date(start_str)
    end = _parse_date(end_str)

    default_start, default_end = _get_date_range()
    start = start or default_start
    end = end or default_end

    query = db.session.query(
        Supplier.name,
        func.count(Purchase.id).label("count"),
        func.sum(Purchase.total).label("total"),
    ).join(Purchase, Purchase.supplier_id == Supplier.id).filter(
        func.date(Purchase.purchase_date) >= start,
        func.date(Purchase.purchase_date) <= end,
        Purchase.status != "CANCELADA",
    ).group_by(Supplier.name).order_by(func.sum(Purchase.total).desc())

    results = query.all()

    return render_template(
        "reports/compras_proveedor.html",
        results=results,
        start=start,
        end=end,
                active_page="reports.index",
    )


@reports_bp.route("/ventas/periodo")
@login_required
@role_required("reports.view")
def ventas_periodo():
    start_str = request.args.get("start", "")
    end_str = request.args.get("end", "")
    status = request.args.get("status", "")

    start = _parse_date(start_str)
    end = _parse_date(end_str)

    if not start or not end:
        default_start, default_end = _get_date_range()
        start = start or default_start
        end = end or default_end

    query = Sale.query.filter(
        func.date(Sale.sale_date) >= start,
        func.date(Sale.sale_date) <= end,
    )

    if status:
        query = query.filter(Sale.status == status)

    sales = query.order_by(Sale.sale_date.desc()).all()
    total = sum(s.total for s in sales if s.status != "CANCELADA")

    return render_template(
        "reports/ventas_periodo.html",
        sales=sales,
        total=total,
        start=start,
        end=end,
        status=status,
                active_page="reports.index",
    )


@reports_bp.route("/ventas/usuario")
@login_required
@role_required("reports.view")
def ventas_usuario():
    start_str = request.args.get("start", "")
    end_str = request.args.get("end", "")

    start = _parse_date(start_str)
    end = _parse_date(end_str)

    default_start, default_end = _get_date_range()
    start = start or default_start
    end = end or default_end

    query = db.session.query(
        Sale.user_id,
        func.count(Sale.id).label("count"),
        func.sum(Sale.total).label("total"),
    ).filter(
        func.date(Sale.sale_date) >= start,
        func.date(Sale.sale_date) <= end,
        Sale.status != "CANCELADA",
    ).group_by(Sale.user_id).order_by(func.sum(Sale.total).desc())

    results = query.all()

    user_data = []
    from ..models.security import User
    for user_id, count, total in results:
        user = db.session.get(User, user_id)
        user_data.append({
            "name": user.full_name if user else "Desconocido",
            "count": count,
            "total": total or 0,
        })

    return render_template(
        "reports/ventas_usuario.html",
        results=user_data,
        start=start,
        end=end,
                active_page="reports.index",
    )


@reports_bp.route("/ventas/productos")
@login_required
@role_required("reports.view")
def ventas_productos():
    start_str = request.args.get("start", "")
    end_str = request.args.get("end", "")
    limit = request.args.get("limit", "20")

    start = _parse_date(start_str)
    end = _parse_date(end_str)

    default_start, default_end = _get_date_range()
    start = start or default_start
    end = end or default_end

    try:
        limit = int(limit)
    except ValueError:
        limit = 20
    limit = min(limit, 100)

    query = db.session.query(
        Product.name,
        Product.code,
        func.sum(SaleItem.quantity).label("qty"),
        func.sum(SaleItem.subtotal).label("total"),
    ).join(SaleItem, SaleItem.product_id == Product.id).join(
        Sale, Sale.id == SaleItem.sale_id
    ).filter(
        func.date(Sale.sale_date) >= start,
        func.date(Sale.sale_date) <= end,
        Sale.status != "CANCELADA",
    ).group_by(Product.id).order_by(func.sum(SaleItem.quantity).desc()).limit(limit)

    results = query.all()

    return render_template(
        "reports/ventas_productos.html",
        results=results,
        start=start,
        end=end,
                active_page="reports.index",
    )


@reports_bp.route("/ventas/metodos")
@login_required
@role_required("reports.view")
def ventas_metodos():
    start_str = request.args.get("start", "")
    end_str = request.args.get("end", "")

    start = _parse_date(start_str)
    end = _parse_date(end_str)

    default_start, default_end = _get_date_range()
    start = start or default_start
    end = end or default_end

    query = db.session.query(
        Sale.payment_method,
        func.count(Sale.id).label("count"),
        func.sum(Sale.total).label("total"),
    ).filter(
        func.date(Sale.sale_date) >= start,
        func.date(Sale.sale_date) <= end,
        Sale.status != "CANCELADA",
    ).group_by(Sale.payment_method).order_by(func.sum(Sale.total).desc())

    results = query.all()

    labels = {
        "EFECTIVO": "Efectivo",
        "TARJETA": "Tarjeta",
        "TRANSFERENCIA": "Transferencia",
        "CREDITO": "Credito",
    }

    return render_template(
        "reports/ventas_metodos.html",
        results=results,
        labels=labels,
        start=start,
        end=end,
                active_page="reports.index",
    )


@reports_bp.route("/inventario/actuales")
@login_required
@role_required("reports.view")
def inventario_actuales():
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()

    stock_data = []
    for p in products:
        batches = [b for b in p.batches if b.is_active]
        total_stock = sum(b.current_quantity for b in batches)
        stock_data.append({
            "product": p,
            "stock": total_stock,
            "min_stock": p.minimum_stock,
            "batches": len(batches),
        })

    return render_template(
        "reports/inventario_actuales.html",
        stock_data=stock_data,
                active_page="reports.index",
    )


@reports_bp.route("/inventario/stock-bajo")
@login_required
@role_required("reports.view")
def inventario_stock_bajo():
    products = Product.query.filter_by(is_active=True).order_by(Product.name).all()

    low_stock = []
    for p in products:
        batches = [b for b in p.batches if b.is_active]
        total_stock = sum(b.current_quantity for b in batches)
        if total_stock <= p.minimum_stock:
            low_stock.append({
                "product": p,
                "stock": total_stock,
                "min_stock": p.minimum_stock,
            })

    return render_template(
        "reports/inventario_stock_bajo.html",
        stock_data=low_stock,
                active_page="reports.index",
    )


@reports_bp.route("/inventario/vencidos")
@login_required
@role_required("reports.view")
def inventario_vencidos():
    batches = ProductBatch.query.filter(
        ProductBatch.is_active == True,
        ProductBatch.expiration_date < date.today(),
    ).order_by(ProductBatch.expiration_date).all()

    return render_template(
        "reports/inventario_vencidos.html",
        batches=batches,
                active_page="reports.index",
    )


@reports_bp.route("/inventario/proximos-vencer")
@login_required
@role_required("reports.view")
def inventario_proximos_vencer():
    threshold = date.today() + timedelta(days=90)
    batches = ProductBatch.query.filter(
        ProductBatch.is_active == True,
        ProductBatch.expiration_date <= threshold,
        ProductBatch.expiration_date >= date.today(),
    ).order_by(ProductBatch.expiration_date).all()

    return render_template(
        "reports/inventario_proximos_vencer.html",
        batches=batches,
                active_page="reports.index",
    )


@reports_bp.route("/inventario/movimientos")
@login_required
@role_required("reports.view")
def inventario_movimientos():
    start_str = request.args.get("start", "")
    end_str = request.args.get("end", "")
    movement_type = request.args.get("type", "")

    start = _parse_date(start_str)
    end = _parse_date(end_str)

    default_start, default_end = _get_date_range()
    start = start or default_start
    end = end or default_end

    query = InventoryMovement.query.filter(
        func.date(InventoryMovement.created_at) >= start,
        func.date(InventoryMovement.created_at) <= end,
    )

    if movement_type:
        query = query.filter(InventoryMovement.movement_type == movement_type)

    movements = query.order_by(InventoryMovement.created_at.desc()).all()

    return render_template(
        "reports/inventario_movimientos.html",
        movements=movements,
        start=start,
        end=end,
        movement_type=movement_type,
                active_page="reports.index",
    )


@reports_bp.route("/rrhh/planilla-mes")
@login_required
@role_required("reports.view")
def rrhh_planilla_mes():
    start_str = request.args.get("start", "")
    end_str = request.args.get("end", "")

    start = _parse_date(start_str)
    end = _parse_date(end_str)

    default_start, default_end = _get_date_range()
    start = start or default_start
    end = end or default_end

    periods = PayrollPeriod.query.filter(
        func.date(PayrollPeriod.created_at) >= start,
        func.date(PayrollPeriod.created_at) <= end,
    ).order_by(PayrollPeriod.year.desc(), PayrollPeriod.month.desc()).all()

    data = []
    for period in periods:
        for payroll in period.payrolls:
            data.append({
                "period": period,
                "payroll": payroll,
            })

    return render_template(
        "reports/rrhh_planilla_mes.html",
        data=data,
        start=start,
        end=end,
        month_names=MONTH_NAMES,
                active_page="reports.index",
    )


@reports_bp.route("/rrhh/pagos-empleado")
@login_required
@role_required("reports.view")
def rrhh_pagos_empleado():
    start_str = request.args.get("start", "")
    end_str = request.args.get("end", "")

    start = _parse_date(start_str)
    end = _parse_date(end_str)

    default_start, default_end = _get_date_range()
    start = start or default_start
    end = end or default_end

    query = db.session.query(
        PayrollItem.employee_id,
        func.sum(PayrollItem.gross_salary).label("gross"),
        func.sum(PayrollItem.employee_inss).label("inss"),
        func.sum(PayrollItem.monthly_income_tax).label("ir"),
        func.sum(PayrollItem.net_salary).label("net"),
        func.count(PayrollItem.id).label("count"),
    ).join(Payroll, Payroll.id == PayrollItem.payroll_id).join(
        PayrollPeriod, PayrollPeriod.id == Payroll.payroll_period_id
    ).filter(
        Payroll.status.in_(["CALCULADA", "APROBADA", "PAGADA"]),
        func.date(PayrollPeriod.created_at) >= start,
        func.date(PayrollPeriod.created_at) <= end,
    ).group_by(PayrollItem.employee_id).order_by(
        func.sum(PayrollItem.net_salary).desc()
    )

    results = query.all()

    employee_data = []
    for emp_id, gross, inss, ir, net, count in results:
        emp = db.session.get(Employee, emp_id)
        employee_data.append({
            "employee": emp,
            "gross": gross or 0,
            "inss": inss or 0,
            "ir": ir or 0,
            "net": net or 0,
            "count": count,
        })

    return render_template(
        "reports/rrhh_pagos_empleado.html",
        results=employee_data,
        start=start,
        end=end,
                active_page="reports.index",
    )


@reports_bp.route("/rrhh/totales")
@login_required
@role_required("reports.view")
def rrhh_totales():
    start_str = request.args.get("start", "")
    end_str = request.args.get("end", "")

    start = _parse_date(start_str)
    end = _parse_date(end_str)

    default_start, default_end = _get_date_range()
    start = start or default_start
    end = end or default_end

    query = db.session.query(
        func.sum(PayrollItem.gross_salary).label("gross"),
        func.sum(PayrollItem.employee_inss).label("inss"),
        func.sum(PayrollItem.monthly_income_tax).label("ir"),
        func.sum(PayrollItem.other_deductions).label("other"),
        func.sum(PayrollItem.net_salary).label("net"),
        func.count(PayrollItem.id).label("count"),
    ).join(Payroll, Payroll.id == PayrollItem.payroll_id).join(
        PayrollPeriod, PayrollPeriod.id == Payroll.payroll_period_id
    ).filter(
        Payroll.status.in_(["CALCULADA", "APROBADA", "PAGADA"]),
        func.date(PayrollPeriod.created_at) >= start,
        func.date(PayrollPeriod.created_at) <= end,
    )

    result = query.one()

    return render_template(
        "reports/rrhh_totales.html",
        gross=result.gross or 0,
        inss=result.inss or 0,
        ir=result.ir or 0,
        other=result.other or 0,
        net=result.net or 0,
        count=result.count or 0,
        start=start,
        end=end,
                active_page="reports.index",
    )

