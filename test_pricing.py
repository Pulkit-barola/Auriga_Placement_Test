import unittest

from pricing import calculate_quote


class PricingEngineTests(unittest.TestCase):
    def test_member_quote_has_exact_paisa_breakdown(self):
        quote = calculate_quote({"Silver": 2, "Gold": 1, "Recliner": 0}, member=True)
        self.assertEqual(quote["subtotal"], "620.00")
        self.assertEqual(quote["festival_discount"], "100.00")
        self.assertEqual(quote["member_discount"], "52.00")
        self.assertEqual(quote["convenience_fee"], "75.00")
        self.assertEqual(quote["gst"], "97.74")
        self.assertEqual(quote["total"], "640.74")

    def test_member_discount_cap_is_respected(self):
        quote = calculate_quote({"Silver": 20, "Gold": 20, "Recliner": 10}, member=True)
        self.assertEqual(quote["member_discount"], "200.00")

    def test_zero_cart_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least one"):
            calculate_quote({"Silver": 0, "Gold": 0, "Recliner": 0})

    def test_inventory_is_rejected_before_pricing(self):
        with self.assertRaisesRegex(ValueError, "Only 24 Recliner"):
            calculate_quote({"Recliner": 25})

    def test_seat_selection_drives_ticket_tiers(self):
        quote = calculate_quote(seats=["S01", "S02", "G01"], member=False)
        self.assertEqual(quote["tickets"], {"Silver": 2, "Gold": 1, "Recliner": 0})
        self.assertEqual(quote["seats"], ["G01", "S01", "S02"])

    def test_invalid_or_duplicate_seat_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate or invalid"):
            calculate_quote(seats=["S01", "S01"])
        with self.assertRaisesRegex(ValueError, "does not exist"):
            calculate_quote(seats=["X99"])

    def test_messy_price_import_reports_all_decisions(self):
        from pricing import import_price_list

        report = import_price_list(
            "Seat Class,Price\n"
            "silver, ₹180\n"
            "GOLD,2,60.00\n"
            "Recliner, INR 420\n"
            "SILVER,200\n"
            "Gold,-250\n"
            "VIP,900\n"
            "Recliner,\n"
        )
        self.assertEqual(report["cleaned_prices"], {"Silver": "180.00", "Gold": "260.00", "Recliner": "420.00"})
        self.assertEqual(len(report["imported"]), 3)
        self.assertEqual(len(report["deduplicated"]), 1)
        self.assertEqual(len(report["rejected"]), 3)

    def test_discount_cannot_make_subtotal_negative(self):
        quote = calculate_quote({"Silver": 1})
        self.assertEqual(quote["festival_discount"], "100.00")
        self.assertGreaterEqual(float(quote["discounted_tickets"]), 0)


if __name__ == "__main__":
    unittest.main()
