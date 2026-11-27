from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connections
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature

from shop.models import Product, ProductVariant, StockAdjustment
from shop.services import adjust_stock


def make_operator(username="operator"):
    user = get_user_model().objects.create_user(
        username=username, password="test-only-password", is_staff=True
    )
    permission = Permission.objects.get(
        content_type__app_label="shop", codename="add_stockadjustment"
    )
    user.user_permissions.add(permission)
    return user


class StockAdjustmentServiceTests(TestCase):
    def setUp(self):
        self.operator = make_operator()
        self.viewer = get_user_model().objects.create_user(username="viewer", password="test-only-password")
        product = Product.objects.create(slug="stock-fixture", name="Synthetic stock fixture")
        self.variant = ProductVariant.objects.create(
            product=product, sku="STOCK-001", stock_on_hand=2, is_active=True
        )

    def test_authorized_adjustment_updates_stock_and_writes_actor_reason_and_result(self):
        record = adjust_stock(
            variant_id=self.variant.pk,
            delta=5,
            reason="fixture receipt",
            actor=self.operator,
        )

        self.variant.refresh_from_db()
        record.refresh_from_db()
        self.assertEqual(self.variant.stock_on_hand, 7)
        self.assertEqual(record.delta, 5)
        self.assertEqual(record.resulting_quantity, 7)
        self.assertEqual(record.reason, "fixture receipt")
        self.assertEqual(record.actor_id, self.operator.pk)

    def test_adjustment_cannot_make_stock_negative_and_failure_leaves_no_audit_record(self):
        with self.assertRaises(ValidationError):
            adjust_stock(
                variant_id=self.variant.pk,
                delta=-3,
                reason="too many units",
                actor=self.operator,
            )

        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_on_hand, 2)
        self.assertEqual(StockAdjustment.objects.count(), 0)

    def test_zero_adjustment_is_rejected(self):
        with self.assertRaises(ValidationError):
            adjust_stock(
                variant_id=self.variant.pk,
                delta=0,
                reason="no change",
                actor=self.operator,
            )
        self.assertEqual(StockAdjustment.objects.count(), 0)

    def test_actor_without_stock_permission_is_denied(self):
        with self.assertRaises(PermissionDenied):
            adjust_stock(
                variant_id=self.variant.pk,
                delta=1,
                reason="unauthorized",
                actor=self.viewer,
            )
        self.assertEqual(StockAdjustment.objects.count(), 0)

    def test_audit_record_cannot_be_edited_or_deleted(self):
        record = adjust_stock(
            variant_id=self.variant.pk,
            delta=1,
            reason="fixture receipt",
            actor=self.operator,
        )
        record.reason = "rewritten"

        with self.assertRaises(ValidationError):
            record.save()
        with self.assertRaises(ValidationError):
            record.delete()

        stored = StockAdjustment.objects.get(pk=record.pk)
        self.assertEqual(stored.reason, "fixture receipt")


@skipUnlessDBFeature("has_select_for_update")
class ConcurrentStockAdjustmentTests(TransactionTestCase):
    reset_sequences = True

    def test_two_concurrent_consumers_cannot_oversell_the_last_unit(self):
        operator = make_operator("concurrent-operator")
        product = Product.objects.create(slug="concurrent-fixture", name="Concurrent fixture")
        variant = ProductVariant.objects.create(
            product=product, sku="RACE-001", stock_on_hand=1, is_active=True
        )
        gate = Barrier(2)
        operator_id = operator.pk
        variant_id = variant.pk

        def consume_one():
            from django.db import close_old_connections

            close_old_connections()
            try:
                worker = get_user_model().objects.get(pk=operator_id)
                gate.wait(timeout=10)
                try:
                    adjust_stock(
                        variant_id=variant_id,
                        delta=-1,
                        reason="concurrent test sale",
                        actor=worker,
                    )
                    return "accepted"
                except ValidationError:
                    return "rejected"
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _index: consume_one(), range(2)))

        variant.refresh_from_db()
        self.assertCountEqual(outcomes, ["accepted", "rejected"])
        self.assertEqual(variant.stock_on_hand, 0)
        self.assertEqual(StockAdjustment.objects.filter(variant=variant).count(), 1)
