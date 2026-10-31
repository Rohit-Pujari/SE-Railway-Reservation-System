"""Administrator management for stations, routes, and train-route assignments."""

import math
import re
from decimal import Decimal, InvalidOperation

from .db import get_db_connection


STATION_CODE_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,10}$")


class StationRouteValidationError(ValueError):
    """Raised when station, route, or assignment data is invalid."""


class DuplicateStationCodeError(ValueError):
    """Raised when a station code is already in use."""


class DuplicateTrainRouteError(ValueError):
    """Raised when a train is already assigned to a route."""


def validate_station(station_code, station_name, city, state=None):
    if not isinstance(station_code, str) or not STATION_CODE_PATTERN.fullmatch(station_code.strip()):
        raise StationRouteValidationError("Station code must contain 1–10 letters, numbers, or hyphens.")
    code = station_code.strip().upper()
    values = []
    for value, label, limit, required in (
        (station_name, "Station name", 120, True),
        (city, "City", 100, True),
        (state, "State", 100, False),
    ):
        if value is None and not required:
            values.append(None)
            continue
        if not isinstance(value, str):
            raise StationRouteValidationError(f"{label} is required.")
        normalized = " ".join(value.split())
        if required and not normalized:
            raise StationRouteValidationError(f"{label} is required.")
        if len(normalized) > limit:
            raise StationRouteValidationError(f"{label} must be {limit} characters or fewer.")
        values.append(normalized or None)
    return (code, *values)


def validate_route(route_name, stops):
    if not isinstance(route_name, str):
        raise StationRouteValidationError("Route name is required.")
    name = " ".join(route_name.split())
    if not name or len(name) > 150:
        raise StationRouteValidationError("Route name is required and must be 150 characters or fewer.")
    if not isinstance(stops, list) or len(stops) < 2 or len(stops) > 100:
        raise StationRouteValidationError("A route must contain between 2 and 100 stops.")
    normalized = []
    seen = set()
    previous_distance = Decimal("-1")
    for index, stop in enumerate(stops, start=1):
        if not isinstance(stop, dict):
            raise StationRouteValidationError("Each route stop must be an object.")
        station_id = stop.get("station_id")
        sequence = stop.get("sequence", index)
        try:
            if isinstance(station_id, bool) or int(station_id) <= 0:
                raise ValueError
            station_id = int(station_id)
            if isinstance(sequence, bool) or int(sequence) != index:
                raise ValueError
        except (TypeError, ValueError):
            raise StationRouteValidationError("Stops must have valid station IDs and consecutive sequence numbers.") from None
        if station_id in seen:
            raise StationRouteValidationError("A station can appear only once in a route.")
        seen.add(station_id)
        try:
            distance = Decimal(str(stop.get("distance_from_origin_km", 0)))
        except (InvalidOperation, TypeError):
            raise StationRouteValidationError("Stop distances must be valid non-negative numbers.") from None
        if not distance.is_finite() or distance < 0 or distance > Decimal("999999.99"):
            raise StationRouteValidationError("Stop distances must be between 0 and 999999.99 km.")
        if distance < previous_distance:
            raise StationRouteValidationError("Stop distances must not decrease along the route.")
        if index == 1 and distance != 0:
            raise StationRouteValidationError("The first stop must have a distance of 0 km.")
        normalized.append((station_id, index, distance))
        previous_distance = distance
    return name, normalized


