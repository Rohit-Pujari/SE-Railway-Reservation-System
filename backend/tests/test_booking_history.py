"""Tests for passenger-owned upcoming and previous booking history."""

import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from backend.app.booking_history import get_booking_history
from backend.tests.drf_client import RailwayAPIClient, set_session


def history_row(booking_id=51, trip_type="UPCOMING", passenger_id=501):
    return {
        "booking_id": booking_id,
        "pnr": "PNR123456789",
        "booking_status": "PENDING_PAYMENT" if trip_type == "UPCOMING" else "CONFIRMED",
        "train_number_snapshot": "12627",
        "train_name_snapshot": "Karnataka Express",
        "boarding_station_code_snapshot": "SBC",
        "boarding_station_name_snapshot": "KSR Bengaluru",
        "alighting_station_code_snapshot": "NDLS",
        "alighting_station_name_snapshot": "New Delhi",
        "departure_at_snapshot": datetime(2026, 11, 15, 20, 0),
        "arrival_at_snapshot": datetime(2026, 11, 16, 10, 0),
        "class_code_snapshot": "SL",
        "base_fare_total": Decimal("900.00"),
        "other_charges": Decimal("0.00"),
        "total_fare": Decimal("900.00"),
        "currency_code": "INR",
        "created_at": datetime(2026, 10, 30, 9, 0),
        "confirmed_at": None,
        "trip_type": trip_type,
        "booking_passenger_id": passenger_id,
        "passenger_name": "Santosh N",
        "age": 21,
        "gender": None,
        "berth_preference": "LOWER",
        "passenger_fare": Decimal("900.00"),
        "allocation_status": "HELD",
        "hold_expires_at": datetime(2026, 10, 30, 9, 15),
        "coach_number": "S1",
        "seat_number": "42",
    }


class BookingHistoryServiceTests(unittest.TestCase):
    def test_groups_bookings_and_passengers_for_the_requested_owner(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchall.return_value = [
            history_row(51, "UPCOMING", 501),
            history_row(52, "PREVIOUS", 502),
        ]

        result = get_booking_history(7, connection_factory=lambda: connection)

        self.assertEqual(result["count"], 2)
        self.assertEqual([item["booking_id"] for item in result["upcoming"]], [51])
        self.assertEqual([item["booking_id"] for item in result["previous"]], [52])
        upcoming = result["upcoming"][0]
        self.assertEqual(upcoming["pnr"], "PNR123456789")
        self.assertEqual(upcoming["passengers"][0]["passenger_name"], "Santosh N")
        self.assertEqual(upcoming["passengers"][0]["coach_number"], "S1")
        self.assertEqual(upcoming["passengers"][0]["seat_number"], "42")
        self.assertEqual(upcoming["total_fare"], 900.0)
        self.assertEqual(cursor.execute.call_args.args[1], (7,))
        self.assertIn("WHERE booking.user_id = %s", cursor.execute.call_args.args[0])
        connection.close.assert_called_once_with()
        cursor.close.assert_called_once_with()

    def test_empty_history_returns_empty_sections(self):
        connection = MagicMock()
        connection.cursor.return_value.fetchall.return_value = []
        result = get_booking_history(9, connection_factory=lambda: connection)
        self.assertEqual(result, {"upcoming": [], "previous": [], "count": 0})

    def test_invalid_owner_is_rejected_before_database_access(self):
        factory = MagicMock()
        with self.assertRaises(ValueError):
            get_booking_history(0, connection_factory=factory)
        factory.assert_not_called()


class BookingHistoryEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = RailwayAPIClient()

    def test_anonymous_user_cannot_view_booking_history(self):
        response = self.client.get("/api/bookings/history")
        self.assertEqual(response.status_code, 401)

    @patch("backend.app.django_views.get_booking_history")
    def test_authenticated_passenger_receives_only_their_history(self, get_history):
        get_history.return_value = {"upcoming": [], "previous": [], "count": 0}
        set_session(self.client, user_id=7, role="PASSENGER")

        response = self.client.get("/api/bookings/history")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["count"], 0)
        get_history.assert_called_once_with(7)

    @patch("backend.app.django_views.get_booking_history")
    def test_admin_cannot_access_passenger_booking_history(self, get_history):
        set_session(self.client, user_id=3, role="ADMIN")
        response = self.client.get("/api/bookings/history")
        self.assertEqual(response.status_code, 401)
        get_history.assert_not_called()


if __name__ == "__main__":
    unittest.main()
