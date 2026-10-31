"""Cancel a passenger-owned booking atomically and release its seat holds."""
from .db import get_db_connection


class BookingCancellationError(ValueError):
    """The cancellation request is invalid or the booking cannot be cancelled."""


class BookingCancellationNotFound(LookupError):
    """No booking with this ID belongs to the signed-in passenger."""


def _positive_id(value, field):
    if isinstance(value, bool):
        raise BookingCancellationError(f"Enter a valid {field}.")
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise BookingCancellationError(f"Enter a valid {field}.") from None
    if number <= 0 or str(value).strip() != str(number):
        raise BookingCancellationError(f"Enter a valid {field}.")
    return number


def cancel_booking(user_id, booking_id, reason=None, connection_factory=None):
    """Cancel all remaining passengers on a booking owned by user_id.

    Booking, cancellation audit rows, passenger cancellation items, and seat
    releases are committed in one transaction. Refund processing is separate.
    """
    owner_id = _positive_id(user_id, "passenger account")
    target_id = _positive_id(booking_id, "booking")
    if reason is not None and not isinstance(reason, str):
        raise BookingCancellationError("Enter a valid cancellation reason.")
    reason = reason.strip()[:255] if reason else None

    connection = cursor = None
    try:
        connection = (connection_factory or get_db_connection)()
        connection.start_transaction(isolation_level="READ COMMITTED")
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """SELECT booking_id, pnr, booking_status, departure_at_snapshot
               FROM bookings
               WHERE booking_id = %s AND user_id = %s
               FOR UPDATE""",
            (target_id, owner_id),
        )
        booking = cursor.fetchone()
        if not booking:
            raise BookingCancellationNotFound("Booking was not found in your account.")
        status = booking["booking_status"]
        if status == "CANCELLED":
            raise BookingCancellationError("This booking has already been cancelled.")
        if status in ("EXPIRED", "PAYMENT_FAILED"):
            raise BookingCancellationError("This booking is no longer active and cannot be cancelled.")
        if status not in ("PENDING_PAYMENT", "CONFIRMED", "PARTIALLY_CANCELLED"):
            raise BookingCancellationError("This booking cannot be cancelled.")
        cursor.execute(
            "SELECT CURRENT_TIMESTAMP AS current_time"
        )
        current = cursor.fetchone()["current_time"]
        if booking["departure_at_snapshot"] <= current:
            raise BookingCancellationError("A booking cannot be cancelled after its journey has started.")

        cursor.execute(
            """SELECT booking_passenger_id
               FROM booking_passengers
               WHERE booking_id = %s
               ORDER BY booking_passenger_id
               FOR UPDATE""",
            (target_id,),
        )
        passengers = cursor.fetchall() or []
        if not passengers:
            raise BookingCancellationError("This booking has no passengers to cancel.")

        cursor.execute(
            """SELECT allocation_id
               FROM seat_allocations
               WHERE booking_id = %s
               ORDER BY allocation_id
               FOR UPDATE""",
            (target_id,),
        )
        allocations = cursor.fetchall() or []

        cursor.execute(
            """INSERT INTO cancellations
                   (booking_id, requested_by_user_id, cancellation_status, reason,
                    requested_at, completed_at)
               VALUES (%s, %s, 'COMPLETED', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (target_id, owner_id, reason),
        )
        cancellation_id = cursor.lastrowid

        for passenger in passengers:
            cursor.execute(
                """INSERT INTO cancellation_items
                       (cancellation_id, booking_id, booking_passenger_id, item_status,
                        cancellation_charge, refund_amount, completed_at)
                   VALUES (%s, %s, %s, 'COMPLETED', 0.00, 0.00, CURRENT_TIMESTAMP)""",
                (cancellation_id, target_id, passenger["booking_passenger_id"]),
            )

        cursor.execute(
            """UPDATE seat_allocations
               SET allocation_status = 'RELEASED',
                   released_at = CURRENT_TIMESTAMP
               WHERE booking_id = %s
                 AND allocation_status IN ('HELD', 'CONFIRMED')""",
            (target_id,),
        )
        released_seats = cursor.rowcount

        cursor.execute(
            """UPDATE bookings
               SET booking_status = 'CANCELLED'
               WHERE booking_id = %s AND user_id = %s""",
            (target_id, owner_id),
        )
        if cursor.rowcount != 1:
            raise BookingCancellationError("The booking changed while it was being cancelled. Please retry.")

        connection.commit()
        return {
            "booking_id": target_id,
            "pnr": booking["pnr"],
            "booking_status": "CANCELLED",
            "cancelled_passengers": len(passengers),
            "released_seats": released_seats,
            "message": "Booking cancelled successfully. Any applicable refund is handled separately.",
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
