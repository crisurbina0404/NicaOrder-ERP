from datetime import datetime, timezone
from ..extensions import db


class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    identity_number = db.Column(db.String(50), unique=True, nullable=False)
    phone = db.Column(db.String(30), nullable=True)
    email = db.Column(db.String(120), nullable=True)
    address = db.Column(db.String(300), nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    sales = db.relationship("Sale", back_populates="customer", lazy=True)

    def __repr__(self):
        return f"<Customer {self.name}>"


class Sale(db.Model):
    __tablename__ = "sales"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    sale_date = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="BORRADOR")
    payment_method = db.Column(db.String(20), nullable=False, default="EFECTIVO")
    subtotal = db.Column(db.Float, default=0.0, nullable=False)
    discount = db.Column(db.Float, default=0.0, nullable=False)
    tax = db.Column(db.Float, default=0.0, nullable=False)
    total = db.Column(db.Float, default=0.0, nullable=False)
    notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    customer = db.relationship("Customer", back_populates="sales")
    user = db.relationship("User", backref="sales")
    items = db.relationship(
        "SaleItem", back_populates="sale", lazy=True, cascade="all, delete-orphan"
    )

    def recalculate_totals(self):
        self.subtotal = sum(item.subtotal for item in self.items)
        self.total = self.subtotal - self.discount + self.tax

    def __repr__(self):
        return f"<Sale {self.id} - {self.status}>"


class SaleItem(db.Model):
    __tablename__ = "sale_items"

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey("sales.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    batch_id = db.Column(
        db.Integer, db.ForeignKey("product_batches.id"), nullable=True
    )
    quantity = db.Column(db.Integer, nullable=False)
    quantity_returned = db.Column(db.Integer, nullable=False, default=0)
    unit_price = db.Column(db.Float, nullable=False)
    subtotal = db.Column(db.Float, nullable=False)

    sale = db.relationship("Sale", back_populates="items")
    product = db.relationship("Product")
    batch = db.relationship("ProductBatch")

    def __repr__(self):
        return f"<SaleItem {self.product_id} x{self.quantity}>"
