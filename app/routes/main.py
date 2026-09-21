from datetime import date, timedelta
from flask import Blueprint, render_template, g
from sqlalchemy import func
from ..auth import login_required
from ..extensions import db
from ..models import (
    Product, Purchase, Sale, SaleItem, ProductBatch, InventoryMovement,
    Employee, Position, PayrollPeriod, Payroll, PayrollItem, PayrollAdjustment,
    Customer,
)

main_bp = Blueprint("main", __name__)

MONTH_NAMES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


@main_bp.route("/")
@login_required
def index():
    return dashboard()


@main_bp.route("/dashboard")
@login_required
def dashboard():
    user = g.user

    # Administrador: vision completa del negocio
    if user.role and user.role.name == "Administrador":
        data = get_dashboard_data()
        return render_template(
            "main/dashboard.html",
            active_page="main.dashboard",
            dashboard_data=data,
        )

    # RRHH: personas, planilla y contrataciones
    if user.has_permission("hr.employees.view"):
        data = _get_hr_dashboard_data()
        return render_template(
            "main/dashboard_rrhh.html",
            active_page="main.dashboard",
            dashboard_data=data,
        )

    # Vendedor/Cajero: sus ventas y clientes
    if user.has_permission("sales.view"):
        data = _get_sales_dashboard_data()
        return render_template(
            "main/dashboard_ventas.html",
            active_page="main.dashboard",
            active_sales=True,
            dashboard_data=data,
        )

    # Bodeguero: cuarentena, stock y compras
    if user.has_permission("inventory.view"):
        data = _get_warehouse_dashboard_data()
        return render_template(
            "main/dashboard_bodega.html",
            active_page="main.dashboard",
            dashboard_data=data,
        )

    # Administrador / fallback: vision completa del negocio
    data = get_dashboard_data()
    return render_template(
        "main/dashboard.html",
        active_page="main.dashboard",
        dashboard_data=data,
    )


def get_dashboard_data():
    today = date.today()
    month_start = today.replace(day=1)

    total_products = Product.query.filter_by(is_active=True).count()

    low_stock_products = []
    for p in Product.query.filter_by(is_active=True).all():
        batches = [b for b in p.batches if b.is_active]
        stock = sum(b.current_quantity for b in batches)
        if stock <= p.minimum_stock:
            low_stock_products.append(p)

    expiring_soon = ProductBatch.query.filter(
        ProductBatch.is_active == True,
        ProductBatch.expiration_date <= today + timedelta(days=90),
        ProductBatch.expiration_date >= today,
    ).count()

    today_sales = Sale.query.filter(
        func.date(Sale.sale_date) == today,
        Sale.status != "CANCELADA",
    ).all()
    today_sales_total = sum(s.total for s in today_sales)
    today_sales_count = len(today_sales)

    month_sales = Sale.query.filter(
        func.date(Sale.sale_date) >= month_start,
        Sale.status != "CANCELADA",
    ).all()
    month_sales_total = sum(s.total for s in month_sales)
    month_sales_count = len(month_sales)

    month_purchases = Purchase.query.filter(
        func.date(Purchase.purchase_date) >= month_start,
        Purchase.status != "CANCELADA",
    ).all()
    month_purchases_total = sum(p.total for p in month_purchases)

    active_employees = Employee.query.filter_by(status="ACTIVO").count()

    payroll_total = 0
    current_period = PayrollPeriod.query.filter(
        PayrollPeriod.month == today.month,
        PayrollPeriod.year == today.year,
    ).first()
    if current_period:
        for payroll in current_period.payrolls:
            if payroll.status in ("CALCULADA", "APROBADA", "PAGADA"):
                payroll_total = payroll.total_net
                break

    recent_sales = Sale.query.order_by(Sale.created_at.desc()).limit(5).all()

    recent_movements = InventoryMovement.query.order_by(
        InventoryMovement.created_at.desc()
    ).limit(5).all()

    return {
        "total_products": total_products,
        "low_stock_count": len(low_stock_products),
        "low_stock_products": low_stock_products[:5],
        "expiring_soon": expiring_soon,
        "today_sales_total": today_sales_total,
        "today_sales_count": today_sales_count,
        "month_sales_total": month_sales_total,
        "month_sales_count": month_sales_count,
        "month_purchases_total": month_purchases_total,
        "active_employees": active_employees,
        "payroll_total": payroll_total,
        "recent_sales": recent_sales,
        "recent_movements": recent_movements,
        "current_period": current_period,
        "today": today,
        "month_names": MONTH_NAMES,
    }


# ===== Dashboard RRHH: personal, planilla y contrataciones =====

