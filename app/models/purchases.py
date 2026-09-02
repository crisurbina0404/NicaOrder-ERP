from datetime import datetime, timezone
from ..extensions import db


class Supplier(db.Model):
    __tablename__ = "suppliers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    tax_id = db.Column(db.String(50), unique=True, nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.String(300), nullable=True)
    contact_person = db.Column(db.String(150), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    purchases = db.relationship("Purchase", back_populates="supplier", lazy=True)

    def __repr__(self):
        return f"<Supplier {self.name}>"


class Purchase(db.Model):
    __tablename__ = "purchases"

    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    purchase_date = db.Column(db.DateTime, nullable=False)
    invoice_number = db.Column(db.String(50), nullable=False)
    invoice_type = db.Column(db.String(20), nullable=False, default="FACTURA")
    status = db.Column(db.String(20), nullable=False, default="BORRADOR")
    subtotal = db.Column(db.Float, default=0.0, nullable=False)
    discount = db.Column(db.Float, default=0.0, nullable=False)
    tax = db.Column(db.Float, default=0.0, nullable=False)
    total = db.Column(db.Float, default=0.0, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    supplier = db.relationship("Supplier", back_populates="purchases")
    user = db.relationship("User", backref="purchases")
    items = db.relationship(
        "PurchaseItem", back_populates="purchase", lazy=True, cascade="all, delete-orphan"
    )

    def recalculate_totals(self):
        self.subtotal = sum(item.subtotal for item in self.items)
        self.total = self.subtotal - self.discount + self.tax

    def __repr__(self):
        return f"<Purchase {self.id} - {self.status}>"


class PurchaseItem(db.Model):
    __tablename__ = "purchase_items"

    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(
        db.Integer, db.ForeignKey("purchases.id"), nullable=False
    )
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    quantity_received = db.Column(db.Integer, nullable=False, default=0)
    unit_cost = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)
    manufacturing_date = db.Column(db.Date, nullable=True)
    expiration_date = db.Column(db.Date, nullable=True)

    purchase = db.relationship("Purchase", back_populates="items")
    product = db.relationship("Product")

    def __repr__(self):
        return f"<PurchaseItem {self.product_id} x{self.quantity}>"
