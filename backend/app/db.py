"""MySQL connection helper. Database schema and queries are added separately."""

import mysql.connector
from mysql.connector import MySQLConnection

from .config import Config


def get_db_connection() -> MySQLConnection:
    """Open a MySQL connection using the current environment configuration."""
    return mysql.connector.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        database=Config.DB_NAME,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        connection_timeout=5,
    )
