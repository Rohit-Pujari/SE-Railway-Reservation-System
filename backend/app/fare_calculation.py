"""Fare calculation using the configured route, segment, and travel-class fares."""

from decimal import Decimal, InvalidOperation

import mysql.connector

from .db import get_db_connection


class FareCalculationError(ValueError):
    """The booking cannot be priced with the configured fare rules."""


def calculate_booking_fare(booking_id, user_id, connection_factory=None):
    """Calculate and persist fares for all passengers on an owned pending booking."""
    try:
        booking_id, user_id = int(booking_id), int(user_id)
    except (TypeError, ValueError):
        raise FareCalculationError("Select a valid booking.") from None
    if booking_id <= 0 or user_id <= 0:
        raise FareCalculationError("Select a valid booking.")

    factory = connection_factory or get_db_connection
    connection = cursor = None
    try:
        connection = factory()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """SELECT b.booking_id, b.booking_status, b.schedule_id, b.class_id,
                      b.boarding_schedule_stop_id, b.alighting_schedule_stop_id,
                      b.other_charges, schedule.route_id
               FROM bookings AS b
               JOIN train_schedules AS schedule ON schedule.schedule_id = b.schedule_id
               WHERE b.booking_id = %s AND b.user_id = %s
               FOR UPDATE""",
            (booking_id, user_id),
        )
        booking = cursor.fetchone()
        if not booking:
            raise FareCalculationError("Booking was not found.")
        if booking["booking_status"] != "PENDING_PAYMENT":
            raise FareCalculationError("Fare can only be calculated for a pending booking.")

        cursor.execute(
            """SELECT passenger.booking_passenger_id
               FROM booking_passengers AS passenger
               WHERE passenger.booking_id = %s
               ORDER BY passenger.booking_passenger_id
               FOR UPDATE""",
            (booking_id,),
        )
        passengers = cursor.fetchall()
        if not passengers:
            raise FareCalculationError("Add passenger details before calculating the fare.")

        cursor.execute(
            """SELECT fare.fare_amount, fare.currency_code,
                      origin.stop_sequence AS origin_sequence,
                      destination.stop_sequence AS destination_sequence
               FROM route_fares AS fare
               JOIN route_stops AS origin
                 ON origin.route_id = fare.route_id
                AND origin.route_stop_id = fare.from_route_stop_id
               JOIN route_stops AS destination
                 ON destination.route_id = fare.route_id
                AND destination.route_stop_id = fare.to_route_stop_id
               JOIN schedule_stops AS boarding
                 ON boarding.schedule_id = %s
                AND boarding.schedule_stop_id = %s
                AND boarding.route_stop_id = origin.route_stop_id
               JOIN schedule_stops AS alighting
                 ON alighting.schedule_id = %s
                AND alighting.schedule_stop_id = %s
                AND alighting.route_stop_id = destination.route_stop_id
               JOIN travel_classes AS travel_class
                 ON travel_class.class_id = fare.class_id
               WHERE fare.route_id = %s
                 AND fare.class_id = %s
                 AND travel_class.class_status = 'ACTIVE'
                 AND origin.stop_sequence < destination.stop_sequence
               LIMIT 1""",
            (
                booking["schedule_id"], booking["boarding_schedule_stop_id"],
                booking["schedule_id"], booking["alighting_schedule_stop_id"],
                booking["route_id"], booking["class_id"],
            ),
        )
        fare_row = cursor.fetchone()
        if not fare_row:
            raise FareCalculationError("No fare is configured for this route segment and travel class.")

        passenger_fare = Decimal(str(fare_row["fare_amount"])).quantize(Decimal("0.01"))
        if passenger_fare < 0:
            raise FareCalculationError("Configured fare must not be negative.")
        base_total = (passenger_fare * len(passengers)).quantize(Decimal("0.01"))
        try:
            other_charges = Decimal(str(booking.get("other_charges") or "0.00")).quantize(Decimal("0.01"))
        except (InvalidOperation, ValueError):
            raise FareCalculationError("Booking charges are invalid.") from None
        if other_charges < 0:
            raise FareCalculationError("Booking charges must not be negative.")
        total = (base_total + other_charges).quantize(Decimal("0.01"))

        cursor.execute(
            """UPDATE booking_passengers
               SET passenger_fare = %s
               WHERE booking_id = %s""",
            (passenger_fare, booking_id),
        )
        cursor.execute(
            """UPDATE bookings
               SET base_fare_total = %s, total_fare = %s, currency_code = %s
               WHERE booking_id = %s AND user_id = %s AND booking_status = 'PENDING_PAYMENT'""",
            (base_total, total, fare_row["currency_code"], booking_id, user_id),
        )
        connection.commit()
        return {
            "booking_id": booking_id,
            "passenger_count": len(passengers),
            "currency_code": fare_row["currency_code"],
            "fare_per_passenger": float(passenger_fare),
            "base_fare_total": float(base_total),
            "other_charges": float(other_charges),
            "total_fare": float(total),
        }
    except FareCalculationError:
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
