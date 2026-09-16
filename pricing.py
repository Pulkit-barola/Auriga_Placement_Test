"""Pricing rules for the multiplex counter.

All money values are represented as Decimal rupees and rounded only at the
currency boundary, using Indian-style half-up rounding.
"""
from decimal import Decimal, ROUND_HALF_UP
import csv
import io
import re
from typing import Mapping

MONEY = Decimal("0.01")

CONFIG = {
    "cinema": "Auriga Multiplex",
    "show": "Friday Night at the Multiplex",
    "date": "Friday, 16 October 2026",
    "showtime": "9:30 PM",
    "tiers": {
        "Silver": {"price": Decimal("180.00"), "available": 80},
        "Gold": {"price": Decimal("260.00"), "available": 60},
        "Recliner": {"price": Decimal("420.00"), "available": 24},
    },
    "festival_discount": Decimal("100.00"),
    "member_discount_rate": Decimal("10"),
    "member_discount_cap": Decimal("200.00"),
    "convenience_fee": Decimal("25.00"),
    "gst_rate": Decimal("18"),
}

PRICE_IMPORT_REPORT = {
    "status": "Built-in price list",
    "imported": [],
    "deduplicated": [],
    "rejected": [],
}

SEAT_PREFIXES = {"Silver": "S", "Gold": "G", "Recliner": "R"}
SEATS = {
    tier_name: [
        {"id": f"{SEAT_PREFIXES[tier_name]}{seat_number:02d}", "booked": False}
        for seat_number in range(1, details["available"] + 1)
    ]
    for tier_name, details in CONFIG["tiers"].items()
}


def money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def _clean_price(value: object) -> Decimal:
    if value is None or not str(value).strip():
        raise ValueError("blank price")
    cleaned = re.sub(r"(?:INR|Rs\.?|₹|,|\s)", "", str(value), flags=re.IGNORECASE)
    try:
        price = Decimal(cleaned)
    except Exception as exc:
        raise ValueError("invalid price format") from exc
    if price < 0:
        raise ValueError("negative price")
    if price == 0:
        raise ValueError("zero price")
    return money(price)


def import_price_list(raw_text: str) -> dict:
    """Import messy tier,price CSV text and apply a clean normalized list."""
    aliases = {name.casefold(): name for name in CONFIG["tiers"]}
    rows = list(csv.reader(io.StringIO(raw_text or "")))
    report = {"status": "Imported", "imported": [], "deduplicated": [], "rejected": []}
    cleaned = {}
    for line_number, row in enumerate(rows, 1):
        if not row or not any(cell.strip() for cell in row):
            continue
        if line_number == 1 and row[0].strip().casefold() in {"tier", "seat class", "class", "name"}:
            continue
        if len(row) < 2:
            report["rejected"].append({"line": line_number, "value": ",".join(row), "reason": "expected class and price"})
            continue
        raw_name, raw_value = row[0].strip(), ",".join(row[1:]).strip()
        tier_name = aliases.get(raw_name.casefold())
        if not tier_name:
            report["rejected"].append({"line": line_number, "value": raw_name, "reason": "unknown seat class"})
            continue
        try:
            price = _clean_price(raw_value)
        except ValueError as error:
            report["rejected"].append({"line": line_number, "value": f"{raw_name}: {raw_value}", "reason": str(error)})
            continue
        item = {"class": tier_name, "price": str(price), "line": line_number}
        if tier_name in cleaned:
            report["deduplicated"].append({"line": line_number, "class": tier_name, "kept": cleaned[tier_name]["price"], "ignored": str(price)})
            continue
        cleaned[tier_name] = item
        report["imported"].append(item)

    for tier_name, item in cleaned.items():
        CONFIG["tiers"][tier_name]["price"] = Decimal(item["price"])
    report["cleaned_prices"] = {name: str(CONFIG["tiers"][name]["price"]) for name in CONFIG["tiers"]}
    global PRICE_IMPORT_REPORT
    PRICE_IMPORT_REPORT = report
    return report


def price_import_report() -> dict:
    return PRICE_IMPORT_REPORT


def load_persistent_state(booked_seat_ids: set[str], imported_report: dict | None = None) -> None:
    """Restore seats and the last accepted prices when the server starts."""
    for tier_seats in SEATS.values():
        for seat in tier_seats:
            seat["booked"] = seat["id"] in booked_seat_ids
    if imported_report and imported_report.get("cleaned_prices"):
        for tier_name, price in imported_report["cleaned_prices"].items():
            if tier_name in CONFIG["tiers"]:
                CONFIG["tiers"][tier_name]["price"] = Decimal(price)


def display_money(value: Decimal) -> str:
    return f"₹{money(value):,.2f}"


