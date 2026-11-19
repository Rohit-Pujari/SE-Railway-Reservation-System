"""Manual payment approval for local demonstrations; no gateway is contacted."""

import uuid

import mysql.connector

from .db import get_db_connection


class PaymentApprovalError(ValueError):
    """A payment request cannot be created or reviewed in its current state."""


class PaymentApprovalConflict(PaymentApprovalError):
    """The booking or payment state changed before review completed."""


def request_payment_approval(booking_id, user_id, idempotency_key, connection_factory=None):
    try:
        booking_id, user_id = int(booking_id), int(user_id)
    except (TypeError, ValueError):
        raise PaymentApprovalError("Select a valid booking.") from None
    if booking_id <= 0 or user_id <= 0:
        raise PaymentApprovalError("Select a valid booking.")
    if not isinstance(idempotency_key, str) or not idempotency_key.strip() or len(idempotency_key) > 128:
        raise PaymentApprovalError("A valid payment request key is required.")

    connection = cursor = None
    try:
        connection = (connection_factory or get_db_connection)()
        connection.start_transaction(isolation_level="READ COMMITTED")
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT booking_id, pnr, booking_status, schedule_id, class_id, total_fare, currency_code "
            "FROM bookings WHERE booking_id = %s AND user_id = %s FOR UPDATE",
            (booking_id, user_id),
        )
        booking = cursor.fetchone()
        if not booking:
            raise PaymentApprovalError("Booking was not found in your account.")
        if booking["booking_status"] != "PENDING_PAYMENT":
            raise PaymentApprovalConflict("Only pending bookings can be submitted for approval.")

        cursor.execute(
            "SELECT payment_id, payment_status, amount, currency_code FROM payments "
            "WHERE booking_id = %s AND payment_provider = 'ADMIN_REVIEW' "
            "AND payment_status = 'INITIATED' ORDER BY payment_id DESC LIMIT 1 FOR UPDATE",
            (booking_id,),
        )
        pending = cursor.fetchone()
        if pending:
            connection.commit()
            return {"payment_id": int(pending["payment_id"]), "payment_status": "INITIATED",
                    "booking_status": booking["booking_status"], "pnr": booking["pnr"],
                    "amount": float(pending["amount"]), "currency_code": pending["currency_code"],
                    "awaiting_admin": True, "replayed": True}

        cursor.execute(
            "SELECT payment_id FROM payments WHERE booking_id = %s AND payment_status = 'SUCCEEDED' "
            "LIMIT 1 FOR UPDATE", (booking_id,),
        )
        if cursor.fetchone():
            raise PaymentApprovalConflict("This booking already has a successful payment.")
        cursor.execute(
            "SELECT schedule_seat_id FROM schedule_seats WHERE schedule_id = %s AND class_id = %s "
            "AND operational_status = 'IN_SERVICE' ORDER BY schedule_seat_id FOR UPDATE",
            (booking["schedule_id"], booking["class_id"]),
        )
        cursor.fetchall()
        cursor.execute("SELECT booking_passenger_id FROM booking_passengers WHERE booking_id = %s FOR UPDATE", (booking_id,))
        passengers = cursor.fetchall()
        cursor.execute(
            "SELECT allocation_id, allocation_status, hold_expires_at FROM seat_allocations "
            "WHERE booking_id = %s ORDER BY allocation_id FOR UPDATE", (booking_id,),
        )
        allocations = cursor.fetchall()
        cursor.execute("SELECT CURRENT_TIMESTAMP AS db_now")
        now = cursor.fetchone()["db_now"]
        if (not passengers or len(allocations) != len(passengers)
                or any(row["allocation_status"] != "HELD" or not row["hold_expires_at"]
                       or row["hold_expires_at"] <= now for row in allocations)):
            raise PaymentApprovalConflict("The seat hold expired or is incomplete. Start a new booking.")

        cursor.execute(
            "INSERT INTO payments (booking_id, payment_provider, payment_method, amount, currency_code, "
            "payment_status, idempotency_key) VALUES (%s, 'ADMIN_REVIEW', 'SIMULATED', %s, %s, 'INITIATED', %s)",
            (booking_id, booking["total_fare"], booking["currency_code"], idempotency_key.strip()),
        )
        payment_id = int(cursor.lastrowid)
        connection.commit()
        return {"payment_id": payment_id, "payment_status": "INITIATED",
                "booking_status": booking["booking_status"], "pnr": booking["pnr"],
                "amount": float(booking["total_fare"]), "currency_code": booking["currency_code"],
                "awaiting_admin": True, "replayed": False}
    except PaymentApprovalError:
        if connection is not None:
            connection.rollback()
        raise
    except mysql.connector.IntegrityError as exc:
        if connection is not None:
            connection.rollback()
        if getattr(exc, "errno", None) == 1062:
            raise PaymentApprovalConflict("This payment request was already submitted.") from None
        raise
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def list_pending_payment_approvals(connection_factory=None):
    connection = cursor = None
    try:
        connection = (connection_factory or get_db_connection)()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            "SELECT payment.payment_id, payment.booking_id, payment.amount, payment.currency_code, "
            "payment.created_at, booking.pnr, booking.booking_status, booking.train_number_snapshot, "
            "booking.train_name_snapshot, booking.boarding_station_name_snapshot, "
            "booking.alighting_station_name_snapshot, booking.departure_at_snapshot, "
            "booking.arrival_at_snapshot, booking.class_code_snapshot, booking.total_fare, "
            "booking.user_id, user.full_name, user.email, "
            "(SELECT COUNT(*) FROM booking_passengers passenger WHERE passenger.booking_id = booking.booking_id) AS passenger_count, "
            "(SELECT MIN(hold_expires_at) FROM seat_allocations allocation "
            " WHERE allocation.booking_id = booking.booking_id AND allocation.allocation_status = 'HELD') AS hold_expires_at "
            "FROM payments payment JOIN bookings booking ON booking.booking_id = payment.booking_id "
            "JOIN users user ON user.user_id = booking.user_id "
            "WHERE payment.payment_provider = 'ADMIN_REVIEW' AND payment.payment_status = 'INITIATED' "
            "ORDER BY payment.created_at ASC LIMIT 300"
        )
        return cursor.fetchall() or []
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


