"""Tests for administrator cancellation and refund records."""
import unittest
from unittest.mock import patch
from backend.app.admin_cancellation_records import get_admin_cancellation_records
from backend.tests.drf_client import RailwayAPIClient, set_session

class FakeCursor:
    def __init__(self, records):
        self.records, self.query, self.closed = records, None, False
    def execute(self, query): self.query = query
    def fetchall(self): return self.records
    def close(self): self.closed = True

class FakeConnection:
    def __init__(self, records):
        self.cursor_instance, self.closed = FakeCursor(records), False
    def cursor(self, dictionary=False):
        if not dictionary: raise AssertionError("Expected dictionary cursor.")
        return self.cursor_instance
    def close(self): self.closed = True

class AdminCancellationRecordServiceTests(unittest.TestCase):
    def test_returns_refund_and_passenger_details_and_closes_connection(self):
        from datetime import datetime
        from decimal import Decimal
        requested = datetime(2026, 10, 31, 10, 30)
        connection = FakeConnection([{
            "cancellation_id": 8, "cancellation_status": "COMPLETED", "requested_at": requested,
            "cancellation_charge": Decimal("50.00"), "expected_refund_amount": Decimal("800.00"),
            "refund_amount": Decimal("800.00"), "refund_status": "SUCCEEDED",
            "passenger_name": "Test Passenger", "pnr": "ABC123",
        }])
        records = get_admin_cancellation_records(connection_factory=lambda: connection)
        self.assertEqual(records[0]["refund_status"], "SUCCEEDED")
        self.assertEqual(records[0]["passenger_name"], "Test Passenger")
        self.assertEqual(records[0]["cancellation_charge"], 50.0)
        self.assertEqual(records[0]["refund_amount"], 800.0)
        self.assertEqual(records[0]["requested_at"], requested.isoformat())
        self.assertIn("LEFT JOIN refunds", connection.cursor_instance.query)
        self.assertTrue(connection.cursor_instance.closed)
        self.assertTrue(connection.closed)

    def test_returns_empty_list_when_no_cancellations_exist(self):
        connection = FakeConnection([])
        self.assertEqual(get_admin_cancellation_records(connection_factory=lambda: connection), [])

class AdminCancellationRecordEndpointTests(unittest.TestCase):
    def setUp(self): self.client = RailwayAPIClient()
    def test_anonymous_user_cannot_read_cancellation_records(self):
        self.assertEqual(self.client.get("/api/admin/cancellations").status_code, 401)
    def test_passenger_cannot_read_cancellation_records(self):
        set_session(self.client, user_id=12, role="PASSENGER")
        self.assertEqual(self.client.get("/api/admin/cancellations").status_code, 403)
    @patch("backend.app.admin_cancellation_records.get_admin_cancellation_records")
    def test_admin_can_read_cancellation_and_refund_details(self, get_records):
        set_session(self.client, user_id=7, role="ADMIN")
        get_records.return_value = [{"cancellation_id": 8, "pnr": "ABC123",
            "passenger_name": "Test Passenger", "refund_status": "SUCCEEDED", "refund_amount": 800.0}]
        response = self.client.get("/api/admin/cancellations")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["cancellations"][0]["refund_status"], "SUCCEEDED")
        self.assertEqual(response.json()["cancellations"][0]["refund_amount"], 800.0)
        get_records.assert_called_once_with()

if __name__ == "__main__": unittest.main()
