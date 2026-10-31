"""Validation, uniqueness, and authorization tests for administrator train creation."""

import unittest
from unittest.mock import MagicMock, patch

from backend.app.train_management import (
    DuplicateTrainNumberError,
    TrainValidationError,
    create_train,
    validate_train_details,
)
from backend.tests.drf_client import RailwayAPIClient, set_session


class TrainDetailsValidationTests(unittest.TestCase):
    def test_normalizes_train_number_and_name(self):
        self.assertEqual(
            validate_train_details(" 12627 ", "  Karnataka   Express  "),
            ("12627", "Karnataka Express", "ACTIVE"),
        )

    def test_rejects_missing_required_fields(self):
        for number, name in [(None, "Express"), ("12627", None), (" ", "Express"), ("12627", "  ")]:
            with self.subTest(number=number, name=name):
                with self.assertRaises(TrainValidationError):
                    validate_train_details(number, name)

    def test_rejects_invalid_number_and_overlong_name(self):
        with self.assertRaises(TrainValidationError):
            validate_train_details("12/627", "Express")
        with self.assertRaises(TrainValidationError):
            validate_train_details("12627", "X" * 151)

    def test_rejects_invalid_status(self):
        with self.assertRaises(TrainValidationError):
            validate_train_details("12627", "Express", "PAUSED")


class CreateTrainServiceTests(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        self.cursor = MagicMock()
        self.connection.cursor.return_value = self.cursor
        self.cursor.fetchone.return_value = None
        self.cursor.lastrowid = 42

    def test_inserts_and_commits_valid_train(self):
        result = create_train("12627", "Karnataka Express", connection_factory=lambda: self.connection)
        self.assertEqual(result, {
            "train_id": 42, "train_number": "12627",
            "train_name": "Karnataka Express", "train_status": "ACTIVE",
        })
        self.cursor.execute.assert_any_call(
            "INSERT INTO trains (train_number, train_name, train_status) VALUES (%s, %s, %s)",
            ("12627", "Karnataka Express", "ACTIVE"),
        )
        self.connection.commit.assert_called_once_with()
        self.connection.close.assert_called_once_with()

    def test_rejects_duplicate_number_without_insert(self):
        self.cursor.fetchone.return_value = (7,)
        with self.assertRaises(DuplicateTrainNumberError):
            create_train("12627", "Karnataka Express", connection_factory=lambda: self.connection)
        self.assertEqual(self.cursor.execute.call_count, 1)
        self.connection.rollback.assert_called_once_with()
        self.connection.close.assert_called_once_with()


class AdminTrainCreationEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = RailwayAPIClient()

    def test_anonymous_user_cannot_add_train(self):
        response = self.client.post("/api/admin/trains", data={"train_number": "12627", "train_name": "Express"}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_passenger_cannot_add_train(self):
        set_session(self.client, user_id=12, role="PASSENGER")
        response = self.client.post("/api/admin/trains", data={"train_number": "12627", "train_name": "Express"}, format="json")
        self.assertEqual(response.status_code, 403)

    @patch("backend.app.train_management.create_train")
    def test_admin_can_add_train(self, create_train_mock):
        set_session(self.client, user_id=7, role="ADMIN")
        create_train_mock.return_value = {
            "train_id": 42, "train_number": "12627",
            "train_name": "Karnataka Express", "train_status": "ACTIVE",
        }
        response = self.client.post(
            "/api/admin/trains",
            data={"train_number": "12627", "train_name": "Karnataka Express"},
            format="json",
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["train"]["train_id"], 42)
        create_train_mock.assert_called_once_with("12627", "Karnataka Express", "ACTIVE")

    @patch("backend.app.train_management.create_train", side_effect=DuplicateTrainNumberError("A train with this train number already exists."))
    def test_duplicate_number_returns_conflict(self, create_train_mock):
        set_session(self.client, user_id=7, role="ADMIN")
        response = self.client.post(
            "/api/admin/trains",
            data={"train_number": "12627", "train_name": "Karnataka Express"},
            format="json",
        )
        self.assertEqual(response.status_code, 409)


if __name__ == "__main__":
    unittest.main()
