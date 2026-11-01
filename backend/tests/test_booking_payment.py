"""Tests for the simulated payment and booking confirmation workflow."""

import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

from backend.app.booking_payment import (
    PaymentBookingNotFound,
    PaymentConfirmationError,
    confirm_booking_payment,
)


def payment_connection(*, allocation_expiry=None, email="passenger@example.com", phone="9876543210"):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.side_effect = [
        {
            "booking_id": 42, "pnr": "AB23456789CD",
            "booking_status": "PENDING_PAYMENT", "total_fare": 850.00,
            "currency_code": "INR", "email": email, "phone_number": phone,
        },
        {"current_time": datetime(2026, 11, 1, 10, 0)},
        {"passenger_count": 1},
    ]
    cursor.fetchall.return_value = [{
        "allocation_id": 5, "allocation_status": "HELD",
        "hold_expires_at": allocation_expiry or datetime(2026, 11, 1, 10, 15),
    }]
    cursor.lastrowid = 99
    cursor.rowcount = 1
    return connection, cursor


class BookingPaymentTests(unittest.TestCase):
    def test_success_confirms_booking_and_queues_available_channels(self):
        connection, cursor = payment_connection()
        result = confirm_booking_payment(7, 42, lambda: connection)

        self.assertEqual(result["booking_status"], "CONFIRMED")
        self.assertEqual(result["payment_status"], "SUCCEEDED")
        self.assertEqual(result["payment_method"], "SIMULATED")
        self.assertEqual([item["channel"] for item in result["notifications"]], ["EMAIL", "SMS"])
        self.assertTrue(any("INSERT INTO payments" in call.args[0] for call in cursor.execute.call_args_list))
        self.assertTrue(any("UPDATE bookings" in call.args[0] for call in cursor.execute.call_args_list))
        self.assertEqual(cursor.execute.call_count, 9)
        connection.commit.assert_called_once()

    def test_email_only_when_phone_number_is_not_available(self):
        connection, _ = payment_connection(phone=None)
        result = confirm_booking_payment(7, 42, lambda: connection)
        self.assertEqual([item["channel"] for item in result["notifications"]], ["EMAIL"])

    def test_booking_must_belong_to_passenger(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.return_value = None
        with self.assertRaises(PaymentBookingNotFound):
            confirm_booking_payment(7, 42, lambda: connection)
        connection.rollback.assert_called_once()

    def test_expired_seat_hold_cannot_be_paid(self):
        connection, _ = payment_connection(allocation_expiry=datetime(2026, 11, 1, 9, 59))
        with self.assertRaises(PaymentConfirmationError):
            confirm_booking_payment(7, 42, lambda: connection)
        connection.rollback.assert_called_once()

    def test_invalid_booking_id_is_rejected_before_database_access(self):
        with self.assertRaises(PaymentConfirmationError):
            confirm_booking_payment(7, 0, lambda: self.fail("database should not be called"))


if __name__ == "__main__":
    unittest.main()
