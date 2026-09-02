import sys
import os
import secrets

os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"

from app.config import Config
Config.SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from datetime import date, timedelta
from app import create_app
from app.extensions import db as _db
from app.models import (
    User, Role, Permission, AuditLog,
    Product, Supplier, Purchase, PurchaseItem,
    Customer, Sale, SaleItem,
    ProductBatch, InventoryMovement,
    Employee, SalaryHistory,
    PayrollParameter, IncomeTaxBracket,
    PayrollPeriod, Payroll, PayrollItem,
)


@pytest.fixture(scope="session")
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False

    with app.app_context():
        _seed_test_data()
        yield app
        _db.session.remove()


@pytest.fixture(scope="function")
def client(app):
    with app.test_client() as client:
        with app.app_context():
            yield client


def _seed_test_data():
    existing_roles = {r.name: r for r in Role.query.all()}
    existing_perms = {p.name: p for p in Permission.query.all()}

    rrhh_role = existing_roles.get("RRHH")
    if not rrhh_role:
        rrhh_role = Role(name="RRHH", description="Recursos Humanos")
        _db.session.add(rrhh_role)
        _db.session.flush()

    rrhh_perms = [existing_perms[p] for p in ("hr.employees.view", "hr.employees.manage", "payroll.view", "payroll.manage") if p in existing_perms]
    rrhh_role.permissions = rrhh_perms

    vendedor_role = existing_roles.get("Vendedor")

    admin_user = User.query.filter_by(username="admin").first()
    if admin_user:
        admin_user.set_password("test1234")

    rrhh_user = User.query.filter_by(username="rrhh").first()
    if not rrhh_user:
        rrhh_user = User(
            username="rrhh",
            full_name="RRHH Test",
            email="rrhh@test.com",
            role_id=rrhh_role.id,
            is_active=True,
        )
        rrhh_user.set_password("test1234")
        _db.session.add(rrhh_user)

    vendedor_user = User.query.filter_by(username="vendedor").first()
    if not vendedor_user and vendedor_role:
        vendedor_user = User(
            username="vendedor",
            full_name="Vendedor Test",
            email="vendedor@test.com",
            role_id=vendedor_role.id,
            is_active=True,
        )
        vendedor_user.set_password("test1234")
        _db.session.add(vendedor_user)

    existing_products = {p.code for p in Product.query.filter_by(is_active=True).all()}
    cat = _db.session.execute(
        _db.text("SELECT id FROM categories LIMIT 1")
    ).fetchone()
    brand = _db.session.execute(
        _db.text("SELECT id FROM brands LIMIT 1")
    ).fetchone()

    if cat and brand:
        test_product = None
        if "TEST-001" not in existing_products:
            test_product = Product(
                code="TEST-001", name="Producto Test Venta",
                description="Producto para pruebas de venta",
                category_id=cat[0], brand_id=brand[0],
                presentation="Caja", unit="Caja",
                purchase_price=50.0, sale_price=100.0,
                minimum_stock=5, is_active=True,
            )
            _db.session.add(test_product)
            _db.session.flush()

        existing_batches = _db.session.execute(
            _db.text("SELECT COUNT(*) FROM product_batches")
        ).fetchone()

        if test_product and existing_batches and existing_batches[0] == 0:
            batch1 = ProductBatch(
                product_id=test_product.id,
                batch_number="LOT-TEST-001",
                expiration_date=date.today() + timedelta(days=180),
                quantity=10, purchase_price=50.0, is_active=True,
            )
            batch2 = ProductBatch(
                product_id=test_product.id,
                batch_number="LOT-TEST-002",
                expiration_date=date.today() + timedelta(days=90),
                quantity=5, purchase_price=55.0, is_active=True,
            )
            _db.session.add_all([batch1, batch2])
            _db.session.flush()

            user_id = admin_user.id if admin_user else 1
            for b in [batch1, batch2]:
                _db.session.add(InventoryMovement(
                    product_id=test_product.id,
                    batch_id=b.id,
                    movement_type="ENTRADA",
                    quantity=b.quantity,
                    reference_type="TEST_SEED",
                    description="Entrada de prueba",
                    user_id=user_id,
                ))

    _db.session.commit()


def login(client, username="admin", password="test1234"):
    return client.post("/auth/login", data={
        "username": username, "password": password,
    }, follow_redirects=True)


class TestLogin:
    def test_login_success(self, client):
        resp = login(client)
        assert resp.status_code == 200
        assert b"Dashboard" in resp.data

    def test_login_wrong_password(self, client):
        resp = login(client, password="wrong123")
        assert b"incorrectos" in resp.data

    def test_login_unknown_user(self, client):
        resp = login(client, username="noexiste")
        assert b"incorrectos" in resp.data

    def test_login_empty_fields(self, client):
        resp = client.post("/auth/login", data={"username": "", "password": ""}, follow_redirects=True)
        assert b"Ingrese usuario y contrasena" in resp.data

    def test_login_normalizes_username(self, client):
        resp = login(client, username="Admin")
        assert resp.status_code == 200

    def test_logout_requires_post(self, client):
        login(client)
        resp = client.get("/auth/logout")
        assert resp.status_code == 405

    def test_logout_post(self, client):
        login(client)
        resp = client.post("/auth/logout", follow_redirects=True)
        assert b"Cerrada" in resp.data or b"login" in resp.data


