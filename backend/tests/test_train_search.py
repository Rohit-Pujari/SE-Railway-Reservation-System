"""Tests for station listing and scheduled train search."""

import unittest
from datetime import date, datetime
from unittest.mock import MagicMock, patch

import mysql.connector

from backend.app import create_app
from backend.app.train_search import (
    TrainSearchValidationError,
    search_trains,
    validate_search,
)


class TrainSearchValidationTests(unittest.TestCase):
    def test_valid_search_normalizes_station_ids_and_date(self):
        self.assertEqual(
            validate_search("1", "2", "2026-11-15"),
            (1, 2, date(2026, 11, 15), None),
        )

    def test_missing_or_non_numeric_station_ids_are_rejected(self):
        for source, destination in ((None, "2"), ("abc", "2"), ("1", None), ("1", "x")):
            with self.subTest(source=source, destination=destination):
                with self.assertRaises(TrainSearchValidationError):
                    validate_search(source, destination, "2026-11-15")

    def test_non_positive_station_ids_are_rejected(self):
        for source, destination in (("0", "2"), ("-1", "2"), ("1", "0")):
            with self.subTest(source=source, destination=destination):
                with self.assertRaises(TrainSearchValidationError):
                    validate_search(source, destination, "2026-11-15")

    def test_same_station_is_rejected(self):
        with self.assertRaises(TrainSearchValidationError):
            validate_search("3", "3", "2026-11-15")

    def test_invalid_date_is_rejected(self):
        for journey_date in ("", "15-11-2026", "2026-02-30", "2026-1-1", None):
            with self.subTest(journey_date=journey_date):
                with self.assertRaises(TrainSearchValidationError):
                    validate_search("1", "2", journey_date)


class TrainSearchQueryTests(unittest.TestCase):
    def test_search_uses_parameterized_query_and_formats_results(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchall.return_value = [{
            "schedule_id": 9,
            "train_number": "12001",
            "train_name": "Sample Express",
            "source_station_id": 1,
            "source_station_code": "AAA",
            "source_station_name": "Alpha",
            "source_city": "Alpha City",
            "destination_station_id": 2,
            "destination_station_code": "BBB",
            "destination_station_name": "Beta",
            "destination_city": "Beta City",
            "departure_at": datetime(2026, 11, 15, 9, 30),
            "arrival_at": datetime(2026, 11, 15, 12, 15),
            "starting_fare": 450.00,
            "currency_code": "INR",
            "available_seats": 42,
        }]
        result = search_trains("1", "2", "2026-11-15", connection_factory=lambda: connection)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["departure_at"], "2026-11-15T09:30:00")
        self.assertEqual(result[0]["arrival_at"], "2026-11-15T12:15:00")
        self.assertEqual(result[0]["starting_fare"], 450.0)
        self.assertEqual(result[0]["currency_code"], "INR")
        self.assertEqual(result[0]["available_seats"], 42)
        sql, params = cursor.execute.call_args.args
        self.assertIn("origin_stop.stop_sequence < destination_stop.stop_sequence", sql)
        self.assertIn("route_fares", sql)
        self.assertIn("seat_allocations", sql)
        self.assertEqual(params[0:6], (None, None, None, None, None, None))
        self.assertEqual(params[6], 1)
        self.assertEqual(params[7], 2)
        self.assertEqual(params[8], datetime(2026, 11, 15, 0, 0))
        self.assertEqual(params[9], datetime(2026, 11, 16, 0, 0))
        self.assertEqual(params[10], 100)
        connection.close.assert_called_once()
        cursor.close.assert_called_once()

    def test_database_errors_propagate_for_api_handling(self):
        connection = MagicMock()
        connection.cursor.return_value.execute.side_effect = mysql.connector.Error("db unavailable")
        with self.assertRaises(mysql.connector.Error):
            search_trains("1", "2", "2026-11-15", connection_factory=lambda: connection)
        connection.close.assert_called_once()


class TrainSearchEndpointTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = self.app.test_client()

    @patch("backend.app.routes.get_active_stations")
    def test_station_list(self, get_stations):
        get_stations.return_value = [{
            "station_id": 1, "station_code": "AAA", "station_name": "Alpha",
            "city": "Alpha City", "state": None,
        }]
        response = self.client.get("/api/stations")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["stations"][0]["station_code"], "AAA")

    @patch("backend.app.routes.get_active_stations")
    def test_station_database_error_is_safe(self, get_stations):
        get_stations.side_effect = mysql.connector.Error("secret db details")
        response = self.client.get("/api/stations")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret db details", response.get_data(as_text=True))

    def test_missing_search_parameters_rejected(self):
        response = self.client.get("/api/trains/search")
        self.assertEqual(response.status_code, 400)

    @patch("backend.app.routes.search_trains")
    def test_search_success(self, search):
        search.return_value = [{
            "schedule_id": 9, "train_number": "12001", "train_name": "Sample Express",
            "source_station_name": "Alpha", "destination_station_name": "Beta",
            "departure_at": "2026-11-15T09:30:00", "arrival_at": "2026-11-15T12:15:00",
        }]
        response = self.client.get(
            "/api/trains/search?source_station_id=1&destination_station_id=2&journey_date=2026-11-15&class_id=3"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["count"], 1)
        self.assertEqual(response.json["trains"][0]["train_number"], "12001")

    @patch("backend.app.routes.search_trains")
    def test_search_validation_error(self, search):
        search.side_effect = TrainSearchValidationError("Source and destination stations must be different.")
        response = self.client.get(
            "/api/trains/search?source_station_id=1&destination_station_id=1&journey_date=2026-11-15"
        )
        self.assertEqual(response.status_code, 400)

    @patch("backend.app.routes.search_trains")
    def test_search_database_error_is_safe(self, search):
        search.side_effect = mysql.connector.Error("secret db details")
        response = self.client.get(
            "/api/trains/search?source_station_id=1&destination_station_id=2&journey_date=2026-11-15"
        )
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret db details", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
