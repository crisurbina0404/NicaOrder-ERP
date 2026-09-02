from datetime import datetime, timezone
from ..extensions import db


class ProductBatch(db.Model):
    __tablename__ = "product_batches"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    purchase_id = db.Column(db.Integer, db.ForeignKey("purchases.id"), nullable=True)
    batch_number = db.Column(db.String(50), nullable=False)
    expiration_date = db.Column(db.Date, nullable=False)
    manufacturing_date = db.Column(db.Date, nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    purchase_price = db.Column(db.Float, nullable=False)
    quarantine_status = db.Column(db.String(20), nullable=False, default="CUARENTENA")
    quarantine_notes = db.Column(db.String(300), nullable=True)
    released_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    released_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    product = db.relationship("Product", backref="batches")
    purchase = db.relationship("Purchase", backref="batches")
    movements = db.relationship(
        "InventoryMovement", back_populates="batch", lazy=True
    )

    QUARANTINE_STATUSES = ["CUARENTENA", "LIBERADO", "RECHAZADO"]

    @property
    def current_quantity(self):
        incoming = sum(
            m.quantity for m in self.movements if m.movement_type == "ENTRADA"
        )
        outgoing = sum(
            m.quantity for m in self.movements if m.movement_type == "SALIDA"
        )
        return max(incoming - outgoing, 0)

    @property
    def is_expired(self):
        return self.expiration_date < datetime.now().date()

    @property
    def is_expiring_soon(self):
        from datetime import timedelta
        threshold = datetime.now().date() + timedelta(days=90)
        return self.expiration_date <= threshold and not self.is_expired

    @property
    def is_available_for_sale(self):
        return self.quarantine_status == "LIBERADO" and self.is_active

    def __repr__(self):
        return f"<ProductBatch {self.batch_number} - {self.product_id}>"


class InventoryMovement(db.Model):
    __tablename__ = "inventory_movements"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=False)
    batch_id = db.Column(
        db.Integer, db.ForeignKey("product_batches.id"), nullable=True
    )
    movement_type = db.Column(db.String(20), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    reference_type = db.Column(db.String(30), nullable=True)
    reference_id = db.Column(db.Integer, nullable=True)
    description = db.Column(db.String(300), nullable=True)
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    product = db.relationship("Product", backref="inventory_movements")
    batch = db.relationship("ProductBatch", back_populates="movements")
    user = db.relationship("User")

    def __repr__(self):
        return f"<InventoryMovement {self.movement_type} {self.quantity} - {self.product_id}>"
