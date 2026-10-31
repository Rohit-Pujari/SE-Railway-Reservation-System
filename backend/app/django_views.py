"""DRF endpoints adapted to the existing parameterized MySQL service layer."""

from functools import wraps
import mimetypes
from pathlib import Path

import mysql.connector
from django.conf import settings
from django.http import Http404, HttpResponse, JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from mysql.connector import IntegrityError
from rest_framework.decorators import api_view
from rest_framework.exceptions import ParseError, UnsupportedMediaType
from rest_framework.request import Request
from rest_framework.response import Response

from .booking import BookingRequestError, BookingUnavailableError, create_booking
from .booking_history import get_booking_history
from .booking_cancellation import (
    BookingCancellationError,
    BookingCancellationNotFound,
    cancel_booking,
)
from .booking_status import get_booking_status
from .db import get_db_connection
from .fare_calculation import FareCalculationError, calculate_booking_fare
from .passenger_details import PassengerDetailsValidationError, save_passenger_details
from .registration import RegistrationValidationError, register_user
from .seat_availability import (
    SeatAvailabilityValidationError,
    get_active_travel_classes,
    get_seat_availability,
)
from .train_search import TrainSearchValidationError, get_active_stations, search_trains
from werkzeug.security import check_password_hash


def endpoint(methods):
    """Build a DRF endpoint protected by Django's CSRF middleware."""
    def decorate(view):
        protected_view = csrf_protect(api_view(methods)(view))
        # api_view marks callbacks csrf_exempt because DRF normally applies
        # authentication-specific CSRF checks. This app uses signed sessions
        # with manual role checks, so require middleware-level CSRF on every
        # unsafe API method, including anonymous login/registration requests.
        if hasattr(protected_view, "csrf_exempt"):
            delattr(protected_view, "csrf_exempt")
        return protected_view
    return decorate


def _payload(request):
    try:
        data = request.data
    except (ParseError, UnsupportedMediaType):
        return None
    return data if isinstance(data, dict) else None


def _user_id(request):
    if request.session.get("role") != "PASSENGER":
        return None
    return request.session.get("user_id")


def _admin_required(view):
    @wraps(view)
    def wrapped(request: Request, *args, **kwargs):
        if not request.session.get("user_id"):
            return Response({"status": "error", "message": "Authentication required."}, status=401)
        if request.session.get("role") != "ADMIN":
            return Response({"status": "error", "message": "Administrator access required."}, status=403)
        return view(request, *args, **kwargs)
    return wrapped


@ensure_csrf_cookie
def csrf_token(request):
    return JsonResponse({"csrfToken": get_token(request)})


@endpoint(["GET"])
def health_check(request):
    return Response({"status": "ok", "service": "railway-reservation-api"})


@endpoint(["GET"])
def database_health_check(request):
    connection = None
    try:
        connection = get_db_connection()
        if connection.is_connected():
            return Response({"status": "ok", "database": "connected"})
        return Response({"status": "error", "database": "unavailable"}, status=503)
    except mysql.connector.Error:
        return Response({"status": "error", "database": "unavailable"}, status=503)
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


@endpoint(["POST"])
def registration(request):
    payload = _payload(request)
    if payload is None:
        return Response({"status": "error", "message": "Submit valid registration details."}, status=400)
    try:
        user = register_user(payload)
    except RegistrationValidationError as exc:
        return Response({"status": "error", "message": str(exc)}, status=400)
    except IntegrityError as exc:
        if getattr(exc, "errno", None) == 1062:
            return Response({"status": "error", "message": "An account with this email already exists."}, status=409)
        return Response({"status": "error", "message": "Registration could not be completed. Please try again."}, status=500)
    except mysql.connector.Error:
        return Response({"status": "error", "message": "Registration is temporarily unavailable. Please try again."}, status=503)
    except Exception:
        return Response({"status": "error", "message": "Registration could not be completed. Please try again."}, status=500)
    return Response({"status": "ok", "message": "Account created successfully.", "user": user}, status=201)


@endpoint(["POST"])
def passenger_login(request):
    payload = _payload(request)
    if payload is None:
        return Response({"status": "error", "message": "Submit an email and password."}, status=400)
    email, password = payload.get("email"), payload.get("password")
    if not isinstance(email, str) or not isinstance(password, str) or not email.strip() or not password:
        return Response({"status": "error", "message": "Email and password are required."}, status=400)
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
        return Response({"status": "error", "message": "Login is temporarily unavailable."}, status=503)
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
        return Response({"status": "error", "message": "Invalid email or password."}, status=401)
    request.session.flush()
    request.session["user_id"] = user["user_id"]
    request.session["role"] = "PASSENGER"
    return Response({"status": "ok", "message": "Login successful.", "user": {
        "user_id": user["user_id"], "full_name": user["full_name"], "email": user["email"],
    }})


