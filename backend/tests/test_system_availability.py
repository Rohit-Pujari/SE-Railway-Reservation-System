"""Availability, graceful degradation, and restart-recovery regression tests."""

import unittest
from unittest.mock import MagicMock, patch

import mysql.connector
from django.conf import settings

from backend.tests.drf_client import RailwayAPIClient, set_session


class SystemAvailabilityEndpointTests(unittest.TestCase):
    def setUp(self):
        self.client = RailwayAPIClient()

    def test_api_health_remains_available_when_database_is_down(self):
        with patch(
            "backend.app.django_views.get_db_connection",
            side_effect=mysql.connector.Error("private database details"),
        ):
            response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {
            "status": "ok",
            "service": "railway-reservation-api",
        })

    def test_database_health_returns_service_unavailable_without_leaking_details(self):
        with patch(
            "backend.app.django_views.get_db_connection",
            side_effect=mysql.connector.Error("private database details"),
        ):
            response = self.client.get("/api/health/db")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json(), {
            "status": "error",
            "database": "unavailable",
        })
        self.assertNotIn("private database details", response.content.decode())

    def test_database_health_recovers_after_database_connection_returns(self):
        connection = MagicMock()
        connection.is_connected.return_value = True

        with patch(
            "backend.app.django_views.get_db_connection",
            side_effect=[mysql.connector.Error("temporary outage"), connection],
        ) as connect:
            unavailable = self.client.get("/api/health/db")
            recovered = self.client.get("/api/health/db")

        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(recovered.status_code, 200)
        self.assertEqual(recovered.json(), {"status": "ok", "database": "connected"})
        self.assertEqual(connect.call_count, 2)
        connection.close.assert_called_once()

    def test_signed_session_can_be_restored_by_a_fresh_client_after_worker_restart(self):
        # Signed-cookie sessions are self-contained and do not depend on an
        # in-memory session store owned by the previous Django worker.
        original_client = RailwayAPIClient()
        set_session(original_client, user_id=73, role="PASSENGER")
        signed_cookie = original_client.cookies[settings.SESSION_COOKIE_NAME].value

        restarted_client = RailwayAPIClient()
        restarted_client.cookies[settings.SESSION_COOKIE_NAME] = signed_cookie
        restored_session = restarted_client.session

        self.assertEqual(restored_session["user_id"], 73)
        self.assertEqual(restored_session["role"], "PASSENGER")

    def test_database_dependent_endpoint_returns_retryable_error_during_outage(self):
        with patch(
            "backend.app.django_views.get_active_stations",
            side_effect=mysql.connector.Error("private database details"),
        ):
            response = self.client.get("/api/stations")

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["status"], "error")
        self.assertNotIn("private database details", response.content.decode())


if __name__ == "__main__":
    unittest.main()
