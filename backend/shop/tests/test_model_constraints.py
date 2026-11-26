from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from shop.models import Product, ProductVariant


class ProductVariantValidationTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(slug="constraint-fixture", name="Constraint fixture")

    def test_price_and_currency_must_be_provided_together(self):
        variant = ProductVariant(
            product=self.product,
            sku="INVALID-PAIR",
            price_amount=Decimal("10.00"),
            currency_code="",
        )

        with self.assertRaises(ValidationError):
            variant.full_clean()

        variant = ProductVariant(
            product=self.product,
            sku="INVALID-PAIR-REVERSE",
            price_amount=None,
            currency_code="TEST",
        )
        with self.assertRaises(ValidationError):
            variant.full_clean()

    def test_database_rejects_price_without_currency_even_when_validation_is_bypassed(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProductVariant.objects.create(
                    product=self.product,
                    sku="INVALID-DB-PAIR",
                    price_amount=Decimal("10.00"),
                    currency_code="",
                )

    def test_database_rejects_currency_without_price_even_when_validation_is_bypassed(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProductVariant.objects.create(
                    product=self.product,
                    sku="INVALID-DB-PAIR-REVERSE",
                    price_amount=None,
                    currency_code="TEST",
                )

    def test_database_rejects_nonpositive_price_even_when_validation_is_bypassed(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProductVariant.objects.create(
                    product=self.product,
                    sku="NONPOSITIVE-PRICE",
                    price_amount=Decimal("0.00"),
                    currency_code="TEST",
                )

    def test_database_rejects_negative_stock_even_when_validation_is_bypassed(self):
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ProductVariant.objects.create(
                    product=self.product,
                    sku="NEGATIVE-STOCK",
                    stock_on_hand=-1,
                )
