"""Regression checks for the database indexes added for Issue #41."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INDEXES = (
    "idx_stations_active_city",
    "idx_schedule_stops_station_departure",
    "idx_schedule_stops_station_arrival",
    "idx_route_fares_segment_price",
    "idx_bookings_user_departure_created",
    "idx_seat_allocations_booking_passenger",
)


class DatabasePerformanceSchemaTests(unittest.TestCase):
    def test_performance_indexes_exist_in_fresh_schema_and_upgrade_migration(self):
        schema = (ROOT / "database" / "schema.sql").read_text()
        migration = (
            ROOT / "database" / "migrations"
            / "002_add_search_booking_indexes.sql"
        ).read_text()

        for index_name in INDEXES:
            with self.subTest(index=index_name):
                self.assertIn(index_name, schema)
                self.assertIn(index_name, migration)

    def test_migration_skips_indexes_that_already_exist(self):
        migration = (
            ROOT / "database" / "migrations"
            / "002_add_search_booking_indexes.sql"
        ).read_text()
        self.assertIn("information_schema.statistics", migration)
        self.assertIn("DROP PROCEDURE apply_index_if_missing", migration)


if __name__ == "__main__":
    unittest.main()
