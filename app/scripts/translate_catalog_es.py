"""
Traduce al espanol los nombres y descripciones de los productos importados
desde el catalogo FDA UDI (codigos IMP-####).

- Traduce la terminologia medica con un diccionario ES construido sobre el
  vocabulario real del catalogo (frases completas primero, luego palabras).
- Preserva intactas las marcas comerciales (ENCORE, HALYARD, GAMMEX...),
  los numeros de modelo y las medidas (5.5, 7.0, ml, fr...).
- Limpia el sufijo "TM" heredado del simbolo (tm) en marcas.

Uso:
    python -m app.scripts.translate_catalog_es --dry-run   # solo muestra
    python -m app.scripts.translate_catalog_es             # aplica cambios
"""

import argparse
import re
import sys

# ---------------------------------------------------------------------------
# Diccionario de traduccion. Las frases se evaluan de la mas larga a la mas
# corta: primero cubren combinaciones de material + tipo + atributos para
# lograr un orden de palabras natural en espanol.
# ---------------------------------------------------------------------------
FRASES = {
    # --- Guantes: material + tipo + atributo (variantes de orden) ---------
    "nitrile examination glove powder free": "guante de exploracion de nitrilo sin polvo",
    "powder free nitrile examination glove": "guante de exploracion de nitrilo sin polvo",
    "powder-free nitrile examination glove": "guante de exploracion de nitrilo sin polvo",
    "nitrile examination glove": "guante de exploracion de nitrilo",
    "latex examination glove powder free": "guante de exploracion de latex sin polvo",
    "powder free latex examination glove": "guante de exploracion de latex sin polvo",
    "powder-free latex examination glove": "guante de exploracion de latex sin polvo",
    "latex examination glove": "guante de exploracion de latex",
    "vinyl examination glove": "guante de exploracion de vinilo",
    "polyethylene examination glove": "guante de exploracion de polietileno",
    "sterile latex powder-free surgical glove": "guante quirurgico esteril de latex sin polvo",
    "sterile polyisoprene powder-free surgical glove": "guante quirurgico esteril de poliisopreno sin polvo",
    "sterile neoprene powder-free surgical glove": "guante quirurgico esteril de neopreno sin polvo",
    "latex powder-free surgical glove": "guante quirurgico de latex sin polvo",
    "polyisoprene powder-free surgical glove": "guante quirurgico de poliisopreno sin polvo",
    "neoprene powder-free surgical glove": "guante quirurgico de neopreno sin polvo",
    "powder-free latex surgical glove": "guante quirurgico de latex sin polvo",
    "powder-free polyisoprene surgical glove": "guante quirurgico de poliisopreno sin polvo",
    "powder-free neoprene surgical glove": "guante quirurgico de neopreno sin polvo",
    "powder-free nitrile surgical glove": "guante quirurgico de nitrilo sin polvo",
    "polyisoprene surgical glove": "guante quirurgico de poliisopreno",
    "neoprene surgical glove": "guante quirurgico de neopreno",
    "latex surgical glove": "guante quirurgico de latex",
    "examination glove": "guante de exploracion",
    "surgical glove": "guante quirurgico",
    # --- Mascarillas, proteccion ------------------------------------------
    "surgical mask": "mascarilla quirurgica",
    "procedure mask": "mascarilla de procedimiento",
    "face mask": "mascarilla facial",
    "ear loop mask": "mascarilla con orejeras elasticas",
    "earloop mask": "mascarilla con orejeras elasticas",
    "face shield": "protector facial",
    "medical face shield": "protector facial medico",
    "filtering facepiece": "respirador",
    "protective goggles": "gafas de proteccion",
    "safety goggles": "gafas de seguridad",
    "disposable gown": "bata desechable",
    "isolation gown": "bata de aislamiento",
    "powder-free": "sin polvo",
    "powder free": "sin polvo",
    "latex-free": "sin latex",
    "latex free": "sin latex",
    "non-latex": "sin latex",
    "non latex": "sin latex",
    "non-sterile": "no esteril",
    "single use": "de un solo uso",
    "single-use": "de un solo uso",
    "anti-fog": "antivaho",
    "anti fog": "antivaho",
    "anti-reflux": "antirreflujo",
    # --- Equipos ------------------------------------------------------------
    "blood pressure monitor": "monitor de presion arterial",
    "blood pressure": "presion arterial",
    "pulse oximeter": "oximetro de pulso",
    "fingertip pulse": "oximetro de pulso de dedo",
    "blood glucose meter": "glucometro",
    "glucose meter": "glucometro",
    "blood glucose": "glucosa en sangre",
    "control solution": "solucion de control",
    "test strip": "tira reactiva",
    "test strips": "tiras reactivas",
    "lancing device": "dispositivo de puncion",
    "digital thermometer": "termometro digital",
    "weighing scale": "bascula",
    "patient scale": "bascula para paciente",
    "sphygmomanometer": "esfigmomanometro",
    "dual head stethoscope": "estetoscopio de doble campana",
    "double head stethoscope": "estetoscopio de doble campana",
    "single head stethoscope": "estetoscopio de una campana",
    "chest piece": "campana",
    "chestpiece": "campana",
    # --- Material de curacion ------------------------------------------------
    "blood collection tube": "tubo de extraccion de sangre",
    "blood collection": "extraccion de sangre",
    "nasogastric tube": "sonda nasogastrica",
    "feeding tube": "sonda de alimentacion",
    "suction catheter": "sonda de aspiracion",
    "oxygen mask": "mascarilla de oxigeno",
    "nebulizer mask kit": "kit de mascarilla para nebulizador",
    "nebulizer mask": "mascarilla para nebulizador",
    "nebulizer kit": "kit de nebulizador",
    "nasal cannula": "canula nasal",
    "iv administration set": "equipo de administracion intravenosa",
    "iv administration": "administracion intravenosa",
    "administration set": "equipo de administracion",
    "urine collection bag": "bolsa colectora de orina",
    "urinary drainage bag": "bolsa de drenaje urinario",
    "collection bag": "bolsa colectora",
    "gauze bandage roll": "rollo de venda de gasa",
    "adhesive bandage": "tirita adhesiva",
    "gauze bandage": "venda de gasa",
    "elastic bandage": "venda elastica",
    "conforming bandage": "venda de conformacion",
    "gauze sponge": "compresa de gasa",
    "abdominal pad": "aposito abdominal",
    "wound dressing": "aposito para heridas",
    "adhesive tape": "cinta adhesiva",
    "sterile gauze": "gasa esteril",
    "medical gauze": "gasa medica",
    "hypodermic needle": "aguja hipodermica",
    "insulin syringe": "jeringa de insulina",
    "tuberculin syringe": "jeringa de tuberculina",
    "disposable syringe": "jeringa desechable",
    "first aid kit": "kit de primeros auxilios",
    "first aid": "primeros auxilios",
    "luer lock": "luer lock",
    "oxygen tubing": "manguera de oxigeno",
    "eye irrigation": "irrigacion ocular",
    # --- Tallas ---------------------------------------------------------------
    "xx-large": "talla XXL",
    "x-large": "talla extragrande",
    "x-small": "talla extrapequena",
    "extra large": "talla extragrande",
    "extra small": "talla extrapequena",
    "size small": "talla pequena",
    "size medium": "talla mediana",
    "size large": "talla grande",
    "small adult": "adulto talla pequena",
    "3 ply": "3 capas",
    "three ply": "3 capas",
    "4 ply": "4 capas",
    "ear loop": "con orejeras elasticas",
    "earloop": "con orejeras elasticas",
    "made in": "fabricado en",
    "not made": "no fabricado",
    "intended for": "destinado a",
}

