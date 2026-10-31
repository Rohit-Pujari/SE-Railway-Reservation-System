"""Regression checks for the Django/DRF + React runtime architecture."""

import json
import os
import subprocess
import unittest
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")

import django

django.setup()

from django.conf import settings
from django.urls import resolve

from backend.config.urls import urlpatterns


ROOT = Path(__file__).resolve().parents[2]


class DjangoReactArchitectureTests(unittest.TestCase):
    def test_reservation_apis_are_drf_views_with_csrf_protection(self):
        api_paths = [
            "api/health",
            "api/health/db",
            "api/register",
            "api/login",
            "api/session",
            "api/logout",
            "api/admin/login",
            "api/admin/logout",
            "api/travel-classes",
            "api/seats/availability",
            "api/stations",
            "api/trains/search",
            "api/bookings",
            "api/bookings/history",
            "api/bookings/status",
            "api/bookings/1/passengers",
            "api/bookings/1/fare",
        ]
        for path in api_paths:
            with self.subTest(path=path):
                callback = resolve(f"/{path}").func
                self.assertTrue(hasattr(callback, "cls"), "API routes should be dispatched by DRF views.")
                self.assertFalse(getattr(callback, "csrf_exempt", False))

    def test_mysql_and_session_settings_do_not_require_new_schema_tables(self):
        self.assertEqual(settings.DATABASES["default"]["ENGINE"], "mysql.connector.django")
        self.assertEqual(settings.SESSION_ENGINE, "django.contrib.sessions.backends.signed_cookies")
        self.assertNotIn("django.contrib.sessions", settings.INSTALLED_APPS)
        self.assertEqual(len(urlpatterns), 20)

    def test_react_frontend_has_locked_build_and_runtime_entry(self):
        package = json.loads((ROOT / "frontend" / "package.json").read_text())
        lock = json.loads((ROOT / "frontend" / "package-lock.json").read_text())
        self.assertIn("react", package["dependencies"])
        self.assertIn("react-dom", package["dependencies"])
        self.assertEqual(lock["packages"][""]["name"], package["name"])
        self.assertTrue((ROOT / "frontend" / "src" / "main.jsx").is_file())

    def test_one_command_launcher_is_valid_shell_and_starts_both_servers(self):
        launcher = ROOT / "run-dev.sh"
        subprocess.run(["bash", "-n", str(launcher)], check=True)
        contents = launcher.read_text()
        self.assertIn("backend.manage runserver", contents)
        self.assertIn("node_modules/.bin/vite", contents)
        self.assertIn('cd "$ROOT_DIR/frontend"', contents)
        self.assertIn("wait -n", contents)


if __name__ == "__main__":
    unittest.main()
