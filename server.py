"""Zero-dependency web server for the multiplex counter."""
import json
import os
import secrets
from urllib.parse import quote
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from database import booked_seats, init_db, latest_price_report, recent_bookings, save_booking, save_price_report
from pricing import calculate_quote, import_price_list, load_persistent_state, price_import_report, public_config, reserve

ROOT = Path(__file__).parent


def load_local_env():
    """Load simple KEY=value settings without adding a dependency."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            os.environ.setdefault("TMDB_API_KEY", line.strip('"').strip("'"))
            continue
        name, value = line.split("=", 1)
        os.environ.setdefault(name.strip(), value.strip().strip('"').strip("'"))


load_local_env()
init_db()
load_persistent_state(booked_seats(), latest_price_report())


def movie_catalog():
    """Return optional live TMDB data with a reliable cinema fallback."""
    fallback = [
        {"id": "auriga-friday", "title": "Friday Night at the Multiplex", "genre": "Drama", "duration": "2h 18m", "rating": "U/A", "showtime": "9:30 PM", "screen": "04", "poster": "art-midnight", "live": False},
        {"id": "auriga-comet", "title": "The Last Comet", "genre": "Sci-fi", "duration": "2h 04m", "rating": "U/A", "showtime": "7:15 PM", "screen": "02", "poster": "art-comet", "live": False},
        {"id": "auriga-moons", "title": "Paper Moons", "genre": "Romance", "duration": "1h 52m", "rating": "U", "showtime": "8:00 PM", "screen": "01", "poster": "art-paper", "live": False},
    ]
    read_token = os.getenv("TMDB_API_KEY")
    v3_key = os.getenv("TMDB_V3_API_KEY")
    if not read_token and not v3_key:
        return {"source": "Auriga schedule", "updated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"), "movies": fallback}
    try:
        import urllib.request
        endpoint = "https://api.themoviedb.org/3/movie/now_playing?language=en-IN&region=IN&page=1"
        headers = {"Accept": "application/json"}
        if v3_key:
            endpoint = f"{endpoint}&api_key={quote(v3_key)}"
        elif read_token:
            headers["Authorization"] = f"Bearer {read_token}"
        request = urllib.request.Request(endpoint, headers=headers)
        with urllib.request.urlopen(request, timeout=4) as response:
            live_movies = json.loads(response.read()).get("results", [])[:6]
        movies = [{"id": item["id"], "title": item["title"], "genre": "Now playing", "duration": "Feature film", "rating": "U/A", "showtime": "Today", "screen": "Auriga", "poster": f"https://image.tmdb.org/t/p/w500{item['poster_path']}" if item.get("poster_path") else "art-midnight", "overview": item.get("overview", ""), "live": True} for item in live_movies]
        return {"source": "TMDB live catalogue", "updated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"), "movies": movies or fallback}
    except Exception:
        return {"source": "Auriga schedule", "updated_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"), "movies": fallback}


class CounterHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, content_type):
        try:
            body = path.read_bytes()
        except FileNotFoundError:
            self._send_json({"error": "Not found"}, 404)
            return
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/config":
            self._send_json(public_config())
        elif path == "/api/prices/import":
            self._send_json(price_import_report())
        elif path == "/api/bookings":
            self._send_json({"bookings": recent_bookings()})
        elif path == "/api/movies":
            self._send_json(movie_catalog())
        elif path in ("/", "/index.html"):
            self._send_file(ROOT / "static" / "index.html", "text/html; charset=utf-8")
        elif path == "/static/app.js":
            self._send_file(ROOT / "static" / "app.js", "text/javascript; charset=utf-8")
        elif path == "/static/styles.css":
            self._send_file(ROOT / "static" / "styles.css", "text/css; charset=utf-8")
        else:
            self._send_json({"error": "Not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ("/api/quote", "/api/book", "/api/prices/import"):
            self._send_json({"error": "Not found"}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
            if path == "/api/prices/import":
                raw_text = payload.get("content", "")
                if not isinstance(raw_text, str) or len(raw_text) > 100_000:
                    raise ValueError("Price list must be text under 100 KB")
                report = import_price_list(raw_text)
                save_price_report(report)
                self._send_json(report)
                return
            tickets = payload.get("tickets")
            seats = payload.get("seats")
            member = bool(payload.get("member", False))
            quote = reserve(tickets, member, seats) if path == "/api/book" else calculate_quote(tickets, member, seats)
            if path == "/api/book":
                quote["booking_id"] = f"AUR-{secrets.token_hex(3).upper()}"
                quote["customer"] = {
                    "name": str(payload.get("customer", {}).get("name", "Guest")).strip() or "Guest",
                    "phone": str(payload.get("customer", {}).get("phone", "")).strip(),
                }
                save_booking(quote["booking_id"], quote["customer"], quote)
            self._send_json(quote, 201 if path == "/api/book" else 200)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self._send_json({"error": str(exc)}, 400)

    def log_message(self, format, *args):
        print(f"{self.address_string()} - {format % args}")


def main():
    port = 8000
    print(f"Auriga Multiplex counter running at http://localhost:{port}")
    ThreadingHTTPServer(("0.0.0.0", port), CounterHandler).serve_forever()


if __name__ == "__main__":
    main()
