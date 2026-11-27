import json

from django.test import Client, TestCase

from shop.models import Product, ProductVariant


class ServerCartAPITests(TestCase):
    def setUp(self):
        product = Product.objects.create(
            slug="cart-fixture",
            name="Synthetic cart product",
            is_active=True,
            is_approved=True,
        )
        self.variant = ProductVariant.objects.create(
            product=product,
            sku="CART-FIXTURE-1",
            stock_on_hand=4,
            is_active=True,
        )

    def set_quantity(self, client, variant_id, quantity):
        return client.put(
            f"/api/cart/items/{variant_id}",
            data=json.dumps({"quantity": quantity}),
            content_type="application/json",
        )

    def test_new_cart_is_empty_and_does_not_create_a_session(self):
        response = self.client.get("/api/cart")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"items": []})
        self.assertNotIn("sessionid", self.client.cookies)

    def test_cart_survives_a_new_client_reusing_the_opaque_session_cookie(self):
        response = self.set_quantity(self.client, self.variant.pk, 2)

        self.assertEqual(response.status_code, 200)
        self.assertIn("sessionid", self.client.cookies)

        restarted_client = Client()
        restarted_client.cookies["sessionid"] = self.client.cookies["sessionid"].value
        restored = restarted_client.get("/api/cart")

        self.assertEqual(
            restored.json(),
            {"items": [{"variant_id": self.variant.pk, "quantity": 2}]},
        )
        self.assertEqual(Client().get("/api/cart").json(), {"items": []})

    def test_put_sets_quantity_and_returns_only_variant_id_and_quantity(self):
        first = self.set_quantity(self.client, self.variant.pk, 2)
        second = self.set_quantity(self.client, self.variant.pk, 3)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json(), {"variant_id": self.variant.pk, "quantity": 3})
        self.assertEqual(
            self.client.get("/api/cart").json(),
            {"items": [{"variant_id": self.variant.pk, "quantity": 3}]},
        )
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_on_hand, 4)

    def test_cart_responses_are_not_shared_cacheable(self):
        listed = self.client.get("/api/cart")
        updated = self.set_quantity(self.client, self.variant.pk, 1)

        self.assertIn("no-store", listed["Cache-Control"])
        self.assertIn("no-store", updated["Cache-Control"])

    def test_delete_removes_an_item_from_the_current_session_cart(self):
        self.assertEqual(self.set_quantity(self.client, self.variant.pk, 2).status_code, 200)

        response = self.client.delete(f"/api/cart/items/{self.variant.pk}")

        self.assertEqual(response.status_code, 204)
        self.assertEqual(self.client.get("/api/cart").json(), {"items": []})

    def test_nonpositive_noninteger_and_malformed_quantities_are_rejected(self):
        for quantity in (0, -1, "2", 1.5, True, None, 2**63):
            with self.subTest(quantity=quantity):
                response = self.set_quantity(self.client, self.variant.pk, quantity)
                self.assertEqual(response.status_code, 400)

        with_extra_field = self.client.put(
            f"/api/cart/items/{self.variant.pk}",
            data=json.dumps({"quantity": 1, "price_amount": "0.01"}),
            content_type="application/json",
        )
        self.assertEqual(with_extra_field.status_code, 400)

        malformed = self.client.put(
            f"/api/cart/items/{self.variant.pk}",
            data="{not-json",
            content_type="application/json",
        )
        self.assertEqual(malformed.status_code, 400)
        self.assertEqual(self.client.get("/api/cart").json(), {"items": []})

    def test_unknown_or_unavailable_variants_cannot_be_added(self):
        unavailable_product = Product.objects.create(
            slug="unapproved-cart-fixture",
            name="Unapproved synthetic product",
            is_active=True,
            is_approved=False,
        )
        unavailable_variant = ProductVariant.objects.create(
            product=unavailable_product,
            sku="CART-FIXTURE-2",
            stock_on_hand=4,
            is_active=True,
        )
        out_of_stock_variant = ProductVariant.objects.create(
            product=self.variant.product,
            sku="CART-FIXTURE-3",
            stock_on_hand=0,
            is_active=True,
        )
        inactive_variant = ProductVariant.objects.create(
            product=self.variant.product,
            sku="CART-FIXTURE-4",
            stock_on_hand=4,
            is_active=False,
        )
        inactive_product = Product.objects.create(
            slug="inactive-cart-fixture",
            name="Inactive synthetic product",
            is_active=False,
            is_approved=True,
        )
        inactive_product_variant = ProductVariant.objects.create(
            product=inactive_product,
            sku="CART-FIXTURE-5",
            stock_on_hand=4,
            is_active=True,
        )

        for variant_id in (
            999999,
            unavailable_variant.pk,
            out_of_stock_variant.pk,
            inactive_variant.pk,
            inactive_product_variant.pk,
        ):
            with self.subTest(variant_id=variant_id):
                response = self.set_quantity(self.client, variant_id, 1)
                self.assertEqual(response.status_code, 404)

        self.assertEqual(self.client.get("/api/cart").json(), {"items": []})

    def test_mutating_cart_requires_csrf_protection(self):
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.get("/api/cart")

        rejected = self.set_quantity(csrf_client, self.variant.pk, 1)

        self.assertEqual(rejected.status_code, 403)
        csrf_cookie = csrf_client.cookies.get("csrftoken")
        self.assertIsNotNone(csrf_cookie)
        accepted = csrf_client.put(
            f"/api/cart/items/{self.variant.pk}",
            data=json.dumps({"quantity": 1}),
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_cookie.value,
        )
        self.assertEqual(accepted.status_code, 200)
