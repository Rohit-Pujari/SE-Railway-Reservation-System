"""Station lookup and passenger train-search query helpers."""

from datetime import date, datetime, time, timedelta

import mysql.connector

from .db import get_db_connection


MAX_SEARCH_RESULTS = 100


class TrainSearchValidationError(ValueError):
    """Raised when train-search parameters are missing or invalid."""


def validate_search(source_station_id, destination_station_id, journey_date):
    """Normalize search inputs before any database query is made."""
    try:
        source_id = int(source_station_id)
        destination_id = int(destination_station_id)
    except (TypeError, ValueError):
        raise TrainSearchValidationError("Select a source and destination station.") from None

    if source_id <= 0 or destination_id <= 0:
        raise TrainSearchValidationError("Select a valid source and destination station.")
    if source_id == destination_id:
        raise TrainSearchValidationError("Source and destination stations must be different.")

    if not isinstance(journey_date, str):
        raise TrainSearchValidationError("Select a journey date.")
    try:
        parsed_date = date.fromisoformat(journey_date)
    except ValueError:
        raise TrainSearchValidationError("Journey date must use YYYY-MM-DD format.") from None
    if parsed_date.isoformat() != journey_date:
        raise TrainSearchValidationError("Journey date must use YYYY-MM-DD format.")

    return source_id, destination_id, parsed_date


def _format_datetime(value):
    """Return consistent ISO 8601 strings for JSON responses."""
    if value is None:
        return None
    if isinstance(value, str):
        return value.replace(" ", "T")
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def get_active_stations(connection_factory=None):
    """Return active stations, sorted for predictable dropdowns."""
    factory = connection_factory or get_db_connection
    connection = cursor = None
    try:
        connection = factory()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """SELECT station_id, station_code, station_name, city, state
               FROM stations
               WHERE station_status = 'ACTIVE'
               ORDER BY city, station_name, station_code"""
        )
        stations = cursor.fetchall()
        return [
            {
                "station_id": row["station_id"],
                "station_code": row["station_code"],
                "station_name": row["station_name"],
                "city": row["city"],
                "state": row.get("state"),
            }
            for row in stations
        ]
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


def search_trains(source_station_id, destination_station_id, journey_date, connection_factory=None):
    """Return active scheduled trains stopping at origin before destination."""
    source_id, destination_id, travel_date = validate_search(
        source_station_id, destination_station_id, journey_date
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
                   train.train_number,
                   train.train_name,
                   source.station_id AS source_station_id,
                   source.station_code AS source_station_code,
                   source.station_name AS source_station_name,
                   source.city AS source_city,
                   destination.station_id AS destination_station_id,
                   destination.station_code AS destination_station_code,
                   destination.station_name AS destination_station_name,
                   destination.city AS destination_city,
                   origin_stop.departure_at AS departure_at,
                   destination_stop.arrival_at AS arrival_at,
                   (
                       SELECT fare.fare_amount
                       FROM route_fares AS fare
                       JOIN route_stops AS fare_origin
                         ON fare_origin.route_stop_id = fare.from_route_stop_id
                       JOIN route_stops AS fare_destination
                         ON fare_destination.route_stop_id = fare.to_route_stop_id
                       JOIN travel_classes AS fare_class
                         ON fare_class.class_id = fare.class_id
                       WHERE fare.route_id = route.route_id
                         AND fare_origin.route_stop_id = origin_stop.route_stop_id
                         AND fare_destination.route_stop_id = destination_stop.route_stop_id
                         AND fare_origin.stop_sequence < fare_destination.stop_sequence
                         AND fare_class.class_status = 'ACTIVE'
                       ORDER BY fare.fare_amount ASC
                       LIMIT 1
                   ) AS starting_fare,
                   (
                       SELECT fare.currency_code
                       FROM route_fares AS fare
                       JOIN route_stops AS fare_origin
                         ON fare_origin.route_stop_id = fare.from_route_stop_id
                       JOIN route_stops AS fare_destination
                         ON fare_destination.route_stop_id = fare.to_route_stop_id
                       JOIN travel_classes AS fare_class
                         ON fare_class.class_id = fare.class_id
                       WHERE fare.route_id = route.route_id
                         AND fare_origin.route_stop_id = origin_stop.route_stop_id
                         AND fare_destination.route_stop_id = destination_stop.route_stop_id
                         AND fare_origin.stop_sequence < fare_destination.stop_sequence
                         AND fare_class.class_status = 'ACTIVE'
                       ORDER BY fare.fare_amount ASC
                       LIMIT 1
                   ) AS currency_code,
                   (
                       SELECT COUNT(*)
                       FROM schedule_seats AS available_seat
                       JOIN seats AS physical_seat
                         ON physical_seat.seat_id = available_seat.seat_id
                       JOIN travel_classes AS seat_class
                         ON seat_class.class_id = available_seat.class_id
                       WHERE available_seat.schedule_id = schedule.schedule_id
                         AND available_seat.operational_status = 'IN_SERVICE'
                         AND physical_seat.seat_status = 'ACTIVE'
                         AND seat_class.class_status = 'ACTIVE'
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
                   ) AS available_seats
               FROM train_schedules AS schedule
               JOIN trains AS train
                 ON train.train_id = schedule.train_id
               JOIN routes AS route
                 ON route.route_id = schedule.route_id
               JOIN schedule_stops AS origin_stop
                 ON origin_stop.schedule_id = schedule.schedule_id
               JOIN stations AS source
                 ON source.station_id = origin_stop.station_id
               JOIN schedule_stops AS destination_stop
                 ON destination_stop.schedule_id = schedule.schedule_id
               JOIN stations AS destination
                 ON destination.station_id = destination_stop.station_id
               WHERE origin_stop.station_id = %s
                 AND destination_stop.station_id = %s
                 AND origin_stop.stop_sequence < destination_stop.stop_sequence
                 AND origin_stop.departure_at >= %s
                 AND origin_stop.departure_at < %s
                 AND destination_stop.arrival_at IS NOT NULL
                 AND schedule.schedule_status = 'SCHEDULED'
                 AND train.train_status = 'ACTIVE'
                 AND route.route_status = 'ACTIVE'
                 AND source.station_status = 'ACTIVE'
                 AND destination.station_status = 'ACTIVE'
               ORDER BY origin_stop.departure_at, train.train_number
               LIMIT %s""",
            (source_id, destination_id, start_at, end_at, MAX_SEARCH_RESULTS),
        )
        rows = cursor.fetchall()
        return [
            {
                "schedule_id": row["schedule_id"],
                "train_number": row["train_number"],
                "train_name": row["train_name"],
                "source_station_id": row["source_station_id"],
                "source_station_code": row["source_station_code"],
                "source_station_name": row["source_station_name"],
                "source_city": row["source_city"],
                "destination_station_id": row["destination_station_id"],
                "destination_station_code": row["destination_station_code"],
                "destination_station_name": row["destination_station_name"],
                "destination_city": row["destination_city"],
                "departure_at": _format_datetime(row["departure_at"]),
                "arrival_at": _format_datetime(row["arrival_at"]),
                "starting_fare": float(row["starting_fare"]) if row.get("starting_fare") is not None else None,
                "currency_code": row.get("currency_code") or "INR",
                "available_seats": int(row.get("available_seats") or 0),
            }
            for row in rows
        ]
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