@endpoint(["GET"])
def passenger_session(request):
    if _user_id(request) is None:
        return Response({"status": "unauthenticated", "authenticated": False}, status=401)
    connection = cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT user_id, full_name, email FROM users "
            "WHERE user_id = %s AND role = 'PASSENGER' AND account_status = 'ACTIVE' LIMIT 1",
            (request.session["user_id"],),
        )
        user = cursor.fetchone()
    except mysql.connector.Error:
        return Response({"status": "error", "message": "Session is temporarily unavailable."}, status=503)
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
    if not user:
        request.session.flush()
        return Response({"status": "unauthenticated", "authenticated": False}, status=401)
    return Response({"status": "ok", "authenticated": True, "user": user})


@endpoint(["POST"])
def passenger_logout(request):
    request.session.flush()
    return Response({"status": "ok", "message": "Logged out successfully."})


@endpoint(["POST"])
def admin_login(request):
    payload = _payload(request)
    if payload is None:
        return Response({"status": "error", "message": "Submit an email and password."}, status=400)
    email, password = payload.get("email"), payload.get("password")
    if not isinstance(email, str) or not isinstance(password, str) or not email.strip() or not password:
        return Response({"status": "error", "message": "Email and password are required."}, status=400)
    connection = cursor = None
    try:
        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT user_id, email, password_hash, role, account_status FROM users WHERE email = %s LIMIT 1",
            (email.strip().lower(),),
        )
        user = cursor.fetchone()
    except mysql.connector.Error:
        return Response({"status": "error", "message": "Login is temporarily unavailable."}, status=503)
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
    if (not user or user.get("role") != "ADMIN" or user.get("account_status") != "ACTIVE"
            or not check_password_hash(user.get("password_hash", ""), password)):
        return Response({"status": "error", "message": "Invalid administrator credentials."}, status=401)
    request.session.flush()
    request.session["user_id"] = user["user_id"]
    request.session["role"] = "ADMIN"
    return Response({"status": "ok", "message": "Administrator login successful.", "admin": {
        "user_id": user["user_id"], "email": user["email"],
    }})


@endpoint(["POST"])
@_admin_required
def admin_logout(request):
    request.session.flush()
    return Response({"status": "ok", "message": "Administrator logged out."})


@endpoint(["GET"])
def travel_classes(request):
    try:
        return Response({"status": "ok", "travel_classes": get_active_travel_classes()})
    except mysql.connector.Error:
        return Response({"status": "error", "message": "Travel classes are temporarily unavailable."}, status=503)
    except Exception:
        return Response({"status": "error", "message": "Travel classes could not be loaded."}, status=500)


@endpoint(["GET"])
def seat_availability(request):
    try:
        result = get_seat_availability(*(request.query_params.get(key) for key in (
            "schedule_id", "source_station_id", "destination_station_id", "journey_date", "class_id",
        )))
    except SeatAvailabilityValidationError as exc:
        return Response({"status": "error", "message": str(exc)}, status=400)
    except mysql.connector.Error:
        return Response({"status": "error", "message": "Seat availability is temporarily unavailable."}, status=503)
    except Exception:
        return Response({"status": "error", "message": "Seat availability could not be checked."}, status=500)
    return Response({"status": "ok", **result})


@endpoint(["GET"])
def stations(request):
    try:
        return Response({"status": "ok", "stations": get_active_stations()})
    except mysql.connector.Error:
        return Response({"status": "error", "message": "Stations are temporarily unavailable."}, status=503)
    except Exception:
        return Response({"status": "error", "message": "Stations could not be loaded."}, status=500)


@endpoint(["GET"])
def train_search(request):
    try:
        results = search_trains(*(request.query_params.get(key) for key in (
            "source_station_id", "destination_station_id", "journey_date", "class_id",
        )))
    except TrainSearchValidationError as exc:
        return Response({"status": "error", "message": str(exc)}, status=400)
    except mysql.connector.Error:
        return Response({"status": "error", "message": "Train search is temporarily unavailable."}, status=503)
    except Exception:
        return Response({"status": "error", "message": "Train search could not be completed."}, status=500)
    return Response({"status": "ok", "count": len(results), "trains": results})


