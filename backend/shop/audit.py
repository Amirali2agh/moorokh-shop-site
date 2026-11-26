from .models import CatalogAudit, Product, ProductVariant


def record_catalog_change(*, instance, actor, before_state):
    CatalogAudit.objects.create(
        object_type=_object_type(instance),
        object_id=instance.pk,
        action=CatalogAudit.Action.CREATED if before_state is None else CatalogAudit.Action.UPDATED,
        actor=actor,
        before_state=before_state,
        after_state=catalog_state(instance),
    )


def catalog_state(instance):
    if isinstance(instance, Product):
        return {
            "slug": instance.slug,
            "name": instance.name,
            "category": instance.category,
            "description": instance.description,
            "specifications": instance.specifications,
            "image_url": instance.image_url,
            "is_active": instance.is_active,
            "is_approved": instance.is_approved,
        }
    if isinstance(instance, ProductVariant):
        return {
            "product_id": instance.product_id,
            "sku": instance.sku,
            "label": instance.label,
            "attributes": instance.attributes,
            "price_amount": format(instance.price_amount, "f") if instance.price_amount is not None else None,
            "currency_code": instance.currency_code,
            "is_active": instance.is_active,
        }
    raise TypeError("Catalog audit supports Product and ProductVariant only.")


def _object_type(instance):
    if isinstance(instance, Product):
        return CatalogAudit.ObjectType.PRODUCT
    if isinstance(instance, ProductVariant):
        return CatalogAudit.ObjectType.VARIANT
    raise TypeError("Catalog audit supports Product and ProductVariant only.")
