import sys
import os
import secrets
from datetime import date, timedelta, datetime

os.environ["SECRET_KEY"] = "test-secret-key-for-testing-only"

from app.config import Config
Config.SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from app import create_app
from app.extensions import db as _db
from app.models import (
    User, Role, Permission,
    Product, Category, Brand, Supplier,
    Purchase, PurchaseItem, ProductBatch, InventoryMovement,
)


@pytest.fixture(scope="session")
def app():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.app_context():
        yield app
        _db.session.remove()


@pytest.fixture(autouse=True)
def setup_db(app):
    with app.app_context():
        _db.session.rollback()
        _seed_minimal_data()
        yield
        _db.session.rollback()


def _seed_minimal_data():
    if not Role.query.filter_by(name="Administrador").first():
        admin_role = Role(name="Administrador", description="Admin")
        _db.session.add(admin_role)
        _db.session.flush()

    admin_role = Role.query.filter_by(name="Administrador").first()

    if not User.query.filter_by(username="admin_svc").first():
        admin = User(
            username="admin_svc",
            full_name="Admin Service",
            email="admin_svc@test.com",
            role_id=admin_role.id,
            is_active=True,
        )
        admin.set_password("test1234")
        _db.session.add(admin)

    if not User.query.filter_by(username="bodeguero_svc").first():
        bodeguero_role = Role.query.filter_by(name="Bodeguero").first()
        if not bodeguero_role:
            bodeguero_role = Role(name="Bodeguero", description="Bodeguero")
            _db.session.add(bodeguero_role)
            _db.session.flush()
        bodeguero = User(
            username="bodeguero_svc",
            full_name="Bodeguero Service",
            email="bodeguero_svc@test.com",
            role_id=bodeguero_role.id,
            is_active=True,
        )
        bodeguero.set_password("test1234")
        _db.session.add(bodeguero)

    if not Category.query.filter_by(name="Medicamentos").first():
        cat = Category(name="Medicamentos", description="Farmaceuticos")
        _db.session.add(cat)
        _db.session.flush()
    else:
        cat = Category.query.filter_by(name="Medicamentos").first()

    if not Brand.query.filter_by(name="Genfar").first():
        brand = Brand(name="Genfar", description="Laboratorio Genfar")
        _db.session.add(brand)
        _db.session.flush()
    else:
        brand = Brand.query.filter_by(name="Genfar").first()

    if not Product.query.filter_by(code="MED-001").first():
        p1 = Product(
            code="MED-001", name="Paracetamol 500mg",
            category_id=cat.id, brand_id=brand.id,
            unit="Caja", purchase_price=5.0, sale_price=10.0,
            minimum_stock=10, is_active=True,
        )
        _db.session.add(p1)

    if not Product.query.filter_by(code="MED-002").first():
        p2 = Product(
            code="MED-002", name="Ibuprofeno 400mg",
            category_id=cat.id, brand_id=brand.id,
            unit="Caja", purchase_price=8.0, sale_price=15.0,
            minimum_stock=10, is_active=True,
        )
        _db.session.add(p2)

    if not Supplier.query.filter_by(tax_id="J0310000000001").first():
        supplier = Supplier(
            name="Distribuidora Farmaceutica SA",
            tax_id="J0310000000001",
            is_active=True,
        )
        _db.session.add(supplier)

    _db.session.commit()


def _make_supplier():
    s = Supplier(
        name=f"Proveedor Test {secrets.token_hex(4)}",
        tax_id=f"J0{secrets.token_hex(6)}",
        is_active=True,
    )
    _db.session.add(s)
    _db.session.flush()
    return s


def _make_product():
    cat = Category.query.first()
    brand = Brand.query.first()
    p = Product(
        code=f"PRD-{secrets.token_hex(4)}",
        name=f"Producto Test {secrets.token_hex(4)}",
        category_id=cat.id,
        brand_id=brand.id,
        unit="Caja",
        purchase_price=10.0,
        sale_price=20.0,
        minimum_stock=5,
        is_active=True,
    )
    _db.session.add(p)
    _db.session.flush()
    return p


