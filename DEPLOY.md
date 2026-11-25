# Deployment

Primary public URL: `https://shopdemo.binux.tech/`. Existing wildcard DNS points to `iran-entry-new` (130.185.73.91); no DNS change. Native `caddy.service` serves only static `public/` files from `/opt/parallax/www/binux-shop-demo`, no app unit or port. Site block: `deploy/shopdemo.binux.tech.Caddyfile`. Pre-addition config backup: `/etc/caddy/Caddyfile.pre-shopdemo-1795258128`. Roll back by removing just this block from the current config, validating and reloading Caddy. Deployment verified with matching file checksums, HTTPS 200 from FI and the Iranian server, and desktop/mobile Playwright checkout. Apex returned 200 after reload.

## Previous preview (still active)

Public HTTPS: `https://binux-shop-demo.speed-service.shop/` (FI host). Caddy serves the static copy at `/config/binux-shop-demo` in `marzban-caddy-1`, backed by the `marzban_caddy_config` named volume. No service port or backend is required for the public site. `deploy/demo.Caddyfile` is the isolated site block. Only GET/HEAD for the explicitly allowed public paths work; no indexing. Local preview: see README.

On 2026-11-21 the host Caddyfile and the container's mounted file were different inodes. The block was persisted in the host Caddyfile, and the existing mounted baseline plus demo block was validated and reloaded via stdin to avoid changing unrelated live routes. Backups: host `/opt/marzban/Caddyfile.pre-binux-demo-1795257198`, mounted baseline saved as `/config/binux-demo-active-base.caddy` (outside the web root). To remove the demo, remove only its block from the current host config and reload a validated live config without the block; don't restore the old whole configuration if other sites have changed since launch.

Verified: HTTPS 200, HTML matches source, assets 200, private docs and POST return 404. Playwright checkout passed on desktop and mobile against the public URL. Access from inside Iran was not independently verified.