def _quantity(value: object, name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{name} must be a whole number")
    try:
        quantity = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a whole number") from exc
    if quantity < 0 or str(value).strip() != str(quantity):
        raise ValueError(f"{name} must be a whole number of 0 or more")
    return quantity


def _seat_selection(seats: object) -> tuple[dict[str, int], list[str]]:
    if not isinstance(seats, list) or not seats:
        raise ValueError("Select at least one seat")
    selected = []
    quantities = {tier_name: 0 for tier_name in CONFIG["tiers"]}
    seen = set()
    for seat_id in seats:
        if not isinstance(seat_id, str) or seat_id in seen:
            raise ValueError("Seat selection contains a duplicate or invalid seat")
        seen.add(seat_id)
        matching_tier = next(
            (tier_name for tier_name, tier_seats in SEATS.items()
             if any(seat["id"] == seat_id for seat in tier_seats)),
            None,
        )
        if matching_tier is None:
            raise ValueError(f"Seat {seat_id} does not exist")
        seat = next(seat for seat in SEATS[matching_tier] if seat["id"] == seat_id)
        if seat["booked"]:
            raise ValueError(f"Seat {seat_id} is no longer available")
        quantities[matching_tier] += 1
        selected.append(seat_id)
    return quantities, sorted(selected)


def calculate_quote(tickets: Mapping[str, object] | None = None, member: bool = False, seats: object = None) -> dict:
    """Validate a cart and return a complete, auditable quote."""
    quantities = {}
    selected_seats = []
    if seats is not None:
        quantities, selected_seats = _seat_selection(seats)
    elif tickets is None:
        raise ValueError("Select at least one seat")
    total_tickets = 0
    subtotal = Decimal("0")
    ticket_lines = []

    for tier_name, tier in CONFIG["tiers"].items():
        quantity = quantities[tier_name] if seats is not None else _quantity(
            tickets.get(tier_name, 0), f"{tier_name} tickets"
        )
        available = sum(not seat["booked"] for seat in SEATS[tier_name])
        if quantity > available:
            raise ValueError(
                f"Only {available} {tier_name} seats remain for this show"
            )
        quantities[tier_name] = quantity
        line_total = money(tier["price"] * quantity)
        subtotal += line_total
        total_tickets += quantity
        if quantity:
            ticket_lines.append({
                "label": f"{tier_name} × {quantity}",
                "unit_price": str(money(tier["price"])),
                "amount": str(line_total),
            })

    if total_tickets == 0:
        raise ValueError("Select at least one ticket")

    subtotal = money(subtotal)
    festival_discount = min(CONFIG["festival_discount"], subtotal)
    member_base = money(subtotal - festival_discount)
    member_discount = Decimal("0")
    if member:
        calculated_member_discount = money(
            member_base * CONFIG["member_discount_rate"] / Decimal("100")
        )
        member_discount = min(calculated_member_discount, CONFIG["member_discount_cap"])
    discounted_tickets = money(member_base - member_discount)
    convenience_fee = money(CONFIG["convenience_fee"] * total_tickets)
    taxable_amount = money(discounted_tickets + convenience_fee)
    gst = money(taxable_amount * CONFIG["gst_rate"] / Decimal("100"))
    total = money(taxable_amount + gst)

    if not selected_seats:
        for tier_name, quantity in quantities.items():
            available_seats = [seat["id"] for seat in SEATS[tier_name] if not seat["booked"]]
            selected_seats.extend(available_seats[:quantity])

    return {
        "tickets": quantities,
        "seats": selected_seats,
        "ticket_lines": ticket_lines,
        "total_tickets": total_tickets,
        "subtotal": str(subtotal),
        "festival_discount": str(money(festival_discount)),
        "member_discount": str(money(member_discount)),
        "discounted_tickets": str(discounted_tickets),
        "convenience_fee": str(convenience_fee),
        "taxable_amount": str(taxable_amount),
        "gst": str(gst),
        "gst_rate": str(CONFIG["gst_rate"]),
        "total": str(total),
        "member": bool(member),
    }


def public_config() -> dict:
    return {
        "cinema": CONFIG["cinema"],
        "show": CONFIG["show"],
        "date": CONFIG["date"],
        "showtime": CONFIG["showtime"],
        "tiers": {
            name: {
                "price": str(details["price"]),
                "available": sum(not seat["booked"] for seat in SEATS[name]),
                "total": len(SEATS[name]),
            }
            for name, details in CONFIG["tiers"].items()
        },
        "seats": [
            {
                "id": seat["id"],
                "tier": tier_name,
                "available": not seat["booked"],
            }
            for tier_name, tier_seats in SEATS.items()
            for seat in tier_seats
        ],
        "festival_discount": str(CONFIG["festival_discount"]),
        "member_discount_rate": str(CONFIG["member_discount_rate"]),
        "member_discount_cap": str(CONFIG["member_discount_cap"]),
        "convenience_fee": str(CONFIG["convenience_fee"]),
        "gst_rate": str(CONFIG["gst_rate"]),
    }


def reserve(tickets: Mapping[str, object] | None = None, member: bool = False, seats: object = None) -> dict:
    """Atomically validate and reserve the requested seats in this process."""
    quote = calculate_quote(tickets, member, seats)
    for seat_id in quote["seats"]:
        for tier_seats in SEATS.values():
            for seat in tier_seats:
                if seat["id"] == seat_id:
                    seat["booked"] = True
    return quote
