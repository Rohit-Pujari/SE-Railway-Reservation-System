"""Administrator inspection and control of per-schedule seat inventory."""

from .db import get_db_connection


class SeatManagementValidationError(ValueError):
    """Raised when a schedule or seat inventory value is invalid."""


class SeatManagementConflictError(ValueError):
    """Raised when a seat cannot safely be taken out of service."""


def _positive_id(value, label):
    if isinstance(value, bool):
        raise SeatManagementValidationError(f"Select a valid {label}.")
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise SeatManagementValidationError(f"Select a valid {label}.") from None
    if parsed <= 0 or str(value).strip() != str(parsed):
        raise SeatManagementValidationError(f"Select a valid {label}.")
    return parsed


def validate_operational_status(value):
    if value not in {"IN_SERVICE", "OUT_OF_SERVICE"}:
        raise SeatManagementValidationError(
            "Seat status must be IN_SERVICE or OUT_OF_SERVICE."
        )
    return value


def get_schedule_seats(schedule_id, connection_factory=None):
    """Return the selected journey's physical seats and active allocation details."""
    schedule = _positive_id(schedule_id, "schedule")
    connection = (connection_factory or get_db_connection)()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """SELECT schedule.schedule_id, schedule.schedule_status,
                      schedule.departure_at, schedule.arrival_at,
                      train.train_number, train.train_name, route.route_name
               FROM train_schedules AS schedule
               JOIN trains AS train ON train.train_id = schedule.train_id
               JOIN routes AS route ON route.route_id = schedule.route_id
               WHERE schedule.schedule_id = %s""",
            (schedule,),
        )
        schedule_row = cursor.fetchone()
        if schedule_row is None:
            raise LookupError("Train schedule not found.")

        cursor.execute(
            """SELECT scheduled_seat.schedule_seat_id,
                      scheduled_seat.operational_status,
                      physical_seat.coach_number, physical_seat.seat_number,
                      travel_class.class_id, travel_class.class_code,
                      travel_class.class_name,
                      EXISTS (
                          SELECT 1
                          FROM seat_allocations AS active_allocation
                          WHERE active_allocation.schedule_id = scheduled_seat.schedule_id
                            AND active_allocation.schedule_seat_id = scheduled_seat.schedule_seat_id
                            AND (
                                active_allocation.allocation_status = 'CONFIRMED'
                                OR (
                                    active_allocation.allocation_status = 'HELD'
                                    AND active_allocation.hold_expires_at > CURRENT_TIMESTAMP
                                )
                            )
                      ) AS has_active_allocation,
                      (
                          SELECT GROUP_CONCAT(DISTINCT active_booking.pnr
                                              ORDER BY active_booking.pnr SEPARATOR ', ')
                          FROM seat_allocations AS active_allocation
                          JOIN bookings AS active_booking
                            ON active_booking.booking_id = active_allocation.booking_id
                          WHERE active_allocation.schedule_id = scheduled_seat.schedule_id
                            AND active_allocation.schedule_seat_id = scheduled_seat.schedule_seat_id
                            AND (
                                active_allocation.allocation_status = 'CONFIRMED'
                                OR (
                                    active_allocation.allocation_status = 'HELD'
                                    AND active_allocation.hold_expires_at > CURRENT_TIMESTAMP
                                )
                            )
                      ) AS active_pnrs
               FROM schedule_seats AS scheduled_seat
               JOIN seats AS physical_seat ON physical_seat.seat_id = scheduled_seat.seat_id
               JOIN travel_classes AS travel_class ON travel_class.class_id = scheduled_seat.class_id
               WHERE scheduled_seat.schedule_id = %s
               ORDER BY travel_class.class_code, physical_seat.coach_number,
                        physical_seat.seat_number""",
            (schedule,),
        )
        seats = cursor.fetchall() or []
        for seat in seats:
            seat["schedule_seat_id"] = int(seat["schedule_seat_id"])
            seat["class_id"] = int(seat["class_id"])
            seat["has_active_allocation"] = bool(seat["has_active_allocation"])
        return {"schedule": schedule_row, "seats": seats}
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def update_schedule_seat_status(
    schedule_id, schedule_seat_id, operational_status, connection_factory=None
):
    """Change a seat's service state without invalidating active passenger allocations."""
    schedule = _positive_id(schedule_id, "schedule")
    scheduled_seat = _positive_id(schedule_seat_id, "scheduled seat")
    status = validate_operational_status(operational_status)
    connection = (connection_factory or get_db_connection)()
    cursor = None
    try:
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """SELECT schedule_seat_id, operational_status
               FROM schedule_seats
               WHERE schedule_id = %s AND schedule_seat_id = %s
               FOR UPDATE""",
            (schedule, scheduled_seat),
        )
        seat = cursor.fetchone()
        if seat is None:
            raise LookupError("Seat was not found in this train schedule.")

        if status == "OUT_OF_SERVICE":
            cursor.execute(
                """SELECT allocation_id
                   FROM seat_allocations
                   WHERE schedule_id = %s AND schedule_seat_id = %s
                     AND (
                         allocation_status = 'CONFIRMED'
                         OR (
                             allocation_status = 'HELD'
                             AND hold_expires_at > CURRENT_TIMESTAMP
                         )
                     )
                   LIMIT 1 FOR UPDATE""",
                (schedule, scheduled_seat),
            )
            if cursor.fetchone() is not None:
                raise SeatManagementConflictError(
                    "This seat has an active booking or reservation hold and cannot be taken out of service."
                )

        cursor.execute(
            """UPDATE schedule_seats
               SET operational_status = %s
               WHERE schedule_id = %s AND schedule_seat_id = %s""",
            (status, schedule, scheduled_seat),
        )
        connection.commit()
        return {
            "schedule_id": schedule,
            "schedule_seat_id": scheduled_seat,
            "operational_status": status,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()
