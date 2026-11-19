"""Boundary and class-rate tests for cancellation refund calculations."""
import unittest
from decimal import Decimal

from backend.app.booking_refunds import calculate_cancellation_refund


class CancellationRefundPolicyTests(unittest.TestCase):
    def test_flat_charge_more_than_48_hours_before_departure(self):
        result = calculate_cancellation_refund("1000.00", "SL", 72)
        self.assertEqual(result["cancellation_charge"], Decimal("120.00"))
        self.assertEqual(result["refund_amount"], Decimal("880.00"))
        self.assertEqual(result["policy_band"], "FLAT_OVER_48_HOURS")

    def test_25_percent_charge_between_12_and_48_hours(self):
        result = calculate_cancellation_refund("1000.00", "SL", 24)
        self.assertEqual(result["cancellation_charge"], Decimal("250.00"))
        self.assertEqual(result["refund_amount"], Decimal("750.00"))

    def test_exactly_48_hours_uses_the_percentage_band(self):
        result = calculate_cancellation_refund("1000.00", "SL", 48)
        self.assertEqual(result["cancellation_charge"], Decimal("250.00"))
        self.assertEqual(result["policy_band"], "25_PERCENT_12_TO_48_HOURS")

    def test_50_percent_charge_between_4_and_12_hours(self):
        result = calculate_cancellation_refund("1000.00", "SL", 6)
        self.assertEqual(result["cancellation_charge"], Decimal("500.00"))
        self.assertEqual(result["refund_amount"], Decimal("500.00"))

    def test_flat_minimum_and_ac_gst_are_applied(self):
        result = calculate_cancellation_refund("1000.00", "3A", 72)
        self.assertEqual(result["cancellation_charge"], Decimal("189.00"))
        self.assertEqual(result["refund_amount"], Decimal("811.00"))

    def test_no_refund_within_four_hours(self):
        result = calculate_cancellation_refund("1000.00", "SL", 3.99)
        self.assertEqual(result["cancellation_charge"], Decimal("1000.00"))
        self.assertEqual(result["refund_amount"], Decimal("0.00"))

    def test_charge_never_exceeds_fare(self):
        result = calculate_cancellation_refund("50.00", "1A", 72)
        self.assertEqual(result["cancellation_charge"], Decimal("50.00"))
        self.assertEqual(result["refund_amount"], Decimal("0.00"))

    def test_unknown_class_is_rejected(self):
        with self.assertRaises(ValueError):
            calculate_cancellation_refund("1000", "UNKNOWN", 72)


if __name__ == "__main__":
    unittest.main()
