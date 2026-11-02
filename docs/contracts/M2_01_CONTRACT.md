# M2-01 V0.2 Contract / Known limits
- PostgreSQL schema + SQL seed are supplied; API still reads deterministic JSON fixture, not PostgreSQL. DB integration is pending.
- ERP owns orders/BOM/supply; WMS owns inventory; MES owns production order state. Mock endpoints have deliberately different source field names. These are contract simulations, not separate deployed services.
- Shared inventory is netted once per material and chronological day, and planned MAKE quantities explode at release date. The second order shares inventory and receipts; late receipts remain for later demand.
- Finished product is MTO, so final assembly is not netted against finished-goods inventory. This is an explicit V1 assumption.
- Order priorities are stable for source listing, but order-specific material pegging/allocation is not implemented. Aggregate per-day netting cannot claim order-specific allocation fairness.
- Same-day supply is assumed usable. No work calendars, production capacity, quality holds, real supplier confirmations, reservations per order, or distributed transactions.
- The plan is not persisted and endpoints have no authentication yet; do not expose to public networks.
- For database initialization: `docker compose up -d postgres`; `docker compose down -v` resets all demo data.
