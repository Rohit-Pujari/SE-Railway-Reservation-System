"""Atomically reserve seats and create a pending train booking."""

from datetime import date, datetime, time, timedelta
from decimal import Decimal
import secrets

import mysql.connector

from .db import get_db_connection
from .passenger_details import validate_passengers

MAX_PASSENGERS = 6
SEAT_HOLD_MINUTES = 15
PNR_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


class BookingRequestError(ValueError):
    """The booking request is malformed or cannot be completed."""


class BookingUnavailableError(BookingRequestError):
    """The selected train, class, or seat count is unavailable."""


def _positive_int(value, label):
    if isinstance(value, bool):
        raise BookingRequestError(f"Select a valid {label}.")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise BookingRequestError(f"Select a valid {label}.") from None
    if parsed <= 0 or str(value).strip() != str(parsed):
        raise BookingRequestError(f"Select a valid {label}.")
    return parsed


def _validate_request(user_id, schedule_id, source_station_id, destination_station_id,
                      journey_date, class_id, idempotency_key):
    user = _positive_int(user_id, "passenger")
    schedule = _positive_int(schedule_id, "train")
    source = _positive_int(source_station_id, "source station")
    destination = _positive_int(destination_station_id, "destination station")
    travel_class = _positive_int(class_id, "travel class")
    if source == destination:
        raise BookingRequestError("Source and destination stations must be different.")
    if not isinstance(journey_date, str):
        raise BookingRequestError("Select a journey date.")
    try:
        parsed_date = date.fromisoformat(journey_date)
    except ValueError:
        raise BookingRequestError("Journey date must use YYYY-MM-DD format.") from None
    if parsed_date.isoformat() != journey_date:
        raise BookingRequestError("Journey date must use YYYY-MM-DD format.")
    if not isinstance(idempotency_key, str) or not idempotency_key.strip() or len(idempotency_key) > 128:
        raise BookingRequestError("A valid booking request key is required.")
    return user, schedule, source, destination, parsed_date, travel_class, idempotency_key.strip()


def _new_pnr():
    return "".join(secrets.choice(PNR_ALPHABET) for _ in range(10))


def _active_allocated_seats(cursor, booking_id):
    cursor.execute(
        """SELECT physical_seat.coach_number, physical_seat.seat_number
           FROM seat_allocations AS allocation
           JOIN schedule_seats AS scheduled_seat
             ON scheduled_seat.schedule_seat_id = allocation.schedule_seat_id
           JOIN seats AS physical_seat ON physical_seat.seat_id = scheduled_seat.seat_id
           WHERE allocation.booking_id = %s
             AND (allocation.allocation_status = 'CONFIRMED'
                  OR (allocation.allocation_status = 'HELD'
                      AND allocation.hold_expires_at > CURRENT_TIMESTAMP))
           ORDER BY scheduled_seat.schedule_seat_id""",
        (booking_id,),
    )
    return [
        {"coach_number": row["coach_number"], "seat_number": row["seat_number"]}
        for row in cursor.fetchall()
    ]


