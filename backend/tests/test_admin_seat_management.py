"""Authorization and validation tests for administrator seat inventory controls."""

import unittest
from unittest.mock import patch

from backend.app.seat_management import (
    SeatManagementConflictError,
    SeatManagementValidationError,
    validate_operational_status,
)
from backend.tests.drf_client import RailwayAPIClient, set_session


class SeatManagementValidationTests(unittest.TestCase):
    def test_accepts_supported_operational_statuses(self):
        self.assertEqual(validate_operational_status("IN_SERVICE"), "IN_SERVICE")
        self.assertEqual(validate_operational_status("OUT_OF_SERVICE"), "OUT_OF_SERVICE")

    def test_rejects_unknown_operational_status(self):
        with self.assertRaises(SeatManagementValidationError):
            validate_operational_status("BOOKED")


class AdminSeatInventoryEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = RailwayAPIClient()

    def _admin_csrf(self):
        set_session(self.client, user_id=7, role="ADMIN")
        return self.client.get("/api/csrf").json()["csrfToken"]

    def test_anonymous_user_cannot_read_schedule_seats(self):
        response = self.client.get("/api/admin/schedules/19/seats")
        self.assertEqual(response.status_code, 401)

    def test_passenger_cannot_read_schedule_seats(self):
        set_session(self.client, user_id=12, role="PASSENGER")
        response = self.client.get("/api/admin/schedules/19/seats")
        self.assertEqual(response.status_code, 403)

    @patch("backend.app.seat_management.get_schedule_seats")
    def test_admin_can_view_schedule_seat_inventory(self, get_seats):
        self._admin_csrf()
        get_seats.return_value = {
            "schedule": {"schedule_id": 19, "train_number": "12001"},
            "seats": [{"schedule_seat_id": 31, "operational_status": "IN_SERVICE"}],
        }
        response = self.client.get("/api/admin/schedules/19/seats")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["seats"][0]["schedule_seat_id"], 31)
        get_seats.assert_called_once_with(19)

    def test_anonymous_user_cannot_change_seat_status(self):
        response = self.client.patch(
            "/api/admin/schedules/19/seats/31",
            {"operational_status": "OUT_OF_SERVICE"},
            format="json",
        )
        self.assertEqual(response.status_code, 401)

    def test_passenger_cannot_change_seat_status(self):
        set_session(self.client, user_id=12, role="PASSENGER")
        response = self.client.patch(
            "/api/admin/schedules/19/seats/31",
            {"operational_status": "OUT_OF_SERVICE"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    @patch("backend.app.seat_management.update_schedule_seat_status")
    def test_admin_can_change_seat_status(self, update_status):
        csrf = self._admin_csrf()
        update_status.return_value = {
            "schedule_id": 19,
            "schedule_seat_id": 31,
            "operational_status": "OUT_OF_SERVICE",
        }
        response = self.client.patch(
            "/api/admin/schedules/19/seats/31",
            {"operational_status": "OUT_OF_SERVICE"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["seat"]["operational_status"], "OUT_OF_SERVICE")
        update_status.assert_called_once_with(19, 31, "OUT_OF_SERVICE")

    def test_invalid_seat_status_returns_bad_request(self):
        csrf = self._admin_csrf()
        response = self.client.patch(
            "/api/admin/schedules/19/seats/31",
            {"operational_status": "BOOKED"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 400)

    @patch("backend.app.seat_management.update_schedule_seat_status")
    def test_seat_with_active_booking_returns_conflict(self, update_status):
        csrf = self._admin_csrf()
        update_status.side_effect = SeatManagementConflictError(
            "This seat has an active booking."
        )
        response = self.client.patch(
            "/api/admin/schedules/19/seats/31",
            {"operational_status": "OUT_OF_SERVICE"},
            format="json",
            HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 409)

    @patch("backend.app.seat_management.get_schedule_seats")
    def test_unknown_schedule_returns_not_found(self, get_seats):
        self._admin_csrf()
        get_seats.side_effect = LookupError("Train schedule not found.")
        response = self.client.get("/api/admin/schedules/999/seats")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