class TestCreateUser:
    def test_admin_seeded(self, app):
        from werkzeug.security import check_password_hash
        with app.app_context():
            user = User.query.filter_by(username="admin").first()
            assert user is not None
            assert user.is_active is True
            assert check_password_hash(user.password_hash, "test1234")

    def test_password_hashed(self, app):
        from werkzeug.security import check_password_hash
        with app.app_context():
            user = User.query.filter_by(username="admin").first()
            assert user.password_hash != "test1234"
            assert check_password_hash(user.password_hash, "test1234")

    def test_password_min_length(self, app):
        with app.app_context():
            user = User(username="testpw", full_name="T", email="tpw@test.com",
                        role_id=1, is_active=True)
            with pytest.raises(ValueError):
                user.set_password("short")


class TestRegisterProduct:
    def test_create_product(self, client):
        login(client)
        resp = client.post("/products/create", data={
            "code": "MED-NEW-001", "name": "Amoxicilina 500mg",
            "description": "Antibiotico", "category_id": "1", "brand_id": "1",
            "presentation": "Caja x 10", "unit": "Caja",
            "purchase_price": "60", "sale_price": "100",
            "minimum_stock": "5", "sanitary_registration": "INV-001",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Amoxicilina" in resp.data

    def test_duplicate_code_rejected(self, client, app):
        login(client)
        with app.app_context():
            existing = Product.query.first()
            code = existing.code if existing else "PP-001"
        resp = client.post("/products/create", data={
            "code": code, "name": "Duplicado",
            "category_id": "1", "brand_id": "1", "unit": "Caja",
            "purchase_price": "50", "sale_price": "80", "minimum_stock": "5",
        }, follow_redirects=True)
        assert b"ya esta registrado" in resp.data

    def test_negative_price_rejected(self, client):
        login(client)
        resp = client.post("/products/create", data={
            "code": "NEG-001", "name": "Negativo",
            "category_id": "1", "brand_id": "1", "unit": "Caja",
            "purchase_price": "-10", "sale_price": "80", "minimum_stock": "5",
        }, follow_redirects=True)
        assert b"negativo" in resp.data


class TestRegisterSupplier:
    def test_create_supplier(self, client):
        login(client)
        resp = client.post("/suppliers/create", data={
            "name": "Proveedor Nuevo SA", "tax_id": "J001000009999",
            "phone": "8888-3000", "email": "prov@test.com",
            "address": "Managua", "contact_person": "Pedro Perez",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Proveedor Nuevo" in resp.data

    def test_duplicate_tax_id_rejected(self, client, app):
        login(client)
        with app.app_context():
            existing = Supplier.query.first()
            tax_id = existing.tax_id if existing else "J001001001"
        resp = client.post("/suppliers/create", data={
            "name": "Otro Proveedor", "tax_id": tax_id,
        }, follow_redirects=True)
        assert b"ya esta registrado" in resp.data

    def test_duplicate_name_rejected(self, client, app):
        login(client)
        with app.app_context():
            existing = Supplier.query.first()
            name = existing.name if existing else "Distribuidora"
        resp = client.post("/suppliers/create", data={
            "name": name, "tax_id": "J001000009999",
        }, follow_redirects=True)
        assert b"ya esta registrado" in resp.data


class TestRegisterCustomer:
    def test_create_customer(self, client):
        login(client)
        resp = client.post("/customers/create", data={
            "name": "Cliente Nuevo", "identity_number": "J002000009999",
            "phone": "8888-4000", "email": "cli@test.com",
            "address": "Managua",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_duplicate_identity_rejected(self, client, app):
        login(client)
        with app.app_context():
            existing = Customer.query.first()
            ident = existing.identity_number if existing else "J101001001"
        resp = client.post("/customers/create", data={
            "name": "Duplicado", "identity_number": ident,
        }, follow_redirects=True)
        assert b"ya esta registrado" in resp.data


class TestPurchaseFlow:
    _invoice_counter = 0

    def _get_supplier_id(self, app):
        with app.app_context():
            s = Supplier.query.filter_by(is_active=True).first()
            return s.id if s else None

    def _get_product_ids(self, app, n=2):
        with app.app_context():
            products = Product.query.filter_by(is_active=True).limit(n).all()
            return [p.id for p in products]

    def _next_invoice(self):
        TestPurchaseFlow._invoice_counter += 1
        return f"FAC-TEST-{TestPurchaseFlow._invoice_counter:04d}"

    def test_create_purchase(self, client, app):
        login(client)
        supplier_id = self._get_supplier_id(app)
        product_ids = self._get_product_ids(app, 2)
        resp = client.post("/purchases/create", data={
            "supplier_id": str(supplier_id),
            "purchase_date": date.today().strftime("%Y-%m-%d"),
            "invoice_number": self._next_invoice(),
            "invoice_type": "FACTURA",
            "discount": "0", "tax": "0", "notes": "Compra test",
            "item_product_id[]": [str(pid) for pid in product_ids],
            "item_quantity[]": ["10", "5"],
            "item_unit_cost[]": ["50", "75"],
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_receive_purchase_creates_batches(self, client, app):
        login(client)
        supplier_id = self._get_supplier_id(app)
        product_ids = self._get_product_ids(app, 2)
        client.post("/purchases/create", data={
            "supplier_id": str(supplier_id),
            "purchase_date": date.today().strftime("%Y-%m-%d"),
            "invoice_number": self._next_invoice(),
            "invoice_type": "FACTURA",
            "discount": "0", "tax": "0", "notes": "",
            "item_product_id[]": [str(pid) for pid in product_ids],
            "item_quantity[]": ["10", "5"],
            "item_unit_cost[]": ["50", "75"],
        }, follow_redirects=True)

        with app.app_context():
            purchase = Purchase.query.filter_by(status="BORRADOR").order_by(Purchase.id.desc()).first()
            assert purchase is not None
            purchase_id = purchase.id

        resp = client.post(f"/purchases/{purchase_id}/status", data={
            "status": "RECIBIDA",
        }, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            purchase = Purchase.query.get(purchase_id)
            assert purchase.status == "RECIBIDA"
            batches = ProductBatch.query.filter_by(purchase_id=purchase_id).all()
            assert len(batches) == 2
            for batch in batches:
                assert batch.quarantine_status == "CUARENTENA"

    def test_receive_creates_inventory_movements(self, client, app):
        login(client)
        supplier_id = self._get_supplier_id(app)
        product_ids = self._get_product_ids(app, 2)
        client.post("/purchases/create", data={
            "supplier_id": str(supplier_id),
            "purchase_date": date.today().strftime("%Y-%m-%d"),
            "invoice_number": self._next_invoice(),
            "invoice_type": "FACTURA",
            "discount": "0", "tax": "0", "notes": "",
            "item_product_id[]": [str(pid) for pid in product_ids],
            "item_quantity[]": ["10", "5"],
            "item_unit_cost[]": ["50", "75"],
        }, follow_redirects=True)

        with app.app_context():
            purchase = Purchase.query.filter_by(status="BORRADOR").order_by(Purchase.id.desc()).first()
            purchase_id = purchase.id

        client.post(f"/purchases/{purchase_id}/status", data={"status": "RECIBIDA"}, follow_redirects=True)

        with app.app_context():
            movements = InventoryMovement.query.filter_by(
                reference_type="COMPRA", reference_id=purchase_id
            ).all()
            assert len(movements) == 2
            assert all(m.movement_type == "ENTRADA" for m in movements)


class TestSaleFlow:
    def _get_test_product_id(self, app):
        with app.app_context():
            p = Product.query.filter_by(code="TEST-001").first()
            return p.id if p else None

    def _get_customer_id(self, app):
        with app.app_context():
            c = Customer.query.filter_by(is_active=True).first()
            return c.id if c else None

    def test_create_and_confirm_sale(self, client, app):
        product_id = self._get_test_product_id(app)
        customer_id = self._get_customer_id(app)
        assert product_id is not None
        assert customer_id is not None

        login(client)
        resp = client.post("/sales/create", data={
            "customer_id": str(customer_id),
            "sale_date": date.today().strftime("%Y-%m-%d"),
            "payment_method": "EFECTIVO", "notes": "",
            "item_product_id[]": [str(product_id)],
            "item_quantity[]": ["3"],
            "item_unit_price[]": ["100"],
        }, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            sale = Sale.query.filter_by(status="BORRADOR").order_by(Sale.id.desc()).first()
            assert sale is not None
            sale_id = sale.id

        resp = client.post(f"/sales/{sale_id}/confirm", follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            sale = Sale.query.get(sale_id)
            assert sale.status == "CONFIRMADA"

    def test_confirm_decreases_inventory(self, client, app):
        product_id = self._get_test_product_id(app)
        customer_id = self._get_customer_id(app)

        login(client)

        with app.app_context():
            before_exit = sum(
                1 for m in InventoryMovement.query.filter_by(
                    product_id=product_id, movement_type="SALIDA"
                ).all()
            )

        client.post("/sales/create", data={
            "customer_id": str(customer_id),
            "sale_date": date.today().strftime("%Y-%m-%d"),
            "payment_method": "EFECTIVO",
            "item_product_id[]": [str(product_id)],
            "item_quantity[]": ["3"],
            "item_unit_price[]": ["100"],
        }, follow_redirects=True)

        with app.app_context():
            sale = Sale.query.filter_by(status="BORRADOR").order_by(Sale.id.desc()).first()
            sale_id = sale.id

        client.post(f"/sales/{sale_id}/confirm", follow_redirects=True)

        with app.app_context():
            after_exit = sum(
                1 for m in InventoryMovement.query.filter_by(
                    product_id=product_id, movement_type="SALIDA"
                ).all()
            )
            assert after_exit > before_exit

    def test_insufficient_stock_blocked(self, client, app):
        product_id = self._get_test_product_id(app)
        customer_id = self._get_customer_id(app)

        login(client)
        client.post("/sales/create", data={
            "customer_id": str(customer_id),
            "sale_date": date.today().strftime("%Y-%m-%d"),
            "payment_method": "EFECTIVO",
            "item_product_id[]": [str(product_id)],
            "item_quantity[]": ["1000"],
            "item_unit_price[]": ["100"],
        }, follow_redirects=True)

        with app.app_context():
            sale = Sale.query.filter_by(status="BORRADOR").order_by(Sale.id.desc()).first()
            sale_id = sale.id

        resp = client.post(f"/sales/{sale_id}/confirm", follow_redirects=True)
        assert b"insuficiente" in resp.data or b"Stock" in resp.data

        with app.app_context():
            sale = Sale.query.get(sale_id)
            assert sale.status == "BORRADOR"

    def test_fefo_selects_earliest_expiration(self, client, app):
        from datetime import timedelta as td
        product_id = self._get_test_product_id(app)
        customer_id = self._get_customer_id(app)

        with app.app_context():
            b1 = ProductBatch(
                product_id=product_id, batch_number="FEFO-A",
                expiration_date=date.today() + td(days=180),
                quantity=20, purchase_price=50.0, is_active=True,
            )
            b2 = ProductBatch(
                product_id=product_id, batch_number="FEFO-B",
                expiration_date=date.today() + td(days=90),
                quantity=10, purchase_price=55.0, is_active=True,
            )
            _db.session.add_all([b1, b2])
            _db.session.flush()
            _db.session.add(InventoryMovement(
                product_id=product_id, batch_id=b1.id,
                movement_type="ENTRADA", quantity=20,
                reference_type="TEST", description="Test",
                user_id=1,
            ))
            _db.session.add(InventoryMovement(
                product_id=product_id, batch_id=b2.id,
                movement_type="ENTRADA", quantity=10,
                reference_type="TEST", description="Test",
                user_id=1,
            ))
            _db.session.commit()
            b1_id = b1.id
            b2_id = b2.id

        login(client)
        client.post("/sales/create", data={
            "customer_id": str(customer_id),
            "sale_date": date.today().strftime("%Y-%m-%d"),
            "payment_method": "EFECTIVO",
            "item_product_id[]": [str(product_id)],
            "item_quantity[]": ["3"],
            "item_unit_price[]": ["100"],
        }, follow_redirects=True)

        with app.app_context():
            sale = Sale.query.filter_by(status="BORRADOR").order_by(Sale.id.desc()).first()
            sale_id = sale.id

        client.post(f"/sales/{sale_id}/confirm", follow_redirects=True)

        with app.app_context():
            sale = Sale.query.get(sale_id)
            item = sale.items[0]
            assert item.batch_id is not None
            assert item.batch_id == b2_id

    def test_cancel_restores_inventory(self, client, app):
        product_id = self._get_test_product_id(app)
        customer_id = self._get_customer_id(app)

        login(client)
        client.post("/sales/create", data={
            "customer_id": str(customer_id),
            "sale_date": date.today().strftime("%Y-%m-%d"),
            "payment_method": "EFECTIVO",
            "item_product_id[]": [str(product_id)],
            "item_quantity[]": ["3"],
            "item_unit_price[]": ["100"],
        }, follow_redirects=True)

        with app.app_context():
            sale = Sale.query.filter_by(status="BORRADOR").order_by(Sale.id.desc()).first()
            sale_id = sale.id

        client.post(f"/sales/{sale_id}/confirm", follow_redirects=True)

        with app.app_context():
            before_movements = InventoryMovement.query.filter_by(product_id=product_id).count()

        client.post(f"/sales/{sale_id}/cancel", follow_redirects=True)

        with app.app_context():
            sale = Sale.query.get(sale_id)
            assert sale.status == "CANCELADA"
            after_movements = InventoryMovement.query.filter_by(product_id=product_id).count()
            assert after_movements > before_movements
            devoluciones = InventoryMovement.query.filter_by(
                product_id=product_id, reference_type="SALE_CANCEL"
            ).count()
            assert devoluciones > 0


class TestEmployeeAndSalary:
    def test_create_employee(self, client, app):
        login(client)
        with app.app_context():
            dept = _db.session.execute(_db.text("SELECT id FROM departments LIMIT 1")).fetchone()
            pos = _db.session.execute(_db.text("SELECT id FROM positions LIMIT 1")).fetchone()
            dept_id = dept[0] if dept else 1
            pos_id = pos[0] if pos else 1

        resp = client.post("/hr/create", data={
            "employee_code": "EMP-TEST-001", "first_name": "Pedro",
            "last_name": "Garcia", "identity_number": "001-150788-1003X",
            "birth_date": "1988-07-15", "phone": "8888-1003",
            "email": "pedro@test.com", "address": "Managua",
            "department_id": str(dept_id), "position_id": str(pos_id),
            "hire_date": "2024-01-15", "contract_type": "INDEFINIDO",
            "base_salary": "12000", "status": "ACTIVO",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_salary_change_creates_history(self, client, app):
        with app.app_context():
            emp = Employee.query.filter_by(employee_code="EMP-002").first()
            emp_id = emp.id
            dept_id = emp.department_id
            pos_id = emp.position_id
            old_salary = emp.base_salary

        new_salary = old_salary + 5000

        login(client)
        resp = client.post(f"/hr/{emp_id}/edit", data={
            "employee_code": "EMP-002", "first_name": "Maria",
            "last_name": "Lopez", "identity_number": "001-220390-1002X",
            "birth_date": "1990-03-22", "phone": "8888-1002",
            "email": "maria@nicaorder.com", "address": "Managua",
            "department_id": str(dept_id), "position_id": str(pos_id),
            "hire_date": "2021-06-15", "contract_type": "INDEFINIDO",
            "base_salary": str(new_salary), "status": "ACTIVO",
            "salary_reason": "Aumento salarial",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"actualizado" in resp.data

        with app.app_context():
            emp = Employee.query.get(emp_id)
            assert emp.base_salary == new_salary
            history = SalaryHistory.query.filter_by(employee_id=emp_id).order_by(
                SalaryHistory.start_date.desc()
            ).all()
            assert len(history) >= 2
            assert history[0].salary == new_salary


class TestPayrollCalculations:
    def _create_period(self, client):
        resp = client.post("/payroll/period/create", data={
            "month": "1", "year": "2026",
        }, follow_redirects=True)
        return resp

    def test_create_payroll_period(self, client, app):
        login(client)
        self._create_period(client)
        with app.app_context():
            period = PayrollPeriod.query.filter_by(month=1, year=2026).first()
            assert period is not None
            assert period.status == "ABIERTO"

    def test_calculate_gross_salary(self, app):
        with app.app_context():
            from app.services.payroll_services import calculate_gross_salary
            assert calculate_gross_salary(15000) == 15000.0
            assert calculate_gross_salary(15000, 2000, 1000, 500) == 18500.0
            assert calculate_gross_salary(15000, 0, 0, 0) == 15000.0

    def test_calculate_inss(self, app):
        with app.app_context():
            from app.services.payroll_services import calculate_employee_inss
            inss = calculate_employee_inss(15000)
            assert inss == 15000 * 0.07
            assert inss == 1050.0

    def test_calculate_income_tax_low_salary(self, app):
        with app.app_context():
            from app.services.payroll_services import (
                calculate_annual_taxable_income, get_tax_bracket,
                calculate_annual_income_tax, calculate_monthly_income_tax,
                calculate_employee_inss,
            )
            gross = 8000
            inss = calculate_employee_inss(gross)
            annual = calculate_annual_taxable_income(gross, inss)
            expected_annual = (gross - inss) * 12
            assert annual == expected_annual
            assert annual <= 100000

            bracket = get_tax_bracket(annual, 2026)
            assert bracket is not None
            assert bracket.excess_percentage == 0

            annual_tax = calculate_annual_income_tax(annual, bracket)
            assert annual_tax == 0.0

            monthly_tax = calculate_monthly_income_tax(annual_tax)
            assert monthly_tax == 0.0

    def test_calculate_income_tax_high_salary(self, app):
        with app.app_context():
            from app.services.payroll_services import (
                calculate_annual_taxable_income, get_tax_bracket,
                calculate_annual_income_tax, calculate_monthly_income_tax,
                calculate_employee_inss,
            )
            gross = 25000
            inss = calculate_employee_inss(gross)
            annual = calculate_annual_taxable_income(gross, inss)
            expected_annual = (gross - inss) * 12
            assert annual == expected_annual
            assert 200000 < annual <= 350000

            bracket = get_tax_bracket(annual, 2026)
            assert bracket is not None
            assert bracket.excess_percentage == 20

            annual_tax = calculate_annual_income_tax(annual, bracket)
            assert annual_tax > 0

            monthly_tax = calculate_monthly_income_tax(annual_tax)
            assert monthly_tax == round(annual_tax / 12, 2)

    def test_calculate_net_salary(self, app):
        with app.app_context():
            from app.services.payroll_services import calculate_net_salary
            net = calculate_net_salary(15000, 1050, 0, 0)
            assert net == 15000 - 1050

            net2 = calculate_net_salary(15000, 1050, 500, 200)
            assert net2 == 15000 - 1050 - 500 - 200

    def test_full_payroll_calculation(self, client, app):
        login(client)
        self._create_period(client)

        with app.app_context():
            period = PayrollPeriod.query.filter_by(month=1, year=2026).first()
            period_id = period.id

        resp = client.post("/payroll/calculate", data={
            "period_id": str(period_id),
        }, follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            payroll = Payroll.query.filter_by(payroll_period_id=period_id).first()
            assert payroll is not None
            assert payroll.status == "CALCULADA"
            assert len(payroll.items) > 0
            item = payroll.items[0]
            assert item.gross_salary == item.base_salary
            assert item.employee_inss > 0
            assert item.net_salary < item.gross_salary


class TestRouteProtection:
    def test_unauthenticated_redirects_to_login(self, client):
        resp = client.get("/products/")
        assert resp.status_code == 302
        assert "login" in resp.headers["Location"]

    def test_hr_requires_hr_permission(self, client):
        login(client, username="vendedor", password="test1234")
        resp = client.get("/hr/")
        assert resp.status_code == 302
        assert "unauthorized" in resp.headers["Location"]

    def test_payroll_requires_permission(self, client):
        login(client, username="vendedor", password="test1234")
        resp = client.get("/payroll/")
        assert resp.status_code == 302
        assert "unauthorized" in resp.headers["Location"]

    def test_reports_requires_permission(self, client):
        login(client, username="vendedor", password="test1234")
        resp = client.get("/reports/")
        assert resp.status_code == 302
        assert "unauthorized" in resp.headers["Location"]

    def test_admin_can_access_hr(self, client):
        login(client, username="admin")
        resp = client.get("/hr/")
        assert resp.status_code == 200

    def test_rrhh_user_can_access_hr(self, client):
        login(client, username="rrhh")
        resp = client.get("/hr/")
        assert resp.status_code == 200

    def test_rrhh_user_can_access_payroll(self, client):
        login(client, username="rrhh")
        resp = client.get("/payroll/")
        assert resp.status_code == 200

    def test_vendedor_can_access_sales(self, client):
        login(client, username="vendedor")
        resp = client.get("/sales/")
        assert resp.status_code == 200


class TestAdminRoutes:
    def test_admin_users_list(self, client):
        login(client)
        resp = client.get("/admin/users/")
        assert resp.status_code == 200
        assert b"Usuarios" in resp.data

    def test_admin_roles_list(self, client):
        login(client)
        resp = client.get("/admin/roles/")
        assert resp.status_code == 200
        assert b"Roles" in resp.data

    def test_admin_create_user(self, client):
        login(client)
        resp = client.post("/admin/users/create", data={
            "username": "nuevouser",
            "full_name": "Usuario Nuevo",
            "email": "nuevo@test.com",
            "role_id": "1",
            "password": "test1234",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"nuevouser" in resp.data

    def test_admin_duplicate_username_rejected(self, client):
        login(client)
        resp = client.post("/admin/users/create", data={
            "username": "admin",
            "full_name": "Duplicado",
            "email": "dup@test.com",
            "role_id": "1",
            "password": "test1234",
        }, follow_redirects=True)
        assert b"ya esta registrado" in resp.data

    def test_admin_short_password_rejected(self, client):
        login(client)
        resp = client.post("/admin/users/create", data={
            "username": "shortpw",
            "full_name": "Short PW",
            "email": "shortpw@test.com",
            "role_id": "1",
            "password": "123",
        }, follow_redirects=True)
        assert b"8 caracteres" in resp.data

    def test_admin_toggle_user(self, client, app):
        login(client)
        with app.app_context():
            from app.models import User
            u = User.query.filter_by(username="nuevouser").first()
            uid = u.id
            was_active = u.is_active

        resp = client.post(f"/admin/users/{uid}/toggle", follow_redirects=True)
        assert resp.status_code == 200

        with app.app_context():
            u = User.query.get(uid)
            assert u.is_active != was_active

    def test_admin_cannot_deactivate_self(self, client, app):
        login(client)
        with app.app_context():
            from app.models import User
            admin = User.query.filter_by(username="admin").first()
            admin_id = admin.id

        resp = client.post(f"/admin/users/{admin_id}/toggle", follow_redirects=True)
        assert b"propio usuario" in resp.data

    def test_admin_create_role(self, client):
        login(client)
        resp = client.post("/admin/roles/create", data={
            "name": "Tester",
            "description": "Rol de prueba",
            "permissions": ["1", "2"],
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Tester" in resp.data

    def test_admin_duplicate_role_rejected(self, client):
        login(client)
        resp = client.post("/admin/roles/create", data={
            "name": "Administrador",
            "description": "Duplicado",
        }, follow_redirects=True)
        assert b"ya esta registrado" in resp.data

    def test_vendedor_cannot_access_admin(self, client):
        login(client, username="vendedor", password="test1234")
        resp = client.get("/admin/users/")
        assert resp.status_code == 302
        assert "unauthorized" in resp.headers["Location"]

    def test_rrhh_cannot_access_admin_users(self, client):
        login(client, username="rrhh", password="test1234")
        resp = client.get("/admin/users/")
        assert resp.status_code == 302
        assert "unauthorized" in resp.headers["Location"]

    def test_admin_sidebar_link(self, client):
        login(client)
        resp = client.get("/dashboard")
        assert b"/admin/users/" in resp.data


class TestRegistration:
    def test_register_as_bodeguero(self, client):
        resp = client.post("/auth/register", data={
            "full_name": "Nuevo Bodeguero",
            "username": "bodeguero_test",
            "email": "bodeguero@test.com",
            "phone": "8888-9999",
            "password": "test1234",
            "confirm_password": "test1234",
            "requested_role": "Bodeguero",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"pendiente de aprobacion" in resp.data

    def test_register_as_vendedor(self, client):
        resp = client.post("/auth/register", data={
            "full_name": "Nuevo Vendedor",
            "username": "vendedor_test",
            "email": "vendedor_new@test.com",
            "password": "test1234",
            "confirm_password": "test1234",
            "requested_role": "Vendedor",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_register_as_rrhh(self, client):
        resp = client.post("/auth/register", data={
            "full_name": "Nuevo RRHH",
            "username": "rrhh_test",
            "email": "rrhh_new@test.com",
            "password": "test1234",
            "confirm_password": "test1234",
            "requested_role": "RRHH",
        }, follow_redirects=True)
        assert resp.status_code == 200

    def test_cannot_register_as_admin(self, client):
        resp = client.post("/auth/register", data={
            "full_name": "Fake Admin",
            "username": "fake_admin",
            "email": "fake@admin.com",
            "password": "test1234",
            "confirm_password": "test1234",
            "requested_role": "Administrador",
        }, follow_redirects=True)
        assert b"no es posible registrarse como administrador" in resp.data.lower()

    def test_register_duplicate_username(self, client):
        resp = client.post("/auth/register", data={
            "full_name": "Dup User",
            "username": "admin",
            "email": "dup2@test.com",
            "password": "test1234",
            "confirm_password": "test1234",
            "requested_role": "Vendedor",
        }, follow_redirects=True)
        assert b"ya esta registrado" in resp.data

    def test_register_password_mismatch(self, client):
        resp = client.post("/auth/register", data={
            "full_name": "Mismatch User",
            "username": "mismatch_user",
            "email": "mismatch@test.com",
            "password": "test1234",
            "confirm_password": "different123",
            "requested_role": "Vendedor",
        }, follow_redirects=True)
        assert b"no coinciden" in resp.data

    def test_register_short_password(self, client):
        resp = client.post("/auth/register", data={
            "full_name": "Short PW",
            "username": "shortpw_user",
            "email": "shortpw@test.com",
            "password": "123",
            "confirm_password": "123",
            "requested_role": "Bodeguero",
        }, follow_redirects=True)
        assert b"8 caracteres" in resp.data


class TestAccountStatus:
    def _create_pending_user(self, username, email, role_name):
        role = Role.query.filter_by(name=role_name).first()
        u = User(
            username=username,
            full_name=f"Test {username}",
            email=email,
            role_id=role.id,
            is_active=False,
            account_status="PENDIENTE",
            requested_role_id=role.id,
        )
        u.set_password("test1234")
        _db.session.add(u)
        _db.session.commit()
        return u

    def test_pending_cannot_login(self, client, app):
        u = self._create_pending_user("pend_login_test", "pend@test.com", "Bodeguero")

        resp = client.post("/auth/login", data={
            "username": "pend_login_test",
            "password": "test1234",
        }, follow_redirects=True)
        assert b"pendiente de aprobacion" in resp.data

    def test_admin_can_approve_user(self, client, app):
        u = self._create_pending_user("approve_test", "approve@test.com", "Vendedor")
        uid = u.id
        role_id = u.requested_role_id

        login(client)
        resp = client.post(f"/admin/users/{uid}/approve", data={
            "role_id": str(role_id),
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"aprobada" in resp.data

        u = _db.session.get(User, uid)
        assert u.account_status == "ACTIVA"
        assert u.is_active is True

    def test_admin_can_reject_user(self, client, app):
        u = self._create_pending_user("reject_test", "reject@test.com", "RRHH")
        uid = u.id

        login(client)
        resp = client.post(f"/admin/users/{uid}/reject", data={
            "reason": "No cumple requisitos",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"rechazada" in resp.data

        u = _db.session.get(User, uid)
        assert u.account_status == "RECHAZADA"
        assert u.is_active is False

    def test_rejected_cannot_login(self, client, app):
        u = User.query.filter_by(username="reject_test").first()
        if not u:
            return

        resp = client.post("/auth/login", data={
            "username": "reject_test",
            "password": "test1234",
        }, follow_redirects=True)
        assert b"no fue aprobada" in resp.data

    def test_admin_can_block_user(self, client, app):
        login(client)
        u = User.query.filter_by(username="approve_test").first()
        if not u:
            return
        uid = u.id

        resp = client.post(f"/admin/users/{uid}/block", follow_redirects=True)
        assert resp.status_code == 200
        assert b"bloqueado" in resp.data

        u = _db.session.get(User, uid)
        assert u.account_status == "BLOQUEADA"
        assert u.is_active is False

    def test_blocked_cannot_login(self, client, app):
        u = User.query.filter_by(username="approve_test").first()
        if not u:
            return

        resp = client.post("/auth/login", data={
            "username": "approve_test",
            "password": "test1234",
        }, follow_redirects=True)
        assert b"bloqueada" in resp.data

    def test_pending_users_page(self, client, app):
        login(client)
        resp = client.get("/admin/users/pending/")
        assert resp.status_code == 200


class TestRoleBasedAccess:
    def test_vendedor_cannot_access_inventory_adjust(self, client):
        login(client, username="vendedor", password="test1234")
        resp = client.get("/inventory/adjust")
        assert resp.status_code == 302
        assert "unauthorized" in resp.headers["Location"]

    def test_vendedor_cannot_access_hr(self, client):
        login(client, username="vendedor", password="test1234")
        resp = client.get("/hr/")
        assert resp.status_code == 302
        assert "unauthorized" in resp.headers["Location"]

    def test_vendedor_cannot_access_payroll(self, client):
        login(client, username="vendedor", password="test1234")
        resp = client.get("/payroll/")
        assert resp.status_code == 302
        assert "unauthorized" in resp.headers["Location"]

    def test_vendedor_cannot_access_purchases(self, client):
        login(client, username="vendedor", password="test1234")
        resp = client.get("/purchases/")
        assert resp.status_code == 302
        assert "unauthorized" in resp.headers["Location"]

    def test_vendedor_cannot_access_suppliers(self, client):
        login(client, username="vendedor", password="test1234")
        resp = client.get("/suppliers/")
        assert resp.status_code == 302
        assert "unauthorized" in resp.headers["Location"]

    def test_vendedor_can_view_inventory_stock(self, client):
        login(client, username="vendedor", password="test1234")
        resp = client.get("/inventory/stock")
        assert resp.status_code == 200

    def test_bodeguero_can_access_inventory(self, client, app):
        login(client)
        bodeguero = Role.query.filter_by(name="Bodeguero").first()
        u = User(
            username="bodeguero_access",
            full_name="Bodeguero Access",
            email="bodeguero_access@test.com",
            role_id=bodeguero.id,
            is_active=True,
            account_status="ACTIVA",
        )
        u.set_password("test1234")
        _db.session.add(u)
        _db.session.commit()

        resp = client.post("/auth/login", data={
            "username": "bodeguero_access",
            "password": "test1234",
        }, follow_redirects=True)
        resp = client.get("/inventory/stock")
        assert resp.status_code == 200

    def test_bodeguero_can_access_purchases(self, client):
        login(client, username="bodeguero_access", password="test1234")
        resp = client.get("/purchases/")
        assert resp.status_code == 200

    def test_bodeguero_can_access_products(self, client):
        login(client, username="bodeguero_access", password="test1234")
        resp = client.get("/products/")
        assert resp.status_code == 200

    def test_bodeguero_can_access_suppliers(self, client):
        login(client, username="bodeguero_access", password="test1234")
        resp = client.get("/suppliers/")
        assert resp.status_code == 200

    def test_bodeguero_cannot_access_sales(self, client):
        login(client, username="bodeguero_access", password="test1234")
        resp = client.get("/sales/")
        assert resp.status_code == 302
        assert "unauthorized" in resp.headers["Location"]

    def test_bodeguero_cannot_access_customers(self, client):
        login(client, username="bodeguero_access", password="test1234")
        resp = client.get("/customers/")
        assert resp.status_code == 302
        assert "unauthorized" in resp.headers["Location"]

    def test_bodeguero_cannot_access_hr(self, client):
        login(client, username="bodeguero_access", password="test1234")
        resp = client.get("/hr/")
        assert resp.status_code == 302
        assert "unauthorized" in resp.headers["Location"]

    def test_bodeguero_cannot_access_admin(self, client):
        login(client, username="bodeguero_access", password="test1234")
        resp = client.get("/admin/users/")
        assert resp.status_code == 302
        assert "unauthorized" in resp.headers["Location"]

    def test_rrhh_can_access_hr_and_payroll(self, client):
        login(client, username="rrhh", password="test1234")
        resp = client.get("/hr/")
        assert resp.status_code == 200
        resp = client.get("/payroll/")
        assert resp.status_code == 200

    def test_rrhh_cannot_access_sales(self, client):
        login(client, username="rrhh", password="test1234")
        resp = client.get("/sales/")
        assert resp.status_code == 302
        assert "unauthorized" in resp.headers["Location"]

    def test_rrhh_cannot_access_purchases(self, client):
        login(client, username="rrhh", password="test1234")
        resp = client.get("/purchases/")
        assert resp.status_code == 302
        assert "unauthorized" in resp.headers["Location"]

    def test_rrhh_cannot_access_products(self, client):
        login(client, username="rrhh", password="test1234")
        resp = client.get("/products/")
        assert resp.status_code == 302
        assert "unauthorized" in resp.headers["Location"]

    def test_rrhh_cannot_access_admin_users(self, client):
        login(client, username="rrhh", password="test1234")
        resp = client.get("/admin/users/")
        assert resp.status_code == 302
        assert "unauthorized" in resp.headers["Location"]

    def test_dynamic_menu_bodeguero(self, client):
        login(client, username="bodeguero_access", password="test1234")
        resp = client.get("/inventory/stock")
        assert resp.status_code == 200
        assert b"Inventario" in resp.data
        assert b"Productos" in resp.data
        assert b"Proveedores" in resp.data
        assert b"Compras" in resp.data
        assert b"Administracion" not in resp.data
        assert b"Nomina" not in resp.data
        assert b"Ventas" not in resp.data

    def test_dynamic_menu_vendedor(self, client):
        login(client, username="vendedor", password="test1234")
        resp = client.get("/sales/")
        assert resp.status_code == 200
        assert b"Ventas" in resp.data
        assert b"Clientes" in resp.data
        assert b"Productos" in resp.data
        assert b"Inventario" in resp.data
        assert b"Administracion" not in resp.data
        assert b"Nomina" not in resp.data
        assert b"Compras" not in resp.data

    def test_dynamic_menu_rrhh(self, client):
        login(client, username="rrhh", password="test1234")
        resp = client.get("/hr/")
        assert resp.status_code == 200
        assert b"Recursos Humanos" in resp.data
        assert b"Nomina" in resp.data
        assert b'nav-label">Administracion' not in resp.data
        assert b'nav-label">Ventas' not in resp.data
        assert b'nav-label">Compras' not in resp.data

    def test_unauthorized_json_response(self, client):
        login(client, username="vendedor", password="test1234")
        resp = client.get("/purchases/")
        assert resp.status_code == 302
        assert "unauthorized" in resp.headers["Location"]

    def test_blocked_route_returns_unauthorized(self, client):
        login(client, username="rrhh", password="test1234")
        resp = client.get("/inventory/adjust")
        assert resp.status_code == 302
        assert "unauthorized" in resp.headers["Location"]


class TestAuditTrail:
    def test_approval_creates_audit(self, client, app):
        role = Role.query.filter_by(name="Vendedor").first()
        u = User(
            username="audit_test_user",
            full_name="Audit Test",
            email="audit@test.com",
            role_id=role.id,
            is_active=False,
            account_status="PENDIENTE",
            requested_role_id=role.id,
        )
        u.set_password("test1234")
        _db.session.add(u)
        _db.session.commit()
        uid = u.id

        login(client)
        resp = client.post(f"/admin/users/{uid}/approve", data={
            "role_id": str(role.id),
        }, follow_redirects=True)

        audit = AuditLog.query.filter_by(target_user_id=uid, action="APPROVE").first()
        assert audit is not None
        assert audit.previous_status == "PENDIENTE"
        assert audit.new_status == "ACTIVA"

    def test_rejection_creates_audit(self, client, app):
        role = Role.query.filter_by(name="Bodeguero").first()
        u = User(
            username="reject_audit_user",
            full_name="Reject Audit",
            email="reject_audit@test.com",
            role_id=role.id,
            is_active=False,
            account_status="PENDIENTE",
            requested_role_id=role.id,
        )
        u.set_password("test1234")
        _db.session.add(u)
        _db.session.commit()
        uid = u.id

        login(client)
        resp = client.post(f"/admin/users/{uid}/reject", data={
            "reason": "Motivo de prueba",
        }, follow_redirects=True)

        audit = AuditLog.query.filter_by(target_user_id=uid, action="REJECT").first()
        assert audit is not None
        assert audit.new_status == "RECHAZADA"
        assert audit.reason == "Motivo de prueba"

    def test_audit_log_page(self, client):
        login(client)
        resp = client.get("/admin/audit/")
        assert resp.status_code == 200
        assert b"Auditoria" in resp.data or b"auditoria" in resp.data.lower()
