"""Read a passenger's own previous and upcoming train bookings."""

from .db import get_db_connection


def _positive_user_id(value):
    if isinstance(value, bool):
        raise ValueError("A valid passenger account is required.")
    try:
        user_id = int(value)
    except (TypeError, ValueError):
        raise ValueError("A valid passenger account is required.") from None
    if user_id <= 0 or str(value).strip() != str(user_id):
        raise ValueError("A valid passenger account is required.")
    return user_id


def _iso(value):
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else value


def get_booking_history(user_id, connection_factory=None):
    """Return grouped upcoming and previous bookings owned by the passenger."""
    owner_id = _positive_user_id(user_id)
    factory = connection_factory or get_db_connection
    connection = cursor = None
    try:
        connection = factory()
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
                      booking.other_charges, booking.total_fare,
                      booking.currency_code, booking.created_at,
                      booking.confirmed_at,
                      CASE WHEN booking.departure_at_snapshot >= CURRENT_TIMESTAMP
                           THEN 'UPCOMING' ELSE 'PREVIOUS' END AS trip_type,
                      passenger.booking_passenger_id, passenger.passenger_name,
                      passenger.age, passenger.gender, passenger.berth_preference,
                      passenger.passenger_fare, allocation.allocation_status,
                      allocation.hold_expires_at,
                      physical_seat.coach_number, physical_seat.seat_number
               FROM bookings AS booking
               LEFT JOIN booking_passengers AS passenger
                 ON passenger.booking_id = booking.booking_id
               LEFT JOIN seat_allocations AS allocation
                 ON allocation.booking_id = booking.booking_id
                AND allocation.booking_passenger_id = passenger.booking_passenger_id
               LEFT JOIN schedule_seats AS scheduled_seat
                 ON scheduled_seat.schedule_id = allocation.schedule_id
                AND scheduled_seat.schedule_seat_id = allocation.schedule_seat_id
               LEFT JOIN seats AS physical_seat
                 ON physical_seat.seat_id = scheduled_seat.seat_id
               WHERE booking.user_id = %s
               ORDER BY booking.departure_at_snapshot ASC,
                        booking.created_at DESC,
                        passenger.booking_passenger_id ASC""",
            (owner_id,),
        )
        rows = cursor.fetchall() or []
        grouped = {}
        for row in rows:
            booking_id = int(row["booking_id"])
            if booking_id not in grouped:
                grouped[booking_id] = {
                    "booking_id": booking_id,
                    "pnr": row["pnr"],
                    "booking_status": row["booking_status"],
                    "trip_type": row["trip_type"],
                    "train_number": row["train_number_snapshot"],
                    "train_name": row["train_name_snapshot"],
                    "source_station_code": row["boarding_station_code_snapshot"],
                    "source_station_name": row["boarding_station_name_snapshot"],
                    "destination_station_code": row["alighting_station_code_snapshot"],
                    "destination_station_name": row["alighting_station_name_snapshot"],
                    "departure_at": _iso(row["departure_at_snapshot"]),
                    "arrival_at": _iso(row["arrival_at_snapshot"]),
                    "class_code": row["class_code_snapshot"],
                    "base_fare_total": float(row["base_fare_total"] or 0),
                    "other_charges": float(row["other_charges"] or 0),
                    "total_fare": float(row["total_fare"] or 0),
                    "currency_code": row["currency_code"],
                    "created_at": _iso(row["created_at"]),
                    "confirmed_at": _iso(row["confirmed_at"]),
                    "passengers": [],
                }
            if row.get("booking_passenger_id") is not None:
                grouped[booking_id]["passengers"].append({
                    "passenger_id": int(row["booking_passenger_id"]),
                    "passenger_name": row["passenger_name"],
                    "age": row["age"],
                    "gender": row["gender"],
                    "berth_preference": row["berth_preference"],
                    "passenger_fare": float(row["passenger_fare"] or 0),
                    "allocation_status": row["allocation_status"],
                    "hold_expires_at": _iso(row["hold_expires_at"]),
                    "coach_number": row["coach_number"],
                    "seat_number": row["seat_number"],
                })
        bookings = list(grouped.values())
        return {
            "upcoming": [item for item in bookings if item["trip_type"] == "UPCOMING"],
            "previous": [item for item in bookings if item["trip_type"] == "PREVIOUS"],
            "count": len(bookings),
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
