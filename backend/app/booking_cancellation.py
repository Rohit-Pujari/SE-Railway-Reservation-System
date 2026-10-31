"""Cancel a passenger-owned booking atomically and calculate its refund."""
from decimal import Decimal

from .booking_refunds import calculate_cancellation_refund
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
    """Cancel all remaining passengers and persist calculated refund records.

    Cancellation items, pending refund records, seat releases, and booking
    status are committed atomically. No payment provider is called here.
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
            """SELECT booking_id, pnr, booking_status, departure_at_snapshot,
                      class_code_snapshot, currency_code
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
        cursor.execute("SELECT CURRENT_TIMESTAMP AS current_time")
        current = cursor.fetchone()["current_time"]
        if booking["departure_at_snapshot"] <= current:
            raise BookingCancellationError("A booking cannot be cancelled after its journey has started.")

        cursor.execute(
            """SELECT passenger.booking_passenger_id, passenger.passenger_fare
               FROM booking_passengers AS passenger
               WHERE passenger.booking_id = %s
                 AND NOT EXISTS (
                     SELECT 1 FROM cancellation_items AS prior_item
                     WHERE prior_item.booking_passenger_id = passenger.booking_passenger_id
                       AND prior_item.item_status = 'COMPLETED'
                 )
               ORDER BY passenger.booking_passenger_id
               FOR UPDATE""",
            (target_id,),
        )
        passengers = cursor.fetchall() or []
        if not passengers:
            raise BookingCancellationError("This booking has no passengers left to cancel.")

        cursor.execute(
            """SELECT allocation_id
               FROM seat_allocations
               WHERE booking_id = %s
               ORDER BY allocation_id
               FOR UPDATE""",
            (target_id,),
        )
        cursor.fetchall()

        cursor.execute(
            """SELECT amount, currency_code
               FROM payments
               WHERE booking_id = %s AND payment_status = 'SUCCEEDED'
               ORDER BY completed_at DESC, payment_id DESC
               LIMIT 1
               FOR UPDATE""",
            (target_id,),
        )
        successful_payment = cursor.fetchone()
        paid_amount = (
            Decimal(str(successful_payment["amount"]))
            if successful_payment
            and successful_payment["currency_code"] == booking["currency_code"]
            else Decimal("0.00")
        )
        passenger_fares = [Decimal(str(item["passenger_fare"] or 0)) for item in passengers]
        fare_total = sum(passenger_fares, Decimal("0.00"))
        paid_ratio = min(Decimal("1"), paid_amount / fare_total) if fare_total > 0 else Decimal("0")
        hours_until_departure = (
            booking["departure_at_snapshot"] - current
        ).total_seconds() / 3600

        cursor.execute(
            """INSERT INTO cancellations
                   (booking_id, requested_by_user_id, cancellation_status, reason,
                    requested_at, completed_at)
               VALUES (%s, %s, 'COMPLETED', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)""",
            (target_id, owner_id, reason),
        )
        cancellation_id = cursor.lastrowid

        passenger_refunds = []
        total_charge = Decimal("0.00")
        total_refund = Decimal("0.00")
        remaining_paid = paid_amount
        for index, (passenger, passenger_fare) in enumerate(zip(passengers, passenger_fares)):
            if index == len(passengers) - 1:
                paid_fare = min(passenger_fare, remaining_paid)
            else:
                paid_fare = min(
                    passenger_fare,
                    (passenger_fare * paid_ratio).quantize(Decimal("0.01")),
                )
            remaining_paid = max(Decimal("0.00"), remaining_paid - paid_fare)
            if paid_fare > 0:
                breakdown = calculate_cancellation_refund(
                    paid_fare, booking["class_code_snapshot"], hours_until_departure
                )
            else:
                breakdown = {
                    "cancellation_charge": Decimal("0.00"),
                    "refund_amount": Decimal("0.00"),
                    "policy_band": "NO_SUCCESSFUL_PAYMENT",
                }
            charge = breakdown["cancellation_charge"]
            refund = breakdown["refund_amount"]
            total_charge += charge
            total_refund += refund

            cursor.execute(
                """INSERT INTO cancellation_items
                       (cancellation_id, booking_id, booking_passenger_id, item_status,
                        cancellation_charge, refund_amount, completed_at)
                   VALUES (%s, %s, %s, 'COMPLETED', %s, %s, CURRENT_TIMESTAMP)""",
                (cancellation_id, target_id, passenger["booking_passenger_id"], charge, refund),
            )
            cancellation_item_id = cursor.lastrowid
            if refund > 0:
                cursor.execute(
                    """INSERT INTO refunds
                           (cancellation_item_id, refund_provider, amount, currency_code,
                            refund_status, idempotency_key)
                       VALUES (%s, 'SIMULATED', %s, %s, 'PENDING', %s)""",
                    (
                        cancellation_item_id, refund, booking["currency_code"],
                        f"cancellation-item-{cancellation_item_id}",
                    ),
                )
            passenger_refunds.append({
                "booking_passenger_id": int(passenger["booking_passenger_id"]),
                "cancellation_charge": float(charge),
                "refund_amount": float(refund),
                "policy_band": breakdown["policy_band"],
                "refund_status": "PENDING" if refund > 0 else "NOT_APPLICABLE",
            })

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
        currency = booking["currency_code"]
        message = (
            f"Booking cancelled. Cancellation charges: {currency} {total_charge:.2f}. "
            f"Refund due: {currency} {total_refund:.2f}."
        )
        if total_refund > 0:
            message += " Refund records are pending; no payment provider has been contacted."
        elif not successful_payment:
            message += " No successful payment was found, so no refund is due."
        return {
            "booking_id": target_id,
            "pnr": booking["pnr"],
            "booking_status": "CANCELLED",
            "cancelled_passengers": len(passengers),
            "released_seats": released_seats,
            "currency_code": currency,
            "cancellation_charge": float(total_charge),
            "refund_amount": float(total_refund),
            "refund_status": "PENDING" if total_refund > 0 else "NOT_APPLICABLE",
            "passenger_refunds": passenger_refunds,
            "message": message,
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
