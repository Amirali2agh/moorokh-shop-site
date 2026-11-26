# Binux Shop Demo

Persian RTL product-browse demo. The current `public/` page is static: favorites and the sample selection list stay in the browser; it does not collect customer data, submit real orders, or process payments.

The displayed 14-product catalog uses brochure-derived names, photos, and marketing claims. The claims have not been independently verified, and the brochure contained no prices. These listings remain demo-only and are not approved for the backend catalog; approval of real store identity, product data, prices, and selling policies is tracked in issue #6. The original brochure is not in the repository; asset provenance is recorded in `ASSETS.md`.

A backend foundation now exists under `backend/` (Django 5.2.19 with PostgreSQL 18.7 as the database target). It has no seeded products and is not connected to the public page or deployed. The static page remains the only live storefront until the follow-up integration and production-release issues are completed.
