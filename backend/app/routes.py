""""API endpoints for health checks, registration, and train search."""

import mysql.connector
from flask import Blueprint, jsonify, request
from mysql.connector import IntegrityError

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
