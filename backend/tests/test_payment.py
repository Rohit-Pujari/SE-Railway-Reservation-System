"""Tests for simulated payment recording and booking confirmation."""

import unittest
from decimal import Decimal
from unittest.mock import MagicMock, patch

import mysql.connector

from backend.app.payment import PaymentConflictError, PaymentRequestError, process_payment
from backend.tests.drf_client import RailwayAPIClient, set_session


def configured_connection(*, held_count=2):
    connection = MagicMock()
    cursor = connection.cursor.return_value
    cursor.fetchone.side_effect = [
        {
            "booking_id": 41,
            "pnr": "AB23456789CD",
            "booking_status": "PENDING_PAYMENT",
            "total_fare": Decimal("251.00"),
            "currency_code": "INR",
        },
        None,
        None,
    ]
    cursor.fetchall.side_effect = [
        [{"booking_passenger_id": 501}, {"booking_passenger_id": 502}],
        [{"allocation_id": 601 + index} for index in range(held_count)],
    ]
    cursor.lastrowid = 801

    def set_rowcount(sql, params=None):
        if "UPDATE payments" in sql or "UPDATE bookings" in sql:
            cursor.rowcount = 1
        elif "UPDATE seat_allocations" in sql:
            cursor.rowcount = held_count

    cursor.execute.side_effect = set_rowcount
    return connection


