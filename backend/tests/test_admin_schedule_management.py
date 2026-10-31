"""Validation and API authorization tests for train schedule administration."""

import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch

from backend.app.schedule_management import (
    ScheduleConflictError,
    ScheduleValidationError,
    _build_stop_times,
    validate_schedule,
)
from backend.tests.drf_client import RailwayAPIClient, set_session


class ScheduleValidationTests(unittest.TestCase):
    def test_valid_schedule_normalizes_ids_and_datetime_local_values(self):
        result = validate_schedule(
            "12", "5", "2026-11-02T08:30", "2026-11-02T14:45", "SCHEDULED"
        )
        self.assertEqual(result, (
            12, 5, datetime(2026, 11, 2, 8, 30),
            datetime(2026, 11, 2, 14, 45), "SCHEDULED",
        ))

    def test_arrival_must_be_after_departure(self):
        with self.assertRaises(ScheduleValidationError):
            validate_schedule(1, 1, "2026-11-02T14:00", "2026-11-02T14:00")

    def test_invalid_datetime_is_rejected(self):
        with self.assertRaises(ScheduleValidationError):
            validate_schedule(1, 1, "not-a-date", "2026-11-02T14:00")

    def test_timezone_aware_datetime_is_rejected(self):
        with self.assertRaises(ScheduleValidationError):
            validate_schedule(1, 1, "2026-11-02T08:30+05:30", "2026-11-02T14:00")

    def test_invalid_schedule_status_is_rejected(self):
        with self.assertRaises(ScheduleValidationError):
            validate_schedule(1, 1, "2026-11-02T08:30", "2026-11-02T14:00", "ACTIVE")

    def test_stop_times_are_interpolated_by_route_distance(self):
        stops = [
            {"route_stop_id": 11, "station_id": 1, "stop_sequence": 1, "distance_from_origin_km": Decimal("0")},
            {"route_stop_id": 12, "station_id": 2, "stop_sequence": 2, "distance_from_origin_km": Decimal("50")},
            {"route_stop_id": 13, "station_id": 3, "stop_sequence": 3, "distance_from_origin_km": Decimal("100")},
        ]
        rows = _build_stop_times(
            stops, datetime(2026, 11, 2, 8), datetime(2026, 11, 2, 10)
        )
        self.assertIsNone(rows[0][3])
        self.assertEqual(rows[0][4], datetime(2026, 11, 2, 8))
        self.assertEqual(rows[1][3], datetime(2026, 11, 2, 9))
        self.assertEqual(rows[1][4], datetime(2026, 11, 2, 9))
        self.assertEqual(rows[2][3], datetime(2026, 11, 2, 10))
        self.assertIsNone(rows[2][4])


class ScheduleEndpointAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.client = RailwayAPIClient()
        self.payload = {
            "train_id": 1, "route_id": 2,
            "departure_at": "2026-11-02T08:30",
            "arrival_at": "2026-11-02T14:00",
        }

    def test_anonymous_user_cannot_create_schedule(self):
        response = self.client.post("/api/admin/schedules", self.payload)
        self.assertEqual(response.status_code, 401)

    def test_passenger_cannot_create_schedule(self):
        set_session(self.client, user_id=12, role="PASSENGER")
        response = self.client.post("/api/admin/schedules", self.payload)
        self.assertEqual(response.status_code, 403)

    @patch("backend.app.schedule_management.create_schedule")
    def test_admin_can_create_schedule(self, create_schedule):
        set_session(self.client, user_id=7, role="ADMIN")
        create_schedule.return_value = {"schedule_id": 19}
        response = self.client.post("/api/admin/schedules", self.payload)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["schedule"]["schedule_id"], 19)

    def test_invalid_schedule_payload_returns_bad_request(self):
        set_session(self.client, user_id=7, role="ADMIN")
        invalid = {**self.payload, "arrival_at": self.payload["departure_at"]}
        response = self.client.post("/api/admin/schedules", invalid)
        self.assertEqual(response.status_code, 400)

    @patch("backend.app.schedule_management.update_schedule")
    def test_admin_can_update_schedule(self, update_schedule):
        set_session(self.client, user_id=7, role="ADMIN")
        update_schedule.return_value = {"schedule_id": 19, "schedule_status": "CANCELLED"}
        csrf = self.client.get("/api/csrf").json()["csrfToken"]
        response = self.client.patch(
            "/api/admin/schedules/19", {"schedule_status": "CANCELLED"},
            format="json", HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["schedule"]["schedule_id"], 19)

    @patch("backend.app.schedule_management.update_schedule")
    def test_schedule_with_bookings_conflict_is_reported(self, update_schedule):
        set_session(self.client, user_id=7, role="ADMIN")
        update_schedule.side_effect = ScheduleConflictError("Schedule has bookings.")
        csrf = self.client.get("/api/csrf").json()["csrfToken"]
        response = self.client.patch(
            "/api/admin/schedules/19", {"departure_at": "2026-11-02T09:00"},
            format="json", HTTP_X_CSRFTOKEN=csrf,
        )
        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
