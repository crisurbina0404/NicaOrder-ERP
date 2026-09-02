from datetime import date, timedelta
from flask import Blueprint, render_template, g
from sqlalchemy import func
from ..auth import login_required
from ..models import (
    Product, Purchase, Sale, ProductBatch, InventoryMovement,
    Employee, PayrollPeriod, Payroll, PayrollItem,
)

main_bp = Blueprint("main", __name__)

MONTH_NAMES = [
    "", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
]


@main_bp.route("/")
@login_required
def index():
    data = get_dashboard_data()
    return render_template(
        "main/dashboard.html",
        active_page="main.dashboard",
        dashboard_data=data,
    )


@main_bp.route("/dashboard")
@login_required
def dashboard():
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
