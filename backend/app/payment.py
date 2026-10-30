"""Simulated payment processing against the existing payments schema.

This module deliberately has no real gateway integration or card-data handling.
The caller chooses a simulator outcome so both success and failure flows can be
demonstrated without charging money.
"""

from decimal import Decimal, InvalidOperation
import uuid

import mysql.connector

from .db import get_db_connection


PAYMENT_PROVIDER = "SIMULATED"
PAYMENT_OUTCOMES = {"SUCCESS", "FAILURE"}


class PaymentRequestError(ValueError):
    """The payment request is invalid or its booking cannot be paid."""


class PaymentConflictError(PaymentRequestError):
    """The booking state conflicts with the requested payment operation."""


def process_payment(booking_id, user_id, idempotency_key, simulated_outcome,
                    connection_factory=None):
    """Record a simulated payment and confirm the held booking only on success."""
    try:
        booking_id, user_id = int(booking_id), int(user_id)
    except (TypeError, ValueError):
        raise PaymentRequestError("Select a valid booking.") from None
    if booking_id <= 0 or user_id <= 0:
        raise PaymentRequestError("Select a valid booking.")
    if not isinstance(idempotency_key, str) or not idempotency_key.strip() or len(idempotency_key) > 128:
        raise PaymentRequestError("A valid payment request key is required.")
    if not isinstance(simulated_outcome, str) or simulated_outcome not in PAYMENT_OUTCOMES:
        raise PaymentRequestError("Choose a valid simulated payment outcome.")

    factory = connection_factory or get_db_connection
    connection = cursor = None
    try:
        connection = factory()
        connection.start_transaction(isolation_level="READ COMMITTED")
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """SELECT booking_id, pnr, booking_status, total_fare, currency_code
               FROM bookings
               WHERE booking_id = %s AND user_id = %s
               FOR UPDATE""",
            (booking_id, user_id),
        )
        booking = cursor.fetchone()
        if not booking:
            raise PaymentRequestError("Booking was not found.")

        cursor.execute(
            """SELECT payment_id, booking_id, payment_status, amount, currency_code
               FROM payments
               WHERE payment_provider = %s AND idempotency_key = %s
               FOR UPDATE""",
            (PAYMENT_PROVIDER, idempotency_key.strip()),
        )
        previous = cursor.fetchone()
        if previous:
            if int(previous["booking_id"]) != booking_id:
                raise PaymentConflictError("This payment request key was already used.")
            connection.commit()
            return {
                "payment_id": int(previous["payment_id"]),
                "payment_status": previous["payment_status"],
                "booking_status": booking["booking_status"],
                "amount": float(previous["amount"]),
                "currency_code": previous["currency_code"],
                "pnr": booking["pnr"],
                "replayed": True,
            }

        if booking["booking_status"] != "PENDING_PAYMENT":
            raise PaymentConflictError("Only pending bookings can be paid.")

        cursor.execute(
            """SELECT payment_id
               FROM payments
               WHERE booking_id = %s AND payment_status = 'SUCCEEDED'
               LIMIT 1
               FOR UPDATE""",
            (booking_id,),
        )
        if cursor.fetchone():
            raise PaymentConflictError("This booking has already been paid.")

        try:
            amount = Decimal(str(booking["total_fare"])).quantize(Decimal("0.01"))
        except (InvalidOperation, TypeError, ValueError):
            raise PaymentRequestError("The booking amount is invalid.") from None
        if amount < 0 or not booking["currency_code"]:
            raise PaymentRequestError("The booking amount is not payable.")

        cursor.execute(
            """SELECT booking_passenger_id
               FROM booking_passengers
               WHERE booking_id = %s
               ORDER BY booking_passenger_id
               FOR UPDATE""",
            (booking_id,),
        )
        passengers = cursor.fetchall()
        if not passengers:
            raise PaymentConflictError("Add passenger details before paying.")

        cursor.execute(
            """SELECT allocation_id
               FROM seat_allocations
               WHERE booking_id = %s
                 AND allocation_status = 'HELD'
                 AND hold_expires_at > CURRENT_TIMESTAMP
               ORDER BY schedule_seat_id
               FOR UPDATE""",
            (booking_id,),
        )
        held_allocations = cursor.fetchall()
        if len(held_allocations) != len(passengers):
            raise PaymentConflictError("The seat hold has expired. Start a new booking.")

        cursor.execute(
            """INSERT INTO payments (
                   booking_id, payment_provider, payment_method, amount,
                   currency_code, payment_status, idempotency_key
               ) VALUES (%s, %s, 'SIMULATED', %s, %s, 'INITIATED', %s)""",
            (booking_id, PAYMENT_PROVIDER, amount, booking["currency_code"], idempotency_key.strip()),
        )
        payment_id = int(cursor.lastrowid)
        succeeded = simulated_outcome == "SUCCESS"
        payment_status = "SUCCEEDED" if succeeded else "FAILED"
        transaction_id = f"SIM-{uuid.uuid4().hex}" if succeeded else None
        failure_code = None if succeeded else "SIMULATED_DECLINE"
        cursor.execute(
            """UPDATE payments
               SET payment_status = %s, provider_transaction_id = %s,
                   failure_code = %s, completed_at = CURRENT_TIMESTAMP
               WHERE payment_id = %s AND payment_status = 'INITIATED'""",
            (payment_status, transaction_id, failure_code, payment_id),
        )

        booking_status = booking["booking_status"]
        if succeeded:
            cursor.execute(
                """UPDATE bookings
                   SET booking_status = 'CONFIRMED', confirmed_at = CURRENT_TIMESTAMP
                   WHERE booking_id = %s AND user_id = %s
                     AND booking_status = 'PENDING_PAYMENT'""",
                (booking_id, user_id),
            )
            if getattr(cursor, "rowcount", 1) != 1:
                raise PaymentConflictError("Booking status changed; please retry.")
            cursor.execute(
                """UPDATE seat_allocations
                   SET allocation_status = 'CONFIRMED', hold_expires_at = NULL
                   WHERE booking_id = %s AND allocation_status = 'HELD'
                     AND hold_expires_at > CURRENT_TIMESTAMP""",
                (booking_id,),
            )
            if getattr(cursor, "rowcount", len(passengers)) != len(passengers):
                raise PaymentConflictError("The seat hold expired while payment was processing.")
            booking_status = "CONFIRMED"

        connection.commit()
        return {
            "payment_id": payment_id,
            "payment_status": payment_status,
            "booking_status": booking_status,
            "amount": float(amount),
            "currency_code": booking["currency_code"],
            "pnr": booking["pnr"],
            "replayed": False,
        }
    except PaymentRequestError:
        if connection is not None:
            connection.rollback()
        raise
    except mysql.connector.IntegrityError as exc:
        if connection is not None:
            connection.rollback()
        if getattr(exc, "errno", None) == 1062 and "uq_payment_idempotency" in str(exc).lower():
            raise PaymentConflictError("This payment request key was already used.") from None
        raise
    except mysql.connector.Error:
        if connection is not None:
            connection.rollback()
        raise
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
