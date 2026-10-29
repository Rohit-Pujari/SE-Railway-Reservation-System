"""Unit tests for registration validation, persistence, and API errors."""

import unittest
from unittest.mock import MagicMock, patch

import mysql.connector
from werkzeug.security import check_password_hash

from backend.tests.drf_client import RailwayAPIClient, set_session
from backend.app.registration import (
    PASSWORD_MAX_LENGTH,
    RegistrationValidationError,
    register_user,
    validate_registration,
)

VALID = {
    "full_name": "Aditi Rao",
    "email": "Aditi.Rao@example.com",
    "phone_number": "9876543210",
    "password": "StrongPass1",
}


class RegistrationServiceTests(unittest.TestCase):
    def test_validation_normalizes_email(self):
        self.assertEqual(validate_registration(VALID)["email"], "aditi.rao@example.com")

    def test_missing_required_fields_rejected(self):
        for field in ("full_name", "email", "password"):
            with self.subTest(field=field), self.assertRaises(RegistrationValidationError):
                validate_registration(dict(VALID, **{field: ""}))

    def test_invalid_email_rejected(self):
        for email in ("not-an-email", "name@", "@example.com", "two@@example.com"):
            with self.subTest(email=email), self.assertRaises(RegistrationValidationError):
                validate_registration(dict(VALID, email=email))

    def test_password_policy_enforced(self):
        for password in ("short1A", "alllowercase1", "ALLUPPERCASE1", "NoDigitsHere"):
            with self.subTest(password=password), self.assertRaises(RegistrationValidationError):
                validate_registration(dict(VALID, password=password))

    def test_password_over_maximum_length_rejected(self):
        password = "Aa1" + ("x" * PASSWORD_MAX_LENGTH)
        with self.assertRaises(RegistrationValidationError):
            validate_registration(dict(VALID, password=password))

    def test_password_at_maximum_length_is_accepted(self):
        password = "Aa1" + ("x" * (PASSWORD_MAX_LENGTH - 3))
        self.assertEqual(len(validate_registration(dict(VALID, password=password))["password"]), PASSWORD_MAX_LENGTH)

    def test_password_hash_inserted_not_plaintext(self):
        connection = MagicMock()
        connection.cursor.return_value.lastrowid = 42
        result = register_user(VALID, connection_factory=lambda: connection)
        params = connection.cursor.return_value.execute.call_args.args[1]
        stored_hash = params[3]
        self.assertNotEqual(stored_hash, VALID["password"])
        self.assertTrue(check_password_hash(stored_hash, VALID["password"]))
        self.assertEqual(result["user_id"], 42)
        connection.commit.assert_called_once()
        connection.close.assert_called_once()

    def test_database_failure_rolls_back(self):
        connection = MagicMock()
        connection.cursor.return_value.execute.side_effect = mysql.connector.Error("internal detail")
        with self.assertRaises(mysql.connector.Error):
            register_user(VALID, connection_factory=lambda: connection)
        connection.rollback.assert_called_once()
        connection.close.assert_called_once()


class RegistrationEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = RailwayAPIClient()

    @patch("backend.app.django_views.register_user")
    def test_success(self, register):
        register.return_value = {"user_id": 42, "full_name": "Aditi Rao", "email": "aditi.rao@example.com"}
        response = self.client.post("/api/register", json=VALID)
        self.assertEqual(response.status_code, 201)

    @patch("backend.app.django_views.register_user")
    def test_validation_error(self, register):
        register.side_effect = RegistrationValidationError("Enter a valid email address.")
        response = self.client.post("/api/register", json=VALID)
        self.assertEqual(response.status_code, 400)

    @patch("backend.app.django_views.register_user")
    def test_duplicate_key_returns_conflict(self, register):
        register.side_effect = mysql.connector.IntegrityError(errno=1062, msg="duplicate")
        response = self.client.post("/api/register", json=VALID)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["message"], "An account with this email already exists.")

    @patch("backend.app.django_views.register_user")
    def test_non_duplicate_integrity_error_is_safe_server_error(self, register):
        register.side_effect = mysql.connector.IntegrityError(errno=1452, msg="foreign key failure")
        response = self.client.post("/api/register", json=VALID)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("foreign key", response.content.decode())
        self.assertNotIn("1452", response.content.decode())

    @patch("backend.app.django_views.register_user")
    def test_database_error_is_not_leaked(self, register):
        register.side_effect = mysql.connector.Error("secret host/password")
        response = self.client.post("/api/register", json=VALID)
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("secret", response.content.decode())

    @patch("backend.app.django_views.register_user")
    def test_unexpected_error_is_not_leaked(self, register):
        register.side_effect = RuntimeError("private internals")
        response = self.client.post("/api/register", json=VALID)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("private internals", response.content.decode())

    def test_non_json_request_rejected(self):
        response = self.client.post("/api/register", data="not json", content_type="text/plain")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