def review_payment_approval(payment_id, admin_user_id, decision, connection_factory=None):
    try:
        payment_id, admin_user_id = int(payment_id), int(admin_user_id)
    except (TypeError, ValueError):
        raise PaymentApprovalError("Select a valid payment request.") from None
    if (payment_id <= 0 or admin_user_id <= 0 or not isinstance(decision, str)
            or decision not in {"APPROVE", "REJECT"}):
        raise PaymentApprovalError("Choose approve or reject for a valid payment request.")

    connection = cursor = None
    try:
        connection = (connection_factory or get_db_connection)()
        connection.start_transaction(isolation_level="READ COMMITTED")
        cursor = connection.cursor(dictionary=True)
        # Lock in booking -> payment order, matching passenger submission and
        # avoiding the request/review lock inversion around the same booking.
        cursor.execute(
            "SELECT booking_id FROM payments WHERE payment_id = %s "
            "AND payment_provider = 'ADMIN_REVIEW'", (payment_id,),
        )
        payment_ref = cursor.fetchone()
        if not payment_ref:
            raise PaymentApprovalConflict("This request does not exist.")
        booking_id = int(payment_ref["booking_id"])
        cursor.execute(
            "SELECT booking_id, user_id, pnr, booking_status, schedule_id, class_id "
            "FROM bookings WHERE booking_id = %s FOR UPDATE", (booking_id,),
        )
        booking = cursor.fetchone()
        if not booking or booking["booking_status"] != "PENDING_PAYMENT":
            raise PaymentApprovalConflict("The booking is no longer awaiting payment.")
        cursor.execute(
            "SELECT payment_id, booking_id, amount, currency_code, payment_status FROM payments "
            "WHERE payment_id = %s AND payment_provider = 'ADMIN_REVIEW' FOR UPDATE",
            (payment_id,),
        )
        payment = cursor.fetchone()
        if (not payment or int(payment["booking_id"]) != booking_id
                or payment["payment_status"] != "INITIATED"):
            raise PaymentApprovalConflict("This request has already been reviewed or does not exist.")

        if decision == "REJECT":
            cursor.execute(
                "UPDATE payments SET payment_status = 'FAILED', failure_code = %s, completed_at = CURRENT_TIMESTAMP "
                "WHERE payment_id = %s AND payment_status = 'INITIATED'",
                (f"ADMIN_REJECTED_BY_{admin_user_id}", payment_id),
            )
            connection.commit()
            return {"payment_id": payment_id, "booking_id": booking_id, "pnr": booking["pnr"],
                    "payment_status": "FAILED", "booking_status": "PENDING_PAYMENT"}

        cursor.execute(
            "SELECT payment_id FROM payments WHERE booking_id = %s AND payment_status = 'SUCCEEDED' "
            "AND payment_id <> %s LIMIT 1 FOR UPDATE", (booking_id, payment_id),
        )
        if cursor.fetchone():
            raise PaymentApprovalConflict("This booking already has a successful payment.")

        cursor.execute(
            "SELECT schedule_seat_id FROM schedule_seats WHERE schedule_id = %s AND class_id = %s "
            "AND operational_status = 'IN_SERVICE' ORDER BY schedule_seat_id FOR UPDATE",
            (booking["schedule_id"], booking["class_id"]),
        )
        cursor.fetchall()
        cursor.execute("SELECT COUNT(*) AS passenger_count FROM booking_passengers WHERE booking_id = %s", (booking_id,))
        passenger_count = int(cursor.fetchone()["passenger_count"])
        cursor.execute("SELECT CURRENT_TIMESTAMP AS db_now")
        now = cursor.fetchone()["db_now"]
        cursor.execute(
            "SELECT allocation_id, allocation_status, hold_expires_at FROM seat_allocations "
            "WHERE booking_id = %s ORDER BY allocation_id FOR UPDATE", (booking_id,),
        )
        allocations = cursor.fetchall()
        if (passenger_count < 1 or len(allocations) != passenger_count
                or any(row["allocation_status"] != "HELD" or not row["hold_expires_at"]
                       or row["hold_expires_at"] <= now for row in allocations)):
            raise PaymentApprovalConflict("The seat hold expired or is incomplete; this payment cannot be approved.")

        cursor.execute(
            "UPDATE seat_allocations SET allocation_status = 'CONFIRMED', hold_expires_at = NULL "
            "WHERE booking_id = %s AND allocation_status = 'HELD' AND hold_expires_at > CURRENT_TIMESTAMP",
            (booking_id,),
        )
        if cursor.rowcount != passenger_count:
            raise PaymentApprovalConflict("Seat allocation changed during approval. Please retry.")
        cursor.execute(
            "UPDATE bookings SET booking_status = 'CONFIRMED', confirmed_at = CURRENT_TIMESTAMP "
            "WHERE booking_id = %s AND booking_status = 'PENDING_PAYMENT'", (booking_id,),
        )
        if cursor.rowcount != 1:
            raise PaymentApprovalConflict("Booking status changed during approval. Please retry.")
        cursor.execute(
            "UPDATE payments SET payment_status = 'SUCCEEDED', "
            "provider_transaction_id = %s, completed_at = CURRENT_TIMESTAMP, failure_code = NULL "
            "WHERE payment_id = %s AND payment_status = 'INITIATED'",
            (f"ADMIN-APPROVED-{admin_user_id}-{uuid.uuid4().hex}", payment_id),
        )
        if cursor.rowcount != 1:
            raise PaymentApprovalConflict("Payment status changed during approval. Please retry.")
        connection.commit()
        return {"payment_id": payment_id, "booking_id": booking_id, "pnr": booking["pnr"],
                "payment_status": "SUCCEEDED", "booking_status": "CONFIRMED"}
    except PaymentApprovalError:
        if connection is not None:
            connection.rollback()
        raise
    except Exception:
        if connection is not None:
            connection.rollback()
        raise
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()
