"""User registration validation and persistence helpers."""

import re

from werkzeug.security import generate_password_hash

from .db import get_db_connection

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
NAME_MAX_LENGTH = 120
EMAIL_MAX_LENGTH = 254
PHONE_MAX_LENGTH = 25


class RegistrationValidationError(ValueError):
    """Raised when submitted registration data is invalid."""


def validate_registration(data):
    """Validate registration fields and return normalized safe values."""
    if not isinstance(data, dict):
        raise RegistrationValidationError("Submit registration details.")

    full_name = data.get("full_name", "")
    email = data.get("email", "")
    phone_number = data.get("phone_number", "")
    password = data.get("password", "")

    if not all(isinstance(value, str) for value in (full_name, email, phone_number, password)):
        raise RegistrationValidationError("All fields must contain text.")

    full_name = full_name.strip()
    email = email.strip().lower()
    phone_number = phone_number.strip()

    if not full_name:
        raise RegistrationValidationError("Full name is required.")
    if len(full_name) > NAME_MAX_LENGTH:
        raise RegistrationValidationError("Full name must be 120 characters or fewer.")
    if not email:
        raise RegistrationValidationError("Email is required.")
    if len(email) > EMAIL_MAX_LENGTH or not EMAIL_RE.fullmatch(email):
        raise RegistrationValidationError("Enter a valid email address.")
    if phone_number and len(phone_number) > PHONE_MAX_LENGTH:
        raise RegistrationValidationError("Phone number must be 25 characters or fewer.")
    if len(password) < 8 or not any(c.islower() for c in password) or not any(c.isupper() for c in password) or not any(c.isdigit() for c in password):
        raise RegistrationValidationError("Password must be at least 8 characters and include uppercase, lowercase, and a number.")

    return {
        "full_name": full_name,
        "email": email,
        "phone_number": phone_number or None,
        "password": password,
    }


def register_user(data, connection_factory=None):
    """Create a passenger account, storing only a Werkzeug password hash."""
    values = validate_registration(data)
    password_hash = generate_password_hash(values["password"])
    factory = connection_factory or get_db_connection
    connection = None
    cursor = None
    try:
        connection = factory()
        cursor = connection.cursor()
        cursor.execute(
            """INSERT INTO users (full_name, email, phone_number, password_hash)
               VALUES (%s, %s, %s, %s)""",
            (values["full_name"], values["email"], values["phone_number"], password_hash),
        )
        user_id = cursor.lastrowid
        connection.commit()
        return {"user_id": user_id, "full_name": values["full_name"], "email": values["email"]}
    except Exception:
        if connection is not None:
            try:
                connection.rollback()
            except Exception:
                pass
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
