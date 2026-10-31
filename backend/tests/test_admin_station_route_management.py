"""Validation and authorization tests for station and route administration."""

import unittest
from unittest.mock import patch

from backend.app.station_route_management import StationRouteValidationError, validate_route, validate_station
from backend.tests.drf_client import RailwayAPIClient, set_session


class StationRouteValidationTests(unittest.TestCase):
    def test_station_fields_are_normalized(self):
        self.assertEqual(
            validate_station(" blr ", "  Bengaluru   City ", " Bengaluru ", " Karnataka "),
            ("BLR", "Bengaluru City", "Bengaluru", "Karnataka"),
        )

    def test_station_code_format_is_checked(self):
        with self.assertRaises(StationRouteValidationError):
            validate_station("BANGALORE-CENTRAL", "Bengaluru", "Bengaluru")

    def test_route_requires_two_stops(self):
        with self.assertRaises(StationRouteValidationError):
            validate_route("Bengaluru-Mysuru", [{"station_id": 1, "sequence": 1}])

    def test_route_requires_explicit_distance_for_every_stop(self):
        with self.assertRaises(StationRouteValidationError):
            validate_route("Route", [
                {"station_id": 1, "sequence": 1},
                {"station_id": 2, "sequence": 2, "distance_from_origin_km": 10},
            ])

    def test_route_rejects_duplicate_stations(self):
        with self.assertRaises(StationRouteValidationError):
            validate_route("Loop", [
                {"station_id": 1, "sequence": 1, "distance_from_origin_km": 0},
                {"station_id": 1, "sequence": 2, "distance_from_origin_km": 10},
            ])

    def test_route_rejects_decreasing_distance(self):
        with self.assertRaises(StationRouteValidationError):
            validate_route("Route", [
                {"station_id": 1, "sequence": 1, "distance_from_origin_km": 0},
                {"station_id": 2, "sequence": 2, "distance_from_origin_km": 20},
                {"station_id": 3, "sequence": 3, "distance_from_origin_km": 10},
            ])

    def test_route_requires_consecutive_stop_sequence(self):
        with self.assertRaises(StationRouteValidationError):
            validate_route("Route", [
                {"station_id": 1, "sequence": 1, "distance_from_origin_km": 0},
                {"station_id": 2, "sequence": 4, "distance_from_origin_km": 10},
            ])


class StationRouteEndpointAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.client = RailwayAPIClient()

    def test_anonymous_user_cannot_create_station(self):
        response = self.client.post("/api/admin/stations", {
            "station_code": "BLR", "station_name": "Bengaluru", "city": "Bengaluru",
        })
        self.assertEqual(response.status_code, 401)

    def test_passenger_cannot_create_route(self):
        set_session(self.client, user_id=12, role="PASSENGER")
        response = self.client.post("/api/admin/routes", {
            "route_name": "Bengaluru-Mysuru",
            "stops": [
                {"station_id": 1, "sequence": 1, "distance_from_origin_km": 0},
                {"station_id": 2, "sequence": 2, "distance_from_origin_km": 140},
            ],
        })
        self.assertEqual(response.status_code, 403)

    @patch("backend.app.station_route_management.create_station")
    def test_admin_can_create_station(self, create_station):
        set_session(self.client, user_id=7, role="ADMIN")
        create_station.return_value = {"station_id": 1, "station_code": "BLR"}
        response = self.client.post("/api/admin/stations", {
            "station_code": "BLR", "station_name": "Bengaluru City", "city": "Bengaluru",
        })
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["station"]["station_id"], 1)

    def test_invalid_station_payload_returns_bad_request(self):
        set_session(self.client, user_id=7, role="ADMIN")
        response = self.client.post("/api/admin/stations", {
            "station_code": "TOO-LONG-STATION", "station_name": "X", "city": "Y",
        })
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
