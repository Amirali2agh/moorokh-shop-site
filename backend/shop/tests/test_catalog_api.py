from decimal import Decimal

from django.test import TestCase


class PublicCatalogContractTests(TestCase):
    def test_empty_catalog_is_a_successful_read_until_approved_products_are_added(self):
        response = self.client.get("/api/products")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"results": []})

    def test_public_read_includes_only_approved_active_products_and_safe_variant_data(self):
        from shop.models import Product, ProductVariant

        approved = Product.objects.create(
            slug="approved-fixture",
            name="Approved test product",
            category="test-category",
            description="Synthetic test fixture",
            specifications={"size": "fixture"},
            image_url="/static/fixture.webp",
            is_active=True,
            is_approved=True,
        )
        first_variant = ProductVariant.objects.create(
            product=approved,
            sku="FIXTURE-001",
            label="Small",
            attributes={"size": "small"},
            price_amount=Decimal("125.00"),
            currency_code="TEST",
            stock_on_hand=7,
            is_active=True,
        )
        second_variant = ProductVariant.objects.create(
            product=approved,
            sku="FIXTURE-005",
            price_amount=None,
            currency_code="",
            stock_on_hand=0,
            is_active=True,
        )
        unapproved = Product.objects.create(
            slug="unapproved-fixture", name="Must stay hidden", is_active=True, is_approved=False
        )
        ProductVariant.objects.create(product=unapproved, sku="FIXTURE-002", is_active=True, stock_on_hand=4)
        inactive = Product.objects.create(
            slug="inactive-fixture", name="Must stay hidden too", is_active=False, is_approved=True
        )
        ProductVariant.objects.create(product=inactive, sku="FIXTURE-003", is_active=True, stock_on_hand=4)
        no_active_variant = Product.objects.create(
            slug="no-active-variant", name="No sellable variant", is_active=True, is_approved=True
        )
        ProductVariant.objects.create(product=no_active_variant, sku="FIXTURE-004", is_active=False, stock_on_hand=4)

        response = self.client.get("/api/products")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "results": [
                    {
                        "id": "approved-fixture",
                        "name": "Approved test product",
                        "category": "test-category",
                        "description": "Synthetic test fixture",
                        "specifications": {"size": "fixture"},
                        "image_url": "/static/fixture.webp",
                        "variants": [
                            {
                                "id": first_variant.pk,
                                "sku": "FIXTURE-001",
                                "label": "Small",
                                "attributes": {"size": "small"},
                                "price_amount": "125.00",
                                "currency_code": "TEST",
                                "is_available": True,
                            },
                            {
                                "id": second_variant.pk,
                                "sku": "FIXTURE-005",
                                "label": "",
                                "attributes": {},
                                "price_amount": None,
                                "currency_code": None,
                                "is_available": False,
                            }
                        ],
                    }
                ]
            },
        )
        self.assertNotIn("stock_on_hand", response.json()["results"][0]["variants"][0])

    def test_public_catalog_rejects_browser_writes(self):
        response = self.client.post("/api/products", data='{"price_amount":"1.00"}', content_type="application/json")

        self.assertEqual(response.status_code, 405)
