from datetime import datetime, timezone
from ..extensions import db


class ProductBatch(db.Model):
    __tablename__ = "lotes_producto"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column("producto_id", db.Integer, db.ForeignKey("productos.id"), nullable=False)
    purchase_id = db.Column("compra_id", db.Integer, db.ForeignKey("compras.id"), nullable=True)
    batch_number = db.Column("numero_lote", db.String(50), nullable=False)
    expiration_date = db.Column("fecha_vencimiento", db.Date, nullable=False)
    manufacturing_date = db.Column("fecha_fabricacion", db.Date, nullable=True)
    quantity = db.Column("cantidad", db.Integer, nullable=False, default=0)
    purchase_price = db.Column("precio_compra", db.Float, nullable=False)
    quarantine_status = db.Column("estado_cuarentena", db.String(20), nullable=False, default="CUARENTENA")
    quarantine_notes = db.Column("notas_cuarentena", db.String(300), nullable=True)
    released_by = db.Column("liberado_por", db.Integer, db.ForeignKey("usuarios.id"), nullable=True)
    released_at = db.Column("fecha_liberacion", db.DateTime, nullable=True)
    is_active = db.Column("activo", db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        "fecha_creacion", db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
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
    __tablename__ = "movimientos_inventario"

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column("producto_id", db.Integer, db.ForeignKey("productos.id"), nullable=False)
    batch_id = db.Column(
        "lote_id", db.Integer, db.ForeignKey("lotes_producto.id"), nullable=True
    )
    movement_type = db.Column("tipo_movimiento", db.String(20), nullable=False)
    quantity = db.Column("cantidad", db.Integer, nullable=False)
    reference_type = db.Column("tipo_referencia", db.String(30), nullable=True)
    reference_id = db.Column("referencia_id", db.Integer, nullable=True)
    description = db.Column("descripcion", db.String(300), nullable=True)
    created_at = db.Column(
        "fecha_creacion", db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )
    user_id = db.Column("usuario_id", db.Integer, db.ForeignKey("usuarios.id"), nullable=False)

    product = db.relationship("Product", backref="inventory_movements")
    batch = db.relationship("ProductBatch", back_populates="movements")
    user = db.relationship("User")

    def __repr__(self):
        return f"<InventoryMovement {self.movement_type} {self.quantity} - {self.product_id}>"
