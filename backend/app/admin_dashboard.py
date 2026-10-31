"""Read-only administrator dashboard queries for the existing railway schema."""

from .db import get_db_connection


def get_admin_dashboard(connection_factory=None):
    """Return bounded operational lists and summary counts for an authenticated admin."""
    connection = (connection_factory or get_db_connection)()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        data = {}

        cursor.execute("""
            SELECT train_id, train_number, train_name, train_status
            FROM trains ORDER BY train_number LIMIT 200
        """)
        data["trains"] = cursor.fetchall() or []

        cursor.execute("""
            SELECT route.route_id, route.route_name, route.route_status,
                   stop.stop_sequence, station.station_id, station.station_code,
                   station.station_name, station.city, stop.distance_from_origin_km
            FROM routes AS route
            LEFT JOIN route_stops AS stop ON stop.route_id = route.route_id
            LEFT JOIN stations AS station ON station.station_id = stop.station_id
            ORDER BY route.route_id, stop.stop_sequence LIMIT 1000
        """)
        route_rows = cursor.fetchall() or []
        routes = {}
        for row in route_rows:
            route = routes.setdefault(row["route_id"], {
                "route_id": row["route_id"], "route_name": row["route_name"],
                "route_status": row["route_status"], "stops": [],
            })
            if row["station_id"] is not None:
                route["stops"].append({
                    "sequence": row["stop_sequence"], "station_code": row["station_code"],
                    "station_name": row["station_name"], "city": row["city"],
                    "distance_km": float(row["distance_from_origin_km"] or 0),
                })
        data["routes"] = list(routes.values())

        cursor.execute("""
            SELECT schedule.schedule_id, schedule.schedule_status,
                   schedule.departure_at, schedule.arrival_at,
                   train.train_id, train.train_number, train.train_name,
                   route.route_id, route.route_name,
                   COUNT(DISTINCT schedule_seat.schedule_seat_id) AS total_seats,
                   COUNT(DISTINCT CASE WHEN schedule_seat.operational_status = 'IN_SERVICE'
                       AND (allocation.allocation_status IS NULL
                            OR allocation.allocation_status = 'RELEASED'
                            OR (allocation.allocation_status = 'HELD'
                                AND allocation.hold_expires_at <= CURRENT_TIMESTAMP))
                       THEN schedule_seat.schedule_seat_id END) AS available_seats
            FROM train_schedules AS schedule
            JOIN trains AS train ON train.train_id = schedule.train_id
            JOIN routes AS route ON route.route_id = schedule.route_id
            LEFT JOIN schedule_seats AS schedule_seat ON schedule_seat.schedule_id = schedule.schedule_id
            LEFT JOIN seat_allocations AS allocation
              ON allocation.schedule_id = schedule_seat.schedule_id
             AND allocation.schedule_seat_id = schedule_seat.schedule_seat_id
             AND allocation.allocation_status IN ('HELD','CONFIRMED')
            GROUP BY schedule.schedule_id, schedule.schedule_status, schedule.departure_at,
                     schedule.arrival_at, train.train_id, train.train_number, train.train_name,
                     route.route_id, route.route_name
            ORDER BY schedule.departure_at DESC LIMIT 200
        """)
        data["schedules"] = cursor.fetchall() or []

        cursor.execute("""
            SELECT booking.booking_id, booking.pnr, booking.booking_status,
                   booking.train_number_snapshot, booking.train_name_snapshot,
                   booking.boarding_station_name_snapshot, booking.alighting_station_name_snapshot,
                   booking.departure_at_snapshot, booking.arrival_at_snapshot,
                   booking.class_code_snapshot, booking.total_fare, booking.currency_code,
                   booking.created_at, user.full_name, user.email,
                   COUNT(DISTINCT passenger.booking_passenger_id) AS passenger_count
            FROM bookings AS booking
            JOIN users AS user ON user.user_id = booking.user_id
            LEFT JOIN booking_passengers AS passenger ON passenger.booking_id = booking.booking_id
            GROUP BY booking.booking_id, booking.pnr, booking.booking_status,
                     booking.train_number_snapshot, booking.train_name_snapshot,
                     booking.boarding_station_name_snapshot, booking.alighting_station_name_snapshot,
                     booking.departure_at_snapshot, booking.arrival_at_snapshot,
                     booking.class_code_snapshot, booking.total_fare, booking.currency_code,
                     booking.created_at, user.full_name, user.email
            ORDER BY booking.created_at DESC LIMIT 200
        """)
        data["bookings"] = cursor.fetchall() or []

        cursor.execute("""
            SELECT cancellation.cancellation_id, cancellation.booking_id,
                   cancellation.cancellation_status, cancellation.reason,
                   cancellation.requested_at, cancellation.completed_at,
                   booking.pnr, booking.train_name_snapshot, booking.train_number_snapshot,
                   user.full_name, user.email,
                   COUNT(item.cancellation_item_id) AS passenger_items,
                   COALESCE(SUM(item.cancellation_charge), 0) AS cancellation_charge,
                   COALESCE(SUM(item.refund_amount), 0) AS refund_amount
            FROM cancellations AS cancellation
            JOIN bookings AS booking ON booking.booking_id = cancellation.booking_id
            JOIN users AS user ON user.user_id = cancellation.requested_by_user_id
            LEFT JOIN cancellation_items AS item ON item.cancellation_id = cancellation.cancellation_id
            GROUP BY cancellation.cancellation_id, cancellation.booking_id,
                     cancellation.cancellation_status, cancellation.reason,
                     cancellation.requested_at, cancellation.completed_at,
                     booking.pnr, booking.train_name_snapshot, booking.train_number_snapshot,
                     user.full_name, user.email
            ORDER BY cancellation.requested_at DESC LIMIT 200
        """)
        data["cancellations"] = cursor.fetchall() or []

        cursor.execute("""
            SELECT COUNT(*) AS total_bookings,
                   SUM(booking_status IN ('PENDING_PAYMENT','CONFIRMED','PARTIALLY_CANCELLED')) AS active_bookings,
                   SUM(booking_status = 'CANCELLED') AS cancelled_bookings
            FROM bookings
        """)
        data["summary"] = cursor.fetchone() or {}
        data["summary"]["total_trains"] = len(data["trains"])
        data["summary"]["total_routes"] = len(data["routes"])
        data["summary"]["total_schedules"] = len(data["schedules"])
        data["summary"]["total_cancellations"] = len(data["cancellations"])
        return data
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def update_train_status(train_id, status, connection_factory=None):
    """Enable or disable a train without deleting historical booking snapshots."""
    if isinstance(train_id, bool) or not str(train_id).isdigit() or int(train_id) <= 0:
        raise ValueError("Enter a valid train ID.")
    if status not in ("ACTIVE", "INACTIVE"):
        raise ValueError("Train status must be ACTIVE or INACTIVE.")
    connection = (connection_factory or get_db_connection)()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(
            "UPDATE trains SET train_status = %s WHERE train_id = %s",
            (status, int(train_id)),
        )
        if cursor.rowcount != 1:
            raise LookupError("Train not found.")
        connection.commit()
        return {"train_id": int(train_id), "train_status": status}
    except Exception:
        connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()