@endpoint(["POST"])
def booking_create(request):
    user_id = _user_id(request)
    if user_id is None:
        return Response({"status": "error", "message": "Please log in to book a train."}, status=401)
    payload = _payload(request)
    if payload is None:
        return Response({"status": "error", "message": "Submit booking details as JSON."}, status=400)
    try:
        result = create_booking(user_id, payload.get("schedule_id"), payload.get("source_station_id"),
            payload.get("destination_station_id"), payload.get("journey_date"), payload.get("class_id"),
            payload.get("passengers"), payload.get("idempotency_key"))
    except BookingUnavailableError as exc:
        return Response({"status": "error", "message": str(exc)}, status=409)
    except (BookingRequestError, PassengerDetailsValidationError) as exc:
        return Response({"status": "error", "message": str(exc)}, status=400)
    except IntegrityError as exc:
        if getattr(exc, "errno", None) == 1062:
            return Response({"status": "error", "message": "This booking request was already received. Retry the same request."}, status=409)
        return Response({"status": "error", "message": "Booking could not be created."}, status=500)
    except mysql.connector.Error:
        return Response({"status": "error", "message": "Booking is temporarily unavailable."}, status=503)
    except Exception:
        return Response({"status": "error", "message": "Booking could not be created."}, status=500)
    return Response({"status": "ok", **result}, status=200 if result.get("replayed") else 201)


@endpoint(["GET"])
def passenger_booking_history(request):
    user_id = _user_id(request)
    if user_id is None:
        return Response({"status": "error", "message": "Please log in to view your booking history."}, status=401)
    try:
        result = get_booking_history(user_id)
    except mysql.connector.Error:
        return Response({"status": "error", "message": "Booking history is temporarily unavailable."}, status=503)
    except Exception:
        return Response({"status": "error", "message": "Booking history could not be loaded."}, status=500)
    return Response({"status": "ok", **result})


@endpoint(["POST"])
def booking_passenger_details(request, booking_id):
    user_id = _user_id(request)
    if user_id is None:
        return Response({"status": "error", "message": "Please log in to add passenger details."}, status=401)
    payload = _payload(request)
    if payload is None:
        return Response({"status": "error", "message": "Submit passenger details as JSON."}, status=400)
    try:
        result = save_passenger_details(booking_id, user_id, payload.get("passengers"))
    except PassengerDetailsValidationError as exc:
        return Response({"status": "error", "message": str(exc)}, status=400)
    except mysql.connector.Error:
        return Response({"status": "error", "message": "Passenger details could not be saved right now."}, status=503)
    except Exception:
        return Response({"status": "error", "message": "Passenger details could not be saved."}, status=500)
    return Response({"status": "ok", **result}, status=201)


@endpoint(["POST"])
def booking_fare(request, booking_id):
    user_id = _user_id(request)
    if user_id is None:
        return Response({"status": "error", "message": "Please log in to calculate the fare."}, status=401)
    try:
        result = calculate_booking_fare(booking_id, user_id)
    except FareCalculationError as exc:
        return Response({"status": "error", "message": str(exc)}, status=409)
    except mysql.connector.Error:
        return Response({"status": "error", "message": "Fare calculation is temporarily unavailable."}, status=503)
    except Exception:
        return Response({"status": "error", "message": "Fare could not be calculated."}, status=500)
    return Response({"status": "ok", **result})


@ensure_csrf_cookie
def frontend(request):
    index = settings.FRONTEND_DIST / "index.html"
    if not index.is_file():
        return JsonResponse({"message": "React frontend is not built. Run `npm run build` in frontend/."}, status=503)
    return HttpResponse(index.read_bytes(), content_type="text/html")


def frontend_asset(request, asset_path):
    root = settings.FRONTEND_DIST.resolve()
    asset = (root / asset_path).resolve()
    if root not in asset.parents or not asset.is_file():
        raise Http404
    return HttpResponse(asset.read_bytes(), content_type=mimetypes.guess_type(asset.name)[0] or "application/octet-stream")



@endpoint(["GET"])
def passenger_booking_status(request):
    user_id = _user_id(request)
    if user_id is None:
        return Response({"status": "error", "message": "Please log in to check a booking."}, status=401)
    pnr = request.query_params.get("pnr")
    try:
        result = get_booking_status(user_id, pnr)
    except ValueError as exc:
        return Response({"status": "error", "message": str(exc)}, status=400)
    except mysql.connector.Error:
        return Response({"status": "error", "message": "Booking status is temporarily unavailable."}, status=503)
    except Exception:
        return Response({"status": "error", "message": "Booking status could not be loaded."}, status=500)
    if result is None:
        return Response({"status": "error", "message": "No booking with that PNR was found in your account."}, status=404)
    return Response({"status": "ok", **result})



