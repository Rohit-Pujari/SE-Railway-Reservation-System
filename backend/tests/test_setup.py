"""Smoke tests for the initial application scaffold."""

import unittest

from backend.app import create_app


class ApplicationSetupTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_health_endpoint(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")

    def test_frontend_homepage_is_served(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Railway Reservation System", response.data)

    def test_frontend_assets_are_served(self):
        self.assertEqual(self.client.get("/styles.css").status_code, 200)
        self.assertEqual(self.client.get("/app.js").status_code, 200)


if __name__ == "__main__":
    unittest.main()
