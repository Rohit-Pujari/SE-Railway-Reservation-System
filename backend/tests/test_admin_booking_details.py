"""Authorization and response tests for administrator booking details."""

import unittest
from unittest.mock import patch

from backend.app.admin_booking_details import get_admin_booking_details
from backend.tests.drf_client import RailwayAPIClient, set_session


class AdminBookingDetailServiceTests(unittest.TestCase):
    def test_rejects_invalid_booking_ids(self):
        for value in (None, True, 0, -1, "abc", "01"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    get_admin_booking_details(value, connection_factory=lambda: self.fail("DB should not be opened."))


class AdminBookingDetailEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = RailwayAPIClient()

    def test_anonymous_user_cannot_view_booking_details(self):
        response = self.client.get("/api/admin/bookings/41")
        self.assertEqual(response.status_code, 401)

    def test_passenger_cannot_view_booking_details(self):
        set_session(self.client, user_id=12, role="PASSENGER")
        response = self.client.get("/api/admin/bookings/41")
        self.assertEqual(response.status_code, 403)

    @patch("backend.app.admin_booking_details.get_admin_booking_details")
    def test_admin_can_view_booking_and_passenger_details(self, get_details):
        set_session(self.client, user_id=7, role="ADMIN")
        get_details.return_value = {
            "booking": {"booking_id": 41, "pnr": "ABC123", "booking_status": "CONFIRMED"},
            "passengers": [{"passenger_name": "Test Passenger", "coach_number": "B1", "seat_number": "12"}],
            "payments": [{"payment_status": "SUCCEEDED", "amount": 850.0}],
            "cancellations": [],
        }
        response = self.client.get("/api/admin/bookings/41")
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["booking"]["pnr"], "ABC123")
        self.assertEqual(payload["passengers"][0]["seat_number"], "12")
        self.assertEqual(payload["payments"][0]["payment_status"], "SUCCEEDED")
        get_details.assert_called_once_with(41)

    @patch("backend.app.admin_booking_details.get_admin_booking_details")
    def test_unknown_booking_returns_not_found(self, get_details):
        set_session(self.client, user_id=7, role="ADMIN")
        get_details.return_value = None
        response = self.client.get("/api/admin/bookings/99999")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
