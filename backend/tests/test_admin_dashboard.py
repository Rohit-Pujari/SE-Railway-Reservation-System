"""Authorization and response tests for the administrator dashboard."""

import unittest
from unittest.mock import patch

from backend.tests.drf_client import RailwayAPIClient, set_session


class AdminDashboardEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = RailwayAPIClient()

    def test_anonymous_user_cannot_read_dashboard(self):
        response = self.client.get("/api/admin/dashboard")
        self.assertEqual(response.status_code, 401)

    def test_passenger_cannot_read_dashboard(self):
        set_session(self.client, user_id=12, role="PASSENGER")
        response = self.client.get("/api/admin/dashboard")
        self.assertEqual(response.status_code, 403)

    @patch("backend.app.admin_dashboard.get_admin_dashboard")
    def test_admin_can_read_dashboard_sections(self, get_dashboard):
        set_session(self.client, user_id=7, role="ADMIN")
        get_dashboard.return_value = {
            "summary": {"total_trains": 1, "total_routes": 1, "total_schedules": 1,
                        "total_bookings": 2, "active_bookings": 1,
                        "cancelled_bookings": 1, "total_cancellations": 1},
            "trains": [{"train_id": 1, "train_number": "12001", "train_name": "Test Express",
                        "train_status": "ACTIVE"}],
            "routes": [], "schedules": [], "bookings": [], "cancellations": [],
        }
        response = self.client.get("/api/admin/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["trains"][0]["train_number"], "12001")
        self.assertIn("cancellations", response.json())
        get_dashboard.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
