from datetime import datetime, timezone
from ..extensions import db


class Customer(db.Model):
    __tablename__ = "clientes"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column("nombre", db.String(150), nullable=False)
    identity_number = db.Column("cedula", db.String(50), unique=True, nullable=False)
    phone = db.Column("telefono", db.String(30), nullable=True)
    email = db.Column("correo", db.String(120), nullable=True)
    address = db.Column("direccion", db.String(300), nullable=True)
    is_active = db.Column("activo", db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        "fecha_creacion", db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    sales = db.relationship("Sale", back_populates="customer", lazy=True)

    def __repr__(self):
        return f"<Customer {self.name}>"


class Sale(db.Model):
    __tablename__ = "ventas"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column("cliente_id", db.Integer, db.ForeignKey("clientes.id"), nullable=False)
    user_id = db.Column("usuario_id", db.Integer, db.ForeignKey("usuarios.id"), nullable=False)
    sale_date = db.Column("fecha_venta", db.DateTime, nullable=False)
    status = db.Column("estado", db.String(20), nullable=False, default="BORRADOR")
    payment_method = db.Column("metodo_pago", db.String(20), nullable=False, default="EFECTIVO")
    subtotal = db.Column("subtotal", db.Float, default=0.0, nullable=False)
    discount = db.Column("descuento", db.Float, default=0.0, nullable=False)
    tax = db.Column("impuesto", db.Float, default=0.0, nullable=False)
    total = db.Column("total", db.Float, default=0.0, nullable=False)
    notes = db.Column("notas", db.Text, nullable=True)
    created_at = db.Column(
        "fecha_creacion", db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
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
    __tablename__ = "detalle_ventas"

    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column("venta_id", db.Integer, db.ForeignKey("ventas.id"), nullable=False)
    product_id = db.Column("producto_id", db.Integer, db.ForeignKey("productos.id"), nullable=False)
    batch_id = db.Column(
        "lote_id", db.Integer, db.ForeignKey("lotes_producto.id"), nullable=True
    )
    quantity = db.Column("cantidad", db.Integer, nullable=False)
    quantity_returned = db.Column("cantidad_devuelta", db.Integer, nullable=False, default=0)
    unit_price = db.Column("precio_unitario", db.Float, nullable=False)
    subtotal = db.Column("subtotal", db.Float, nullable=False)

    sale = db.relationship("Sale", back_populates="items")
    product = db.relationship("Product")
    batch = db.relationship("ProductBatch")

    def __repr__(self):
        return f"<SaleItem {self.product_id} x{self.quantity}>"
