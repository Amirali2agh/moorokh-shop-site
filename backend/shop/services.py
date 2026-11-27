from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from .models import ProductVariant, StockAdjustment

MAX_STOCK = 2**63 - 1
MIN_DELTA = -(2**63)
MAX_DELTA = 2**63 - 1


def adjust_stock(*, variant_id, delta, reason, actor):
    _require_stock_operator(actor)
    _validate_adjustment(delta=delta, reason=reason)

    with transaction.atomic():
        try:
            variant = ProductVariant.objects.select_for_update().get(pk=variant_id)
        except ProductVariant.DoesNotExist as exc:
            raise ValidationError("Product variant does not exist.") from exc

        resulting_quantity = variant.stock_on_hand + delta
        if resulting_quantity < 0:
            raise ValidationError("Stock cannot be reduced below zero.")
        if resulting_quantity > MAX_STOCK:
            raise ValidationError("Stock exceeds the supported quantity range.")

        variant.stock_on_hand = resulting_quantity
        variant.updated_at = timezone.now()
        variant.save(update_fields=("stock_on_hand", "updated_at"))

        return StockAdjustment.objects.create(
            variant=variant,
            delta=delta,
            resulting_quantity=resulting_quantity,
            reason=reason.strip(),
            actor=actor,
        )


def _require_stock_operator(actor):
    if (
        actor is None
        or not getattr(actor, "is_authenticated", False)
        or not getattr(actor, "is_active", False)
        or not getattr(actor, "is_staff", False)
        or not actor.has_perm("shop.add_stockadjustment")
    ):
        raise PermissionDenied("An authorized staff operator is required to adjust stock.")


def _validate_adjustment(*, delta, reason):
    if isinstance(delta, bool) or not isinstance(delta, int):
        raise ValidationError("Stock adjustment must be a whole number.")
    if delta == 0:
        raise ValidationError("Stock adjustment cannot be zero.")
    if delta < MIN_DELTA or delta > MAX_DELTA:
        raise ValidationError("Stock adjustment exceeds the supported quantity range.")
    if not isinstance(reason, str) or not reason.strip():
        raise ValidationError("A reason is required for every stock adjustment.")
    if len(reason.strip()) > 240:
        raise ValidationError("Reason must be 240 characters or fewer.")
