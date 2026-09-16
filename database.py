"""Small SQLite persistence layer for the cinema counter."""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "auriga.db"


def connection():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with connection() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS bookings (
            booking_id TEXT PRIMARY KEY,
            customer_name TEXT NOT NULL,
            customer_phone TEXT,
            seats_json TEXT NOT NULL,
            total TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS booked_seats (
            seat_id TEXT PRIMARY KEY,
            booking_id TEXT NOT NULL REFERENCES bookings(booking_id)
        );
        CREATE TABLE IF NOT EXISTS price_imports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """)


def booked_seats():
    with connection() as db:
        return {row["seat_id"] for row in db.execute("SELECT seat_id FROM booked_seats")}


def latest_price_report():
    with connection() as db:
        row = db.execute("SELECT report_json FROM price_imports ORDER BY id DESC LIMIT 1").fetchone()
    return json.loads(row["report_json"]) if row else None


def save_price_report(report):
    with connection() as db:
        db.execute(
            "INSERT INTO price_imports(report_json, created_at) VALUES (?, ?)",
            (json.dumps(report), datetime.now(timezone.utc).isoformat()),
        )


def save_booking(booking_id, customer, quote):
    with connection() as db:
        db.execute(
            "INSERT INTO bookings VALUES (?, ?, ?, ?, ?, ?)",
            (booking_id, customer["name"], customer["phone"], json.dumps(quote["seats"]), quote["total"], datetime.now(timezone.utc).isoformat()),
        )
        db.executemany(
            "INSERT INTO booked_seats(seat_id, booking_id) VALUES (?, ?)",
            [(seat_id, booking_id) for seat_id in quote["seats"]],
        )


def recent_bookings(limit=20):
    with connection() as db:
        rows = db.execute("SELECT * FROM bookings ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(row) | {"seats": json.loads(row["seats_json"])} for row in rows]