def _get_hr_dashboard_data():
    today = date.today()
    month_start = today.replace(day=1)

    total_employees = Employee.query.count()
    active_employees = Employee.query.filter_by(status="ACTIVO").count()
    inactive_employees = total_employees - active_employees

    # Distribucion por departamento (para barras)
    dept_counts = {}
    for emp in Employee.query.all():
        name = emp.department.name if emp.department else "Sin departamento"
        dept_counts[name] = dept_counts.get(name, 0) + 1
    max_dept_count = max(dept_counts.values()) if dept_counts else 0
    dept_distribution = sorted(dept_counts.items(), key=lambda kv: kv[1], reverse=True)

    # Cumpleanos del mes
    birthdays = [
        e for e in Employee.query.filter_by(status="ACTIVO").all()
        if e.birth_date and e.birth_date.month == today.month
    ]
    birthdays.sort(key=lambda e: e.birth_date.day)

    # Contrataciones del mes (por fecha de ingreso, cualquier ano)
    month_hires = [
        e for e in Employee.query.all()
        if e.hire_date.month == today.month
    ]

    # Nominas
    periods = PayrollPeriod.query.order_by(
        PayrollPeriod.year.desc(), PayrollPeriod.month.desc()
    ).all()
    current_period = next(
        (p for p in periods if p.month == today.month and p.year == today.year),
        None,
    )
    period_status = current_period.status if current_period else "SIN PERIODO"
    period_net = 0.0
    period_count = 0
    if current_period:
        for payroll in current_period.payrolls:
            if payroll.status in ("CALCULADA", "APROBADA", "PAGADA"):
                period_net = payroll.total_net
                period_count = len(payroll.items)
                break

    # Novedades (ajustes) del periodo actual
    pending_adjustments = 0
    if current_period:
        pending_adjustments = PayrollAdjustment.query.filter_by(
            payroll_period_id=current_period.id
        ).count()

    # Ultimos ingresos al empleo (ordenados por fecha de contratacion)
    recent_hires = Employee.query.filter_by(status="ACTIVO").order_by(
        Employee.hire_date.desc()
    ).limit(5).all()

    return {
        "total_employees": total_employees,
        "active_employees": active_employees,
        "inactive_employees": inactive_employees,
        "dept_distribution": dept_distribution,
        "max_dept_count": max_dept_count,
        "birthdays": birthdays,
        "month_hires": month_hires,
        "current_period": current_period,
        "period_status": period_status,
        "period_net": period_net,
        "period_count": period_count,
        "pending_adjustments": pending_adjustments,
        "recent_hires": recent_hires,
        "today": today,
        "month_names": MONTH_NAMES,
    }


# ===== Dashboard Ventas: desempeno propio del vendedor/cajero =====

def _get_sales_dashboard_data():
    today = date.today()
    month_start = today.replace(day=1)
    user_id = g.user.id

    my_today_sales = Sale.query.filter(
        Sale.user_id == user_id,
        func.date(Sale.sale_date) == today,
        Sale.status != "CANCELADA",
    ).all()
    my_today_total = sum(s.total for s in my_today_sales)
    my_today_count = len(my_today_sales)

    my_month_sales = Sale.query.filter(
        Sale.user_id == user_id,
        func.date(Sale.sale_date) >= month_start,
        Sale.status != "CANCELADA",
    ).all()
    my_month_total = sum(s.total for s in my_month_sales)
    my_month_count = len(my_month_sales)

    # Ventas de todo el equipo (todos los vendedores) — hoy y mes
    team_today_sales = Sale.query.filter(
        func.date(Sale.sale_date) == today,
        Sale.status != "CANCELADA",
    ).all()
    team_today_total = sum(s.total for s in team_today_sales)
    team_today_count = len(team_today_sales)

    team_month_sales = Sale.query.filter(
        func.date(Sale.sale_date) >= month_start,
        Sale.status != "CANCELADA",
    ).all()
    team_month_total = sum(s.total for s in team_month_sales)
    team_month_count = len(team_month_sales)

    my_draft_sales = Sale.query.filter(
        Sale.user_id == user_id,
        Sale.status == "BORRADOR",
    ).order_by(Sale.created_at.desc()).all()

    my_cancelled = Sale.query.filter(
        Sale.user_id == user_id,
        func.date(Sale.sale_date) >= month_start,
        Sale.status == "CANCELADA",
    ).count()

    # Ticket promedio del mes
    avg_ticket = (my_month_total / my_month_count) if my_month_count else 0.0

    # Meta del mes: promedio de los ultimos 3 meses del propio usuario (min C$5,000)
    three_months_ago = (month_start - timedelta(days=1)).replace(day=1)
    hist_sales = Sale.query.filter(
        Sale.user_id == user_id,
        func.date(Sale.sale_date) >= three_months_ago,
        func.date(Sale.sale_date) < month_start,
        Sale.status != "CANCELADA",
    ).all()
    months_span = max((month_start - three_months_ago).days / 30.0, 1.0)
    hist_monthly_avg = (sum(s.total for s in hist_sales) / months_span) if hist_sales else 0.0
    monthly_goal = max(hist_monthly_avg, 5000.0)
    goal_percent = min((my_month_total / monthly_goal * 100) if monthly_goal else 0, 100)

    # Top productos vendidos por el usuario este mes
    top_products = (
        db.session.query(
            Product.name,
            func.sum(SaleItem.quantity).label("qty"),
            func.sum(SaleItem.subtotal).label("total"),
        )
        .join(SaleItem, SaleItem.product_id == Product.id)
        .join(Sale, Sale.id == SaleItem.sale_id)
        .filter(
            Sale.user_id == user_id,
            func.date(Sale.sale_date) >= month_start,
            Sale.status != "CANCELADA",
        )
        .group_by(Product.id)
        .order_by(func.sum(SaleItem.quantity).desc())
        .limit(5)
        .all()
    )

    # Top clientes del usuario este mes
    top_customers = (
        db.session.query(
            Customer.name,
            func.count(Sale.id).label("count"),
            func.sum(Sale.total).label("total"),
        )
        .join(Sale, Sale.customer_id == Customer.id)
        .filter(
            Sale.user_id == user_id,
            func.date(Sale.sale_date) >= month_start,
            Sale.status != "CANCELADA",
        )
        .group_by(Customer.id)
        .order_by(func.sum(Sale.total).desc())
        .limit(5)
        .all()
    )

    # Metodos de pago usados por el usuario este mes
    payment_counts = {}
    for s in my_month_sales:
        payment_counts[s.payment_method] = payment_counts.get(s.payment_method, 0) + 1

    # Ultimas ventas del equipo (globales, todos los vendedores)
    recent_sales = Sale.query.order_by(Sale.created_at.desc()).limit(6).all()

    active_customers = Customer.query.filter_by(is_active=True).count()

    return {
        "my_today_total": my_today_total,
        "my_today_count": my_today_count,
        "team_today_total": team_today_total,
        "team_today_count": team_today_count,
        "team_month_total": team_month_total,
        "team_month_count": team_month_count,
        "my_month_total": my_month_total,
        "my_month_count": my_month_count,
        "my_draft_sales": my_draft_sales,
        "my_draft_count": len(my_draft_sales),
        "my_cancelled": my_cancelled,
        "avg_ticket": avg_ticket,
        "monthly_goal": monthly_goal,
        "goal_percent": goal_percent,
        "top_products": top_products,
        "top_customers": top_customers,
        "payment_counts": payment_counts,
        "recent_sales": recent_sales,
        "active_customers": active_customers,
        "today": today,
        "month_names": MONTH_NAMES,
    }