def create_booking(user_id, schedule_id, source_station_id, destination_station_id,
                   journey_date, class_id, passengers, idempotency_key,
                   connection_factory=None):
    """Create a PENDING_PAYMENT booking and hold all its seats atomically.

    The schedule inventory is locked in stable order before availability is
    checked. Booking, passenger fares, and expiring seat holds commit together.
    Payment is a separate workflow; these holds expire after 15 minutes.
    """
    validated_passengers = validate_passengers(passengers)
    if len(validated_passengers) > MAX_PASSENGERS:
        raise BookingRequestError(f"A booking can include at most {MAX_PASSENGERS} passengers.")
    (user, schedule, source, destination, travel_date, travel_class,
     request_key) = _validate_request(
        user_id, schedule_id, source_station_id, destination_station_id,
        journey_date, class_id, idempotency_key,
    )
    start_at = datetime.combine(travel_date, time.min)
    end_at = start_at + timedelta(days=1)
    factory = connection_factory or get_db_connection
    connection = cursor = None
    try:
        connection = factory()
        connection.start_transaction(isolation_level="READ COMMITTED")
        cursor = connection.cursor(dictionary=True)

        cursor.execute(
            """SELECT user_id FROM users
               WHERE user_id = %s AND role = 'PASSENGER' AND account_status = 'ACTIVE'
               FOR UPDATE""",
            (user,),
        )
        if not cursor.fetchone():
            raise BookingUnavailableError("This passenger account is not active.")

        # Repeated HTTP submissions with the same key return the first booking.
        cursor.execute(
            """SELECT booking.booking_id, booking.pnr, booking.schedule_id,
                      booking.class_id, booking.booking_status, booking.total_fare,
                      booking.currency_code,
                      boarding.station_id AS source_station_id,
                      alighting.station_id AS destination_station_id,
                      (SELECT COUNT(*) FROM booking_passengers AS passenger
                       WHERE passenger.booking_id = booking.booking_id) AS passenger_count,
                      (SELECT MAX(allocation.hold_expires_at) FROM seat_allocations AS allocation
                       WHERE allocation.booking_id = booking.booking_id) AS hold_expires_at
               FROM bookings AS booking
               JOIN schedule_stops AS boarding
                 ON boarding.schedule_id = booking.schedule_id
                AND boarding.schedule_stop_id = booking.boarding_schedule_stop_id
               JOIN schedule_stops AS alighting
                 ON alighting.schedule_id = booking.schedule_id
                AND alighting.schedule_stop_id = booking.alighting_schedule_stop_id
               WHERE booking.user_id = %s AND booking.idempotency_key = %s
               FOR UPDATE""",
            (user, request_key),
        )
        existing = cursor.fetchone()
        if existing:
            if (
                int(existing["schedule_id"]) != schedule
                or int(existing["class_id"]) != travel_class
                or int(existing["source_station_id"]) != source
                or int(existing["destination_station_id"]) != destination
                or int(existing["passenger_count"]) != len(validated_passengers)
            ):
                raise BookingUnavailableError("This booking request key was already used.")
            assignments = _active_allocated_seats(cursor, existing["booking_id"])
            if len(assignments) != len(validated_passengers):
                raise BookingUnavailableError("The seat hold for this booking has expired. Start a new booking.")
            connection.commit()
            return {
                "booking_id": int(existing["booking_id"]),
                "pnr": existing["pnr"],
                "status": existing["booking_status"],
                "assigned_seats": assignments,
                "currency_code": existing["currency_code"],
                "total_fare": float(existing["total_fare"]),
                "hold_expires_at": (
                    existing["hold_expires_at"].isoformat()
                    if existing["hold_expires_at"] else None
                ),
                "replayed": True,
            }

        cursor.execute(
            """SELECT schedule.schedule_id, schedule.route_id,
                      train.train_number, train.train_name,
                      origin_stop.schedule_stop_id AS boarding_stop_id,
                      origin_stop.route_stop_id AS boarding_route_stop_id,
                      origin_stop.stop_sequence AS boarding_sequence,
                      origin_stop.departure_at,
                      source.station_code AS source_code,
                      source.station_name AS source_name,
                      destination_stop.schedule_stop_id AS alighting_stop_id,
                      destination_stop.route_stop_id AS alighting_route_stop_id,
                      destination_stop.stop_sequence AS alighting_sequence,
                      destination_stop.arrival_at,
                      destination.station_code AS destination_code,
                      destination.station_name AS destination_name,
                      travel_class.class_code
               FROM train_schedules AS schedule
               JOIN trains AS train ON train.train_id = schedule.train_id
               JOIN routes AS route ON route.route_id = schedule.route_id
               JOIN schedule_stops AS origin_stop
                 ON origin_stop.schedule_id = schedule.schedule_id
                AND origin_stop.station_id = %s
               JOIN stations AS source ON source.station_id = origin_stop.station_id
               JOIN schedule_stops AS destination_stop
                 ON destination_stop.schedule_id = schedule.schedule_id
                AND destination_stop.station_id = %s
               JOIN stations AS destination ON destination.station_id = destination_stop.station_id
               JOIN travel_classes AS travel_class ON travel_class.class_id = %s
               WHERE schedule.schedule_id = %s
                 AND origin_stop.stop_sequence < destination_stop.stop_sequence
                 AND origin_stop.departure_at >= %s
                 AND origin_stop.departure_at < %s
                 AND destination_stop.arrival_at IS NOT NULL
                 AND schedule.schedule_status = 'SCHEDULED'
                 AND train.train_status = 'ACTIVE'
                 AND route.route_status = 'ACTIVE'
                 AND source.station_status = 'ACTIVE'
                 AND destination.station_status = 'ACTIVE'
                 AND travel_class.class_status = 'ACTIVE'
               ORDER BY origin_stop.stop_sequence, destination_stop.stop_sequence
               LIMIT 1
               FOR UPDATE""",
            (source, destination, travel_class, schedule, start_at, end_at),
        )
        itinerary = cursor.fetchone()
        if not itinerary:
            raise BookingUnavailableError("This train is no longer available for the selected journey.")

        # Lock every in-service seat for this schedule/class to serialize
        # booking attempts with the same locks used by booking confirmation.
        cursor.execute(
            """SELECT schedule_seat_id
               FROM schedule_seats
               WHERE schedule_id = %s AND class_id = %s
                 AND operational_status = 'IN_SERVICE'
               ORDER BY schedule_seat_id
               FOR UPDATE""",
            (schedule, travel_class),
        )
        cursor.fetchall()
        cursor.execute(
            """SELECT available_seat.schedule_seat_id,
                      physical_seat.coach_number, physical_seat.seat_number
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
               ORDER BY available_seat.schedule_seat_id
               FOR UPDATE""",
            (schedule, travel_class, itinerary["alighting_sequence"], itinerary["boarding_sequence"]),
        )
        free_seats = cursor.fetchall()
        if len(free_seats) < len(validated_passengers):
            raise BookingUnavailableError(
                f"Only {len(free_seats)} seat(s) remain for this journey; choose fewer passengers or another train."
            )

        cursor.execute(
            """SELECT fare.fare_amount, fare.currency_code
               FROM route_fares AS fare
               WHERE fare.route_id = %s
                 AND fare.from_route_stop_id = %s
                 AND fare.to_route_stop_id = %s
                 AND fare.class_id = %s""",
            (
                itinerary["route_id"], itinerary["boarding_route_stop_id"],
                itinerary["alighting_route_stop_id"], travel_class,
            ),
        )
        fare = cursor.fetchone()
        if not fare:
            raise BookingUnavailableError("No fare is configured for this route segment and class.")
        fare_per_passenger = Decimal(str(fare["fare_amount"])).quantize(Decimal("0.01"))
        base_total = fare_per_passenger * len(validated_passengers)

        pnr = _new_pnr()
        cursor.execute(
            """INSERT INTO bookings (
                   pnr, user_id, schedule_id, boarding_schedule_stop_id,
                   alighting_schedule_stop_id, class_id, train_number_snapshot,
                   train_name_snapshot, boarding_station_code_snapshot,
                   boarding_station_name_snapshot, alighting_station_code_snapshot,
                   alighting_station_name_snapshot, departure_at_snapshot,
                   arrival_at_snapshot, class_code_snapshot, base_fare_total,
                   other_charges, total_fare, currency_code, idempotency_key
               ) VALUES (
                   %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                   %s, %s, %s, %s, 0.00, %s, %s, %s
               )""",
            (
                pnr, user, schedule, itinerary["boarding_stop_id"],
                itinerary["alighting_stop_id"], travel_class, itinerary["train_number"],
                itinerary["train_name"], itinerary["source_code"], itinerary["source_name"],
                itinerary["destination_code"], itinerary["destination_name"],
                itinerary["departure_at"], itinerary["arrival_at"], itinerary["class_code"],
                base_total, base_total, fare["currency_code"], request_key,
            ),
        )
        booking_id = int(cursor.lastrowid)
        assignments = []
        hold_expiry = None
        for passenger, seat in zip(validated_passengers, free_seats):
            cursor.execute(
                """INSERT INTO booking_passengers (
                       booking_id, passenger_name, age, gender, berth_preference, passenger_fare
                   ) VALUES (%s, %s, %s, %s, %s, %s)""",
                (
                    booking_id, passenger["passenger_name"], passenger["age"],
                    passenger["gender"], passenger["berth_preference"], fare_per_passenger,
                ),
            )
            passenger_id = int(cursor.lastrowid)
            cursor.execute(
                f"""INSERT INTO seat_allocations (
                       booking_id, schedule_id, class_id, booking_passenger_id,
                       schedule_seat_id, allocation_status, hold_expires_at
                   ) VALUES (%s, %s, %s, %s, %s, 'HELD',
                             DATE_ADD(CURRENT_TIMESTAMP, INTERVAL {SEAT_HOLD_MINUTES} MINUTE))""",
                (booking_id, schedule, travel_class, passenger_id, seat["schedule_seat_id"]),
            )
            assignments.append({
                "coach_number": seat["coach_number"],
                "seat_number": seat["seat_number"],
            })

        cursor.execute(
            """SELECT MAX(hold_expires_at) AS hold_expires_at
               FROM seat_allocations WHERE booking_id = %s""",
            (booking_id,),
        )
        expiry_row = cursor.fetchone()
        hold_expiry = expiry_row["hold_expires_at"].isoformat() if expiry_row and expiry_row["hold_expires_at"] else None
        connection.commit()
        return {
            "booking_id": booking_id,
            "pnr": pnr,
            "status": "PENDING_PAYMENT",
            "currency_code": fare["currency_code"],
            "fare_per_passenger": float(fare_per_passenger),
            "total_fare": float(base_total),
            "assigned_seats": assignments,
            "hold_expires_at": hold_expiry,
            "replayed": False,
        }
    except (BookingRequestError, mysql.connector.Error):
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
