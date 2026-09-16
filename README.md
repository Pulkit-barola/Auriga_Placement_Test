# Auriga Cinema

A complete Python cinema booking application for the Round 2 multiplex pricing brief. It combines a cinema-style website with a counter-trusted pricing engine.

Customers or counter staff can:

- Browse the home page, movies, offers, and booking history views.
- Load current movies from TMDB, with a built-in fallback schedule.
- Choose exact Silver, Gold, or Recliner seats from a popup seat map.
- Enter customer details and apply member pricing.
- See a line-by-line INR receipt with exact paisa rounding.
- Confirm a booking and receive a booking reference.
- Import a messy INR price list and see accepted, duplicate, and rejected rows.

## Quick Start

Requirements: Python 3.10+; no pip packages are required.

```bash
python3 server.py
```

Open `http://localhost:8000` in the same environment. In GitHub Codespaces, open the forwarded port 8000 URL shown by VS Code. Keep the terminal running while using the app.

To stop the server, focus the server terminal and press `Ctrl+C`.

## Optional Live Movie Data

The app works without credentials using the built-in Auriga schedule. For current TMDB movies, create a local `.env` file from the template:

```bash
cp .env.example .env
```

Use either credential format:

```env
# TMDB v4 Read Access Token
TMDB_API_KEY=your_read_access_token

# Or TMDB v3 API Key
TMDB_V3_API_KEY=your_api_key
```

If both exist, the v3 API key is preferred. Never commit `.env` or paste a real token into chat. Restart the server after changing credentials. The movie API returns `TMDB live catalogue` when the live request succeeds and `Auriga schedule` when it falls back.

## Pricing Rules

The pricing engine applies rules in this order:

1. Price each selected seat at its tier price.
2. Subtract a flat `₹100.00` festival discount, limited to the ticket subtotal.
3. If the customer is a member, subtract `10%` of the post-festival ticket amount, capped at `₹200.00`.
4. Add a `₹25.00` convenience fee per ticket.
5. Calculate `18%` GST on discounted tickets plus the convenience fee.
6. Add the GST to produce the payable total.

All money uses Python `Decimal` and round-half-up to two decimal places. The API returns money as strings so the browser cannot introduce floating-point errors.

## Price-List Twist

Open **Price list** in the website. Paste rows or upload a CSV containing a seat class and price. The importer supports case differences, INR symbols, `INR`, `Rs`, spaces, and comma-formatted values.

```csv
Seat Class,Price
silver, ₹180
GOLD,2,60.00
Recliner, INR 420
Silver,
Gold,-250
VIP,900
```

The first valid occurrence of a known class is kept. Later valid occurrences are reported as de-duplicated. Blank, zero, negative, malformed, incomplete, and unknown-class rows are rejected with their line number and reason. Cleaned prices are applied to future quotes.

For the sample above the report is:

```text
Imported: 3
De-duplicated: 1
Rejected: 3
Silver: ₹180.00, Gold: ₹260.00, Recliner: ₹420.00
```

## Database

The app uses built-in SQLite. `auriga.db` is created automatically and is ignored by Git.

Tables:

- `bookings`: reference, customer, selected seats, total, and timestamp.
- `booked_seats`: one row per reserved seat, used to restore inventory after restart.
- `price_imports`: cleaned import reports and timestamps.

Inspect the database with:

```bash
sqlite3 auriga.db '.tables'
```

Recent bookings are also available through `GET /api/bookings`.

## API Examples

```bash
curl http://localhost:8000/api/config
curl http://localhost:8000/api/movies
curl http://localhost:8000/api/bookings

curl -X POST http://localhost:8000/api/quote \
	-H 'Content-Type: application/json' \
	-d '{"seats":["S01","G01"],"member":true}'

curl -X POST http://localhost:8000/api/prices/import \
	-H 'Content-Type: application/json' \
	-d '{"content":"Seat Class,Price\nsilver,180\nGold,260"}'
```

## Tests and Debugging

Run all regression tests:

```bash
python3 -m unittest -v test_pricing.py
python3 -m py_compile database.py pricing.py server.py test_pricing.py
```

Common issues:

- `Address already in use`: a server is already running on port 8000. Use that app or stop the old process before starting another.
- `localhost` not opening from Windows: use the Codespaces forwarded port URL, or create an SSH port tunnel.
- TMDB fallback schedule: check the credential type, restart the server, and inspect `/api/movies`.
- Browser showing old UI: use `Ctrl+Shift+R`.

## Project Map

- `server.py`: standard-library HTTP server, API routes, TMDB integration, and request validation.
- `database.py`: SQLite schema and persistence operations.
- `pricing.py`: Decimal pricing, seats, offers, tax, price import cleanup, and reservations.
- `static/index.html`: cinema website views and booking forms.
- `static/app.js`: navigation, live movies, seat popup, quote updates, import report, and booking UI.
- `static/styles.css`: responsive visual design and animations.
- `test_pricing.py`: pricing, inventory, seat, and messy-import regression tests.
- `REASONING.md`: design decisions and trade-offs.
- `AI_LOGS.md`: conversation log required by the placement brief.