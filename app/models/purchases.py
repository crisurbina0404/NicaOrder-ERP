from datetime import datetime, timezone
from ..extensions import db


class Supplier(db.Model):
    __tablename__ = "proveedores"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column("nombre", db.String(150), unique=True, nullable=False)
    tax_id = db.Column("numero_fiscal", db.String(50), unique=True, nullable=False)
    phone = db.Column("telefono", db.String(30), nullable=True)
    email = db.Column("correo", db.String(120), nullable=True)
    address = db.Column("direccion", db.String(300), nullable=True)
    contact_person = db.Column("persona_contacto", db.String(150), nullable=True)
    is_active = db.Column("activo", db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        "fecha_creacion", db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    purchases = db.relationship("Purchase", back_populates="supplier", lazy=True)

    def __repr__(self):
        return f"<Supplier {self.name}>"


class Purchase(db.Model):
    __tablename__ = "compras"

    id = db.Column(db.Integer, primary_key=True)
    supplier_id = db.Column("proveedor_id", db.Integer, db.ForeignKey("proveedores.id"), nullable=False)
    user_id = db.Column("usuario_id", db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    purchase_date = db.Column("fecha_compra", db.DateTime, nullable=False)
    invoice_number = db.Column("numero_factura", db.String(50), nullable=False)
    invoice_type = db.Column("tipo_factura", db.String(20), nullable=False, default="FACTURA")
    status = db.Column("estado", db.String(20), nullable=False, default="BORRADOR")
    subtotal = db.Column("subtotal", db.Float, default=0.0, nullable=False)
    discount = db.Column("descuento", db.Float, default=0.0, nullable=False)
    tax = db.Column("impuesto", db.Float, default=0.0, nullable=False)
    total = db.Column("total", db.Float, default=0.0, nullable=False)
    notes = db.Column("notas", db.Text, nullable=True)
    created_at = db.Column(
        "fecha_creacion", db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
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
    __tablename__ = "detalle_compras"

    id = db.Column(db.Integer, primary_key=True)
    purchase_id = db.Column(
        "compra_id", db.Integer, db.ForeignKey("compras.id"), nullable=False
    )
    product_id = db.Column("producto_id", db.Integer, db.ForeignKey("productos.id"), nullable=False)
    quantity = db.Column("cantidad", db.Integer, nullable=False)
    quantity_received = db.Column("cantidad_recibida", db.Integer, nullable=False, default=0)
    unit_cost = db.Column("costo_unitario", db.Float, nullable=False)
    subtotal = db.Column("subtotal", db.Float, nullable=False)
    manufacturing_date = db.Column("fecha_fabricacion", db.Date, nullable=True)
    expiration_date = db.Column("fecha_vencimiento", db.Date, nullable=True)

    purchase = db.relationship("Purchase", back_populates="items")
    product = db.relationship("Product")

    def __repr__(self):
        return f"<PurchaseItem {self.product_id} x{self.quantity}>"
