from datetime import datetime, timezone
from sqlalchemy.exc import IntegrityError
from ..extensions import db
from ..models import Purchase, PurchaseItem, ProductBatch, InventoryMovement, AuditLog


class ReceptionError(Exception):
    pass


class DuplicateInvoiceError(ReceptionError):
    pass


class QuantityExceededError(ReceptionError):
    pass


class InvalidStateError(ReceptionError):
    pass


def validate_invoice_uniqueness(supplier_id, invoice_number, exclude_purchase_id=None):
    query = Purchase.query.filter(
        Purchase.supplier_id == supplier_id,
        Purchase.invoice_number == invoice_number,
        Purchase.status != "CANCELADA",
    )
    if exclude_purchase_id:
        query = query.filter(Purchase.id != exclude_purchase_id)
    existing = query.first()
    if existing:
        raise DuplicateInvoiceError(
            f"El proveedor ya tiene la factura '{invoice_number}' "
            f"registrada en la compra #{existing.id}."
        )
    return True


def validate_reception_quantities(purchase):
    errors = []
    for item in purchase.items:
        if item.quantity_received > item.quantity:
            product_name = item.product.name if item.product else f"#{item.product_id}"
            errors.append(
                f"Producto '{product_name}': recibido ({item.quantity_received}) "
                f"excede la cantidad pedida ({item.quantity})."
            )
    if errors:
        raise QuantityExceededError("; ".join(errors))
    return True


def receive_purchase(purchase_id, user_id, received_items=None):
    purchase = Purchase.query.get(purchase_id)
    if not purchase:
        raise InvalidStateError(f"Compra #{purchase_id} no encontrada.")
    if purchase.status not in ("BORRADOR",):
        raise InvalidStateError(
            f"La compra #{purchase_id} esta en estado '{purchase.status}'. "
            f"Solo se pueden recibir compras en estado BORRADOR."
        )

    if received_items:
        for item_data in received_items:
            item = PurchaseItem.query.get(item_data["purchase_item_id"])
            if item and item.purchase_id == purchase.id:
                new_qty = item_data.get("quantity_received", item.quantity_received or 0)
                item.quantity_received = new_qty

    for item in purchase.items:
        if not item.quantity_received:
            item.quantity_received = item.quantity

    validate_reception_quantities(purchase)
    validate_invoice_uniqueness(
        purchase.supplier_id, purchase.invoice_number, exclude_purchase_id=purchase.id
    )

    batches_created = []
    movements_created = []

    for item in purchase.items:
        if item.quantity_received <= 0:
            continue

        batch_number = f"CMP-{purchase.id}-{item.product_id}"
        expiration_date = item.expiration_date or (
            datetime.now().date()
            + __import__("datetime").timedelta(days=365)
        )
        manufacturing_date = item.manufacturing_date

        batch = ProductBatch(
            product_id=item.product_id,
            purchase_id=purchase.id,
            batch_number=batch_number,
            expiration_date=expiration_date,
            manufacturing_date=manufacturing_date,
            quantity=0,
            purchase_price=item.unit_cost,
            quarantine_status="CUARENTENA",
            is_active=True,
        )
        db.session.add(batch)
        db.session.flush()

        movement = InventoryMovement(
            product_id=item.product_id,
            batch_id=batch.id,
            movement_type="ENTRADA",
            quantity=item.quantity_received,
            reference_type="COMPRA",
            reference_id=purchase.id,
            description=f"Entrada por compra #{purchase.id} - Lote {batch_number}",
            user_id=user_id,
        )
        db.session.add(movement)
        db.session.flush()

        batches_created.append(batch)
        movements_created.append(movement)

    purchase.status = "RECIBIDA"

    audit = AuditLog(
        user_id=user_id,
        action="RECEIVE",
        module="PURCHASES",
        description=(
            f"Compra #{purchase.id} recibida - "
            f"{len(batches_created)} lote(s) en CUARENTENA"
        ),
    )
    db.session.add(audit)

    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        raise DuplicateInvoiceError(
            f"El proveedor ya tiene la factura '{purchase.invoice_number}' "
            f"registrada en otra compra activa."
        )
    except Exception:
        db.session.rollback()
        raise

    return {
        "purchase": purchase,
        "batches": batches_created,
        "movements": movements_created,
    }


def release_batch(batch_id, user_id, notes=None):
    batch = ProductBatch.query.get(batch_id)
    if not batch:
        raise InvalidStateError(f"Lote #{batch_id} no encontrado.")
    if batch.quarantine_status != "CUARENTENA":
        raise InvalidStateError(
            f"El lote '{batch.batch_number}' esta en estado "
            f"'{batch.quarantine_status}'. Solo se pueden liberar lotes en CUARENTENA."
        )

    batch.quarantine_status = "LIBERADO"
    batch.quarantine_notes = notes
    batch.released_by = user_id
    batch.released_at = datetime.now(timezone.utc)

    audit = AuditLog(
        user_id=user_id,
        action="RELEASE_BATCH",
        module="INVENTORY",
        description=f"Lote '{batch.batch_number}' liberado para venta.",
    )
    db.session.add(audit)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return batch


def reject_batch(batch_id, user_id, notes=None):
    batch = ProductBatch.query.get(batch_id)
    if not batch:
        raise InvalidStateError(f"Lote #{batch_id} no encontrado.")
    if batch.quarantine_status != "CUARENTENA":
        raise InvalidStateError(
            f"El lote '{batch.batch_number}' esta en estado "
            f"'{batch.quarantine_status}'. Solo se pueden rechazar lotes en CUARENTENA."
        )

    batch.quarantine_status = "RECHAZADO"
    batch.quarantine_notes = notes
    batch.released_by = user_id
    batch.released_at = datetime.now(timezone.utc)
    batch.is_active = False

    audit = AuditLog(
        user_id=user_id,
        action="REJECT_BATCH",
        module="INVENTORY",
        description=f"Lote '{batch.batch_number}' rechazado.",
    )
    db.session.add(audit)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return batch
