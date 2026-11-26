from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import HttpResponseRedirect
from django.template.response import TemplateResponse
from django.urls import reverse

from .audit import catalog_state, record_catalog_change
from .models import CatalogAudit, Product, ProductVariant, StockAdjustment
from .services import adjust_stock


class CatalogAuditAdminMixin:
    def save_model(self, request, obj, form, change):
        with transaction.atomic():
            before_state = (
                catalog_state(self.model.objects.select_for_update().get(pk=obj.pk))
                if change
                else None
            )
            super().save_model(request, obj, form, change)
            record_catalog_change(instance=obj, actor=request.user, before_state=before_state)


@admin.register(Product)
class ProductAdmin(CatalogAuditAdminMixin, admin.ModelAdmin):
    list_display = ("name", "slug", "category", "is_active", "is_approved", "updated_at")
    search_fields = ("name", "slug", "category")
    list_filter = ("is_active", "is_approved", "category")
    readonly_fields = ("created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProductVariant)
class ProductVariantAdmin(CatalogAuditAdminMixin, admin.ModelAdmin):
    list_display = ("sku", "product", "label", "price_amount", "currency_code", "stock_on_hand", "is_active")
    search_fields = ("sku", "product__name", "product__slug")
    list_filter = ("is_active", "currency_code")
    readonly_fields = ("stock_on_hand", "created_at", "updated_at")
    autocomplete_fields = ("product",)
    list_select_related = ("product",)

    def has_delete_permission(self, request, obj=None):
        return False


class StockAdjustmentForm(forms.Form):
    variant = forms.ModelChoiceField(
        queryset=ProductVariant.objects.select_related("product").order_by("product__name", "sku"),
        help_text="Choose the catalog variant whose stock is changing.",
    )
    delta = forms.IntegerField(help_text="Positive adds stock; negative removes stock.")
    reason = forms.CharField(max_length=240, strip=True)

    def clean_delta(self):
        delta = self.cleaned_data["delta"]
        if delta == 0:
            raise forms.ValidationError("Stock adjustment cannot be zero.")
        return delta

    def clean_reason(self):
        reason = self.cleaned_data["reason"].strip()
        if not reason:
            raise forms.ValidationError("A reason is required.")
        return reason


@admin.register(StockAdjustment)
class StockAdjustmentAdmin(admin.ModelAdmin):
    change_list_template = "admin/shop/stockadjustment/change_list.html"
    list_display = ("variant", "delta", "resulting_quantity", "reason", "actor", "created_at")
    list_select_related = ("variant", "variant__product", "actor")
    search_fields = ("variant__sku", "variant__product__name", "reason", "actor__username")
    readonly_fields = ("variant", "delta", "resulting_quantity", "reason", "actor", "created_at")
    actions = None

    def has_add_permission(self, request):
        return (
            request.user.is_active
            and request.user.is_staff
            and request.user.has_perm("shop.add_stockadjustment")
        )

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def add_view(self, request, form_url="", extra_context=None):
        if not self.has_add_permission(request):
            raise PermissionDenied

        form = StockAdjustmentForm(request.POST or None)
        if request.method == "POST" and form.is_valid():
            try:
                with transaction.atomic():
                    adjustment = adjust_stock(
                        variant_id=form.cleaned_data["variant"].pk,
                        delta=form.cleaned_data["delta"],
                        reason=form.cleaned_data["reason"],
                        actor=request.user,
                    )
                    self.log_addition(
                        request,
                        adjustment,
                        f"Stock adjustment {adjustment.delta:+d} by {request.user}",
                    )
            except ValidationError as exc:
                form.add_error(None, exc)
            else:
                self.message_user(request, "Stock adjustment recorded.", messages.SUCCESS)
                destination = (
                    "admin:shop_stockadjustment_changelist"
                    if self.has_view_permission(request)
                    else "admin:index"
                )
                return HttpResponseRedirect(reverse(destination))

        context = {
            **self.admin_site.each_context(request),
            "title": "Adjust stock",
            "opts": self.model._meta,
            "form": form,
            "media": form.media,
        }
        return TemplateResponse(request, "admin/shop/stock_adjustment_form.html", context)


@admin.register(CatalogAudit)
class CatalogAuditAdmin(admin.ModelAdmin):
    list_display = ("object_type", "object_id", "action", "actor", "created_at")
    list_filter = ("object_type", "action", "created_at")
    search_fields = ("object_id", "actor__username")
    readonly_fields = ("object_type", "object_id", "action", "actor", "before_state", "after_state", "created_at")
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
