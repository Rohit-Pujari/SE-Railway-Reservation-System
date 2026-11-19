"""Administrator read-only cancellation and refund history."""
from .db import get_db_connection

def _iso(value):
    return value.isoformat() if value is not None and hasattr(value, "isoformat") else value

def _amount(value):
    return float(value) if value is not None else 0.0

def get_admin_cancellation_records(connection_factory=None):
    """Return one row per cancelled passenger and refund attempt."""
    connection = cursor = None
    try:
        connection = (connection_factory or get_db_connection)()
        cursor = connection.cursor(dictionary=True)
        cursor.execute(
            """SELECT cancellation.cancellation_id, cancellation.booking_id,
                      cancellation.cancellation_status, cancellation.reason,
                      cancellation.requested_at, cancellation.completed_at,
                      requester.full_name AS requested_by_name,
                      requester.email AS requested_by_email,
                      booking.pnr, booking.booking_status,
                      booking.train_number_snapshot, booking.train_name_snapshot,
                      booking.departure_at_snapshot, booking.boarding_station_name_snapshot,
                      booking.alighting_station_name_snapshot, booking.currency_code,
                      item.cancellation_item_id, item.item_status,
                      item.created_at AS item_created_at,
                      item.completed_at AS item_completed_at,
                      item.cancellation_charge, item.refund_amount AS expected_refund_amount,
                      passenger.passenger_name,
                      refund.refund_id, refund.refund_provider, refund.amount AS refund_amount,
                      refund.currency_code AS refund_currency,
                      refund.refund_status, refund.provider_refund_id,
                      refund.failure_code, refund.created_at AS refund_created_at,
                      refund.updated_at AS refund_updated_at,
                      refund.completed_at AS refund_completed_at
               FROM cancellations AS cancellation
               JOIN bookings AS booking ON booking.booking_id = cancellation.booking_id
               JOIN users AS requester ON requester.user_id = cancellation.requested_by_user_id
               LEFT JOIN cancellation_items AS item ON item.cancellation_id = cancellation.cancellation_id
               LEFT JOIN booking_passengers AS passenger
                 ON passenger.booking_passenger_id = item.booking_passenger_id
                AND passenger.booking_id = item.booking_id
               LEFT JOIN refunds AS refund ON refund.cancellation_item_id = item.cancellation_item_id
               ORDER BY cancellation.requested_at DESC, cancellation.cancellation_id DESC,
                        item.cancellation_item_id, refund.created_at DESC, refund.refund_id DESC"""
        )
        records = cursor.fetchall() or []
        for record in records:
            for field in ("requested_at", "completed_at", "departure_at_snapshot", "item_created_at",
                          "item_completed_at", "refund_created_at", "refund_updated_at", "refund_completed_at"):
                record[field] = _iso(record.get(field))
            for field in ("cancellation_charge", "expected_refund_amount", "refund_amount"):
                record[field] = _amount(record.get(field))
        return records
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()