PALABRAS = {
    # tipos de producto
    "gloves": "guantes", "glove": "guante",
    "masks": "mascarillas", "mask": "mascarilla",
    "respirator": "respirador",
    "bandages": "vendas", "bandage": "venda",
    "gauze": "gasa", "sponges": "compresas", "sponge": "compresa",
    "pads": "apositos", "pad": "aposito",
    "dressings": "apositos", "dressing": "aposito",
    "tape": "cinta", "syringes": "jeringas", "syringe": "jeringa",
    "needles": "agujas", "needle": "aguja",
    "tubes": "tubos", "tube": "tubo", "tubing": "tubo",
    "catheters": "sondas", "catheter": "sonda",
    "bags": "bolsas", "bag": "bolsa",
    "kit": "kit", "kits": "kits", "sets": "equipos", "set": "equipo",
    "rolls": "rollos", "roll": "rollo",
    "vials": "viales", "vial": "vial",
    "stethoscope": "estetoscopio", "stethoscopes": "estetoscopios",
    "thermometer": "termometro",
    "monitor": "monitor", "cuff": "brazalete", "cuffs": "brazaletes",
    "scale": "bascula",
    "oximeter": "oximetro", "glucometer": "glucometro",
    "meter": "medidor", "device": "dispositivo", "devices": "dispositivos",
    "strips": "tiras", "strip": "tira",
    "lancets": "lancetas", "lancet": "lanceta",
    "goggles": "gafas", "visor": "visera",
    "gown": "bata", "gowns": "batas",
    "cannula": "canula",
    "nebulizer": "nebulizador",
    "filter": "filtro", "filters": "filtros",
    "swab": "hisopo", "swabs": "hisopos",
    "cap": "tapa", "closure": "cierre", "funnel": "embudo",
    "valve": "valvula", "valves": "valvulas",
    "connector": "conector", "stylet": "fiador",
    "tourniquet": "torniquete", "tourniquets": "torniquetes",
    # materiales
    "latex": "latex", "nitrile": "nitrilo", "polyisoprene": "poliisopreno",
    "neoprene": "neopreno", "vinyl": "vinilo", "polyethylene": "polietileno",
    "polypropylene": "polipropileno", "plastic": "plastico",
    "rubber": "caucho", "cotton": "algodon",
    # atributos
    "sterile": "esteril", "sterility": "esterilidad",
    "disposable": "desechable", "examination": "exploracion",
    "exam": "exploracion", "surgical": "quirurgico",
    "medical": "medico", "elastic": "elastico",
    "adhesive": "adhesivo", "protective": "protectora",
    "protection": "proteccion", "safety": "seguridad",
    "digital": "digital", "pediatric": "pediatrico",
    "adult": "adulto", "infant": "infantil", "child": "infantil",
    "neonatal": "neonatal", "powder": "polvo",
    "textured": "texturizado", "micro": "micro",
    "breathable": "transpirable", "flexible": "flexible",
    "comfortable": "comodo", "soft": "suave",
    "waterproof": "impermeable", "fluid": "fluidos",
    "resistant": "resistente", "adjustable": "ajustable",
    "transparent": "transparente", "clear": "transparente",
    "automatic": "automatico", "manual": "manual",
    "hygienic": "higienico", "hygiene": "higiene",
    # medidas y colores
    "size": "talla", "sizes": "tallas", "inch": "pulgada",
    "inches": "pulgadas", "gauge": "calibre",
    "green": "verde", "blue": "azul", "pink": "rosa", "red": "rojo",
    "yellow": "amarillo", "black": "negro", "gray": "gris",
    "orange": "naranja", "purple": "morado", "lavender": "lila",
    "white": "blanco", "silver": "plateado", "burgundy": "borgona",
    # tallas sueltas de guantes (contexto del catalogo)
    "small": "talla pequena", "medium": "talla mediana", "large": "talla grande",
    # conectores y palabras de relleno comunes
    "with": "con", "and": "y", "for": "para", "the": "el",
    "of": "de", "in": "en", "or": "o", "per": "por", "each": "cada",
    "is": "es", "are": "son", "not": "no", "on": "sobre",
    "use": "uso", "uses": "usos", "used": "usado",
    "single": "individual", "double": "doble",
    "box": "caja", "case": "caja", "pack": "paquete",
    "package": "empaque", "packaging": "empaque",
    "included": "incluido", "include": "incluye",
    "designed": "disenado", "provide": "proporcionar",
    "provides": "proporciona", "barrier": "barrera",
    "filtration": "filtracion", "efficiency": "eficiencia",
    "nose": "nariz", "mouth": "boca", "face": "facial",
    "eye": "ocular", "eyes": "ojos", "skin": "piel",
    "wound": "herida", "wounds": "heridas",
    "blood": "sangre", "fluids": "fluidos",
    "patient": "paciente", "patients": "pacientes",
    "healthcare": "salud", "professionals": "profesionales",
    "professional": "profesional",
    "sample": "muestra", "samples": "muestras",
    "collection": "recoleccion", "handling": "manipulacion",
    "cleaning": "limpieza", "disinfection": "desinfeccion",
    "pressure": "presion", "pulse": "pulso",
    "oxygen": "oxigeno", "saturation": "saturacion",
    "glucose": "glucosa", "temperature": "temperatura",
    "body": "corporal", "oral": "oral", "axillary": "axilar",
    "tip": "punta", "probe": "sonda", "battery": "bateria",
    "display": "pantalla", "screen": "pantalla",
    "alarm": "alarma", "memory": "memoria",
    "care": "cuidado", "daily": "diario",
    # terminos especificos vistos en descripciones del catalogo
    "clamshell": "empaque tipo concha",
    "wallchart": "cartel de pared",
    "procedura": "procedimiento",
    "hazard": "riesgo", "exposure": "exposicion",
    "cross": "cruz", "contamination": "contaminacion",
    "elastic": "elastico", "stretch": "elastico",
    "seamless": "sin costuras", "beaded": "con borde",
    "ambidextrous": "ambidiestro", "straight": "recto",
    "curved": "curvo", "funnel": "embudo",
    "sleeve": "manga", "neck": "cuello",
    "drawstring": "con cordon", "ties": "con lazadas",
    "knit": "tejido", "cuff": "brazalete",
}

