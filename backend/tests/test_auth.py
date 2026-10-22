"""Tests for login, session restoration, and logout."""
import unittest
from unittest.mock import MagicMock, patch

from backend.app import create_app


class AuthenticationEndpointTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config.update(TESTING=True, SECRET_KEY="test-session-secret")
        self.client = self.app.test_client()

    def test_login_requires_json_credentials(self):
        response = self.client.post("/api/login", json={"email": "", "password": ""})
        self.assertEqual(response.status_code, 400)

    @patch("backend.app.routes.get_db_connection")
    def test_invalid_credentials_return_generic_401(self, get_connection):
        connection = MagicMock()
        connection.cursor.return_value.fetchone.return_value = None
        get_connection.return_value = connection
        response = self.client.post("/api/login", json={"email": "unknown@example.com", "password": "BadPass1"})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json["message"], "Invalid email or password.")
        connection.close.assert_called_once()

    @patch("backend.app.routes.check_password_hash", return_value=True)
    @patch("backend.app.routes.get_db_connection")
    def test_successful_login_creates_session(self, get_connection, check_hash):
        connection = MagicMock()
        connection.cursor.return_value.fetchone.return_value = {
            "user_id": 7, "full_name": "Aditi Rao", "email": "aditi@example.com", "password_hash": "stored-hash"
        }
        get_connection.return_value = connection
        response = self.client.post("/api/login", json={"email": "ADITI@example.com", "password": "StrongPass1"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["user"]["id"], 7)
        connection.cursor.return_value.execute.assert_called_once()
        self.assertIn("aditi@example.com", connection.cursor.return_value.execute.call_args.args[1])
        session_response = self.client.get("/api/session")
        self.assertEqual(session_response.status_code, 200)
        self.assertTrue(session_response.json["authenticated"])
        self.assertEqual(session_response.json["user"]["email"], "aditi@example.com")
        connection.close.assert_called_once()

    def test_session_requires_login(self):
        response = self.client.get("/api/session")
        self.assertEqual(response.status_code, 401)
        self.assertFalse(response.json["authenticated"])

    def test_logout_clears_session(self):
        with self.client.session_transaction() as current:
            current["user_id"] = 7
            current["user_name"] = "Aditi Rao"
            current["user_email"] = "aditi@example.com"
        response = self.client.post("/api/logout")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get("/api/session").status_code, 401)

    @patch("backend.app.routes.get_db_connection")
    def test_database_failure_is_safe(self, get_connection):
        get_connection.side_effect = RuntimeError("database password must not leak")
        response = self.client.post("/api/login", json={"email": "a@example.com", "password": "StrongPass1"})
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("database password", response.get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()
