"""Confirm a pending passenger booking with the project's simulated payment provider.

No real card, UPI, bank, email, or SMS provider is configured in this repository.
Successful simulated payments are recorded, held seats are confirmed, and
notification delivery requests are queued in the existing notifications table.
"""

from .db import get_db_connection


class PaymentConfirmationError(ValueError):
    """The booking cannot be paid or its seat hold is no longer valid."""


class PaymentBookingNotFound(LookupError):
    """The booking does not belong to the signed-in passenger."""


def _positive_id(value, field):
    if isinstance(value, bool):
        raise PaymentConfirmationError(f"Enter a valid {field}.")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise PaymentConfirmationError(f"Enter a valid {field}.") from None
    if parsed <= 0 or str(value).strip() != str(parsed):
        raise PaymentConfirmationError(f"Enter a valid {field}.")
    return parsed


def confirm_booking_payment(user_id, booking_id, connection_factory=None):
    """Record one idempotent simulated payment and confirm its held seats."""
    owner_id = _positive_id(user_id, "passenger account")
    target_id = _positive_id(booking_id, "booking")
    connection = cursor = None
    try:
        connection = (connection_factory or get_db_connection)()
        connection.start_transaction(isolation_level="READ COMMITTED")
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """SELECT booking.booking_id, booking.pnr, booking.booking_status,
                      booking.total_fare, booking.currency_code,
                      user.email, user.phone_number
               FROM bookings AS booking
               JOIN users AS user ON user.user_id = booking.user_id
               WHERE booking.booking_id = %s AND booking.user_id = %s
               FOR UPDATE""",
            (target_id, owner_id),
        )
        booking = cursor.fetchone()
        if not booking:
            raise PaymentBookingNotFound("Booking was not found in your account.")

        if booking["booking_status"] == "CONFIRMED":
            cursor.execute(
                """SELECT payment_id, amount, currency_code, payment_status
                   FROM payments
                   WHERE booking_id = %s AND payment_status = 'SUCCEEDED'
                   ORDER BY payment_id DESC LIMIT 1""",
                (target_id,),
            )
            payment = cursor.fetchone()
            if not payment:
                raise PaymentConfirmationError(
                    "This booking is marked confirmed but has no successful payment record. Contact support."
                )
            cursor.execute(
                """SELECT channel, delivery_status FROM notifications
                   WHERE booking_id = %s AND notification_type = 'BOOKING_CONFIRMATION'
                   ORDER BY notification_id""",
                (target_id,),
            )
            notifications = cursor.fetchall() or []
            connection.commit()
            return {
                "booking_id": target_id, "pnr": booking["pnr"],
                "booking_status": "CONFIRMED", "payment_status": "SUCCEEDED",
                "payment_method": "SIMULATED", "amount": float(payment["amount"]),
                "currency_code": payment["currency_code"], "replayed": True,
                "notifications": notifications,
                "message": "This ticket is already confirmed. No duplicate payment was created.",
            }

        if booking["booking_status"] != "PENDING_PAYMENT":
            raise PaymentConfirmationError("Only a pending booking can be paid.")

        cursor.execute("SELECT CURRENT_TIMESTAMP AS current_time")
        current_time = cursor.fetchone()["current_time"]
        cursor.execute(
            """SELECT COUNT(*) AS passenger_count
               FROM booking_passengers WHERE booking_id = %s""",
            (target_id,),
        )
        passenger_count = int(cursor.fetchone()["passenger_count"])
        cursor.execute(
            """SELECT allocation_id, allocation_status, hold_expires_at
               FROM seat_allocations
               WHERE booking_id = %s
               ORDER BY allocation_id
               FOR UPDATE""",
            (target_id,),
        )
        allocations = cursor.fetchall() or []
        if (passenger_count < 1 or len(allocations) != passenger_count
                or any(item["allocation_status"] != "HELD"
                       or item["hold_expires_at"] is None
                       or item["hold_expires_at"] <= current_time
                       for item in allocations)):
            raise PaymentConfirmationError(
                "The seat hold has expired or is incomplete. Start a new booking."
            )

        amount = booking["total_fare"]
        currency = booking["currency_code"]
        idempotency_key = f"booking-confirmation-{target_id}"
        provider_reference = f"SIMULATED-BOOKING-{target_id}"
        cursor.execute(
            """INSERT INTO payments
                   (booking_id, payment_provider, payment_method, amount,
                    currency_code, payment_status, provider_transaction_id,
                    idempotency_key, completed_at)
               VALUES (%s, 'SIMULATED', 'SIMULATED', %s, %s, 'SUCCEEDED',
                       %s, %s, CURRENT_TIMESTAMP)""",
            (target_id, amount, currency, provider_reference, idempotency_key),
        )
        payment_id = int(cursor.lastrowid)

        cursor.execute(
            """UPDATE seat_allocations
               SET allocation_status = 'CONFIRMED'
               WHERE booking_id = %s AND allocation_status = 'HELD'""",
            (target_id,),
        )
        if cursor.rowcount != passenger_count:
            raise PaymentConfirmationError("Seat allocation changed during payment. Please retry.")

        cursor.execute(
            """UPDATE bookings
               SET booking_status = 'CONFIRMED', confirmed_at = CURRENT_TIMESTAMP
               WHERE booking_id = %s AND user_id = %s
                 AND booking_status = 'PENDING_PAYMENT'""",
            (target_id, owner_id),
        )
        if cursor.rowcount != 1:
            raise PaymentConfirmationError("Booking status changed during payment. Please retry.")

        notification_channels = []
        if booking.get("email"):
            notification_channels.append("EMAIL")
        if booking.get("phone_number"):
            notification_channels.append("SMS")
        for channel in notification_channels:
            cursor.execute(
                """INSERT INTO notifications
                       (user_id, booking_id, channel, notification_type, delivery_status)
                   VALUES (%s, %s, %s, 'BOOKING_CONFIRMATION', 'QUEUED')""",
                (owner_id, target_id, channel),
            )

        connection.commit()
        return {
            "booking_id": target_id, "pnr": booking["pnr"],
            "booking_status": "CONFIRMED", "payment_status": "SUCCEEDED",
            "payment_method": "SIMULATED", "payment_id": payment_id,
            "amount": float(amount), "currency_code": currency,
            "replayed": False,
            "notifications": [{"channel": channel, "delivery_status": "QUEUED"}
                             for channel in notification_channels],
            "message": (
                "Payment simulated successfully. Your ticket is confirmed. "
                "Notification requests have been queued; no real email or SMS was sent."
            ),
        }
    except Exception:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
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
