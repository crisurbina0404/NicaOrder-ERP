"""
Importacion de catalogo internacional de insumos medicos a NicaOrder.

Fuente: openFDA - device/udi (base UDI/GUDID de la FDA, 5+ millones de
registros con GTIN/codigo de barras GS1, marca y fabricante reales).
  GET https://api.fda.gov/device/udi.json?search=...&limit=1000

Precios: openFDA NO publica precios. Se usan precios de referencia
internacionales (rango UNICEF Supply Catalogue 2025) en USD y se
convierten a cordobas con el tipo de cambio real del dia
(open.er-api.com). El precio de venta aplica margen del 35%.

Uso:
    python -m app.scripts.import_fda_catalog            # importar todo
    python -m app.scripts.import_fda_catalog --dry-run  # sin escribir BD
    python -m app.scripts.import_fda_catalog --max 40   # tope por busqueda
"""

import argparse
import json
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

API_FDA = "https://api.fda.gov/device/udi.json"
API_TC = "https://open.er-api.com/v6/latest/USD"

MARGEN_VENTA = 0.35  # 35% sobre costo
STOCK_INICIAL = 25
DIAS_VENCIMIENTO = 3 * 365

# ---------------------------------------------------------------------------
# Productos a buscar en la FDA UDI database.
# query: busqueda literal en device_description (resultados con marca real)
# cat:   categoria interna de NicaOrder (mapeada a las ya sembradas)
# precio_usd: precio de referencia internacional estimado (UNICEF range),
#             aplicado a la unidad de empaque del registro UDI elegido.
# ---------------------------------------------------------------------------
BUSQUEDAS = [
    {"query": "nitrile examination glove", "cat": "Proteccion Personal", "precio_usd": 5.20},
    {"query": "latex examination glove", "cat": "Proteccion Personal", "precio_usd": 4.30},
    {"query": "surgical glove", "cat": "Proteccion Personal", "precio_usd": 8.50},
    {"query": "surgical mask", "cat": "Proteccion Personal", "precio_usd": 4.00},
    {"query": "filtering facepiece respirator", "cat": "Proteccion Personal", "precio_usd": 6.90},
    {"query": "protective goggles", "cat": "Proteccion Personal", "precio_usd": 7.40},
    {"query": "medical face shield", "cat": "Proteccion Personal", "precio_usd": 3.10},
    {"query": "disposable gown", "cat": "Proteccion Personal", "precio_usd": 6.20},
    {"query": "gauze bandage roll", "cat": "Material de Curacion", "precio_usd": 2.10},
    {"query": "adhesive bandage", "cat": "Material de Curacion", "precio_usd": 3.40},
    {"query": "adhesive tape", "cat": "Material de Curacion", "precio_usd": 2.80},
    {"query": "abdominal pad", "cat": "Material de Curacion", "precio_usd": 3.90},
    {"query": "gauze sponge", "cat": "Material de Curacion", "precio_usd": 2.60},
    {"query": "elastic bandage", "cat": "Material de Curacion", "precio_usd": 4.10},
    {"query": "disposable syringe", "cat": "Material de Curacion", "precio_usd": 0.15},
    {"query": "hypodermic needle", "cat": "Material de Curacion", "precio_usd": 0.09},
    {"query": "blood collection tube", "cat": "Material de Curacion", "precio_usd": 0.22},
    {"query": "iv administration set", "cat": "Material de Curacion", "precio_usd": 2.95},
    {"query": "urine collection bag", "cat": "Material de Curacion", "precio_usd": 2.20},
    {"query": "nasogastric tube", "cat": "Material de Curacion", "precio_usd": 1.85},
    {"query": "digital thermometer", "cat": "Equipos Basicos", "precio_usd": 5.60},
    {"query": "blood pressure monitor", "cat": "Equipos Basicos", "precio_usd": 28.00},
    {"query": "stethoscope", "cat": "Equipos Basicos", "precio_usd": 14.50},
    {"query": "pulse oximeter", "cat": "Equipos Basicos", "precio_usd": 16.00},
    {"query": "glucose meter", "cat": "Equipos Basicos", "precio_usd": 18.90},
    {"query": "weighing scale patient", "cat": "Equipos Basicos", "precio_usd": 55.00},
    {"query": "suction catheter", "cat": "Material de Curacion", "precio_usd": 1.20},
    {"query": "oxygen mask", "cat": "Material de Curacion", "precio_usd": 1.75},
    {"query": "nebulizer mask kit", "cat": "Equipos Basicos", "precio_usd": 9.20},
    {"query": "wound dressing", "cat": "Material de Curacion", "precio_usd": 3.70},
]

