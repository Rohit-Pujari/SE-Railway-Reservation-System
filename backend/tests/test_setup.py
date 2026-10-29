"""Smoke tests for the application scaffold."""

import unittest

from pathlib import Path
from django.test import Client

from backend.tests.drf_client import RailwayAPIClient, set_session


class ApplicationSetupTests(unittest.TestCase):
    def setUp(self):
        self.client = RailwayAPIClient()

    def test_health_endpoint(self):
        response = self.client.get("/api/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

    @unittest.skipUnless(
        (Path(__file__).resolve().parents[2] / "frontend" / "dist" / "index.html").is_file(),
        "Build the React frontend to test the served homepage.",
    )
    def test_frontend_homepage_is_served(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Trackline", response.content)

    @unittest.skipUnless(
        (Path(__file__).resolve().parents[2] / "frontend" / "dist" / "assets").is_dir(),
        "Build the React frontend to test served asset files.",
    )
    def test_frontend_assets_are_served(self):
        built_assets = Path(__file__).resolve().parents[2] / "frontend" / "dist" / "assets"
        assets = list(built_assets.iterdir())
        stylesheet = next(path for path in assets if path.suffix == ".css")
        script = next(path for path in assets if path.suffix == ".js")
        self.assertEqual(self.client.get(f"/assets/{stylesheet.name}").status_code, 200)
        self.assertEqual(self.client.get(f"/assets/{script.name}").status_code, 200)

    def test_csrf_protects_session_mutations(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post("/api/logout").status_code, 403)
        token_response = client.get("/api/csrf")
        token = token_response.json()["csrfToken"]
        response = client.post("/api/logout", HTTP_X_CSRFTOKEN=token)
        self.assertEqual(response.status_code, 200)


if __name__ == "__main__":
    unittest.main()