# Nombres propios que nunca deben traducirse (marcas + terminos tecnicos)
NOMBRES_PROPIOS = {
    "encore", "novaplus", "gammex", "halyard", "sempermed", "syntegra",
    "touchntuff", "omnitrust", "vixone", "kimberly", "clark", "medline",
    "ansell", "edta", "heparin", "sodium", "lithium", "fluoride",
    "citrate", "oxalate", "potassium", "k2", "k3",
    "luer", "cpap", "oled", "lcd", "iv", "ml", "fr", "cc",
    "rspatm", "kimvent", "mic-key", "corpak", "argyle", "dovewhisper",
    "kimberly-clark",
}

TM_RESIDUAL = re.compile(r"(?<=[A-Za-z])(TM|tm)\b")


def _proteger_texto(texto):
    """Reemplaza marcas, modelos y medidas por placeholders {0}..{n}."""
    protegidos = []

    def proteger(match):
        token = match.group(0)
        if token.lower() in NOMBRES_PROPIOS or re.fullmatch(
            r"[A-Za-z]*\d[\w.\-]*", token
        ):
            protegidos.append(token)
            return f"\x00{len(protegidos) - 1}\x00"
        return token

    resultado = re.sub(r"[\w.\-]+", proteger, texto)
    return resultado, protegidos


