from django.db import transaction

from .models import Cart, CartItem, ProductVariant


def list_cart_items(session):
    if not session.session_key or not session.exists(session.session_key):
        return []
    return list(
        CartItem.objects.filter(cart_id=session.session_key)
        .order_by("variant_id")
        .values("variant_id", "quantity")
    )


@transaction.atomic
def set_cart_item_quantity(session, *, variant_id, quantity):
    variant = ProductVariant.objects.filter(
        pk=variant_id,
        product__is_active=True,
        product__is_approved=True,
        is_active=True,
        stock_on_hand__gt=0,
    ).first()
    if variant is None:
        return False

    session_key = session.session_key
    if not session_key or not session.exists(session_key):
        session.create()
        session_key = session.session_key

    cart, _ = Cart.objects.get_or_create(session_id=session_key)
    CartItem.objects.update_or_create(
        cart=cart,
        variant=variant,
        defaults={"quantity": quantity},
    )
    return True


def remove_cart_item(session, *, variant_id):
    session_key = session.session_key
    if not session_key or not session.exists(session_key):
        return
    CartItem.objects.filter(cart_id=session_key, variant_id=variant_id).delete()
