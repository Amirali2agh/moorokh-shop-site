# Binux Shop Demo

Persian RTL storefront source. The existing `public/` page is still a demo and is not connected to checkout or payments. This PR adds a backend foundation only; public-page integration is deferred until PR #5 is merged, as required by issue #7.

Demo-product approval and provenance are documented in [`PRODUCT.md`](PRODUCT.md). Do not copy demo listings into the backend catalog.

## Backend foundation

- Runtime: Python with Django 5.2.19; production database target: PostgreSQL 18.7.
- Local development defaults to SQLite. No product, price, stock, or demo records are seeded.
- `GET /api/products` returns only products explicitly marked both active and approved, with active variants. Prices are decimal strings or `null`; availability is a boolean, not an exposed stock count.
- Catalog changes are available only through the authenticated Django admin (`/admin/`). Product and variant create/update events store before/after snapshots with the operator. Products and variants are deactivated rather than deleted.
- Stock quantity is read-only in product/variant forms. Adjustments use a separate permission-gated admin form; each append-only record stores operator, delta, reason, and resulting quantity. PostgreSQL triggers prevent hard deletes and rewrites of catalog audit and stock-adjustment history.
- Database constraints reject negative stock, non-positive prices, and a price/currency mismatch. The public API does not accept catalog writes.
- The catalog endpoint is read-only (`POST /api/products` returns 405). There is no cart persistence, checkout, payment, customer messaging, or production deployment in this change.

## Current storefront preview

```bash
python3 -m http.server 8876 --bind 127.0.0.1 --directory public
```

Open `http://127.0.0.1:8876/`. This preview remains independent of the backend until the storefront-integration follow-up.

## Local backend startup

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver 127.0.0.1:8000
```

Open `http://127.0.0.1:8000/admin/` to manage catalog records and `http://127.0.0.1:8000/api/products` to read the public catalog. Without PostgreSQL environment variables, local development stores data in the ignored `backend/db.sqlite3` file. For PostgreSQL, set `POSTGRES_DB_HOST`, `POSTGRES_DB_NAME`, `POSTGRES_DB_USER`, `POSTGRES_DB_PASSWORD`, and optionally `POSTGRES_DB_PORT`; use a local-only password and keep environment files out of git.

Production proxy settings are not a deployment recipe. A TLS-terminating proxy must overwrite incoming `X-Forwarded-Proto` before `DJANGO_BEHIND_PROXY=1` is enabled; production deployment and proxy validation belong to issue #11.

## Tests

```bash
cd backend
python manage.py test --verbosity 2
python manage.py makemigrations --check --dry-run
```

The local SQLite run skips the row-lock concurrency and reconnect-persistence tests because SQLite does not implement `SELECT FOR UPDATE`. The pull-request workflow runs the complete suite against PostgreSQL 18.7, including those tests. Synthetic rows exist only in tests; production migrations do not seed catalog data.
