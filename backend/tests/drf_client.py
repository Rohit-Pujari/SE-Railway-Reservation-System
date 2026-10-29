"""DRF APIClient helpers for CSRF-protected requests and signed sessions."""

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.config.settings")

import django

django.setup()

from django.conf import settings
from rest_framework.test import APIClient


class RailwayAPIClient(APIClient):
    """Send JSON and CSRF tokens as the React client does."""

    def post(self, path, data=None, format=None, content_type=None, **extra):
        if "json" in extra:
            data = extra.pop("json")
            format = "json"
        csrf_response = self.get("/api/csrf")
        extra.setdefault("HTTP_X_CSRFTOKEN", csrf_response.json()["csrfToken"])
        return super().post(path, data=data, format=format, content_type=content_type, **extra)


def set_session(client, **values):
    """Seed the signed-cookie session with the same claims the login view uses."""
    session = client.session
    session.update(values)
    session.save()
    client.cookies[settings.SESSION_COOKIE_NAME] = session.session_key
