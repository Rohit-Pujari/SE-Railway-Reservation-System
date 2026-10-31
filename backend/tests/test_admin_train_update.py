"""Service and endpoint tests for editing and validating existing train details."""

import unittest
from unittest.mock import MagicMock, patch

from backend.app.train_management import (
    DuplicateTrainNumberError,
    TrainValidationError,
    update_train,
)
from backend.tests.drf_client import RailwayAPIClient, set_session


class UpdateTrainServiceTests(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        self.cursor = MagicMock()
        self.connection.cursor.return_value = self.cursor
        self.cursor.fetchone.side_effect = [
            {"train_id": 42, "train_number": "12627", "train_name": "Old Express", "train_status": "ACTIVE"},
            None,
        ]

    def test_updates_and_commits_train_details(self):
        result = update_train(
            42, " 12628 ", "  New   Express ", "INACTIVE",
            connection_factory=lambda: self.connection,
        )
        self.assertEqual(result, {
            "train_id": 42, "train_number": "12628",
            "train_name": "New Express", "train_status": "INACTIVE",
        })
        self.cursor.execute.assert_any_call(
            "UPDATE trains SET train_number = %s, train_name = %s, train_status = %s WHERE train_id = %s",
            ("12628", "New Express", "INACTIVE", 42),
        )
        self.connection.commit.assert_called_once_with()
        self.connection.close.assert_called_once_with()

    def test_keeps_existing_values_when_only_status_is_changed(self):
        result = update_train(42, train_status="INACTIVE", connection_factory=lambda: self.connection)
        self.assertEqual(result["train_number"], "12627")
        self.assertEqual(result["train_name"], "Old Express")
        self.assertEqual(result["train_status"], "INACTIVE")

    def test_rejects_duplicate_train_number(self):
        self.cursor.fetchone.side_effect = [
            {"train_id": 42, "train_number": "12627", "train_name": "Old Express", "train_status": "ACTIVE"},
            {"train_id": 9},
        ]
        with self.assertRaises(DuplicateTrainNumberError):
            update_train(42, train_number="12001", connection_factory=lambda: self.connection)
        self.connection.rollback.assert_called_once_with()
        self.connection.close.assert_called_once_with()

    def test_rejects_invalid_details(self):
        with self.assertRaises(TrainValidationError):
            update_train(42, train_name=" " * 3, connection_factory=lambda: self.connection)
        self.connection.rollback.assert_called_once_with()

    def test_missing_train_is_not_found(self):
        self.cursor.fetchone.side_effect = None
        self.cursor.fetchone.return_value = None
        with self.assertRaises(LookupError):
            update_train(42, train_name="New Name", connection_factory=lambda: self.connection)
        self.connection.rollback.assert_called_once_with()


class AdminTrainUpdateEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = RailwayAPIClient()

    def test_anonymous_user_cannot_update_train(self):
        response = self.client.patch("/api/admin/trains/42", data={"train_name": "Updated"}, format="json")
        self.assertEqual(response.status_code, 401)

    def test_passenger_cannot_update_train(self):
        set_session(self.client, user_id=12, role="PASSENGER")
        response = self.client.patch("/api/admin/trains/42", data={"train_name": "Updated"}, format="json")
        self.assertEqual(response.status_code, 403)

    @patch("backend.app.train_management.update_train")
    def test_admin_can_update_train(self, update_train_mock):
        set_session(self.client, user_id=7, role="ADMIN")
        update_train_mock.return_value = {
            "train_id": 42, "train_number": "12628",
            "train_name": "Updated Express", "train_status": "ACTIVE",
        }
        response = self.client.patch(
            "/api/admin/trains/42",
            data={"train_number": "12628", "train_name": "Updated Express", "train_status": "ACTIVE"},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["train"]["train_name"], "Updated Express")
        update_train_mock.assert_called_once_with(42, "12628", "Updated Express", "ACTIVE")

    @patch("backend.app.train_management.update_train", side_effect=DuplicateTrainNumberError("Duplicate train number."))
    def test_duplicate_train_number_returns_conflict(self, update_train_mock):
        set_session(self.client, user_id=7, role="ADMIN")
        response = self.client.patch("/api/admin/trains/42", data={"train_number": "12001"}, format="json")
        self.assertEqual(response.status_code, 409)

    @patch("backend.app.train_management.update_train", side_effect=TrainValidationError("Train name is required."))
    def test_invalid_details_return_bad_request(self, update_train_mock):
        set_session(self.client, user_id=7, role="ADMIN")
        response = self.client.patch("/api/admin/trains/42", data={"train_name": " "}, format="json")
        self.assertEqual(response.status_code, 400)

    def test_empty_update_is_rejected(self):
        set_session(self.client, user_id=7, role="ADMIN")
        response = self.client.patch("/api/admin/trains/42", data={}, format="json")
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