# ===== Dashboard Bodega: cuarentena, stock y compras =====

def _get_warehouse_dashboard_data():
    today = date.today()

    # Lotes pendientes de liberar de cuarentena
    quarantine_batches = ProductBatch.query.filter(
        ProductBatch.is_active == True,
        ProductBatch.quarantine_status == "CUARENTENA",
    ).order_by(ProductBatch.created_at.desc()).all()

    total_products = Product.query.filter_by(is_active=True).count()

    # Stock bajo y vencimientos
    low_stock_products = []
    total_stock_value = 0.0
    for p in Product.query.filter_by(is_active=True).all():
        batches = [b for b in p.batches if b.is_active]
        stock = sum(b.current_quantity for b in batches)
        for b in batches:
            total_stock_value += b.current_quantity * b.purchase_price
        if stock <= p.minimum_stock:
            low_stock_products.append({"product": p, "stock": stock})

    expired_batches = ProductBatch.query.filter(
        ProductBatch.is_active == True,
        ProductBatch.expiration_date < today,
    ).count()

    expiring_soon_batches = ProductBatch.query.filter(
        ProductBatch.is_active == True,
        ProductBatch.expiration_date <= today + timedelta(days=90),
        ProductBatch.expiration_date >= today,
    ).order_by(ProductBatch.expiration_date).all()

    month_start = today.replace(day=1)
    month_purchases = Purchase.query.filter(
        func.date(Purchase.purchase_date) >= month_start,
        Purchase.status != "CANCELADA",
    ).all()
    month_purchases_total = sum(p.total for p in month_purchases)

    # Compras pendientes de recibir
    pending_purchases = Purchase.query.filter(
        Purchase.status == "BORRADOR",
    ).order_by(Purchase.created_at.desc()).limit(6).all()

    recent_movements = InventoryMovement.query.order_by(
        InventoryMovement.created_at.desc()
    ).limit(6).all()

    return {
        "quarantine_count": len(quarantine_batches),
        "quarantine_batches": quarantine_batches[:5],
        "total_products": total_products,
        "low_stock_count": len(low_stock_products),
        "low_stock_products": low_stock_products[:5],
        "expired_batches": expired_batches,
        "expiring_soon_batches": expiring_soon_batches[:5],
        "expiring_soon_count": len(expiring_soon_batches),
        "total_stock_value": total_stock_value,
        "month_purchases_total": month_purchases_total,
        "pending_purchases": pending_purchases,
        "recent_movements": recent_movements,
        "today": today,
        "month_names": MONTH_NAMES,
    }
