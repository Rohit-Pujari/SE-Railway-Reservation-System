"""Atomic confirmation of pending bookings with segment-aware seat allocation."""

import mysql.connector

from .db import get_db_connection


class BookingConfirmationError(ValueError):
    """A booking cannot be confirmed because it is invalid or no seats remain."""


def confirm_booking(booking_id, user_id, connection_factory=None):
    """Allocate seats and confirm a pending booking in one transaction.

    All confirmations lock the schedule's seat inventory in stable ID order
    before checking allocations. This serializes competing confirmations for
    the same schedule/class; the conflict check then sees the prior transaction
    after it commits. Any failure rolls back booking, passenger allocations,
    and status changes together.
    """
    try:
        booking_id = int(booking_id)
        user_id = int(user_id)
    except (TypeError, ValueError):
        raise BookingConfirmationError("Select a valid booking.") from None
    if booking_id <= 0 or user_id <= 0:
        raise BookingConfirmationError("Select a valid booking.")

    factory = connection_factory or get_db_connection
    connection = cursor = None
    try:
        connection = factory()
        # Explicit transaction: don't rely on connector defaults.
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """SELECT booking_id, user_id, schedule_id, boarding_schedule_stop_id,
                      alighting_schedule_stop_id, class_id, booking_status
               FROM bookings
               WHERE booking_id = %s
               FOR UPDATE""",
            (booking_id,),
        )
        booking = cursor.fetchone()
        if not booking or int(booking["user_id"]) != user_id:
            raise BookingConfirmationError("Booking was not found.")
        if booking["booking_status"] != "PENDING_PAYMENT":
            raise BookingConfirmationError("Only pending bookings can be confirmed.")

        cursor.execute(
            """SELECT stop_sequence
               FROM schedule_stops
               WHERE schedule_id = %s AND schedule_stop_id = %s""",
            (booking["schedule_id"], booking["boarding_schedule_stop_id"]),
        )
        boarding = cursor.fetchone()
        cursor.execute(
            """SELECT stop_sequence
               FROM schedule_stops
               WHERE schedule_id = %s AND schedule_stop_id = %s""",
            (booking["schedule_id"], booking["alighting_schedule_stop_id"]),
        )
        alighting = cursor.fetchone()
        if not boarding or not alighting or int(boarding["stop_sequence"]) >= int(alighting["stop_sequence"]):
            raise BookingConfirmationError("The booking journey is invalid.")

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
            raise BookingConfirmationError("Add at least one passenger before confirming.")

        # Lock the inventory rows, not just matching allocation rows. This
        # provides a stable mutex even when no allocation exists yet.
        cursor.execute(
            """SELECT schedule_seat_id
               FROM schedule_seats
               WHERE schedule_id = %s AND class_id = %s
                 AND operational_status = 'IN_SERVICE'
               ORDER BY schedule_seat_id
               FOR UPDATE""",
            (booking["schedule_id"], booking["class_id"]),
        )
        inventory = cursor.fetchall()
        if len(inventory) < len(passengers):
            raise BookingConfirmationError("Not enough seats are available for this booking.")

        cursor.execute(
            """SELECT available_seat.schedule_seat_id
               FROM schedule_seats AS available_seat
               JOIN seats AS physical_seat
                 ON physical_seat.seat_id = available_seat.seat_id
                AND physical_seat.seat_status = 'ACTIVE'
               WHERE available_seat.schedule_id = %s
                 AND available_seat.class_id = %s
                 AND available_seat.operational_status = 'IN_SERVICE'
                 AND NOT EXISTS (
                     SELECT 1
                     FROM seat_allocations AS allocation
                     JOIN bookings AS occupied_booking
                       ON occupied_booking.booking_id = allocation.booking_id
                     JOIN schedule_stops AS occupied_boarding
                       ON occupied_boarding.schedule_stop_id = occupied_booking.boarding_schedule_stop_id
                     JOIN schedule_stops AS occupied_alighting
                       ON occupied_alighting.schedule_stop_id = occupied_booking.alighting_schedule_stop_id
                     WHERE allocation.schedule_id = available_seat.schedule_id
                       AND allocation.schedule_seat_id = available_seat.schedule_seat_id
                       AND (
                           allocation.allocation_status = 'CONFIRMED'
                           OR (allocation.allocation_status = 'HELD'
                               AND allocation.hold_expires_at > CURRENT_TIMESTAMP)
                       )
                       AND occupied_boarding.stop_sequence < %s
                       AND occupied_alighting.stop_sequence > %s
                 )
               ORDER BY available_seat.schedule_seat_id""",
            (
                booking["schedule_id"], booking["class_id"],
                alighting["stop_sequence"], boarding["stop_sequence"],
            ),
        )
        free_seats = cursor.fetchall()
        if len(free_seats) < len(passengers):
            raise BookingConfirmationError("Not enough seats are available for this journey.")

        for passenger, seat in zip(passengers, free_seats):
            cursor.execute(
                """INSERT INTO seat_allocations
                       (booking_id, schedule_id, class_id, booking_passenger_id,
                        schedule_seat_id, allocation_status, hold_expires_at)
                   VALUES (%s, %s, %s, %s, %s, 'CONFIRMED', NULL)""",
                (
                    booking_id, booking["schedule_id"], booking["class_id"],
                    passenger["booking_passenger_id"], seat["schedule_seat_id"],
                ),
            )

        # Confirmation and allocations are committed atomically.
        cursor.execute(
            """UPDATE bookings
               SET booking_status = 'CONFIRMED', confirmed_at = CURRENT_TIMESTAMP
               WHERE booking_id = %s AND booking_status = 'PENDING_PAYMENT'""",
            (booking_id,),
        )
        if getattr(cursor, "rowcount", 1) != 1:
            raise BookingConfirmationError("Booking status changed; please retry.")
        connection.commit()
        return {"booking_id": booking_id, "allocated_seats": len(passengers), "status": "CONFIRMED"}
    except BookingConfirmationError:
        if connection is not None:
            connection.rollback()
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
