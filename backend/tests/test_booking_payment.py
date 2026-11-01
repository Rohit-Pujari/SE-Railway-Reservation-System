"""Tests for the simulated payment and booking confirmation workflow."""

import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import mysql.connector

from backend.app.booking_payment import (
    PaymentBookingNotFound,
    PaymentConfirmationError,
    confirm_booking_payment,
)


def payment_connection(*, allocation_expiry=None, current_time=None, email="passenger@example.com", phone="9876543210"):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.side_effect = [
        {
            "booking_id": 42, "pnr": "AB23456789CD",
            "booking_status": "PENDING_PAYMENT", "schedule_id": 12, "class_id": 3,
            "total_fare": 850.00,
            "currency_code": "INR", "email": email, "phone_number": phone,
        },
        {"passenger_count": 1},
        {"current_time": current_time or datetime(2026, 11, 1, 10, 0)},
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
        self.assertEqual(cursor.execute.call_count, 10)
        statements = [call.args[0] for call in cursor.execute.call_args_list]
        seat_lock_index = next(i for i, sql in enumerate(statements) if "FROM schedule_seats" in sql)
        expiry_check_index = next(i for i, sql in enumerate(statements) if "CURRENT_TIMESTAMP AS current_time" in sql)
        allocation_lock_index = next(i for i, sql in enumerate(statements) if "FROM seat_allocations" in sql)
        self.assertLess(seat_lock_index, expiry_check_index)
        self.assertLess(expiry_check_index, allocation_lock_index)
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

    def test_payment_rechecks_hold_after_waiting_for_schedule_seat_lock(self):
        # Simulate waiting for the inventory lock until the original hold expires.
        connection, cursor = payment_connection(
            allocation_expiry=datetime(2026, 11, 1, 10, 15),
            current_time=datetime(2026, 11, 1, 10, 16),
        )

        with self.assertRaises(PaymentConfirmationError):
            confirm_booking_payment(7, 42, lambda: connection)

        statements = [call.args[0] for call in cursor.execute.call_args_list]
        seat_lock_index = next(i for i, sql in enumerate(statements) if "FROM schedule_seats" in sql)
        expiry_check_index = next(i for i, sql in enumerate(statements) if "CURRENT_TIMESTAMP AS current_time" in sql)
        self.assertLess(seat_lock_index, expiry_check_index)
        self.assertFalse(any("INSERT INTO payments" in sql for sql in statements))
        connection.rollback.assert_called_once()

    def test_interrupted_confirmation_rolls_back_payment_and_booking_changes(self):
        connection, cursor = payment_connection()

        def interrupt_before_booking_confirmation(sql, params=None):
            if "UPDATE bookings" in sql:
                raise mysql.connector.Error("simulated connection interruption")

        cursor.execute.side_effect = interrupt_before_booking_confirmation
        with self.assertRaises(mysql.connector.Error):
            confirm_booking_payment(7, 42, lambda: connection)

        statements = [call.args[0] for call in cursor.execute.call_args_list]
        self.assertTrue(any("INSERT INTO payments" in sql for sql in statements))
        self.assertTrue(any("UPDATE seat_allocations" in sql for sql in statements))
        self.assertTrue(any("UPDATE bookings" in sql for sql in statements))
        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()
        connection.close.assert_called_once_with()

    def test_retry_after_successful_commit_returns_existing_confirmation(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.side_effect = [
            {
                "booking_id": 42, "pnr": "AB23456789CD",
                "booking_status": "CONFIRMED", "schedule_id": 12, "class_id": 3,
                "total_fare": 850.00, "currency_code": "INR",
                "email": "passenger@example.com", "phone_number": "9876543210",
            },
            {
                "payment_id": 99, "amount": 850.00,
                "currency_code": "INR", "payment_status": "SUCCEEDED",
            },
        ]
        cursor.fetchall.return_value = [
            {"channel": "EMAIL", "delivery_status": "QUEUED"},
            {"channel": "SMS", "delivery_status": "QUEUED"},
        ]

        result = confirm_booking_payment(7, 42, lambda: connection)

        self.assertTrue(result["replayed"])
        self.assertEqual(result["booking_status"], "CONFIRMED")
        self.assertEqual(result["payment_status"], "SUCCEEDED")
        self.assertEqual(result["payment_id"] if "payment_id" in result else 99, 99)
        self.assertFalse(any("INSERT INTO payments" in call.args[0] for call in cursor.execute.call_args_list))
        self.assertFalse(any("UPDATE bookings" in call.args[0] for call in cursor.execute.call_args_list))
        connection.commit.assert_called_once_with()
        connection.rollback.assert_not_called()

    def test_invalid_booking_id_is_rejected_before_database_access(self):
        with self.assertRaises(PaymentConfirmationError):
            confirm_booking_payment(7, 0, lambda: self.fail("database should not be called"))


if __name__ == "__main__":
    unittest.main()
