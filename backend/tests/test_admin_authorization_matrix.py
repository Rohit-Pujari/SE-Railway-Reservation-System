"""Regression matrix proving passenger sessions cannot invoke admin data/actions."""

import unittest

from backend.tests.drf_client import RailwayAPIClient, set_session


ADMIN_ENDPOINTS = [
    ("POST", "/api/admin/logout"),
    ("GET", "/api/admin/dashboard"),
    ("GET", "/api/admin/cancellations"),
    ("GET", "/api/admin/bookings/1"),
    ("POST", "/api/admin/trains"),
    ("PATCH", "/api/admin/trains/1"),
    ("DELETE", "/api/admin/trains/1"),
    ("POST", "/api/admin/stations"),
    ("PATCH", "/api/admin/stations/1"),
    ("POST", "/api/admin/routes"),
    ("PATCH", "/api/admin/routes/1"),
    ("POST", "/api/admin/train-routes"),
    ("DELETE", "/api/admin/train-routes"),
    ("POST", "/api/admin/schedules"),
    ("PATCH", "/api/admin/schedules/1"),
    ("GET", "/api/admin/schedules/1/seats"),
    ("PATCH", "/api/admin/schedules/1/seats/2"),
]


class AdminAuthorizationMatrixTests(unittest.TestCase):
    def setUp(self):
        self.client = RailwayAPIClient()

    def _request(self, method, path):
        return self.client.generic(
            method,
            path,
            data="{}",
            content_type="application/json",
        )

    def test_anonymous_users_are_rejected_from_every_admin_action(self):
        for method, path in ADMIN_ENDPOINTS:
            with self.subTest(method=method, path=path):
                response = self._request(method, path)
                self.assertEqual(response.status_code, 401)

    def test_passengers_are_forbidden_from_every_admin_action(self):
        set_session(self.client, user_id=42, role="PASSENGER")
        for method, path in ADMIN_ENDPOINTS:
            with self.subTest(method=method, path=path):
                response = self._request(method, path)
                self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
