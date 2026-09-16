# Reasoning

## 1. Interpreting the brief

The core risk is not the screen design; it is incorrect money at a busy counter. I treated the application as two related products:

- A customer/counter website for discovering a show, selecting exact seats, and reviewing a receipt.
- A backend pricing and inventory boundary that every browser request must use.

The implementation is configurable around cinema metadata, showtime, seat tiers, inventory, offers, fees, and tax instead of hard-coding a single calculation into the page.

## 2. Money correctness

Floating-point numbers can produce values such as `19.999999`, which is unacceptable when a customer asks for exact paisa. `pricing.py` uses `Decimal` throughout and rounds with `ROUND_HALF_UP` at defined currency boundaries. API responses return money as strings.

The calculation order is deliberately explicit:

1. Sum tier-priced tickets.
2. Apply the flat festival discount, never below zero.
3. Apply the member percentage to the post-festival amount and cap the saving.
4. Add the per-ticket convenience fee.
5. Calculate GST on the discounted ticket amount plus the fee.
6. Add GST to reach the payable total.

This order makes every receipt row explainable and keeps the taxable base visible.

## 3. Exact seats and inventory

The first version of the workflow was quantity-based, but real cinema bookings need exact seat identity. Each tier now generates seat IDs such as `S01`, `G01`, and `R01`. A quote validates seats without mutating state, which makes preview safe. A booking validates again and marks the chosen seats unavailable before returning a booking reference.

Inventory is persisted in SQLite through the `booked_seats` table. On server startup, the pricing engine restores those booked IDs, so a restart does not make sold seats bookable again.

## 4. Discounts, fees, and taxes

The rules are kept in one configuration object so a different cinema can change prices and policies without changing the algorithm. The current defaults are:

- Festival discount: `₹100.00` per booking.
- Member saving: `10%`, capped at `₹200.00`.
- Convenience fee: `₹25.00` per ticket.
- GST: `18%` of discounted tickets plus convenience fee.

Tests cover the ordinary member calculation, the member cap, zero carts, inventory limits, and exact seat-to-tier mapping.

## 5. Messy price-list twist

The importer is deliberately on the backend boundary, not just a browser formatter. It uses Python's CSV parser, matches known class names case-insensitively, and normalizes supported INR formats through `Decimal`. For values such as `GOLD,2,60.00`, the comma-separated numeric fields are joined before currency parsing.

The cleanup policy is deterministic:

- The first valid row for a known tier becomes the active price.
- Later valid rows for the same tier are de-duplicated and reported.
- Blank, zero, negative, malformed, incomplete, and unknown-class rows are rejected.
- Every rejection includes an input line and a human-readable reason.

The report is saved in SQLite and the cleaned values are applied to future quotes. This means an operator can explain both what was accepted and what was not.

## 6. Persistence choice

SQLite was chosen because it is included with Python, requires no package or service, works in Codespaces, and is appropriate for this single-counter assessment. The database contains bookings, booked seats, and price-import reports. The persistence module has a small boundary, so it can later be replaced by PostgreSQL for multiple counters or high concurrency.

## 7. Website and API boundary

The browser is a zero-dependency HTML/CSS/JavaScript client. It has Home, Movies, Offers, Price list, My bookings, and Booking views. It fetches movie data from `/api/movies`, exact inventory from `/api/config`, quotes from `/api/quote`, bookings from `/api/book`, and imports through `/api/prices/import`.

The browser never calculates the authoritative total itself. It only displays the quote returned by the Python engine. This prevents a future client or UI change from creating a second, conflicting pricing implementation.

## 8. Validation and known production improvements

The focused test suite covers the high-risk pricing and import paths, and live smoke checks cover the HTTP endpoints. The current app is intentionally portable and does not include payment processing, staff authentication, seat-hold expiry, or a production multi-process locking strategy. Before deploying to a real cinema, I would add database transactions around seat holds, authentication, payment/idempotency handling, structured logs, and a migration system.