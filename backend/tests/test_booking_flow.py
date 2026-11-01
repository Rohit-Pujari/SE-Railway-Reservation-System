"""End-to-end API regression tests for the passenger booking journey."""

import unittest
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

from backend.tests.drf_client import RailwayAPIClient


class PassengerBookingFlowTests(unittest.TestCase):
    """Exercise the public API in the same order used by the passenger UI."""

    def setUp(self):
        self.client = RailwayAPIClient()
        self.user = {
            "user_id": 7,
            "full_name": "Test Passenger",
            "email": "passenger@example.com",
            "password_hash": "stored-password-hash",
        }
        self.passengers = [{
            "passenger_name": "Ananya Rao",
            "age": 22,
            "gender": "Female",
            "berth_preference": "LOWER",
        }]

    def login(self):
        connection = MagicMock()
        connection.cursor.return_value.fetchone.return_value = self.user
        with patch("backend.app.django_views.get_db_connection", return_value=connection), \
             patch("backend.app.django_views.check_password_hash", return_value=True):
            response = self.client.post("/api/login", json={
                "email": "PASSENGER@example.com",
                "password": "correct-password",
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["user_id"], 7)
        connection.close.assert_called_once()
        return response

    def test_passenger_completes_search_seat_payment_and_pnr_confirmation_flow(self):
        self.login()

        with patch("backend.app.django_views.get_active_stations", return_value=[
            {"station_id": 1, "station_code": "SBC", "station_name": "Bengaluru"},
            {"station_id": 2, "station_code": "MAS", "station_name": "Chennai"},
        ]) as stations, \
             patch("backend.app.django_views.get_active_travel_classes", return_value=[
                 {"class_id": 3, "class_code": "SL", "class_name": "Sleeper"},
             ]) as classes, \
             patch("backend.app.django_views.search_trains", return_value=[{
                 "schedule_id": 9,
                 "train_number": "12028",
                 "train_name": "Sample Express",
                 "source_station_id": 1,
                 "destination_station_id": 2,
                 "departure_at": "2026-11-15T09:30:00",
                 "arrival_at": "2026-11-15T15:30:00",
                 "starting_fare": 850.0,
                 "currency_code": "INR",
                 "available_seats": 18,
             }]) as search, \
             patch("backend.app.django_views.get_seat_availability", return_value={
                 "schedule_id": 9,
                 "class_id": 3,
                 "class_code": "SL",
                 "available_seats": 18,
             }) as availability, \
             patch("backend.app.django_views.create_booking", return_value={
                 "booking_id": 501,
                 "pnr": "AB23456789CD",
                 "status": "PENDING_PAYMENT",
                 "currency_code": "INR",
                 "fare_per_passenger": 850.0,
                 "total_fare": 850.0,
                 "assigned_seats": [{"coach_number": "S1", "seat_number": "24"}],
                 "hold_expires_at": "2026-11-15T09:15:00",
                 "replayed": False,
             }) as create_booking, \
             patch("backend.app.django_views.calculate_booking_fare", return_value={
                 "booking_id": 501,
                 "pnr": "AB23456789CD",
                 "passenger_count": 1,
                 "total_fare": 850.0,
                 "currency_code": "INR",
             }) as calculate_fare, \
             patch("backend.app.django_views.confirm_booking_payment", return_value={
                 "booking_id": 501,
                 "pnr": "AB23456789CD",
                 "booking_status": "CONFIRMED",
                 "payment_status": "SUCCEEDED",
                 "payment_method": "SIMULATED",
                 "amount": 850.0,
                 "currency_code": "INR",
                 "notifications": [{"channel": "EMAIL", "delivery_status": "QUEUED"}],
                 "replayed": False,
             }) as pay_booking, \
             patch("backend.app.django_views.get_booking_status", return_value={
                 "booking_id": 501,
                 "pnr": "AB23456789CD",
                 "booking_status": "CONFIRMED",
                 "payment_status": "SUCCEEDED",
                 "train_number": "12028",
                 "train_name": "Sample Express",
                 "passengers": self.passengers,
             }) as booking_status:

            # 1. Load stations and travel classes before searching.
            station_response = self.client.get("/api/stations")
            self.assertEqual(station_response.status_code, 200)
            self.assertEqual(
                [item["station_id"] for item in station_response.json()["stations"]],
                [1, 2],
            )
            class_response = self.client.get("/api/travel-classes")
            self.assertEqual(class_response.status_code, 200)
            self.assertEqual(class_response.json()["travel_classes"][0]["class_id"], 3)

            # 2. Search trains for the selected route/date/class.
            search_response = self.client.get(
                "/api/trains/search?source_station_id=1&destination_station_id=2"
                "&journey_date=2026-11-15&class_id=3"
            )
            self.assertEqual(search_response.status_code, 200)
            self.assertEqual(search_response.json()["count"], 1)
            train = search_response.json()["trains"][0]
            self.assertEqual(train["schedule_id"], 9)
            self.assertEqual(train["train_number"], "12028")
            search.assert_called_once_with("1", "2", "2026-11-15", "3")

            # 3. Check inventory for the chosen schedule and class.
            seat_response = self.client.get(
                "/api/seats/availability?schedule_id=9&source_station_id=1"
                "&destination_station_id=2&journey_date=2026-11-15&class_id=3"
            )
            self.assertEqual(seat_response.status_code, 200)
            self.assertEqual(seat_response.json()["available_seats"], 18)
            availability.assert_called_once_with("9", "1", "2", "2026-11-15", "3")

            # 4. Submit passenger details with the selected train/class.
            booking_response = self.client.post("/api/bookings", json={
                "schedule_id": 9,
                "source_station_id": 1,
                "destination_station_id": 2,
                "journey_date": "2026-11-15",
                "class_id": 3,
                "passengers": self.passengers,
                "idempotency_key": "flow-test-request-001",
            })
            self.assertEqual(booking_response.status_code, 201)
            booking = booking_response.json()
            self.assertEqual(booking["booking_id"], 501)
            self.assertEqual(booking["status"], "PENDING_PAYMENT")
            self.assertEqual(booking["pnr"], "AB23456789CD")
            self.assertEqual(len(booking["pnr"]), 12)
            create_booking.assert_called_once_with(
                7, 9, 1, 2, "2026-11-15", 3,
                self.passengers, "flow-test-request-001",
            )

            # 5. Verify fare calculation uses the newly created booking.
            fare_response = self.client.post("/api/bookings/501/fare", json={})
            self.assertEqual(fare_response.status_code, 200)
            self.assertEqual(fare_response.json()["total_fare"], 850.0)
            calculate_fare.assert_called_once_with(501, 7)

            # 6. Pay and confirm the booking.
            payment_response = self.client.post("/api/bookings/501/pay", json={})
            self.assertEqual(payment_response.status_code, 201)
            self.assertEqual(payment_response.json()["booking_status"], "CONFIRMED")
            self.assertEqual(payment_response.json()["payment_status"], "SUCCEEDED")
            self.assertEqual(payment_response.json()["payment_method"], "SIMULATED")
            self.assertEqual(payment_response.json()["pnr"], booking["pnr"])
            pay_booking.assert_called_once_with(7, 501)

            # 7. Retrieve the final confirmation by the generated PNR.
            status_response = self.client.get(
                "/api/bookings/status?pnr=AB23456789CD"
            )
            self.assertEqual(status_response.status_code, 200)
            confirmed = status_response.json()
            self.assertEqual(confirmed["pnr"], booking["pnr"])
            self.assertEqual(confirmed["booking_status"], "CONFIRMED")
            self.assertEqual(confirmed["payment_status"], "SUCCEEDED")
            booking_status.assert_called_once_with(7, "AB23456789CD")
            stations.assert_called_once_with()
            classes.assert_called_once_with()

    def test_booking_is_blocked_when_selected_class_has_no_available_seats(self):
        self.login()
        with patch("backend.app.django_views.get_seat_availability", return_value={
            "schedule_id": 9, "class_id": 3, "class_code": "SL",
            "available_seats": 0,
        }), patch("backend.app.django_views.create_booking") as create_booking:
            response = self.client.get(
                "/api/seats/availability?schedule_id=9&source_station_id=1"
                "&destination_station_id=2&journey_date=2026-11-15&class_id=3"
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["available_seats"], 0)
            create_booking.assert_not_called()

    def test_anonymous_passenger_cannot_pay_for_a_booking(self):
        response = self.client.post("/api/bookings/501/pay", json={})
        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
