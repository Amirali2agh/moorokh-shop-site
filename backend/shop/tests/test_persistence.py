from django.contrib.auth import get_user_model
from django.db import connections
from django.test import Client, TransactionTestCase, skipUnlessDBFeature

from shop.models import Product, ProductVariant, StockAdjustment
from shop.services import adjust_stock


@skipUnlessDBFeature("has_select_for_update")
class CatalogPersistenceTests(TransactionTestCase):
    def test_catalog_and_stock_audit_survive_database_connection_reopen(self):
        operator = get_user_model().objects.create_superuser(
            username="durability-admin", email="durability@example.invalid", password="test-only-password"
        )
        product = Product.objects.create(
            slug="durability-fixture",
            name="Synthetic persistence fixture",
            is_active=True,
            is_approved=True,
        )
        variant = ProductVariant.objects.create(
            product=product,
            sku="DURABLE-001",
            stock_on_hand=1,
            is_active=True,
        )
        adjustment = adjust_stock(
            variant_id=variant.pk,
            delta=4,
            reason="durability test",
            actor=operator,
        )
        product_id = product.slug
        variant_id = variant.pk
        adjustment_id = adjustment.pk

        connections.close_all()
        response = Client().get("/api/products")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["results"][0]["id"], product_id)
        self.assertTrue(response.json()["results"][0]["variants"][0]["is_available"])
        self.assertEqual(ProductVariant.objects.get(pk=variant_id).stock_on_hand, 5)
        self.assertEqual(StockAdjustment.objects.get(pk=adjustment_id).resulting_quantity, 5)
