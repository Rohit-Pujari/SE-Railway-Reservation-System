"""Retrieve a passenger-owned booking and its payment/cancellation lifecycle."""
from .db import get_db_connection


def _valid_pnr(value):
    if not isinstance(value, str):
        raise ValueError("Enter a valid PNR.")
    pnr = value.strip().upper()
    if not pnr or len(pnr) > 20 or not pnr.isalnum():
        raise ValueError("Enter a valid PNR.")
    return pnr


def get_booking_status(user_id, pnr, connection_factory=None):
    """Return booking, payment, cancellation and refund status for its owner."""
    if isinstance(user_id, bool):
        raise ValueError("A valid passenger account is required.")
    try:
        owner_id = int(user_id)
    except (TypeError, ValueError):
        raise ValueError("A valid passenger account is required.") from None
    if owner_id <= 0 or str(user_id).strip() != str(owner_id):
        raise ValueError("A valid passenger account is required.")
    lookup_pnr = _valid_pnr(pnr)
    connection = cursor = None
    try:
        connection = (connection_factory or get_db_connection)()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """SELECT booking_id, pnr, booking_status, train_number_snapshot,
                      train_name_snapshot, boarding_station_code_snapshot,
                      boarding_station_name_snapshot, alighting_station_code_snapshot,
                      alighting_station_name_snapshot, departure_at_snapshot,
                      arrival_at_snapshot, class_code_snapshot, total_fare,
                      currency_code, created_at, confirmed_at
               FROM bookings WHERE user_id = %s AND pnr = %s LIMIT 1""",
            (owner_id, lookup_pnr),
        )
        booking = cursor.fetchone()
        if not booking:
            return None
        booking["departure_at"] = booking.pop("departure_at_snapshot").isoformat()
        booking["arrival_at"] = booking.pop("arrival_at_snapshot").isoformat()
        for field in ("created_at", "confirmed_at"):
            if booking[field] is not None:
                booking[field] = booking[field].isoformat()
        booking["total_fare"] = float(booking["total_fare"])
        booking_id = booking["booking_id"]

        cursor.execute(
            """SELECT payment_status, payment_method, amount, currency_code,
                      provider_transaction_id, failure_code, created_at, completed_at
               FROM payments WHERE booking_id = %s
               ORDER BY created_at DESC, payment_id DESC""",
            (booking_id,),
        )
        payments = cursor.fetchall() or []
        for payment in payments:
            payment["amount"] = float(payment["amount"])
            payment["created_at"] = payment["created_at"].isoformat()
            if payment["completed_at"] is not None:
                payment["completed_at"] = payment["completed_at"].isoformat()

        cursor.execute(
            """SELECT cancellation.cancellation_status, cancellation.reason,
                      cancellation.requested_at, cancellation.completed_at,
                      item.item_status, item.cancellation_charge, item.refund_amount,
                      refund.refund_status, refund.amount AS refunded_amount,
                      refund.currency_code AS refund_currency, refund.created_at AS refund_created_at
               FROM cancellations AS cancellation
               LEFT JOIN cancellation_items AS item
                 ON item.cancellation_id = cancellation.cancellation_id
               LEFT JOIN refunds AS refund
                 ON refund.cancellation_item_id = item.cancellation_item_id
               WHERE cancellation.booking_id = %s
               ORDER BY cancellation.requested_at DESC, refund.created_at DESC""",
            (booking_id,),
        )
        cancellations = cursor.fetchall() or []
        for item in cancellations:
            for field in ("requested_at", "completed_at", "refund_created_at"):
                if item[field] is not None:
                    item[field] = item[field].isoformat()
            for field in ("cancellation_charge", "refund_amount", "refunded_amount"):
                if item[field] is not None:
                    item[field] = float(item[field])
        return {
            "booking": booking,
            "payment_status": payments[0]["payment_status"] if payments else "NOT_STARTED",
            "payments": payments,
            "cancellations": cancellations,
        }
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
