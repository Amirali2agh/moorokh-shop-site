from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from shop.models import Product, ProductVariant, StockAdjustment
from shop.pricing import QuoteLine, quote_merchandise


class MerchandisePricingTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(
            slug="pricing-fixture", name="Synthetic pricing fixture", is_active=True, is_approved=True
        )
        cls.first = ProductVariant.objects.create(
            product=cls.product,
            sku="PRICE-001",
            price_amount=Decimal("12.35"),
            currency_code="TEST",
            stock_on_hand=1,
            is_active=True,
        )
        cls.second = ProductVariant.objects.create(
            product=cls.product,
            sku="PRICE-002",
            price_amount=Decimal("0.29"),
            currency_code="TEST",
            stock_on_hand=0,
            is_active=True,
        )

    def setUp(self):
        stock_before = self.stock_snapshot()
        self.addCleanup(self.assert_inventory_unchanged, stock_before)

    def stock_snapshot(self):
        return dict(ProductVariant.objects.values_list("pk", "stock_on_hand"))

    def assert_inventory_unchanged(self, stock_before):
        self.assertEqual(self.stock_snapshot(), stock_before)
        self.assertFalse(StockAdjustment.objects.exists())

    def test_quote_uses_persisted_unit_prices_even_when_stock_is_insufficient(self):
        quote = quote_merchandise({self.second.pk: 3, self.first.pk: 2})

        self.assertEqual(quote.currency_code, "TEST")
        self.assertEqual(
            quote.lines,
            (
                QuoteLine(self.second.pk, 3, Decimal("0.29"), Decimal("0.87")),
                QuoteLine(self.first.pk, 2, Decimal("12.35"), Decimal("24.70")),
            ),
        )
        self.assertEqual(quote.total, Decimal("25.57"))

    def test_next_quote_uses_saved_price_change(self):
        quantities = {self.first.pk: 2}
        self.assertEqual(quote_merchandise(quantities).total, Decimal("24.70"))
        self.first.price_amount = Decimal("10.15")
        self.first.save(update_fields=["price_amount"])

        quote = quote_merchandise(quantities)
        self.assertEqual(quote.lines[0].unit_price, Decimal("10.15"))
        self.assertEqual(quote.total, Decimal("20.30"))

    def test_client_price_and_total_fields_are_rejected(self):
        with self.assertRaises(ValidationError):
            quote_merchandise({self.first.pk: {"quantity": 2, "unit_price": "0.01"}})
        with self.assertRaises(ValidationError):
            quote_merchandise({self.first.pk: 2, "total": "0.02"})

    def test_rejects_unknown_variant(self):
        with self.assertRaisesMessage(ValidationError, "unavailable"):
            quote_merchandise({self.first.pk: 1, self.second.pk + 1: 1})

    def test_rejects_inactive_variant(self):
        self.second.is_active = False
        self.second.save(update_fields=["is_active"])
        with self.assertRaisesMessage(ValidationError, "unavailable"):
            quote_merchandise({self.first.pk: 1, self.second.pk: 1})

    def test_rejects_inactive_or_unapproved_product(self):
        for is_active, is_approved in ((False, True), (True, False)):
            with self.subTest(is_active=is_active, is_approved=is_approved):
                self.product.is_active = is_active
                self.product.is_approved = is_approved
                self.product.save(update_fields=["is_active", "is_approved"])
                with self.assertRaisesMessage(ValidationError, "unavailable"):
                    quote_merchandise({self.first.pk: 1})

    def test_rejects_missing_price_or_currency(self):
        for price, currency in ((None, ""), (Decimal("0.29"), " ")):
            with self.subTest(price=price, currency=currency):
                self.second.price_amount = price
                self.second.currency_code = currency
                self.second.save(update_fields=["price_amount", "currency_code"])
                with self.assertRaisesMessage(ValidationError, "requires a price and currency"):
                    quote_merchandise({self.first.pk: 1, self.second.pk: 1})

    def test_rejects_invalid_quantities(self):
        for quantity in (0, -1, True, 1.0, Decimal("1"), "1", None):
            with self.subTest(quantity=quantity):
                with self.assertRaisesMessage(ValidationError, "positive whole numbers"):
                    quote_merchandise({self.first.pk: quantity})

    def test_rejects_empty_quote(self):
        with self.assertRaisesMessage(ValidationError, "at least one"):
            quote_merchandise({})

    def test_rejects_mixed_currencies(self):
        self.second.currency_code = "OTHER"
        self.second.save(update_fields=["currency_code"])
        with self.assertRaisesMessage(ValidationError, "single currency"):
            quote_merchandise({self.first.pk: 1, self.second.pk: 1})

    def test_large_quantity_keeps_exact_cents(self):
        quote = quote_merchandise({self.first.pk: 10**30 + 1, self.second.pk: 1})

        self.assertEqual(quote.total, Decimal("12350000000000000000000000000012.64"))
