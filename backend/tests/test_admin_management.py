"""Tests for administrator dashboard, booking details, station/route, and schedule management."""

import unittest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import mysql.connector

from backend.app.admin_booking_details import get_admin_booking_details
from backend.app.admin_dashboard import get_admin_dashboard, update_train_status
from backend.app.schedule_management import (
    ScheduleConflictError,
    ScheduleValidationError,
    create_schedule,
    update_schedule,
    validate_schedule,
)
from backend.app.station_route_management import (
    DuplicateStationCodeError,
    DuplicateTrainRouteError,
    StationRouteValidationError,
    assign_route_to_train,
    create_route,
    create_station,
    remove_train_route,
    update_route,
    update_station,
    validate_route,
    validate_station,
)


class AdminDashboardTests(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value

    def _mock_cursor_rows(self, rows_list):
        """Set fetchall to return successive lists."""
        self.cursor.fetchall.side_effect = rows_list
        self.cursor.fetchone.side_effect = [None] * len(rows_list) + [{}]

    def test_get_admin_dashboard_returns_all_sections(self):
        self.cursor.fetchall.side_effect = [
            [{"train_id": 1, "train_number": "12001", "train_name": "Express", "train_status": "ACTIVE"}],
            [
                {"route_id": 1, "route_name": "North Route", "route_status": "ACTIVE",
                 "stop_sequence": 1, "station_id": 1, "station_code": "NDL",
                 "station_name": "New Delhi", "city": "Delhi", "distance_from_origin_km": Decimal("0")},
                {"route_id": 1, "route_name": "North Route", "route_status": "ACTIVE",
                 "stop_sequence": 2, "station_id": 2, "station_code": "KOTA",
                 "station_name": "Kota", "city": "Rajasthan", "distance_from_origin_km": Decimal("500")},
            ],
            [],
            [],
            [],
        ]
        self.cursor.fetchone.return_value = {
            "total_bookings": 5, "active_bookings": 3, "cancelled_bookings": 2,
        }
        result = get_admin_dashboard(connection_factory=lambda: self.connection)
        self.assertEqual(len(result["trains"]), 1)
        self.assertEqual(len(result["routes"]), 1)
        self.assertEqual(len(result["routes"][0]["stops"]), 2)
        self.assertEqual(result["summary"]["total_trains"], 1)
        self.assertEqual(result["summary"]["total_routes"], 1)
        self.assertEqual(result["summary"]["total_bookings"], 5)
        self.connection.commit.assert_not_called()  # read-only
        self.connection.close.assert_called_once()

    def test_update_train_status_activates_and_deactivates(self):
        self.cursor.rowcount = 1
        result = update_train_status(1, "INACTIVE", connection_factory=lambda: self.connection)
        self.assertEqual(result, {"train_id": 1, "train_status": "INACTIVE"})
        self.connection.commit.assert_called_once()

    def test_update_train_status_rejects_invalid_id(self):
        for bad_id in (True, False, 0, -1, "abc", 1.5):
            with self.subTest(bad_id=bad_id):
                with self.assertRaises(ValueError):
                    update_train_status(bad_id, "ACTIVE", connection_factory=lambda: self.connection)

    def test_update_train_status_rejects_invalid_status(self):
        with self.assertRaises(ValueError):
            update_train_status(1, "UNKNOWN", connection_factory=lambda: self.connection)

    def test_update_train_status_raises_when_not_found(self):
        self.cursor.rowcount = 0
        with self.assertRaises(LookupError):
            update_train_status(999, "ACTIVE", connection_factory=lambda: self.connection)
        self.connection.rollback.assert_called_once()

    def test_update_train_status_rolls_back_on_db_error(self):
        self.cursor.execute.side_effect = mysql.connector.Error("db down")
        with self.assertRaises(mysql.connector.Error):
            update_train_status(1, "ACTIVE", connection_factory=lambda: self.connection)
        self.connection.rollback.assert_called_once()


class AdminBookingDetailsTests(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value

    def test_get_admin_booking_details_returns_full_record(self):
        self.cursor.fetchone.side_effect = [
            {
                "booking_id": 501, "pnr": "AB23456789CD", "booking_status": "CONFIRMED",
                "train_number_snapshot": "12001", "train_name_snapshot": "Express",
                "boarding_station_code_snapshot": "NDL", "boarding_station_name_snapshot": "New Delhi",
                "alighting_station_code_snapshot": "KOTA", "alighting_station_name_snapshot": "Kota",
                "departure_at_snapshot": datetime(2026, 11, 20, 9, 0),
                "arrival_at_snapshot": datetime(2026, 11, 20, 15, 0),
                "class_code_snapshot": "SL", "base_fare_total": Decimal("800.00"),
                "other_charges": Decimal("0.00"), "total_fare": Decimal("800.00"),
                "currency_code": "INR", "created_at": datetime(2026, 11, 18, 10, 0),
                "confirmed_at": datetime(2026, 11, 18, 10, 30),
                "user_id": 7, "account_name": "Test User", "email": "user@example.com",
                "phone_number": "9876543210",
            },
            None,  # payments
            None,  # cancellations
        ]
        self.cursor.fetchall.side_effect = [
            [
                {
                    "booking_passenger_id": 801, "passenger_name": "Ananya Rao",
                    "age": 22, "gender": "Female", "berth_preference": "LOWER",
                    "passenger_fare": Decimal("800.00"), "allocation_status": "CONFIRMED",
                    "hold_expires_at": None, "allocated_at": datetime(2026, 11, 18, 10, 0),
                    "released_at": None, "coach_number": "S1", "seat_number": "24",
                }
            ],
            [],
            [],
        ]
        result = get_admin_booking_details(501, connection_factory=lambda: self.connection)
        self.assertEqual(result["booking"]["pnr"], "AB23456789CD")
        self.assertEqual(result["booking"]["total_fare"], 800.0)
        self.assertEqual(result["passengers"][0]["passenger_name"], "Ananya Rao")
        self.assertEqual(result["passengers"][0]["seat_number"], "24")
        self.assertEqual(result["payments"], [])
        self.assertEqual(result["cancellations"], [])

    def test_get_admin_booking_details_returns_none_when_missing(self):
        self.cursor.fetchone.return_value = None
        result = get_admin_booking_details(999, connection_factory=lambda: self.connection)
        self.assertIsNone(result)

    def test_get_admin_booking_details_rejects_invalid_id(self):
        for bad_id in (True, False, 0, -1, "abc", "01", 1.5):
            with self.subTest(bad_id=bad_id):
                with self.assertRaises(ValueError):
                    get_admin_booking_details(bad_id, connection_factory=lambda: self.connection)

    def test_get_admin_booking_details_propagates_db_error(self):
        self.cursor.execute.side_effect = mysql.connector.Error("db down")
        with self.assertRaises(mysql.connector.Error):
            get_admin_booking_details(501, connection_factory=lambda: self.connection)
        self.connection.close.assert_called_once()


class StationValidationTests(unittest.TestCase):
    def test_validate_station_accepts_valid_input(self):
        code, name, city, state = validate_station("ndl", "New Delhi", "Delhi", "Delhi")
        self.assertEqual((code, name, city, state), ("NDL", "New Delhi", "Delhi", "Delhi"))

    def test_validate_station_accepts_optional_state_none(self):
        code, name, city, state = validate_station("MUM", "Mumbai", "Mumbai", None)
        self.assertEqual((code, name, city, state), ("MUM", "Mumbai", "Mumbai", None))

    def test_validate_station_rejects_invalid_code(self):
        for code in ("", "AB!", "toolongstationcode", True, 123):
            with self.subTest(code=code):
                with self.assertRaises(StationRouteValidationError):
                    validate_station(code, "Name", "City")

    def test_validate_station_rejects_empty_name(self):
        with self.assertRaises(StationRouteValidationError):
            validate_station("NDL", "", "City")

    def test_validate_route_accepts_valid_stops(self):
        stops = [
            {"station_id": 1, "sequence": 1, "distance_from_origin_km": 0},
            {"station_id": 2, "sequence": 2, "distance_from_origin_km": 500},
        ]
        name, normalized = validate_route("North Route", stops)
        self.assertEqual(name, "North Route")
        self.assertEqual(len(normalized), 2)

    def test_validate_route_rejects_invalid(self):
        with self.assertRaises(StationRouteValidationError):
            validate_route("", [{"station_id": 1, "sequence": 1, "distance_from_origin_km": 0}])
        with self.assertRaises(StationRouteValidationError):
            validate_route("Route", [{"station_id": 1, "sequence": 1, "distance_from_origin_km": 0}])  # only 1 stop
        with self.assertRaises(StationRouteValidationError):
            validate_route("Route", [
                {"station_id": 1, "sequence": 1, "distance_from_origin_km": 100},  # first stop not 0
                {"station_id": 2, "sequence": 2, "distance_from_origin_km": 200},
            ])


class StationManagementTests(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value

    def test_create_station_success(self):
        self.cursor.fetchone.return_value = None
        self.cursor.lastrowid = 42
        result = create_station({
            "station_code": "ndl", "station_name": "New Delhi",
            "city": "Delhi", "state": "Delhi",
        }, connection_factory=lambda: self.connection)
        self.assertEqual(result["station_code"], "NDL")
        self.assertEqual(result["station_id"], 42)
        self.connection.commit.assert_called_once()

    def test_create_station_duplicate_code(self):
        self.cursor.fetchone.return_value = {"station_id": 1}
        with self.assertRaises(DuplicateStationCodeError):
            create_station({
                "station_code": "NDL", "station_name": "New Delhi",
                "city": "Delhi", "state": "Delhi",
            }, connection_factory=lambda: self.connection)

    def test_update_station_success(self):
        self.cursor.fetchone.side_effect = [
            {"station_id": 1, "station_code": "NDL", "station_name": "Old Delhi",
             "city": "Delhi", "state": "Delhi"},
            None,  # no duplicate code
        ]
        result = update_station(1, {"station_name": "New Delhi"}, connection_factory=lambda: self.connection)
        self.assertEqual(result["station_name"], "New Delhi")

    def test_update_station_not_found(self):
        self.cursor.fetchone.return_value = None
        with self.assertRaises(LookupError):
            update_station(999, {"station_name": "X"}, connection_factory=lambda: self.connection)

    def test_update_station_rejects_invalid_id(self):
        for bad_id in (True, False, 0, -1, "abc"):
            with self.subTest(bad_id=bad_id):
                with self.assertRaises(StationRouteValidationError):
                    update_station(bad_id, {"station_name": "X"}, connection_factory=lambda: self.connection)


class RouteManagementTests(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value

    def _mock_active_stations(self, ids):
        self.cursor.fetchall.return_value = [(sid,) for sid in ids]

    def test_create_route_success(self):
        self._mock_active_stations([1, 2])
        self.cursor.lastrowid = 10
        result = create_route({
            "route_name": "North Route",
            "stops": [
                {"station_id": 1, "sequence": 1, "distance_from_origin_km": 0},
                {"station_id": 2, "sequence": 2, "distance_from_origin_km": 500},
            ],
        }, connection_factory=lambda: self.connection)
        self.assertEqual(result["route_id"], 10)
        self.connection.commit.assert_called_once()

    def test_update_route_success(self):
        self.cursor.fetchone.side_effect = [
            {"route_id": 1, "route_name": "Old Route", "route_status": "ACTIVE"},
        ]
        self._mock_active_stations([1, 2])
        result = update_route(1, {"route_name": "New Route"}, connection_factory=lambda: self.connection)
        self.assertEqual(result["route_name"], "New Route")

    def test_update_route_not_found(self):
        self.cursor.fetchone.return_value = None
        with self.assertRaises(LookupError):
            update_route(999, {"route_name": "X"}, connection_factory=lambda: self.connection)


class TrainRouteAssignmentTests(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value

    def test_assign_route_to_train_success(self):
        self.cursor.fetchone.side_effect = [
            {"train_id": 1},  # active train
            {"route_id": 2},  # active route
            {"stop_count": 3},  # route has stops
        ]
        result = assign_route_to_train(1, 2, connection_factory=lambda: self.connection)
        self.assertEqual(result, {"train_id": 1, "route_id": 2})

    def test_assign_route_to_train_rejects_inactive_train(self):
        self.cursor.fetchone.return_value = None
        with self.assertRaises(LookupError):
            assign_route_to_train(999, 2, connection_factory=lambda: self.connection)

    def test_remove_train_route_success(self):
        self.cursor.fetchone.return_value = None  # no schedules using this pair
        self.cursor.rowcount = 1
        result = remove_train_route(1, 2, connection_factory=lambda: self.connection)
        self.assertEqual(result, {"train_id": 1, "route_id": 2})

    def test_remove_train_route_used_by_schedule(self):
        self.cursor.fetchone.return_value = {"schedule_id": 5}
        with self.assertRaises(StationRouteValidationError):
            remove_train_route(1, 2, connection_factory=lambda: self.connection)


class ScheduleValidationTests(unittest.TestCase):
    def test_validate_schedule_accepts_valid(self):
        dep = datetime(2026, 11, 20, 9, 0)
        arr = datetime(2026, 11, 20, 15, 0)
        result = validate_schedule(1, 2, dep, arr, "SCHEDULED")
        self.assertEqual(result, (1, 2, dep, arr, "SCHEDULED"))

    def test_validate_schedule_rejects_arrival_before_departure(self):
        dep = datetime(2026, 11, 20, 15, 0)
        arr = datetime(2026, 11, 20, 9, 0)
        with self.assertRaises(ScheduleValidationError):
            validate_schedule(1, 2, dep, arr)

    def test_validate_schedule_rejects_invalid_status(self):
        dep = datetime(2026, 11, 20, 9, 0)
        arr = datetime(2026, 11, 20, 15, 0)
        with self.assertRaises(ScheduleValidationError):
            validate_schedule(1, 2, dep, arr, "INVALID")

    def test_validate_schedule_rejects_boolean_id(self):
        dep = datetime(2026, 11, 20, 9, 0)
        arr = datetime(2026, 11, 20, 15, 0)
        with self.assertRaises(ScheduleValidationError):
            validate_schedule(True, 2, dep, arr)


class ScheduleManagementTests(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value

    def _mock_schedule_creation(self):
        self.cursor.fetchone.side_effect = [
            {"train_id": 1},  # active train
            {"route_id": 2},  # active route
            {"train_id": 1},  # train-route assignment exists
        ]
        self.cursor.fetchall.return_value = [
            {"route_stop_id": 101, "station_id": 1, "stop_sequence": 1, "distance_from_origin_km": Decimal("0")},
            {"route_stop_id": 102, "station_id": 2, "stop_sequence": 2, "distance_from_origin_km": Decimal("500")},
        ]
        self.cursor.lastrowid = 100

    def test_create_schedule_success(self):
        self._mock_schedule_creation()
        result = create_schedule({
            "train_id": 1, "route_id": 2,
            "departure_at": datetime(2026, 11, 20, 9, 0),
            "arrival_at": datetime(2026, 11, 20, 15, 0),
        }, connection_factory=lambda: self.connection)
        self.assertEqual(result["schedule_id"], 100)
        self.assertEqual(result["schedule_status"], "SCHEDULED")
        self.connection.commit.assert_called_once()

    def test_update_schedule_status_only(self):
        self.cursor.fetchone.side_effect = [
            {
                "schedule_id": 1, "train_id": 1, "route_id": 2,
                "departure_at": datetime(2026, 11, 20, 9, 0),
                "arrival_at": datetime(2026, 11, 20, 15, 0),
                "schedule_status": "SCHEDULED",
            },
            {"total": 0},  # no bookings
        ]
        result = update_schedule(1, {"schedule_status": "CANCELLED"}, connection_factory=lambda: self.connection)
        self.assertEqual(result["schedule_status"], "CANCELLED")

    def test_update_schedule_not_found(self):
        self.cursor.fetchone.return_value = None
        with self.assertRaises(LookupError):
            update_schedule(999, {"schedule_status": "CANCELLED"}, connection_factory=lambda: self.connection)

    def test_update_schedule_conflict_with_bookings(self):
        dep = datetime(2026, 11, 20, 9, 0)
        arr = datetime(2026, 11, 20, 15, 0)
        self.cursor.fetchone.side_effect = [
            {
                "schedule_id": 1, "train_id": 1, "route_id": 2,
                "departure_at": dep, "arrival_at": arr,
                "schedule_status": "SCHEDULED",
            },
            {"total": 5},  # has bookings
        ]
        self.cursor.fetchall.return_value = [
            {"route_stop_id": 101, "station_id": 1, "stop_sequence": 1, "distance_from_origin_km": Decimal("0")},
            {"route_stop_id": 102, "station_id": 2, "stop_sequence": 2, "distance_from_origin_km": Decimal("500")},
        ]
        with self.assertRaises(ScheduleConflictError):
            update_schedule(1, {
                "train_id": 1, "route_id": 2,
                "departure_at": dep + timedelta(hours=1),
                "arrival_at": arr + timedelta(hours=1),
            }, connection_factory=lambda: self.connection)


if __name__ == "__main__":
    unittest.main()
