"""Tests for confirmed-ticket refund policy and cancellation persistence."""
import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from backend.app.booking_cancellation import (
    BookingCancellationError,
    BookingCancellationNotFound,
    cancel_booking,
)
from backend.tests.drf_client import RailwayAPIClient, set_session


class BookingCancellationServiceTests(unittest.TestCase):
    def _connection(self, status="CONFIRMED", passenger_count=2, paid=True):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.side_effect = [
            {"booking_id": 41, "pnr": "PNR123456789", "booking_status": status,
             "departure_at_snapshot": datetime.now() + timedelta(days=3),
             "class_code_snapshot": "SL", "currency_code": "INR"},
            {"current_time": datetime.now()},
            ({"amount": Decimal("250.00"), "currency_code": "INR"} if paid else None),
        ]
        cursor.fetchall.side_effect = [
            [{"booking_passenger_id": i + 1, "passenger_fare": Decimal("125.00")}
             for i in range(passenger_count)],
            [{"allocation_id": i + 1} for i in range(passenger_count)],
        ]
        next_id = iter([91, 101, 102, 103, 104, 105])
        def record_insert(sql, params=None):
            if "INSERT INTO cancellations" in sql or "INSERT INTO cancellation_items" in sql:
                cursor.lastrowid = next(next_id)
        cursor.execute.side_effect = record_insert
        cursor.rowcount = 1
        return connection

    def test_cancels_booking_calculates_refunds_and_releases_seats_atomically(self):
        connection = self._connection()
        result = cancel_booking(7, 41, "Change of plans", connection_factory=lambda: connection)
        cursor = connection.cursor.return_value
        self.assertEqual(result["booking_status"], "CANCELLED")
        self.assertEqual(result["cancelled_passengers"], 2)
        self.assertEqual(result["released_seats"], 1)
        self.assertEqual(result["cancellation_charge"], 240.0)
        self.assertEqual(result["refund_amount"], 10.0)
        self.assertEqual(result["refund_status"], "PENDING")
        self.assertEqual(len(result["passenger_refunds"]), 2)
        self.assertEqual(cursor.execute.call_args_list[0].args[1], (41, 7))
        self.assertIn("WHERE booking_id = %s AND user_id = %s", cursor.execute.call_args_list[0].args[0])
        refund_inserts = [call for call in cursor.execute.call_args_list if "INSERT INTO refunds" in call.args[0]]
        self.assertEqual(len(refund_inserts), 2)
        self.assertTrue(all(call.args[1][3].startswith("cancellation-item-") for call in refund_inserts))
        connection.commit.assert_called_once_with()
        connection.rollback.assert_not_called()
        connection.close.assert_called_once_with()

    def test_pending_payment_booking_has_no_refund_record(self):
        connection = self._connection(status="PENDING_PAYMENT", paid=False)
        result = cancel_booking(7, 41, connection_factory=lambda: connection)
        self.assertEqual(result["refund_amount"], 0.0)
        self.assertEqual(result["refund_status"], "NOT_APPLICABLE")
        self.assertFalse(any("INSERT INTO refunds" in call.args[0]
                             for call in connection.cursor.return_value.execute.call_args_list))
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
            "class_code_snapshot": "SL", "currency_code": "INR",
        }
        with self.assertRaisesRegex(BookingCancellationError, "already been cancelled"):
            cancel_booking(7, 41, connection_factory=lambda: connection)
        connection.rollback.assert_called_once_with()

    def test_rejects_booking_after_journey_started(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.side_effect = [
            {"booking_id": 41, "pnr": "PNR123456789", "booking_status": "CONFIRMED",
             "departure_at_snapshot": datetime.now() - timedelta(hours=1),
             "class_code_snapshot": "SL", "currency_code": "INR"},
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
                               "released_seats": 2, "refund_amount": 850.0,
                               "message": "Booking cancelled. Refund due: INR 850.00."}
        set_session(self.client, user_id=7, role="PASSENGER")
        response = self.client.post("/api/bookings/41/cancel", {"reason": "Change of plans"}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["refund_amount"], 850.0)
        cancel.assert_called_once_with(7, 41, "Change of plans")

    @patch("backend.app.django_views.cancel_booking")
    def test_non_owned_booking_returns_not_found(self, cancel):
        cancel.side_effect = BookingCancellationNotFound("Booking was not found in your account.")
        set_session(self.client, user_id=7, role="PASSENGER")
        response = self.client.post("/api/bookings/41/cancel", {}, format="json")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
