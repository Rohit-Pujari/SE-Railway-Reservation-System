"""Configuration loaded from environment variables."""
import os
import secrets
from dotenv import load_dotenv
load_dotenv()

class Config:
    APP_HOST = os.getenv("APP_HOST", "127.0.0.1")
    APP_PORT = int(os.getenv("APP_PORT", "5000"))
    APP_DEBUG = os.getenv("APP_DEBUG", "false").strip().lower() in {"1", "true", "yes"}
    SECRET_KEY = os.getenv("SECRET_KEY") or secrets.token_hex(32)
    PERMANENT_SESSION_LIFETIME = 1800
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "false").strip().lower() in {"1", "true", "yes"}
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_NAME = os.getenv("DB_NAME", "railway_reservation")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
