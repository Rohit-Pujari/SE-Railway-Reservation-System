"""Health, registration, train search, and administrator authentication API."""

import mysql.connector
from flask import Blueprint, jsonify, request, session
from mysql.connector import IntegrityError
from werkzeug.security import check_password_hash

from .admin_auth import admin_required
from .booking_confirmation import BookingConfirmationError, confirm_booking
from .db import get_db_connection
from .registration import RegistrationValidationError, register_user
from .seat_availability import (
    SeatAvailabilityValidationError,
    get_active_travel_classes,
    get_seat_availability,
)
from .train_search import (
    TrainSearchValidationError,
    get_active_stations,
    search_trains,
)

api = Blueprint("api", __name__, url_prefix="/api")


@api.get("/health")
def health_check():
    return jsonify({"status": "ok", "service": "railway-reservation-api"}), 200


@api.get("/health/db")
def database_health_check():
    connection = None
    try:
        connection = get_db_connection()
        if connection.is_connected():
            return jsonify({"status": "ok", "database": "connected"}), 200
        return jsonify({"status": "error", "database": "unavailable"}), 503
    except mysql.connector.Error:
        return jsonify({"status": "error", "database": "unavailable"}), 503
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


@api.post("/register")
def registration():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"status": "error", "message": "Submit valid registration details."}), 400
    try:
        user = register_user(payload)
    except RegistrationValidationError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except IntegrityError as exc:
        # MySQL error 1062 is ER_DUP_ENTRY. Other integrity failures are not
        # necessarily duplicate emails and must not be reported as such.
        if getattr(exc, "errno", None) == 1062:
            return jsonify({"status": "error", "message": "An account with this email already exists."}), 409
        return jsonify({"status": "error", "message": "Registration could not be completed. Please try again."}), 500
    except mysql.connector.Error:
        return jsonify({"status": "error", "message": "Registration is temporarily unavailable. Please try again."}), 503
    except Exception:
        return jsonify({"status": "error", "message": "Registration could not be completed. Please try again."}), 500
    return jsonify({"status": "ok", "message": "Account created successfully.", "user": user}), 201


@api.post("/login")
def passenger_login():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"status": "error", "message": "Submit an email and password."}), 400

    email, password = payload.get("email"), payload.get("password")
    if not isinstance(email, str) or not isinstance(password, str) or not email.strip() or not password:
        return jsonify({"status": "error", "message": "Email and password are required."}), 400

    connection = cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT user_id, full_name, email, password_hash FROM users "
            "WHERE email = %s AND account_status = 'ACTIVE' AND role = 'PASSENGER' LIMIT 1",
            (email.strip().lower(),),
        )
        user = cursor.fetchone()
    except mysql.connector.Error:
        return jsonify({"status": "error", "message": "Login is temporarily unavailable."}), 503
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

    if not user or not check_password_hash(user["password_hash"], password):
        return jsonify({"status": "error", "message": "Invalid email or password."}), 401

    session.clear()
    session["user_id"] = user["user_id"]
    session["role"] = "PASSENGER"
    session["full_name"] = user["full_name"]
    session["email"] = user["email"]
    session.permanent = True
    return jsonify({
        "status": "ok",
        "message": "Login successful.",
        "user": {"user_id": user["user_id"], "full_name": user["full_name"], "email": user["email"]},
    }), 200


@api.get("/session")
def passenger_session():
    if "user_id" not in session or session.get("role") != "PASSENGER":
        return jsonify({"status": "unauthenticated", "authenticated": False}), 401
    return jsonify({
        "status": "ok",
        "authenticated": True,
        "user": {
            "user_id": session["user_id"],
            "full_name": session.get("full_name", ""),
            "email": session.get("email", ""),
        },
    }), 200


@api.post("/logout")
def passenger_logout():
    session.clear()
    return jsonify({"status": "ok", "message": "Logged out successfully."}), 200


