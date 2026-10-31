"""Administrator train creation with validation and database uniqueness checks."""

import re

from .db import get_db_connection


TRAIN_NUMBER_PATTERN = re.compile(r"^[A-Za-z0-9-]{1,20}$")


class TrainValidationError(ValueError):
    """Raised when required train details are missing or invalid."""


class DuplicateTrainNumberError(ValueError):
    """Raised when a train number is already registered."""


def validate_train_details(train_number, train_name, train_status="ACTIVE"):
    """Normalize and validate the fields supported by the trains table."""
    if not isinstance(train_number, str):
        raise TrainValidationError("Train number is required.")
    number = train_number.strip().upper()
    if not number:
        raise TrainValidationError("Train number is required.")
    if not TRAIN_NUMBER_PATTERN.fullmatch(number):
        raise TrainValidationError("Train number must contain 1–20 letters, numbers, or hyphens.")

    if not isinstance(train_name, str):
        raise TrainValidationError("Train name is required.")
    name = " ".join(train_name.split())
    if not name:
        raise TrainValidationError("Train name is required.")
    if len(name) > 150:
        raise TrainValidationError("Train name must be 150 characters or fewer.")

    if train_status is None:
        train_status = "ACTIVE"
    if not isinstance(train_status, str) or train_status.upper() not in ("ACTIVE", "INACTIVE"):
        raise TrainValidationError("Train status must be ACTIVE or INACTIVE.")
    return number, name, train_status.upper()


def create_train(train_number, train_name, train_status="ACTIVE", connection_factory=None):
    """Insert a train, relying on the unique train-number index as the final guard."""
    number, name, status = validate_train_details(train_number, train_name, train_status)
    connection = (connection_factory or get_db_connection)()
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute("SELECT train_id FROM trains WHERE train_number = %s LIMIT 1", (number,))
        if cursor.fetchone() is not None:
            raise DuplicateTrainNumberError("A train with this train number already exists.")
        cursor.execute(
            "INSERT INTO trains (train_number, train_name, train_status) VALUES (%s, %s, %s)",
            (number, name, status),
        )
        train_id = cursor.lastrowid
        connection.commit()
        return {"train_id": train_id, "train_number": number, "train_name": name, "train_status": status}
    except Exception:
        connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()



def update_train(train_id, train_number=None, train_name=None, train_status=None, connection_factory=None):
    """Update editable train details while preserving fields omitted by the caller."""
    if isinstance(train_id, bool) or not str(train_id).isdigit() or int(train_id) <= 0:
        raise ValueError("Enter a valid train ID.")

    connection = (connection_factory or get_db_connection)()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT train_id, train_number, train_name, train_status "
            "FROM trains WHERE train_id = %s FOR UPDATE",
            (int(train_id),),
        )
        existing = cursor.fetchone()
        if existing is None:
            raise LookupError("Train not found.")

        number, name, status = validate_train_details(
            existing["train_number"] if train_number is None else train_number,
            existing["train_name"] if train_name is None else train_name,
            existing["train_status"] if train_status is None else train_status,
        )
        cursor.execute(
            "SELECT train_id FROM trains WHERE train_number = %s AND train_id <> %s LIMIT 1",
            (number, int(train_id)),
        )
        if cursor.fetchone() is not None:
            raise DuplicateTrainNumberError("A train with this train number already exists.")

        cursor.execute(
            "UPDATE trains SET train_number = %s, train_name = %s, train_status = %s "
            "WHERE train_id = %s",
            (number, name, status, int(train_id)),
        )
        connection.commit()
        return {
            "train_id": int(train_id),
            "train_number": number,
            "train_name": name,
            "train_status": status,
        }
    except Exception:
        connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()
