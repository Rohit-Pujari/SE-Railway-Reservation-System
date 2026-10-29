"""Passenger-detail validation and persistence for pending bookings."""

import mysql.connector

from .db import get_db_connection

MAX_PASSENGERS_PER_REQUEST = 6
NAME_MAX_LENGTH = 120
ALLOWED_BERTH_PREFERENCES = {
    "LOWER", "MIDDLE", "UPPER", "SIDE_LOWER", "SIDE_UPPER", "NO_PREFERENCE"
}


class PassengerDetailsValidationError(ValueError):
    """Passenger details are invalid or cannot be attached to the booking."""


def _validate_passengers(passengers):
    if not isinstance(passengers, list) or not passengers:
        raise PassengerDetailsValidationError("Add at least one passenger.")
    if len(passengers) > MAX_PASSENGERS_PER_REQUEST:
        raise PassengerDetailsValidationError("A booking can include at most 6 passengers.")

    validated = []
    for index, passenger in enumerate(passengers, start=1):
        if not isinstance(passenger, dict):
            raise PassengerDetailsValidationError(f"Passenger {index} details are invalid.")

        name = passenger.get("passenger_name")
        age = passenger.get("age")
        gender = passenger.get("gender")
        berth = passenger.get("berth_preference", "NO_PREFERENCE")

        if not isinstance(name, str) or not name.strip() or len(name.strip()) > NAME_MAX_LENGTH:
            raise PassengerDetailsValidationError(
                f"Passenger {index} name must be between 1 and {NAME_MAX_LENGTH} characters."
            )
        if isinstance(age, bool):
            raise PassengerDetailsValidationError(f"Passenger {index} age must be between 0 and 120.")
        try:
            parsed_age = int(age)
        except (TypeError, ValueError):
            raise PassengerDetailsValidationError(f"Passenger {index} age must be a whole number.") from None
        if str(age).strip() != str(parsed_age) or not 0 <= parsed_age <= 120:
            raise PassengerDetailsValidationError(f"Passenger {index} age must be between 0 and 120.")

        if gender is not None:
            if not isinstance(gender, str) or len(gender.strip()) > 30:
                raise PassengerDetailsValidationError(f"Passenger {index} gender must be 30 characters or fewer.")
            gender = gender.strip() or None
        if not isinstance(berth, str) or berth not in ALLOWED_BERTH_PREFERENCES:
            raise PassengerDetailsValidationError(f"Passenger {index} berth preference is invalid.")

        validated.append({
            "passenger_name": name.strip(),
            "age": parsed_age,
            "gender": gender,
            "berth_preference": berth,
        })
    return validated


def save_passenger_details(booking_id, user_id, passengers, connection_factory=None):
    """Attach validated passenger details to an owned, pending booking atomically."""
    try:
        booking_id, user_id = int(booking_id), int(user_id)
    except (TypeError, ValueError):
        raise PassengerDetailsValidationError("Select a valid booking.") from None
    if booking_id <= 0 or user_id <= 0:
        raise PassengerDetailsValidationError("Select a valid booking.")
    validated = _validate_passengers(passengers)

    factory = connection_factory or get_db_connection
    connection = cursor = None
    try:
        connection = factory()
        connection.start_transaction()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """SELECT booking_id, booking_status
               FROM bookings
               WHERE booking_id = %s AND user_id = %s
               FOR UPDATE""",
            (booking_id, user_id),
        )
        booking = cursor.fetchone()
        if not booking:
            raise PassengerDetailsValidationError("Booking was not found.")
        if booking["booking_status"] != "PENDING_PAYMENT":
            raise PassengerDetailsValidationError("Passenger details can only be changed before confirmation.")

        cursor.execute(
            "SELECT COUNT(*) AS passenger_count FROM booking_passengers WHERE booking_id = %s",
            (booking_id,),
        )
        existing = cursor.fetchone()
        if int(existing["passenger_count"]) + len(validated) > MAX_PASSENGERS_PER_REQUEST:
            raise PassengerDetailsValidationError("A booking can include at most 6 passengers.")

        saved = []
        for passenger in validated:
            cursor.execute(
                """INSERT INTO booking_passengers
                       (booking_id, passenger_name, age, gender, berth_preference, passenger_fare)
                   VALUES (%s, %s, %s, %s, %s, 0.00)""",
                (
                    booking_id, passenger["passenger_name"], passenger["age"],
                    passenger["gender"], passenger["berth_preference"],
                ),
            )
            saved.append({
                "passenger_name": passenger["passenger_name"],
                "age": passenger["age"],
                "gender": passenger["gender"],
                "berth_preference": passenger["berth_preference"],
            })
        connection.commit()
        return {"booking_id": booking_id, "passengers_added": len(saved), "passengers": saved}
    except PassengerDetailsValidationError:
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