# Mapeo a las categorias sembradas en db_init.py
CATEGORIAS_VALIDAS = {
    "Proteccion Personal",
    "Material de Curacion",
    "Desinfeccion",
    "Equipos Basicos",
}


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
def log(msg):
    print(msg, flush=True)


def limpiar_texto(s, max_len):
    """Limpia caracteres de control/encoding y recorta."""
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", str(s))
    s = s.replace("\u00c2", "").replace("\u00ae", "")
    s = " ".join(s.split())
    return s[:max_len]


def traducir_nombre(desc, brand, model):
    """Nombre de producto compacto: descripcion + marca [+ modelo]."""
    partes = [limpiar_texto(desc, 90)]
    if brand:
        partes.append(limpiar_texto(brand, 30))
    if model:
        partes.append(f"Modelo {limpiar_texto(model, 20)}")
    return " - ".join(p for p in partes if p)[:150]


def mostrar_error_fda(status, body):
    try:
        err = json.loads(body).get("error", {})
        return err.get("message", body[:200])
    except Exception:
        return body[:200]


# ---------------------------------------------------------------------------
# Fuentes externas
# ---------------------------------------------------------------------------
def obtener_tipo_cambio():
    """Tipo de cambio USD -> NIO (cordobas) del dia."""
    req = urllib.request.Request(
        API_TC, headers={"User-Agent": "NicaOrder/1.0 (importador de catalogo)"}
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    nio = data["rates"]["NIO"]
    log(f"   Tipo de cambio: 1 USD = {nio:.4f} C$ "
        f"({data.get('time_last_update_utc', 'n/a')})")
    return nio


def buscar_fda(query, max_resultados, reintentos=3):
    """Busca registros UDI con GTIN y marca real. Devuelve lista de dicts."""
    filtros = [
        "identifiers.issuing_agency:GS1",       # exige GTIN (codigo de barras)
        "NOT brand_name:*generic*",             # evita descripciones genericas
        "commercial_distribution_status:%22In+Commercial+Distribution%22",
        "_exists_:brand_name",
    ]
    search = f'device_description:"{query}" AND ' + " AND ".join(filtros)
    url = f"{API_FDA}?search={urllib.parse.quote(search)}&limit={min(max_resultados, 1000)}"

    for intento in range(1, reintentos + 1):
        try:
            req = urllib.request.Request(
                url, headers={"User-Agent": "NicaOrder/1.0 (importador de catalogo)"}
            )
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read().decode())
            return data.get("results", [])
        except urllib.error.HTTPError as e:
            if e.code == 404:  # sin resultados para esa busqueda
                return []
            if e.code == 429 and intento < reintentos:  # rate limit
                time.sleep(5 * intento)
                continue
            log(f"   [WARN] FDA {e.code} en '{query}': "
                f"{mostrar_error_fda(e.code, e.read().decode(errors='ignore'))}")
            return []
        except Exception as e:
            if intento < reintentos:
                time.sleep(3 * intento)
                continue
            log(f"   [WARN] error de red en '{query}': {e}")
            return []
    return []