def _restaurar_texto(texto, protegidos):
    for i, token in enumerate(protegidos):
        texto = texto.replace(f"\x00{i}\x00", token)
    return texto


def traducir(texto):
    """Traduce un fragmento de texto tecnico-medico al espanol."""
    if not texto:
        return texto

    texto = TM_RESIDUAL.sub("", texto)
    protegible, protegidos = _proteger_texto(texto)

    # Frases multi-palabra (de mas larga a mas corta)
    for en in sorted(FRASES, key=len, reverse=True):
        patron = re.compile(re.escape(en), re.IGNORECASE)
        protegible = patron.sub(FRASES[en], protegible)

    # Palabras sueltas
    def reemplazar_palabra(match):
        palabra = match.group(0)
        return PALABRAS.get(palabra.lower(), palabra)

    resultado = re.sub(r"[A-Za-z]+", reemplazar_palabra, protegible)
    resultado = _restaurar_texto(resultado, protegidos)

    # Limpieza final
    resultado = re.sub(r"\s+", " ", resultado).strip()
    resultado = re.sub(r"\s+([,.;:)])", r"\1", resultado)
    resultado = re.sub(r"\(\s+", "(", resultado)
    resultado = re.sub(r"\btalla talla\b", "talla", resultado)
    if resultado:
        resultado = resultado[0].upper() + resultado[1:]
    return resultado