class PaymentServiceTests(unittest.TestCase):
    def process(self, connection, outcome="SUCCESS", key="payment-key"):
        return process_payment(41, 7, key, outcome, connection_factory=lambda: connection)

    def test_success_records_payment_and_confirms_booking_and_held_seats(self):
        connection = configured_connection()
        result = self.process(connection)

        self.assertEqual(result["payment_status"], "SUCCEEDED")
        self.assertEqual(result["booking_status"], "CONFIRMED")
        self.assertEqual(result["amount"], 251.0)
        self.assertEqual(result["currency_code"], "INR")
        self.assertEqual(result["pnr"], "AB23456789CD")
        connection.commit.assert_called_once_with()
        connection.rollback.assert_not_called()
        sql_calls = connection.cursor.return_value.execute.call_args_list
        self.assertTrue(any("INSERT INTO payments" in call.args[0] for call in sql_calls))
        self.assertTrue(any("UPDATE bookings" in call.args[0] and "'CONFIRMED'" in call.args[0] for call in sql_calls))
        self.assertTrue(any("UPDATE seat_allocations" in call.args[0] and "'CONFIRMED'" in call.args[0] for call in sql_calls))
        payment_insert = next(call for call in sql_calls if "INSERT INTO payments" in call.args[0])
        self.assertEqual(payment_insert.args[1][2], Decimal("251.00"))
        self.assertEqual(payment_insert.args[1][3], "INR")
        connection.close.assert_called_once_with()

    def test_failure_is_recorded_without_confirming_booking_or_releasing_hold(self):
        connection = configured_connection()
        result = self.process(connection, outcome="FAILURE")

        self.assertEqual(result["payment_status"], "FAILED")
        self.assertEqual(result["booking_status"], "PENDING_PAYMENT")
        connection.commit.assert_called_once_with()
        sql_calls = connection.cursor.return_value.execute.call_args_list
        self.assertFalse(any("UPDATE bookings" in call.args[0] for call in sql_calls))
        self.assertFalse(any("UPDATE seat_allocations" in call.args[0] for call in sql_calls))
        payment_update = next(call for call in sql_calls if "UPDATE payments" in call.args[0])
        self.assertEqual(payment_update.args[1][0], "FAILED")
        self.assertEqual(payment_update.args[1][2], "SIMULATED_DECLINE")

    def test_retry_after_failure_can_succeed_while_seat_hold_is_active(self):
        failed_attempt = configured_connection()
        retry_attempt = configured_connection()

        failed = self.process(failed_attempt, outcome="FAILURE", key="attempt-one")
        succeeded = self.process(retry_attempt, outcome="SUCCESS", key="attempt-two")

        self.assertEqual(failed["payment_status"], "FAILED")
        self.assertEqual(failed["booking_status"], "PENDING_PAYMENT")
        self.assertEqual(succeeded["payment_status"], "SUCCEEDED")
        self.assertEqual(succeeded["booking_status"], "CONFIRMED")
        failed_attempt.commit.assert_called_once_with()
        retry_attempt.commit.assert_called_once_with()

    def test_payment_idempotency_replays_existing_attempt(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value
        cursor.fetchone.side_effect = [
            {"booking_id": 41, "pnr": "AB23456789CD", "booking_status": "CONFIRMED",
             "total_fare": Decimal("251.00"), "currency_code": "INR"},
            {"payment_id": 801, "booking_id": 41, "payment_status": "SUCCEEDED",
             "amount": Decimal("251.00"), "currency_code": "INR"},
        ]

        result = self.process(connection)

        self.assertTrue(result["replayed"])
        self.assertEqual(result["payment_id"], 801)
        self.assertEqual(result["payment_status"], "SUCCEEDED")
        self.assertEqual(cursor.execute.call_count, 2)
        connection.commit.assert_called_once_with()
        connection.close.assert_called_once_with()

    def test_cannot_reuse_payment_key_for_another_booking(self):
        connection = MagicMock()
        connection.cursor.return_value.fetchone.side_effect = [
            {"booking_id": 41, "pnr": "AB23456789CD", "booking_status": "PENDING_PAYMENT",
             "total_fare": Decimal("251.00"), "currency_code": "INR"},
            {"payment_id": 802, "booking_id": 42, "payment_status": "FAILED",
             "amount": Decimal("80.00"), "currency_code": "INR"},
        ]
        with self.assertRaisesRegex(PaymentConflictError, "already used"):
            self.process(connection)
        connection.rollback.assert_called_once_with()
        self.assertEqual(connection.cursor.return_value.execute.call_count, 2)

    def test_booking_not_owned_by_passenger_is_not_payable(self):
        connection = MagicMock()
        connection.cursor.return_value.fetchone.return_value = None
        with self.assertRaisesRegex(PaymentRequestError, "not found"):
            self.process(connection)
        connection.rollback.assert_called_once_with()
        connection.cursor.return_value.execute.assert_called_once()

    def test_expired_or_incomplete_hold_is_rejected(self):
        connection = configured_connection(held_count=1)
        with self.assertRaisesRegex(PaymentConflictError, "seat hold has expired"):
            self.process(connection)

        connection.rollback.assert_called_once_with()
        self.assertFalse(any("INSERT INTO payments" in call.args[0]
                             for call in connection.cursor.return_value.execute.call_args_list))

    def test_invalid_outcome_is_rejected_before_database_access(self):
        factory = MagicMock()
        with self.assertRaises(PaymentRequestError):
            process_payment(41, 7, "payment-key", "SUCCESSFUL", connection_factory=factory)
        factory.assert_not_called()

    def test_database_failure_rolls_back(self):
        connection = MagicMock()
        connection.cursor.return_value.execute.side_effect = mysql.connector.Error("db down")
        with self.assertRaises(mysql.connector.Error):
            self.process(connection)
        connection.rollback.assert_called_once_with()
        connection.commit.assert_not_called()
        connection.close.assert_called_once_with()


class PaymentEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = RailwayAPIClient()

    def test_anonymous_user_cannot_pay(self):
        response = self.client.post("/api/bookings/41/payment", json={})
        self.assertEqual(response.status_code, 401)

    @patch("backend.app.django_views.process_payment")
    def test_authenticated_user_can_submit_simulated_payment(self, process):
        process.return_value = {
            "payment_id": 801, "payment_status": "SUCCEEDED", "booking_status": "CONFIRMED",
            "amount": 251.0, "currency_code": "INR", "pnr": "AB23456789CD", "replayed": False,
        }
        set_session(self.client, user_id=7, role="PASSENGER")
        response = self.client.post("/api/bookings/41/payment", json={
            "idempotency_key": "payment-key", "simulated_outcome": "SUCCESS",
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["booking_status"], "CONFIRMED")
        process.assert_called_once_with(41, 7, "payment-key", "SUCCESS")

    @patch("backend.app.django_views.process_payment")
    def test_failed_payment_is_returned_for_retry(self, process):
        process.return_value = {
            "payment_id": 801, "payment_status": "FAILED", "booking_status": "PENDING_PAYMENT",
            "amount": 251.0, "currency_code": "INR", "pnr": "AB23456789CD", "replayed": False,
        }
        set_session(self.client, user_id=7, role="PASSENGER")
        response = self.client.post("/api/bookings/41/payment", json={
            "idempotency_key": "payment-key", "simulated_outcome": "FAILURE", "amount": 0,
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["payment_status"], "FAILED")
        self.assertEqual(response.json()["booking_status"], "PENDING_PAYMENT")
        process.assert_called_once_with(41, 7, "payment-key", "FAILURE")

    @patch("backend.app.django_views.process_payment")
    def test_failed_payment_can_be_retried_and_confirmed(self, process):
        process.side_effect = [
            {
                "payment_id": 801, "payment_status": "FAILED", "booking_status": "PENDING_PAYMENT",
                "amount": 251.0, "currency_code": "INR", "pnr": "AB23456789CD", "replayed": False,
            },
            {
                "payment_id": 802, "payment_status": "SUCCEEDED", "booking_status": "CONFIRMED",
                "amount": 251.0, "currency_code": "INR", "pnr": "AB23456789CD", "replayed": False,
            },
        ]
        set_session(self.client, user_id=7, role="PASSENGER")

        failed = self.client.post("/api/bookings/41/payment", json={
            "idempotency_key": "attempt-one", "simulated_outcome": "FAILURE",
        })
        retried = self.client.post("/api/bookings/41/payment", json={
            "idempotency_key": "attempt-two", "simulated_outcome": "SUCCESS",
        })

        self.assertEqual(failed.status_code, 201)
        self.assertEqual(failed.json()["payment_status"], "FAILED")
        self.assertEqual(failed.json()["booking_status"], "PENDING_PAYMENT")
        self.assertEqual(retried.status_code, 201)
        self.assertEqual(retried.json()["payment_status"], "SUCCEEDED")
        self.assertEqual(retried.json()["booking_status"], "CONFIRMED")
        self.assertEqual([call.args for call in process.call_args_list], [
            (41, 7, "attempt-one", "FAILURE"),
            (41, 7, "attempt-two", "SUCCESS"),
        ])


if __name__ == "__main__":
    unittest.main()
