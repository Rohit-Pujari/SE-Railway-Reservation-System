"""Administrator management for train schedules and their operational stop times."""

from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from .db import get_db_connection


class ScheduleValidationError(ValueError):
    """Raised when schedule details are invalid."""


class ScheduleConflictError(ValueError):
    """Raised when a schedule cannot be safely changed."""


SCHEDULE_STATUSES = {"SCHEDULED", "CANCELLED", "COMPLETED"}
PROTECTED_FIELDS = {"train_id", "route_id", "departure_at", "arrival_at"}


def _positive_id(value, label):
    if isinstance(value, bool):
        raise ScheduleValidationError(f"Select a valid {label}.")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ScheduleValidationError(f"Select a valid {label}.") from None
    if parsed <= 0 or str(value).strip() != str(parsed):
        raise ScheduleValidationError(f"Select a valid {label}.")
    return parsed


def _parse_datetime(value, label):
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.strip())
        except ValueError:
            raise ScheduleValidationError(f"{label} must be a valid date and time.") from None
    else:
        raise ScheduleValidationError(f"{label} must be a valid date and time.")
    if parsed.tzinfo is not None:
        raise ScheduleValidationError(f"{label} must not include a timezone offset.")
    if parsed.second or parsed.microsecond:
        parsed = parsed.replace(second=0, microsecond=0)
    return parsed


def validate_schedule(train_id, route_id, departure_at, arrival_at, schedule_status="SCHEDULED"):
    train = _positive_id(train_id, "train")
    route = _positive_id(route_id, "route")
    departure = _parse_datetime(departure_at, "Departure")
    arrival = _parse_datetime(arrival_at, "Arrival")
    if arrival <= departure:
        raise ScheduleValidationError("Arrival time must be later than departure time.")
    if schedule_status not in SCHEDULE_STATUSES:
        raise ScheduleValidationError("Schedule status must be SCHEDULED, CANCELLED, or COMPLETED.")
    return train, route, departure, arrival, schedule_status


def _load_active_route(cursor, train_id, route_id):
    cursor.execute(
        "SELECT train_id FROM trains WHERE train_id=%s AND train_status='ACTIVE' FOR UPDATE",
        (train_id,),
    )
    if cursor.fetchone() is None:
        raise ScheduleValidationError("Select an existing active train.")
    cursor.execute(
        "SELECT route_id FROM routes WHERE route_id=%s AND route_status='ACTIVE' FOR UPDATE",
        (route_id,),
    )
    if cursor.fetchone() is None:
        raise ScheduleValidationError("Select an existing active route.")
    cursor.execute(
        "SELECT train_id FROM train_routes WHERE train_id=%s AND route_id=%s FOR UPDATE",
        (train_id, route_id),
    )
    if cursor.fetchone() is None:
        raise ScheduleValidationError("The selected route must be assigned to the selected train first.")
    cursor.execute(
        """SELECT stop.route_stop_id, stop.station_id, stop.stop_sequence,
                  stop.distance_from_origin_km
           FROM route_stops AS stop
           JOIN stations AS station ON station.station_id=stop.station_id
           WHERE stop.route_id=%s AND station.station_status='ACTIVE'
           ORDER BY stop.stop_sequence FOR UPDATE""",
        (route_id,),
    )
    stops = cursor.fetchall() or []
    if len(stops) < 2:
        raise ScheduleValidationError("The selected route must contain at least two active stations.")
    distances = [Decimal(str(stop["distance_from_origin_km"])) for stop in stops]
    if distances[0] != 0 or any(distances[i] <= distances[i - 1] for i in range(1, len(distances))):
        raise ScheduleValidationError("The selected route must have valid increasing cumulative distances.")
    return stops


def _build_stop_times(stops, departure, arrival):
    total_distance = Decimal(str(stops[-1]["distance_from_origin_km"]))
    duration_seconds = int((arrival - departure).total_seconds())
    rows = []
    for index, stop in enumerate(stops):
        if index == 0:
            stop_arrival, stop_departure = None, departure
        elif index == len(stops) - 1:
            stop_arrival, stop_departure = arrival, None
        else:
            distance = Decimal(str(stop["distance_from_origin_km"]))
            elapsed = int(Decimal(duration_seconds) * distance / total_distance)
            passing_time = departure + timedelta(seconds=elapsed)
            stop_arrival = passing_time
            stop_departure = passing_time
        rows.append((
            stop["route_stop_id"], stop["station_id"], stop["stop_sequence"],
            stop_arrival, stop_departure,
        ))
    return rows