@api.post("/admin/login")
def admin_login():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"status": "error", "message": "Submit an email and password."}), 400

    email, password = payload.get("email"), payload.get("password")
    if not isinstance(email, str) or not isinstance(password, str) or not email.strip() or not password:
        return jsonify({"status": "error", "message": "Email and password are required."}), 400

    connection = cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT user_id, email, password_hash, role, account_status "
            "FROM users WHERE email = %s LIMIT 1",
            (email.strip().lower(),),
        )
        user = cursor.fetchone()
    except mysql.connector.Error:
        return jsonify({"status": "error", "message": "Login is temporarily unavailable."}), 503
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

    if (
        not user
        or user.get("role") != "ADMIN"
        or user.get("account_status") != "ACTIVE"
        or not check_password_hash(user.get("password_hash", ""), password)
    ):
        # Use a generic response to avoid disclosing account roles/existence.
        return jsonify({"status": "error", "message": "Invalid administrator credentials."}), 401

    session.clear()
    session["user_id"] = user["user_id"]
    session["role"] = "ADMIN"
    session["email"] = user["email"]
    session.permanent = True
    return jsonify(
        {
            "status": "ok",
            "message": "Administrator login successful.",
            "admin": {"user_id": user["user_id"], "email": user["email"]},
        }
    ), 200


@api.post("/admin/logout")
@admin_required
def admin_logout():
    session.clear()
    return jsonify({"status": "ok", "message": "Administrator logged out."}), 200


@api.get("/admin/dashboard")
@admin_required
def admin_dashboard():
    return jsonify({"status": "ok", "message": "Administrator access granted."}), 200


@api.get("/travel-classes")
def travel_classes():
    """Return active travel classes for the passenger search form."""
    try:
        classes = get_active_travel_classes()
    except mysql.connector.Error:
        return jsonify({"status": "error", "message": "Travel classes are temporarily unavailable."}), 503
    except Exception:
        return jsonify({"status": "error", "message": "Travel classes could not be loaded."}), 500
    return jsonify({"status": "ok", "travel_classes": classes}), 200


@api.get("/seats/availability")
def seat_availability():
    """Return class-specific available seats for a route segment and date."""
    try:
        result = get_seat_availability(
            request.args.get("schedule_id"),
            request.args.get("source_station_id"),
            request.args.get("destination_station_id"),
            request.args.get("journey_date"),
            request.args.get("class_id"),
        )
    except SeatAvailabilityValidationError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except mysql.connector.Error:
        return jsonify({"status": "error", "message": "Seat availability is temporarily unavailable."}), 503
    except Exception:
        return jsonify({"status": "error", "message": "Seat availability could not be checked."}), 500
    return jsonify({"status": "ok", **result}), 200


@api.get("/stations")
def stations():
    """Return active stations for the passenger search form."""
    try:
        return jsonify({"status": "ok", "stations": get_active_stations()}), 200
    except mysql.connector.Error:
        return jsonify({"status": "error", "message": "Stations are temporarily unavailable."}), 503
    except Exception:
        return jsonify({"status": "error", "message": "Stations could not be loaded."}), 500


@api.get("/trains/search")
def train_search():
    """Find scheduled trains that stop at the requested origin and destination."""
    try:
        results = search_trains(
            request.args.get("source_station_id"),
            request.args.get("destination_station_id"),
            request.args.get("journey_date"),
            request.args.get("class_id"),
        )
    except TrainSearchValidationError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except mysql.connector.Error:
        return jsonify({"status": "error", "message": "Train search is temporarily unavailable."}), 503
    except Exception:
        return jsonify({"status": "error", "message": "Train search could not be completed."}), 500

    return jsonify({"status": "ok", "count": len(results), "trains": results}), 200



@api.post("/bookings/<int:booking_id>/confirm")
def booking_confirmation():
    """Atomically confirm a pending booking and allocate non-conflicting seats."""
    if "user_id" not in session or session.get("role") != "PASSENGER":
        return jsonify({"status": "error", "message": "Please log in to confirm a booking."}), 401
    try:
        result = confirm_booking(booking_id, session["user_id"])
    except BookingConfirmationError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 409
    except mysql.connector.Error:
        return jsonify({"status": "error", "message": "Booking could not be confirmed right now."}), 503
    except Exception:
        return jsonify({"status": "error", "message": "Booking could not be confirmed."}), 500
    return jsonify({"status": "ok", **result}), 200