def extraer_gtin(registro):
    """Primer GTIN GS1 tipo Primary (unidad de uso); si no, cualquier GS1."""
    ids = [i for i in registro.get("identifiers", [])
           if i.get("issuing_agency") == "GS1" and i.get("id")]
    primarios = [i["id"] for i in ids if i.get("type") == "Primary"]
    elegido = (primarios or [i["id"] for i in ids] or [None])[0]
    if not elegido:
        return None, None
    cant = next(
        (i.get("quantity_per_package") for i in ids
         if i.get("type") == "Package" and i.get("quantity_per_package")),
        None,
    )
    return elegido, cant


# ---------------------------------------------------------------------------
# Importacion
# ---------------------------------------------------------------------------
def importar(dry_run=False, max_por_busqueda=8, usuario_id=1):
    sys.path.insert(0, ".")
    from app import create_app
    from app.extensions import db
    from app.models.products import Brand, Category, Product
    from app.models.inventory import InventoryMovement, ProductBatch
    from app.models.security import AuditLog, User

    app = create_app()
    with app.app_context():
        # --- Tipo de cambio -------------------------------------------------
        log("[1/4] Obteniendo tipo de cambio USD -> C$ ...")
        if dry_run:
            tipo_cambio = 36.75  # valor de referencia para el modo prueba
        else:
            tipo_cambio = obtener_tipo_cambio()

        # --- Obtener registros de la FDA ------------------------------------
        log("[2/4] Consultando catalogo UDI de openFDA ...")
        gtins_vistos = set()
        seleccion = []
        for b in BUSQUEDAS:
            if b["cat"] not in CATEGORIAS_VALIDAS:
                log(f"   [WARN] categoria desconocida para '{b['query']}': {b['cat']}")
                continue
            resultados = buscar_fda(b["query"], max_por_busqueda)
            log(f"   {b['query']}: {len(resultados)} registro(s)")
            for r in resultados:
                gtin, cantidad_pkg = extraer_gtin(r)
                if not gtin or gtin in gtins_vistos:
                    continue
                gtins_vistos.add(gtin)
                seleccion.append({
                    "gtin": gtin,
                    "descripcion": limpiar_texto(r.get("device_description", ""), 300),
                    "marca": limpiar_texto(r.get("brand_name", ""), 100),
                    "fabricante": limpiar_texto(r.get("company_name", ""), 100),
                    "modelo": limpiar_texto(r.get("version_or_model_number")
                                            or r.get("version_model_number", ""), 50),
                    "categoria": b["cat"],
                    "precio_usd": b["precio_usd"],
                    "cantidad_pkg": cantidad_pkg,
                })
            time.sleep(0.6)  # respetar rate limit (240 req/min, margen amplio)

        if not seleccion:
            log("No se obtuvieron registros de la FDA. Nada que importar.")
            return

        # --- Construir entidades NicaOrder -----------------------------------
        log("[3/4] Construyendo productos, lotes y kardex ...")
        cats = {c.name: c for c in Category.query.all()}
        marcas = {m.name.upper(): m for m in Brand.query.all()}
        codigos_existentes = {c for (c,) in db.session.query(Product.code).all()}
        gtins_en_bd = {
            (p.sanitary_registration or "") for p in Product.query.all()
        }

        admin = User.query.filter_by(username="admin").first()
        admin_id = admin.id if admin else usuario_id

        hoy = date.today()
        vencimiento = hoy + timedelta(days=DIAS_VENCIMIENTO)
        contador = 0
        importados = 0

        for item in seleccion:
            if item["gtin"] in gtins_en_bd:
                continue  # ya importado en una corrida anterior (idempotente)

            contador += 1
            codigo = f"IMP-{contador:04d}"

            # Evitar colision de codigo IMP-#### si ya existieran
            while codigo in codigos_existentes:
                contador += 1
                codigo = f"IMP-{contador:04d}"
            codigos_existentes.add(codigo)

            # Precio de referencia USD -> cordobas
            precio_compra = round(item["precio_usd"] * tipo_cambio, 2)
            precio_venta = round(precio_compra * (1 + MARGEN_VENTA), 2)

            # Categoria (obligatoria) y marca (crear si es nueva)
            cat = cats.get(item["categoria"])
            if cat is None:
                log(f"   [WARN] categoria inexistente: {item['categoria']}")
                continue
            clave_marca = (item["marca"] or "GENERICA").upper()[:100]
            marca = marcas.get(clave_marca)
            if marca is None:
                marca = Brand(
                    name=clave_marca[:100],
                    description=f"Importada desde FDA UDI (fabricante: "
                                f"{item['fabricante'][:80] or 'N/D'})",
                )
                db.session.add(marca)
                db.session.flush()
                marcas[clave_marca] = marca

            nombre = traducir_nombre(
                item["descripcion"], item["marca"], item["modelo"]
            )
            presentacion = (
                f"Empaque x {item['cantidad_pkg']}" if item["cantidad_pkg"] else None
            )

            producto = Product(
                code=codigo,
                name=nombre,
                description=(
                    f"{item['descripcion']} | Fabricante: {item['fabricante']}"
                )[:300],
                category_id=cat.id,
                brand_id=marca.id,
                presentation=presentacion,
                unit="Unidad",
                purchase_price=precio_compra,
                sale_price=precio_venta,
                minimum_stock=5,
                sanitary_registration=item["gtin"],  # GTIN como identificador
                is_active=True,
            )
            db.session.add(producto)
            db.session.flush()

            # Lote inicial LIBERADO con movimiento ENTRADA (kardex)
            lote = ProductBatch(
                product_id=producto.id,
                batch_number=f"FDA-{gtin[-8:]}",
                expiration_date=vencimiento,
                quantity=STOCK_INICIAL,
                purchase_price=precio_compra,
                quarantine_status="LIBERADO",
                quarantine_notes="Lote inicial de importacion de catalogo",
                is_active=True,
            )
            db.session.add(lote)
            db.session.flush()
            db.session.add(InventoryMovement(
                product_id=producto.id,
                batch_id=lote.id,
                movement_type="ENTRADA",
                quantity=STOCK_INICIAL,
                reference_type="IMPORTACION",
                description=f"Stock inicial importado (GTIN {item['gtin']}, "
                            f"{precio_usd_str(item['precio_usd'])} -> "
                            f"{precio_compra} C$)",
                user_id=admin_id,
            ))
            gtins_en_bd.add(item["gtin"])
            importados += 1

        # --- Auditoria --------------------------------------------------------
        log("[4/4] Guardando ...")
        if not dry_run and importados:
            db.session.add(AuditLog(
                user_id=admin_id,
                action="CREATE",
                module="PRODUCTS",
                description=f"Importacion de catalogo internacional FDA UDI: "
                            f"{importados} producto(s), TC {tipo_cambio} C$/USD",
            ))
            db.session.commit()
            log(f"OK - {importados} producto(s) importados al inventario.")
        elif dry_run:
            db.session.rollback()
            log(f"[DRY-RUN] Se habrian importado {importados} producto(s).")
        else:
            db.session.rollback()
            log("Nada nuevo que importar (todo ya estaba en la BD).")


def precio_usd_str(v):
    return f"{v:.2f} USD"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Importa insumos medicos (GTIN + marca real) desde openFDA "
                    "con precios convertidos a cordobas."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="no escribe en la base de datos")
    parser.add_argument("--max", type=int, default=8,
                        help="maximo de registros por busqueda (default 8)")
    parser.add_argument("--user-id", type=int, default=1,
                        help="id del usuario para auditoria (default 1)")
    args = parser.parse_args()
    importar(dry_run=args.dry_run, max_por_busqueda=args.max,
             usuario_id=args.user_id)
