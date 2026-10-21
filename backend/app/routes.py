"""Initial health endpoints for the backend."""

from flask import Blueprint, jsonify
import mysql.connector

from .db import get_db_connection

api = Blueprint("api", __name__, url_prefix="/api")


@api.get("/health")
def health_check():
    """Report that the API process is responding."""
    return jsonify({"status": "ok", "service": "railway-reservation-api"}), 200


@api.get("/health/db")
def database_health_check():
    """Check MySQL connectivity without exposing credentials or server details."""
    connection = None
    try:
        connection = get_db_connection()
        if connection.is_connected():
            return jsonify({"status": "ok", "database": "connected"}), 200
        return jsonify({"status": "error", "database": "unavailable"}), 503
    except mysql.connector.Error:
        return jsonify({"status": "error", "database": "unavailable"}), 503
    finally:
        if connection is not None and connection.is_connected():
            connection.close()
