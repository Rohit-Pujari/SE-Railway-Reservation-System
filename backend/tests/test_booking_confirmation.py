"""Tests for atomic seat allocation during booking confirmation."""

import unittest
from unittest.mock import MagicMock, patch

import mysql.connector

from backend.app import create_app
from backend.app.booking_confirmation import BookingConfirmationError, confirm_booking


def configured_connection(*, enough_seats=True):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.side_effect = [
        {
            "booking_id": 41, "user_id": 7, "schedule_id": 9,
            "boarding_schedule_stop_id": 101, "alighting_schedule_stop_id": 103,
            "class_id": 2, "booking_status": "PENDING_PAYMENT",
        },
        {"stop_sequence": 1},
        {"stop_sequence": 3},
    ]
    cursor.fetchall.side_effect = [
        [{"booking_passenger_id": 501}, {"booking_passenger_id": 502}],
        [{"schedule_seat_id": 701}, {"schedule_seat_id": 702}],
        ([{"schedule_seat_id": 701}, {"schedule_seat_id": 702}] if enough_seats
         else [{"schedule_seat_id": 701}]),
    ]
    cursor.rowcount = 1
    return connection


class BookingConfirmationTests(unittest.TestCase):
    def test_confirmation_allocates_distinct_seats_and_commits(self):
        connection = configured_connection()
        result = confirm_booking(41, 7, connection_factory=lambda: connection)

        self.assertEqual(result, {"booking_id": 41, "allocated_seats": 2, "status": "CONFIRMED"})
        connection.start_transaction.assert_called_once_with()
        connection.commit.assert_called_once_with()
        connection.rollback.assert_not_called()
        cursor = connection.cursor.return_value
        inserts = [
            call for call in cursor.execute.call_args_list
            if "INSERT INTO seat_allocations" in call.args[0]
        ]
        self.assertEqual(len(inserts), 2)
        self.assertEqual(inserts[0].args[1][4], 701)
        self.assertEqual(inserts[1].args[1][4], 702)
        self.assertIn("FOR UPDATE", cursor.execute.call_args_list[0].args[0])
        self.assertTrue(any("ORDER BY schedule_seat_id" in call.args[0] and "FOR UPDATE" in call.args[0]
                            for call in cursor.execute.call_args_list))
        self.assertTrue(all("'CONFIRMED', NULL" in call.args[0] for call in inserts))
        connection.close.assert_called_once()

    def test_insufficient_seats_rolls_back_without_creating_allocations(self):
        connection = configured_connection(enough_seats=False)
        with self.assertRaisesRegex(BookingConfirmationError, "Not enough seats"):
            confirm_booking(41, 7, connection_factory=lambda: connection)

        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()
        cursor = connection.cursor.return_value
        self.assertFalse(any("INSERT INTO seat_allocations" in call.args[0]
                             for call in cursor.execute.call_args_list))

    def test_wrong_user_or_missing_booking_rolls_back(self):
        connection = configured_connection()
        connection.cursor.return_value.fetchone.side_effect = [None]
        with self.assertRaisesRegex(BookingConfirmationError, "not found"):
            confirm_booking(41, 8, connection_factory=lambda: connection)
        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()

    def test_non_pending_booking_is_not_allocated(self):
        connection = configured_connection()
        connection.cursor.return_value.fetchone.side_effect = [
            {
                "booking_id": 41, "user_id": 7, "schedule_id": 9,
                "boarding_schedule_stop_id": 101, "alighting_schedule_stop_id": 103,
                "class_id": 2, "booking_status": "CONFIRMED",
            }
        ]
        with self.assertRaisesRegex(BookingConfirmationError, "Only pending"):
            confirm_booking(41, 7, connection_factory=lambda: connection)
        connection.rollback.assert_called_once_with()
        self.assertEqual(connection.cursor.return_value.execute.call_count, 1)

    def test_database_error_rolls_back_and_propagates(self):
        connection = MagicMock()
        connection.cursor.return_value.execute.side_effect = mysql.connector.Error("db down")
        with self.assertRaises(mysql.connector.Error):
            confirm_booking(41, 7, connection_factory=lambda: connection)
        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()
        connection.close.assert_called_once()


class BookingConfirmationEndpointTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        self.client = self.app.test_client()

    def test_anonymous_user_cannot_confirm_booking(self):
        response = self.client.post("/api/bookings/41/confirm")
        self.assertEqual(response.status_code, 401)

    @patch("backend.app.routes.confirm_booking")
    def test_authenticated_passenger_can_confirm_booking(self, confirm):
        confirm.return_value = {"booking_id": 41, "allocated_seats": 1, "status": "CONFIRMED"}
        with self.client.session_transaction() as session:
            session["user_id"] = 7
            session["role"] = "PASSENGER"
        response = self.client.post("/api/bookings/41/confirm")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["allocated_seats"], 1)
        confirm.assert_called_once_with(41, 7)

    @patch("backend.app.routes.confirm_booking")
    def test_conflict_returns_409(self, confirm):
        confirm.side_effect = BookingConfirmationError("Not enough seats are available.")
        with self.client.session_transaction() as session:
            session["user_id"] = 7
            session["role"] = "PASSENGER"
        response = self.client.post("/api/bookings/41/confirm")
        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
