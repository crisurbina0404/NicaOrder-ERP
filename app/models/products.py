from datetime import datetime, timezone
from ..extensions import db


class Category(db.Model):
    __tablename__ = "categorias"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column("nombre", db.String(100), unique=True, nullable=False)
    description = db.Column("descripcion", db.String(200), nullable=True)
    is_active = db.Column("activo", db.Boolean, default=True, nullable=False)

    products = db.relationship("Product", back_populates="category", lazy=True)

    def __repr__(self):
        return f"<Category {self.name}>"


class Brand(db.Model):
    __tablename__ = "marcas"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column("nombre", db.String(100), unique=True, nullable=False)
    description = db.Column("descripcion", db.String(200), nullable=True)
    is_active = db.Column("activo", db.Boolean, default=True, nullable=False)

    products = db.relationship("Product", back_populates="brand", lazy=True)

    def __repr__(self):
        return f"<Brand {self.name}>"


class Product(db.Model):
    __tablename__ = "productos"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column("codigo", db.String(50), unique=True, nullable=False)
    name = db.Column("nombre", db.String(150), nullable=False)
    description = db.Column("descripcion", db.String(300), nullable=True)
    category_id = db.Column("categoria_id", db.Integer, db.ForeignKey("categorias.id"), nullable=False)
    brand_id = db.Column("marca_id", db.Integer, db.ForeignKey("marcas.id"), nullable=False)
    presentation = db.Column("presentacion", db.String(100), nullable=True)
    unit = db.Column("unidad", db.String(30), nullable=False)
    purchase_price = db.Column("precio_compra", db.Float, nullable=False)
    sale_price = db.Column("precio_venta", db.Float, nullable=False)
    minimum_stock = db.Column("stock_minimo", db.Integer, default=0, nullable=False)
    sanitary_registration = db.Column("registro_sanitario", db.String(100), nullable=True)
    is_active = db.Column("activo", db.Boolean, default=True, nullable=False)
    created_at = db.Column(
        "fecha_creacion", db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False
    )

    category = db.relationship("Category", back_populates="products")
    brand = db.relationship("Brand", back_populates="products")

    def __repr__(self):
        return f"<Product {self.code} - {self.name}>"