def _make_purchase(supplier=None, items_data=None, invoice_number=None):
    if not supplier:
        supplier = _make_supplier()
    if not items_data:
        p1 = Product.query.filter_by(code="MED-001").first()
        p2 = Product.query.filter_by(code="MED-002").first()
        items_data = [
            {"product_id": p1.id, "quantity": 100, "unit_cost": 5.0,
             "expiration_date": date.today() + timedelta(days=365)},
            {"product_id": p2.id, "quantity": 50, "unit_cost": 8.0,
             "expiration_date": date.today() + timedelta(days=180)},
        ]

    admin = User.query.filter_by(username="admin_svc").first()

    purchase = Purchase(
        supplier_id=supplier.id,
        user_id=admin.id,
        purchase_date=datetime.now(),
        invoice_number=invoice_number or f"INV-{secrets.token_hex(4)}",
        invoice_type="FACTURA",
        status="BORRADOR",
        discount=0.0,
        tax=0.0,
    )
    _db.session.add(purchase)
    _db.session.flush()

    for item_data in items_data:
        item = PurchaseItem(
            purchase_id=purchase.id,
            product_id=item_data["product_id"],
            quantity=item_data["quantity"],
            quantity_received=0,
            unit_cost=item_data["unit_cost"],
            subtotal=item_data["quantity"] * item_data["unit_cost"],
            expiration_date=item_data.get("expiration_date"),
            manufacturing_date=item_data.get("manufacturing_date"),
        )
        _db.session.add(item)

    _db.session.commit()
    return purchase


class TestPartialReceptionValid:
    def test_partial_reception_reduces_quantity(self, app):
        from app.services.purchase_reception_service import receive_purchase
        with app.app_context():
            purchase = _make_purchase()
            admin = User.query.filter_by(username="admin_svc").first()

            received_items = [
                {"purchase_item_id": purchase.items[0].id, "quantity_received": 60},
                {"purchase_item_id": purchase.items[1].id, "quantity_received": 30},
            ]
            result = receive_purchase(
                purchase_id=purchase.id,
                user_id=admin.id,
                received_items=received_items,
            )

            assert result["purchase"].status == "RECIBIDA"
            assert len(result["batches"]) == 2
            assert result["batches"][0].quarantine_status == "CUARENTENA"
            assert result["batches"][1].quarantine_status == "CUARENTENA"

            for batch in result["batches"]:
                assert batch.purchase_id == purchase.id
                assert batch.is_active is True
                assert batch.expiration_date is not None

            item0 = PurchaseItem.query.get(purchase.items[0].id)
            item1 = PurchaseItem.query.get(purchase.items[1].id)
            assert item0.quantity_received == 60
            assert item1.quantity_received == 30

    def test_partial_reception_creates_movements(self, app):
        from app.services.purchase_reception_service import receive_purchase
        with app.app_context():
            purchase = _make_purchase()
            admin = User.query.filter_by(username="admin_svc").first()

            received_items = [
                {"purchase_item_id": purchase.items[0].id, "quantity_received": 40},
                {"purchase_item_id": purchase.items[1].id, "quantity_received": 20},
            ]
            result = receive_purchase(
                purchase_id=purchase.id,
                user_id=admin.id,
                received_items=received_items,
            )

            movements = InventoryMovement.query.filter_by(
                reference_type="COMPRA", reference_id=purchase.id
            ).all()
            assert len(movements) == 2
            assert all(m.movement_type == "ENTRADA" for m in movements)
            assert movements[0].quantity == 40
            assert movements[1].quantity == 20

    def test_full_reception_when_no_received_items_specified(self, app):
        from app.services.purchase_reception_service import receive_purchase
        with app.app_context():
            purchase = _make_purchase()
            admin = User.query.filter_by(username="admin_svc").first()

            result = receive_purchase(
                purchase_id=purchase.id,
                user_id=admin.id,
                received_items=None,
            )

            items = PurchaseItem.query.filter_by(purchase_id=purchase.id).all()
            for item in items:
                assert item.quantity_received == item.quantity

            movements = InventoryMovement.query.filter_by(
                reference_type="COMPRA", reference_id=purchase.id
            ).all()
            assert movements[0].quantity == 100
            assert movements[1].quantity == 50

    def test_reception_creates_audit_log(self, app):
        from app.services.purchase_reception_service import receive_purchase
        from app.models import AuditLog
        with app.app_context():
            purchase = _make_purchase()
            admin = User.query.filter_by(username="admin_svc").first()

            receive_purchase(
                purchase_id=purchase.id,
                user_id=admin.id,
                received_items=None,
            )

            audit = AuditLog.query.filter_by(
                user_id=admin.id, action="RECEIVE", module="PURCHASES"
            ).order_by(AuditLog.id.desc()).first()
            assert audit is not None
            assert str(purchase.id) in audit.description
            assert "CUARENTENA" in audit.description


