from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import DatabaseError, transaction
from django.test import TestCase, skipUnlessDBFeature

from shop.models import CatalogAudit, Product, ProductVariant, StockAdjustment


class CatalogAuditInstanceGuardTests(TestCase):
    def test_instance_save_and_delete_are_rejected_without_changing_state(self):
        actor = get_user_model().objects.create_user(username="instance-audit-operator")
        audit = CatalogAudit.objects.create(
            object_type=CatalogAudit.ObjectType.PRODUCT,
            object_id=1,
            action=CatalogAudit.Action.CREATED,
            actor=actor,
            before_state=None,
            after_state={"name": "original"},
        )
        original_state = audit.after_state

        audit.after_state = {"name": "rewritten"}
        with self.assertRaises(ValidationError):
            audit.save()
        with self.assertRaises(ValidationError):
            audit.delete()

        audit.refresh_from_db()
        self.assertEqual(audit.after_state, original_state)
        self.assertTrue(CatalogAudit.objects.filter(pk=audit.pk).exists())


@skipUnlessDBFeature("has_select_for_update")
class DatabaseWriteGuardTests(TestCase):
    def setUp(self):
        self.actor = get_user_model().objects.create_user(username="audit-operator")
        self.product = Product.objects.create(slug="guard-fixture", name="Guard fixture")
        self.variant = ProductVariant.objects.create(product=self.product, sku="GUARD-001")
        self.catalog_audit = CatalogAudit.objects.create(
            object_type=CatalogAudit.ObjectType.PRODUCT,
            object_id=self.product.pk,
            action=CatalogAudit.Action.CREATED,
            actor=self.actor,
            before_state=None,
            after_state={"name": self.product.name},
        )
        self.stock_adjustment = StockAdjustment.objects.create(
            variant=self.variant,
            delta=1,
            resulting_quantity=1,
            reason="synthetic database-guard fixture",
            actor=self.actor,
        )

    def _assert_database_write_rejected(self, write):
        with self.assertRaises(DatabaseError):
            with transaction.atomic():
                write()

    def test_catalog_rows_cannot_be_deleted_through_queryset(self):
        empty_product = Product.objects.create(slug="guard-empty", name="No variants")
        variant_product = Product.objects.create(slug="guard-variant", name="Variant fixture")
        empty_variant = ProductVariant.objects.create(
            product=variant_product,
            sku="GUARD-EMPTY-001",
        )

        self._assert_database_write_rejected(
            lambda: Product.objects.filter(pk=empty_product.pk).delete()
        )
        self._assert_database_write_rejected(
            lambda: ProductVariant.objects.filter(pk=empty_variant.pk).delete()
        )

        self.assertTrue(Product.objects.filter(pk=empty_product.pk).exists())
        self.assertTrue(ProductVariant.objects.filter(pk=empty_variant.pk).exists())

    def test_catalog_audit_rejects_queryset_update_and_delete(self):
        original_state = self.catalog_audit.after_state

        self._assert_database_write_rejected(
            lambda: CatalogAudit.objects.filter(pk=self.catalog_audit.pk).update(
                after_state={"name": "rewritten"}
            )
        )
        self._assert_database_write_rejected(
            lambda: CatalogAudit.objects.filter(pk=self.catalog_audit.pk).delete()
        )

        self.catalog_audit.refresh_from_db()
        self.assertEqual(self.catalog_audit.after_state, original_state)
        self.assertTrue(CatalogAudit.objects.filter(pk=self.catalog_audit.pk).exists())

    def test_stock_adjustment_rejects_queryset_update_and_delete(self):
        self._assert_database_write_rejected(
            lambda: StockAdjustment.objects.filter(pk=self.stock_adjustment.pk).update(delta=5)
        )
        self._assert_database_write_rejected(
            lambda: StockAdjustment.objects.filter(pk=self.stock_adjustment.pk).delete()
        )

        self.stock_adjustment.refresh_from_db()
        self.assertEqual(self.stock_adjustment.delta, 1)
        self.assertTrue(StockAdjustment.objects.filter(pk=self.stock_adjustment.pk).exists())
