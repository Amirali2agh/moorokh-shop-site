from .models import CatalogAudit, Product, ProductVariant


def _product_state(instance):
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


def _variant_state(instance):
    return {
        "product_id": instance.product_id,
        "sku": instance.sku,
        "label": instance.label,
        "attributes": instance.attributes,
        "price_amount": format(instance.price_amount, "f") if instance.price_amount is not None else None,
        "currency_code": instance.currency_code,
        "is_active": instance.is_active,
    }


_AUDIT_SERIALIZERS = {
    Product: (CatalogAudit.ObjectType.PRODUCT, _product_state),
    ProductVariant: (CatalogAudit.ObjectType.VARIANT, _variant_state),
}


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
    _, serializer = _audit_definition_for(instance)
    return serializer(instance)


def _object_type(instance):
    object_type, _ = _audit_definition_for(instance)
    return object_type


def _audit_definition_for(instance):
    for model, definition in _AUDIT_SERIALIZERS.items():
        if isinstance(instance, model):
            return definition
    raise TypeError("Catalog audit supports Product and ProductVariant only.")
