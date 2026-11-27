from django.db import migrations


POSTGRESQL_UP_SQL = (
    """CREATE FUNCTION shop_reject_immutable_catalog_mutation()
       RETURNS trigger AS $$
       BEGIN
           RAISE EXCEPTION '% rows are immutable', TG_TABLE_NAME
               USING ERRCODE = 'check_violation';
           RETURN OLD;
       END;
       $$ LANGUAGE plpgsql""",
    """CREATE TRIGGER shop_product_no_delete
       BEFORE DELETE ON shop_product
       FOR EACH ROW EXECUTE FUNCTION shop_reject_immutable_catalog_mutation()""",
    """CREATE TRIGGER shop_productvariant_no_delete
       BEFORE DELETE ON shop_productvariant
       FOR EACH ROW EXECUTE FUNCTION shop_reject_immutable_catalog_mutation()""",
    """CREATE TRIGGER shop_catalogaudit_immutable
       BEFORE UPDATE OR DELETE ON shop_catalogaudit
       FOR EACH ROW EXECUTE FUNCTION shop_reject_immutable_catalog_mutation()""",
    """CREATE TRIGGER shop_stockadjustment_immutable
       BEFORE UPDATE OR DELETE ON shop_stockadjustment
       FOR EACH ROW EXECUTE FUNCTION shop_reject_immutable_catalog_mutation()""",
)
POSTGRESQL_REVERSE_SQL = (
    "DROP TRIGGER IF EXISTS shop_product_no_delete ON shop_product",
    "DROP TRIGGER IF EXISTS shop_productvariant_no_delete ON shop_productvariant",
    "DROP TRIGGER IF EXISTS shop_catalogaudit_immutable ON shop_catalogaudit",
    "DROP TRIGGER IF EXISTS shop_stockadjustment_immutable ON shop_stockadjustment",
    "DROP FUNCTION IF EXISTS shop_reject_immutable_catalog_mutation()",
)


class PostgreSQLRunSQL(migrations.RunSQL):
    """Apply PostgreSQL trigger DDL while keeping SQLite available for local development."""

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        vendor = schema_editor.connection.vendor
        if vendor == "postgresql":
            return super().database_forwards(app_label, schema_editor, from_state, to_state)
        if vendor != "sqlite":
            raise RuntimeError(f"Database guards are not implemented for {vendor}.")

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        vendor = schema_editor.connection.vendor
        if vendor == "postgresql":
            return super().database_backwards(app_label, schema_editor, from_state, to_state)
        if vendor != "sqlite":
            raise RuntimeError(f"Database guards are not implemented for {vendor}.")


class Migration(migrations.Migration):
    dependencies = [("shop", "0001_initial")]

    operations = [
        PostgreSQLRunSQL(POSTGRESQL_UP_SQL, reverse_sql=POSTGRESQL_REVERSE_SQL),
    ]
