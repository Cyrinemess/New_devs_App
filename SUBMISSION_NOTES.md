# Revenue Dashboard Debugging Notes

## Bugs found and fixed

1. **Cross-tenant cache leakage** — revenue was cached only by `property_id`, even
   though property IDs are reused by different tenants. The cache key now includes
   both `tenant_id` and `property_id`, and cached payloads are tenant-validated.
2. **Incorrect monthly timezone boundaries** — calendar months were constructed as
   naive datetimes instead of in the property's timezone. Local month boundaries are
   now converted to UTC before querying reservations.
3. **Financial precision loss** — exact `NUMERIC`/`Decimal` values were converted to
   binary floats at the API boundary. Totals are now rounded with `ROUND_HALF_UP` and
   returned as two-decimal strings.
4. **Unsafe fallback data** — a database failure returned property-only mock revenue,
   which could expose another tenant's figures. Revenue now fails closed with a 503.
5. **Broken database pool configuration** — the pool ignored `DATABASE_URL`, used
   undefined settings, and exposed an async session factory incorrectly. It now uses
   the configured async Postgres URL and an idempotent shared pool.
6. **Cross-tenant property names in the dashboard** — the selector listed every
   seeded property. It now shows only the signed-in tenant's properties.

## Verification

- Backend regression tests cover tenant-scoped caching, rejection of mismatched cache
  payloads, DST-aware March boundaries for Paris, and exact currency rounding.
- The production frontend build completes successfully.

## Loom outline (5–10 minutes)

1. Log in as Sunset Properties and Ocean Rentals and show each tenant's property list.
2. Show the old cache key (`revenue:{property_id}`) and explain why shared `prop-001`
   caused leakage; then show the tenant-scoped key and regression test.
3. Explain why the Paris reservation at `2024-02-29 23:30 UTC` belongs to March
   locally, then show the UTC boundary test.
4. Show the Decimal rounding/API serialization fix and the failing-closed behavior.
5. Run the backend tests and frontend build to demonstrate the fixes.