class TestQuantityExceededRejected:
    def test_exceeding_quantity_raises_error(self, app):
        from app.services.purchase_reception_service import (
            receive_purchase, QuantityExceededError,
        )
        with app.app_context():
            purchase = _make_purchase()
            admin = User.query.filter_by(username="admin_svc").first()

            received_items = [
                {"purchase_item_id": purchase.items[0].id, "quantity_received": 150},
                {"purchase_item_id": purchase.items[1].id, "quantity_received": 30},
            ]

            with pytest.raises(QuantityExceededError) as exc_info:
                receive_purchase(
                    purchase_id=purchase.id,
                    user_id=admin.id,
                    received_items=received_items,
                )
            assert "excede" in str(exc_info.value).lower()

    def test_excess_does_not_create_batches(self, app):
        from app.services.purchase_reception_service import (
            receive_purchase, QuantityExceededError,
        )
        with app.app_context():
            purchase = _make_purchase()
            admin = User.query.filter_by(username="admin_svc").first()

            received_items = [
                {"purchase_item_id": purchase.items[0].id, "quantity_received": 999},
            ]

            with pytest.raises(QuantityExceededError):
                receive_purchase(
                    purchase_id=purchase.id,
                    user_id=admin.id,
                    received_items=received_items,
                )

            batches = ProductBatch.query.filter_by(purchase_id=purchase.id).all()
            assert len(batches) == 0
            assert purchase.status == "BORRADOR"

    def test_excess_does_not_commit(self, app):
        from app.services.purchase_reception_service import (
            receive_purchase, QuantityExceededError,
        )
        with app.app_context():
            purchase = _make_purchase()
            admin = User.query.filter_by(username="admin_svc").first()

            received_items = [
                {"purchase_item_id": purchase.items[0].id, "quantity_received": 200},
            ]

            with pytest.raises(QuantityExceededError):
                receive_purchase(
                    purchase_id=purchase.id,
                    user_id=admin.id,
                    received_items=received_items,
                )

            assert purchase.status == "BORRADOR"
            movements = InventoryMovement.query.filter_by(
                reference_type="COMPRA", reference_id=purchase.id
            ).all()
            assert len(movements) == 0


class TestDuplicateInvoiceRejected:
    def test_duplicate_invoice_raises_error(self, app):
        from app.services.purchase_reception_service import (
            receive_purchase, DuplicateInvoiceError,
        )
        with app.app_context():
            supplier = _make_supplier()
            admin = User.query.filter_by(username="admin_svc").first()

            p1 = _make_product()
            purchase1 = _make_purchase(
                supplier=supplier,
                items_data=[{"product_id": p1.id, "quantity": 10, "unit_cost": 5.0,
                             "expiration_date": date.today() + timedelta(days=365)}],
                invoice_number="FAC-DUPLICATE-001",
            )
            receive_purchase(
                purchase_id=purchase1.id,
                user_id=admin.id,
                received_items=[
                    {"purchase_item_id": purchase1.items[0].id, "quantity_received": 10},
                ],
            )

            p2 = _make_product()
            purchase2 = _make_purchase(
                supplier=supplier,
                items_data=[{"product_id": p2.id, "quantity": 20, "unit_cost": 8.0,
                             "expiration_date": date.today() + timedelta(days=300)}],
                invoice_number="FAC-DUPLICATE-001",
            )

            received_items = [
                {"purchase_item_id": purchase2.items[0].id, "quantity_received": 20},
            ]
            with pytest.raises(DuplicateInvoiceError) as exc_info:
                receive_purchase(
                    purchase_id=purchase2.id,
                    user_id=admin.id,
                    received_items=received_items,
                )
            assert "FAC-DUPLICATE-001" in str(exc_info.value)

    def test_same_invoice_different_supplier_allowed(self, app):
        from app.services.purchase_reception_service import receive_purchase
        with app.app_context():
            admin = User.query.filter_by(username="admin_svc").first()

            supplier1 = _make_supplier()
            supplier2 = _make_supplier()
            p1 = _make_product()
            p2 = _make_product()

            purchase1 = _make_purchase(
                supplier=supplier1,
                items_data=[{"product_id": p1.id, "quantity": 10, "unit_cost": 5.0,
                             "expiration_date": date.today() + timedelta(days=365)}],
                invoice_number="FAC-SAME-001",
            )
            receive_purchase(
                purchase_id=purchase1.id,
                user_id=admin.id,
                received_items=[
                    {"purchase_item_id": purchase1.items[0].id, "quantity_received": 10},
                ],
            )

            purchase2 = _make_purchase(
                supplier=supplier2,
                items_data=[{"product_id": p2.id, "quantity": 15, "unit_cost": 7.0,
                             "expiration_date": date.today() + timedelta(days=300)}],
                invoice_number="FAC-SAME-001",
            )
            result = receive_purchase(
                purchase_id=purchase2.id,
                user_id=admin.id,
                received_items=[
                    {"purchase_item_id": purchase2.items[0].id, "quantity_received": 15},
                ],
            )
            assert result["purchase"].status == "RECIBIDA"

    def test_cancelled_purchase_does_not_block_same_invoice(self, app):
        from app.services.purchase_reception_service import receive_purchase
        with app.app_context():
            admin = User.query.filter_by(username="admin_svc").first()

            supplier = _make_supplier()
            p1 = _make_product()
            purchase1 = _make_purchase(
                supplier=supplier,
                items_data=[{"product_id": p1.id, "quantity": 10, "unit_cost": 5.0,
                             "expiration_date": date.today() + timedelta(days=365)}],
                invoice_number="FAC-CANCEL-001",
            )
            purchase1.status = "CANCELADA"
            _db.session.commit()

            p2 = _make_product()
            purchase2 = _make_purchase(
                supplier=supplier,
                items_data=[{"product_id": p2.id, "quantity": 20, "unit_cost": 8.0,
                             "expiration_date": date.today() + timedelta(days=300)}],
                invoice_number="FAC-CANCEL-001",
            )
            result = receive_purchase(
                purchase_id=purchase2.id,
                user_id=admin.id,
                received_items=[
                    {"purchase_item_id": purchase2.items[0].id, "quantity_received": 20},
                ],
            )
            assert result["purchase"].status == "RECIBIDA"


