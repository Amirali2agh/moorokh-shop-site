from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .catalog import list_public_products


@require_GET
def product_list(request):
    return JsonResponse({"results": list_public_products()})
