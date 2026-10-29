"""MySQL connection helper. Database schema and queries are added separately."""

import mysql.connector
from mysql.connector import MySQLConnection

from .config import DatabaseConfig


def get_db_connection() -> MySQLConnection:
    """Open a MySQL connection using the current environment configuration."""
    return mysql.connector.connect(
        host=DatabaseConfig.DB_HOST,
        port=DatabaseConfig.DB_PORT,
        database=DatabaseConfig.DB_NAME,
        user=DatabaseConfig.DB_USER,
        password=DatabaseConfig.DB_PASSWORD,
        connection_timeout=5,
    )