class TestBatchCreatedInQuarantine:
    def test_batch_starts_in_quarantine(self, app):
        from app.services.purchase_reception_service import receive_purchase
        with app.app_context():
            purchase = _make_purchase()
            admin = User.query.filter_by(username="admin_svc").first()

            result = receive_purchase(
                purchase_id=purchase.id,
                user_id=admin.id,
                received_items=None,
            )

            for batch in result["batches"]:
                assert batch.quarantine_status == "CUARENTENA"
                assert batch.is_active is True
                assert batch.released_by is None
                assert batch.released_at is None

    def test_batch_not_available_for_sale_in_quarantine(self, app):
        from app.services.purchase_reception_service import receive_purchase
        with app.app_context():
            purchase = _make_purchase()
            admin = User.query.filter_by(username="admin_svc").first()

            result = receive_purchase(
                purchase_id=purchase.id,
                user_id=admin.id,
                received_items=None,
            )

            for batch in result["batches"]:
                assert batch.is_available_for_sale is False

    def test_batch_quantity_zero_before_movement(self, app):
        from app.services.purchase_reception_service import receive_purchase
        with app.app_context():
            purchase = _make_purchase()
            admin = User.query.filter_by(username="admin_svc").first()

            result = receive_purchase(
                purchase_id=purchase.id,
                user_id=admin.id,
                received_items=[
                    {"purchase_item_id": purchase.items[0].id, "quantity_received": 75},
                    {"purchase_item_id": purchase.items[1].id, "quantity_received": 25},
                ],
            )

            for batch in result["batches"]:
                assert batch.quantity == 0

            batch0_movements = InventoryMovement.query.filter_by(
                batch_id=result["batches"][0].id, movement_type="ENTRADA"
            ).first()
            assert batch0_movements.quantity == 75

    def test_expiration_date_from_purchase_item(self, app):
        from app.services.purchase_reception_service import receive_purchase
        with app.app_context():
            admin = User.query.filter_by(username="admin_svc").first()
            supplier = _make_supplier()
            p = _make_product()
            exp_date = date(2027, 6, 15)

            purchase = _make_purchase(
                supplier=supplier,
                items_data=[{"product_id": p.id, "quantity": 50, "unit_cost": 12.0,
                             "expiration_date": exp_date}],
            )

            result = receive_purchase(
                purchase_id=purchase.id,
                user_id=admin.id,
                received_items=[
                    {"purchase_item_id": purchase.items[0].id, "quantity_received": 50},
                ],
            )

            assert result["batches"][0].expiration_date == exp_date

    def test_reception_with_no_expiration_uses_default(self, app):
        from app.services.purchase_reception_service import receive_purchase
        with app.app_context():
            admin = User.query.filter_by(username="admin_svc").first()
            supplier = _make_supplier()
            p = _make_product()

            purchase = _make_purchase(
                supplier=supplier,
                items_data=[{"product_id": p.id, "quantity": 30, "unit_cost": 5.0,
                             "expiration_date": None}],
            )

            result = receive_purchase(
                purchase_id=purchase.id,
                user_id=admin.id,
                received_items=[
                    {"purchase_item_id": purchase.items[0].id, "quantity_received": 30},
                ],
            )

            expected_default = date.today() + timedelta(days=365)
            assert result["batches"][0].expiration_date == expected_default

    def test_invalid_purchase_id_raises_error(self, app):
        from app.services.purchase_reception_service import (
            receive_purchase, InvalidStateError,
        )
        with app.app_context():
            admin = User.query.filter_by(username="admin_svc").first()

            with pytest.raises(InvalidStateError):
                receive_purchase(purchase_id=99999, user_id=admin.id)

    def test_already_received_purchase_raises_error(self, app):
        from app.services.purchase_reception_service import (
            receive_purchase, InvalidStateError,
        )
        with app.app_context():
            purchase = _make_purchase()
            admin = User.query.filter_by(username="admin_svc").first()

            receive_purchase(
                purchase_id=purchase.id,
                user_id=admin.id,
                received_items=[
                    {"purchase_item_id": purchase.items[0].id, "quantity_received": 100},
                    {"purchase_item_id": purchase.items[1].id, "quantity_received": 50},
                ],
            )

            with pytest.raises(InvalidStateError):
                receive_purchase(
                    purchase_id=purchase.id,
                    user_id=admin.id,
                    received_items=[
                        {"purchase_item_id": purchase.items[0].id, "quantity_received": 100},
                    ],
                )

    def test_atomic_rollback_on_error(self, app):
        from app.services.purchase_reception_service import (
            receive_purchase, QuantityExceededError,
        )
        with app.app_context():
            admin = User.query.filter_by(username="admin_svc").first()
            supplier = _make_supplier()
            p1 = _make_product()
            p2 = _make_product()

            purchase = _make_purchase(
                supplier=supplier,
                items_data=[
                    {"product_id": p1.id, "quantity": 50, "unit_cost": 5.0,
                     "expiration_date": date.today() + timedelta(days=365)},
                    {"product_id": p2.id, "quantity": 30, "unit_cost": 8.0,
                     "expiration_date": date.today() + timedelta(days=200)},
                ],
            )

            with pytest.raises(QuantityExceededError):
                receive_purchase(
                    purchase_id=purchase.id,
                    user_id=admin.id,
                    received_items=[
                        {"purchase_item_id": purchase.items[0].id, "quantity_received": 50},
                        {"purchase_item_id": purchase.items[1].id, "quantity_received": 100},
                    ],
                )

            assert purchase.status == "BORRADOR"
            batches = ProductBatch.query.filter_by(purchase_id=purchase.id).all()
            assert len(batches) == 0
            movements = InventoryMovement.query.filter_by(
                reference_type="COMPRA", reference_id=purchase.id
            ).all()
            assert len(movements) == 0

    def test_release_batch(self, app):
        from app.services.purchase_reception_service import (
            receive_purchase, release_batch,
        )
        with app.app_context():
            purchase = _make_purchase()
            admin = User.query.filter_by(username="admin_svc").first()

            result = receive_purchase(
                purchase_id=purchase.id,
                user_id=admin.id,
                received_items=[
                    {"purchase_item_id": purchase.items[0].id, "quantity_received": 100},
                    {"purchase_item_id": purchase.items[1].id, "quantity_received": 50},
                ],
            )

            batch = result["batches"][0]
            released = release_batch(
                batch_id=batch.id,
                user_id=admin.id,
                notes="Cumple especificaciones",
            )

            assert released.quarantine_status == "LIBERADO"
            assert released.is_available_for_sale is True
            assert released.released_by == admin.id
            assert released.released_at is not None
            assert released.quarantine_notes == "Cumple especificaciones"

    def test_reject_batch(self, app):
        from app.services.purchase_reception_service import (
            receive_purchase, reject_batch,
        )
        with app.app_context():
            purchase = _make_purchase()
            admin = User.query.filter_by(username="admin_svc").first()

            result = receive_purchase(
                purchase_id=purchase.id,
                user_id=admin.id,
                received_items=[
                    {"purchase_item_id": purchase.items[0].id, "quantity_received": 100},
                    {"purchase_item_id": purchase.items[1].id, "quantity_received": 50},
                ],
            )

            batch = result["batches"][0]
            rejected = reject_batch(
                batch_id=batch.id,
                user_id=admin.id,
                notes="Empaque danado",
            )

            assert rejected.quarantine_status == "RECHAZADO"
            assert rejected.is_available_for_sale is False
            assert rejected.is_active is False
            assert rejected.released_by == admin.id
