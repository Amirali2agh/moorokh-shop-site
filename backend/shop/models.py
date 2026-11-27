from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Product(models.Model):
    slug = models.SlugField(max_length=160, unique=True)
    name = models.CharField(max_length=200)
    category = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    specifications = models.JSONField(default=dict, blank=True)
    image_url = models.CharField(max_length=500, blank=True)
    is_active = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("name", "pk")

    def __str__(self):
        return self.name


class ProductVariant(models.Model):
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="variants")
    sku = models.CharField(max_length=80, unique=True)
    label = models.CharField(max_length=160, blank=True)
    attributes = models.JSONField(default=dict, blank=True)
    price_amount = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    currency_code = models.CharField(max_length=12, blank=True)
    stock_on_hand = models.PositiveBigIntegerField(default=0)
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("product__name", "sku")
        constraints = [
            models.CheckConstraint(
                condition=Q(price_amount__isnull=True, currency_code="")
                | (Q(price_amount__isnull=False) & ~Q(currency_code="")),
                name="shop_variant_price_currency_pair",
            ),
            models.CheckConstraint(
                condition=Q(price_amount__isnull=True) | Q(price_amount__gt=0),
                name="shop_variant_price_positive",
            ),
            models.CheckConstraint(
                condition=Q(stock_on_hand__gte=0),
                name="shop_variant_stock_nonnegative",
            ),
        ]

    def clean(self):
        errors = {}
        if self.price_amount is None and self.currency_code:
            errors["currency_code"] = "Currency must be empty when no price is set."
        elif self.price_amount is not None and not self.currency_code:
            errors["currency_code"] = "Currency is required when a price is set."
        if self.price_amount is not None and self.price_amount <= 0:
            errors["price_amount"] = "Price must be greater than zero."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.product.name} — {self.sku}"


class AppendOnlyModel(models.Model):
    append_only_message = "Records are append-only."

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(self.append_only_message)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(self.append_only_message)


class CatalogAudit(AppendOnlyModel):
    append_only_message = "Catalog audit records are append-only."

    class ObjectType(models.TextChoices):
        PRODUCT = "product", "Product"
        VARIANT = "variant", "Variant"

    class Action(models.TextChoices):
        CREATED = "created", "Created"
        UPDATED = "updated", "Updated"

    object_type = models.CharField(max_length=16, choices=ObjectType.choices)
    object_id = models.PositiveBigIntegerField()
    action = models.CharField(max_length=16, choices=Action.choices)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    before_state = models.JSONField(null=True, blank=True)
    after_state = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")

    def __str__(self):
        return f"{self.object_type} {self.object_id}: {self.action}"


class StockAdjustment(AppendOnlyModel):
    append_only_message = "Stock adjustment records are append-only."

    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, related_name="stock_adjustments")
    delta = models.BigIntegerField()
    resulting_quantity = models.PositiveBigIntegerField()
    reason = models.CharField(max_length=240)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at", "-pk")
        constraints = [
            models.CheckConstraint(condition=~Q(delta=0), name="shop_stock_adjustment_nonzero_delta"),
        ]

    def __str__(self):
        return f"{self.variant.sku}: {self.delta:+d} → {self.resulting_quantity}"
