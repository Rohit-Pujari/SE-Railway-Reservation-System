"""Tests for passenger detail validation and persistence."""

import unittest
from unittest.mock import MagicMock

import mysql.connector

from backend.app import create_app
from backend.app.passenger_details import (
    PassengerDetailsValidationError,
    save_passenger_details,
)


def configured_connection(existing_count=0, booking=None):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.side_effect = [
        booking or {"booking_id": 41, "booking_status": "PENDING_PAYMENT"},
        {"passenger_count": existing_count},
    ]
    cursor.lastrowid = 100
    return connection


class PassengerDetailsServiceTests(unittest.TestCase):
    def test_saves_valid_passenger_details_to_pending_booking(self):
        connection = configured_connection()
        result = save_passenger_details(
            41, 7,
            [{"passenger_name": "  Ananya Rao ", "age": 22, "gender": "Female",
              "berth_preference": "LOWER"}],
            connection_factory=lambda: connection,
        )
        self.assertEqual(result["passengers_added"], 1)
        self.assertEqual(result["passengers"][0]["passenger_name"], "Ananya Rao")
        insert = next(call for call in connection.cursor.return_value.execute.call_args_list
                      if "INSERT INTO booking_passengers" in call.args[0])
        self.assertEqual(insert.args[1], (41, "Ananya Rao", 22, "Female", "LOWER"))
        connection.commit.assert_called_once_with()
        connection.close.assert_called_once()

    def test_rejects_invalid_passenger_name_age_and_berth(self):
        invalid = [
            [{"passenger_name": " ", "age": 22}],
            [{"passenger_name": "A", "age": 121}],
            [{"passenger_name": "A", "age": "twenty"}],
            [{"passenger_name": "A", "age": 20, "berth_preference": "WINDOW"}],
            [],
        ]
        for passengers in invalid:
            with self.subTest(passengers=passengers):
                with self.assertRaises(PassengerDetailsValidationError):
                    save_passenger_details(41, 7, passengers, connection_factory=lambda: configured_connection())

    def test_rejects_wrong_owner_or_missing_booking(self):
        connection = configured_connection(booking=None)
        connection.cursor.return_value.fetchone.return_value = None
        with self.assertRaisesRegex(PassengerDetailsValidationError, "not found"):
            save_passenger_details(41, 8, [{"passenger_name": "A", "age": 20}],
                                   connection_factory=lambda: connection)
        connection.rollback.assert_called_once_with()

    def test_rejects_confirmed_booking(self):
        connection = configured_connection(booking={"booking_id": 41, "booking_status": "CONFIRMED"})
        with self.assertRaisesRegex(PassengerDetailsValidationError, "before confirmation"):
            save_passenger_details(41, 7, [{"passenger_name": "A", "age": 20}],
                                   connection_factory=lambda: connection)
        connection.rollback.assert_called_once_with()

    def test_enforces_six_passenger_limit_including_existing(self):
        connection = configured_connection(existing_count=5)
        with self.assertRaisesRegex(PassengerDetailsValidationError, "at most 6"):
            save_passenger_details(41, 7, [{"passenger_name": "A", "age": 20},
                                           {"passenger_name": "B", "age": 21}],
                                   connection_factory=lambda: connection)
        connection.rollback.assert_called_once_with()

    def test_database_failure_rolls_back(self):
        connection = MagicMock()
        connection.cursor.return_value.execute.side_effect = mysql.connector.Error("database down")
        with self.assertRaises(mysql.connector.Error):
            save_passenger_details(41, 7, [{"passenger_name": "A", "age": 20}],
                                   connection_factory=lambda: connection)
        connection.rollback.assert_called_once_with()
        connection.close.assert_called_once()


class PassengerDetailsEndpointTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = self.app.test_client()

    def test_requires_passenger_login(self):
        response = self.client.post("/api/bookings/41/passengers", json={
            "passengers": [{"passenger_name": "A", "age": 20}]
        })
        self.assertEqual(response.status_code, 401)

    def test_rejects_invalid_json_shape(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 7
            session["role"] = "PASSENGER"
        response = self.client.post("/api/bookings/41/passengers", json=["not", "an object"])
        self.assertEqual(response.status_code, 400)

    def test_saves_passengers_for_authenticated_user(self):
        from unittest.mock import patch
        with self.client.session_transaction() as session:
            session["user_id"] = 7
            session["role"] = "PASSENGER"
        with patch("backend.app.routes.save_passenger_details") as save:
            save.return_value = {"booking_id": 41, "passengers_added": 1,
                                 "passengers": [{"passenger_name": "A", "age": 20,
                                                 "gender": None, "berth_preference": "NO_PREFERENCE"}]}
            response = self.client.post("/api/bookings/41/passengers", json={
                "passengers": [{"passenger_name": "A", "age": 20}]
            })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["passengers_added"], 1)
        save.assert_called_once_with(41, 7, [{"passenger_name": "A", "age": 20}])


if __name__ == "__main__":
    unittest.main()