def limpiar_marca(nombre):
    """Quita el sufijo 'TM' heredado del simbolo (tm)."""
    limpio = TM_RESIDUAL.sub("", nombre.strip())
    return limpio[:100] if limpio else nombre[:100]


def traducir_nombre(nombre):
    """Traduce el nombre manteniendo 'MARCA - Modelo X' intacto."""
    partes = nombre.rsplit(" - ", 2)
    if len(partes) == 3 and partes[2].startswith("Modelo "):
        desc, marca, modelo = partes
        return f"{traducir(desc)} - {limpiar_marca(marca)} - {modelo}"
    return traducir(nombre)


def traducir_descripcion(descripcion):
    """Traduce la parte descriptiva y conserva '| Fabricante: X'."""
    if not descripcion:
        return descripcion
    if " | Fabricante: " in descripcion:
        desc, fabricante = descripcion.split(" | Fabricante: ", 1)
        return f"{traducir(desc)} | Fabricante: {fabricante}"
    return traducir(descripcion)


def main(dry_run=False):
    sys.path.insert(0, ".")
    from app import create_app
    from app.extensions import db
    from app.models.products import Brand, Product
    from app.models.security import AuditLog

    app = create_app()
    with app.app_context():
        productos = Product.query.filter(Product.code.like("IMP-%")).all()
        log = print
        log(f"Productos a traducir: {len(productos)}")

        cambiados = 0
        muestra = []
        for p in productos:
            nombre_nuevo = traducir_nombre(p.name)
            desc_nueva = traducir_descripcion(p.description)
            if nombre_nuevo != p.name or desc_nueva != p.description:
                if len(muestra) < 10:
                    muestra.append((p.code, p.name, nombre_nuevo))
                if not dry_run:
                    p.name = nombre_nuevo
                    p.description = desc_nueva
                cambiados += 1

        # Limpieza de marcas con sufijo TM
        marcas_limpiadas = 0
        if not dry_run:
            for marca in Brand.query.all():
                limpio = limpiar_marca(marca.name)
                if limpio != marca.name:
                    colision = Brand.query.filter(
                        Brand.name == limpio, Brand.id != marca.id
                    ).first()
                    if colision is None:
                        marca.name = limpio
                        marcas_limpiadas += 1

        if dry_run:
            log(f"[DRY-RUN] Se traducirian {cambiados} producto(s).")
        else:
            if cambiados:
                db.session.add(AuditLog(
                    user_id=1,
                    action="UPDATE",
                    module="PRODUCTS",
                    description=(
                        f"Traduccion al espanol del catalogo importado: "
                        f"{cambiados} producto(s); {marcas_limpiadas} marca(s) "
                        f"normalizadas"
                    ),
                ))
                db.session.commit()
            log(f"OK - {cambiados} producto(s) traducidos, "
                f"{marcas_limpiadas} marca(s) normalizadas.")

        log("\n--- Muestra de traduccion ---")
        for codigo, antes, despues in muestra:
            log(f"{codigo}")
            log(f"  EN: {antes}")
            log(f"  ES: {despues}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Traduce al espanol los productos importados (IMP-####)"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="muestra el resultado sin escribir en la BD")
    args = parser.parse_args()
    main(dry_run=args.dry_run)
