"""Tests for passenger-owned booking, payment, cancellation and refund status."""
import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from backend.app.booking_status import get_booking_status
from backend.tests.drf_client import RailwayAPIClient, set_session


class BookingStatusServiceTests(unittest.TestCase):
    def test_returns_booking_payment_cancellation_and_refund_status(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.return_value = {
            "booking_id": 12, "pnr": "ABCD23456789", "booking_status": "PARTIALLY_CANCELLED",
            "train_number_snapshot": "12627", "train_name_snapshot": "Karnataka Express",
            "boarding_station_code_snapshot": "SBC", "boarding_station_name_snapshot": "Bengaluru",
            "alighting_station_code_snapshot": "NDLS", "alighting_station_name_snapshot": "New Delhi",
            "departure_at_snapshot": datetime(2026, 11, 15, 20), "arrival_at_snapshot": datetime(2026, 11, 16, 10),
            "class_code_snapshot": "SL", "total_fare": Decimal("900.00"), "currency_code": "INR",
            "created_at": datetime(2026, 10, 30, 9), "confirmed_at": datetime(2026, 10, 30, 9, 5),
        }
        cursor.fetchall.side_effect = [
            [{"payment_status": "SUCCEEDED", "payment_method": "UPI", "amount": Decimal("900.00"),
              "currency_code": "INR", "provider_transaction_id": "TX123", "failure_code": None,
              "created_at": datetime(2026, 10, 30, 9), "completed_at": datetime(2026, 10, 30, 9, 1)}],
            [{"cancellation_status": "COMPLETED", "reason": "Passenger request",
              "requested_at": datetime(2026, 10, 31, 9), "completed_at": datetime(2026, 10, 31, 9, 1),
              "item_status": "COMPLETED", "cancellation_charge": Decimal("50.00"),
              "refund_amount": Decimal("850.00"), "refund_status": "SUCCEEDED",
              "refunded_amount": Decimal("850.00"), "refund_currency": "INR",
              "refund_created_at": datetime(2026, 10, 31, 9, 1)}],
        ]

        result = get_booking_status(7, "abcd23456789", connection_factory=lambda: connection)

        self.assertEqual(result["booking"]["booking_status"], "PARTIALLY_CANCELLED")
        self.assertEqual(result["payment_status"], "SUCCEEDED")
        self.assertEqual(result["payments"][0]["amount"], 900.0)
        self.assertEqual(result["cancellations"][0]["refund_status"], "SUCCEEDED")
        self.assertEqual(result["cancellations"][0]["refunded_amount"], 850.0)
        self.assertEqual(cursor.execute.call_args_list[0].args[1], (7, "ABCD23456789"))
        self.assertIn("WHERE user_id = %s AND pnr = %s", cursor.execute.call_args_list[0].args[0])
        connection.close.assert_called_once_with()

    def test_does_not_find_another_users_pnr(self):
        connection = MagicMock()
        connection.cursor.return_value.fetchone.return_value = None
        self.assertIsNone(get_booking_status(7, "ABCD23456789", connection_factory=lambda: connection))
        self.assertEqual(connection.cursor.return_value.execute.call_count, 1)

    def test_invalid_pnr_is_rejected_without_database_access(self):
        factory = MagicMock()
        with self.assertRaises(ValueError):
            get_booking_status(7, "bad pnr!", connection_factory=factory)
        factory.assert_not_called()


class BookingStatusEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = RailwayAPIClient()

    def test_anonymous_user_cannot_check_booking_status(self):
        response = self.client.get("/api/bookings/status?pnr=ABCD23456789")
        self.assertEqual(response.status_code, 401)

    @patch("backend.app.django_views.get_booking_status")
    def test_passenger_can_check_status_using_their_session(self, get_status):
        get_status.return_value = {"booking": {"pnr": "ABCD23456789"}, "payment_status": "NOT_STARTED",
                                   "payments": [], "cancellations": []}
        set_session(self.client, user_id=7, role="PASSENGER")
        response = self.client.get("/api/bookings/status?pnr=ABCD23456789")
        self.assertEqual(response.status_code, 200)
        get_status.assert_called_once_with(7, "ABCD23456789")

    @patch("backend.app.django_views.get_booking_status")
    def test_unknown_or_other_owners_pnr_returns_not_found(self, get_status):
        get_status.return_value = None
        set_session(self.client, user_id=7, role="PASSENGER")
        response = self.client.get("/api/bookings/status?pnr=OTHERPNR123")
        self.assertEqual(response.status_code, 404)

if __name__ == "__main__":
    unittest.main()
