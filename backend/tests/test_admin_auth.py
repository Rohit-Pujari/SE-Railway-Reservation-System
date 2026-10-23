"""Tests for administrator login and role-protected API routes."""

import unittest
from unittest.mock import MagicMock, patch

from werkzeug.security import generate_password_hash

from backend.app import create_app


class AdminAuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY="test-secret-key")
        self.client = self.app.test_client()

    @patch("backend.app.routes.get_db_connection")
    def test_admin_can_login_and_access_admin_endpoint(self, get_connection):
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
        self.assertEqual(self.client.get("/api/admin/dashboard").status_code, 200)
        cursor.execute.assert_called_once_with(
            unittest.mock.ANY, ("admin@example.com",)
        )
        connection.close.assert_called_once()

    def test_dashboard_rejects_anonymous_request(self):
        response = self.client.get("/api/admin/dashboard")
        self.assertEqual(response.status_code, 401)

    def test_dashboard_rejects_passenger_session(self):
        with self.client.session_transaction() as session:
            session["user_id"] = 10
            session["role"] = "PASSENGER"
        response = self.client.get("/api/admin/dashboard")
        self.assertEqual(response.status_code, 403)

    @patch("backend.app.routes.get_db_connection")
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
        self.assertEqual(self.client.get("/api/admin/dashboard").status_code, 401)

    @patch("backend.app.routes.get_db_connection")
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
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.get("/api/admin/dashboard").status_code, 401)

    @patch("backend.app.routes.get_db_connection")
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
        with self.client.session_transaction() as session:
            session["user_id"] = 7
            session["role"] = "ADMIN"
        response = self.client.post("/api/admin/logout")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/admin/dashboard").status_code, 401)


if __name__ == "__main__":
    unittest.main()
