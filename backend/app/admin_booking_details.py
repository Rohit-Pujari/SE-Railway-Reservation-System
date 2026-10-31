"""Administrator-only detailed view of a passenger reservation."""

from .db import get_db_connection


def _iso(value):
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else value


def _amount(value):
    return float(value) if value is not None else 0.0


def get_admin_booking_details(booking_id, connection_factory=None):
    """Return one booking with owner, passengers, seats, payments and refunds."""
    if isinstance(booking_id, bool):
        raise ValueError("Enter a valid booking ID.")
    try:
        identifier = int(booking_id)
    except (TypeError, ValueError):
        raise ValueError("Enter a valid booking ID.") from None
    if identifier <= 0 or str(booking_id).strip() != str(identifier):
        raise ValueError("Enter a valid booking ID.")

    connection = cursor = None
    try:
        connection = (connection_factory or get_db_connection)()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """SELECT booking.booking_id, booking.pnr, booking.booking_status,
                      booking.train_number_snapshot, booking.train_name_snapshot,
                      booking.boarding_station_code_snapshot,
                      booking.boarding_station_name_snapshot,
                      booking.alighting_station_code_snapshot,
                      booking.alighting_station_name_snapshot,
                      booking.departure_at_snapshot, booking.arrival_at_snapshot,
                      booking.class_code_snapshot, booking.base_fare_total,
                      booking.other_charges, booking.total_fare, booking.currency_code,
                      booking.created_at, booking.confirmed_at,
                      user.user_id, user.full_name AS account_name, user.email,
                      user.phone_number
               FROM bookings AS booking
               JOIN users AS user ON user.user_id = booking.user_id
               WHERE booking.booking_id = %s
               LIMIT 1""",
            (identifier,),
        )
        booking = cursor.fetchone()
        if booking is None:
            return None
        for field in ("departure_at_snapshot", "arrival_at_snapshot", "created_at", "confirmed_at"):
            booking[field] = _iso(booking[field])
        for field in ("base_fare_total", "other_charges", "total_fare"):
            booking[field] = _amount(booking[field])
        booking["user_id"] = int(booking["user_id"])

        cursor.execute(
            """SELECT passenger.booking_passenger_id, passenger.passenger_name,
                      passenger.age, passenger.gender, passenger.berth_preference,
                      passenger.passenger_fare, allocation.allocation_status,
                      allocation.hold_expires_at, allocation.allocated_at,
                      allocation.released_at, physical_seat.coach_number,
                      physical_seat.seat_number
               FROM booking_passengers AS passenger
               LEFT JOIN seat_allocations AS allocation
                 ON allocation.booking_id = passenger.booking_id
                AND allocation.booking_passenger_id = passenger.booking_passenger_id
               LEFT JOIN schedule_seats AS scheduled_seat
                 ON scheduled_seat.schedule_id = allocation.schedule_id
                AND scheduled_seat.schedule_seat_id = allocation.schedule_seat_id
               LEFT JOIN seats AS physical_seat
                 ON physical_seat.seat_id = scheduled_seat.seat_id
               WHERE passenger.booking_id = %s
               ORDER BY passenger.booking_passenger_id""",
            (identifier,),
        )
        passengers = cursor.fetchall() or []
        for passenger in passengers:
            passenger["booking_passenger_id"] = int(passenger["booking_passenger_id"])
            passenger["age"] = int(passenger["age"])
            passenger["passenger_fare"] = _amount(passenger["passenger_fare"])
            for field in ("hold_expires_at", "allocated_at", "released_at"):
                passenger[field] = _iso(passenger[field])

        cursor.execute(
            """SELECT payment_id, payment_provider, payment_method, amount,
                      currency_code, payment_status, provider_transaction_id,
                      failure_code, created_at, completed_at
               FROM payments
               WHERE booking_id = %s
               ORDER BY created_at DESC, payment_id DESC""",
            (identifier,),
        )
        payments = cursor.fetchall() or []
        for payment in payments:
            payment["payment_id"] = int(payment["payment_id"])
            payment["amount"] = _amount(payment["amount"])
            payment["created_at"] = _iso(payment["created_at"])
            payment["completed_at"] = _iso(payment["completed_at"])

        cursor.execute(
            """SELECT cancellation.cancellation_id, cancellation.cancellation_status,
                      cancellation.reason, cancellation.requested_at,
                      cancellation.completed_at, item.cancellation_item_id,
                      item.item_status, passenger.passenger_name,
                      item.cancellation_charge, item.refund_amount,
                      refund.refund_status, refund.amount AS refunded_amount,
                      refund.currency_code AS refund_currency,
                      refund.created_at AS refund_created_at
               FROM cancellations AS cancellation
               LEFT JOIN cancellation_items AS item
                 ON item.cancellation_id = cancellation.cancellation_id
               LEFT JOIN booking_passengers AS passenger
                 ON passenger.booking_passenger_id = item.booking_passenger_id
               LEFT JOIN refunds AS refund
                 ON refund.cancellation_item_id = item.cancellation_item_id
               WHERE cancellation.booking_id = %s
               ORDER BY cancellation.requested_at DESC, item.cancellation_item_id""",
            (identifier,),
        )
        cancellations = cursor.fetchall() or []
        for item in cancellations:
            for field in ("requested_at", "completed_at", "refund_created_at"):
                item[field] = _iso(item[field])
            for field in ("cancellation_charge", "refund_amount", "refunded_amount"):
                item[field] = _amount(item[field])
        return {
            "booking": booking,
            "passengers": passengers,
            "payments": payments,
            "cancellations": cancellations,
        }
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()
