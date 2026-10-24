"""Health, registration, train search, and administrator authentication API."""

import mysql.connector
from flask import Blueprint, jsonify, request, session
from mysql.connector import IntegrityError
from werkzeug.security import check_password_hash

from .admin_auth import admin_required
from .db import get_db_connection
from .registration import RegistrationValidationError, register_user
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
        )
    except TrainSearchValidationError as exc:
        return jsonify({"status": "error", "message": str(exc)}), 400
    except mysql.connector.Error:
        return jsonify({"status": "error", "message": "Train search is temporarily unavailable."}), 503
    except Exception:
        return jsonify({"status": "error", "message": "Train search could not be completed."}), 500

    return jsonify({"status": "ok", "count": len(results), "trains": results}), 200
