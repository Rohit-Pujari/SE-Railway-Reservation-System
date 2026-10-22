"""API endpoints for health checks, registration, and session authentication."""

import mysql.connector
from flask import Blueprint, jsonify, request, session
from mysql.connector import IntegrityError
from werkzeug.security import check_password_hash

from .db import get_db_connection
from .registration import RegistrationValidationError, register_user

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
        if getattr(exc, "errno", None) == 1062:
            return jsonify({"status": "error", "message": "An account with this email already exists."}), 409
        return jsonify({"status": "error", "message": "Registration could not be completed. Please try again."}), 500
    except mysql.connector.Error:
        return jsonify({"status": "error", "message": "Registration is temporarily unavailable. Please try again."}), 503
    except Exception:
        return jsonify({"status": "error", "message": "Registration could not be completed. Please try again."}), 500
    return jsonify({"status": "ok", "message": "Account created successfully.", "user": user}), 201


@api.post("/login")
def login():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"status": "error", "message": "Submit valid login details."}), 400
    email = payload.get("email")
    password = payload.get("password")
    if not isinstance(email, str) or not isinstance(password, str) or not email.strip() or not password:
        return jsonify({"status": "error", "message": "Email and password are required."}), 400

    connection = None
    cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT id, full_name, email, password_hash FROM users WHERE email = %s LIMIT 1",
            (email.strip().lower(),),
        )
        user = cursor.fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            return jsonify({"status": "error", "message": "Invalid email or password."}), 401

        session.clear()
        session["user_id"] = user["id"]
        session["user_name"] = user["full_name"]
        session["user_email"] = user["email"]
        return jsonify({
            "status": "ok",
            "message": "Login successful.",
            "user": {"id": user["id"], "full_name": user["full_name"], "email": user["email"]},
        }), 200
    except mysql.connector.Error:
        return jsonify({"status": "error", "message": "Login is temporarily unavailable. Please try again."}), 503
    except Exception:
        return jsonify({"status": "error", "message": "Login could not be completed. Please try again."}), 500
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


@api.get("/session")
def current_session():
    if "user_id" not in session:
        return jsonify({"status": "unauthenticated", "authenticated": False}), 401
    return jsonify({
        "status": "ok",
        "authenticated": True,
        "user": {
            "id": session["user_id"],
            "full_name": session.get("user_name", ""),
            "email": session.get("user_email", ""),
        },
    }), 200


@api.post("/logout")
def logout():
    session.clear()
    return jsonify({"status": "ok", "message": "Logged out successfully."}), 200
