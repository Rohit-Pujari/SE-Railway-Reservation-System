"""Django and DRF settings; business data continues to use the existing MySQL schema."""

import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def _env_bool(name, default=False):
    """Parse a boolean environment setting without treating 'false' as true."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
DEBUG = _env_bool("APP_DEBUG", False)
ALLOWED_HOSTS = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",") if host.strip()]
if "testserver" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("testserver")
ROOT_URLCONF = "backend.config.urls"
WSGI_APPLICATION = "backend.config.wsgi.application"
ASGI_APPLICATION = "backend.config.asgi.application"

INSTALLED_APPS = ["rest_framework"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]

TEMPLATES = []
USE_TZ = True
TIME_ZONE = os.getenv("TIME_ZONE", "Asia/Kolkata")
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# The application uses parameterized mysql-connector-python queries and deliberately
# does not migrate or create Django-owned tables in the supplied reservation schema.
DATABASES = {
    "default": {
        "ENGINE": "mysql.connector.django",
        "NAME": os.getenv("DB_NAME", "railway_reservation"),
        "USER": os.getenv("DB_USER", "root"),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "3306"),
    }
}

SESSION_ENGINE = "django.contrib.sessions.backends.signed_cookies"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
# Cookies must only travel over HTTPS by default outside local development.
# Deployments may explicitly override this when TLS terminates elsewhere.
SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", default=not DEBUG)
SESSION_COOKIE_AGE = 1800
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = _env_bool("CSRF_COOKIE_SECURE", default=SESSION_COOKIE_SECURE)
CSRF_TRUSTED_ORIGINS = [
    origin.strip() for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()
]

# Add browser-side protections to every response. HSTS is intentionally opt-in
# because it is safe only after the deployment is confirmed to serve HTTPS.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "0"))

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "UNAUTHENTICATED_USER": None,
}

FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