def _insert_schedule_stops(cursor, schedule_id, route_id, stops, departure, arrival):
    stop_rows = _build_stop_times(stops, departure, arrival)
    cursor.executemany(
        """INSERT INTO schedule_stops
           (schedule_id, route_id, route_stop_id, station_id, stop_sequence, arrival_at, departure_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        [(schedule_id, route_id, *row) for row in stop_rows],
    )


def _insert_schedule_seats(cursor, schedule_id, train_id):
    cursor.execute(
        """INSERT INTO schedule_seats (schedule_id, train_id, seat_id, class_id, operational_status)
           SELECT %s, seat.train_id, seat.seat_id, seat.class_id, 'IN_SERVICE'
           FROM seats AS seat
           JOIN travel_classes AS travel_class ON travel_class.class_id=seat.class_id
           WHERE seat.train_id=%s AND seat.seat_status='ACTIVE'
             AND travel_class.class_status='ACTIVE'""",
        (schedule_id, train_id),
    )


def create_schedule(payload, connection_factory=None):
    train_id, route_id, departure, arrival, status = validate_schedule(
        payload.get("train_id"), payload.get("route_id"),
        payload.get("departure_at"), payload.get("arrival_at"),
        payload.get("schedule_status", "SCHEDULED"),
    )
    connection = (connection_factory or get_db_connection)()
    cursor = None
    try:
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)
        stops = _load_active_route(cursor, train_id, route_id)
        cursor.execute(
            """INSERT INTO train_schedules
               (train_id, route_id, departure_at, arrival_at, schedule_status)
               VALUES (%s,%s,%s,%s,%s)""",
            (train_id, route_id, departure, arrival, status),
        )
        schedule_id = cursor.lastrowid
        _insert_schedule_stops(cursor, schedule_id, route_id, stops, departure, arrival)
        _insert_schedule_seats(cursor, schedule_id, train_id)
        connection.commit()
        return {
            "schedule_id": schedule_id, "train_id": train_id, "route_id": route_id,
            "departure_at": departure.isoformat(sep=" "),
            "arrival_at": arrival.isoformat(sep=" "), "schedule_status": status,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def update_schedule(schedule_id, payload, connection_factory=None):
    schedule = _positive_id(schedule_id, "schedule")
    if not isinstance(payload, dict) or not payload:
        raise ScheduleValidationError("Submit at least one schedule detail.")
    allowed = PROTECTED_FIELDS | {"schedule_status"}
    if set(payload) - allowed:
        raise ScheduleValidationError("The schedule contains unsupported fields.")
    connection = (connection_factory or get_db_connection)()
    cursor = None
    try:
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM train_schedules WHERE schedule_id=%s FOR UPDATE", (schedule,))
        existing = cursor.fetchone()
        if existing is None:
            raise LookupError("Schedule not found.")
        cursor.execute("SELECT COUNT(*) AS total FROM bookings WHERE schedule_id=%s", (schedule,))
        has_bookings = int(cursor.fetchone()["total"] or 0) > 0

        train_id = _positive_id(payload.get("train_id", existing["train_id"]), "train")
        route_id = _positive_id(payload.get("route_id", existing["route_id"]), "route")
        departure = _parse_datetime(payload.get("departure_at", existing["departure_at"]), "Departure")
        arrival = _parse_datetime(payload.get("arrival_at", existing["arrival_at"]), "Arrival")
        status = payload.get("schedule_status", existing["schedule_status"])
        if arrival <= departure:
            raise ScheduleValidationError("Arrival time must be later than departure time.")
        if status not in SCHEDULE_STATUSES:
            raise ScheduleValidationError("Schedule status must be SCHEDULED, CANCELLED, or COMPLETED.")

        changed_service_details = (
            train_id != int(existing["train_id"])
            or route_id != int(existing["route_id"])
            or departure != existing["departure_at"]
            or arrival != existing["arrival_at"]
        )
        if has_bookings and changed_service_details:
            raise ScheduleConflictError(
                "Train, route, and timetable cannot be changed after bookings exist. You can still update the schedule status."
            )

        if changed_service_details:
            stops = _load_active_route(cursor, train_id, route_id)
            cursor.execute("DELETE FROM schedule_seats WHERE schedule_id=%s", (schedule,))
            cursor.execute("DELETE FROM schedule_stops WHERE schedule_id=%s", (schedule,))
        else:
            stops = None

        cursor.execute(
            """UPDATE train_schedules
               SET train_id=%s, route_id=%s, departure_at=%s, arrival_at=%s, schedule_status=%s
               WHERE schedule_id=%s""",
            (train_id, route_id, departure, arrival, status, schedule),
        )
        if changed_service_details:
            _insert_schedule_stops(cursor, schedule, route_id, stops, departure, arrival)
            _insert_schedule_seats(cursor, schedule, train_id)
        connection.commit()
        return {
            "schedule_id": schedule, "train_id": train_id, "route_id": route_id,
            "departure_at": departure.isoformat(sep=" "),
            "arrival_at": arrival.isoformat(sep=" "), "schedule_status": status,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()
