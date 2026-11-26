from django.urls import path

from . import views

urlpatterns = [
    path("products", views.product_list, name="product-list"),
    path("cart", views.cart_list, name="cart-list"),
    path("cart/items/<int:variant_id>", views.cart_item, name="cart-item"),
]
