"""Tests for transactional passenger bookings and expiring seat holds."""

import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import mysql.connector

from backend.app import create_app
from backend.app.booking import (
    BookingRequestError,
    BookingUnavailableError,
    create_booking,
)
from backend.app.passenger_details import PassengerDetailsValidationError


def valid_passengers(count=2):
    return [
        {
            "passenger_name": f"Passenger {index}",
            "age": 30,
            "gender": None,
            "berth_preference": "NO_PREFERENCE",
        }
        for index in range(1, count + 1)
    ]


def configured_connection(*, available_seats=2):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.side_effect = [
        {"user_id": 7},
        None,
        {
            "schedule_id": 9,
            "route_id": 5,
            "train_number": "12001",
            "train_name": "Sample Express",
            "boarding_stop_id": 101,
            "boarding_route_stop_id": 201,
            "boarding_sequence": 1,
            "departure_at": datetime(2026, 11, 15, 9, 0),
            "source_code": "AAA",
            "source_name": "Alpha",
            "alighting_stop_id": 103,
            "alighting_route_stop_id": 203,
            "alighting_sequence": 3,
            "arrival_at": datetime(2026, 11, 15, 12, 0),
            "destination_code": "CCC",
            "destination_name": "Charlie",
            "class_code": "SL",
        },
        {"fare_amount": Decimal("125.50"), "currency_code": "INR"},
        {"hold_expires_at": datetime(2026, 11, 15, 9, 15)},
    ]
    cursor.fetchall.side_effect = [
        [{"schedule_seat_id": 701}, {"schedule_seat_id": 702}],
        [
            {"schedule_seat_id": seat_id, "coach_number": "S1", "seat_number": str(seat_id)}
            for seat_id in range(701, 701 + available_seats)
        ],
    ]
    inserted_ids = iter([88, 501, 502])

    def record_insert(sql, params=None):
        if "INSERT INTO bookings" in sql or "INSERT INTO booking_passengers" in sql:
            cursor.lastrowid = next(inserted_ids)

    cursor.execute.side_effect = record_insert
    return connection


class BookingRequestValidationTests(unittest.TestCase):
    def test_invalid_input_is_rejected_before_database_access(self):
        factory = MagicMock()
        cases = [
            {"schedule_id": 0},
            {"source_station_id": 2, "destination_station_id": 2},
            {"journey_date": "2026-02-30"},
            {"idempotency_key": ""},
            {"passengers": []},
            {"passengers": valid_passengers(7)},
        ]
        base = {
            "user_id": 7,
            "schedule_id": 9,
            "source_station_id": 1,
            "destination_station_id": 3,
            "journey_date": "2026-11-15",
            "class_id": 2,
            "passengers": valid_passengers(),
            "idempotency_key": "request-1",
        }
        for overrides in cases:
            args = {**base, **overrides}
            with self.subTest(overrides=overrides), self.assertRaises(
                (BookingRequestError, PassengerDetailsValidationError)
            ):
                create_booking(**args, connection_factory=factory)
        factory.assert_not_called()


