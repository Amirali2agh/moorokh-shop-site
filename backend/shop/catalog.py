from django.db.models import Prefetch

from .models import Product, ProductVariant


def list_public_products():
    active_variants = ProductVariant.objects.filter(is_active=True).order_by("sku")
    products = (
        Product.objects.filter(is_active=True, is_approved=True, variants__is_active=True)
        .distinct()
        .prefetch_related(Prefetch("variants", queryset=active_variants))
    )
    return [_serialize_product(product) for product in products]


def _serialize_product(product):
    return {
        "id": product.slug,
        "name": product.name,
        "category": product.category,
        "description": product.description,
        "specifications": product.specifications,
        "image_url": product.image_url,
        "variants": [_serialize_variant(variant) for variant in product.variants.all()],
    }


def _serialize_variant(variant):
    return {
        "id": variant.pk,
        "sku": variant.sku,
        "label": variant.label,
        "attributes": variant.attributes,
        "price_amount": format(variant.price_amount, ".2f") if variant.price_amount is not None else None,
        "currency_code": variant.currency_code or None,
        "is_available": variant.stock_on_hand > 0,
    }
