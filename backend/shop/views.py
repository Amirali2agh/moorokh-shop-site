import json

from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_http_methods

from .catalog import list_public_products
from .cart import list_cart_items, remove_cart_item, set_cart_item_quantity

MAX_CART_QUANTITY = 9_223_372_036_854_775_807


@require_GET
def product_list(request):
    return JsonResponse({"results": list_public_products()})


@never_cache
@ensure_csrf_cookie
@require_GET
def cart_list(request):
    return JsonResponse({"items": list_cart_items(request.session)})


@never_cache
@require_http_methods(["PUT", "DELETE"])
def cart_item(request, variant_id):
    if request.method == "DELETE":
        remove_cart_item(request.session, variant_id=variant_id)
        return HttpResponse(status=204)

    if request.content_type != "application/json":
        return JsonResponse({"error": "invalid_request"}, status=400)
    try:
        payload = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "invalid_request"}, status=400)
    if (
        not isinstance(payload, dict)
        or set(payload) != {"quantity"}
        or type(payload["quantity"]) is not int
        or not 1 <= payload["quantity"] <= MAX_CART_QUANTITY
    ):
        return JsonResponse({"error": "invalid_request"}, status=400)

    quantity = payload["quantity"]
    if not set_cart_item_quantity(request.session, variant_id=variant_id, quantity=quantity):
        return JsonResponse({"error": "variant_unavailable"}, status=404)
    return JsonResponse({"variant_id": variant_id, "quantity": quantity})
