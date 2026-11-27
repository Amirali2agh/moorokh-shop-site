from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase

from shop.models import CatalogAudit, Product, ProductVariant, StockAdjustment


class CatalogAdminTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser(
            username="root", email="root@example.invalid", password="test-only-password"
        )

    def test_public_users_cannot_open_catalog_management(self):
        response = self.client.get("/admin/shop/product/")

        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_staff_without_model_permission_cannot_open_catalog_management(self):
        staff = get_user_model().objects.create_user(
            username="unprivileged-staff", password="test-only-password", is_staff=True
        )
        self.client.force_login(staff)

        response = self.client.get("/admin/shop/product/")

        self.assertEqual(response.status_code, 403)

    def test_product_creation_through_admin_records_actor_and_snapshot(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            "/admin/shop/product/add/",
            {
                "slug": "admin-fixture",
                "name": "Admin test product",
                "category": "test-category",
                "description": "Synthetic test fixture",
                "specifications": '{"size":"test"}',
                "image_url": "/fixture.webp",
                "is_active": "on",
                "is_approved": "on",
                "_save": "Save",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        product = Product.objects.get(slug="admin-fixture")
        audit = CatalogAudit.objects.get(object_type=CatalogAudit.ObjectType.PRODUCT, object_id=product.pk)
        self.assertEqual(audit.actor_id, self.admin.pk)
        self.assertEqual(audit.action, CatalogAudit.Action.CREATED)
        self.assertIsNone(audit.before_state)
        self.assertEqual(audit.after_state["name"], "Admin test product")
        self.assertTrue(audit.after_state["is_approved"])

    def test_product_update_through_admin_records_before_and_after_states(self):
        product = Product.objects.create(
            slug="update-fixture", name="Before name", is_active=True, is_approved=True
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            f"/admin/shop/product/{product.pk}/change/",
            {
                "slug": product.slug,
                "name": "After name",
                "category": "test-category",
                "description": "Updated by admin test",
                "specifications": "{}",
                "image_url": "",
                "is_active": "on",
                "is_approved": "on",
                "_save": "Save",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        audit = CatalogAudit.objects.get(object_type=CatalogAudit.ObjectType.PRODUCT, object_id=product.pk)
        self.assertEqual(audit.action, CatalogAudit.Action.UPDATED)
        self.assertEqual(audit.before_state["name"], "Before name")
        self.assertEqual(audit.after_state["name"], "After name")

    def test_catalog_records_cannot_be_deleted_from_admin(self):
        product = Product.objects.create(slug="protected-fixture", name="Protected fixture")
        self.client.force_login(self.admin)

        response = self.client.get(f"/admin/shop/product/{product.pk}/delete/")

        self.assertEqual(response.status_code, 403)

    def test_catalog_audit_changelist_search_renders(self):
        CatalogAudit.objects.create(
            object_type=CatalogAudit.ObjectType.PRODUCT,
            object_id=1,
            action=CatalogAudit.Action.CREATED,
            actor=self.admin,
            before_state=None,
            after_state={"name": "Synthetic audit fixture"},
        )
        self.client.force_login(self.admin)

        response = self.client.get("/admin/shop/catalogaudit/?q=1")

        self.assertEqual(response.status_code, 200)

    def test_stock_adjustment_admin_uses_authorized_service_and_records_actor(self):
        product = Product.objects.create(slug="admin-stock", name="Stock test product")
        variant = ProductVariant.objects.create(product=product, sku="ADMIN-001", stock_on_hand=2)
        self.client.force_login(self.admin)

        response = self.client.post(
            "/admin/shop/stockadjustment/add/",
            {"variant": str(variant.pk), "delta": "-1", "reason": "counted test stock"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        variant.refresh_from_db()
        adjustment = StockAdjustment.objects.get(variant=variant)
        self.assertEqual(variant.stock_on_hand, 1)
        self.assertEqual(adjustment.delta, -1)
        self.assertEqual(adjustment.resulting_quantity, 1)
        self.assertEqual(adjustment.actor_id, self.admin.pk)

    def test_add_only_stock_operator_can_finish_adjustment_without_changelist_access(self):
        product = Product.objects.create(slug="add-only-stock", name="Add-only stock fixture")
        variant = ProductVariant.objects.create(product=product, sku="ADD-ONLY-001", stock_on_hand=0)
        operator = get_user_model().objects.create_user(
            username="add-only-stock-operator", password="test-only-password", is_staff=True
        )
        add_permission = Permission.objects.get(
            content_type__app_label="shop",
            codename="add_stockadjustment",
        )
        operator.user_permissions.add(add_permission)
        self.client.force_login(operator)

        response = self.client.post(
            "/admin/shop/stockadjustment/add/",
            {"variant": str(variant.pk), "delta": "1", "reason": "counted test stock"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        variant.refresh_from_db()
        self.assertEqual(variant.stock_on_hand, 1)
        self.assertEqual(StockAdjustment.objects.get(variant=variant).actor_id, operator.pk)

    def test_staff_without_stock_permission_cannot_use_adjustment_form(self):
        product = Product.objects.create(slug="denied-stock", name="Stock test product")
        variant = ProductVariant.objects.create(product=product, sku="DENIED-001", stock_on_hand=2)
        staff = get_user_model().objects.create_user(
            username="stock-viewer", password="test-only-password", is_staff=True
        )
        self.client.force_login(staff)

        response = self.client.get("/admin/shop/stockadjustment/add/")
        post_response = self.client.post(
            "/admin/shop/stockadjustment/add/",
            {"variant": str(variant.pk), "delta": "-1", "reason": "unauthorized attempt"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(post_response.status_code, 403)
        variant.refresh_from_db()
        self.assertEqual(variant.stock_on_hand, 2)
        self.assertFalse(StockAdjustment.objects.filter(variant=variant).exists())

    def test_stock_adjustment_admin_shows_validation_error_without_writing(self):
        product = Product.objects.create(slug="empty-stock", name="Empty stock fixture")
        variant = ProductVariant.objects.create(product=product, sku="EMPTY-001", stock_on_hand=0)
        self.client.force_login(self.admin)

        response = self.client.post(
            "/admin/shop/stockadjustment/add/",
            {"variant": str(variant.pk), "delta": "-1", "reason": "invalid test adjustment"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Stock cannot be reduced below zero.")
        self.assertEqual(response.content.count(b"<h1"), 1)
        variant.refresh_from_db()
        self.assertEqual(variant.stock_on_hand, 0)
        self.assertEqual(StockAdjustment.objects.filter(variant=variant).count(), 0)

    def test_variant_admin_cannot_change_stock_outside_adjustment_flow(self):
        product = Product.objects.create(slug="variant-admin", name="Variant admin fixture")
        variant = ProductVariant.objects.create(
            product=product, sku="VARIANT-001", stock_on_hand=2, is_active=True
        )
        self.client.force_login(self.admin)

        response = self.client.post(
            f"/admin/shop/productvariant/{variant.pk}/change/",
            {
                "product": str(product.pk),
                "sku": variant.sku,
                "label": "Updated label",
                "attributes": "{}",
                "price_amount": "12.50",
                "currency_code": "TEST",
                "stock_on_hand": "999",
                "is_active": "on",
                "_save": "Save",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        variant.refresh_from_db()
        self.assertEqual(variant.stock_on_hand, 2)
        audit = CatalogAudit.objects.get(object_type=CatalogAudit.ObjectType.VARIANT, object_id=variant.pk)
        self.assertEqual(audit.after_state["price_amount"], "12.50")
        self.assertNotIn("stock_on_hand", audit.after_state)