class BookingTransactionTests(unittest.TestCase):
    def create(self, connection, passengers=None):
        return create_booking(
            7, 9, 1, 3, "2026-11-15", 2,
            passengers or valid_passengers(), "request-1",
            connection_factory=lambda: connection,
        )

    def test_booking_passengers_and_seat_holds_commit_together(self):
        connection = configured_connection()
        result = self.create(connection)

        self.assertEqual(result["booking_id"], 88)
        self.assertEqual(result["pnr"], result["pnr"].upper())
        self.assertEqual(result["status"], "PENDING_PAYMENT")
        self.assertEqual(result["currency_code"], "INR")
        self.assertEqual(result["total_fare"], 251.0)
        self.assertEqual(len(result["assigned_seats"]), 2)
        self.assertEqual(result["assigned_seats"][0], {"coach_number": "S1", "seat_number": "701"})
        self.assertEqual(result["hold_expires_at"], "2026-11-15T09:15:00")

        connection.start_transaction.assert_called_once_with(isolation_level="READ COMMITTED")
        connection.commit.assert_called_once_with()
        connection.rollback.assert_not_called()
        sql_calls = connection.cursor.return_value.execute.call_args_list
        booking_insert = next(call for call in sql_calls if "INSERT INTO bookings" in call.args[0])
        self.assertEqual(booking_insert.args[1][0], result["pnr"])
        self.assertEqual(booking_insert.args[1][15], Decimal("251.00"))
        self.assertIn("FOR UPDATE", next(call.args[0] for call in sql_calls if "FROM schedule_seats" in call.args[0]))
        allocation_inserts = [call for call in sql_calls if "INSERT INTO seat_allocations" in call.args[0]]
        self.assertEqual(len(allocation_inserts), 2)
        self.assertTrue(all("'HELD'" in call.args[0] for call in allocation_inserts))
        connection.close.assert_called_once_with()

    def test_insufficient_seats_rolls_back_without_booking(self):
        connection = configured_connection(available_seats=1)
        with self.assertRaises(BookingUnavailableError):
            self.create(connection)

        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()
        sql_calls = connection.cursor.return_value.execute.call_args_list
        self.assertFalse(any("INSERT INTO bookings" in call.args[0] for call in sql_calls))

    def test_fare_or_database_failure_rolls_back_partial_booking(self):
        connection = configured_connection()
        cursor = connection.cursor.return_value

        def fail_on_passenger_insert(sql, params=None):
            if "INSERT INTO booking_passengers" in sql:
                raise mysql.connector.Error("simulated insert failure")

        cursor.execute.side_effect = fail_on_passenger_insert
        with self.assertRaises(mysql.connector.Error):
            self.create(connection)

        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()
        connection.close.assert_called_once_with()

    def test_database_retries_return_existing_booking_and_seats(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.side_effect = [
            {"user_id": 7},
            {
                "booking_id": 88,
                "pnr": "AB23456789",
                "schedule_id": 9,
                "class_id": 2,
                "booking_status": "PENDING_PAYMENT",
                "total_fare": Decimal("251.00"),
                "currency_code": "INR",
                "source_station_id": 1,
                "destination_station_id": 3,
                "passenger_count": 2,
                "hold_expires_at": datetime(2026, 11, 15, 9, 15),
            },
        ]
        cursor.fetchall.return_value = [
            {"coach_number": "S1", "seat_number": "1"},
            {"coach_number": "S1", "seat_number": "2"},
        ]

        result = self.create(connection)

        self.assertTrue(result["replayed"])
        self.assertEqual(result["booking_id"], 88)
        self.assertEqual(len(result["assigned_seats"]), 2)
        self.assertEqual(cursor.execute.call_count, 3)
        connection.commit.assert_called_once_with()
        self.assertFalse(any("INSERT INTO" in call.args[0] for call in cursor.execute.call_args_list))


class BookingEndpointTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = self.app.test_client()

    def test_anonymous_user_cannot_create_booking(self):
        response = self.client.post("/api/bookings", json={})
        self.assertEqual(response.status_code, 401)

    @patch("backend.app.routes.create_booking")
    def test_authenticated_passenger_can_start_booking(self, create):
        create.return_value = {
            "booking_id": 88,
            "pnr": "AB23456789",
            "status": "PENDING_PAYMENT",
            "assigned_seats": [{"coach_number": "S1", "seat_number": "1"}],
            "replayed": False,
        }
        with self.client.session_transaction() as session:
            session["user_id"] = 7
            session["role"] = "PASSENGER"
        response = self.client.post("/api/bookings", json={
            "schedule_id": 9,
            "source_station_id": 1,
            "destination_station_id": 3,
            "journey_date": "2026-11-15",
            "class_id": 2,
            "passengers": valid_passengers(1),
            "idempotency_key": "request-1",
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json["pnr"], "AB23456789")
        create.assert_called_once()

    @patch("backend.app.routes.create_booking")
    def test_no_seats_returns_conflict(self, create):
        create.side_effect = BookingUnavailableError("No seats remain.")
        with self.client.session_transaction() as session:
            session["user_id"] = 7
            session["role"] = "PASSENGER"
        response = self.client.post("/api/bookings", json={"idempotency_key": "request-1"})
        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
