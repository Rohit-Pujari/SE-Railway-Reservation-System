import unittest
from unittest.mock import MagicMock, patch
from backend.app.train_management import remove_train
from backend.tests.drf_client import RailwayAPIClient, set_session

class RemoveTrainServiceTests(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        self.cursor = MagicMock()
        self.connection.cursor.return_value = self.cursor
        self.cursor.fetchone.side_effect = [
            {"train_id": 42, "train_number": "12627", "train_name": "Karnataka Express", "train_status": "ACTIVE"},
            {"schedule_count": 0, "booking_count": 0},
        ]
        self.cursor.rowcount = 1

    def test_deletes_train_and_seats_when_no_schedule_exists(self):
        result = remove_train(42, connection_factory=lambda: self.connection)
        self.assertEqual(result["action"], "deleted")
        self.cursor.execute.assert_any_call("DELETE FROM seats WHERE train_id = %s", (42,))
        self.cursor.execute.assert_any_call("DELETE FROM trains WHERE train_id = %s", (42,))
        self.connection.commit.assert_called_once_with()

    def test_deactivates_train_with_booking_history(self):
        self.cursor.fetchone.side_effect = [
            {"train_id": 42, "train_number": "12627", "train_name": "Karnataka Express", "train_status": "ACTIVE"},
            {"schedule_count": 2, "booking_count": 3},
        ]
        result = remove_train(42, connection_factory=lambda: self.connection)
        self.assertEqual(result["action"], "deactivated")
        self.assertIn("booking history", result["message"])
        self.assertFalse(any("DELETE FROM trains" in str(call) for call in self.cursor.execute.call_args_list))

    def test_deactivates_train_with_schedules_even_without_bookings(self):
        self.cursor.fetchone.side_effect = [
            {"train_id": 42, "train_number": "12627", "train_name": "Karnataka Express", "train_status": "ACTIVE"},
            {"schedule_count": 1, "booking_count": 0},
        ]
        result = remove_train(42, connection_factory=lambda: self.connection)
        self.assertEqual(result["action"], "deactivated")
        self.assertIn("existing schedules", result["message"])

    def test_missing_train_raises_lookup_error(self):
        self.cursor.fetchone.side_effect = None
        self.cursor.fetchone.return_value = None
        with self.assertRaises(LookupError):
            remove_train(42, connection_factory=lambda: self.connection)
        self.connection.rollback.assert_called_once_with()

    def test_invalid_id_is_rejected_before_connecting(self):
        with self.assertRaises(ValueError):
            remove_train("invalid", connection_factory=lambda: self.connection)
        self.connection.cursor.assert_not_called()

class AdminTrainRemovalEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = RailwayAPIClient()

    def test_anonymous_user_cannot_remove_train(self):
        response = self.client.delete("/api/admin/trains/42")
        self.assertEqual(response.status_code, 401)

    def test_passenger_cannot_remove_train(self):
        set_session(self.client, user_id=12, role="PASSENGER")
        response = self.client.delete("/api/admin/trains/42")
        self.assertEqual(response.status_code, 403)

    @patch("backend.app.train_management.remove_train")
    def test_admin_can_remove_train(self, remove_train_mock):
        set_session(self.client, user_id=7, role="ADMIN")
        remove_train_mock.return_value = {"train_id": 42, "action": "deleted", "message": "Train removed successfully."}
        response = self.client.delete("/api/admin/trains/42")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["train"]["action"], "deleted")
        remove_train_mock.assert_called_once_with(42)

    @patch("backend.app.train_management.remove_train", side_effect=LookupError("Train not found."))
    def test_missing_train_returns_404(self, remove_train_mock):
        set_session(self.client, user_id=7, role="ADMIN")
        response = self.client.delete("/api/admin/trains/42")
        self.assertEqual(response.status_code, 404)

if __name__ == "__main__":
    unittest.main()
