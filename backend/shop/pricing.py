from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, localcontext

from django.core.exceptions import ValidationError

from .models import ProductVariant


@dataclass(frozen=True)
class QuoteLine:
    variant_id: int
    quantity: int
    unit_price: Decimal
    subtotal: Decimal


@dataclass(frozen=True)
class MerchandiseQuote:
    currency_code: str
    lines: tuple[QuoteLine, ...]
    total: Decimal


def quote_merchandise(quantities: Mapping[int, int]) -> MerchandiseQuote:
    """Price a nonempty mapping of variant IDs to quantities in input order."""
    if not isinstance(quantities, Mapping) or not quantities:
        raise ValidationError("Provide at least one variant ID and quantity.")

    items = tuple(quantities.items())
    for variant_id, quantity in items:
        if type(variant_id) is not int or variant_id <= 0:
            raise ValidationError("Variant IDs must be positive integers.")
        if type(quantity) is not int or quantity <= 0:
            raise ValidationError("Quantities must be positive whole numbers.")

    variants = ProductVariant.objects.filter(
        is_active=True, product__is_active=True, product__is_approved=True
    ).in_bulk(variant_id for variant_id, _ in items)
    priced_items = []
    currency_code = None
    for variant_id, quantity in items:
        variant = variants.get(variant_id)
        if variant is None:
            raise ValidationError(f"Variant {variant_id} is unavailable for quoting.")
        if variant.price_amount is None or not variant.currency_code.strip():
            raise ValidationError(f"Variant {variant_id} requires a price and currency.")
        if currency_code is not None and currency_code != variant.currency_code:
            raise ValidationError("A quote must use a single currency.")
        currency_code = variant.currency_code
        priced_items.append((variant, quantity))

    # Allow enough digits for the largest multiplication and the sum of all lines.
    with localcontext() as context:
        context.prec = max(
            len(variant.price_amount.as_tuple().digits) + Decimal(quantity).adjusted() + 1
            for variant, quantity in priced_items
        ) + len(str(len(priced_items)))
        lines = tuple(
            QuoteLine(variant.pk, quantity, variant.price_amount, variant.price_amount * quantity)
            for variant, quantity in priced_items
        )
        total = sum((line.subtotal for line in lines), Decimal("0.00"))

    return MerchandiseQuote(currency_code, lines, total)