@endpoint(["POST"])
def passenger_booking_cancel(request, booking_id):
    user_id = _user_id(request)
    if user_id is None:
        return Response({"status": "error", "message": "Please log in to cancel a booking."}, status=401)
    payload = _payload(request)
    if payload is None:
        return Response({"status": "error", "message": "Submit valid cancellation details."}, status=400)
    try:
        result = cancel_booking(user_id, booking_id, payload.get("reason"))
    except BookingCancellationNotFound as exc:
        return Response({"status": "error", "message": str(exc)}, status=404)
    except BookingCancellationError as exc:
        return Response({"status": "error", "message": str(exc)}, status=400)
    except mysql.connector.Error:
        return Response({"status": "error", "message": "Cancellation is temporarily unavailable. Please try again."}, status=503)
    except Exception:
        return Response({"status": "error", "message": "Booking could not be cancelled."}, status=500)
    return Response({"status": "ok", **result})


@endpoint(["GET"])
@_admin_required
def admin_dashboard_data(request):
    """Return the administrator's operational dashboard data."""
    from .admin_dashboard import get_admin_dashboard
    try:
        return Response({"status": "ok", **get_admin_dashboard()})
    except mysql.connector.Error:
        return Response({"status": "error", "message": "Dashboard data is temporarily unavailable."}, status=503)
    except Exception:
        return Response({"status": "error", "message": "Dashboard data could not be loaded."}, status=500)


@endpoint(["PATCH", "DELETE"])
@_admin_required
def admin_train_update(request, train_id):
    """Update train details or safely remove a train for an administrator."""
    if request.method == "DELETE":
        from .train_management import remove_train
        try:
            result = remove_train(train_id)
        except ValueError as exc:
            return Response({"status": "error", "message": str(exc)}, status=400)
        except LookupError as exc:
            return Response({"status": "error", "message": str(exc)}, status=404)
        except IntegrityError:
            return Response({
                "status": "error",
                "message": "Train is still linked to railway records and could not be deleted.",
            }, status=409)
        except mysql.connector.Error:
            return Response({"status": "error", "message": "Train management is temporarily unavailable."}, status=503)
        except Exception:
            return Response({"status": "error", "message": "Train could not be removed."}, status=500)
        return Response({"status": "ok", "message": result["message"], "train": result})

    payload = _payload(request)
    if payload is None or not any(key in payload for key in ("train_number", "train_name", "train_status")):
        return Response({"status": "error", "message": "Submit at least one valid train detail."}, status=400)
    from .train_management import (
        DuplicateTrainNumberError,
        TrainValidationError,
        update_train,
    )
    try:
        result = update_train(
            train_id,
            payload.get("train_number"),
            payload.get("train_name"),
            payload.get("train_status"),
        )
    except DuplicateTrainNumberError as exc:
        return Response({"status": "error", "message": str(exc)}, status=409)
    except (TrainValidationError, ValueError) as exc:
        return Response({"status": "error", "message": str(exc)}, status=400)
    except LookupError as exc:
        return Response({"status": "error", "message": str(exc)}, status=404)
    except IntegrityError as exc:
        if getattr(exc, "errno", None) == 1062:
            return Response({"status": "error", "message": "A train with this train number already exists."}, status=409)
        return Response({"status": "error", "message": "Train details could not be updated."}, status=500)
    except mysql.connector.Error:
        return Response({"status": "error", "message": "Train management is temporarily unavailable."}, status=503)
    except Exception:
        return Response({"status": "error", "message": "Train details could not be updated."}, status=500)
    return Response({"status": "ok", "message": "Train details updated successfully.", "train": result})


@endpoint(["POST"])
@_admin_required
def admin_train_create(request):
    """Create a train from validated details submitted by an administrator."""
    payload = _payload(request)
    if payload is None:
        return Response({"status": "error", "message": "Submit train details as JSON."}, status=400)
    from .train_management import (
        DuplicateTrainNumberError,
        TrainValidationError,
        create_train,
    )
    try:
        result = create_train(
            payload.get("train_number"),
            payload.get("train_name"),
            payload.get("train_status", "ACTIVE"),
        )
    except TrainValidationError as exc:
        return Response({"status": "error", "message": str(exc)}, status=400)
    except DuplicateTrainNumberError as exc:
        return Response({"status": "error", "message": str(exc)}, status=409)
    except IntegrityError as exc:
        if getattr(exc, "errno", None) == 1062:
            return Response({"status": "error", "message": "A train with this train number already exists."}, status=409)
        return Response({"status": "error", "message": "Train could not be added."}, status=500)
    except mysql.connector.Error:
        return Response({"status": "error", "message": "Train management is temporarily unavailable."}, status=503)
    except Exception:
        return Response({"status": "error", "message": "Train could not be added."}, status=500)
    return Response({"status": "ok", "message": "Train added successfully.", "train": result}, status=201)
