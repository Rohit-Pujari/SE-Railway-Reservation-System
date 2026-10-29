"""Class-specific seat availability for a scheduled train journey."""

from datetime import date, datetime, time, timedelta

from .db import get_db_connection


class SeatAvailabilityValidationError(ValueError):
    """Raised when availability search parameters are missing or invalid."""


def _positive_int(value, label):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise SeatAvailabilityValidationError(f"Select a valid {label}.") from None
    if parsed <= 0:
        raise SeatAvailabilityValidationError(f"Select a valid {label}.")
    return parsed


def validate_availability(schedule_id, source_station_id, destination_station_id, journey_date, class_id):
    schedule = _positive_int(schedule_id, "train schedule")
    source = _positive_int(source_station_id, "source station")
    destination = _positive_int(destination_station_id, "destination station")
    travel_class = _positive_int(class_id, "travel class")
    if source == destination:
        raise SeatAvailabilityValidationError("Source and destination stations must be different.")
    if not isinstance(journey_date, str):
        raise SeatAvailabilityValidationError("Select a journey date.")
    try:
        parsed_date = date.fromisoformat(journey_date)
    except ValueError:
        raise SeatAvailabilityValidationError("Journey date must use YYYY-MM-DD format.") from None
    if parsed_date.isoformat() != journey_date:
        raise SeatAvailabilityValidationError("Journey date must use YYYY-MM-DD format.")
    return schedule, source, destination, parsed_date, travel_class


def get_seat_availability(schedule_id, source_station_id, destination_station_id, journey_date, class_id, connection_factory=None):
    """Count in-service seats in a class not occupied on any overlapping journey segment."""
    schedule, source, destination, travel_date, travel_class = validate_availability(
        schedule_id, source_station_id, destination_station_id, journey_date, class_id
    )
    start_at = datetime.combine(travel_date, time.min)
    end_at = start_at + timedelta(days=1)
    factory = connection_factory or get_db_connection
    connection = cursor = None
    try:
        connection = factory()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """SELECT
                   schedule.schedule_id,
                   travel_class.class_id,
                   travel_class.class_code,
                   COUNT(available_seat.schedule_seat_id) AS available_seats
               FROM train_schedules AS schedule
               JOIN schedule_stops AS origin_stop
                 ON origin_stop.schedule_id = schedule.schedule_id
                AND origin_stop.station_id = %s
               JOIN schedule_stops AS destination_stop
                 ON destination_stop.schedule_id = schedule.schedule_id
                AND destination_stop.station_id = %s
                AND origin_stop.stop_sequence < destination_stop.stop_sequence
               JOIN schedule_seats AS available_seat
                 ON available_seat.schedule_id = schedule.schedule_id
                AND available_seat.class_id = %s
                AND available_seat.operational_status = 'IN_SERVICE'
               JOIN seats AS physical_seat
                 ON physical_seat.seat_id = available_seat.seat_id
                AND physical_seat.seat_status = 'ACTIVE'
               JOIN travel_classes AS travel_class
                 ON travel_class.class_id = available_seat.class_id
                AND travel_class.class_status = 'ACTIVE'
               WHERE schedule.schedule_id = %s
                 AND schedule.schedule_status = 'SCHEDULED'
                 AND origin_stop.departure_at >= %s
                 AND origin_stop.departure_at < %s
                 AND destination_stop.arrival_at IS NOT NULL
                 AND NOT EXISTS (
                     SELECT 1
                     FROM seat_allocations AS allocation
                     JOIN bookings AS booking
                       ON booking.booking_id = allocation.booking_id
                     JOIN schedule_stops AS boarding_stop
                       ON boarding_stop.schedule_stop_id = booking.boarding_schedule_stop_id
                     JOIN schedule_stops AS alighting_stop
                       ON alighting_stop.schedule_stop_id = booking.alighting_schedule_stop_id
                     WHERE allocation.schedule_id = schedule.schedule_id
                       AND allocation.schedule_seat_id = available_seat.schedule_seat_id
                       AND (
                           allocation.allocation_status = 'CONFIRMED'
                           OR (
                               allocation.allocation_status = 'HELD'
                               AND allocation.hold_expires_at > CURRENT_TIMESTAMP
                           )
                       )
                       AND boarding_stop.stop_sequence < destination_stop.stop_sequence
                       AND alighting_stop.stop_sequence > origin_stop.stop_sequence
                 )
               GROUP BY schedule.schedule_id, travel_class.class_id, travel_class.class_code""",
            (source, destination, travel_class, schedule, start_at, end_at),
        )
        row = cursor.fetchone()
        if row is None:
            return {
                "schedule_id": schedule,
                "class_id": travel_class,
                "class_code": None,
                "available_seats": 0,
            }
        return {
            "schedule_id": int(row["schedule_id"]),
            "class_id": int(row["class_id"]),
            "class_code": row["class_code"],
            "available_seats": int(row["available_seats"] or 0),
        }
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
