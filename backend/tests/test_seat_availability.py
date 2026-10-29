"""Tests for class-specific seat availability."""

import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import mysql.connector

from backend.tests.drf_client import RailwayAPIClient, set_session
from backend.app.seat_availability import (
    SeatAvailabilityValidationError,
    get_active_travel_classes,
    get_seat_availability,
    validate_availability,
)


class TravelClassQueryTests(unittest.TestCase):
    def test_returns_active_travel_classes_and_closes_resources(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchall.return_value = [
            {"class_id": 1, "class_code": "SL", "class_name": "Sleeper"},
        ]
        result = get_active_travel_classes(connection_factory=lambda: connection)
        self.assertEqual(result, [{"class_id": 1, "class_code": "SL", "class_name": "Sleeper"}])
        sql = cursor.execute.call_args.args[0]
        self.assertIn("class_status = 'ACTIVE'", sql)
        self.assertIn("ORDER BY class_id", sql)
        cursor.close.assert_called_once()
        connection.close.assert_called_once()

    def test_database_errors_propagate(self):
        connection = MagicMock()
        connection.cursor.return_value.execute.side_effect = mysql.connector.Error("db unavailable")
        with self.assertRaises(mysql.connector.Error):
            get_active_travel_classes(connection_factory=lambda: connection)
        connection.close.assert_called_once()


class SeatAvailabilityValidationTests(unittest.TestCase):
    def test_valid_parameters_are_normalized(self):
        self.assertEqual(
            validate_availability("9", "1", "2", "2026-11-15", "3"),
            (9, 1, 2, datetime(2026, 11, 15).date(), 3),
        )

    def test_invalid_ids_and_same_station_are_rejected(self):
        cases = [
            (None, "1", "2", "2026-11-15", "3"),
            ("0", "1", "2", "2026-11-15", "3"),
            ("9", "1", "1", "2026-11-15", "3"),
            ("9", "1", "2", "2026-02-30", "3"),
            ("9", "1", "2", "2026-11-15", "0"),
        ]
        for args in cases:
            with self.subTest(args=args), self.assertRaises(SeatAvailabilityValidationError):
                validate_availability(*args)


class SeatAvailabilityQueryTests(unittest.TestCase):
    def test_query_counts_class_specific_seats_and_ignores_overlapping_allocations(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.return_value = {
            "schedule_id": 9,
            "class_id": 3,
            "class_code": "3A",
            "available_seats": 27,
        }

        result = get_seat_availability(
            "9", "1", "2", "2026-11-15", "3",
            connection_factory=lambda: connection,
        )

        self.assertEqual(result, {
            "schedule_id": 9,
            "class_id": 3,
            "class_code": "3A",
            "available_seats": 27,
        })
        sql, params = cursor.execute.call_args.args
        self.assertIn("seat_allocations", sql)
        self.assertIn("allocation_status = 'CONFIRMED'", sql)
        self.assertIn("hold_expires_at > CURRENT_TIMESTAMP", sql)
        self.assertEqual(params[0:3], (1, 2, 3))
        self.assertEqual(params[3], 9)
        self.assertEqual(params[4], datetime(2026, 11, 15, 0, 0))
        connection.close.assert_called_once()
        cursor.close.assert_called_once()

    def test_missing_schedule_returns_zero_available(self):
        connection = MagicMock()
        connection.cursor.return_value.fetchone.return_value = None
        result = get_seat_availability(
            "9", "1", "2", "2026-11-15", "3",
            connection_factory=lambda: connection,
        )
        self.assertEqual(result["available_seats"], 0)
        self.assertIsNone(result["class_code"])

    def test_database_errors_propagate_for_api_handling(self):
        connection = MagicMock()
        connection.cursor.return_value.execute.side_effect = mysql.connector.Error("db unavailable")
        with self.assertRaises(mysql.connector.Error):
            get_seat_availability(
                "9", "1", "2", "2026-11-15", "3",
                connection_factory=lambda: connection,
            )
        connection.close.assert_called_once()


class SeatAvailabilityEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = RailwayAPIClient()

    @patch("backend.app.django_views.get_active_travel_classes")
    def test_travel_classes_endpoint_returns_active_classes(self, get_classes):
        get_classes.return_value = [{"class_id": 1, "class_code": "SL", "class_name": "Sleeper"}]
        response = self.client.get("/api/travel-classes")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["travel_classes"][0]["class_code"], "SL")

    @patch("backend.app.django_views.get_active_travel_classes")
    def test_travel_classes_database_error_is_safe(self, get_classes):
        get_classes.side_effect = mysql.connector.Error("secret database details")
        response = self.client.get("/api/travel-classes")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret database details", response.content.decode())

    @patch("backend.app.django_views.get_seat_availability")
    def test_endpoint_returns_class_availability(self, availability):
        availability.return_value = {
            "schedule_id": 9,
            "class_id": 3,
            "class_code": "3A",
            "available_seats": 27,
        }
        response = self.client.get(
            "/api/seats/availability?schedule_id=9&source_station_id=1"
            "&destination_station_id=2&journey_date=2026-11-15&class_id=3"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["available_seats"], 27)
        self.assertEqual(response.json()["class_code"], "3A")

    @patch("backend.app.django_views.get_seat_availability")
    def test_invalid_search_returns_400(self, availability):
        availability.side_effect = SeatAvailabilityValidationError("Select a valid travel class.")
        response = self.client.get("/api/seats/availability")
        self.assertEqual(response.status_code, 400)

    @patch("backend.app.django_views.get_seat_availability")
    def test_database_error_is_safe(self, availability):
        availability.side_effect = mysql.connector.Error("secret database details")
        response = self.client.get(
            "/api/seats/availability?schedule_id=9&source_station_id=1"
            "&destination_station_id=2&journey_date=2026-11-15&class_id=3"
        )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret database details", response.content.decode())


if __name__ == "__main__":
    unittest.main()
