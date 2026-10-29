"""Tests for booking fare calculation and the fare API."""

import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

import mysql.connector

from backend.app import create_app
from backend.app.fare_calculation import FareCalculationError, calculate_booking_fare


class FareCalculationServiceTests(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value
        self.cursor.fetchone.side_effect = [
            {
                "booking_id": 10,
                "booking_status": "PENDING_PAYMENT",
                "schedule_id": 4,
                "class_id": 2,
                "boarding_schedule_stop_id": 31,
                "alighting_schedule_stop_id": 35,
                "other_charges": Decimal("20.00"),
                "route_id": 7,
            },
            {"fare_amount": Decimal("125.50"), "currency_code": "INR",
             "origin_sequence": 1, "destination_sequence": 4},
        ]
        self.cursor.fetchall.return_value = [
            {"booking_passenger_id": 100}, {"booking_passenger_id": 101}
        ]

    def test_calculates_per_passenger_and_total_and_persists(self):
        result = calculate_booking_fare(10, 5, connection_factory=lambda: self.connection)
        self.assertEqual(result, {
            "booking_id": 10,
            "passenger_count": 2,
            "currency_code": "INR",
            "fare_per_passenger": 125.5,
            "base_fare_total": 251.0,
            "other_charges": 20.0,
            "total_fare": 271.0,
        })
        self.assertEqual(self.cursor.execute.call_count, 5)
        self.assertEqual(self.cursor.execute.call_args_list[1].args[1], (10,))
        self.assertEqual(self.cursor.execute.call_args_list[3].args[1], (Decimal("125.50"), 10))
        self.assertEqual(
            self.cursor.execute.call_args_list[4].args[1],
            (Decimal("251.00"), Decimal("271.00"), "INR", 10, 5),
        )
        self.connection.commit.assert_called_once()
        self.connection.close.assert_called_once()

    def test_rejects_missing_booking_and_rolls_back(self):
        self.cursor.fetchone.side_effect = [None]
        with self.assertRaisesRegex(FareCalculationError, "not found"):
            calculate_booking_fare(10, 5, connection_factory=lambda: self.connection)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    def test_rejects_non_pending_booking(self):
        self.cursor.fetchone.side_effect = [{
            "booking_id": 10, "booking_status": "CONFIRMED", "schedule_id": 4,
            "class_id": 2, "boarding_schedule_stop_id": 31,
            "alighting_schedule_stop_id": 35, "other_charges": Decimal("0"), "route_id": 7,
        }]
        with self.assertRaisesRegex(FareCalculationError, "pending"):
            calculate_booking_fare(10, 5, connection_factory=lambda: self.connection)
        self.connection.rollback.assert_called_once()

    def test_requires_passengers(self):
        self.cursor.fetchall.return_value = []
        with self.assertRaisesRegex(FareCalculationError, "passenger"):
            calculate_booking_fare(10, 5, connection_factory=lambda: self.connection)
        self.connection.rollback.assert_called_once()

    def test_rejects_unconfigured_segment_class_fare(self):
        self.cursor.fetchone.side_effect = [
            {
                "booking_id": 10, "booking_status": "PENDING_PAYMENT", "schedule_id": 4,
                "class_id": 2, "boarding_schedule_stop_id": 31,
                "alighting_schedule_stop_id": 35, "other_charges": Decimal("0"), "route_id": 7,
            },
            None,
        ]
        with self.assertRaisesRegex(FareCalculationError, "No fare is configured"):
            calculate_booking_fare(10, 5, connection_factory=lambda: self.connection)
        self.connection.rollback.assert_called_once()

    def test_rolls_back_database_errors(self):
        self.cursor.execute.side_effect = mysql.connector.Error("database unavailable")
        with self.assertRaises(mysql.connector.Error):
            calculate_booking_fare(10, 5, connection_factory=lambda: self.connection)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()


class FareCalculationEndpointTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY="fare-test-secret")
        self.client = self.app.test_client()

    def test_requires_passenger_login(self):
        response = self.client.post("/api/bookings/10/fare")
        self.assertEqual(response.status_code, 401)

    @patch("backend.app.routes.calculate_booking_fare")
    def test_returns_calculated_total_for_logged_in_passenger(self, calculate):
        calculate.return_value = {
            "booking_id": 10, "passenger_count": 2, "currency_code": "INR",
            "fare_per_passenger": 125.5, "base_fare_total": 251.0,
            "other_charges": 20.0, "total_fare": 271.0,
        }
        with self.client.session_transaction() as sess:
            sess["user_id"] = 5
            sess["role"] = "PASSENGER"
        response = self.client.post("/api/bookings/10/fare")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["total_fare"], 271.0)
        calculate.assert_called_once_with(10, 5)

    @patch("backend.app.routes.calculate_booking_fare")
    def test_validation_failure_returns_conflict(self, calculate):
        calculate.side_effect = FareCalculationError("No fare is configured.")
        with self.client.session_transaction() as sess:
            sess["user_id"] = 5
            sess["role"] = "PASSENGER"
        response = self.client.post("/api/bookings/10/fare")
        self.assertEqual(response.status_code, 409)
        self.assertIn("No fare is configured", response.json["message"])


if __name__ == "__main__":
    unittest.main()
