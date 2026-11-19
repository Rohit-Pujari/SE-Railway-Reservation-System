"""End-to-end API regression tests for the passenger ticket cancellation journey."""

import unittest
from unittest.mock import MagicMock, patch

from backend.tests.drf_client import RailwayAPIClient


class PassengerCancellationFlowTests(unittest.TestCase):
    """Exercise login, booking history, cancellation, refund, and refreshed status."""

    def setUp(self):
        self.client = RailwayAPIClient()
        self.user = {
            "user_id": 7,
            "full_name": "Test Passenger",
            "email": "passenger@example.com",
            "password_hash": "stored-password-hash",
        }
        self.booking = {
            "booking_id": 501,
            "pnr": "AB23456789CD",
            "booking_status": "CONFIRMED",
            "trip_type": "UPCOMING",
            "train_number": "12028",
            "train_name": "Sample Express",
            "source_station_code": "SBC",
            "source_station_name": "Bengaluru",
            "destination_station_code": "MAS",
            "destination_station_name": "Chennai",
            "departure_at": "2026-12-15T09:30:00",
            "arrival_at": "2026-12-15T15:30:00",
            "class_code": "SL",
            "total_fare": 1000.0,
            "currency_code": "INR",
            "passengers": [{
                "passenger_id": 801,
                "passenger_name": "Ananya Rao",
                "passenger_fare": 1000.0,
                "allocation_status": "CONFIRMED",
                "coach_number": "S1",
                "seat_number": "24",
            }],
        }

    def login(self):
        connection = MagicMock()
        connection.cursor.return_value.fetchone.return_value = self.user
        with (
            patch("backend.app.django_views.get_db_connection", return_value=connection),
            patch("backend.app.django_views.check_password_hash", return_value=True),
        ):
            response = self.client.post("/api/login", json={
                "email": "PASSENGER@example.com",
                "password": "correct-password",
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["user_id"], 7)
        connection.close.assert_called_once()
        return response

    def test_passenger_views_booking_cancels_receives_refund_and_sees_updated_status(self):
        self.login()

        before_cancellation = {
            "upcoming": [self.booking],
            "previous": [],
            "count": 1,
        }
        after_cancellation = {
            "upcoming": [],
            "previous": [{**self.booking, "booking_status": "CANCELLED",
                          "trip_type": "PREVIOUS"}],
            "count": 1,
        }
        cancellation_result = {
            "booking_id": 501,
            "pnr": "AB23456789CD",
            "booking_status": "CANCELLED",
            "cancelled_passengers": 1,
            "released_seats": 1,
            "cancellation_charge": 100.0,
            "refund_amount": 900.0,
            "refund_status": "PENDING",
            "passenger_refunds": [{
                "booking_passenger_id": 801,
                "cancellation_charge": 100.0,
                "refund_amount": 900.0,
                "refund_status": "PENDING",
            }],
            "message": "Booking cancelled. Refund due: INR 900.00.",
        }

        with patch(
            "backend.app.django_views.get_booking_history",
            side_effect=[before_cancellation, after_cancellation],
        ) as get_history, patch(
            "backend.app.django_views.cancel_booking",
            return_value=cancellation_result,
        ) as cancel_booking:

            # 1. View the passenger's booking list and select the confirmed ticket.
            history_response = self.client.get("/api/bookings/history")
            self.assertEqual(history_response.status_code, 200)
            selected = history_response.json()["upcoming"][0]
            self.assertEqual(selected["booking_id"], 501)
            self.assertEqual(selected["booking_status"], "CONFIRMED")
            self.assertEqual(selected["passengers"][0]["seat_number"], "24")
            get_history.assert_called_once_with(7)

            # 2. Cancel the selected booking using the authenticated session identity.
            cancellation_response = self.client.post(
                "/api/bookings/501/cancel",
                json={"reason": "Change of plans"},
            )
            self.assertEqual(cancellation_response.status_code, 200)
            cancelled = cancellation_response.json()
            self.assertEqual(cancelled["booking_status"], "CANCELLED")
            self.assertEqual(cancelled["cancelled_passengers"], 1)
            self.assertEqual(cancelled["released_seats"], 1)
            self.assertEqual(cancelled["cancellation_charge"], 100.0)
            self.assertEqual(cancelled["refund_amount"], 900.0)
            self.assertEqual(cancelled["refund_status"], "PENDING")
            self.assertEqual(cancelled["passenger_refunds"][0]["booking_passenger_id"], 801)
            cancel_booking.assert_called_once_with(7, 501, "Change of plans")

            # 3. Refresh booking history and verify the cancelled status is visible.
            refreshed_response = self.client.get("/api/bookings/history")
            self.assertEqual(refreshed_response.status_code, 200)
            refreshed = refreshed_response.json()
            self.assertEqual(refreshed["upcoming"], [])
            self.assertEqual(refreshed["previous"][0]["booking_status"], "CANCELLED")
            self.assertEqual(refreshed["previous"][0]["pnr"], "AB23456789CD")
            self.assertEqual(get_history.call_count, 2)

    def test_anonymous_passenger_cannot_start_cancellation_flow(self):
        response = self.client.get("/api/bookings/history")
        self.assertEqual(response.status_code, 401)

        cancellation_response = self.client.post(
            "/api/bookings/501/cancel",
            json={"reason": "Change of plans"},
        )
        self.assertEqual(cancellation_response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