def create_station(payload, connection_factory=None):
    code, name, city, state = validate_station(
        payload.get("station_code"), payload.get("station_name"), payload.get("city"), payload.get("state")
    )
    connection = (connection_factory or get_db_connection)()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT station_id FROM stations WHERE station_code = %s LIMIT 1", (code,))
        if cursor.fetchone():
            raise DuplicateStationCodeError("A station with this code already exists.")
        cursor.execute(
            "INSERT INTO stations (station_code, station_name, city, state) VALUES (%s, %s, %s, %s)",
            (code, name, city, state),
        )
        result = {"station_id": cursor.lastrowid, "station_code": code, "station_name": name, "city": city, "state": state}
        connection.commit()
        return result
    except Exception:
        connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def update_station(station_id, payload, connection_factory=None):
    if isinstance(station_id, bool) or not str(station_id).isdigit() or int(station_id) <= 0:
        raise StationRouteValidationError("Enter a valid station ID.")
    connection = (connection_factory or get_db_connection)()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM stations WHERE station_id = %s FOR UPDATE", (int(station_id),))
        existing = cursor.fetchone()
        if existing is None:
            raise LookupError("Station not found.")
        code, name, city, state = validate_station(
            payload.get("station_code", existing["station_code"]),
            payload.get("station_name", existing["station_name"]),
            payload.get("city", existing["city"]),
            payload.get("state", existing.get("state")),
        )
        cursor.execute(
            "SELECT station_id FROM stations WHERE station_code = %s AND station_id <> %s LIMIT 1",
            (code, int(station_id)),
        )
        if cursor.fetchone():
            raise DuplicateStationCodeError("A station with this code already exists.")
        cursor.execute(
            "UPDATE stations SET station_code=%s, station_name=%s, city=%s, state=%s WHERE station_id=%s",
            (code, name, city, state, int(station_id)),
        )
        connection.commit()
        return {"station_id": int(station_id), "station_code": code, "station_name": name, "city": city, "state": state}
    except Exception:
        connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def create_route(payload, connection_factory=None):
    name, stops = validate_route(payload.get("route_name"), payload.get("stops"))
    status = payload.get("route_status", "ACTIVE")
    if status not in ("ACTIVE", "INACTIVE"):
        raise StationRouteValidationError("Route status must be ACTIVE or INACTIVE.")
    connection = (connection_factory or get_db_connection)()
    cursor = None
    try:
        cursor = connection.cursor()
        placeholders = ",".join(["%s"] * len(stops))
        cursor.execute(
            f"SELECT station_id FROM stations WHERE station_id IN ({placeholders}) AND station_status='ACTIVE' FOR UPDATE",
            tuple(stop[0] for stop in stops),
        )
        active_ids = {int(row[0]) for row in cursor.fetchall()}
        if active_ids != {stop[0] for stop in stops}:
            raise StationRouteValidationError("Every route stop must reference an existing active station.")
        cursor.execute("INSERT INTO routes (route_name, route_status) VALUES (%s, %s)", (name, status))
        route_id = cursor.lastrowid
        cursor.executemany(
            "INSERT INTO route_stops (route_id, station_id, stop_sequence, distance_from_origin_km) VALUES (%s,%s,%s,%s)",
            [(route_id, *stop) for stop in stops],
        )
        connection.commit()
        return {"route_id": route_id, "route_name": name, "route_status": status}
    except Exception:
        connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def update_route(route_id, payload, connection_factory=None):
    if isinstance(route_id, bool) or not str(route_id).isdigit() or int(route_id) <= 0:
        raise StationRouteValidationError("Enter a valid route ID.")
    connection = (connection_factory or get_db_connection)()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT * FROM routes WHERE route_id=%s FOR UPDATE", (int(route_id),))
        existing = cursor.fetchone()
        if existing is None:
            raise LookupError("Route not found.")
        name = payload.get("route_name", existing["route_name"])
        if not isinstance(name, str) or not " ".join(name.split()) or len(" ".join(name.split())) > 150:
            raise StationRouteValidationError("Route name is required and must be 150 characters or fewer.")
        name = " ".join(name.split())
        status = payload.get("route_status", existing["route_status"])
        if status not in ("ACTIVE", "INACTIVE"):
            raise StationRouteValidationError("Route status must be ACTIVE or INACTIVE.")
        if "stops" in payload:
            _, stops = validate_route(name, payload["stops"])
            cursor.execute(
                "SELECT (SELECT COUNT(*) FROM train_schedules WHERE route_id=%s) AS schedules, "
                "(SELECT COUNT(*) FROM route_fares WHERE route_id=%s) AS fares",
                (int(route_id), int(route_id)),
            )
            dependencies = cursor.fetchone()
            if int(dependencies["schedules"] or 0) or int(dependencies["fares"] or 0):
                raise StationRouteValidationError("Route stops cannot be changed after schedules or fares reference this route.")
            placeholders = ",".join(["%s"] * len(stops))
            cursor.execute(
                f"SELECT station_id FROM stations WHERE station_id IN ({placeholders}) AND station_status='ACTIVE'",
                tuple(stop[0] for stop in stops),
            )
            active_ids = {int(row["station_id"]) for row in cursor.fetchall()}
            if active_ids != {stop[0] for stop in stops}:
                raise StationRouteValidationError("Every route stop must reference an existing active station.")
            cursor.execute("DELETE FROM route_stops WHERE route_id=%s", (int(route_id),))
            cursor.executemany(
                "INSERT INTO route_stops (route_id, station_id, stop_sequence, distance_from_origin_km) VALUES (%s,%s,%s,%s)",
                [(int(route_id), *stop) for stop in stops],
            )
        cursor.execute("UPDATE routes SET route_name=%s, route_status=%s WHERE route_id=%s", (name, status, int(route_id)))
        connection.commit()
        return {"route_id": int(route_id), "route_name": name, "route_status": status}
    except Exception:
        connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def assign_route_to_train(train_id, route_id, connection_factory=None):
    for value, label in ((train_id, "train"), (route_id, "route")):
        if isinstance(value, bool) or not str(value).isdigit() or int(value) <= 0:
            raise StationRouteValidationError(f"Enter a valid {label} ID.")
    train_id, route_id = int(train_id), int(route_id)
    connection = (connection_factory or get_db_connection)()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT train_id FROM trains WHERE train_id=%s AND train_status='ACTIVE' FOR UPDATE", (train_id,))
        if cursor.fetchone() is None:
            raise LookupError("Active train not found.")
        cursor.execute("SELECT route_id FROM routes WHERE route_id=%s AND route_status='ACTIVE' FOR UPDATE", (route_id,))
        if cursor.fetchone() is None:
            raise LookupError("Active route not found.")
        cursor.execute("SELECT COUNT(*) AS stop_count FROM route_stops WHERE route_id=%s", (route_id,))
        if int((cursor.fetchone() or {}).get("stop_count") or 0) < 2:
            raise StationRouteValidationError("A route must have at least two stops before it can be assigned.")
        cursor.execute("INSERT INTO train_routes (train_id, route_id) VALUES (%s, %s)", (train_id, route_id))
        connection.commit()
        return {"train_id": train_id, "route_id": route_id}
    except Exception:
        connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def remove_train_route(train_id, route_id, connection_factory=None):
    if any(isinstance(value, bool) or not str(value).isdigit() or int(value) <= 0 for value in (train_id, route_id)):
        raise StationRouteValidationError("Enter valid train and route IDs.")
    connection = (connection_factory or get_db_connection)()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            "DELETE FROM train_routes WHERE train_id=%s AND route_id=%s",
            (int(train_id), int(route_id)),
        )
        if cursor.rowcount != 1:
            raise LookupError("Train-route assignment not found.")
        connection.commit()
        return {"train_id": int(train_id), "route_id": int(route_id)}
    except Exception:
        connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()
