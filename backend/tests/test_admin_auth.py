"""Tests for administrator login and logout."""

import unittest
from unittest.mock import MagicMock, patch

from werkzeug.security import generate_password_hash

from backend.tests.drf_client import RailwayAPIClient, set_session


class AdminAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.client = RailwayAPIClient()

    @patch("backend.app.django_views.get_db_connection")
    def test_admin_can_login_and_logout(self, get_connection):
        connection = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "user_id": 7,
            "email": "admin@example.com",
            "password_hash": generate_password_hash("AdminPass123"),
            "role": "ADMIN",
            "account_status": "ACTIVE",
        }
        connection.cursor.return_value = cursor
        get_connection.return_value = connection

        response = self.client.post(
            "/api/admin/login",
            json={"email": "ADMIN@example.com", "password": "AdminPass123"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.session["role"], "ADMIN")
        self.assertEqual(self.client.post("/api/admin/logout").status_code, 200)
        self.assertNotIn("role", self.client.session)
        cursor.execute.assert_called_once_with(
            unittest.mock.ANY, ("admin@example.com",)
        )
        connection.close.assert_called_once()

    def test_passenger_cannot_use_admin_logout(self):
        set_session(self.client, user_id=10, role="PASSENGER")
        response = self.client.post("/api/admin/logout")
        self.assertEqual(response.status_code, 403)

    @patch("backend.app.django_views.get_db_connection")
    def test_invalid_password_is_rejected(self, get_connection):
        connection = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "user_id": 7,
            "email": "admin@example.com",
            "password_hash": generate_password_hash("CorrectPass123"),
            "role": "ADMIN",
            "account_status": "ACTIVE",
        }
        connection.cursor.return_value = cursor
        get_connection.return_value = connection
        response = self.client.post(
            "/api/admin/login",
            json={"email": "admin@example.com", "password": "WrongPass123"},
        )
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("role", self.client.session)

    @patch("backend.app.django_views.get_db_connection")
    def test_passenger_cannot_login_to_admin_endpoint(self, get_connection):
        connection = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "user_id": 10,
            "email": "passenger@example.com",
            "password_hash": generate_password_hash("Passenger123"),
            "role": "PASSENGER",
            "account_status": "ACTIVE",
        }
        connection.cursor.return_value = cursor
        get_connection.return_value = connection
        response = self.client.post(
            "/api/admin/login",
            json={"email": "passenger@example.com", "password": "Passenger123"},
        )
        # Keep login failures indistinguishable so the endpoint does not
        # reveal whether an account is a passenger or an administrator.
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("role", self.client.session)

    @patch("backend.app.django_views.get_db_connection")
    def test_disabled_admin_is_rejected(self, get_connection):
        connection = MagicMock()
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "user_id": 7,
            "email": "admin@example.com",
            "password_hash": generate_password_hash("AdminPass123"),
            "role": "ADMIN",
            "account_status": "DISABLED",
        }
        connection.cursor.return_value = cursor
        get_connection.return_value = connection
        response = self.client.post(
            "/api/admin/login",
            json={"email": "admin@example.com", "password": "AdminPass123"},
        )
        self.assertEqual(response.status_code, 401)

    def test_logout_clears_admin_session(self):
        set_session(self.client, user_id=7, role="ADMIN")
        response = self.client.post("/api/admin/logout")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("role", self.client.session)


if __name__ == "__main__":
    unittest.main()
