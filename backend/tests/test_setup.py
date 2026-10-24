"""Smoke tests for the application scaffold."""

import unittest

from backend.app import create_app


class ApplicationSetupTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app()
        self.app.config["TESTING"] = True
        self.client = self.app.test_client()

    def test_health_endpoint(self):
        with self.client.get("/api/health") as response:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.get_json()["status"], "ok")

    def test_frontend_homepage_is_served(self):
        with self.client.get("/") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"Railway Reservation System", response.data)

    def test_frontend_assets_are_served(self):
        with self.client.get("/styles.css") as css_response:
            self.assertEqual(css_response.status_code, 200)
        with self.client.get("/app.js") as js_response:
            self.assertEqual(js_response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
