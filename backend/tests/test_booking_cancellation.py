"""Tests for secure, transactional passenger booking cancellation."""
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from backend.app.booking_cancellation import (
    BookingCancellationError,
    BookingCancellationNotFound,
    cancel_booking,
)
from backend.tests.drf_client import RailwayAPIClient, set_session


class BookingCancellationServiceTests(unittest.TestCase):
    def _connection(self, status="CONFIRMED", passenger_count=2, allocation_count=2):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.side_effect = [
            {"booking_id": 41, "pnr": "PNR123456789", "booking_status": status,
             "departure_at_snapshot": datetime.now() + timedelta(days=2)},
            {"current_time": datetime.now()},
        ]
        cursor.fetchall.side_effect = [
            [{"booking_passenger_id": i + 1} for i in range(passenger_count)],
            [{"allocation_id": i + 1} for i in range(allocation_count)],
        ]
        cursor.lastrowid = 91
        cursor.rowcount = 1
        return connection

    def test_cancels_owned_booking_and_releases_seats_in_one_transaction(self):
        connection = self._connection()
        result = cancel_booking(7, 41, "Change of plans", connection_factory=lambda: connection)
        cursor = connection.cursor.return_value
        self.assertEqual(result["booking_status"], "CANCELLED")
        self.assertEqual(result["cancelled_passengers"], 2)
        self.assertEqual(result["released_seats"], 1)
        self.assertEqual(cursor.execute.call_args_list[0].args[1], (41, 7))
        self.assertIn("WHERE booking_id = %s AND user_id = %s", cursor.execute.call_args_list[0].args[0])
        self.assertEqual(cursor.execute.call_args_list[-1].args[1], (41, 7))
        connection.commit.assert_called_once_with()
        connection.rollback.assert_not_called()
        connection.close.assert_called_once_with()

    def test_supports_pending_payment_booking_cancellation(self):
        connection = self._connection(status="PENDING_PAYMENT")
        result = cancel_booking(7, 41, connection_factory=lambda: connection)
        self.assertEqual(result["booking_status"], "CANCELLED")
        connection.commit.assert_called_once_with()

    def test_rejects_booking_owned_by_another_user(self):
        connection = MagicMock()
        connection.cursor.return_value.fetchone.return_value = None
        with self.assertRaises(BookingCancellationNotFound):
            cancel_booking(7, 41, connection_factory=lambda: connection)
        connection.rollback.assert_called_once_with()
        self.assertEqual(connection.cursor.return_value.execute.call_count, 1)

    def test_rejects_already_cancelled_booking(self):
        connection = MagicMock()
        connection.cursor.return_value.fetchone.return_value = {
            "booking_id": 41, "pnr": "PNR123456789", "booking_status": "CANCELLED",
            "departure_at_snapshot": datetime.now() + timedelta(days=2),
        }
        with self.assertRaisesRegex(BookingCancellationError, "already been cancelled"):
            cancel_booking(7, 41, connection_factory=lambda: connection)
        connection.rollback.assert_called_once_with()

    def test_rejects_booking_after_journey_started(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.side_effect = [
            {"booking_id": 41, "pnr": "PNR123456789", "booking_status": "CONFIRMED",
             "departure_at_snapshot": datetime.now() - timedelta(hours=1)},
            {"current_time": datetime.now()},
        ]
        with self.assertRaisesRegex(BookingCancellationError, "journey has started"):
            cancel_booking(7, 41, connection_factory=lambda: connection)
        connection.rollback.assert_called_once_with()

    def test_invalid_booking_id_does_not_open_database(self):
        factory = MagicMock()
        with self.assertRaises(BookingCancellationError):
            cancel_booking(7, "0", connection_factory=factory)
        factory.assert_not_called()


class BookingCancellationEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = RailwayAPIClient()

    def test_anonymous_user_cannot_cancel(self):
        response = self.client.post("/api/bookings/41/cancel", {"reason": "No longer needed"}, format="json")
        self.assertEqual(response.status_code, 401)

    @patch("backend.app.django_views.cancel_booking")
    def test_passenger_cancels_using_their_session_identity(self, cancel):
        cancel.return_value = {"booking_id": 41, "pnr": "PNR123456789",
                               "booking_status": "CANCELLED", "cancelled_passengers": 2,
                               "released_seats": 2, "message": "Booking cancelled successfully."}
        set_session(self.client, user_id=7, role="PASSENGER")
        response = self.client.post("/api/bookings/41/cancel", {"reason": "Change of plans"}, format="json")
        self.assertEqual(response.status_code, 200)
        cancel.assert_called_once_with(7, 41, "Change of plans")

    @patch("backend.app.django_views.cancel_booking")
    def test_non_owned_booking_returns_not_found(self, cancel):
        cancel.side_effect = BookingCancellationNotFound("Booking was not found in your account.")
        set_session(self.client, user_id=7, role="PASSENGER")
        response = self.client.post("/api/bookings/41/cancel", {}, format="json")
        self.assertEqual(response.status_code, 404)

if __name__ == "__main__":
    unittest.main()
