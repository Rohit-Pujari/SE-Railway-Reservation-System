"""MySQL connection settings loaded from environment variables."""
import os
from dotenv import load_dotenv
load_dotenv()

class DatabaseConfig:
    DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
    DB_PORT = int(os.getenv("DB_PORT", "3306"))
    DB_NAME = os.getenv("DB_NAME", "railway_reservation")
    DB_USER = os.getenv("DB_USER", "root")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
